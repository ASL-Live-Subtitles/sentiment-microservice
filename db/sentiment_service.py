from __future__ import annotations

from typing import List, Optional, Any
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
    def update(self, *args: Any, **kwargs: Any) -> Optional[SentimentResult]:
        """
        Generic update required by the abstract base class.

        Historically this forwarded only to `update_text` (updating the input text).
        To avoid API confusion, higher-level code should now prefer the more explicit
        methods:
          - update_text(...)                   -> only change original text
          - update_with_new_analysis(...)      -> change text + sentiment result
        """
        sentiment_id: UUID
        new_text: str

        if args:
            # Expecting positional form: (sentiment_id, new_text)
            if len(args) < 2:
                raise ValueError("update() expects (sentiment_id, new_text) or keyword arguments.")
            sentiment_id = args[0]
            new_text = args[1]
        else:
            # Keyword form: sentiment_id=..., text=...
            if "sentiment_id" not in kwargs or "text" not in kwargs:
                raise ValueError("update() requires 'sentiment_id' and 'text' keyword arguments.")
            sentiment_id = kwargs["sentiment_id"]
            new_text = kwargs["text"]

        return self.update_text(sentiment_id, new_text)

    def update_text(self, sentiment_id: UUID, new_text: str) -> Optional[SentimentResult]:
        """
        Update only the *input text* associated with a sentiment record.

        - We locate the corresponding request row via sentiments.request_id
        - We update requests.input_text
        - We DO NOT automatically re-run sentiment analysis here.
          If you want a new analysis for the updated text, call POST /sentiments again.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        try:
            # Find the corresponding request_id
            cursor.execute(
                "SELECT request_id FROM sentiments WHERE id = %s",
                (str(sentiment_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None

            request_id = str(row[0])

            # Update the original input text
            cursor.execute(
                """
                UPDATE requests
                SET input_text = %s
                WHERE id = %s
                """,
                (new_text, request_id),
            )
            conn.commit()

            # Return the updated joined view (text changes, sentiment result stays the same)
            return self.retrieve(sentiment_id)
        except MySQLError as err:
            print(f"ERROR during UPDATE TEXT: {err}")
            raise
        finally:
            cursor.close()

    def update_with_new_analysis(
        self,
        sentiment_id: UUID,
        new_text: str,
        result_data: SentimentResult,
    ) -> Optional[SentimentResult]:
        """
        Update both:
        - the original input text in `requests.input_text`, and
        - the sentiment fields in `sentiments`

        This is used when the caller has re-run sentiment analysis for a new text
        but wants to keep the same sentiment record ID.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        try:
            # Find the corresponding request_id
            cursor.execute(
                "SELECT request_id FROM sentiments WHERE id = %s",
                (str(sentiment_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None

            request_id = str(row[0])

            # 1) Update input text on the request
            cursor.execute(
                """
                UPDATE requests
                SET input_text = %s
                WHERE id = %s
                """,
                (new_text, request_id),
            )

            # 2) Update sentiment result (keep the same sentiment_id)
            cursor.execute(
                """
                UPDATE sentiments
                SET sentiment = %s,
                    confidence = %s,
                    analyzed_at = %s
                WHERE id = %s
                """,
                (
                    result_data.sentiment,
                    result_data.confidence,
                    result_data.analyzed_at,
                    str(sentiment_id),
                ),
            )

            conn.commit()
            return self.retrieve(sentiment_id)
        except MySQLError as err:
            print(f"ERROR during UPDATE WITH NEW ANALYSIS: {err}")
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
