import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'attendance.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("DROP TABLE IF EXISTS attendance")
conn.commit()
conn.close()
print("Attendance table dropped. It will be recreated on server startup.")
