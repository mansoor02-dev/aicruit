import psycopg2
import os


def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "aicruit"),
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "admin123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

