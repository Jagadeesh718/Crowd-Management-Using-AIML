/* ===================================
   Crowd Ease - Main JavaScript
   =================================== */

// Socket connection
const socket = io();

// ===================================
// Inline Toast Notifications (replaces alert())
// ===================================
function showToast(message, type = 'info') {
    // Remove existing toast
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    
    const icons = {
        error: 'fas fa-exclamation-circle',
        success: 'fas fa-check-circle',
        info: 'fas fa-info-circle',
        warning: 'fas fa-exclamation-triangle'
    };
    
    toast.innerHTML = `
        <i class="${icons[type] || icons.info}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto remove
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function showInlineError(message) {
    showToast(message, 'error');
}

function showInlineSuccess(message) {
    showToast(message, 'success');
}

function showCrowdAlert(camId, count, severity) {
    const cameraName = cameraNames[camId] || camId;
    let message = '';
    let msgClass = '';
    
    if (severity === 'critical') {
        message = `🚨 <strong>CRITICAL:</strong> ${cameraName} has reached ${count} people! Immediate attention required.`;
        msgClass = 'alert';
        playAlertSound('critical');
    } else if (severity === 'warning') {
        message = `⚠️ <strong>WARNING:</strong> ${cameraName} crowd increasing - now ${count} people.`;
        msgClass = 'alert warning';
        playAlertSound('warning');
    } else {
        message = `📈 <strong>Notice:</strong> ${cameraName} headcount increased to ${count} people.`;
        msgClass = 'info';
    }
    
    // Add to chatbot
    addMsg(message, msgClass);
    
    // Add to notification panel
    if (typeof addNotification === 'function') {
        addNotification(message, severity);
    }
    
    // Update alert count
    alerts++;
    document.getElementById('alert-count').textContent = alerts;
    
    // Update unread badge if chatbot is closed
    if (!chatbotOpen) {
        unreadAlerts++;
        updateChatbotBadge();
    }
    
    // Flash the camera card
    const card = document.querySelector(`[data-camera="${camId}"]`);
    if (card) {
        card.classList.add(severity === 'critical' ? 'critical' : 'warning-flash');
        setTimeout(() => {
            card.classList.remove('critical', 'warning-flash');
        }, 3000);
    }
}

// State variables
let selected = 'cam1';
let data = {};
let alerts = 0;
let unreadAlerts = 0;
let chatbotOpen = false;
let peaks = { cam1: 0, cam2: 0, cam3: 0, cam4: 0 };
let lastHeadcount = { cam1: 0, cam2: 0, cam3: 0, cam4: 0 };
let heatmapEnabled = false;

// Thresholds for crowd alerts
const WARNING_THRESHOLD = 3;
const CRITICAL_THRESHOLD = 5;

// Camera names mapping
const cameraNames = {
    cam1: 'Main Entrance',
    cam2: 'Stage Area',
    cam3: 'Food Court',
    cam4: 'Exit Gate'
};

// ===================================
// Chart Initialization
// ===================================
const ctx = document.getElementById('chart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            data: [],
            borderColor: '#007aff',
            backgroundColor: 'rgba(0,122,255,0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            borderWidth: 2
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: {
                display: true,
                grid: { color: '#f0f0f2' },
                ticks: { color: '#86868b', font: { size: 10 }, stepSize: 1 }
            }
        }
    }
});

// ===================================
// Socket Event Handlers
// ===================================
socket.on('connect', () => {
    addBot('🟢 Connected to Crowd Ease monitoring system');
});

socket.on('camera_frame', (d) => {
    if (d.camera === 'cam1') {
        const img = document.getElementById('cam1-img');
        const ph = document.querySelector('#cam1-feed .placeholder');
        img.src = 'data:image/jpeg;base64,' + d.frame;
        img.style.display = 'block';
        if (ph) ph.style.display = 'none';
    }
});

socket.on('camera_update', (d) => {
    data = d;
    
    // Check for headcount changes and show notifications
    for (const camId of ['cam1', 'cam2', 'cam3', 'cam4']) {
        if (d[camId] && d[camId].status === 'online') {
            const currentCount = d[camId].headcount;
            const prevCount = lastHeadcount[camId];
            
            // Detect significant increase
            if (currentCount > prevCount) {
                // Critical threshold crossed
                if (currentCount >= CRITICAL_THRESHOLD && prevCount < CRITICAL_THRESHOLD) {
                    showCrowdAlert(camId, currentCount, 'critical');
                }
                // Warning threshold crossed
                else if (currentCount >= WARNING_THRESHOLD && prevCount < WARNING_THRESHOLD) {
                    showCrowdAlert(camId, currentCount, 'warning');
                }
                // General increase notification (only if significant jump)
                else if (currentCount - prevCount >= 2) {
                    showCrowdAlert(camId, currentCount, 'info');
                }
            }
            
            lastHeadcount[camId] = currentCount;
        }
    }
    
    updateCams(d);
    if (d[selected]) updateStats(d[selected]);
    // Update simulated camera bars
    if (typeof updateSimBars === 'function') updateSimBars(d);
});

socket.on('new_alert', (a) => {
    alerts++;
    document.getElementById('alert-count').textContent = alerts;
    addMsg(a.message, a.severity === 'critical' ? 'alert' : 'alert warning');
    
    // Update unread badge if chatbot is closed
    if (!chatbotOpen) {
        unreadAlerts++;
        updateChatbotBadge();
    }
    
    const card = document.querySelector(`[data-camera="${a.camera}"]`);
    if (card) {
        card.classList.add('critical');
        setTimeout(() => card.classList.remove('critical'), 5000);
    }
    playAlertSound(a.severity);
});

socket.on('chatbot_response', (d) => {
    addBot(d.message);
});

// ===================================
// Camera Functions
// ===================================
function selectCamera(id) {
    // Update active state
    document.querySelectorAll('.camera-card').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-camera="${id}"]`).classList.add('active');
    selected = id;
    
    // Update selected camera name
    document.getElementById('selected-name').textContent = cameraNames[id];
    
    // Update stats
    if (data[id]) updateStats(data[id]);
    
    // Notify server
    socket.emit('select_camera', { camera_id: id });
}

function updateCams(d) {
    let total = 0;
    
    for (const [id, cam] of Object.entries(d)) {
        total += cam.headcount;
        
        // Update count with color coding
        const el = document.getElementById(`${id}-count`);
        el.textContent = cam.headcount;
        el.className = 'camera-stat-value ' + 
            (cam.headcount >= 3 ? 'critical' : cam.headcount >= 2 ? 'warning' : 'normal');
        
        // Update density
        document.getElementById(`${id}-density`).textContent = cam.density + '%';
        
        // Update trend indicator if available
        const trendEl = document.getElementById(`${id}-trend`);
        if (trendEl && cam.trend) {
            const trendIcon = cam.trend === 'increasing' ? 'fa-arrow-up' : 
                              cam.trend === 'decreasing' ? 'fa-arrow-down' : 'fa-minus';
            const trendClass = cam.trend === 'increasing' ? 'trend-up' : 
                               cam.trend === 'decreasing' ? 'trend-down' : 'trend-stable';
            trendEl.innerHTML = `<i class="fas ${trendIcon}"></i>`;
            trendEl.className = `trend-indicator ${trendClass}`;
        }
        
        // Track peaks
        if (cam.headcount > peaks[id]) peaks[id] = cam.headcount;
    }
    
    // Update total count in header
    document.getElementById('total-people').textContent = total;
}

function updateStats(cam) {
    // Current count with color
    const el = document.getElementById('cur-count');
    el.textContent = cam.headcount;
    el.style.color = cam.headcount >= 3 ? '#ff3b30' : cam.headcount >= 2 ? '#ff9500' : '#34c759';
    
    // Density
    document.getElementById('cur-density').textContent = cam.density + '%';
    
    // Peak
    document.getElementById('peak').textContent = peaks[selected];
    
    // Average and chart update
    if (cam.history?.length) {
        const avg = Math.round(cam.history.reduce((s, h) => s + h.count, 0) / cam.history.length);
        document.getElementById('avg').textContent = avg;
        
        chart.data.labels = cam.history.map(h => h.time);
        chart.data.datasets[0].data = cam.history.map(h => h.count);
        chart.update('none');
    }
}

// ===================================
// Chat Functions
// ===================================
function send() {
    const input = document.getElementById('input');
    const msg = input.value.trim();
    
    if (msg) {
        addMsg(msg, 'user');
        socket.emit('chatbot_message', { message: msg });
        input.value = '';
    }
}

function quickMsg(type) {
    addMsg(type, 'user');
    socket.emit('chatbot_message', { message: type });
}

function addMsg(txt, type) {
    const container = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `message ${type}`;
    
    const time = new Date().toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    div.innerHTML = `${txt.replace(/\n/g, '<br>')}<div class="msg-time">${time}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addBot(txt) {
    addMsg(txt, 'bot');
}

// ===================================
// Utility Functions
// ===================================
function playAlertSound(severity) {
    try {
        const audioCtx = new AudioContext();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        oscillator.frequency.value = severity === 'critical' ? 800 : 500;
        gainNode.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.3);
    } catch (e) {
        console.log('Audio not supported');
    }
}

// Handle Enter key in chat input
document.getElementById('input').addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        send();
    }
});

// ===================================
// Chatbot Popup Functions
// ===================================
function toggleChatbot() {
    const popup = document.getElementById('chatbot-popup');
    const fab = document.getElementById('chatbot-fab');
    const fabIcon = document.getElementById('fab-icon');
    
    chatbotOpen = !chatbotOpen;
    
    if (chatbotOpen) {
        popup.classList.add('open');
        fab.classList.add('open');
        fabIcon.className = 'fas fa-times';
        
        // Clear unread alerts when opened
        unreadAlerts = 0;
        updateChatbotBadge();
        
        // Focus input
        setTimeout(() => {
            document.getElementById('input').focus();
        }, 300);
    } else {
        popup.classList.remove('open');
        fab.classList.remove('open');
        fabIcon.className = 'fas fa-robot';
    }
}

function updateChatbotBadge() {
    const badge = document.getElementById('fab-badge');
    
    if (unreadAlerts > 0) {
        badge.textContent = unreadAlerts > 9 ? '9+' : unreadAlerts;
        badge.classList.add('visible');
    } else {
        badge.classList.remove('visible');
    }
}

// Close chatbot when clicking outside
document.addEventListener('click', (event) => {
    const popup = document.getElementById('chatbot-popup');
    const fab = document.getElementById('chatbot-fab');
    
    if (chatbotOpen && 
        !popup.contains(event.target) && 
        !fab.contains(event.target)) {
        toggleChatbot();
    }
});

// Prevent closing when clicking inside popup
document.getElementById('chatbot-popup').addEventListener('click', (event) => {
    event.stopPropagation();
});

// ===================================
// Missing Persons Functions
// ===================================
let missingPersons = [];
let selectedPhotoFile = null;

function openMissingPersonsPanel() {
    const modal = document.getElementById('missing-persons-modal');
    modal.classList.add('open');
    loadMissingPersons();
}

function closeMissingPersonsPanel() {
    const modal = document.getElementById('missing-persons-modal');
    modal.classList.remove('open');
    clearPhotoPreview();
}

function previewPhoto(event) {
    const file = event.target.files[0];
    if (file) {
        selectedPhotoFile = file;
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('upload-preview');
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
        };
        reader.readAsDataURL(file);
    }
}

function clearPhotoPreview() {
    const preview = document.getElementById('upload-preview');
    const fileInput = document.getElementById('person-photo');
    preview.innerHTML = '<i class="fas fa-user-plus"></i><span>Click to upload photo</span>';
    fileInput.value = '';
    selectedPhotoFile = null;
}

function addMissingPerson() {
    const nameInput = document.getElementById('person-name');
    const addBtn = document.querySelector('.add-btn');
    const name = nameInput.value.trim();
    
    if (!name) {
        showInlineError('Please enter the person\'s name');
        return;
    }
    
    if (!selectedPhotoFile) {
        showInlineError('Please upload a photo');
        return;
    }
    
    // Show loading state immediately
    addBtn.disabled = true;
    addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    
    // Get the preview image for instant display
    const previewImg = document.querySelector('#upload-preview img');
    const tempPhotoSrc = previewImg ? previewImg.src : null;
    
    // Add temporary card immediately for instant feedback
    if (tempPhotoSrc) {
        const tempPerson = {
            id: 'temp-' + Date.now(),
            name: name,
            photo: tempPhotoSrc,
            isTemp: true
        };
        missingPersons.push(tempPerson);
        renderMissingPersons();
    }
    
    const formData = new FormData();
    formData.append('name', name);
    formData.append('photo', selectedPhotoFile);
    
    fetch('/api/missing-persons', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Reset button state
        addBtn.disabled = false;
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Person';
        
        if (data.success) {
            nameInput.value = '';
            clearPhotoPreview();
            
            // Reload to get actual data from server
            loadMissingPersons();
            updateMissingPersonsBadge();
            
            // Add notification to chatbot
            addBot(`🔍 New missing person added: <strong>${name}</strong>. Now actively searching in all camera feeds.`);
            showInlineSuccess(`${name} added successfully!`);
        } else {
            // Remove temp card on failure
            missingPersons = missingPersons.filter(p => !p.isTemp);
            renderMissingPersons();
            showInlineError(data.error || 'Failed to add missing person');
        }
    })
    .catch(error => {
        // Reset button state
        addBtn.disabled = false;
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Person';
        
        // Remove temp card on error
        missingPersons = missingPersons.filter(p => !p.isTemp);
        renderMissingPersons();
        
        console.error('Error adding missing person:', error);
        showInlineError('Failed to add missing person');
    });
}

function removeMissingPerson(id) {
    // Find the card and add confirmation UI
    const card = document.querySelector(`[data-person-id="${id}"]`);
    if (!card) {
        // Direct delete if card not found
        deletePersonById(id);
        return;
    }
    
    // Check if already showing confirmation
    if (card.querySelector('.confirm-delete')) {
        return;
    }
    
    // Add inline confirmation overlay
    const confirmOverlay = document.createElement('div');
    confirmOverlay.className = 'confirm-delete';
    confirmOverlay.innerHTML = `
        <p>Remove from search?</p>
        <div class="confirm-buttons">
            <button class="confirm-yes" onclick="deletePersonById('${id}')">Yes</button>
            <button class="confirm-no" onclick="cancelDelete('${id}')">No</button>
        </div>
    `;
    card.appendChild(confirmOverlay);
}

function cancelDelete(id) {
    const card = document.querySelector(`[data-person-id="${id}"]`);
    if (card) {
        const overlay = card.querySelector('.confirm-delete');
        if (overlay) overlay.remove();
    }
}

function deletePersonById(id) {
    fetch(`/api/missing-persons/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadMissingPersons();
            updateMissingPersonsBadge();
            showInlineSuccess('Person removed from search list');
        } else {
            showInlineError(data.error || 'Failed to remove person');
        }
    })
    .catch(error => {
        console.error('Error removing missing person:', error);
        showInlineError('Failed to remove person');
    });
}

function loadMissingPersons() {
    fetch('/api/missing-persons')
    .then(response => response.json())
    .then(data => {
        console.log('Loaded missing persons:', data);
        missingPersons = data.persons || [];
        renderMissingPersons();
        updateMissingPersonsBadge();
    })
    .catch(error => {
        console.error('Error loading missing persons:', error);
    });
}

function renderMissingPersons() {
    const container = document.getElementById('persons-list');
    
    if (missingPersons.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <p>No missing persons in the search list</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = missingPersons.map(person => `
        <div class="person-card ${person.isTemp ? 'loading' : ''}" data-person-id="${person.id}">
            <img src="${person.photo}" alt="${person.name}">
            <div class="person-info">
                <div class="person-name">${person.name}</div>
                <div class="person-status">
                    <i class="fas fa-${person.isTemp ? 'spinner fa-spin' : 'circle'}"></i>
                    ${person.isTemp ? 'Processing...' : 'Actively Searching'}
                </div>
            </div>
            ${person.isTemp ? '' : `<button class="remove-person" onclick="removeMissingPerson('${person.id}')" title="Remove from search">
                <i class="fas fa-times"></i>
            </button>`}
        </div>
    `).join('');
}

function updateMissingPersonsBadge() {
    const badge = document.getElementById('missing-fab-badge');
    // Filter out temp persons for count
    const actualPersons = missingPersons.filter(p => !p.isTemp);
    
    if (badge) {
        if (actualPersons.length > 0) {
            badge.textContent = actualPersons.length;
            badge.classList.add('visible');
        } else {
            badge.classList.remove('visible');
        }
    }
}

// Handle missing person found event
socket.on('missing_person_found', (data) => {
    console.log('Missing person found:', data);
    const { person_name, camera, confidence, time } = data;
    
    // Play alert sound
    playAlertSound('critical');
    
    // Add alert to chatbot
    const alertMsg = `🚨 <strong>MISSING PERSON ALERT!</strong><br>
        <strong>${person_name}</strong> may have been spotted!<br>
        📍 Camera: ${camera}<br>
        🎯 Match confidence: ${confidence}%<br>
        🕐 Time: ${time}`;
    
    addBot(alertMsg);
    
    // Increment unread count if chatbot is closed
    if (!chatbotOpen) {
        unreadAlerts++;
        updateChatbotBadge();
    }
    
    // Flash the camera feed briefly - find camera by name or use cam1
    const cameraCard = document.querySelector('[data-camera="cam1"]');
    if (cameraCard) {
        cameraCard.classList.add('person-found-flash');
        setTimeout(() => {
            cameraCard.classList.remove('person-found-flash');
        }, 3000);
    }
});

// Handle proactive crowd prediction alerts
socket.on('proactive_alert', (data) => {
    console.log('Proactive alert:', data);
    const { message, predicted_count, minutes_ahead, confidence } = data;
    
    // Play warning sound
    playAlertSound('warning');
    
    // Add alert to chatbot
    addBot(`🔮 <strong>PREDICTION ALERT</strong><br>${message}`);
    
    // Increment unread count if chatbot is closed
    if (!chatbotOpen) {
        unreadAlerts++;
        updateChatbotBadge();
    }
    
    // Flash header
    const header = document.querySelector('.header');
    if (header) {
        header.classList.add('prediction-flash');
        setTimeout(() => {
            header.classList.remove('prediction-flash');
        }, 3000);
    }
});

// Handle missing persons list update
socket.on('missing_persons_update', (data) => {
    missingPersons = data.persons || [];
    renderMissingPersons();
    updateMissingPersonsBadge();
});

// Close modal when clicking outside
document.getElementById('missing-persons-modal').addEventListener('click', (event) => {
    // Close only if clicking on the overlay itself, not the modal content
    if (event.target.id === 'missing-persons-modal') {
        closeMissingPersonsPanel();
    }
});

// Load missing persons on page load
document.addEventListener('DOMContentLoaded', () => {
    loadMissingPersons();
});

// ===================================
// Heatmap Functions
// ===================================
function toggleHeatmap() {
    fetch('/api/heatmap/toggle', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                heatmapEnabled = data.enabled;
                updateHeatmapButton();
                showToast(data.message, 'info');
                
                // Add to chatbot
                addBot(`🔥 Heatmap ${data.enabled ? 'enabled' : 'disabled'}. ${data.enabled ? 'Areas with high crowd density will show in warm colors.' : ''}`);
            }
        })
        .catch(error => {
            console.error('Error toggling heatmap:', error);
            showToast('Failed to toggle heatmap', 'error');
        });
}

function updateHeatmapButton() {
    const btn = document.getElementById('heatmap-toggle');
    if (btn) {
        if (heatmapEnabled) {
            btn.classList.add('active');
            btn.title = 'Disable Heatmap';
        } else {
            btn.classList.remove('active');
            btn.title = 'Enable Heatmap';
        }
    }
}

// Handle heatmap status from server
socket.on('heatmap_status', (data) => {
    heatmapEnabled = data.enabled;
    updateHeatmapButton();
});

// ===================================
// Export Reports Functions
// ===================================
function downloadReport(format) {
    showToast(`Opening ${format.toUpperCase()} report...`, 'info');
    
    if (format === 'csv') {
        window.open('/api/reports/export/csv', '_blank');
    } else {
        window.open('/api/reports/export/json', '_blank');
    }
}

// Quick export from chatbot
function handleReportCommand(type) {
    if (type === 'csv' || type === 'json') {
        exportReport(type);
    } else {
        // Show summary
        fetch('/api/reports/summary')
            .then(response => response.json())
            .then(data => {
                const summary = data.summary;
                const msg = `📊 <strong>Session Summary</strong><br>
                    ⏱️ Duration: ${summary.session_duration}<br>
                    👥 Peak Headcount: ${summary.peak_headcount}<br>
                    🚨 Total Alerts: ${summary.total_alerts}<br>
                    🔍 Missing Person Matches: ${summary.missing_person_matches}<br>
                    📝 Events Logged: ${summary.total_events}`;
                addBot(msg);
            })
            .catch(error => {
                console.error('Error getting summary:', error);
                addBot('❌ Failed to get report summary');
            });
    }
}
