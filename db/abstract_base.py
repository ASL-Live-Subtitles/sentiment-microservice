from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
import os
import mysql.connector
from mysql.connector.connection import MySQLConnection
from mysql.connector import Error as MySQLError

# -----------------------------------------------------------------------------
# Configuration (To be replaced by environment variables later)
# -----------------------------------------------------------------------------
# Placeholder configuration. In a real microservice, these would come from 
# environment variables or a dedicated config file.

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

DB_CONFIG = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
    "port": 3306,
    # Setting autocommit to True for simplicity in a microservice CRUD environment
    "autocommit": True, 
}

# -----------------------------------------------------------------------------
# Abstract Base Service
# -----------------------------------------------------------------------------

class AbstractBaseMySQLService(ABC):
    """
    Abstract base class for all database service layers.
    It defines the fundamental methods for managing database connection.
    """

    def __init__(self, db_config: Dict[str, Any] = DB_CONFIG):
        """Initializes the service with database connection configuration."""
        self._db_config = db_config
        self._connection: Optional[MySQLConnection] = None

    def connect(self) -> None:
        """
        Establishes a connection to the MySQL database if one is not already
        active or connected.
        """
        if self._connection is None or not self._connection.is_connected():
            try:
                print(f"INFO: Attempting to connect to MySQL at {self._db_config['host']}...")
                self._connection = mysql.connector.connect(**self._db_config)
                print("INFO: Database connection successful.")
            except MySQLError as err:
                print(f"ERROR: Database connection failed: {err}")
                self._connection = None
                # Re-raise the exception to be handled by the caller (e.g., FastAPI startup)
                raise

    def get_connection(self) -> MySQLConnection:
        """
        Returns the active MySQL connection, ensuring it is open.
        Raises an exception if connection fails.
        """
        if self._connection is None or not self._connection.is_connected():
            self.connect()
        # MyPy check: Connection is guaranteed to be established here if no exception was raised
        return self._connection  # type: ignore

    def close_connection(self) -> None:
        """
        Closes the database connection if it is currently open.
        """
        if self._connection and self._connection.is_connected():
            self._connection.close()
            self._connection = None
            print("INFO: Database connection closed.")
            
    @abstractmethod
    def create(self, *args, **kwargs) -> Any:
        """Abstract method for creating a record."""
        pass

    @abstractmethod
    def retrieve(self, *args, **kwargs) -> Any:
        """Abstract method for retrieving records."""
        pass

    @abstractmethod
    def update(self, *args, **kwargs) -> Any:
        """Abstract method for updating a record."""
        pass

    @abstractmethod
    def delete(self, *args, **kwargs) -> None:
        """Abstract method for deleting a record."""
        pass