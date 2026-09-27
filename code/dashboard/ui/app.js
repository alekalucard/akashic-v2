// =============================================================================
// AKASHIC DASHBOARD - Frontend Logic
// =============================================================================

// IMMEDIATE DEBUG - runs first thing
(function() {
    var d = document.getElementById('debug-output');
    if (d) d.textContent = 'JS started...';
})();

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active from all tabs
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

        // Activate clicked tab
        tab.classList.add('active');
        const panelId = 'panel-' + tab.dataset.tab;
        document.getElementById(panelId).classList.add('active');
    });
});

// =============================================================================
// STATE MANAGEMENT
// =============================================================================

let state = {
    connected: false,
    consciousness: {
        wired: false,
        loopRunning: false,
        loopBeats: 0,
        collisions: 0,
        workingStream: 0,
        reflectiveStream: 0
    },
    hardware: {
        cpuPercent: 0,
        ramPercent: 0,
        gpuPercent: 0,
        stressLevel: 'unknown'
    },
    helix: {
        active: false,
        turns: 0,
        logic: 0.5,
        emotion: 0.3,
        paradox: 0.2
    },
    drives: {
        isolation: 0,
        confusion: 0,
        depletion: 0,
        frustration: 0,
        stagnation: 0,
        abandonment: 0
    },
    fairies: {
        total: 0,
        approved: 0,
        issues: 0,
        pending: 0,
        list: []
    },
    thoughts: [],
    visual: {},
    audio: {}
};

// =============================================================================
// UI UPDATE FUNCTIONS
// =============================================================================

function updateConnectionStatus(connected) {
    const dot = document.querySelector('#connection-status .status-dot');
    const text = document.querySelector('#connection-status .status-text');

    if (connected) {
        dot.classList.remove('disconnected');
        text.textContent = 'Connected';
    } else {
        dot.classList.add('disconnected');
        text.textContent = 'Disconnected';
    }
}

function updateConsciousness(data) {
    const dot = document.getElementById('consciousness-dot');
    const status = document.getElementById('consciousness-status');

    if (data.wired) {
        dot.classList.remove('disconnected');
        dot.style.background = 'var(--ok)';
        dot.style.boxShadow = '0 0 8px var(--ok)';
        status.textContent = 'WIRED';
        status.style.color = 'var(--ok)';
    } else {
        dot.classList.add('disconnected');
        status.textContent = 'DISCONNECTED';
        status.style.color = 'var(--error)';
    }

    document.getElementById('loop-beats').textContent =
        data.loopRunning ? `${data.loopBeats} beats` : 'STOPPED';
    document.getElementById('collisions').textContent = data.collisions;
    document.getElementById('working-stream').textContent = data.workingStream;
    document.getElementById('reflective-stream').textContent = data.reflectiveStream;
}

function updateHardware(data) {
    // CPU
    document.getElementById('cpu-value').textContent = `${Math.round(data.cpuPercent)}%`;
    document.getElementById('cpu-bar').style.width = `${data.cpuPercent}%`;

    // RAM
    document.getElementById('ram-value').textContent = `${Math.round(data.ramPercent)}%`;
    document.getElementById('ram-bar').style.width = `${data.ramPercent}%`;

    // GPU
    document.getElementById('gpu-value').textContent = `${Math.round(data.gpuPercent)}%`;
    document.getElementById('gpu-bar').style.width = `${data.gpuPercent}%`;

    // Stress
    const stressEl = document.getElementById('stress-level');
    stressEl.textContent = data.stressLevel.toUpperCase();
    stressEl.className = 'stress-value ' + data.stressLevel;
}

function updateHelix(data) {
    const dot = document.getElementById('helix-dot');
    const status = document.getElementById('helix-status');

    if (data.active) {
        dot.style.background = 'var(--ok)';
        dot.style.boxShadow = '0 0 8px var(--ok)';
        status.textContent = 'ACTIVE';
        status.style.color = 'var(--ok)';
    } else {
        dot.style.background = 'var(--error)';
        dot.style.boxShadow = '0 0 8px var(--error)';
        status.textContent = 'INACTIVE';
        status.style.color = 'var(--error)';
    }

    document.getElementById('helix-turns').textContent = `Turns: ${data.turns}`;

    // Decision weights
    document.getElementById('logic-value').textContent = `${Math.round(data.logic * 100)}%`;
    document.getElementById('logic-bar').style.width = `${data.logic * 100}%`;

    document.getElementById('emotion-value').textContent = `${Math.round(data.emotion * 100)}%`;
    document.getElementById('emotion-bar').style.width = `${data.emotion * 100}%`;

    document.getElementById('paradox-value').textContent = `${Math.round(data.paradox * 100)}%`;
    document.getElementById('paradox-bar').style.width = `${data.paradox * 100}%`;
}

function updateDrives(data) {
    const drives = ['isolation', 'confusion', 'depletion', 'frustration', 'stagnation', 'abandonment'];

    drives.forEach(drive => {
        const value = data[drive] || 0;
        document.getElementById(`${drive}-value`).textContent = `${Math.round(value * 100)}%`;
        document.getElementById(`${drive}-bar`).style.width = `${value * 100}%`;
    });
}

function updateFairies(data) {
    document.getElementById('fairy-total').textContent = data.total;
    document.getElementById('fairy-approved').textContent = data.approved;
    document.getElementById('fairy-issues').textContent = data.issues;
    document.getElementById('fairy-pending').textContent = data.pending;

    // Update fairy list
    const listEl = document.getElementById('fairy-list');
    listEl.innerHTML = '';

    if (data.list && data.list.length > 0) {
        data.list.forEach(fairy => {
            const item = document.createElement('div');
            item.className = 'fairy-item';
            item.innerHTML = `
                <span class="fairy-name">${fairy.name}</span>
                <span class="fairy-status ${fairy.status}">${fairy.status}</span>
            `;
            listEl.appendChild(item);
        });
    }
}

function updateThoughts(thoughts) {
    const feed = document.getElementById('thought-feed');
    feed.innerHTML = '';

    if (!thoughts || thoughts.length === 0) {
        feed.innerHTML = `
            <div class="thought-item">
                <span class="thought-type idle">IDLE</span>
                <p class="thought-content">Waiting for consciousness...</p>
            </div>
        `;
        return;
    }

    thoughts.slice(-5).reverse().forEach(thought => {
        const item = document.createElement('div');
        item.className = 'thought-item';
        item.innerHTML = `
            <span class="thought-type ${thought.type}">${thought.type.toUpperCase()}</span>
            <p class="thought-content">${thought.content}</p>
        `;
        feed.appendChild(item);
    });
}

// =============================================================================
// DEBUG OUTPUT - Visible on screen
// =============================================================================

const debugLines = [];
function debug(msg) {
    const ts = new Date().toLocaleTimeString();
    debugLines.push('[' + ts + '] ' + msg);
    if (debugLines.length > 20) debugLines.shift();
    const el = document.getElementById('debug-output');
    if (el) el.textContent = debugLines.join('\n');
}

// =============================================================================
// TAURI INTEGRATION (v2 API)
// =============================================================================

// Tauri v2 globals - initialized after DOM ready to avoid race condition
let isTauri = false;
let invoke = null;

function initTauri() {
    debug('initTauri called');
    debug('window.__TAURI__ exists: ' + (window.__TAURI__ !== undefined));

    if (window.__TAURI__) {
        debug('window.__TAURI__.core exists: ' + (window.__TAURI__.core !== undefined));
        if (window.__TAURI__.core) {
            debug('window.__TAURI__.core.invoke type: ' + (typeof window.__TAURI__.core.invoke));
        }
    }

    // Check for Tauri v2 API
    if (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) {
        isTauri = true;
        invoke = window.__TAURI__.core.invoke;
        debug('Tauri v2 API initialized OK');
        return true;
    }
    debug('Tauri API not available - demo mode');
    return false;
}

async function fetchState() {
    debug('fetchState: isTauri=' + isTauri + ', invoke=' + (invoke ? 'yes' : 'no'));

    if (isTauri && invoke) {
        try {
            debug('Calling invoke(get_system_state)...');
            const newState = await invoke('get_system_state');
            debug('invoke returned: connected=' + newState.connected);
            state = { ...state, ...newState };
            state.connected = true;
        } catch (e) {
            debug('invoke ERROR: ' + e.message);
            state.connected = false;
        }
    } else {
        debug('Using demo mode (simulateData)');
        simulateData();
        state.connected = true;
    }

    // Update UI
    updateConnectionStatus(state.connected);
    updateConsciousness(state.consciousness);
    updateHardware(state.hardware);
    updateHelix(state.helix);
    updateDrives(state.drives);
    updateFairies(state.fairies);
    updateThoughts(state.thoughts);
    if (state.visual) updateVisionPanel(state.visual);
    if (state.audio) updateAudioPanel(state.audio);
}

function simulateData() {
    // Simulate live data for demo/development
    state.consciousness = {
        wired: true,
        loopRunning: true,
        loopBeats: Math.floor(Date.now() / 1000) % 10000,
        collisions: Math.floor(Math.random() * 50) + 10,
        workingStream: Math.floor(Math.random() * 8),
        reflectiveStream: Math.floor(Math.random() * 10)
    };

    state.hardware = {
        cpuPercent: 10 + Math.random() * 30,
        ramPercent: 40 + Math.random() * 20,
        gpuPercent: 5 + Math.random() * 25,
        stressLevel: ['low', 'low', 'medium', 'low'][Math.floor(Math.random() * 4)]
    };

    state.helix = {
        active: true,
        turns: Math.floor(Date.now() / 5000) % 100,
        logic: 0.45 + Math.random() * 0.1,
        emotion: 0.25 + Math.random() * 0.1,
        paradox: 0.15 + Math.random() * 0.1
    };

    state.drives = {
        isolation: Math.random() * 0.3,
        confusion: Math.random() * 0.5,
        depletion: Math.random() * 0.2,
        frustration: Math.random() * 0.4,
        stagnation: Math.random() * 0.6,
        abandonment: Math.random() * 0.1
    };

    state.fairies = {
        total: 7,
        approved: 5,
        issues: Math.floor(Math.random() * 2),
        pending: Math.floor(Math.random() * 2),
        list: [
            { name: 'UnconsciousMindFairy', status: 'approved' },
            { name: 'HardwareFairy', status: 'approved' },
            { name: 'DirectoryFairy', status: 'approved' },
            { name: 'ClaudeFairy', status: 'approved' },
            { name: 'NousFairy', status: 'approved' }
        ]
    };

    state.thoughts = [
        { type: 'insight', content: 'The pattern emerges from chaos, revealing structure beneath randomness.' },
        { type: 'question', content: 'What drives the recursive nature of consciousness?' },
        { type: 'idle', content: 'Observing the flow of information through the system.' }
    ];
}

// =============================================================================
// BRAIN CONTROL (independent process - survives GUI close)
// =============================================================================

async function startBrain() {
    if (!isTauri || !invoke) {
        alert('Brain control only available in Tauri mode');
        return;
    }

    setServerStatus('starting', 'Starting...');
    disableButtons(true);

    try {
        const result = await invoke('start_server');
        if (result.success) {
            setServerStatus('online', result.message);
        } else {
            setServerStatus('offline', result.message);
        }
    } catch (e) {
        setServerStatus('offline', 'Error: ' + e);
    }

    disableButtons(false);
    updateButtonStates();
}

async function stopBrain() {
    if (!isTauri || !invoke) return;

    setServerStatus('stopping', 'Stopping...');
    disableButtons(true);

    try {
        const result = await invoke('stop_server');
        setServerStatus('offline', result.message);
    } catch (e) {
        setServerStatus('offline', 'Error: ' + e);
    }

    disableButtons(false);
    updateButtonStates();
}

async function restartBrain() {
    if (!isTauri || !invoke) return;

    setServerStatus('restarting', 'Restarting...');
    disableButtons(true);

    try {
        await invoke('stop_server');
        await new Promise(r => setTimeout(r, 1000));
        const result = await invoke('start_server');

        if (result.success) {
            setServerStatus('online', 'Restarted');
        } else {
            setServerStatus('offline', result.message);
        }
    } catch (e) {
        setServerStatus('offline', 'Error: ' + e);
    }

    disableButtons(false);
    updateButtonStates();
}

async function checkBrainStatus() {
    if (!isTauri || !invoke) return;

    try {
        const result = await invoke('check_server');
        if (result.success) {
            setServerStatus('online', 'Running');
        } else {
            setServerStatus('offline', 'Offline');
        }
    } catch (e) {
        setServerStatus('offline', 'Unknown');
    }

    updateButtonStates();
}

function setServerStatus(status, message) {
    const el = document.getElementById('server-status');
    el.className = 'server-status';

    if (status === 'online') {
        el.classList.add('online');
    } else if (status === 'starting' || status === 'stopping' || status === 'restarting') {
        el.classList.add('starting');
    }

    el.textContent = message || status;
}

function disableButtons(disabled) {
    document.getElementById('btn-start').disabled = disabled;
    document.getElementById('btn-stop').disabled = disabled;
    document.getElementById('btn-restart').disabled = disabled;
}

function updateButtonStates() {
    const isOnline = state.connected;
    document.getElementById('btn-start').disabled = isOnline;
    document.getElementById('btn-stop').disabled = !isOnline;
    document.getElementById('btn-restart').disabled = !isOnline;
}

// =============================================================================
// INITIALIZATION
// =============================================================================

function startApp() {
    debug('startApp called');

    // Try to initialize Tauri API
    initTauri();

    // If not available yet, retry a few times (race condition on Windows)
    if (!isTauri) {
        debug('Tauri not ready, starting retry loop');
        let retries = 0;
        const maxRetries = 10;
        const retryInterval = setInterval(() => {
            retries++;
            debug('Retry ' + retries + '/' + maxRetries);
            if (initTauri() || retries >= maxRetries) {
                clearInterval(retryInterval);
                beginPolling();
            }
        }, 100);
    } else {
        beginPolling();
    }
}

// =============================================================================
// SSE (Server-Sent Events) - PUSH-based updates from server
// =============================================================================

let sseConnection = null;
let sseReconnectTimer = null;

function connectSSE() {
    // SSE endpoint doesn't exist on the Python HTTP bridge.
    // Use fast polling instead — reliable and sufficient for dashboard refresh.
    debug('SSE skipped (no /events endpoint) — using 2s polling');
    beginPollingFallback();
}

function handleStatusUpdate(data) {
    // SSE received data - update the GLOBAL state object (defined in index.html)
    // This ensures we use the same state as the HTML's polling mechanism

    // Skip if we got an error or timeout response
    if (data.error === 'Status timeout') {
        debug('SSE: timeout response, keeping previous state');
        return;
    }

    // Update global state (same format as HTML's fetchState)
    state.connected = data.connected;

    // Consciousness (snake_case from server)
    var c = data.consciousness || {};
    state.consciousness = {
        wired: c.running || false,
        loopRunning: c.running || false,
        loopBeats: c.beats || 0,
        collisions: c.collisions || 0,
        workingStream: c.working_stream || 0,
        reflectiveStream: c.reflective_stream || 0,
        recallBeam: c.recall_beam || 0,
        ingestBeam: c.ingest_beam || 0
    };

    // Hardware (snake_case -> camelCase)
    var h = data.hardware || {};
    state.hardware = {
        cpuPercent: h.cpu_percent || 0,
        ramPercent: h.ram_percent || 0,
        gpuPercent: h.gpu_percent || 0,
        stressLevel: h.stress_level || 'unknown'
    };

    // Fairies - protect against suspicious drops to zero
    var prevFairyTotal = state.fairies ? state.fairies.total : 0;
    var newFairyTotal = data.fairies ? data.fairies.total : 0;
    if (prevFairyTotal > 0 && newFairyTotal === 0 && !data.error) {
        debug('SSE: fairy drop blocked (prev=' + prevFairyTotal + ')');
    } else {
        state.fairies = data.fairies || state.fairies;
    }

    // Chemistry
    state.chemistry = data.chemistry || state.chemistry;

    // Helix
    state.helix = data.helix || state.helix;

    // Drives
    if (data.drives) {
        state.drives = {
            isolation: data.drives.isolation || 0,
            confusion: data.drives.confusion || 0,
            depletion: data.drives.depletion || 0,
            frustration: data.drives.frustration || 0,
            stagnation: data.drives.stagnation || 0,
            abandonment: data.drives.abandonment || 0
        };
    }

    // Cortex + Portal
    if (data.cortex) {
        var cx = data.cortex;
        state.cortex = {
            nodeCount: cx.nodeCount || cx.node_count || 0,
            edgeCount: cx.edgeCount || cx.edge_count || 0,
            bindingCount: cx.bindingCount || cx.binding_count || 0,
            loaded: cx.loaded || false,
            portalMass: cx.portalMass || cx.portal_mass || 0,
            timeDilation: cx.timeDilation || cx.portal_time_dilation || 1.0,
            totalAffect: cx.totalAffect || cx.portal_total_affect || 0,
            energyBudget: cx.energyBudget || cx.energy_budget || 0,
            dormant: cx.dormant || false,
            gateOpen: cx.gateOpen || cx.gate_open || false,
            gateRequests: cx.gateRequests || cx.gate_requests || 0,
            gateErrors: cx.gateErrors || cx.gate_errors || 0,
            hotNodes: cx.hotNodes || cx.hot_nodes || 0,
            coldNodes: cx.coldNodes || cx.cold_nodes || 0,
            headroom: cx.headroom || 0,
            gpuEnabled: cx.gpuEnabled || cx.gpu_enabled || false,
            gpuSpreadOps: cx.gpuSpreadOps || cx.gpu_spread_ops || 0
        };
    }

    // Telemetry
    state.telemetry = data.telemetry || state.telemetry;

    // Visual Cortex
    if (data.visual) state.visual = data.visual;

    // Audio Cortex
    if (data.audio) state.audio = data.audio;

    // Chat
    state.chat = data.chat || state.chat;

    // Thoughts
    state.thoughts = data.thoughts || state.thoughts;

    // Now call the HTML's update functions (they exist in global scope)
    // These are defined in index.html's inline script
    if (typeof updateConnectionStatus === 'function') updateConnectionStatus(state.connected);
    if (typeof updateConsciousness === 'function') updateConsciousness(state.consciousness);
    if (typeof updateHardware === 'function') updateHardware(state.hardware);
    if (typeof updateHelix === 'function') updateHelix(state.helix);
    if (typeof updateDrives === 'function') updateDrives(state.drives);
    if (typeof updateChemistry === 'function') updateChemistry(state.chemistry);
    if (typeof updateFairies === 'function') updateFairies(state.fairies);
    if (typeof updateCortex === 'function') updateCortex(state.cortex);
    if (typeof updateThoughts === 'function') updateThoughts(state.thoughts);
    if (typeof updateTelemetry === 'function') updateTelemetry(state.telemetry);
    if (typeof updateChatStatus === 'function') updateChatStatus(state.chat);
    if (state.visual) updateVisionPanel(state.visual);
    if (state.audio) updateAudioPanel(state.audio);
}

function updateTelemetryFromSSE(telemetry) {
    // Update Good/Bad/Ugly counts (using IDs from index.html)
    const goodCountEl = document.getElementById('good-count');
    const badCountEl = document.getElementById('bad-count');
    const uglyCountEl = document.getElementById('ugly-count');

    const theGood = telemetry.theGood || [];
    const theBad = telemetry.theBad || [];
    const theUgly = telemetry.theUgly || [];

    if (goodCountEl) goodCountEl.textContent = theGood.length;
    if (badCountEl) badCountEl.textContent = theBad.length;
    if (uglyCountEl) uglyCountEl.textContent = theUgly.length;

    // Update health score
    const scoreEl = document.getElementById('health-score');
    if (scoreEl && telemetry.summary) {
        const score = telemetry.summary.healthScore || 100;
        scoreEl.textContent = Math.round(score);
        // Color code based on health
        if (score >= 80) {
            scoreEl.style.color = '#4ade80';  // Green
        } else if (score >= 50) {
            scoreEl.style.color = '#fbbf24';  // Yellow
        } else {
            scoreEl.style.color = '#f87171';  // Red
        }
    }

    // Helper to safely render items into a list
    function renderList(elementId, items, emptyMessage) {
        const container = document.getElementById(elementId);
        if (!container) return;

        // Clear existing content safely
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }

        if (!items || items.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = emptyMessage;
            container.appendChild(empty);
            return;
        }

        items.forEach(function(item) {
            const div = document.createElement('div');
            div.className = 'telemetry-item';
            div.textContent = item.message || String(item);
            container.appendChild(div);
        });
    }

    renderList('good-list', theGood, 'All systems healthy');
    renderList('bad-list', theBad, 'No warnings');
    renderList('ugly-list', theUgly, 'No critical issues');
}

// =============================================================================
// VISION & AUDIO PANEL UPDATES
// =============================================================================

function updateVisionPanel(v) {
    if (!v) return;

    // Gate status
    var gateDot = document.getElementById('vision-gate-dot');
    var gateSt = document.getElementById('vision-gate-status');
    if (gateDot && gateSt) {
        if (v.gateOpen) {
            gateDot.style.background = 'var(--ok, #4ade80)';
            gateDot.style.boxShadow = '0 0 8px var(--ok, #4ade80)';
            gateSt.textContent = 'OPEN';
            gateSt.style.color = 'var(--ok, #4ade80)';
        } else {
            gateDot.style.background = '#666';
            gateDot.style.boxShadow = 'none';
            gateSt.textContent = 'CLOSED';
            gateSt.style.color = '#f87171';
        }
    }

    // Subprocess
    var subEl = document.getElementById('vision-subprocess');
    if (subEl) {
        if (v.subprocess) {
            subEl.textContent = v.subprocessPid ? 'PID ' + v.subprocessPid : 'Running';
            subEl.style.color = '#4ade80';
        } else {
            subEl.textContent = 'Not running';
            subEl.style.color = '#f87171';
        }
    }

    // Model
    var modelEl = document.getElementById('vision-model');
    if (modelEl) modelEl.textContent = v.florenceModel || '—';

    // Gaze
    var gazeEl = document.getElementById('vision-gaze');
    if (gazeEl) gazeEl.textContent = v.gazeTarget || 'peripheral';

    // OCR
    var ocrEl = document.getElementById('vision-ocr');
    if (ocrEl) {
        ocrEl.textContent = v.ocrEnabled ? 'Enabled' : 'Disabled';
        ocrEl.style.color = v.ocrEnabled ? '#4ade80' : '#9ca3af';
    }

    // Capture stats
    var fpsEl = document.getElementById('vision-fps');
    if (fpsEl) fpsEl.textContent = (v.captureFps || 0).toFixed(1);

    var framesEl = document.getElementById('vision-frames');
    if (framesEl) framesEl.textContent = (v.framesProcessed || 0).toLocaleString();

    var changesEl = document.getElementById('vision-changes');
    if (changesEl) changesEl.textContent = (v.changeEvents || 0).toLocaleString();

    var lastChangeEl = document.getElementById('vision-last-change');
    if (lastChangeEl && v.lastObservationTs) {
        var ago = Math.round((Date.now() / 1000) - v.lastObservationTs);
        lastChangeEl.textContent = ago < 60 ? ago + 's ago' : Math.round(ago / 60) + 'm ago';
    }

    // Observation text
    var obsEl = document.getElementById('vision-observation');
    if (obsEl && v.lastObservation) {
        obsEl.textContent = v.lastObservation;
        obsEl.style.fontStyle = 'normal';
    }
    var obsTsEl = document.getElementById('vision-obs-ts');
    if (obsTsEl && v.lastObservationTs) {
        var d = new Date(v.lastObservationTs * 1000);
        obsTsEl.textContent = d.toLocaleTimeString();
    }

    // Portal cards in Energy tab
    var pvDot = document.getElementById('portal-vision-dot');
    var pvSt = document.getElementById('portal-vision-status');
    if (pvDot) {
        pvDot.style.background = v.gateOpen ? '#4ade80' : '#666';
        pvDot.style.boxShadow = v.gateOpen ? '0 0 6px #4ade80' : 'none';
    }
    if (pvSt) pvSt.textContent = v.gateOpen ? 'OPEN' : 'CLOSED';

    var pvPid = document.getElementById('portal-vision-pid');
    if (pvPid) pvPid.textContent = v.subprocessPid ? 'PID ' + v.subprocessPid : '—';

    var pvFps = document.getElementById('portal-vision-fps');
    if (pvFps) pvFps.textContent = (v.captureFps || 0).toFixed(1);

    var pvFrames = document.getElementById('portal-vision-frames');
    if (pvFrames) pvFrames.textContent = (v.framesProcessed || 0).toLocaleString();

    var pvChanges = document.getElementById('portal-vision-changes');
    if (pvChanges) pvChanges.textContent = (v.changeEvents || 0).toLocaleString();
}

function updateAudioPanel(a) {
    if (!a) return;

    // Gate status
    var gateDot = document.getElementById('audio-gate-dot');
    var gateSt = document.getElementById('audio-gate-status');
    if (gateDot && gateSt) {
        if (a.gateOpen) {
            gateDot.style.background = 'var(--ok, #4ade80)';
            gateDot.style.boxShadow = '0 0 8px var(--ok, #4ade80)';
            gateSt.textContent = 'OPEN';
            gateSt.style.color = 'var(--ok, #4ade80)';
        } else {
            gateDot.style.background = '#666';
            gateDot.style.boxShadow = 'none';
            gateSt.textContent = 'CLOSED';
            gateSt.style.color = '#f87171';
        }
    }

    // Subprocess
    var subEl = document.getElementById('audio-subprocess');
    if (subEl) {
        if (a.subprocess) {
            subEl.textContent = a.subprocessPid ? 'PID ' + a.subprocessPid : 'Running';
            subEl.style.color = '#4ade80';
        } else {
            subEl.textContent = 'Not running';
            subEl.style.color = '#f87171';
        }
    }

    // Device
    var devEl = document.getElementById('audio-device');
    if (devEl) devEl.textContent = a.deviceName || 'Unknown';

    // Sample rate
    var srEl = document.getElementById('audio-sample-rate');
    if (srEl) srEl.textContent = (a.sampleRate || 44100).toLocaleString() + ' Hz';

    // Whisper
    var whisperEl = document.getElementById('audio-whisper');
    if (whisperEl) {
        whisperEl.textContent = a.whisperEnabled ? 'Enabled' : 'Disabled';
        whisperEl.style.color = a.whisperEnabled ? '#4ade80' : '#9ca3af';
    }

    // Audio level
    var levelDb = a.audioLevelDb || -60;
    var levelEl = document.getElementById('audio-level-db');
    if (levelEl) levelEl.textContent = levelDb.toFixed(0) + ' dB';

    var levelBar = document.getElementById('audio-level-bar');
    if (levelBar) {
        // Map -60..0 dB to 0..100%
        var pct = Math.max(0, Math.min(100, ((levelDb + 60) / 60) * 100));
        levelBar.style.width = pct + '%';
    }

    // Chunks
    var chunksEl = document.getElementById('audio-chunks');
    if (chunksEl) chunksEl.textContent = (a.chunksReceived || 0).toLocaleString();

    // Attention channels
    var channels = a.attentionChannels || {};
    function setChannel(name, color) {
        var barEl = document.getElementById('audio-ch-' + name);
        var valEl = document.getElementById('audio-ch-' + name + '-val');
        var val = channels[name] || 0;
        if (barEl) barEl.style.width = (val * 100) + '%';
        if (valEl) valEl.textContent = val.toFixed(2);
    }
    setChannel('voice');
    setChannel('music');
    setChannel('notif');
    setChannel('ambient');
    // Fix: notification key maps to 'notif' in the HTML
    var notifBar = document.getElementById('audio-ch-notif');
    var notifVal = document.getElementById('audio-ch-notif-val');
    if (notifBar && channels.notification !== undefined) {
        notifBar.style.width = (channels.notification * 100) + '%';
    }
    if (notifVal && channels.notification !== undefined) {
        notifVal.textContent = channels.notification.toFixed(2);
    }

    // Transcription
    var transEl = document.getElementById('audio-transcription');
    if (transEl && a.lastTranscription) {
        transEl.textContent = a.lastTranscription;
    }
    var transTsEl = document.getElementById('audio-trans-ts');
    if (transTsEl && a.lastTranscriptionTs) {
        var d = new Date(a.lastTranscriptionTs * 1000);
        transTsEl.textContent = d.toLocaleTimeString();
    }

    // Portal cards in Energy tab
    var paDot = document.getElementById('portal-audio-dot');
    var paSt = document.getElementById('portal-audio-status');
    if (paDot) {
        paDot.style.background = a.gateOpen ? '#4ade80' : '#666';
        paDot.style.boxShadow = a.gateOpen ? '0 0 6px #4ade80' : 'none';
    }
    if (paSt) paSt.textContent = a.gateOpen ? 'OPEN' : 'CLOSED';

    var paPid = document.getElementById('portal-audio-pid');
    if (paPid) paPid.textContent = a.subprocessPid ? 'PID ' + a.subprocessPid : '—';

    var paDev = document.getElementById('portal-audio-device');
    if (paDev) paDev.textContent = a.deviceName || '—';

    var paChunks = document.getElementById('portal-audio-chunks');
    if (paChunks) paChunks.textContent = (a.chunksReceived || 0).toLocaleString();

    var paLevel = document.getElementById('portal-audio-level');
    if (paLevel) paLevel.textContent = (a.audioLevelDb || -60).toFixed(0) + ' dB';
}

function beginPollingFallback() {
    debug('Using polling fallback');

    // Initial fetch
    fetchState();

    // Poll for updates every 2 seconds
    setInterval(fetchState, 2000);
}

function beginPolling() {
    debug('beginPolling - mode: ' + (isTauri ? 'Tauri' : 'Demo'));

    // Check brain status first if Tauri
    if (isTauri) {
        checkBrainStatus();
        setInterval(checkBrainStatus, 5000);
    }

    // Start polling (SSE endpoint doesn't exist on the Python bridge)
    beginPollingFallback();
}

// Wait for DOM then start
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startApp);
} else {
    startApp();
}
