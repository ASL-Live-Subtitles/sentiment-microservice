from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4
from mysql.connector.cursor import MySQLCursor

from db.abstract_base import AbstractBaseMySQLService
from mysql.connector import Error as MySQLError
from models.sentiment import TextInput, SentimentResult


class SentimentMySQLService(AbstractBaseMySQLService):
    """
    CRUD operations for sentiment analysis spread across 'requests' and 'sentiments'.
    """

    # ------------------------- Row → Model ---------------------------
    def _map_row_to_sentiment(self, row: tuple) -> SentimentResult:
        """
        Expected order:
          (s.id, s.request_id, r.input_text, s.sentiment, s.confidence, s.analyzed_at)
        """
        sid = UUID(row[0]) if isinstance(row[0], (str, bytes)) else row[0]
        # request_id intentionally not exposed in API model
        return SentimentResult(
            id=sid,
            text=row[2],         # requests.input_text
            sentiment=row[3],    # sentiments.sentiment
            confidence=float(row[4]),
            analyzed_at=row[5],
        )

    # ----------------------------- CREATE ----------------------------
    def create(self, request_data: TextInput, result_data: SentimentResult) -> SentimentResult:
        """
        Insert a new request + sentiment, then return the joined SentimentResult.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()

        try:
            request_id = uuid4()

            # requests
            cursor.execute(
                """
                INSERT INTO requests (id, input_text, created_at, user_id)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    str(request_id),
                    request_data.text,
                    result_data.analyzed_at,
                    None,  # or a real user_id if you add auth
                ),
            )

            # sentiments
            cursor.execute(
                """
                INSERT INTO sentiments (id, request_id, sentiment, confidence, analyzed_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    str(result_data.id),
                    str(request_id),
                    result_data.sentiment,
                    result_data.confidence,
                    result_data.analyzed_at,
                ),
            )

            # autocommit is True (and we also can call conn.commit() if needed)
            # Return the freshly created, joined record
            created = self.retrieve(result_data.id)
            return created or result_data

        except MySQLError as err:
            print(f"ERROR during CREATE: {err}")
            raise
        finally:
            cursor.close()

    # ----------------------------- RETRIEVE --------------------------
    def retrieve(self, sentiment_id: UUID) -> Optional[SentimentResult]:
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.request_id,
                    r.input_text,
                    s.sentiment,
                    s.confidence,
                    s.analyzed_at
                FROM sentiments s
                JOIN requests r ON s.request_id = r.id
                WHERE s.id = %s
                """,
                (str(sentiment_id),),
            )
            row = cursor.fetchone()
            return self._map_row_to_sentiment(row) if row else None
        except MySQLError as err:
            print(f"ERROR during RETRIEVE: {err}")
            raise
        finally:
            cursor.close()

    # ----------------------------- LIST ------------------------------
    def retrieve_all(self, limit: int = 100, offset: int = 0) -> List[SentimentResult]:
        """
        Retrieve list with simple pagination.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.request_id,
                    r.input_text,
                    s.sentiment,
                    s.confidence,
                    s.analyzed_at
                FROM sentiments s
                JOIN requests r ON s.request_id = r.id
                ORDER BY s.analyzed_at DESC
                LIMIT %s OFFSET %s
                """,
                (int(limit), int(offset)),
            )
            rows = cursor.fetchall()
            return [self._map_row_to_sentiment(row) for row in rows]
        except MySQLError as err:
            print(f"ERROR during RETRIEVE ALL: {err}")
            raise
        finally:
            cursor.close()

    # ----------------------------- UPDATE ----------------------------
    def update(self, sentiment_id: UUID, new_data: SentimentResult) -> Optional[SentimentResult]:
        """
        Update only sentiment fields; input_text/request_id remain immutable.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE sentiments
                SET sentiment = %s, confidence = %s, analyzed_at = %s
                WHERE id = %s
                """,
                (
                    new_data.sentiment,
                    new_data.confidence,
                    new_data.analyzed_at,
                    str(sentiment_id),
                ),
            )
            conn.commit()  # explicit commit for safety
            if cursor.rowcount == 0:
                return None
            return self.retrieve(sentiment_id)
        except MySQLError as err:
            print(f"ERROR during UPDATE: {err}")
            raise
        finally:
            cursor.close()

    # ----------------------------- DELETE ----------------------------
    def delete(self, sentiment_id: UUID) -> bool:
        """
        Delete sentiment + its request (via found request_id).
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        try:
            cursor.execute("SELECT request_id FROM sentiments WHERE id = %s", (str(sentiment_id),))
            row = cursor.fetchone()
            if not row:
                return False

            request_id_to_delete = str(row[0])

            cursor.execute("DELETE FROM sentiments WHERE id = %s", (str(sentiment_id),))
            cursor.execute("DELETE FROM requests WHERE id = %s", (request_id_to_delete,))
            return True
        except MySQLError as err:
            print(f"ERROR during DELETE: {err}")
            raise
        finally:
            cursor.close()
