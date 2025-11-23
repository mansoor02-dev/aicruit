import os
import time
import psycopg2
from psycopg2 import OperationalError


def run_schema():
    dbname = os.getenv("DB_NAME", "aicruit")
    user = os.getenv("DB_USER", "admin")
    password = os.getenv("DB_PASS", "admin123")
    host = os.getenv("DB_HOST", "postgres")
    port = int(os.getenv("DB_PORT", "5432"))

    attempts = 0
    max_attempts = 30
    wait_seconds = 2

    while True:
        try:
            print(f"Connecting to database {dbname} at {host}:{port} (attempt {attempts + 1})")
            conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
            break
        except OperationalError as e:
            attempts += 1
            if attempts >= max_attempts:
                print("Could not connect to database after several attempts:", e)
                raise
            print(f"Database not ready, retrying in {wait_seconds} seconds...")
            time.sleep(wait_seconds)

    cur = conn.cursor()

    print("Running schema.sql...")

    with open("schema.sql", "r") as file:
        sql = file.read()
        cur.execute(sql)

    conn.commit()
    cur.close()
    conn.close()

    print("Database initialized successfully!")


if __name__ == "__main__":
    run_schema()
