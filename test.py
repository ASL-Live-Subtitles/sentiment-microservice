# test_db_connection.py

import os
from uuid import uuid4
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("INFO: python-dotenv not installed. Assuming environment variables are set globally.")
    pass

from db.abstract_base import DB_CONFIG
from db.sentiment_service import SentimentMySQLService 

TEST_SENTENCE = "This is a test connection from the microservice."
TEST_USER_ID = uuid4() # Generate a dummy user ID

def run_db_connection_test():
    """
    Instantiates the service and tests the connection and a simple read operation.
    """
    print("--- Starting DB Connection Test ---")

    print(f"Checking config: Host={DB_CONFIG['host']}, User={DB_CONFIG['user']}, DB={DB_CONFIG['database']}")

    db_service = SentimentMySQLService()
    
    try:
        conn = db_service.get_connection()
        print("✅ STEP 1: Successful connection obtained!")
        
        print("Testing simple query (SELECT 1)...")
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        
        if result and result[0] == 1:
            print("✅ STEP 2: Simple query executed successfully (DB connection and permissions OK).")
            
            print("Testing SentimentService method (e.g., retrieve_all)...")
            all_sentiments = db_service.retrieve_all()
            print(f"✅ STEP 3: Successfully retrieved {len(all_sentiments)} existing records from the database.")

        else:
            print("❌ STEP 2: Basic SELECT query failed.")
            
    except Exception as e:
        print(f"❌ CONNECTION FAILED! Error details: {e}")
        if "2003" in str(e):
            print("HINT: Error 2003 means 'Can't connect' - Check Firewall (0.0.0.0/0) or Internal IP.")
        elif "1045" in str(e):
            print("HINT: Error 1045 means 'Access denied' - Check DB_USER/DB_PASSWORD or Host permission (GRANT).")
        elif "1130" in str(e):
             print("HINT: Error 1130 means 'Host not allowed' - Check if 'skip-name-resolve = 1' is set and MySQL is restarted.")
             
    finally:
        # Step 6: Close the connection (good practice)
        db_service.close_connection()
        print("--- Test Finished ---")

if __name__ == "__main__":
    run_db_connection_test()