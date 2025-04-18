import psycopg2
from urllib.parse import urlparse
import os

def init_db():
    POSTGRES_URL = os.getenv("POSTGRES_URL")
    result = urlparse(POSTGRES_URL)
    conn = psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    cursor = conn.cursor()

    with open("jobs/db/sql_scripts/create_tables.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()

    cursor.execute(schema_sql)
    conn.commit()
    cursor.close()
    conn.close()

    print("Tables successfully created")
