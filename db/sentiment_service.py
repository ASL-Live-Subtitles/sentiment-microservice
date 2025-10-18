from typing import List, Optional
from uuid import UUID, uuid4
import mysql.connector
from mysql.connector.cursor import MySQLCursor

# Assuming the base service and models are correctly imported
from db.abstract_base import AbstractBaseMySQLService 
from mysql.connector import Error as MySQLError 
from models.sentiment import TextInput, SentimentResult

class SentimentMySQLService(AbstractBaseMySQLService):
    """
    Implements the CRUD operations for sentiment analysis results,
    storing data across two tables: 'requests' and 'sentiments'.
    """

    # --- Helper Method to transform DB result to Pydantic Model ---
    def _map_row_to_sentiment(self, row: tuple) -> SentimentResult:
        """
        Maps a SQL query result row (tuple) to a SentimentResult Pydantic model.
        The row must contain all required fields in the correct order.
        
        Expected row order from SELECT query:
        (sentiment.id, request_id, requests.input_text, sentiment, confidence, analyzed_at)
        """
        # Ensure UUIDs are converted to UUID objects if the connector returns strings/bytes
        sentiment_id = UUID(row[0]) if isinstance(row[0], (str, bytes)) else row[0]
        request_id = UUID(row[1]) if isinstance(row[1], (str, bytes)) else row[1]
        
        return SentimentResult(
            id=sentiment_id,
            request_id=request_id,
            text=row[2],              # requests.input_text
            sentiment=row[3],         # sentiments.sentiment
            confidence=row[4],        # sentiments.confidence
            analyzed_at=row[5]        # sentiments.analyzed_at
        )

    # --- C: CREATE (Insert data into two tables) ---
    def create(self, request_data: TextInput, result_data: SentimentResult) -> SentimentResult:
        """
        Inserts a new request and its corresponding sentiment result.
        
        request_data: TextInput (contains text, user_id)
        result_data: SentimentResult (contains id, sentiment, confidence, analyzed_at)
        """
        # 1. Get an active database connection
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()

        try:

            request_id = uuid4()
            # SQL for the 'requests' table
            # created_at is handled by the DB or Python's datetime if not set by DB
            request_sql = """
            INSERT INTO requests (id, input_text, created_at, user_id)
            VALUES (%s, %s, %s, %s)
            """
            request_params = (
                str(request_id),
                request_data.text,
                result_data.analyzed_at,
                "user-123"  # Placeholder user_id; replace with actual user_id if available
            )
            cursor.execute(request_sql, request_params)
            
            # SQL for the 'sentiments' table
            sentiment_sql = """
            INSERT INTO sentiments (id, request_id, sentiment, confidence, analyzed_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            sentiment_params = (
                str(result_data.id),
                str(request_id),
                result_data.sentiment,
                result_data.confidence,
                result_data.analyzed_at
            )
            cursor.execute(sentiment_sql, sentiment_params)
            
            # In AbstractBaseMySQLService, autocommit is True, so changes are saved immediately.
            
            return result_data
            
        except MySQLError as err:
            print(f"ERROR during CREATE: {err}")
            raise
        finally:
            cursor.close()

    # --- R: RETRIEVE (Retrieve single record by sentiment ID) ---
    def retrieve(self, sentiment_id: UUID) -> Optional[SentimentResult]:
        """
        Retrieves a single sentiment record by its ID using a JOIN.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        
        # SQL JOIN to combine data from both tables
        sql = """
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
        """
        
        try:
            cursor.execute(sql, (str(sentiment_id),))
            row = cursor.fetchone()
            
            if row:
                return self._map_row_to_sentiment(row)
            return None
        except MySQLError as err:
            print(f"ERROR during RETRIEVE: {err}")
            raise
        finally:
            cursor.close()

    # --- R: RETRIEVE ALL (Retrieve all records) ---
    def retrieve_all(self) -> List[SentimentResult]:
        """
        Retrieves all sentiment records in the database.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        
        sql = """
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
        """
        
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            return [self._map_row_to_sentiment(row) for row in rows]
        except MySQLError as err:
            print(f"ERROR during RETRIEVE ALL: {err}")
            raise
        finally:
            cursor.close()
            
    # --- U: UPDATE (Full replacement, only sentiment/confidence/analyzed_at can change) ---
    def update(self, sentiment_id: UUID, new_data: SentimentResult) -> Optional[SentimentResult]:
        """
        Updates the sentiment result fields (sentiment, confidence, analyzed_at)
        for a given sentiment_id. Text/request_id are considered immutable.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        
        # Only update fields that typically change during re-analysis
        sql = """
        UPDATE sentiments
        SET 
            sentiment = %s, 
            confidence = %s, 
            analyzed_at = %s
        WHERE id = %s
        """
        params = (
            new_data.sentiment,
            new_data.confidence,
            new_data.analyzed_at,
            str(sentiment_id)
        )

        try:
            cursor.execute(sql, params)
            conn.commit()
            if cursor.rowcount == 0:
                return None  # Record not found
            
            # Retrieve the updated record to return
            return self.retrieve(sentiment_id)
        except MySQLError as err:
            print(f"ERROR during UPDATE: {err}")
            raise
        finally:
            cursor.close()

    # --- D: DELETE (Deletes records from both tables) ---
    def delete(self, sentiment_id: UUID) -> bool:
        """
        Deletes the sentiment record and its corresponding request record.
        Returns True if deletion was successful, False otherwise.
        """
        conn = self.get_connection()
        cursor: MySQLCursor = conn.cursor()
        
        try:
            # 1. Find the request_id associated with the sentiment_id
            cursor.execute("SELECT request_id FROM sentiments WHERE id = %s", (str(sentiment_id),))
            row = cursor.fetchone()
            
            if not row:
                return False # Sentiment not found
            
            request_id_to_delete = str(row[0])
            
            # 2. Delete from 'sentiments' table
            cursor.execute("DELETE FROM sentiments WHERE id = %s", (str(sentiment_id),))
            
            # 3. Delete from 'requests' table (using the retrieved request_id)
            cursor.execute("DELETE FROM requests WHERE id = %s", (request_id_to_delete,))
            
            return True
        except MySQLError as err:
            print(f"ERROR during DELETE: {err}")
            raise
        finally:
            cursor.close()