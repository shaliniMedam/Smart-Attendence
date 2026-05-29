// ===== Configuration =====
const API_BASE = 'http://localhost:5000/api';
window.appSettings = {
    org_name: 'Smart Attendance',
    tolerance: 0.4,
    cooldown: 2,
    admin_username: 'admin'
};

async function loadGlobalSettings() {
    try {
        const response = await fetch(`${API_BASE}/settings`);
        const data = await response.json();
        if (data.success && data.settings) {
            window.appSettings = data.settings;
            // Update sidebar logo dynamically
            const logoEl = document.querySelector('.sidebar-logo');
            if (logoEl) {
                logoEl.innerHTML = `🎓 ${window.appSettings.org_name}`;
            }
        }
    } catch (error) {
        console.error('Error loading global settings:', error);
    }
}

// ===== Utility Functions =====
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
        <span>${message}</span>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => alertDiv.remove(), 5000);
}

function showLoading(elementId, show = true) {
    const el = document.getElementById(elementId);
    if (show) {
        el.innerHTML = '<div class="spinner"></div>';
        el.style.display = 'block';
    } else {
        el.style.display = 'none';
    }
}

// ===== Dashboard Stats =====
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('totalStudents').textContent = data.stats.total_students;
            document.getElementById('presentToday').textContent = data.stats.present_today;
            document.getElementById('absentToday').textContent = 
                data.stats.total_students - data.stats.present_today;
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ===== Load Today's Attendance =====
async function loadTodayAttendance() {
    try {
        const response = await fetch(`${API_BASE}/attendance/today`);
        const data = await response.json();
        
        const tbody = document.getElementById('attendanceTableBody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (data.records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:2rem;">No attendance records for today</td></tr>';
            return;
        }
        
        data.records.forEach(record => {
            let badgeClass = 'status-present';
            if (record.status.includes('Late') || record.status.includes('Early') || record.status.includes('No Check-out')) {
                badgeClass = 'status-absent';
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${record.name}</strong></td>
                <td>${record.roll_number}</td>
                <td>${record.check_in || '-'}</td>
                <td>${record.check_out || '-'}</td>
                <td><span class="status-badge ${badgeClass}">✓ ${record.status}</span></td>
                <td>
                    <button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.85rem;" onclick="viewAuditLogs(${record.student_id}, '${data.date}')">
                        👁️ Details
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading attendance:', error);
    }
}

// ===== Camera Functions =====
let videoStream = null;
let currentImageData = null;
let isProcessingScan = false;
let scanningInterval = null;
let isPaused = false;

async function startCamera(videoElementId) {
    const video = document.getElementById(videoElementId);
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480, facingMode: 'user' } 
        });
        video.srcObject = videoStream;
        
        // Auto-start scanning loop if on attendance page
        if (videoElementId === 'camera' && document.getElementById('recognitionResult')) {
            isPaused = false;
            // Restore video visibility and hide preview
            video.style.display = 'block';
            const preview = document.getElementById('imagePreview');
            if (preview) preview.style.display = 'none';
            
            if (scanningInterval) clearInterval(scanningInterval);
            scanningInterval = setInterval(autoScanAndMark, window.appSettings.cooldown * 1000);
        }
        return true;
    } catch (error) {
        showAlert('Could not access camera. Please allow camera permissions.', 'error');
        return false;
    }
}

function stopCamera() {
    if (scanningInterval) {
        clearInterval(scanningInterval);
        scanningInterval = null;
    }
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
}

function captureImage(videoElementId, canvasElementId) {
    const video = document.getElementById(videoElementId);
    const canvas = document.getElementById(canvasElementId);
    const context = canvas.getContext('2d');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0);
    
    currentImageData = canvas.toDataURL('image/jpeg', 0.9);
    
    // Show preview
    const preview = document.getElementById('imagePreview');
    if (preview) {
        preview.src = currentImageData;
        preview.style.display = 'block';
    }
    
    return currentImageData;
}

// ===== Registration =====
async function registerStudent() {
    const name = document.getElementById('regName').value.trim();
    const rollNumber = document.getElementById('regRoll').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    
    if (!name || !rollNumber) {
        showAlert('Please fill in name and roll number', 'error');
        return;
    }
    
    if (!currentImageData) {
        showAlert('Please capture a photo first', 'error');
        return;
    }
    
    const submitBtn = document.getElementById('submitRegBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '⏳ Registering...';
    
    try {
        const response = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                roll_number: rollNumber,
                email: email,
                image: currentImageData
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('Employee registered successfully!', 'success');
            // Reset form
            document.getElementById('regName').value = '';
            document.getElementById('regRoll').value = '';
            document.getElementById('regEmail').value = '';
            document.getElementById('imagePreview').style.display = 'none';
            currentImageData = null;
            // Refresh students list
            loadStudents();
        } else {
            showAlert(data.message || 'Registration failed', 'error');
        }
    } catch (error) {
        showAlert('Network error. Is the server running?', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '✅ Register Employee';
    }
}

// ===== Face Recognition & Attendance =====
async function autoScanAndMark() {
    if (isProcessingScan || isPaused || !videoStream) return;
    
    const video = document.getElementById('camera');
    const canvas = document.getElementById('captureCanvas');
    const resultDiv = document.getElementById('recognitionResult');
    
    if (!video || !canvas || !resultDiv) return;
    
    isProcessingScan = true;
    
    try {
        const context = canvas.getContext('2d');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);
        
        const scanImageData = canvas.toDataURL('image/jpeg', 0.9);
        
        // Show status while scanning
        if (resultDiv.style.display !== 'block' || resultDiv.innerHTML.includes('success') || resultDiv.innerHTML.includes('error')) {
            resultDiv.innerHTML = '<div style="text-align:center;color:var(--primary);font-weight:600;"><div class="spinner"></div>🔍 Scanning... Please look at the camera.</div>';
            resultDiv.style.display = 'block';
        }
        
        const response = await fetch(`${API_BASE}/recognize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: scanImageData })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Successfully recognized! Pause scanning and display success card
            isPaused = true;
            resultDiv.innerHTML = '';
            
            const livenessStatus = document.getElementById('liveness-status');
            if (livenessStatus) livenessStatus.style.display = 'none';
            
            // Show preview of the captured frame
            const preview = document.getElementById('imagePreview');
            if (preview) {
                preview.src = scanImageData;
                preview.style.display = 'block';
            }
            // Freeze video display
            video.style.display = 'none';
            
            resultDiv.innerHTML = `
                <div class="result-card success">
                    <div class="result-avatar">👤</div>
                    <h2>✅ ${data.name}</h2>
                    <p>Roll: <strong>${data.roll_number}</strong></p>
                    <p>Confidence: <strong>${(data.confidence * 100).toFixed(1)}%</strong></p>
                    <p style="margin-top:1rem;color:var(--secondary);font-size:1.1rem;font-weight:bold;">
                        🎉 ${data.attendance_status}
                    </p>
                    ${data.time ? `<p>Time: ${data.time}</p>` : ''}
                    <div style="margin-top:1.5rem;">
                        <button class="btn btn-primary" onclick="resumeScanning()">🔄 Scan Next Person</button>
                    </div>
                </div>
            `;
            
            // Refresh stats if on dashboard
            if (document.getElementById('presentToday')) {
                loadStats();
                loadTodayAttendance();
            }
        } else {
            const livenessStatus = document.getElementById('liveness-status');
            if (data.error === "liveness_failed") {
                resultDiv.innerHTML = '';
                if (livenessStatus) {
                    livenessStatus.innerHTML = `🛡️ ${data.message}`;
                    livenessStatus.style.display = 'block';
                    livenessStatus.style.backgroundColor = '#fee2e2';
                    livenessStatus.style.color = '#dc2626';
                    livenessStatus.style.border = '1px solid #f87171';
                }
            } else {
                if (livenessStatus) livenessStatus.style.display = 'none';
                
                // Face not recognized or not detected
                if (data.message && data.message.includes("No face detected")) {
                    resultDiv.innerHTML = '<div style="text-align:center;color:var(--gray);font-weight:600;">📷 Camera active. Position your face in the guide.</div>';
                } else {
                    resultDiv.innerHTML = `<div style="text-align:center;color:var(--danger);font-weight:600;">❌ ${data.message || 'Face not recognized'}</div>`;
                }
            }
        }
    } catch (error) {
        console.error("Auto scan error:", error);
    } finally {
        isProcessingScan = false;
    }
}

function resumeScanning() {
    isPaused = false;
    const video = document.getElementById('camera');
    const preview = document.getElementById('imagePreview');
    const resultDiv = document.getElementById('recognitionResult');
    const livenessStatus = document.getElementById('liveness-status');
    
    if (livenessStatus) livenessStatus.style.display = 'none';
    
    if (video) video.style.display = 'block';
    if (preview) preview.style.display = 'none';
    if (resultDiv) {
        resultDiv.innerHTML = '<div style="text-align:center;color:var(--primary);font-weight:600;"><div class="spinner"></div>🔍 Scanning... Please look at the camera.</div>';
    }
}

// ===== Load All Students =====
async function loadStudents() {
    const tbody = document.getElementById('studentsTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;"><div class="spinner"></div></td></tr>';
    
    try {
        const response = await fetch(`${API_BASE}/students`);
        const data = await response.json();
        
        tbody.innerHTML = '';
        
        if (data.students.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:2rem;">No employees registered yet</td></tr>';
            return;
        }
        
        data.students.forEach(student => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <div style="display:flex;align-items:center;gap:0.75rem;">
                        <div style="width:40px;height:40px;border-radius:50%;background:var(--primary);color:white;display:flex;align-items:center;justify-content:center;font-weight:bold;">
                            ${student.name.charAt(0)}
                        </div>
                        <strong>${student.name}</strong>
                    </div>
                </td>
                <td>${student.roll_number}</td>
                <td>${student.email || '-'}</td>
                <td><span class="status-badge status-present">Registered</span></td>
                <td>
                    <button class="btn btn-danger" style="padding: 0.25rem 0.75rem; font-size: 0.85rem;" onclick="deleteStudent(${student.id})">
                        🗑️ Delete
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--danger);">Failed to load employees</td></tr>';
    }
}

// ===== Delete Student =====
async function deleteStudent(studentId) {
    if (!confirm('Are you sure you want to delete this employee and all their attendance records?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/students/${studentId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            showAlert('Employee deleted successfully', 'success');
            loadStudents();
        } else {
            showAlert(data.message || 'Failed to delete employee', 'error');
        }
    } catch (error) {
        showAlert('Network error. Failed to delete employee.', 'error');
    }
}

// ===== Export Attendance =====
async function exportAttendance() {
    const date = document.getElementById('exportDate').value;
    if (!date) {
        showAlert('Please select a date', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/export/${date}`);
        const data = await response.json();
        
        if (data.success) {
            showAlert(`Attendance exported: ${data.filename}`, 'success');
        } else {
            showAlert(data.message, 'error');
        }
    } catch (error) {
        showAlert('Export failed', 'error');
    }
}

// ===== Load Attendance History =====
async function loadHistory() {
    const tbody = document.getElementById('historyTableBody');
    const rangeLabel = document.getElementById('rangeLabel');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;"><div class="spinner"></div></td></tr>';
    
    // Determine start and end date based on filter settings
    const filterType = document.getElementById('filterType').value;
    let startStr = '';
    let endStr = '';
    let label = '';
    
    if (filterType === 'daily') {
        const dateInput = document.getElementById('historyDate').value;
        if (!dateInput) {
            showAlert('Please select a date', 'error');
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--danger);">Please select a date.</td></tr>';
            return;
        }
        startStr = dateInput;
        endStr = dateInput;
        label = new Date(dateInput).toLocaleDateString('en-US', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
    } else {
        const monthInput = document.getElementById('historyMonth').value; // format: YYYY-MM
        if (!monthInput) {
            showAlert('Please select a month', 'error');
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--danger);">Please select a month.</td></tr>';
            return;
        }
        
        const [year, month] = monthInput.split('-');
        startStr = `${monthInput}-01`;
        
        // Find last day of the selected month
        const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
        endStr = `${monthInput}-${String(lastDay).padStart(2, '0')}`;
        
        label = new Date(parseInt(year), parseInt(month) - 1).toLocaleDateString('en-US', {
            year: 'numeric', month: 'long'
        });
    }
    
    if (rangeLabel) {
        rangeLabel.textContent = label;
    }
    
    try {
        const response = await fetch(`${API_BASE}/attendance/range?start=${startStr}&end=${endStr}`);
        const data = await response.json();
        
        tbody.innerHTML = '';
        
        if (!data.success || data.records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:2rem;">No attendance records found for this period.</td></tr>';
            return;
        }
        
        data.records.forEach(record => {
            let badgeClass = 'status-present';
            if (record.status.includes('Late') || record.status.includes('Early') || record.status.includes('No Check-out')) {
                badgeClass = 'status-absent';
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${record.date}</td>
                <td><strong>${record.name}</strong></td>
                <td>${record.roll_number}</td>
                <td>${record.check_in || '-'}</td>
                <td>${record.check_out || '-'}</td>
                <td><span class="status-badge ${badgeClass}">✓ ${record.status}</span></td>
                <td>
                    <button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.85rem;" onclick="viewAuditLogs(${record.student_id}, '${record.date}')">
                        👁️ Details
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--danger);">Failed to load history logs.</td></tr>';
    }
}

// ===== Export History CSV =====
async function exportHistoryCsv() {
    const filterType = document.getElementById('filterType').value;
    let startStr = '';
    let endStr = '';
    
    if (filterType === 'daily') {
        const dateInput = document.getElementById('historyDate').value;
        if (!dateInput) {
            showAlert('Please select a date', 'error');
            return;
        }
        startStr = dateInput;
        endStr = dateInput;
    } else {
        const monthInput = document.getElementById('historyMonth').value;
        if (!monthInput) {
            showAlert('Please select a month', 'error');
            return;
        }
        const [year, month] = monthInput.split('-');
        startStr = `${monthInput}-01`;
        const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
        endStr = `${monthInput}-${String(lastDay).padStart(2, '0')}`;
    }
    
    try {
        const response = await fetch(`${API_BASE}/export/range?start=${startStr}&end=${endStr}`);
        const data = await response.json();
        
        if (data.success) {
            showAlert(`Attendance exported: ${data.filename}`, 'success');
        } else {
            showAlert(data.message || 'Export failed', 'error');
        }
    } catch (error) {
        showAlert('Export failed due to a network error.', 'error');
    }
}

// ===== Settings & Maintenance Functions =====
async function saveSystemSettings() {
    const orgName = document.getElementById('orgName').value.trim();
    const tolerance = parseFloat(document.getElementById('tolerance').value);
    const cooldown = parseInt(document.getElementById('cooldown').value);
    
    // Expected times
    const expectedCheckInTimeEl = document.getElementById('expectedCheckInTime');
    const expectedCheckInTime = expectedCheckInTimeEl ? expectedCheckInTimeEl.value : '09:00';
    
    const expectedCheckOutTimeEl = document.getElementById('expectedCheckOutTime');
    const expectedCheckOutTime = expectedCheckOutTimeEl ? expectedCheckOutTimeEl.value : '17:00';
    
    // Admin username field
    const adminUsernameEl = document.getElementById('adminUsername');
    const adminUsername = adminUsernameEl ? adminUsernameEl.value.trim() : '';
    
    // Optional password field
    const newPasswordEl = document.getElementById('newPassword');
    const newPassword = newPasswordEl ? newPasswordEl.value : '';
    
    if (!orgName || isNaN(tolerance) || isNaN(cooldown)) {
        showAlert('Please provide valid settings values', 'error');
        return;
    }
    
    const saveBtn = document.getElementById('saveSettingsBtn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '⏳ Saving Settings...';
    
    try {
        const payload = {
            org_name: orgName,
            tolerance: tolerance,
            cooldown: cooldown,
            expected_check_in_time: expectedCheckInTime,
            expected_check_out_time: expectedCheckOutTime
        };
        
        if (adminUsername) {
            payload.admin_username = adminUsername;
        }
        
        if (newPassword && newPassword.trim()) {
            payload.new_password = newPassword.trim();
        }
        
        const response = await fetch(`${API_BASE}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (data.success) {
            showAlert('Settings saved successfully!', 'success');
            if (newPasswordEl) newPasswordEl.value = ''; // clear input
            await loadGlobalSettings();
        } else {
            showAlert(data.message || 'Failed to save settings', 'error');
        }
    } catch (error) {
        showAlert('Network error. Failed to save settings.', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '💾 Save Settings';
    }
}

async function clearDeepFaceCache() {
    if (!confirm('Are you sure you want to clear the representations cache? The next scan might take a few extra seconds to rebuild it.')) {
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/settings/clear-cache`, {
            method: 'POST'
        });
        const data = await response.json();
        if (data.success) {
            showAlert('DeepFace representations cache cleared successfully!', 'success');
        } else {
            showAlert(data.message || 'Failed to clear cache', 'error');
        }
    } catch (error) {
        showAlert('Network error. Failed to clear cache.', 'error');
    }
}

async function triggerDatabaseReset() {
    const firstConfirm = confirm('⚠️ WARNING: This will permanently delete ALL students and attendance history records from the system. This action CANNOT BE UNDONE. Are you sure you want to proceed?');
    if (!firstConfirm) return;
    
    const secondConfirm = confirm('🚨 FINAL CONFIRMATION: You are about to wipe the database entirely. Confirm that you want to delete all data.');
    if (!secondConfirm) return;
    
    try {
        const response = await fetch(`${API_BASE}/settings/reset-database`, {
            method: 'POST'
        });
        const data = await response.json();
        if (data.success) {
            showAlert('Database and student photo assets reset successfully!', 'success');
            // Refresh lists if present
            if (document.getElementById('studentsTableBody')) {
                loadStudents();
            }
            if (document.getElementById('totalStudents')) {
                loadStats();
                loadTodayAttendance();
            }
        } else {
            showAlert(data.message || 'Failed to reset database', 'error');
        }
    } catch (error) {
        showAlert('Network error. Failed to reset database.', 'error');
    }
}

function logoutUser() {
    sessionStorage.removeItem('isLoggedIn');
    window.location.href = 'login.html';
}

// ===== Initialize Page =====
document.addEventListener('DOMContentLoaded', async () => {
    // Load global settings first
    await loadGlobalSettings();

    // Load stats on dashboard
    if (document.getElementById('totalStudents')) {
        loadStats();
        loadTodayAttendance();
    }
    
    // Load students on students page
    if (document.getElementById('studentsTableBody')) {
        loadStudents();
    }
    
    // Auto-start camera if on attendance page
    if (document.getElementById('camera')) {
        startCamera('camera');
    }
    
    // Set today's date for export
    const exportDateInput = document.getElementById('exportDate');
    if (exportDateInput) {
        exportDateInput.value = new Date().toISOString().split('T')[0];
    }
});

// ===== Audit Log Modal =====
async function viewAuditLogs(studentId, date) {
    const modal = document.getElementById('auditModal');
    const subtitle = document.getElementById('auditModalSubtitle');
    const timeline = document.getElementById('auditTimeline');
    
    if (!modal) return;
    
    subtitle.textContent = `Loading logs for ${date}...`;
    timeline.innerHTML = '<div class="spinner"></div>';
    modal.style.display = 'flex';
    
    try {
        const response = await fetch(`${API_BASE}/logs/${studentId}/${date}`);
        const data = await response.json();
        
        if (data.success) {
            timeline.innerHTML = '';
            subtitle.textContent = `Activity timeline for ${date}`;
            
            if (data.logs.length === 0) {
                timeline.innerHTML = '<p>No detailed scan logs found for this day.</p>';
                return;
            }
            
            data.logs.forEach(log => {
                const item = document.createElement('div');
                item.className = 'timeline-item';
                
                const isCheckIn = log.action === 'check_in';
                
                item.innerHTML = `
                    <div class="timeline-time">${log.time}</div>
                    <div class="timeline-action" style="color: ${isCheckIn ? 'var(--primary)' : 'var(--danger)'}">
                        ${isCheckIn ? '📥 Check-In' : '📤 Check-Out'}
                    </div>
                    ${log.photo_path ? `
                        <div class="photo-container" style="margin-top: 0.5rem; background: var(--bg); padding: 0.75rem; border-radius: 0.5rem; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="const img = this.nextElementSibling; if(img.style.display==='none'){img.style.display='block';}else{img.style.display='none';}">
                                <span style="font-weight: 600; font-size: 0.9rem; color: var(--gray);">📷 View Snapshot</span>
                                <span>▼</span>
                            </div>
                            <img src="http://localhost:5000${log.photo_path}" class="timeline-img" alt="Scan Snapshot" style="display: none; max-width: 100%; margin-top: 0.75rem; border-radius: 0.5rem; border: 1px solid var(--border);">
                        </div>
                    ` : ''}
                `;
                timeline.appendChild(item);
            });
        } else {
            timeline.innerHTML = `<p style="color:var(--danger)">Error loading logs: ${data.message}</p>`;
        }
    } catch (error) {
        timeline.innerHTML = `<p style="color:var(--danger)">Network error while loading logs.</p>`;
    }
}

function closeAuditModal() {
    const modal = document.getElementById('auditModal');
    if (modal) modal.style.display = 'none';
}