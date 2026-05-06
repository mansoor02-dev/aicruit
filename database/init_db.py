import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError as SAOperationalError


def run_schema():
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "admin123")
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "aicruit")

    database_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    attempts = 0
    max_attempts = 30
    wait_seconds = 2

    engine = None
    while True:
        try:
            print(f"Connecting to database {db_name} at {db_host}:{db_port} (attempt {attempts + 1})")
            engine = create_engine(database_url, pool_pre_ping=True)
            # try to connect
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception as e:
            attempts += 1
            if attempts >= max_attempts:
                print("Could not connect to database after several attempts:", e)
                raise
            print(f"Database not ready, retrying in {wait_seconds} seconds...")
            time.sleep(wait_seconds)

    print("Running schema.sql...")
    with open("schema.sql", "r", encoding="utf-8") as file:
        sql = file.read()

    # Execute the SQL script. Use a transaction for safety.
    with engine.begin() as conn:
        # Some SQL files contain multiple statements; execute as text
        conn.execute(text(sql))

    print("Database initialized successfully!")


if __name__ == "__main__":
    run_schema()
