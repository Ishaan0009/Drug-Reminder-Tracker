# database.py
import sqlite3
import datetime
from pathlib import Path

DB_FILE = Path(__file__).parent / "medicines.db"

def connect():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        dosage TEXT,
        times TEXT,          -- comma separated HH:MM entries
        status TEXT DEFAULT 'Pending',
        added_date TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_medicine(name: str, dosage: str, times_csv: str):
    added = datetime.date.today().isoformat()
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO medicines (name, dosage, times, status, added_date) VALUES (?, ?, ?, 'Pending', ?)",
                (name, dosage, times_csv, added))
    conn.commit()
    conn.close()

def get_all_medicines():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, name, dosage, times, status, added_date FROM medicines ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_status(med_id: int, new_status: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE medicines SET status=? WHERE id=?", (new_status, med_id))
    conn.commit()
    conn.close()

def delete_medicine(med_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM medicines WHERE id=?", (med_id,))
    conn.commit()
    conn.close()
