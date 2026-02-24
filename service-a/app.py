import os
import time
import psycopg2
import requests
from flask import Flask, jsonify

APP_NAME = "service-a"
NEXT_URL = os.getenv("NEXT_URL", "http://service-b:8002/run")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "otel_demo")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

app = Flask(__name__)

def db_insert(message: str) -> None:
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO events(service, message) VALUES (%s, %s)",
                    (APP_NAME, message),
                )
    finally:
        conn.close()

@app.get("/run")
def run():
    msg = f"{APP_NAME}: start"
    db_insert(msg)

    # маленькая задержка, чтобы на трейсе было видно распределение времени
    time.sleep(0.1)

    r = requests.get(NEXT_URL, timeout=5)
    return jsonify({
        "service": APP_NAME,
        "db_message": msg,
        "next_status": r.status_code,
        "next_body": r.json()
    })
