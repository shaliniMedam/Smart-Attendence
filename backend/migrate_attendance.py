import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'attendance.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Rename old table
    cursor.execute("ALTER TABLE attendance RENAME TO attendance_old")
    
    # Create new table without UNIQUE constraint
    cursor.execute('''
        CREATE TABLE attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            check_in_time TEXT,
            check_out_time TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    # Copy data
    cursor.execute('''
        INSERT INTO attendance (id, student_id, date, check_in_time, check_out_time)
        SELECT id, student_id, date, check_in_time, check_out_time FROM attendance_old
    ''')
    
    # Drop old table
    cursor.execute("DROP TABLE attendance_old")
    
    conn.commit()
    conn.close()
    print("Migration complete. attendance table is now multi-session capable.")

if __name__ == '__main__':
    migrate()
