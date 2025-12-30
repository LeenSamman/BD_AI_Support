import csv
import sqlite3
from pathlib import Path
# Note: I must not run this again as the data already exists in the database.
# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "staffing.db"
CSV_PATH = BASE_DIR / "countries.csv"

# --- Connect to SQLite ---
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# --- Read CSV and insert ---
with open(CSV_PATH, newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        name = row["Name"].strip()
        iso_code = row["Code"].strip()

        cursor.execute(
            """
            INSERT OR IGNORE INTO Country (name, iso_code)
            VALUES (?, ?)
            """,
            (name, iso_code)
        )

conn.commit()
conn.close()

print(" Countries successfully loaded into the database.")
