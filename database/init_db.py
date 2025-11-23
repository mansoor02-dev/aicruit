import psycopg2

def run_schema():
    conn = psycopg2.connect(
        dbname="aicruit",
        user="admin",
        password="admin123",
        host="localhost",
        port="5432"
    )
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
