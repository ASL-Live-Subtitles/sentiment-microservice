from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
import os
import mysql.connector
from mysql.connector.connection import MySQLConnection
from mysql.connector import Error as MySQLError


def _load_db_config_from_env() -> Dict[str, Any]:
    """Load DB config from environment and validate required fields."""
    host = os.environ.get("DB_HOST")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    database = os.environ.get("DB_NAME")

    missing = [k for k, v in [("DB_HOST", host), ("DB_USER", user), ("DB_PASSWORD", password), ("DB_NAME", database)] if not v]
    if missing:
        raise RuntimeError(f"Missing required DB env vars: {', '.join(missing)}")

    # Allow overriding autocommit via env (default True)
    autocommit = os.environ.get("DB_AUTOCOMMIT", "true").lower() in ("1", "true", "yes")

    return {
        "host": host,
        "user": user,
        "password": password,
        "database": database,
        "port": int(os.environ.get("DB_PORT", "3306")),
        "autocommit": autocommit,
        # Optional niceties
        "connection_timeout": int(os.environ.get("DB_CONN_TIMEOUT", "10")),
        "raise_on_warnings": True,
    }


class AbstractBaseMySQLService(ABC):
    """
    Abstract base class for all database service layers.
    Manages connection lifecycle and defines CRUD interface.
    """

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self._db_config = db_config or _load_db_config_from_env()
        self._connection: Optional[MySQLConnection] = None

    # -------- Context manager helpers (with ... as service) ----------
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close_connection()

    # ------------------ Connection lifecycle -------------------------
    def connect(self) -> None:
        """Establish a connection to MySQL if not connected."""
        if self._connection is None or not self._connection.is_connected():
            try:
                print(f"INFO: Attempting to connect to MySQL at {self._db_config.get('host')}...")
                self._connection = mysql.connector.connect(**self._db_config)
                print("INFO: Database connection successful.")
            except MySQLError as err:
                print(f"ERROR: Database connection failed: {err}")
                self._connection = None
                raise

    def get_connection(self) -> MySQLConnection:
        """
        Ensure there is an active connection. Reconnect if needed.
        """
        if self._connection is None or not self._connection.is_connected():
            self.connect()
        # Ping to keepalive/verify connection (no reconnect if False)
        try:
            self._connection.ping(reconnect=True, attempts=2, delay=1)
        except Exception:
            # Try hard reconnect once more
            self.connect()
        return self._connection  # type: ignore

    def close_connection(self) -> None:
        """Close connection safely."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
            self._connection = None
            print("INFO: Database connection closed.")

    # -------------------------- CRUD API -----------------------------
    @abstractmethod
    def create(self, *args, **kwargs) -> Any: ...
    @abstractmethod
    def retrieve(self, *args, **kwargs) -> Any: ...
    @abstractmethod
    def update(self, *args, **kwargs) -> Any: ...
    @abstractmethod
    def delete(self, *args, **kwargs) -> Any: ...
