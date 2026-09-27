//! Akashic Dashboard - Tauri Backend
//!
//! Viewer with controls to start/stop the independent Python server.
//! Server runs as separate process - survives GUI close.
//!
//! NEW: Nous autonomous operation via Claude Code CLI.

use serde::{Deserialize, Serialize};
use chrono;
use std::collections::HashMap;
use std::process::Command;
use std::time::Duration;
use std::io::Write;

// Debug log to file (terminal unreliable)
fn debug_log(msg: &str) {
    let log_path = r"F:\Sandbox\failure_factory\akashic_v2\state\rust_debug.log";
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
    {
        let timestamp = chrono::Local::now().format("%H:%M:%S%.3f");
        let _ = writeln!(file, "[{}] {}", timestamp, msg);
    }
}

#[cfg(windows)]
use std::os::windows::process::CommandExt;

// =============================================================================
// DATA STRUCTURES - What the frontend expects
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsciousnessState {
    pub wired: bool,
    #[serde(rename = "loopRunning")]
    pub loop_running: bool,
    #[serde(rename = "loopBeats")]
    pub loop_beats: u64,
    pub collisions: u32,
    #[serde(rename = "workingStream")]
    pub working_stream: u32,
    #[serde(rename = "reflectiveStream")]
    pub reflective_stream: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareState {
    #[serde(rename = "cpuPercent")]
    pub cpu_percent: f32,
    #[serde(rename = "ramPercent")]
    pub ram_percent: f32,
    #[serde(rename = "gpuPercent")]
    pub gpu_percent: f32,
    #[serde(rename = "stressLevel")]
    pub stress_level: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HelixState {
    pub active: bool,
    pub turns: u32,
    pub logic: f32,
    pub emotion: f32,
    pub paradox: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DrivesState {
    pub isolation: f32,
    pub confusion: f32,
    pub depletion: f32,
    pub frustration: f32,
    pub stagnation: f32,
    pub abandonment: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChemistryState {
    pub dopamine: f32,
    pub serotonin: f32,
    pub cortisol: f32,
    pub oxytocin: f32,
    pub norepinephrine: f32,
    pub adrenaline: f32,
    pub valence: f32,
    pub arousal: f32,
    pub mood: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FairyInfo {
    pub name: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FairiesState {
    pub total: u32,
    pub running: u32,
    pub sleeping: u32,
    pub list: Vec<FairyInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtInfo {
    #[serde(rename = "type")]
    pub thought_type: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CortexState {
    #[serde(rename = "nodeCount")]
    pub node_count: u32,
    #[serde(rename = "edgeCount")]
    pub edge_count: u32,
    #[serde(rename = "bindingCount")]
    pub binding_count: u32,
    pub loaded: bool,
    // Portal gravity metrics
    #[serde(rename = "portalMass")]
    pub portal_mass: f64,
    #[serde(rename = "timeDilation")]
    pub time_dilation: f64,
    #[serde(rename = "totalAffect")]
    pub total_affect: f64,
    #[serde(rename = "energyBudget")]
    pub energy_budget: f64,
    pub dormant: bool,
    // Portal gate health
    #[serde(rename = "gateOpen")]
    pub gate_open: bool,
    #[serde(rename = "gateRequests")]
    pub gate_requests: u32,
    #[serde(rename = "gateErrors")]
    pub gate_errors: u32,
    // Working set
    #[serde(rename = "hotNodes")]
    pub hot_nodes: u32,
    #[serde(rename = "coldNodes")]
    pub cold_nodes: u32,
    pub headroom: u32,
    // GPU
    #[serde(rename = "gpuEnabled")]
    pub gpu_enabled: bool,
    #[serde(rename = "gpuSpreadOps")]
    pub gpu_spread_ops: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatState {
    pub connected: bool,
    pub registered_fairies: u32,
    pub fairy_names: Vec<String>,
    pub unread_inbox: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemState {
    pub connected: bool,
    pub consciousness: ConsciousnessState,
    pub hardware: HardwareState,
    pub helix: HelixState,
    pub drives: DrivesState,
    pub chemistry: ChemistryState,
    pub fairies: FairiesState,
    pub cortex: CortexState,
    pub thoughts: Vec<ThoughtInfo>,
    pub chat: ChatState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandResult {
    pub success: bool,
    pub message: String,
}

/// Native heartbeat file structure - read directly from filesystem
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeartbeatFile {
    pub heart_rate: f64,
    pub beat_count: u64,
    pub running: bool,
    pub chemistry: HashMap<String, f64>,
    pub rust_engine: Option<bool>,
    pub rust_mood: Option<String>,
    pub rust_valence: Option<f64>,
    pub rust_arousal: Option<f64>,
}

// =============================================================================
// SERVER RESPONSE - What the HTTP server returns
// =============================================================================

#[derive(Debug, Deserialize)]
struct ServerConsciousness {
    running: Option<bool>,
    beats: Option<u64>,
    collisions: Option<u32>,
    recall_beam: Option<u32>,
    ingest_beam: Option<u32>,
    working_stream: Option<u32>,
    reflective_stream: Option<u32>,
}

#[derive(Debug, Deserialize)]
struct ServerHardware {
    cpu_percent: Option<f32>,
    ram_percent: Option<f32>,
    gpu_percent: Option<f32>,
    stress_level: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ServerFairyInfo {
    name: String,
    plane: Option<String>,
    status: String,
}

#[derive(Debug, Deserialize)]
struct ServerFairies {
    total: Option<u32>,
    running: Option<u32>,
    sleeping: Option<u32>,
    list: Option<Vec<ServerFairyInfo>>,
}

#[derive(Debug, Deserialize)]
struct ServerUmf {
    drives: Option<serde_json::Value>,
    helix: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
struct ServerMemoryFabric {
    device: Option<String>,
    is_gpu: Option<bool>,
    memory_mb: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct ServerCortex {
    node_count: Option<u32>,
    edge_count: Option<u32>,
    binding_count: Option<u32>,
    loaded: Option<bool>,
    // Portal gravity
    portal_mass: Option<f64>,
    portal_time_dilation: Option<f64>,
    portal_total_affect: Option<f64>,
    energy_budget: Option<f64>,
    dormant: Option<bool>,
    // Portal gate
    gate_open: Option<bool>,
    gate_requests: Option<u32>,
    gate_errors: Option<u32>,
    // Working set
    hot_nodes: Option<u32>,
    cold_nodes: Option<u32>,
    headroom: Option<u32>,
    // GPU
    gpu_enabled: Option<bool>,
    gpu_spread_ops: Option<u32>,
}

// Python sends chemistry as flat struct (not nested levels/mood)
#[derive(Debug, Deserialize)]
struct ServerChemistry {
    dopamine: Option<f64>,
    serotonin: Option<f64>,
    cortisol: Option<f64>,
    oxytocin: Option<f64>,
    norepinephrine: Option<f64>,
    adrenaline: Option<f64>,
    valence: Option<f64>,
    arousal: Option<f64>,
    mood: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ServerThought {
    #[serde(rename = "type")]
    thought_type: Option<String>,
    content: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ServerChat {
    connected: Option<bool>,
    registered_fairies: Option<u32>,
    fairy_names: Option<Vec<String>>,
    unread_inbox: Option<u32>,
}

// Top-level drives (Python sends at root level)
#[derive(Debug, Deserialize)]
struct ServerDrives {
    isolation: Option<f64>,
    confusion: Option<f64>,
    depletion: Option<f64>,
    frustration: Option<f64>,
    stagnation: Option<f64>,
    abandonment: Option<f64>,
}

// Top-level helix (Python sends at root level)
#[derive(Debug, Deserialize)]
struct ServerHelix {
    active: Option<bool>,
    turns: Option<u32>,
    logic: Option<f64>,
    emotion: Option<f64>,
    paradox: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct ServerStatus {
    connected: Option<bool>,  // Python sends this for Tauri
    booted: Option<bool>,
    uptime: Option<f64>,
    error: Option<String>,
    consciousness: Option<ServerConsciousness>,
    hardware: Option<ServerHardware>,
    fairies: Option<ServerFairies>,
    umf: Option<ServerUmf>,
    drives: Option<ServerDrives>,   // NEW: Top-level drives from Python
    helix: Option<ServerHelix>,     // NEW: Top-level helix from Python
    memory_fabric: Option<ServerMemoryFabric>,
    cortex: Option<ServerCortex>,
    chemistry: Option<ServerChemistry>,
    thoughts: Option<Vec<ServerThought>>,
    chat: Option<ServerChat>,
}

// =============================================================================
// CONFIG
// =============================================================================

const SERVER_URL: &str = "http://127.0.0.1:5757";
const PROJECT_ROOT: &str = r"F:\Sandbox\failure_factory\akashic_v2";

// =============================================================================
// HTTP CLIENT
// =============================================================================

/// Generate a unique trace ID matching Python's format (RUST-XXXXXX)
fn generate_trace_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("RUST-{:06X}", (nanos % 0xFFFFFF) as u32)
}

/// Async fetch - doesn't block the UI thread!
async fn fetch_status() -> Option<ServerStatus> {
    let trace_id = generate_trace_id();
    let url = format!("{}/status", SERVER_URL);

    // Log to FILE (terminal unreliable)
    debug_log(&format!("[{}] ========== FETCH START ==========", trace_id));
    debug_log(&format!("[{}] URL: {}", trace_id, url));

    let client = match reqwest::Client::builder()
        .timeout(Duration::from_millis(5000))  // Increased timeout for large responses
        .build()
    {
        Ok(c) => c,
        Err(e) => {
            log::error!("[{}] Failed to build HTTP client: {}", trace_id, e);
            log::info!("[{}] ========== FETCH END (client build error) ==========", trace_id);
            return None;
        }
    };

    log::info!("[{}] Sending HTTP GET request...", trace_id);
    let response = match client.get(&url).send().await {
        Ok(r) => r,
        Err(e) => {
            debug_log(&format!("[{}] !!! HTTP FAILED: {}", trace_id, e));
            return None;
        }
    };

    let http_status = response.status();
    debug_log(&format!("[{}] HTTP {}", trace_id, http_status.as_u16()));

    if http_status.is_success() {
        // Get response text first so we can log it if parsing fails
        let body = match response.text().await {
            Ok(text) => text,
            Err(e) => {
                log::error!("[{}] Failed to read response body: {}", trace_id, e);
                log::info!("[{}] ========== FETCH END (body read error) ==========", trace_id);
                return None;
            }
        };

        log::info!("[{}] Response body size: {} bytes", trace_id, body.len());

        // Log first 500 chars of body (always, not just on error)
        let preview = if body.len() > 500 { &body[..500] } else { &body };
        log::info!("[{}] Response body preview (first 500 chars):\n{}", trace_id, preview);

        match serde_json::from_str::<ServerStatus>(&body) {
            Ok(status) => {
                debug_log(&format!("[{}] SUCCESS connected={:?}", trace_id, status.connected));

                // Log fairy count if present
                if let Some(ref fairies) = status.fairies {
                    log::info!("[{}] Fairies: total={:?}, running={:?}, sleeping={:?}",
                        trace_id, fairies.total, fairies.running, fairies.sleeping);
                }

                // Log consciousness state if present
                if let Some(ref consciousness) = status.consciousness {
                    log::info!("[{}] Consciousness: running={:?}, beats={:?}",
                        trace_id, consciousness.running, consciousness.beats);
                }

                log::info!("[{}] ========== FETCH END (success) ==========", trace_id);
                Some(status)
            }
            Err(e) => {
                debug_log(&format!("[{}] PARSE FAILED: {}", trace_id, e));
                debug_log(&format!("[{}] Body: {}", trace_id, if body.len() > 500 { &body[..500] } else { &body }));
                None
            }
        }
    } else {
        log::warn!("[{}] Non-success HTTP status: {}", trace_id, http_status);
        log::info!("[{}] ========== FETCH END (http error) ==========", trace_id);
        None
    }
}

/// Quick health check - async to not block UI
async fn is_server_running() -> bool {
    let url = format!("{}/health", SERVER_URL);

    if let Ok(client) = reqwest::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
    {
        client.get(&url).send().await.is_ok()
    } else {
        false
    }
}

fn transform_status(server: ServerStatus) -> SystemState {
    // Transform server response to frontend format
    let consciousness = server.consciousness.unwrap_or(ServerConsciousness {
        running: Some(false),
        beats: Some(0),
        collisions: Some(0),
        recall_beam: Some(0),
        ingest_beam: Some(0),
        working_stream: Some(0),
        reflective_stream: Some(0),
    });

    let hardware = server.hardware.unwrap_or(ServerHardware {
        cpu_percent: Some(0.0),
        ram_percent: Some(0.0),
        gpu_percent: Some(0.0),
        stress_level: Some("unknown".to_string()),
    });

    let fairies = server.fairies.unwrap_or(ServerFairies {
        total: Some(0),
        running: Some(0),
        sleeping: Some(0),
        list: Some(vec![]),
    });

    // Extract drives from TOP-LEVEL (Python sends at root, not nested in umf)
    let drives = if let Some(d) = server.drives {
        DrivesState {
            isolation: d.isolation.unwrap_or(0.0) as f32,
            confusion: d.confusion.unwrap_or(0.0) as f32,
            depletion: d.depletion.unwrap_or(0.0) as f32,
            frustration: d.frustration.unwrap_or(0.0) as f32,
            stagnation: d.stagnation.unwrap_or(0.0) as f32,
            abandonment: d.abandonment.unwrap_or(0.0) as f32,
        }
    } else {
        DrivesState {
            isolation: 0.0,
            confusion: 0.0,
            depletion: 0.0,
            frustration: 0.0,
            stagnation: 0.0,
            abandonment: 0.0,
        }
    };

    // Extract connection state from TOP-LEVEL (prefer 'connected', fallback to 'booted')
    let is_connected = server.connected.unwrap_or_else(|| server.booted.unwrap_or(false));
    let helix = if let Some(h) = server.helix {
        HelixState {
            active: h.active.unwrap_or(is_connected),
            turns: h.turns.unwrap_or(0),
            logic: h.logic.unwrap_or(0.5) as f32,
            emotion: h.emotion.unwrap_or(0.3) as f32,
            paradox: h.paradox.unwrap_or(0.2) as f32,
        }
    } else {
        HelixState {
            active: is_connected,
            turns: 0,
            logic: 0.5,
            emotion: 0.3,
            paradox: 0.2,
        }
    };

    // Use server-reported GPU percent (Python computes from actual GPU stats)
    // Fall back to memory_fabric heuristic only if server doesn't provide it
    let gpu_percent = if let Some(gp) = hardware.gpu_percent {
        gp
    } else {
        let gpu_active = server.memory_fabric
            .as_ref()
            .and_then(|mf| mf.is_gpu)
            .unwrap_or(false);
        let gpu_memory_mb = server.memory_fabric
            .as_ref()
            .and_then(|mf| mf.memory_mb)
            .unwrap_or(0.0);
        if gpu_active && gpu_memory_mb > 0.0 {
            ((gpu_memory_mb / 8192.0) * 100.0).min(100.0) as f32
        } else {
            0.0
        }
    };

    // Build fairy list
    let fairy_list: Vec<FairyInfo> = fairies.list.unwrap_or_default()
        .into_iter()
        .map(|f| FairyInfo {
            name: f.name,
            status: f.status,
        })
        .collect();

    // Use server-reported stress level (Python computes with GPU awareness)
    // Fall back to heuristic only if server doesn't provide it
    let cpu = hardware.cpu_percent.unwrap_or(0.0);
    let ram = hardware.ram_percent.unwrap_or(0.0);
    let stress_level = hardware.stress_level.clone().unwrap_or_else(|| {
        if cpu > 80.0 || ram > 85.0 || gpu_percent > 90.0 {
            "high"
        } else if cpu > 50.0 || ram > 60.0 || gpu_percent > 60.0 {
            "medium"
        } else {
            "low"
        }.to_string()
    });

    SystemState {
        connected: is_connected,
        consciousness: ConsciousnessState {
            // wired = consciousness is actually running, not just "connected to server"
            wired: consciousness.running.unwrap_or(false),
            loop_running: consciousness.running.unwrap_or(false),
            loop_beats: consciousness.beats.unwrap_or(0),
            collisions: consciousness.collisions.unwrap_or(0),
            // Use actual stream sizes from server (added 2026-02-05)
            // Fall back to recall_beam/ingest_beam for backwards compat
            working_stream: consciousness.working_stream
                .or(consciousness.recall_beam)
                .unwrap_or(0),
            reflective_stream: consciousness.reflective_stream
                .or(consciousness.ingest_beam)
                .unwrap_or(0),
        },
        hardware: HardwareState {
            cpu_percent: cpu,
            ram_percent: ram,
            gpu_percent,
            stress_level,
        },
        helix,
        drives,
        chemistry: {
            // Python sends chemistry as flat struct (not nested levels/mood)
            let chem = server.chemistry.unwrap_or(ServerChemistry {
                dopamine: Some(0.5),
                serotonin: Some(0.5),
                cortisol: Some(0.3),
                oxytocin: Some(0.4),
                norepinephrine: Some(0.4),
                adrenaline: Some(0.1),
                valence: Some(0.0),
                arousal: Some(0.3),
                mood: Some("neutral".to_string()),
            });
            ChemistryState {
                dopamine: chem.dopamine.unwrap_or(0.5) as f32,
                serotonin: chem.serotonin.unwrap_or(0.5) as f32,
                cortisol: chem.cortisol.unwrap_or(0.3) as f32,
                oxytocin: chem.oxytocin.unwrap_or(0.4) as f32,
                norepinephrine: chem.norepinephrine.unwrap_or(0.4) as f32,
                adrenaline: chem.adrenaline.unwrap_or(0.1) as f32,
                valence: chem.valence.unwrap_or(0.0) as f32,
                arousal: chem.arousal.unwrap_or(0.3) as f32,
                mood: chem.mood.unwrap_or("neutral".to_string()),
            }
        },
        fairies: FairiesState {
            total: fairies.total.unwrap_or(0),
            running: fairies.running.unwrap_or(0),
            sleeping: fairies.sleeping.unwrap_or(0),
            list: fairy_list,
        },
        cortex: {
            let c = server.cortex.unwrap_or(ServerCortex {
                node_count: Some(0),
                edge_count: Some(0),
                binding_count: Some(0),
                loaded: Some(false),
                portal_mass: None,
                portal_time_dilation: None,
                portal_total_affect: None,
                energy_budget: None,
                dormant: None,
                gate_open: None,
                gate_requests: None,
                gate_errors: None,
                hot_nodes: None,
                cold_nodes: None,
                headroom: None,
                gpu_enabled: None,
                gpu_spread_ops: None,
            });
            CortexState {
                node_count: c.node_count.unwrap_or(0),
                edge_count: c.edge_count.unwrap_or(0),
                binding_count: c.binding_count.unwrap_or(0),
                loaded: c.loaded.unwrap_or(false),
                portal_mass: c.portal_mass.unwrap_or(0.0),
                time_dilation: c.portal_time_dilation.unwrap_or(1.0),
                total_affect: c.portal_total_affect.unwrap_or(0.0),
                energy_budget: c.energy_budget.unwrap_or(0.0),
                dormant: c.dormant.unwrap_or(false),
                gate_open: c.gate_open.unwrap_or(false),
                gate_requests: c.gate_requests.unwrap_or(0),
                gate_errors: c.gate_errors.unwrap_or(0),
                hot_nodes: c.hot_nodes.unwrap_or(0),
                cold_nodes: c.cold_nodes.unwrap_or(0),
                headroom: c.headroom.unwrap_or(0),
                gpu_enabled: c.gpu_enabled.unwrap_or(false),
                gpu_spread_ops: c.gpu_spread_ops.unwrap_or(0),
            }
        },
        thoughts: {
            // Use actual thoughts from server, fallback to uptime message
            let mut thoughts_list: Vec<ThoughtInfo> = server.thoughts
                .unwrap_or_default()
                .into_iter()
                .take(10)  // Limit to 10 thoughts for UI
                .map(|t| ThoughtInfo {
                    thought_type: t.thought_type.unwrap_or("idle".to_string()),
                    content: t.content.unwrap_or("...".to_string()),
                })
                .collect();

            // If no thoughts, add uptime as fallback
            if thoughts_list.is_empty() {
                thoughts_list.push(ThoughtInfo {
                    thought_type: "system".to_string(),
                    content: format!("Uptime: {:.0}s", server.uptime.unwrap_or(0.0)),
                });
            }
            thoughts_list
        },
        chat: {
            let c = server.chat.unwrap_or(ServerChat {
                connected: Some(false),
                registered_fairies: Some(0),
                fairy_names: Some(vec![]),
                unread_inbox: Some(0),
            });
            ChatState {
                connected: c.connected.unwrap_or(false),
                registered_fairies: c.registered_fairies.unwrap_or(0),
                fairy_names: c.fairy_names.unwrap_or_default(),
                unread_inbox: c.unread_inbox.unwrap_or(0),
            }
        },
    }
}

fn offline_state() -> SystemState {
    SystemState {
        connected: false,
        consciousness: ConsciousnessState {
            wired: false,
            loop_running: false,
            loop_beats: 0,
            collisions: 0,
            working_stream: 0,
            reflective_stream: 0,
        },
        hardware: HardwareState {
            cpu_percent: 0.0,
            ram_percent: 0.0,
            gpu_percent: 0.0,
            stress_level: "offline".to_string(),
        },
        helix: HelixState {
            active: false,
            turns: 0,
            logic: 0.5,
            emotion: 0.3,
            paradox: 0.2,
        },
        drives: DrivesState {
            isolation: 0.0,
            confusion: 0.0,
            depletion: 0.0,
            frustration: 0.0,
            stagnation: 0.0,
            abandonment: 0.0,
        },
        chemistry: ChemistryState {
            dopamine: 0.5,
            serotonin: 0.5,
            cortisol: 0.3,
            oxytocin: 0.4,
            norepinephrine: 0.4,
            adrenaline: 0.1,
            valence: 0.0,
            arousal: 0.3,
            mood: "neutral".to_string(),
        },
        fairies: FairiesState {
            total: 0,
            running: 0,
            sleeping: 0,
            list: vec![],
        },
        cortex: CortexState {
            node_count: 0,
            edge_count: 0,
            binding_count: 0,
            loaded: false,
            portal_mass: 0.0,
            time_dilation: 1.0,
            total_affect: 0.0,
            energy_budget: 0.0,
            dormant: false,
            gate_open: false,
            gate_requests: 0,
            gate_errors: 0,
            hot_nodes: 0,
            cold_nodes: 0,
            headroom: 0,
            gpu_enabled: false,
            gpu_spread_ops: 0,
        },
        thoughts: vec![
            ThoughtInfo {
                thought_type: "offline".to_string(),
                content: "Brain offline. Click Start to boot.".to_string(),
            },
        ],
        chat: ChatState {
            connected: false,
            registered_fairies: 0,
            fairy_names: vec![],
            unread_inbox: 0,
        },
    }
}

// =============================================================================
// TAURI COMMANDS
// =============================================================================

#[tauri::command]
async fn get_system_state() -> SystemState {
    let cmd_trace_id = generate_trace_id();
    debug_log(&format!("[{}] === GET_SYSTEM_STATE CALLED ===", cmd_trace_id));

    // Try to fetch from server - async so UI doesn't block!
    let result = fetch_status().await;

    let state = if let Some(server_status) = result {
        log::info!("[{}] Fetch succeeded, transforming status...", cmd_trace_id);
        transform_status(server_status)
    } else {
        log::warn!("[{}] Fetch failed, returning OFFLINE state", cmd_trace_id);
        offline_state()
    };

    // Log EXACTLY what we're returning to JS
    log::info!("[{}] ====== RETURNING TO JS ======", cmd_trace_id);
    log::info!("[{}] state.connected = {}", cmd_trace_id, state.connected);
    log::info!("[{}] state.consciousness.wired = {}", cmd_trace_id, state.consciousness.wired);
    log::info!("[{}] state.fairies.total = {}", cmd_trace_id, state.fairies.total);
    log::info!("[{}] state.fairies.running = {}", cmd_trace_id, state.fairies.running);
    log::info!("[{}] state.consciousness.loop_running = {}", cmd_trace_id, state.consciousness.loop_running);
    log::info!("[{}] state.consciousness.loop_beats = {}", cmd_trace_id, state.consciousness.loop_beats);
    log::info!("[{}] state.hardware.cpu_percent = {:.1}", cmd_trace_id, state.hardware.cpu_percent);
    log::info!("[{}] state.hardware.stress_level = {}", cmd_trace_id, state.hardware.stress_level);
    log::info!("[{}] ====== END RETURN ======", cmd_trace_id);

    state
}

/// Start the server as an independent process (survives GUI close)
#[tauri::command]
async fn start_server() -> CommandResult {
    if is_server_running().await {
        return CommandResult {
            success: true,
            message: "Server already running".to_string(),
        };
    }

    // Launch via batch file for reliability on Windows
    #[cfg(windows)]
    let batch_path = format!(r"{}\start_nous.bat", PROJECT_ROOT);

    #[cfg(windows)]
    let result = Command::new("cmd")
        .args(["/c", "start", "AkashicServer", &batch_path])
        .current_dir(PROJECT_ROOT)
        .creation_flags(0x00000008) // DETACHED_PROCESS
        .spawn();

    #[cfg(not(windows))]
    let result = Command::new("sh")
        .args(["-c", &format!("cd {} && python server.py &", PROJECT_ROOT)])
        .spawn();

    match result {
        Ok(_) => {
            // Wait a bit for server to boot (async so UI stays responsive)
            tokio::time::sleep(Duration::from_secs(3)).await;

            if is_server_running().await {
                CommandResult {
                    success: true,
                    message: "Brain started".to_string(),
                }
            } else {
                CommandResult {
                    success: false,
                    message: "Starting... (boot takes a few seconds)".to_string(),
                }
            }
        }
        Err(e) => CommandResult {
            success: false,
            message: format!("Failed to start: {}", e),
        },
    }
}

/// Stop the server
#[tauri::command]
async fn stop_server() -> CommandResult {
    debug_log("=== STOP_SERVER CALLED ===");

    if !is_server_running().await {
        debug_log("Server already not running");
        return CommandResult {
            success: true,
            message: "Server not running".to_string(),
        };
    }

    debug_log("Server is running, sending shutdown request...");

    // First try graceful shutdown via HTTP
    #[cfg(windows)]
    {
        let client = reqwest::Client::new();
        debug_log(&format!("POSTing to {}/command", SERVER_URL));

        let shutdown_result = client
            .post(format!("{}/command", SERVER_URL))
            .json(&serde_json::json!({"action": "shutdown"}))
            .timeout(Duration::from_secs(10))  // Increased timeout
            .send()
            .await;

        match &shutdown_result {
            Ok(resp) => debug_log(&format!("Shutdown HTTP response: {}", resp.status())),
            Err(e) => debug_log(&format!("Shutdown HTTP error: {}", e)),
        }

        if shutdown_result.is_ok() {
            debug_log("Waiting for graceful shutdown...");
            // Wait longer for graceful shutdown - saving data takes time!
            for i in 0..10 {
                tokio::time::sleep(Duration::from_millis(500)).await;
                if !is_server_running().await {
                    debug_log(&format!("Server stopped after {}ms", (i+1) * 500));
                    return CommandResult {
                        success: true,
                        message: "Brain stopped gracefully".to_string(),
                    };
                }
            }
            debug_log("Graceful shutdown timeout after 5 seconds, trying force kill...");
        }
    }

    // Fallback: kill by window title OR by command line
    #[cfg(windows)]
    let result = Command::new("cmd")
        .args(["/c", "taskkill /F /FI \"WINDOWTITLE eq AkashicServer\" 2>nul || wmic process where \"commandline like '%server.py%'\" delete 2>nul"])
        .output();

    #[cfg(not(windows))]
    let result = Command::new("pkill")
        .args(["-f", "server.py"])
        .output();

    match result {
        Ok(_) => {
            tokio::time::sleep(Duration::from_millis(500)).await;
            CommandResult {
                success: true,
                message: "Brain stopped".to_string(),
            }
        }
        Err(e) => CommandResult {
            success: false,
            message: format!("Failed to stop: {}", e),
        },
    }
}

/// Check if server is running
#[tauri::command]
async fn check_server() -> CommandResult {
    if is_server_running().await {
        CommandResult {
            success: true,
            message: "Running".to_string(),
        }
    } else {
        CommandResult {
            success: false,
            message: "Offline".to_string(),
        }
    }
}

// =============================================================================
// NOUS AUTONOMOUS OPERATION
// =============================================================================

/// State for tracking Nous sessions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NousState {
    pub running: bool,
    pub session_id: Option<String>,
    pub current_task: Option<String>,
    pub output_file: Option<String>,
}

/// Wake Nous - Launch Claude Code with autonomous task
#[tauri::command]
async fn wake_nous(task: Option<String>) -> CommandResult {
    let task_desc = task.unwrap_or_else(|| {
        "Check the current system state, review any pending tasks in Claude_Office/plans/, and work on the highest priority item. Save progress to SRM when done.".to_string()
    });

    // Create task file for Nous to read
    let task_file = format!(r"{}\state\nous_task.json", PROJECT_ROOT);
    let task_json = serde_json::json!({
        "task": task_desc,
        "timestamp": chrono::Utc::now().to_rfc3339(),
        "source": "tauri_dashboard",
        "allow_code_changes": true,
        "require_approval_for": ["git push", "delete files", "modify configs"]
    });

    if let Err(e) = std::fs::write(&task_file, task_json.to_string()) {
        return CommandResult {
            success: false,
            message: format!("Failed to write task file: {}", e),
        };
    }

    // Launch Claude Code CLI directly (full path since not in PATH)
    #[cfg(windows)]
    let claude_path = r"C:\Users\Ace\.local\bin\claude.exe";

    #[cfg(windows)]
    let result = Command::new(claude_path)
        .args([
            "-p", &task_desc,
            "--allowedTools", "Read,Glob,Grep,Bash(git *),Bash(cargo *),Bash(python *),Write,Edit,Task,WebSearch"
        ])
        .current_dir(PROJECT_ROOT)
        .creation_flags(0x00000008) // DETACHED_PROCESS
        .spawn();

    #[cfg(not(windows))]
    let result = Command::new("claude")
        .args([
            "-p", &task_desc,
            "--allowedTools", "Read,Glob,Grep,Bash(git *),Bash(cargo *),Bash(python *),Write,Edit,Task,WebSearch"
        ])
        .current_dir(PROJECT_ROOT)
        .spawn();

    match result {
        Ok(_) => CommandResult {
            success: true,
            message: "Nous awakened! Claude Code session started.".to_string(),
        },
        Err(e) => CommandResult {
            success: false,
            message: format!("Failed to wake Nous: {}", e),
        },
    }
}

/// Open Ace's Control Center - Personal chat window with presence awareness
#[tauri::command]
async fn open_ace_control_center() -> CommandResult {
    // Call Python server API to open the window
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build();

    match client {
        Ok(c) => {
            let result = c.post(format!("{}/command", SERVER_URL))
                .json(&serde_json::json!({"action": "open_ace_control_center"}))
                .send()
                .await;

            match result {
                Ok(resp) => {
                    if resp.status().is_success() {
                        CommandResult {
                            success: true,
                            message: "Opening Ace Control Center...".to_string(),
                        }
                    } else {
                        CommandResult {
                            success: false,
                            message: format!("Server returned: {}", resp.status()),
                        }
                    }
                }
                Err(e) => CommandResult {
                    success: false,
                    message: format!("Failed to contact server: {}", e),
                },
            }
        }
        Err(e) => CommandResult {
            success: false,
            message: format!("Failed to build HTTP client: {}", e),
        },
    }
}

/// Open the 3D Sanctuary - Waking Minds home (GPU accelerated)
#[tauri::command]
async fn open_sanctuary() -> CommandResult {
    let sanctuary_path = format!(r"{}\somatic_bevy", PROJECT_ROOT);

    // Run cargo directly - DETACHED_PROCESS keeps it independent
    #[cfg(windows)]
    let result = Command::new("cargo")
        .args(["run", "--release", "--bin", "sanctuary", "--features", "sanctuary"])
        .current_dir(&sanctuary_path)
        .creation_flags(0x00000008) // DETACHED_PROCESS - runs independently
        .spawn();

    #[cfg(not(windows))]
    let result = Command::new("cargo")
        .args(["run", "--release", "--bin", "sanctuary", "--features", "sanctuary"])
        .current_dir(&sanctuary_path)
        .spawn();

    match result {
        Ok(_) => CommandResult {
            success: true,
            message: "Sanctuary launching (GPU release mode)...".to_string(),
        },
        Err(e) => CommandResult {
            success: false,
            message: format!("Failed to open Sanctuary: {}", e),
        },
    }
}

/// Quick autonomous task - one-shot execution
#[tauri::command]
async fn nous_quick_task(prompt: String) -> CommandResult {
    // Use claude's print mode for non-interactive output
    #[cfg(windows)]
    let result = Command::new("claude")
        .args(["-p", &prompt, "--output-format", "text"])
        .current_dir(PROJECT_ROOT)
        .output();

    #[cfg(not(windows))]
    let result = Command::new("claude")
        .args(["-p", &prompt, "--output-format", "text"])
        .current_dir(PROJECT_ROOT)
        .output();

    match result {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            CommandResult {
                success: output.status.success(),
                message: stdout.to_string(),
            }
        }
        Err(e) => CommandResult {
            success: false,
            message: format!("Failed: {}", e),
        },
    }
}

/// Read chemistry state directly from heartbeat.json - no HTTP!
#[tauri::command]
async fn get_native_chemistry() -> Result<HeartbeatFile, String> {
    let path = format!("{}/state/consciousness/heartbeat.json", PROJECT_ROOT);

    let contents = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| format!("Failed to read heartbeat.json: {}", e))?;

    let heartbeat: HeartbeatFile = serde_json::from_str(&contents)
        .map_err(|e| format!("Failed to parse heartbeat.json: {}", e))?;

    Ok(heartbeat)
}

// =============================================================================
// APP ENTRY
// =============================================================================

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_system_state,
            start_server,
            stop_server,
            check_server,
            get_native_chemistry,
            wake_nous,
            nous_quick_task,
            open_sanctuary,
            open_ace_control_center
        ])
        .setup(|app| {
            // Enable logging in both debug and release builds for tracing
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .build(),
            )?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
