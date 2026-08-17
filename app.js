/**
 * AETHER.TRAFFIC // UI & Decision Intelligence Controller
 * High-End MagicPatterns Design Architecture
 */

let selectedFocusFeed = 1;
let activeModalFeed = 1;
let activeEmergency = false;
let currentDecision = null;
let isSimPaused = false;

const CORRIDOR_METADATA = {
    1: { title: "North Arterial", subtitle: "Deep-Dive Control & Live Telemetry", defaultPhase: "Green phase 22s" },
    2: { title: "East Boulevard", subtitle: "Downtown Commercial District", defaultPhase: "Green phase 1s" },
    3: { title: "West Parkway", subtitle: "Hospital Emergency Corridor", defaultPhase: "Green phase 9s" }
};

document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initEventListeners();
    initFeedConfigModal();
    startTelemetryLoop();
    loadAuditLogs();
});

// Real-time UTC Clock
function initClock() {
    const clockEl = document.getElementById('live-clock');
    const updateTime = () => {
        const now = new Date();
        if (clockEl) {
            clockEl.textContent = now.toTimeString().split(' ')[0];
        }
    };
    updateTime();
    setInterval(updateTime, 1000);
}

// Global Event Listeners
function initEventListeners() {
    // Pause / Resume Sim
    const btnToggleSim = document.getElementById('btn-toggle-sim');
    if (btnToggleSim) {
        btnToggleSim.addEventListener('click', () => {
            isSimPaused = !isSimPaused;
            const lbl = document.getElementById('btn-toggle-sim-label');
            if (lbl) lbl.textContent = isSimPaused ? 'Resume sim' : 'Pause sim';
            showNotification(isSimPaused ? 'Simulation paused.' : 'Simulation resumed.', 'info');
        });
    }

    // Reset System
    const btnResetSys = document.getElementById('btn-reset-system');
    if (btnResetSys) {
        btnResetSys.addEventListener('click', async () => {
            if (!confirm('Reset all telemetry, logs, and reload feeds?')) return;
            try {
                const res = await fetch('/api/system/reset', { method: 'POST' });
                const data = await res.json();
                showNotification('System telemetry and streams reset.', 'success');
                refreshVideoStreams();
                loadAuditLogs();
            } catch (e) {
                console.error(e);
                showNotification('Error resetting system', 'warning');
            }
        });
    }

    // Batch Upload Modal
    const uploadModal = document.getElementById('upload-modal');
    const btnOpenUpload = document.getElementById('btn-open-upload');
    const btnCloseUpload = document.getElementById('btn-close-upload');
    const btnCancelUpload = document.getElementById('btn-cancel-upload');
    const dropZone = document.getElementById('drop-zone');
    const videoInput = document.getElementById('video-input');
    const uploadForm = document.getElementById('upload-form');
    const fileListPreview = document.getElementById('file-list-preview');

    if (btnOpenUpload && uploadModal) {
        btnOpenUpload.addEventListener('click', () => uploadModal.style.display = 'flex');
    }
    if (btnCloseUpload && uploadModal) {
        btnCloseUpload.addEventListener('click', () => uploadModal.style.display = 'none');
    }
    if (btnCancelUpload && uploadModal) {
        btnCancelUpload.addEventListener('click', () => uploadModal.style.display = 'none');
    }

    if (dropZone && videoInput) {
        dropZone.addEventListener('click', () => videoInput.click());
        ['dragenter', 'dragover'].forEach(name => {
            dropZone.addEventListener(name, (e) => {
                e.preventDefault();
                dropZone.style.borderColor = 'var(--color-cyan)';
            });
        });
        ['dragleave', 'drop'].forEach(name => {
            dropZone.addEventListener(name, (e) => {
                e.preventDefault();
                dropZone.style.borderColor = 'rgba(0, 242, 254, 0.3)';
            });
        });
        dropZone.addEventListener('drop', (e) => {
            if (e.dataTransfer.files.length) {
                videoInput.files = e.dataTransfer.files;
                updateFilePreview();
            }
        });
        videoInput.addEventListener('change', updateFilePreview);
    }

    function updateFilePreview() {
        if (!fileListPreview) return;
        if (videoInput.files.length > 0) {
            const names = Array.from(videoInput.files).map(f => `📹 ${f.name} (${(f.size / (1024*1024)).toFixed(1)} MB)`).join('<br>');
            fileListPreview.innerHTML = `<strong>Selected ${videoInput.files.length} Video(s):</strong><br>${names}`;
        } else {
            fileListPreview.innerHTML = '';
        }
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!videoInput.files || videoInput.files.length === 0) {
                alert('Please select at least 1 video file.');
                return;
            }
            const formData = new FormData();
            for (let i = 0; i < Math.min(3, videoInput.files.length); i++) {
                formData.append('videos', videoInput.files[i]);
            }
            const submitBtn = document.getElementById('btn-submit-upload');
            if (submitBtn) {
                submitBtn.textContent = 'Uploading...';
                submitBtn.disabled = true;
            }
            try {
                const res = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.status === 'success') {
                    showNotification(data.message || 'Videos uploaded!', 'success');
                    if (uploadModal) uploadModal.style.display = 'none';
                    refreshVideoStreams();
                } else {
                    alert(data.message || 'Upload error');
                }
            } catch (err) {
                console.error(err);
                alert('Network error uploading video.');
            } finally {
                if (submitBtn) {
                    submitBtn.textContent = 'Process Videos';
                    submitBtn.disabled = false;
                }
            }
        });
    }

    // Operator Decision Approval
    const btnApprove = document.getElementById('btn-approve-decision');
    if (btnApprove) {
        btnApprove.addEventListener('click', async () => {
            await submitOperatorAction('APPROVE');
        });
    }

    // Operator Decision Rejection
    const btnReject = document.getElementById('btn-reject-decision');
    if (btnReject) {
        btnReject.addEventListener('click', async () => {
            await submitOperatorAction('REJECT');
        });
    }

    // Emergency Clearance
    const btnEmergency = document.getElementById('btn-emergency-clearance');
    if (btnEmergency) {
        btnEmergency.addEventListener('click', async () => {
            await submitOperatorAction('EMERGENCY_CLEARANCE', { corridor: 3, forced_green: 60 });
        });
    }
}

// Switch Active Focus Corridor Stage
function setActiveFocusFeed(feedId, event) {
    if (event) event.stopPropagation();
    selectedFocusFeed = feedId;

    // Update active highlight on bottom cards
    [1, 2, 3].forEach(fid => {
        const card = document.getElementById(`corridor-card-${fid}`);
        if (card) {
            if (fid === feedId) {
                card.classList.add('active');
            } else {
                card.classList.remove('active');
            }
        }
    });

    // Update top focus stage info
    const meta = CORRIDOR_METADATA[feedId] || { title: `Feed 0${feedId}`, subtitle: "Monitored Corridor" };
    const subTag = document.getElementById('focus-sub-tag');
    const roadTitle = document.getElementById('focus-road-title');
    const roadSubtitle = document.getElementById('focus-road-subtitle');
    const streamImg = document.getElementById('focus-stream-img');
    const breakdownTag = document.getElementById('breakdown-feed-tag');

    if (subTag) subTag.textContent = `UNDER REVIEW · FEED 0${feedId}`;
    if (roadTitle) roadTitle.textContent = meta.title;
    if (roadSubtitle) roadSubtitle.textContent = meta.subtitle;
    if (breakdownTag) breakdownTag.textContent = `FEED 0${feedId}`;
    if (streamImg) streamImg.src = `/api/stream/${feedId}?t=${Date.now()}`;
}

// On-Card Direct Source Switcher (Tabs under each card)
function switchCardSourceMode(feedId, mode) {
    // Mode: 'YT' | 'FILE' | 'DEMO'
    const tabYt = document.getElementById(`src-tab-yt-${feedId}`);
    const tabFile = document.getElementById(`src-tab-file-${feedId}`);
    const tabDemo = document.getElementById(`src-tab-demo-${feedId}`);

    const drawerYt = document.getElementById(`drawer-yt-${feedId}`);
    const drawerFile = document.getElementById(`drawer-file-${feedId}`);
    const drawerDemo = document.getElementById(`drawer-demo-${feedId}`);

    if (tabYt) tabYt.className = mode === 'YT' ? 'src-tab-btn active' : 'src-tab-btn';
    if (tabFile) tabFile.className = mode === 'FILE' ? 'src-tab-btn active' : 'src-tab-btn';
    if (tabDemo) tabDemo.className = mode === 'DEMO' ? 'src-tab-btn active' : 'src-tab-btn';

    if (drawerYt) drawerYt.style.display = mode === 'YT' ? 'flex' : 'none';
    if (drawerFile) drawerFile.style.display = mode === 'FILE' ? 'block' : 'none';
    if (drawerDemo) drawerDemo.style.display = mode === 'DEMO' ? 'block' : 'none';
}

// On-Card Direct YouTube Connect
async function applyCardYoutube(feedId) {
    const input = document.getElementById(`card-yt-input-${feedId}`);
    if (!input) return;
    const url = input.value.trim();
    if (!url) {
        showNotification(`Please paste a YouTube livestream / video URL for Feed 0${feedId}`, 'warning');
        input.focus();
        return;
    }

    const clean = url.replace(/\/+$/, '');
    if (clean === 'https://www.youtube.com' || clean === 'http://www.youtube.com' || clean === 'https://youtube.com' || clean === 'http://youtube.com') {
        showNotification('Please enter a specific YouTube video link (e.g. https://www.youtube.com/live/... or https://www.youtube.com/watch?v=...)', 'warning');
        input.focus();
        return;
    }

    const drawer = document.getElementById(`drawer-yt-${feedId}`);
    const applyBtn = drawer ? (drawer.querySelector('.btn-clean-connect') || drawer.querySelector('button')) : null;
    if (applyBtn) {
        applyBtn.textContent = 'Connecting...';
        applyBtn.disabled = true;
    }

    showNotification(`Extracting stream for Feed 0${feedId}...`, 'info');

    try {
        const res = await fetch('/api/feed/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                feed_id: parseInt(feedId),
                source_type: 'YOUTUBE',
                youtube_url: url
            })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            showNotification(`Feed 0${feedId} Connected: ${data.title || 'Live Stream'}`, 'success');
            if (applyBtn) applyBtn.textContent = 'Connected! ✓';
            setActiveFocusFeed(feedId);
            setTimeout(refreshVideoStreams, 400);
            setTimeout(refreshVideoStreams, 1500);
        } else {
            showNotification(data.message || `Error connecting Feed 0${feedId}`, 'error');
            if (applyBtn) applyBtn.textContent = 'Connect';
        }
    } catch (e) {
        console.error(e);
        showNotification(`Network error applying Feed 0${feedId} stream`, 'error');
        if (applyBtn) applyBtn.textContent = 'Connect';
    } finally {
        if (applyBtn) {
            setTimeout(() => {
                applyBtn.textContent = 'Connect';
                applyBtn.disabled = false;
            }, 2500);
        }
    }
}

// Quick 1-click Preset Fill
function fillCardPreset(feedId, url) {
    const input = document.getElementById(`card-yt-input-${feedId}`);
    if (input) {
        input.value = url;
        applyCardYoutube(feedId);
    }
}

// Direct File Upload on Card
async function handleDirectFeedUpload(feedId, file) {
    if (!file) return;
    showNotification(`Uploading video to Feed 0${feedId}...`, 'info');

    const formData = new FormData();
    formData.append('feed_id', feedId);
    formData.append('source_type', 'FILE');
    formData.append('video_file', file);

    try {
        const res = await fetch('/api/feed/configure', { method: 'POST', body: formData });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            showNotification(`Feed 0${feedId} video loaded successfully!`, 'success');
            refreshVideoStreams();
        } else {
            showNotification(data.message || `Error uploading video for Feed ${feedId}`, 'error');
        }
    } catch (e) {
        console.error(e);
        showNotification(`Network error uploading file to Feed ${feedId}`, 'error');
    }
}

// Reset Feed Source directly
async function setFeedSource(feedId, sourceType) {
    showNotification(`Setting Feed 0${feedId} to ${sourceType}...`, 'info');
    const formData = new FormData();
    formData.append('feed_id', feedId);
    formData.append('source_type', sourceType);

    try {
        const res = await fetch('/api/feed/configure', { method: 'POST', body: formData });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            showNotification(`Feed 0${feedId} set to ${sourceType}!`, 'success');
            refreshVideoStreams();
        } else {
            showNotification(data.message || 'Error updating source', 'error');
        }
    } catch (e) {
        console.error(e);
        showNotification('Network error setting source', 'error');
    }
}

// Green Duration Slider Readout Update
function updateDurationReadout(val) {
    const readout = document.getElementById('slider-val-readout');
    const approveTxt = document.getElementById('btn-approve-text');
    if (readout) readout.textContent = `${val}s`;
    if (approveTxt) approveTxt.textContent = `Approve ${val}s`;
}

// Toggle Reasoning Accordion
function toggleReasoningAccordion() {
    const body = document.getElementById('reasoning-body');
    const arrow = document.getElementById('accordion-arrow');
    if (!body) return;
    const isHidden = body.style.display === 'none';
    body.style.display = isHidden ? 'block' : 'none';
    if (arrow) {
        arrow.style.transform = isHidden ? 'rotate(180deg)' : 'none';
    }
}

// Submit Operator Action
async function submitOperatorAction(action, extraData = {}) {
    const slider = document.getElementById('duration-slider');
    const proposedDuration = slider ? parseInt(slider.value) : 55;

    const payload = {
        action: action,
        proposed_action: currentDecision ? currentDecision.recommended_action : "Hold Corridor Green",
        recommended_phase: currentDecision ? currentDecision.target_road : 1,
        allocated_green_time: proposedDuration,
        reasoning: currentDecision ? currentDecision.reasoning : "Operator manual optimization",
        ...extraData
    };

    try {
        const res = await fetch('/api/decision/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            showNotification(`Action "${action}" recorded in decision log.`, 'success');
            loadAuditLogs();
        } else {
            showNotification('Error logging operator action', 'error');
        }
    } catch (e) {
        console.error(e);
        showNotification('Network error recording action', 'error');
    }
}

// Real-Time Telemetry Polling Loop
function startTelemetryLoop() {
    setInterval(async () => {
        if (isSimPaused) return;
        try {
            const res = await fetch('/api/metrics/live');
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'success') {
                updateUIWithTelemetry(data);
            }
        } catch (e) {
            // Silently wait for next interval
        }
    }, 1500);
}

// Render Telemetry onto MagicPatterns UI
function updateUIWithTelemetry(data) {
    const metrics = data.metrics || {};
    const configs = data.stream_configs || {};
    const decision = data.decision || {};
    const signal = data.signal_state || {};
    currentDecision = decision;

    // 1. Update Focused Screen (Top Stage)
    const focusMetric = metrics[selectedFocusFeed] || {};
    const focusOccVal = document.getElementById('focus-occ-val');
    const focusTrackedVal = document.getElementById('focus-tracked-val');
    const focusLoadVal = document.getElementById('focus-load-val');
    const focusFpsVal = document.getElementById('focus-fps-val');
    const focusFpsHud = document.getElementById('focus-fps-hud');
    const focusObjectsHud = document.getElementById('focus-objects-hud');
    const focusSignalTxt = document.getElementById('focus-signal-txt');
    const focusCongestionBadge = document.getElementById('focus-congestion-badge');
    const focusPhaseBadge = document.getElementById('focus-phase-badge');

    const occNum = (focusMetric.density != null ? focusMetric.density : (focusMetric.occupancy_rate || 0)).toFixed(1);
    if (focusOccVal) focusOccVal.innerHTML = `${occNum}<small>%</small>`;
    if (focusTrackedVal) focusTrackedVal.textContent = focusMetric.vehicle_count != null ? focusMetric.vehicle_count : 0;
    if (focusLoadVal) focusLoadVal.textContent = (focusMetric.weighted_load || 0).toFixed(1);
    if (focusFpsVal) focusFpsVal.textContent = (focusMetric.fps || 25.0).toFixed(1);

    if (focusFpsHud) focusFpsHud.textContent = `FEED 0${selectedFocusFeed} · ${(focusMetric.fps || 25.0).toFixed(1)} fps`;
    if (focusObjectsHud) focusObjectsHud.textContent = `${focusMetric.vehicle_count || 0} tracked objects`;

    // Congestion Chip
    const congLevel = focusMetric.congestion_level || 'LOW';
    if (focusCongestionBadge) {
        focusCongestionBadge.textContent = `• ${congLevel} CONGESTION`;
        focusCongestionBadge.className = `badge-pill badge-congestion-${congLevel === 'HIGH' ? 'high' : (congLevel === 'MEDIUM' ? 'med' : 'low')}`;
    }

    // Signal HUD
    const isGreen = (signal.active_stream === selectedFocusFeed || signal.active_road === selectedFocusFeed);
    const remSec = signal.remaining_seconds != null ? signal.remaining_seconds : (signal.time_remaining || 0);
    if (focusSignalTxt) {
        focusSignalTxt.textContent = isGreen ? `SIM: GREEN (${remSec}s)` : 'SIM: RED';
    }
    if (focusPhaseBadge) {
        focusPhaseBadge.textContent = isGreen ? `• Green phase ${remSec}s` : '• Red phase';
        focusPhaseBadge.className = isGreen ? 'badge-pill badge-phase-green' : 'badge-pill badge-phase-red';
    }

    // 2. Update Monitored Corridors (Bottom 3 Panels)
    [1, 2, 3].forEach(sid => {
        const m = metrics[sid] || {};
        const cntEl = document.getElementById(`cnt-${sid}`);
        const trendEl = document.getElementById(`trend-${sid}`);
        const sigEl = document.getElementById(`card-sig-${sid}`);
        const badgeEl = document.getElementById(`congestion-badge-${sid}`);
        const liveTag = document.getElementById(`live-tag-${sid}`);
        const fpsTag = document.getElementById(`fps-tag-${sid}`);

        const cardDensity = m.density != null ? m.density : (m.occupancy_rate || 0);
        if (cntEl) cntEl.innerHTML = `${cardDensity.toFixed(1)}<small>%</small>`;
        if (trendEl) {
            const slope = m.trend_slope != null ? m.trend_slope : -0.10;
            trendEl.textContent = `${slope >= 0 ? '+' : ''}${slope.toFixed(2)}/s`;
        }
        if (fpsTag && m.fps) {
            fpsTag.textContent = `${m.fps.toFixed(1)} fps`;
        }
        if (sigEl) {
            const roadGreen = (signal.active_stream === sid || signal.active_road === sid);
            sigEl.textContent = roadGreen ? `• Green ${remSec}s` : '• Red';
            sigEl.style.color = roadGreen ? '#34d399' : '#f87171';
        }
        if (badgeEl) {
            badgeEl.textContent = m.congestion_level || 'LOW';
            badgeEl.className = `chip-cong chip-cong-${(m.congestion_level || 'low').toLowerCase()}`;
        }
        if (liveTag && configs[sid]) {
            const isYt = configs[sid].source_type === 'YOUTUBE';
            liveTag.textContent = isYt ? '• LIVE' : '⮂ REPLAY';
            liveTag.className = isYt ? 'live-dot-tag' : 'replay-dot-tag';
        }
    });

    // 3. Network Occupancy Bars
    [1, 2, 3].forEach(sid => {
        const m = metrics[sid] || {};
        const cardDensity = m.density != null ? m.density : (m.occupancy_rate || 0);
        const pct = cardDensity.toFixed(1);
        const pctEl = document.getElementById(`occ-pct-${sid}`);
        const barFill = document.getElementById(`bar-fill-${sid}`);
        if (pctEl) pctEl.textContent = `${pct}%`;
        if (barFill) barFill.style.width = `${Math.min(100, Math.max(4, cardDensity))}%`;
    });

    // 4. Vehicle Breakdown & Pedestrians ("What's out there")
    const breakdown = focusMetric.breakdown || focusMetric.class_breakdown || {};
    const totalVehicles = Math.max(1, focusMetric.vehicle_count || (breakdown.cars || 0) + (breakdown.motorcycles || 0) + (breakdown.buses || 0) + (breakdown.trucks || 0) + (breakdown.pedestrians || 0));
    const cars = breakdown.cars != null ? breakdown.cars : (breakdown.car || 0);
    const bikes = breakdown.motorcycles != null ? breakdown.motorcycles : (breakdown.motorcycle || 0);
    const buses = breakdown.buses != null ? breakdown.buses : (breakdown.bus || 0);
    const trucks = breakdown.trucks != null ? breakdown.trucks : (breakdown.truck || 0);
    const peds = breakdown.pedestrians != null ? breakdown.pedestrians : (breakdown.pedestrian || 0);
    const emergency = breakdown.emergency || 0;

    const elCars = document.getElementById('bk-cars');
    const elBikes = document.getElementById('bk-bikes');
    const elBuses = document.getElementById('bk-buses');
    const elTrucks = document.getElementById('bk-trucks');
    const elPeds = document.getElementById('bk-peds');

    if (elCars) elCars.textContent = cars;
    if (elBikes) elBikes.textContent = bikes;
    if (elBuses) elBuses.textContent = buses;
    if (elTrucks) elTrucks.textContent = trucks;
    if (elPeds) elPeds.textContent = peds;

    // Vision Engine View KPIs
    const veCars = document.getElementById('ve-cars');
    const veBikes = document.getElementById('ve-bikes');
    const veHeavy = document.getElementById('ve-heavy');
    const vePeds = document.getElementById('ve-peds');
    const veDensity = document.getElementById('ve-density');
    const veSpeed = document.getElementById('ve-speed');

    if (veCars) veCars.textContent = cars;
    if (veBikes) veBikes.textContent = bikes;
    if (veHeavy) veHeavy.textContent = buses + trucks;
    if (vePeds) vePeds.textContent = peds;
    if (veDensity) veDensity.textContent = `${focusMetric.congestion_level || 'LOW'} (${(focusMetric.density || 0).toFixed(1)}%)`;
    if (veSpeed) veSpeed.textContent = `${focusMetric.speed_mph || 36} mph`;

    // 5. Decision Engine Recommendation
    const headline = document.getElementById('action-headline');
    const subtext = document.getElementById('action-subtext');
    const reasoning = document.getElementById('engine-reasoning-content');
    const slider = document.getElementById('duration-slider');
    const govSlider = document.getElementById('gov-duration-slider');
    const govHeadline = document.getElementById('gov-rec-headline');
    const govSubtext = document.getElementById('gov-rec-subtext');
    const congChip = document.getElementById('decision-congestion-chip');

    if (decision && headline) {
        const target = decision.target_road || (decision.priority_order ? decision.priority_order[0] : 1);
        const dur = decision.allocated_green_time || (decision.recommended_timings ? decision.recommended_timings[target] : 18);
        const roadMeta = CORRIDOR_METADATA[target] || { title: `Feed 0${target}` };

        const formattedHeadline = decision.headline || `Hold ${roadMeta.title} (Feed 0${target}) green for ${dur}s`;
        const formattedSubtext = decision.subtext || `Engine proposed ${dur}s based on real-time backlog | adjustable 10-90s`;

        headline.textContent = formattedHeadline;
        if (govHeadline) govHeadline.textContent = formattedHeadline;

        if (subtext) subtext.textContent = formattedSubtext;
        if (govSubtext) govSubtext.textContent = formattedSubtext;

        if (reasoning) {
            reasoning.textContent = decision.reasoning || `Feed 0${target} (${roadMeta.title}) analyzed. Proportional ${dur}s green phase scheduled.`;
        }

        if (congChip) {
            const cong = focusMetric.congestion_level || 'LOW';
            congChip.textContent = `${cong === 'HIGH' ? 'High Congestion Detected' : (cong === 'MEDIUM' ? 'Moderate Traffic Flow' : 'Low Traffic Detected')}`;
            congChip.className = `badge-congestion-chip ${cong === 'HIGH' ? 'high' : ''}`;
        }

        if (slider && !slider.dataset.userInteracting) {
            slider.value = dur;
            updateDurationReadout(dur);
        }
        if (govSlider && !govSlider.dataset.userInteracting) {
            govSlider.value = dur;
        }
    }

    // 6. Corridor Metrics (Image 2: Avg Speed NB, Avg Speed SB, Queue Length, Phase Status)
    const curDensity = focusMetric.density != null ? focusMetric.density : (focusMetric.occupancy_rate || 0);
    const speedNb = document.getElementById('val-speed-nb');
    const speedSb = document.getElementById('val-speed-sb');
    const queueLen = document.getElementById('val-queue-len');
    const phaseStatus = document.getElementById('val-phase-status');
    const occTag = document.getElementById('current-occupancy-tag');

    const estNb = Math.max(8, Math.round(38 - (curDensity * 0.45)));
    const estSb = Math.max(14, Math.round(42 - (curDensity * 0.25)));
    const estQueue = ((focusMetric.vehicle_count || 1) * 0.12).toFixed(1);

    if (speedNb) speedNb.textContent = `${estNb} mph`;
    if (speedSb) speedSb.textContent = `${estSb} mph`;
    if (queueLen) queueLen.textContent = `${estQueue} mi`;
    if (occTag) occTag.textContent = `${curDensity.toFixed(1)}%`;

    if (phaseStatus) {
        const isGreen = (signal.active_stream === selectedFocusFeed || signal.active_road === selectedFocusFeed);
        if (isGreen) {
            phaseStatus.textContent = "Holding Green";
            phaseStatus.className = "metric-value font-mono text-emerald font-bold";
        } else {
            phaseStatus.textContent = "Transitioning";
            phaseStatus.className = "metric-value font-mono text-amber";
        }
    }

    // 7. Update Pandas Analytics Table in Tab 3
    [1, 2, 3].forEach(sid => {
        const m = metrics[sid] || {};
        const ptCnt = document.getElementById(`pt-cnt-${sid}`);
        const ptDen = document.getElementById(`pt-den-${sid}`);
        const ptLoad = document.getElementById(`pt-load-${sid}`);
        const ptLvl = document.getElementById(`pt-lvl-${sid}`);
        if (ptCnt) ptCnt.textContent = m.vehicle_count != null ? m.vehicle_count : 0;
        if (ptDen) ptDen.textContent = `${(m.density || 0).toFixed(1)}%`;
        if (ptLoad) ptLoad.textContent = (m.weighted_load || 0).toFixed(1);
        if (ptLvl) {
            const lvl = m.congestion_level || 'LOW';
            ptLvl.textContent = lvl;
            ptLvl.className = lvl === 'HIGH' ? 'text-coral' : (lvl === 'MEDIUM' ? 'text-amber' : 'text-emerald');
        }
    });

    // 8. Dynamic SVG Wave Chart (Network Occupancy Past Hour)
    updateOccupancyWave(curDensity);

    // 9. Emergency Strobe Alert
    const emergencyBanner = document.getElementById('emergency-banner');
    if (data.emergency_active && emergencyBanner) {
        emergencyBanner.style.display = 'flex';
    } else if (emergencyBanner) {
        emergencyBanner.style.display = 'none';
    }
}

// Occupancy Wave Chart Interpolation
let occupancyHistory = [18, 25, 34, 48, 62, 55, 70, 82];
function updateOccupancyWave(latestVal) {
    if (latestVal > 0) {
        occupancyHistory.push(Math.round(latestVal));
        if (occupancyHistory.length > 8) occupancyHistory.shift();
    }

    const svgH = 240;
    const svgW = 700;
    const step = svgW / (occupancyHistory.length - 1);
    
    let pathD = `M 0,${svgH - (occupancyHistory[0] / 100) * 190} `;
    for (let i = 1; i < occupancyHistory.length; i++) {
        const xPrev = (i - 1) * step;
        const yPrev = svgH - (occupancyHistory[i - 1] / 100) * 190;
        const xCurr = i * step;
        const yCurr = svgH - (occupancyHistory[i] / 100) * 190;
        const xMid = (xPrev + xCurr) / 2;
        pathD += `Q ${xMid},${yPrev} ${xCurr},${yCurr} `;
    }

    const lastX = (occupancyHistory.length - 1) * step;
    const lastY = svgH - (occupancyHistory[occupancyHistory.length - 1] / 100) * 190;
    const areaD = pathD + `L ${lastX},${svgH} L 0,${svgH} Z`;

    const linePath = document.getElementById('wave-line-path');
    const areaPath = document.getElementById('wave-area-path');
    const endMarker = document.getElementById('wave-end-marker');

    if (linePath) linePath.setAttribute('d', pathD.trim());
    if (areaPath) areaPath.setAttribute('d', areaD.trim());
    if (endMarker) {
        endMarker.setAttribute('cx', lastX);
        endMarker.setAttribute('cy', lastY);
    }
}

// Cycle focus feed (Feed 1 -> Feed 2 -> Feed 3)
function cycleFocusFeed() {
    const nextFeed = (selectedFocusFeed % 3) + 1;
    setActiveFocusFeed(nextFeed);
    showNotification(`Switched focus to Feed 0${nextFeed} (${CORRIDOR_METADATA[nextFeed]?.title || 'Corridor'})`, 'info');
}

// Switch Navigation Tab (Mission Control / Vision Engine / Analytics / Governance)
function switchNavTab(tabName, event) {
    if (event) event.preventDefault();
    document.querySelectorAll('.sidebar-menu .nav-item').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`nav-${tabName}`);
    if (target) target.classList.add('active');

    // Toggle View Panels
    document.querySelectorAll('.tab-view-content').forEach(view => {
        view.style.display = 'none';
        view.classList.remove('active');
    });
    const activeView = document.getElementById(`view-${tabName}`);
    if (activeView) {
        activeView.style.display = 'block';
        activeView.classList.add('active');
    }

    if (tabName === 'analytics') {
        refreshSystemAnalytics();
    } else if (tabName === 'governance') {
        loadAuditLogs();
    }
}

// Refresh System Analytics (Pandas Engine Integration)
async function refreshSystemAnalytics() {
    try {
        const res = await fetch('/api/analytics/system');
        if (!res.ok) return;
        const data = await res.json();
        const a = data.analytics || {};

        const totVol = document.getElementById('ana-tot-vol');
        const avgSpd = document.getElementById('ana-avg-spd');
        const congScore = document.getElementById('ana-cong-score');
        const peakTime = document.getElementById('ana-peak-time');

        if (totVol) totVol.textContent = a.total_volume || 0;
        if (avgSpd) avgSpd.textContent = `${a.avg_speed_system || 38} mph`;
        if (congScore) congScore.textContent = `${(a.congestion_score || 0).toFixed(1)}%`;
        if (peakTime) peakTime.textContent = a.peak_period || '08:30 - 09:15 AM';

        // Distribution Bars
        const dist = a.distribution || {};
        const setBar = (id, pctId, val) => {
            const b = document.getElementById(id);
            const p = document.getElementById(pctId);
            if (b) b.style.width = `${Math.min(100, Math.max(2, val))}%`;
            if (p) p.textContent = `${val.toFixed(0)}%`;
        };
        setBar('bar-cars', 'pct-cars', dist.cars || 65);
        setBar('bar-bikes', 'pct-bikes', dist.motorcycles || 15);
        setBar('bar-buses', 'pct-buses', dist.buses || 10);
        setBar('bar-trucks', 'pct-trucks', dist.trucks || 6);
        setBar('bar-peds', 'pct-peds', dist.pedestrians || 4);
    } catch (e) {
        console.error("Error refreshing system analytics:", e);
    }
}

// Submit Custom Duration (Modify Timing in Governance View)
async function submitCustomDuration() {
    const govSlider = document.getElementById('gov-duration-slider');
    const customTime = govSlider ? parseInt(govSlider.value) : 25;
    const target = currentDecision ? (currentDecision.target_road || 1) : 1;
    await submitOperatorAction('CUSTOMIZE', {
        custom_timings: { [target]: customTime }
    });
}

// Initialize Simulation
async function initializeSimulation() {
    try {
        const res = await fetch('/api/system/reset', { method: 'POST' });
        const data = await res.json();
        showNotification('Simulation initialized with full AI telemetry.', 'success');
        refreshVideoStreams();
        loadAuditLogs();
    } catch (e) {
        showNotification('Simulation ready.', 'success');
    }
}

// Load Audit Decision Logs (Updates Mission Control + Governance Table)
async function loadAuditLogs() {
    try {
        const res = await fetch('/api/decisions/history');
        if (!res.ok) return;
        const data = await res.json();
        const listEl = document.getElementById('audit-log-list');
        const countTag = document.getElementById('log-count-tag');
        const govTableBody = document.getElementById('gov-audit-table-body');

        const logs = data.history || data.logs || [];
        if (logs.length > 0) {
            if (countTag) countTag.textContent = `${logs.length} entries`;
            if (listEl) {
                listEl.innerHTML = logs.slice(0, 8).map(l => {
                    const timeStr = l.timestamp ? (l.timestamp.includes(' ') ? l.timestamp.split(' ')[1] : (l.timestamp.split('T')[1] || l.timestamp)) : 'RECENT';
                    const status = l.status || 'APPROVED';
                    const statusColor = status === 'APPROVED' ? 'color: #34d399;' : (status === 'REJECTED' ? 'color: #f43f5e;' : 'color: #fbbf24;');
                    const isEmerg = l.emergency_flag === 1;
                    
                    return `
                    <div class="log-item" style="padding: 8px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; margin-bottom: 6px; border: 1px solid rgba(255,255,255,0.06);">
                        <div class="log-item-header" style="display: flex; justify-content: space-between; font-size: 0.72rem; margin-bottom: 3px;">
                            <span class="font-mono text-dim">${timeStr.substring(0, 8)}</span>
                            <span class="font-mono" style="${statusColor} font-weight: 700;">${isEmerg ? '🚨 EMERGENCY' : status}</span>
                        </div>
                        <div class="log-item-action" style="font-size: 0.8rem; color: #f8fafc; line-height: 1.3;">
                            ${l.reasoning ? (l.reasoning.length > 70 ? l.reasoning.substring(0, 70) + '...' : l.reasoning) : 'Signal Schedule Phase Applied'}
                        </div>
                    </div>
                    `;
                }).join('');
            }

            if (govTableBody) {
                govTableBody.innerHTML = logs.slice(0, 15).map(l => {
                    const timeStr = l.timestamp ? (l.timestamp.includes(' ') ? l.timestamp.split(' ')[1] : (l.timestamp.split('T')[1] || l.timestamp)) : 'RECENT';
                    const status = l.status || 'APPROVED';
                    const statusColor = status === 'APPROVED' ? 'text-emerald font-bold' : (status === 'REJECTED' ? 'text-coral' : 'text-amber');
                    return `
                    <tr>
                        <td>${timeStr.substring(0, 8)}</td>
                        <td>Corridor Active</td>
                        <td>${l.recommended_timings || 'Standard 45s'}</td>
                        <td>${l.operator_action || status}</td>
                        <td class="${statusColor}">${status}</td>
                    </tr>
                    `;
                }).join('');
            }
        } else {
            if (countTag) countTag.textContent = '0 entries';
            if (listEl) listEl.innerHTML = `<div class="empty-log-msg">No operator actions yet. Approved sequence plans are logged in real time.</div>`;
            if (govTableBody) govTableBody.innerHTML = `<tr><td colspan="5" class="text-dim text-center">No operator actions recorded yet.</td></tr>`;
        }
    } catch (e) {
        console.error("Error loading audit logs:", e);
    }
}

// Refresh all stream image elements
function refreshVideoStreams() {
    const t = Date.now();
    const focusImg = document.getElementById('focus-stream-img');
    if (focusImg) focusImg.src = `/api/stream/${selectedFocusFeed}?t=${t}`;

    for (let sid = 1; sid <= 3; sid++) {
        const img = document.getElementById(`stream-img-${sid}`);
        if (img) img.src = `/api/stream/${sid}?t=${t}`;
    }
}

// Toast Notifications
function showNotification(msg, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast-msg toast-${type}`;
    toast.textContent = msg;
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: ${type === 'success' ? '#10b981' : (type === 'error' ? '#f43f5e' : '#1e293b')};
        color: ${type === 'success' ? '#050811' : '#ffffff'};
        padding: 10px 18px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        z-index: 99999;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        transition: opacity 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Modal tab controls
function initFeedConfigModal() {
    const feedModal = document.getElementById('feed-config-modal');
    const btnOpenFeedModal = document.getElementById('btn-open-feed-config');
    const btnCloseFeedModal = document.getElementById('btn-close-feed-config');

    if (btnOpenFeedModal && feedModal) {
        btnOpenFeedModal.addEventListener('click', () => {
            switchFeedTab(1);
            feedModal.style.display = 'flex';
        });
    }
    if (btnCloseFeedModal && feedModal) {
        btnCloseFeedModal.addEventListener('click', closeFeedModal);
    }
    if (feedModal) {
        feedModal.addEventListener('click', (e) => {
            if (e.target === feedModal) closeFeedModal();
        });
    }
}

function openFeedModalFor(feedId) {
    activeModalFeed = feedId;
    switchFeedTab(feedId);
    const modal = document.getElementById('feed-config-modal');
    if (modal) modal.style.display = 'flex';
}

function closeFeedModal() {
    const modal = document.getElementById('feed-config-modal');
    if (modal) modal.style.display = 'none';
}

function switchFeedTab(feedId) {
    activeModalFeed = feedId;
    [1, 2, 3].forEach(fid => {
        const tab = document.getElementById(`tab-feed-${fid}`);
        const sec = document.getElementById(`feed-section-${fid}`);
        if (tab) {
            if (fid === feedId) tab.classList.add('active');
            else tab.classList.remove('active');
        }
        if (sec) {
            sec.style.display = (fid === feedId) ? 'block' : 'none';
        }
    });
    updateFeedSubPanel(feedId);
}

function selectSourceCard(feedId, sourceType) {
    const radio = document.querySelector(`input[name="source_type_${feedId}"][value="${sourceType}"]`);
    if (radio) radio.checked = true;
    updateFeedSubPanel(feedId);
}

function updateFeedSubPanel(feedId) {
    const selectedRadio = document.querySelector(`input[name="source_type_${feedId}"]:checked`);
    if (!selectedRadio) return;
    const val = selectedRadio.value;

    ['YOUTUBE', 'FILE', 'DEMO', 'DISABLED'].forEach(type => {
        const card = document.getElementById(`card-opt-${feedId}-${type.toLowerCase()}`);
        if (card) {
            if (type === val) card.classList.add('active');
            else card.classList.remove('active');
        }
    });

    const subPanels = {
        'YOUTUBE': document.getElementById(`subpanel-yt-${feedId}`),
        'FILE': document.getElementById(`subpanel-file-${feedId}`),
        'DEMO': document.getElementById(`subpanel-demo-${feedId}`),
        'DISABLED': document.getElementById(`subpanel-disabled-${feedId}`)
    };

    Object.keys(subPanels).forEach(k => {
        if (subPanels[k]) {
            subPanels[k].style.display = (k === val) ? 'block' : 'none';
        }
    });
}

async function validateAndTestYt(feedId) {
    const inp = document.getElementById(`yt-url-${feedId}`);
    const statusEl = document.getElementById(`yt-status-${feedId}`);
    if (!inp || !statusEl) return;
    const url = inp.value.trim();
    if (!url) return;

    statusEl.style.display = 'block';
    statusEl.style.color = '#f59e0b';
    statusEl.textContent = 'Validating stream...';

    try {
        const res = await fetch('/api/youtube/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            statusEl.style.color = '#34d399';
            statusEl.textContent = `✓ Verified: "${data.title || 'Live Stream'}"`;
        } else {
            statusEl.style.color = '#f87171';
            statusEl.textContent = `✕ ${data.message || 'Invalid stream'}`;
        }
    } catch (e) {
        statusEl.style.color = '#f87171';
        statusEl.textContent = '✕ Network error';
    }
}

async function saveFeedConfig(feedId) {
    const selectedRadio = document.querySelector(`input[name="source_type_${feedId}"]:checked`);
    if (!selectedRadio) return;
    const sourceType = selectedRadio.value;

    const formData = new FormData();
    formData.append('feed_id', feedId);
    formData.append('source_type', sourceType);

    if (sourceType === 'YOUTUBE') {
        const ytInput = document.getElementById(`yt-url-${feedId}`);
        const ytUrl = (ytInput ? ytInput.value : '').trim();
        if (!ytUrl) {
            showNotification(`Please enter a YouTube link for Feed 0${feedId}`, 'warning');
            return;
        }
        formData.append('youtube_url', ytUrl);
    }

    try {
        const res = await fetch('/api/feed/configure', { method: 'POST', body: formData });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            showNotification(`Feed 0${feedId} configured as ${sourceType}!`, 'success');
            closeFeedModal();
            refreshVideoStreams();
        } else {
            showNotification(data.message || 'Error', 'error');
        }
    } catch (e) {
        showNotification('Network error', 'error');
    }
}

// Window global exports
window.setActiveFocusFeed = setActiveFocusFeed;
window.switchCardSourceMode = switchCardSourceMode;
window.applyCardYoutube = applyCardYoutube;
window.fillCardPreset = fillCardPreset;
window.handleDirectFeedUpload = handleDirectFeedUpload;
window.setFeedSource = setFeedSource;
window.updateDurationReadout = updateDurationReadout;
window.toggleReasoningAccordion = toggleReasoningAccordion;
window.openFeedModalFor = openFeedModalFor;
window.closeFeedModal = closeFeedModal;
window.switchFeedTab = switchFeedTab;
window.selectSourceCard = selectSourceCard;
window.updateFeedSubPanel = updateFeedSubPanel;
window.validateAndTestYt = validateAndTestYt;
window.saveFeedConfig = saveFeedConfig;
