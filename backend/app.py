from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os
from datetime import datetime

from database import (
    init_db, add_student, get_all_students, mark_attendance,
    get_attendance_by_date, get_attendance_stats, export_attendance_csv,
    delete_student, get_attendance_range, get_settings, save_settings,
    reset_database, add_scan_log, get_scan_logs
)
from face_recognizer import (
    save_face_image, recognize_face
)

app = Flask(__name__)
CORS(app)

# In-memory session tracking for liveness challenges
import uuid
import random
liveness_sessions = {}
CHALLENGE_TYPES = ['smile', 'mouth_open', 'turn_left', 'turn_right', 'blink']

# Initialize database on startup
init_db()

@app.route('/')
def home():
    return jsonify({"message": "Face Recognition Attendance API (DeepFace)", "status": "running"})

@app.route('/api/register', methods=['POST'])
def register_student():
    data = request.json
    name = data.get('name')
    roll_number = data.get('roll_number')
    email = data.get('email', '')
    image_base64 = data.get('image')
    
    if not all([name, roll_number, image_base64]):
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    
    try:
        # Decode base64 image
        image_data = base64.b64decode(image_base64.split(',')[1] if ',' in image_base64 else image_base64)
        
        # Save image
        filename = f"{roll_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        photo_path = save_face_image(image_data, filename)
        
        # Verify face is detectable
        from deepface import DeepFace
        try:
            DeepFace.extract_faces(img_path=photo_path, detector_backend="opencv")
        except Exception as e:
            os.remove(photo_path)
            return jsonify({"success": False, "message": f"No clear face detected: {str(e)}"}), 400
        
        # Save to database
        student_id = add_student(name, roll_number, email, photo_path)
        
        return jsonify({
            "success": True,
            "message": "Student registered successfully",
            "student_id": student_id
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/students', methods=['GET'])
def list_students():
    students = get_all_students()
    result = []
    for s in students:
        result.append({
            "id": s[0],
            "name": s[1],
            "roll_number": s[2],
            "email": s[3],
            "photo_path": s[4]
        })
    return jsonify({"success": True, "students": result})

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
def remove_student(student_id):
    try:
        delete_student(student_id)
        return jsonify({"success": True, "message": "Student deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/recognize', methods=['POST'])
def recognize_and_mark():
    data = request.json
    image_base64 = data.get('image')
    
    if not image_base64:
        return jsonify({"success": False, "message": "No image provided"}), 400
        
    try:
        # Check if settings allow attendance today
        # Extract base64 data
        image_data = base64.b64decode(image_base64.split(',')[1] if ',' in image_base64 else image_base64)
        
        # Get tolerance threshold from settings
        settings = get_settings()
        tolerance = float(settings.get('tolerance', 0.4))
        
        # 1. Identify the person first (Bypass Liveness at this stage)
        result = recognize_face(image_data, tolerance=tolerance)
        
        if result["success"]:
            student_id = result["student_id"]
            today = datetime.now().strftime('%Y-%m-%d')
            now = datetime.now().strftime('%H:%M:%S')
            
            import numpy as np
            import cv2
            nparr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            from liveness import verify
            is_live, msg = verify(frame)
            
            logs_today = get_scan_logs(student_id, today)
            
            # Determine expected next action
            expected_action = "check_in"
            if len(logs_today) > 0:
                if logs_today[-1]["action"] == "check_in":
                    expected_action = "check_out"
                else:
                    expected_action = "check_in"
            
            if len(logs_today) == 0:
                if not is_live:
                    return jsonify({
                        "success": False, 
                        "error": "liveness_failed",
                        "message": "Initial Check-In must be a LIVE face."
                    }), 400
            else:
                if expected_action == "check_in" and is_live:
                    return jsonify({
                        "success": False, 
                        "error": "liveness_failed",
                        "message": "Intermediate Check-In must use an ID Card (Static Photo)."
                    }), 400

            # 3. Mark attendance
            action = mark_attendance(student_id, today, now, is_live)
            
            if action == "cooldown":
                result["success"] = False
                result["error"] = "cooldown"
                result["message"] = "Please wait a minute before checking out."
            elif action in ["check_in", "check_out"]:
                # Save audit photo
                audit_dir = os.path.join(os.path.dirname(__file__), 'audit_photos')
                os.makedirs(audit_dir, exist_ok=True)
                audit_filename = f"scan_{result['student_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                audit_path = os.path.join(audit_dir, audit_filename)
                
                with open(audit_path, 'wb') as f:
                    f.write(image_data)
                
                rel_path = f"/api/audit_photos/{audit_filename}"
                add_scan_log(result["student_id"], today, now, action, rel_path)
                
                if action == "check_in":
                    result["attendance_status"] = "Check-In Recorded"
                else:
                    result["attendance_status"] = "Check-Out Recorded"
                    
                if not is_live:
                    result["attendance_status"] += " (ID Scan)"
                    
                result["time"] = now
            else:
                result["success"] = False
                result["message"] = "Error recording attendance."
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance/today', methods=['GET'])
def get_today_attendance():
    today = datetime.now().strftime('%Y-%m-%d')
    records = get_attendance_by_date(today)
    result = []
    for r in records:
        result.append({
            "student_id": r[0],
            "name": r[1],
            "roll_number": r[2],
            "check_in": r[3],
            "check_out": r[4],
            "status": r[5]
        })
    return jsonify({"success": True, "date": today, "records": result})

@app.route('/api/attendance/<date>', methods=['GET'])
def get_date_attendance(date):
    records = get_attendance_by_date(date)
    result = []
    for r in records:
        result.append({
            "student_id": r[0],
            "name": r[1],
            "roll_number": r[2],
            "check_in": r[3],
            "check_out": r[4],
            "status": r[5]
        })
    return jsonify({"success": True, "date": date, "records": result})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = get_attendance_stats()
    return jsonify({"success": True, "stats": stats})

@app.route('/api/export/<date>', methods=['GET'])
def export_csv(date):
    try:
        filename = export_attendance_csv(date)
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance/range', methods=['GET'])
def get_attendance_date_range():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if not start_date or not end_date:
        return jsonify({"success": False, "message": "Missing start or end date parameter"}), 400
        
    try:
        records = get_attendance_range(start_date, end_date)
        result = []
        for r in records:
            result.append({
                "student_id": r[0],
                "name": r[1],
                "roll_number": r[2],
                "date": r[3],
                "check_in": r[4],
                "check_out": r[5],
                "status": r[6]
            })
        return jsonify({"success": True, "start": start_date, "end": end_date, "records": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/export/range', methods=['GET'])
def export_csv_range():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if not start_date or not end_date:
        return jsonify({"success": False, "message": "Missing start or end date parameter"}), 400
        
    try:
        records = get_attendance_range(start_date, end_date)
        
        import csv
        filename = f"attendance_range_{start_date}_to_{end_date}.csv"
        filepath = os.path.join(os.path.dirname(__file__), '..', 'attendance_logs', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Name', 'Roll Number', 'Check-In', 'Check-Out', 'Status'])
            for r in records:
                writer.writerow([r[2], r[0], r[1], r[3], r[4], r[5]])
                
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/audit_photos/<filename>')
def serve_audit_photo(filename):
    audit_dir = os.path.join(os.path.dirname(__file__), 'audit_photos')
    from flask import send_from_directory
    return send_from_directory(audit_dir, filename)

@app.route('/api/logs/<int:student_id>/<date>', methods=['GET'])
def api_get_logs(student_id, date):
    try:
        logs = get_scan_logs(student_id, date)
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    try:
        settings = get_settings()
        return jsonify({
            "success": True,
            "settings": {
                "org_name": settings.get('org_name', 'Smart Attendance'),
                "tolerance": float(settings.get('tolerance', 0.4)),
                "cooldown": int(settings.get('cooldown', 2)),
                "admin_username": settings.get('admin_username', 'admin'),
                "expected_check_in_time": settings.get('expected_check_in_time', '09:00'),
                "expected_check_out_time": settings.get('expected_check_out_time', '17:00')
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"success": False, "message": "Username and password are required"}), 400
        
    try:
        settings = get_settings()
        correct_username = settings.get('admin_username', 'admin')
        correct_password = settings.get('admin_password', 'admin123')
        
        if data.get('username') == correct_username and data.get('password') == correct_password:
            return jsonify({"success": True, "message": "Login successful"})
        else:
            return jsonify({"success": False, "message": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
        
    try:
        org_name = data.get('org_name', 'Smart Attendance')
        tolerance = float(data.get('tolerance', 0.4))
        cooldown = int(data.get('cooldown', 2))
        new_password = data.get('new_password')
        admin_username = data.get('admin_username')
        expected_check_in_time = data.get('expected_check_in_time', '09:00')
        expected_check_out_time = data.get('expected_check_out_time', '17:00')
        
        settings_to_save = {
            'org_name': org_name,
            'tolerance': str(tolerance),
            'cooldown': str(cooldown),
            'expected_check_in_time': expected_check_in_time,
            'expected_check_out_time': expected_check_out_time
        }
        
        if admin_username and admin_username.strip():
            settings_to_save['admin_username'] = admin_username.strip()
            
        if new_password and new_password.strip():
            settings_to_save['admin_password'] = new_password.strip()
            
        save_settings(settings_to_save)
        return jsonify({"success": True, "message": "Settings updated successfully"})
    except ValueError as ve:
        return jsonify({"success": False, "message": f"Invalid settings value: {str(ve)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings/clear-cache', methods=['POST'])
def api_clear_cache():
    try:
        from face_recognizer import clear_representations_cache
        clear_representations_cache()
        return jsonify({"success": True, "message": "DeepFace cache cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings/reset-database', methods=['POST'])
def api_reset_database():
    try:
        reset_database()
        return jsonify({"success": True, "message": "Database reset successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("Starting DeepFace Attendance System...")
    print("First run will download AI models (~100MB)")
    print("This may take a few minutes...")
    print("=" * 50)
    
    # Pre-load AI models in background to avoid long first-scan delay
    import threading
    from deepface import DeepFace
    def preload():
        try:
            print("Pre-loading FaceNet AI into memory... (This takes 10-15 seconds)")
            import os
            from deepface import DeepFace
            
            known_faces_dir = os.path.join(os.path.dirname(__file__), '..', 'known_faces')
            images = [f for f in os.listdir(known_faces_dir) if f.endswith(('.jpg', '.png'))]
            if images:
                print("Warming up representations cache...")
                img_path = os.path.join(known_faces_dir, images[0])
                DeepFace.find(img_path=img_path, db_path=known_faces_dir, model_name="Facenet", detector_backend="opencv", enforce_detection=False)
            else:
                DeepFace.build_model("Facenet")
            print("AI Engine Warmup Complete! Ready for fast scanning.")
        except Exception as e:
            print(f"Preload error: {e}")
    threading.Thread(target=preload, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)