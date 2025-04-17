import os
import psycopg2
from dotenv import load_dotenv

# Load variales from .env
load_dotenv()

# Connect to DB
conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host="db", 
    port=5432
)
cur = conn.cursor()

print("Hello world!")

cur.close()
conn.close()
