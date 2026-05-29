# 🎓 Smart Attendance

An AI-powered face recognition attendance system with liveness detection, built with Flask, DeepFace, and MediaPipe.

---

## Features

- **Face Recognition** — Identifies registered students in real time using DeepFace (FaceNet model)
- **Anti-Spoofing Liveness Detection** — Detects blur, depth (flat-surface), and facial challenges (smile, blink, head turn, mouth open) via MediaPipe Face Landmarker
- **Hybrid Check-In / Check-Out Flow** — First scan (live face) marks check-in; a static ID card photo can mark intermediate check-ins; a final live scan marks check-out
- **Audit Trail** — Every scan is logged with a timestamped photo saved to `audit_photos/`
- **Attendance History** — View and filter daily or monthly records with late/early-exit status computed automatically
- **CSV Export** — Export attendance for a specific date or date range
- **Configurable Settings** — Tolerance threshold, cooldown, expected check-in/out times, organization name, and admin credentials — all configurable from the UI
- **Web Dashboard** — Dark-themed admin UI with sidebar navigation (Dashboard, Register, Attendance, History, Settings)

---

## Project Structure

```
project-root/
├── backend/
│   ├── app.py                  # Flask REST API
│   ├── database.py             # SQLite helpers
│   ├── face_recognizer.py      # DeepFace recognition logic
│   ├── liveness.py             # MediaPipe liveness checks
│   ├── migrate.py              # Drop & recreate attendance table
│   ├── migrate_attendance.py   # Remove UNIQUE constraint migration
│   ├── face_landmarker.task    # MediaPipe model file
│   ├── attendance.db           # SQLite database (auto-created)
│   ├── requirements.txt
│   └── temp/                   # Temp files for recognition
│
├── known_faces/                # Registered student photos + DeepFace cache
├── audit_photos/               # Timestamped scan photos
├── attendance_logs/            # Exported CSV files
│
└── frontend/
    ├── index.html              # Dashboard
    ├── register.html           # Student registration
    ├── attendance.html         # Mark attendance
    ├── history.html            # Attendance history
    ├── settings.html           # System settings
    ├── login.html              # Admin login
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

---

## Requirements

- Python 3.9 – 3.11
- A webcam
- ~500 MB disk space (AI model downloads on first run)

### Python Dependencies

```
Flask==3.0.3
Flask-CORS==4.0.0
deepface==0.0.93
numpy==1.26.4
Pillow==10.3.0
opencv-python==4.9.0.80
tensorflow==2.16.1
tf-keras==2.16.0
mediapipe==0.10.14
scikit-image==0.23.2
```

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd smart-attendance
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Download the MediaPipe Face Landmarker model

Place `face_landmarker.task` in the `backend/` directory. Download it from the [MediaPipe Models page](https://developers.google.com/mediapipe/solutions/vision/face_landmarker#models).

### 5. Start the backend server

```bash
cd backend
python app.py
```

On first run, DeepFace will download the FaceNet model (~100 MB). Subsequent starts are fast. The server runs at `http://localhost:5000`.

### 6. Open the frontend

Open `frontend/index.html` in your browser, or serve the `frontend/` directory with any static file server:

```bash
# Example using Python's built-in server
cd frontend
python -m http.server 8080
```

Then navigate to `http://localhost:8080`.

---

## Default Login Credentials

| Field    | Default      |
|----------|--------------|
| Username | `admin`      |
| Password | `admin123`   |

Change these immediately from **Settings → Company Username / New Admin Password**.

---

## Usage

### Registering a Student

1. Go to **Register** in the sidebar.
2. Start the camera and capture a clear, well-lit photo of the student's face.
3. Fill in the name, roll number, and optional email.
4. Click **Register Student**.

### Marking Attendance

1. Go to **Attendance** in the sidebar.
2. The camera auto-scans every few seconds.
3. **Check-In** — Stand in front of the camera (live face required).
4. **Check-Out** — Stand in front of the camera again (live face required).
5. Intermediate check-ins (re-entry during the day) use a static ID card photo scan.

### Viewing History

- Use the **History** page to filter records by date (daily) or by month.
- Each row shows check-in time, check-out time, and computed status (On Time / Late / Early Exit / No Check-out).
- Click the audit icon on any row to view the full scan timeline with photos.

### Exporting Attendance

- From the **Attendance** page: select a date and click **Export CSV** for a single-day export.
- From the **History** page: click **Export to CSV** after filtering to export the current view.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/register` | Register a student with a base64 face image |
| `GET` | `/api/students` | List all registered students |
| `DELETE` | `/api/students/<id>` | Delete a student |
| `POST` | `/api/recognize` | Recognize a face and mark attendance |
| `GET` | `/api/attendance/today` | Get today's attendance records |
| `GET` | `/api/attendance/<date>` | Get attendance for a specific date |
| `GET` | `/api/attendance/range?start=&end=` | Get attendance for a date range |
| `GET` | `/api/stats` | Get total students and present-today counts |
| `GET` | `/api/export/<date>` | Export attendance CSV for a date |
| `GET` | `/api/export/range?start=&end=` | Export attendance CSV for a date range |
| `GET` | `/api/logs/<student_id>/<date>` | Get scan audit logs for a student on a date |
| `GET` | `/api/audit_photos/<filename>` | Serve a stored audit photo |
| `GET` | `/api/settings` | Retrieve current system settings |
| `POST` | `/api/settings` | Save system settings |
| `POST` | `/api/settings/clear-cache` | Clear DeepFace representation cache |
| `POST` | `/api/settings/reset-database` | Reset all students and attendance records |
| `POST` | `/api/login` | Authenticate admin credentials |

---

## Configuration

All settings are stored in the `settings` table of `attendance.db` and are editable from the Settings page.

| Setting | Default | Description |
|---------|---------|-------------|
| `org_name` | `Smart Attendance` | Organization name shown in the sidebar |
| `admin_username` | `admin` | Login username |
| `admin_password` | `admin123` | Login password |
| `tolerance` | `0.4` | DeepFace cosine distance threshold (lower = stricter) |
| `cooldown` | `2` | Minimum seconds between recognized scans |
| `expected_check_in_time` | `09:00` | Threshold for "Late" status |
| `expected_check_out_time` | `17:00` | Threshold for "Early Exit" status |
| `liveness_blur_variance` | `50.0` | Laplacian variance floor for blur/screen detection |
| `liveness_depth_z_std` | `0.02` | Z-coordinate std-dev floor for 3D depth detection |

---

## Liveness Detection

The system uses a two-layer passive liveness check on every scan:

1. **Texture / Blur Analysis** — Computes the Laplacian variance of the frame. Values below the `liveness_blur_variance` threshold indicate a screen or blurry printout.
2. **3D Depth Analysis** — Uses MediaPipe Face Landmarker Z-coordinates. A low standard deviation across Z values indicates a flat surface (photo or screen).

Active challenge support (smile, blink, mouth open, turn left/right) is implemented in `liveness.py` and can be triggered server-side via the `challenge_type` parameter.

---

## Database

SQLite database at `backend/attendance.db` with four tables:

- **students** — Registered student records and photo paths
- **attendance** — One row per student per day, storing check-in and check-out times
- **scan_logs** — Full audit log of every individual scan event with photo path
- **settings** — Key-value store for all system configuration

### Migrations

If upgrading from an earlier version that had a UNIQUE constraint on the attendance table, run:

```bash
python backend/migrate_attendance.py
```

---

## Troubleshooting

**Camera not starting** — Ensure no other application is using the webcam. Click **Restart Camera** on the Attendance page.

**Face not recognized** — Try re-registering in similar lighting conditions. If recognition is too strict, increase the tolerance value in Settings (try 0.5–0.6).

**Liveness check failing on a real face** — If you're in low light or too close to the camera, the blur variance check may trip. Improve lighting or increase `liveness_blur_variance` in Settings.

**DeepFace model download slow** — The FaceNet model (~100 MB) downloads on first run. Ensure a stable internet connection. Subsequent runs use the cached model.

**`pkl` cache stale after adding/deleting students** — Go to **Settings → Clear DeepFace Cache**. The cache rebuilds automatically on the next scan.

---

 