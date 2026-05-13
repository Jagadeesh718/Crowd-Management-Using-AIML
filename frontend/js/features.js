/* ===================================
   Crowd Ease - New Features Module
   Tabs, Venue Map, Analytics, Notifications, Emergency
   =================================== */

// ===================================
// Tab Navigation
// ===================================
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const tab = document.getElementById('tab-' + tabId);
    if (tab) tab.classList.add('active');
    const btn = document.querySelector(`[data-tab="${tabId}"]`);
    if (btn) btn.classList.add('active');
    if (tabId === 'venue') drawVenueMap();
    if (tabId === 'analytics') refreshAnalytics();
}

// ===================================
// Notification Panel
// ===================================
let notifications = [];
let notifOpen = false;

function toggleNotifications() {
    const panel = document.getElementById('notification-panel');
    notifOpen = !notifOpen;
    panel.classList.toggle('open', notifOpen);
}

function addNotification(message, severity) {
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    notifications.unshift({ message, severity, time });
    if (notifications.length > 50) notifications = notifications.slice(0, 50);
    renderNotifications();
    const badge = document.getElementById('notification-badge');
    badge.textContent = notifications.length;
    badge.classList.add('visible');
}

function renderNotifications() {
    const list = document.getElementById('notif-list');
    if (!notifications.length) {
        list.innerHTML = '<div class="notif-empty"><i class="fas fa-check-circle"></i><p>No notifications</p></div>';
        return;
    }
    list.innerHTML = notifications.slice(0, 20).map(n =>
        `<div class="notif-item ${n.severity}">${n.message}<div class="notif-time">${n.time}</div></div>`
    ).join('');
}

function clearNotifications() {
    notifications = [];
    renderNotifications();
    const badge = document.getElementById('notification-badge');
    badge.classList.remove('visible');
}

// ===================================
// Emergency Mode
// ===================================
let emergencyActive = false;

function toggleEmergency() {
    fetch('/api/emergency/toggle', { method: 'POST' })
        .then(r => r.json())
        .then(d => {
            emergencyActive = d.active;
            const banner = document.getElementById('emergency-banner');
            const btn = document.getElementById('emergency-btn');
            banner.classList.toggle('active', emergencyActive);
            btn.classList.toggle('active', emergencyActive);
            if (emergencyActive) {
                addNotification('🚨 <strong>EMERGENCY MODE ACTIVATED</strong> — Evacuation initiated', 'critical');
                showToast('Emergency Mode Activated!', 'warning');
            } else {
                addNotification('✅ Emergency mode deactivated', 'info');
                showToast('Emergency Mode Deactivated', 'success');
            }
        })
        .catch(() => showToast('Failed to toggle emergency mode', 'error'));
}

// ===================================
// System Health Polling
// ===================================
function pollMetrics() {
    fetch('/api/metrics').then(r => r.json()).then(m => {
        const el = id => document.getElementById(id);
        if (el('ai-fps')) el('ai-fps').textContent = (m.ai_fps || 0).toFixed(1);
        if (el('stream-fps')) el('stream-fps').textContent = (m.stream_fps || 0).toFixed(1);
        if (el('ai-fps-detail')) el('ai-fps-detail').textContent = (m.ai_fps || 0).toFixed(1);
        if (el('inference-ms')) el('inference-ms').textContent = (m.avg_inference_ms || 0).toFixed(0) + 'ms';
        if (el('queue-depth')) el('queue-depth').textContent = m.queue_depth || 0;
        if (el('dropped-frames')) el('dropped-frames').textContent = m.frames_dropped || 0;
        if (el('uptime')) {
            const s = m.uptime_seconds || 0;
            const mm = Math.floor(s / 60), ss = s % 60;
            el('uptime').textContent = `${mm}:${String(ss).padStart(2, '0')}`;
        }
    }).catch(() => {});
}
setInterval(pollMetrics, 2000);

// ===================================
// Simulated Camera Bars
// ===================================
function updateSimBars(d) {
    for (const camId of ['cam2', 'cam3', 'cam4']) {
        if (!d[camId]) continue;
        const bar = document.getElementById(`${camId}-bar`);
        const label = document.getElementById(`${camId}-sim-count`);
        if (bar) bar.style.width = Math.min(100, d[camId].density || 0) + '%';
        if (label) label.textContent = d[camId].headcount + ' people';
    }
}

// ===================================
// Venue Map (Canvas)
// ===================================
let venueData = {};

function drawVenueMap() {
    const canvas = document.getElementById('venue-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0f0f1a';
    ctx.fillRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let i = 0; i < W; i += 40) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke(); }
    for (let i = 0; i < H; i += 40) { ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke(); }

    const zones = Object.entries(venueData);
    if (!zones.length) {
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '16px Inter';
        ctx.textAlign = 'center';
        ctx.fillText('Waiting for venue data...', W / 2, H / 2);
        return;
    }

    // Draw connections
    ctx.lineWidth = 2;
    zones.forEach(([id, z]) => {
        (z.connections || []).forEach(conn => {
            const target = venueData[conn];
            if (!target) return;
            ctx.strokeStyle = 'rgba(255,255,255,0.08)';
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(z.x * W, z.y * H);
            ctx.lineTo(target.x * W, target.y * H);
            ctx.stroke();
            ctx.setLineDash([]);
        });
    });

    // Draw zones
    zones.forEach(([id, z]) => {
        const cx = z.x * W, cy = z.y * H;
        const zw = z.width * W, zh = z.height * H;

        // Zone background with severity color
        const colors = { normal: '#34c759', warning: '#ff9500', critical: '#ff3b30' };
        const col = colors[z.severity] || colors.normal;

        // Glow effect
        const grd = ctx.createRadialGradient(cx, cy, 10, cx, cy, Math.max(zw, zh));
        grd.addColorStop(0, col + '40');
        grd.addColorStop(1, col + '05');
        ctx.fillStyle = grd;
        ctx.fillRect(cx - zw / 2, cy - zh / 2, zw, zh);

        // Border
        ctx.strokeStyle = col + '80';
        ctx.lineWidth = 2;
        ctx.strokeRect(cx - zw / 2, cy - zh / 2, zw, zh);

        // Zone name
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 13px Inter';
        ctx.textAlign = 'center';
        ctx.fillText(z.name, cx, cy - 12);

        // Headcount
        ctx.font = 'bold 22px Inter';
        ctx.fillStyle = col;
        ctx.fillText(z.headcount, cx, cy + 14);

        // Density bar
        const barW = zw * 0.6, barH = 5;
        const barX = cx - barW / 2, barY = cy + 22;
        ctx.fillStyle = 'rgba(255,255,255,0.1)';
        ctx.fillRect(barX, barY, barW, barH);
        ctx.fillStyle = col;
        ctx.fillRect(barX, barY, barW * (z.density / 100), barH);

        // Capacity text
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '10px Inter';
        ctx.fillText(`${z.density}% of ${z.capacity}`, cx, barY + 16);
    });

    // Animated dots (flow particles)
    const time = Date.now() / 1000;
    zones.forEach(([id, z]) => {
        (z.connections || []).forEach(conn => {
            const target = venueData[conn];
            if (!target) return;
            const count = Math.max(1, Math.min(4, Math.floor(z.headcount / 5)));
            for (let i = 0; i < count; i++) {
                const t = ((time * 0.3 + i * 0.25) % 1);
                const px = z.x * W + (target.x * W - z.x * W) * t;
                const py = z.y * H + (target.y * H - z.y * H) * t;
                ctx.beginPath();
                ctx.arc(px, py, 2, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 122, 255, ${0.6 - t * 0.4})`;
                ctx.fill();
            }
        });
    });

    // Update sidebar
    updateZoneSidebar(zones);
}

function updateZoneSidebar(zones) {
    const list = document.getElementById('zone-list');
    if (!list) return;
    const colors = { normal: '#34c759', warning: '#ff9500', critical: '#ff3b30' };
    list.innerHTML = zones.map(([id, z]) => `
        <div class="zone-item">
            <div class="zone-info">
                <div class="zone-dot" style="background:${colors[z.severity] || colors.normal}"></div>
                <span class="zone-name">${z.name}</span>
            </div>
            <div class="zone-stats">
                <div class="zone-count" style="color:${colors[z.severity]}">${z.headcount}</div>
                <div class="zone-density">${z.density}% density</div>
            </div>
        </div>`).join('');

    // Flow summary
    const total = zones.reduce((s, [, z]) => s + z.headcount, 0);
    const busiest = zones.reduce((a, b) => b[1].headcount > (a ? a[1].headcount : 0) ? b : a, null);
    const avgDensity = zones.length ? Math.round(zones.reduce((s, [, z]) => s + z.density, 0) / zones.length) : 0;
    const el = id => document.getElementById(id);
    if (el('flow-total')) el('flow-total').textContent = total;
    if (el('flow-busiest')) el('flow-busiest').textContent = busiest ? busiest[1].name : '—';
    if (el('flow-avg-density')) el('flow-avg-density').textContent = avgDensity + '%';
}

// Animate venue map
let venueAnimFrame;
function animateVenue() {
    const tab = document.getElementById('tab-venue');
    if (tab && tab.classList.contains('active')) drawVenueMap();
    venueAnimFrame = requestAnimationFrame(animateVenue);
}
animateVenue();

// Listen for venue updates
if (typeof socket !== 'undefined') {
    socket.on('venue_update', d => {
        venueData = d;
        // Update emergency stats
        let total = 0;
        Object.values(d).forEach(z => total += z.headcount);
        const evacEl = document.getElementById('evac-people');
        const evacTime = document.getElementById('evac-time');
        if (evacEl) evacEl.textContent = total + ' people';
        if (evacTime) evacTime.textContent = '~' + Math.max(1, Math.ceil(total / 20)) + ' min to evacuate';
    });
}

// ===================================
// Analytics Tab Charts
// ===================================
let trendChart = null, zoneChart = null;

function initAnalyticsCharts() {
    const trendCtx = document.getElementById('analytics-trend-chart');
    const zoneCtx = document.getElementById('analytics-zone-chart');
    if (!trendCtx || !zoneCtx) return;

    trendChart = new Chart(trendCtx.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Entrance', data: [], borderColor: '#007aff', backgroundColor: 'rgba(0,122,255,0.05)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 },
                { label: 'Stage', data: [], borderColor: '#ff9500', backgroundColor: 'rgba(255,149,0,0.05)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 },
                { label: 'Food Court', data: [], borderColor: '#34c759', backgroundColor: 'rgba(52,199,89,0.05)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 },
                { label: 'Exit', data: [], borderColor: '#af52de', backgroundColor: 'rgba(175,82,222,0.05)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
            scales: { x: { display: false }, y: { grid: { color: '#f0f0f2' }, ticks: { font: { size: 10 } } } }
        }
    });

    zoneChart = new Chart(zoneCtx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['Entrance', 'Stage', 'Food Court', 'Exit'],
            datasets: [{
                label: 'Current',
                data: [0, 0, 0, 0],
                backgroundColor: ['#007aff', '#ff9500', '#34c759', '#af52de'],
                borderRadius: 8, barThickness: 40
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { grid: { color: '#f0f0f2' }, ticks: { font: { size: 10 } } }, x: { grid: { display: false } } }
        }
    });
}

function refreshAnalytics() {
    if (!trendChart) initAnalyticsCharts();
    if (typeof data === 'undefined') return;

    // Update overview cards
    const total = Object.values(data).reduce((s, c) => s + (c.headcount || 0), 0);
    const allPeaks = Object.values(peaks || {});
    const peak = allPeaks.length ? Math.max(...allPeaks) : 0;

    const el = id => document.getElementById(id);
    if (el('an-total')) el('an-total').textContent = total;
    if (el('an-peak')) el('an-peak').textContent = peak;
    if (el('an-alerts')) el('an-alerts').textContent = alerts || 0;

    // Uptime
    fetch('/api/metrics').then(r => r.json()).then(m => {
        const s = m.uptime_seconds || 0;
        const mm = Math.floor(s / 60), ss = s % 60;
        if (el('an-uptime')) el('an-uptime').textContent = `${mm}:${String(ss).padStart(2, '0')}`;
    }).catch(() => {});

    // Update trend chart
    if (trendChart) {
        const cams = ['cam1', 'cam2', 'cam3', 'cam4'];
        const cam1hist = (data.cam1 && data.cam1.history) || [];
        const labels = cam1hist.map(h => h.time);
        trendChart.data.labels = labels;
        cams.forEach((c, i) => {
            const hist = (data[c] && data[c].history) || [];
            trendChart.data.datasets[i].data = hist.map(h => h.count);
        });
        trendChart.update('none');
    }

    // Update zone bar chart
    if (zoneChart) {
        const vals = ['cam1', 'cam2', 'cam3', 'cam4'].map(c => (data[c] && data[c].headcount) || 0);
        zoneChart.data.datasets[0].data = vals;
        zoneChart.update('none');
    }
}

// Refresh analytics periodically
setInterval(() => {
    const tab = document.getElementById('tab-analytics');
    if (tab && tab.classList.contains('active')) refreshAnalytics();
}, 3000);

// ===================================
// Hook into existing camera_update
// ===================================
if (typeof socket !== 'undefined') {
    socket.on('camera_update', d => { updateSimBars(d); });
}
