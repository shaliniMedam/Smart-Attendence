import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'attendance.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            email TEXT,
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            check_in_time TEXT,
            check_out_time TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            timestamp TEXT,
            date TEXT,
            action TEXT,
            photo_path TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Initialize default settings if not exists
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('org_name', 'Smart Attendance')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('tolerance', '0.4')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cooldown', '2')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'admin123')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_username', 'admin')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('liveness_blur_variance', '50.0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('liveness_depth_z_std', '0.02')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('expected_check_in_time', '09:00')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('expected_check_out_time', '17:00')")
    
    conn.commit()
    conn.close()

def add_student(name, roll_number, email, photo_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO students (name, roll_number, email, photo_path) VALUES (?, ?, ?, ?)",
        (name, roll_number, email, photo_path)
    )
    conn.commit()
    student_id = cursor.lastrowid
    conn.close()
    return student_id

def get_all_students():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, roll_number, email, photo_path FROM students")
    students = cursor.fetchall()
    conn.close()
    return students

def get_student_by_id(student_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, roll_number, email, photo_path FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    conn.close()
    return student

def compute_status(check_in, check_out, expected_in, expected_out):
    status_parts = []
    if check_in:
        try:
            # Parse expected times properly (they are usually HH:MM)
            exp_in_obj = datetime.strptime(expected_in, '%H:%M').time()
            if datetime.strptime(check_in, '%H:%M:%S').time() > exp_in_obj:
                status_parts.append('Late')
        except: pass
    if check_out:
        try:
            exp_out_obj = datetime.strptime(expected_out, '%H:%M').time()
            if datetime.strptime(check_out, '%H:%M:%S').time() < exp_out_obj:
                status_parts.append('Early Exit')
        except: pass
        
    if not check_out:
        status_parts.append('No Check-out')
        
    if not status_parts:
        return 'On Time'
    return ', '.join(status_parts)

def mark_attendance(student_id, date_str, time_str, is_live=True):
    # 1. Determine action from scan_logs
    logs = get_scan_logs(student_id, date_str)
    
    action = "check_in"
    if len(logs) > 0:
        last_action = logs[-1]["action"]
        if last_action == "check_in":
            action = "check_out"
        else:
            action = "check_in"
            
    # Check cooldown against the last scan time
    if len(logs) > 0:
        last_time_str = logs[-1]["time"]
        t1 = datetime.strptime(last_time_str, '%H:%M:%S')
        t2 = datetime.strptime(time_str, '%H:%M:%S')
        if (t2 - t1).total_seconds() < 15: # Reduced to 15 seconds for easier testing
            return "cooldown"
            
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if a row already exists in attendance for this student and date
    cursor.execute('''
        SELECT id, check_in_time, check_out_time 
        FROM attendance 
        WHERE student_id = ? AND date = ?
    ''', (student_id, date_str))
    row = cursor.fetchone()
    
    if len(logs) == 0:
        # Initial Check-In
        if not row:
            cursor.execute(
                "INSERT INTO attendance (student_id, date, check_in_time) VALUES (?, ?, ?)",
                (student_id, date_str, time_str)
            )
    else:
        # Subsequent scans
        if action == "check_out" and is_live and row:
            # Final Check-Out -> Update main table
            record_id = row[0]
            cursor.execute(
                "UPDATE attendance SET check_out_time = ? WHERE id = ?",
                (time_str, record_id)
            )
            
    conn.commit()
    conn.close()
    return action

def add_scan_log(student_id, date_str, time_str, action, photo_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scan_logs (student_id, timestamp, date, action, photo_path) VALUES (?, ?, ?, ?, ?)",
        (student_id, time_str, date_str, action, photo_path)
    )
    conn.commit()
    conn.close()
    return True

def get_scan_logs(student_id, date_str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, action, photo_path
        FROM scan_logs
        WHERE student_id = ? AND date = ?
        ORDER BY timestamp ASC
    ''', (student_id, date_str))
    records = cursor.fetchall()
    conn.close()
    return [{"time": r[0], "action": r[1], "photo_path": r[2]} for r in records]

def get_attendance_by_date(date_str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.name, s.roll_number, a.check_in_time, a.check_out_time 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE a.date = ? 
        ORDER BY a.check_in_time
    ''', (date_str,))
    records = cursor.fetchall()
    conn.close()
    
    settings = get_settings()
    exp_in = settings.get('expected_check_in_time', '09:00')
    exp_out = settings.get('expected_check_out_time', '17:00')
    
    results = []
    for r in records:
        status = compute_status(r[3], r[4], exp_in, exp_out)
        results.append((r[0], r[1], r[2], r[3] or '-', r[4] or '-', status))
    return results

def get_attendance_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = ?", (today,))
    present_today = cursor.fetchone()[0]
    
    conn.close()
    return {"total_students": total_students, "present_today": present_today}

def export_attendance_csv(date_str):
    import csv
    records = get_attendance_by_date(date_str)
    filename = f"attendance_{date_str}.csv"
    filepath = os.path.join(os.path.dirname(__file__), '..', 'attendance_logs', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Name', 'Roll Number', 'Check-In', 'Check-Out', 'Status'])
        for r in records:
            writer.writerow([r[1], r[2], r[3], r[4], r[5]])
    return filename

def delete_student(student_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get student photo path first to delete it
    cursor.execute("SELECT photo_path FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    photo_path = row[0] if row else None
    
    # Delete student's attendance records first
    cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    
    # Delete student
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    
    conn.commit()
    conn.close()
    
    # Try deleting the photo file from disk
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except Exception:
            pass
            
    # Clear representations cache to force DeepFace.find to update
    try:
        from face_recognizer import clear_representations_cache
        clear_representations_cache()
    except Exception:
        pass
            
    return True

def get_attendance_range(start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.name, s.roll_number, a.date, a.check_in_time, a.check_out_time 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE a.date BETWEEN ? AND ?
        ORDER BY a.date DESC, a.check_in_time DESC
    ''', (start_date, end_date))
    records = cursor.fetchall()
    conn.close()
    
    settings = get_settings()
    exp_in = settings.get('expected_check_in_time', '09:00')
    exp_out = settings.get('expected_check_out_time', '17:00')
    
    results = []
    for r in records:
        status = compute_status(r[4], r[5], exp_in, exp_out)
        results.append((r[0], r[1], r[2], r[3], r[4] or '-', r[5] or '-', status))
    return results

def get_settings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    
    settings_dict = {}
    for row in rows:
        settings_dict[row[0]] = row[1]
        
    # Set default values if not exists
    if 'org_name' not in settings_dict: settings_dict['org_name'] = 'Smart Attendance'
    if 'tolerance' not in settings_dict: settings_dict['tolerance'] = '0.4'
    if 'cooldown' not in settings_dict: settings_dict['cooldown'] = '2'
    if 'admin_username' not in settings_dict: settings_dict['admin_username'] = 'admin'
    if 'expected_check_in_time' not in settings_dict: settings_dict['expected_check_in_time'] = '09:00'
    if 'expected_check_out_time' not in settings_dict: settings_dict['expected_check_out_time'] = '17:00'
    
    return settings_dict

def save_settings(settings_dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for key, value in settings_dict.items():
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
    conn.commit()
    conn.close()
    return True

def reset_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all student photo paths to delete them first
    cursor.execute("SELECT photo_path FROM students")
    rows = cursor.fetchall()
    
    # Delete student records and attendance records
    cursor.execute("DELETE FROM attendance")
    cursor.execute("DELETE FROM students")
    
    conn.commit()
    conn.close()
    
    # Delete photo files from known_faces directory
    for row in rows:
        photo_path = row[0]
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except Exception:
                pass
                
    # Clear representations cache to force DeepFace.find to update
    try:
        from face_recognizer import clear_representations_cache
        clear_representations_cache()
    except Exception:
        pass
        
    return True