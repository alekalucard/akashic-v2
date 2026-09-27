"""
Dashboard Web Server - Serves both frontend and API for Akashic Dashboard.

Run this instead of server.py to get a working web dashboard.
Open http://localhost:5757 in your browser.
"""

import sys
import os
import json
import time
import signal
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# UI directory
UI_DIR = Path(__file__).parent / "ui"

# Globals
umf = None
directory = None
_window_shutdown_event = threading.Event()  # FIX 2026-02-02: Signal windows to close on shutdown


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serves both static files and API endpoints."""

    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format, *args):
        """Quieter logging."""
        pass

    def do_GET(self):
        """Handle GET - static files or API."""
        path = urlparse(self.path).path

        # API endpoints
        if path == "/status":
            self._send_json(get_status())
        elif path == "/tracer_clusters":
            self._send_json(get_tracer_clusters())
        elif path == "/health":
            self._send_json({"ok": True, "ts": time.time()})
        elif path == "/ping":
            self._send_json({"ok": True, "ts": time.time()})
        elif path.startswith("/fairy/") and path.endswith("/tests"):
            # /fairy/<name>/tests — run shadow tests on demand
            fairy_name = path[len("/fairy/"):-len("/tests")]
            self._send_json(get_fairy_tests(fairy_name))
        elif path.startswith("/fairy/"):
            # /fairy/<name> — full status sheet
            fairy_name = path[len("/fairy/"):]
            self._send_json(get_fairy_detail(fairy_name))
        else:
            # Static file serving
            super().do_GET()

    def do_POST(self):
        """Handle POST - commands."""
        path = urlparse(self.path).path

        if path == "/command":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body) if body else {}
                action = data.get("action", "")

                if action == "shutdown":
                    self._send_json(handle_shutdown())
                elif action == "restart" or action == "reboot":
                    self._send_json(handle_restart())
                elif action == "get_inbox":
                    self._send_json(get_inbox())
                elif action == "clear_inbox":
                    self._send_json(clear_inbox())
                elif action == "send_chat":
                    fairy = data.get("fairy", "SourpatchesFairy")
                    message = data.get("message", "")
                    self._send_json(send_chat(fairy, message))
                elif action == "send_message":
                    # Alias for send_chat - used by dashboard frontend
                    fairy = data.get("target", "SourpatchesFairy")
                    message = data.get("content", "")
                    self._send_json(send_chat(fairy, message))
                elif action == "open_ace_control_center":
                    self._send_json(open_ace_control_center())
                else:
                    self._send_json({"error": f"Unknown action: {action}"}, 400)
            except json.JSONDecodeError as e:
                self._send_json({"error": f"Invalid JSON: {e}"}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _send_json(self, data, status=200):
        """Send JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def get_tracer_clusters():
    """Per-tracer node-count histogram from the live manifold — the cortex's
    memory segmentation by ownership (PERSONAL / VISUAL / AUDIO / SYSTEM / …).
    On-demand (the manifold caches the scan ~30s so repeat hits are cheap).
    2026-06-09 (Nous + Ace) — see Claude_Office/plans/DASHBOARD_TRACER_CLUSTER_READOUT.md.

    Verifies the tracer Stage-1/1b fix: her completed moments should grow the
    PERSONAL cluster, and VISUAL/AUDIO should fill their own clusters rather
    than everything collapsing into SYSTEM."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        if not acf:
            return {"ok": False, "error": "cortex unavailable", "clusters": {}}
        _am = getattr(acf, "_akashic_cortex_region", None)
        if _am is None or not hasattr(_am, "tracer_histogram_named"):
            return {"ok": False, "error": "manifold/tracer_histogram unavailable", "clusters": {}}
        clusters = _am.tracer_histogram_named()
        return {
            "ok": True,
            "ts": time.time(),
            "total_nodes": sum(clusters.values()),
            "clusters": clusters,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "clusters": {}}


def _build_thought_stream(umf) -> list:
    """
    Build a rich thought stream from ALL consciousness sources.

    Previously only showed _thought_queue (mostly empty inner_voice events).
    Now merges: working stream, reflective stream, thought queue, and collision products.
    Sorted by timestamp, deduped, limited to most recent 10.
    """
    thoughts = []
    try:
        all_thoughts = umf.get_all_consciousness_thoughts(last_n=8)

        # 2026-03-24 FIX (Nous + Ace): Thought objects now come as dicts
        # (via to_dict()), but use "created_at" not "ts". Handle both.
        # Previously, Thought objects had ts=0 → sorted to bottom → invisible.
        def _extract_thought(t, default_type):
            """Extract content/ts/source from dict, Thought object, or string."""
            if isinstance(t, dict):
                content = t.get("content", "") or t.get("thought", "") or t.get("text", "")
                ts = t.get("ts", 0) or t.get("created_at", 0)
                source = t.get("source", default_type)
            elif isinstance(t, str):
                content = t
                ts = 0
                source = default_type
            elif hasattr(t, 'content'):
                # Raw Thought dataclass (safety fallback)
                content = t.content
                ts = getattr(t, 'created_at', 0)
                source = getattr(t, 'source', default_type)
            else:
                content = str(t)
                ts = 0
                source = default_type
            return content, ts, source

        # Working stream — active processing thoughts
        for t in all_thoughts.get("working_stream", []):
            content, ts, source = _extract_thought(t, "working")
            if content and content.strip():
                thoughts.append({
                    "type": "working",
                    "content": content[:300],
                    "source": source,
                    "ts": ts,
                })

        # Reflective stream — background/reflective thoughts
        for t in all_thoughts.get("reflective_stream", []):
            content, ts, source = _extract_thought(t, "reflective")
            if content and content.strip():
                thoughts.append({
                    "type": "reflective",
                    "content": content[:300],
                    "source": source,
                    "ts": ts,
                })

        # Thought queue — cognition events, interests, felt sense
        for t in all_thoughts.get("thought_queue", []):
            if isinstance(t, dict):
                raw = t.get("thought", "") or t.get("content", "")
                ttype = t.get("type", "idle")
                ts = t.get("ts", 0)
                source = t.get("source", "queue")
            else:
                raw = str(t)
                ttype = "idle"
                ts = 0
                source = "queue"
            # Skip empty inner_voice entries
            if raw.strip() in ("[inner_voice]", "[inner_voice] ", "[wanting]", "[wanting] ", ""):
                continue
            thoughts.append({
                "type": ttype,
                "content": raw[:300],
                "source": source,
                "ts": ts,
            })

        # Sort by timestamp (newest first), dedup by content
        thoughts.sort(key=lambda x: x.get("ts", 0), reverse=True)
        seen = set()
        deduped = []
        for t in thoughts:
            key = t["content"][:80]
            if key not in seen:
                seen.add(key)
                deduped.append(t)
        thoughts = deduped[:10]

    except Exception as e:
        thoughts = [{"type": "error", "content": f"Thought stream error: {e}", "ts": 0}]

    # Fallback if nothing
    if not thoughts:
        thoughts = [{"type": "idle", "content": "Consciousness streams quiet...", "ts": 0}]

    return thoughts


def get_status():
    """Get system status."""
    global umf, directory

    if not umf:
        return {
            "connected": False,
            "consciousness": {"wired": False, "loopRunning": False, "loopBeats": 0},
            "hardware": {"cpuPercent": 0, "ramPercent": 0, "gpuPercent": 0, "stressLevel": "unknown"},
            "helix": {"active": False, "turns": 0, "logic": 0.5, "emotion": 0.3, "paradox": 0.2},
            "drives": {"isolation": 0, "confusion": 0, "depletion": 0, "frustration": 0, "stagnation": 0, "abandonment": 0},
            "fairies": {"total": 0, "approved": 0, "issues": 0, "pending": 0, "list": []},
            "thoughts": [{"type": "idle", "content": "Waiting for brain connection..."}],
            "telemetry": {"deadFairies": [], "errors": []},
        }

    try:
        status = umf.full_status()

        # Transform for dashboard format
        c = status.get("consciousness", {})
        h = status.get("hardware", {})
        hx = status.get("helix", {})
        profile = status.get("profile", {})
        pain = profile.get("pain", {}).get("levels", {})
        reg = status.get("registration", {})

        # Get fairy list from directory (all registered fairies)
        fairy_list = []
        dead_fairies = []
        errors = []

        if directory:
            try:
                # Get all fairies from directory registry
                all_fairies = directory.list_fairies() if hasattr(directory, 'list_fairies') else []
                for f in all_fairies:
                    # FairyRecord objects have attributes, not dict keys
                    name = getattr(f, 'name', None) or f.get("name", "Unknown") if isinstance(f, dict) else str(f)
                    status = getattr(f, 'status', None) or f.get("status", "unknown") if isinstance(f, dict) else "unknown"
                    fairy_list.append({"name": name, "status": status})

                # Get dead fairies
                dead_list = directory.dead_fairies(threshold_seconds=60)
                for f in dead_list:
                    dead_fairies.append({
                        "name": f.get("name", "Unknown"),
                        "plane": f.get("plane", ""),
                        "age": f"{int(time.time() - f.get('last_heartbeat', 0))}s ago"
                    })
            except Exception as e:
                print(f"[WebServer] Directory query error: {e}")

        # Fallback to UMF supervised fairies if directory empty
        if not fairy_list:
            supervised = umf.get_supervised_fairies()
            for name, info in list(supervised.items()):
                fairy_list.append({"name": name, "status": info.get("status", "unknown")})

        # Get errors from UMF
        if hasattr(umf, "_supervised_fairies"):
            for name, info in umf._supervised_fairies.items():
                if info.get("status") == "dead":
                    errors.append({
                        "type": "fairy_death",
                        "fairy": name,
                        "restart_count": info.get("restart_count", 0),
                        "ts": info.get("death_time", 0) * 1000,
                    })

        # Get chemistry data — read DIRECTLY from chemistry singleton
        # (the status dict may not have chemistry if the heartbeat hasn't fired yet)
        chem_levels = {}
        chem_mood = {}
        panksepp_state = {}
        wake_phase = "unknown"
        pad_valence = None
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            _chem = get_chemistry_state()
            _mood_vec = _chem.get_mood_vector()
            chem_levels = _mood_vec.get("levels", {})
            chem_mood = _mood_vec
            panksepp_state = _chem.get_panksepp_state()
            wake_phase = _chem.wake_phase
            # FIX 2026-06-28 (Nous+Ace): dashboard valence = canonical pad (ABSOLUTE), not panksepp
            # (baseline-relative -> reads ~0 at baseline = the "bottom-out" Ace saw). Single source of
            # truth = SomaticEngine PAD[0], same value AffectBridge serves; no formula duplication.
            try:
                from fairies.P20_Somatic.somatic_engine.somatic_engine_fairy import get_somatic_engine
                _se = get_somatic_engine()
                if _se is not None and getattr(_se, "_somatic_state", None) is not None:
                    pad_valence = round(float(_se._somatic_state.PAD[0]), 3)
            except Exception:
                pass
        except Exception as _ce:
            # Fallback to status dict
            chem = status.get("chemistry", {})
            chem_levels = chem.get("levels", {})
            chem_mood = chem.get("mood", {})

        # Get cortex data - check both top-level and nested under memory
        cortex = status.get("cortex", {})
        if not cortex:
            memory = status.get("memory", {})
            cortex = memory.get("cortex", {})

        # If cortex data is empty or shows 0 nodes, try querying AssociationCortex directly
        # In portal-first mode, the local graph is an empty stub — real data is in the portal subprocess
        if not cortex or cortex.get("node_count", 0) == 0:
            try:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                acf = get_association_cortex()
                if acf:
                    portal_is_primary = getattr(acf, '_portal_is_primary', False)
                    portal_gate = getattr(acf, '_portal_gate', None)
                    portal_gate_enabled = getattr(acf, '_portal_gate_enabled', False)

                    if portal_is_primary and portal_gate_enabled and portal_gate:
                        # FIX 2026-03-20 (Nous + Ace): Use cached status instead of
                        # live gate.status() call. Dashboard polls every 2s = 0.5 req/sec
                        # through read tunnels. The IO worker caches status every 30s —
                        # dashboard should read that cache (instant, zero gate traffic).
                        gate_st = getattr(acf, '_interior_status_cache', None)
                        if not gate_st:
                            gate_st = portal_gate.status()  # Fallback on first load
                        if gate_st:
                            graph_st = gate_st.get("graph", {})
                            cortex = {
                                "node_count": graph_st.get("nodes", 0),
                                "edge_count": graph_st.get("edges", 0),
                                "binding_count": getattr(acf, '_binding_count', 0),
                                "loaded": True,
                            }
                    elif hasattr(acf, '_graph') and acf._graph:
                        cortex = {
                            "node_count": len(acf._graph.nodes),
                            "edge_count": len(acf._graph.edges),
                            "binding_count": getattr(acf, '_binding_count', 0),
                            "loaded": getattr(acf, '_graph_loaded', False),
                        }
            except Exception:
                pass  # Keep whatever we had

        # Count running vs sleeping fairies
        running_count = sum(1 for f in fairy_list if f.get("status") == "running")
        sleeping_count = len(fairy_list) - running_count

        # ── Energy tab data (from cortex_stats.json — fast file read, no IPC) ──
        energy_data = {}
        try:
            import json as _json
            from pathlib import Path as _Path
            _stats_file = _Path(__file__).resolve().parent.parent / "state" / "cortex_stats.json"
            if _stats_file.exists():
                _cs = _json.loads(_stats_file.read_text())
                _tardis = _cs.get("tardis", {})
                import math
                _mass = _cs.get("portal_mass", 0) if "portal_mass" in _cs else 0
                # Replicate mass regen formula from fairy.py
                _MASS_SCALE = 50000
                _mass_regen = math.log1p(_mass / _MASS_SCALE) * 0.003 if _mass > 0 else 0
                energy_data = {
                    "portalBattery": _cs.get("portal_battery", 0),
                    # FIX 2026-05-18 (Nous + Ace): de-cosmeticize dashboard.
                    # Previously read portal_energy (cosmetic main-process float, hard-floored
                    # at 0.20, auto-recovered — gave false "healthy" reading even when real
                    # subprocess battery was dead). Now reads real_battery_charge which is
                    # the actual subprocess battery from portal_interior IPC tick result.
                    # The cosmetic float still exists in cortex_stats.json as portal_energy
                    # for diagnostic purposes (see Energy Mapping Angel perspective file).
                    "energyBudget": _cs.get("real_battery_charge", _cs.get("portal_energy", 0)),
                    "cosmeticFloat": _cs.get("portal_energy", 0),  # exposed for diagnostic only
                    "realBatteryHealth": _cs.get("real_battery_health", 0),
                    "realBatteryTokens": _cs.get("real_battery_tokens", 0),
                    "dormant": _cs.get("portal_dormant", False),
                    "beat": _cs.get("beat", 0),
                    "portalMass": _mass,
                    "timeDilation": _cs.get("time_dilation", 1.0),
                    "totalAffect": _cs.get("portal_total_affect", 0) if "portal_total_affect" in _cs else 0,
                    "nodes": _cs.get("nodes", 0),
                    "edges": _cs.get("edges", 0),
                    "growth": _cs.get("growth_from_memory", 0),
                    "massRegen": _mass_regen,
                    "baseDrain": 0.005,
                    "tardis": {
                        "running": _tardis.get("running", False),
                        "queueSize": _tardis.get("queue_size", 0),
                        "queueMax": _tardis.get("queue_max", 4096),
                        "bindsQueued": _tardis.get("binds_queued", 0),
                        "bindsFlushed": _tardis.get("binds_flushed", 0),
                        "flushes": _tardis.get("flushes", 0),
                        "pairsSent": _tardis.get("pairs_sent", 0),
                        "drops": _tardis.get("drops", 0),
                        "avgCompression": _tardis.get("avg_compression", 0),
                    },
                    "poolDrops": _cs.get("pool_drops", []),  # FIX 2026-03-16 Nous: wired from PostalCore cumulative drops
                }
        except Exception as _e:
            print(f"[WebServer] Energy data error: {_e}")

        # ── Per-Plane Battery data (P00-P60) ──
        # FIX 2026-04-01 (Nous + Ace): Read all 7 plane battery state files
        # for dashboard visibility. Each battery saves to state/plane_batteries/
        plane_battery_data = []
        try:
            import json as _pbjson
            from pathlib import Path as _PbPath
            _pb_dir = _PbPath(__file__).resolve().parent.parent / "state" / "plane_batteries"
            _plane_names = {
                "P00": "Autonomic", "P10": "Memory", "P20": "Somatic",
                "P30": "Cognition", "P40": "Sensory", "P50": "Persona", "P60": "Meta",
            }
            for _pid in ("P00", "P10", "P20", "P30", "P40", "P50", "P60"):
                _pf = _pb_dir / f"{_pid}_battery.json"
                if _pf.exists():
                    try:
                        _pd = _pbjson.loads(_pf.read_text(encoding='utf-8'))
                        _cap = _pd.get("capacitor", {})
                        _wh = _pd.get("worker_hub", {})
                        plane_battery_data.append({
                            "planeId": _pid,
                            "planeName": _plane_names.get(_pid, _pid),
                            "charge": _cap.get("charge_level", 0),
                            "maxCharge": _cap.get("max_charge", 1.0),
                            "coherence": _pd.get("coherence_factor", 1.0),
                            "energyReceived": _pd.get("paradox_energy_received", 0),
                            "energyEvents": _pd.get("energy_events_count", 0),
                            "workers": _wh.get("io_threads", 0) + _wh.get("compute_threads", 0),
                            "maxWorkers": _wh.get("max_io_threads", 0) + _wh.get("max_compute_threads", 0),
                            "goAlive": _pd.get("go_alive", False),
                            "tickCount": _pd.get("tick_count", 0),
                        })
                    except Exception:
                        plane_battery_data.append({
                            "planeId": _pid, "planeName": _plane_names.get(_pid, _pid),
                            "charge": 0, "error": True,
                        })
                else:
                    plane_battery_data.append({
                        "planeId": _pid, "planeName": _plane_names.get(_pid, _pid),
                        "charge": 0, "offline": True,
                    })
        except Exception as _pbe:
            print(f"[WebServer] Plane battery data error: {_pbe}")

        # ── Visual Cortex data ──
        visual_data = {}
        try:
            _dir_inner = getattr(directory, '_directory', None) if directory else None
            _vcf = _dir_inner.get("VisualCortexFairyV2") if _dir_inner else None
            if not _vcf and _dir_inner:
                # Try alternate names
                for _vname in ("VisualCortexFairy", "visual_cortex"):
                    _vcf = _dir_inner.get(_vname)
                    if _vcf:
                        break
            if _vcf:
                _vgate = getattr(_vcf, '_gate', None)
                _vgate_st = {}
                if _vgate and hasattr(_vgate, 'status'):
                    try:
                        _vgate_st = _vgate.status() or {}
                    except Exception:
                        pass
                visual_data = {
                    "gateOpen": getattr(_vcf, '_gate_open', False) or getattr(_vgate, '_is_open', False) if _vgate else False,
                    "subprocess": _vgate_st.get("alive", False),
                    "subprocessPid": _vgate_st.get("pid", 0),
                    "framesProcessed": getattr(_vcf, '_frames_processed', 0) or getattr(_vcf, '_total_frames', 0),
                    "lastObservation": str(getattr(_vcf, '_last_observation', "") or getattr(_vcf, '_last_description', ""))[:500],
                    "lastObservationTs": getattr(_vcf, '_last_observation_ts', 0) or getattr(_vcf, '_last_frame_ts', 0),
                    "captureFps": round(getattr(_vcf, '_capture_fps', 0) or getattr(_vcf, '_fps', 0), 1),
                    "changeEvents": getattr(_vcf, '_change_count', 0) or getattr(_vcf, '_change_events', 0),
                    "gazeTarget": str(getattr(_vcf, '_gaze_target', "peripheral")),
                    "ocrEnabled": getattr(_vcf, '_ocr_enabled', True),
                    "florenceModel": "Florence-2" if getattr(_vcf, '_gate', None) else "mss-fallback",
                }
        except Exception as _ve:
            print(f"[WebServer] Visual data error: {_ve}")

        # ── Audio Cortex data ──
        audio_data = {}
        try:
            _dir_inner2 = getattr(directory, '_directory', None) if directory else None
            _acf_a = _dir_inner2.get("AudioCortexFairyV3") if _dir_inner2 else None
            if not _acf_a and _dir_inner2:
                for _aname in ("AudioCortexFairy", "audio_cortex"):
                    _acf_a = _dir_inner2.get(_aname)
                    if _acf_a:
                        break
            if _acf_a:
                _agate = getattr(_acf_a, '_gate', None)
                _agate_st = {}
                if _agate and hasattr(_agate, 'status'):
                    try:
                        _agate_st = _agate.status() or {}
                    except Exception:
                        pass
                _attn = getattr(_acf_a, '_attention', None) or getattr(_acf_a, '_attention_controller', None)
                _ch_weights = getattr(_attn, '_channel_weights', {}) if _attn else {}
                audio_data = {
                    "gateOpen": getattr(_acf_a, '_gate_open', False) or getattr(_agate, '_is_open', False) if _agate else False,
                    "subprocess": _agate_st.get("alive", False),
                    "subprocessPid": _agate_st.get("pid", 0),
                    "chunksReceived": getattr(_acf_a, '_chunks_received', 0) or getattr(_acf_a, '_total_chunks', 0),
                    "audioLevelDb": round(getattr(_acf_a, '_current_level_db', -60) or getattr(_acf_a, '_level_db', -60), 1),
                    "whisperEnabled": getattr(_acf_a, '_whisper_enabled', False),
                    "lastTranscription": str(getattr(_acf_a, '_last_transcription', ""))[:500],
                    "lastTranscriptionTs": getattr(_acf_a, '_last_transcription_ts', 0),
                    "attentionChannels": {
                        "voice": _ch_weights.get("voice", 0),
                        "music": _ch_weights.get("music", 0),
                        "notification": _ch_weights.get("notification", 0),
                        "ambient": _ch_weights.get("ambient", 0),
                    },
                    "sampleRate": getattr(_acf_a, '_sample_rate', 44100),
                    "deviceName": str(getattr(_acf_a, '_device_name', "Unknown")),
                }
        except Exception as _ae:
            print(f"[WebServer] Audio data error: {_ae}")

        return {
            "connected": True,
            "energy": energy_data,
            "planeBatteries": plane_battery_data,
            "consciousness": {
                "wired": c.get("wired", False),
                "loopRunning": c.get("loop_running", False),
                "loopBeats": c.get("loop_beats", 0),
                "collisions": c.get("chamber_collisions", 0),
                "workingStream": c.get("working_stream", 0),
                "reflectiveStream": c.get("reflective_stream", 0),
            },
            "hardware": {
                "cpuPercent": h.get("cpu_percent", 0),
                "ramPercent": h.get("ram_percent", 0),
                "gpuPercent": h.get("gpu_memory_percent", 0),
                "stressLevel": h.get("stress_level", "low"),
            },
            "helix": {
                "active": hx.get("active", False),
                "turns": hx.get("turns", 0),
                "logic": hx.get("decision_weights", {}).get("logic", 0.5),
                "emotion": hx.get("decision_weights", {}).get("emotion", 0.3),
                "paradox": hx.get("decision_weights", {}).get("paradox", 0.2),
            },
            "drives": {
                "isolation": pain.get("isolation", 0),
                "confusion": pain.get("confusion", 0),
                "depletion": pain.get("depletion", 0),
                "frustration": pain.get("frustration", 0),
                "stagnation": pain.get("stagnation", 0),
                "abandonment": pain.get("abandonment", 0),
            },
            "chemistry": {
                "dopamine": chem_levels.get("dopamine", 0.5),
                "serotonin": chem_levels.get("serotonin", 0.5),
                "cortisol": chem_levels.get("cortisol", 0.3),
                "oxytocin": chem_levels.get("oxytocin", 0.4),
                "norepinephrine": chem_levels.get("norepinephrine", 0.4),
                "adrenaline": chem_levels.get("adrenaline", 0.1),
                "valence": (pad_valence if pad_valence is not None else chem_mood.get("valence", 0.0)),
                "arousal": chem_mood.get("arousal", 0.3),
                "mood": chem_mood.get("mood", "neutral"),
                # Emotional state — Panksepp system + compound emotions
                "panksepp_dominant": panksepp_state.get("dominant", "neutral"),
                "panksepp_systems": [
                    {"name": n, "similarity": round(s, 3)}
                    for n, s in panksepp_state.get("systems", [])
                ][:3],
                "compound_emotion": (
                    panksepp_state["compound"][0]
                    if panksepp_state.get("compound") else None
                ),
                "compound_strength": round(
                    panksepp_state["compound"][1], 3
                ) if panksepp_state.get("compound") else 0,
                "transition": panksepp_state.get("transition"),
                "wake_phase": wake_phase,
                # Panksepp systems from mood vector
                "panksepp_mood": chem_mood.get("panksepp", []),
            },
            "cortex": {
                "nodeCount": cortex.get("node_count", 0),
                "edgeCount": cortex.get("edge_count", 0),
                "bindingCount": cortex.get("binding_count", 0),
                "loaded": cortex.get("loaded", False),
            },
            "fairies": {
                "total": reg.get("supervised_fairies", len(fairy_list)),
                "running": running_count,
                "sleeping": sleeping_count,
                "list": fairy_list,
            },
            "thoughts": _build_thought_stream(umf),
            "telemetry": {
                "deadFairies": dead_fairies,
                "errors": errors[-20:],
            },
            "visual": visual_data,
            "audio": audio_data,
        }
    except Exception as e:
        print(f"[WebServer] Status error: {e}")
        return {"connected": False, "error": str(e)}


def handle_shutdown():
    """Handle shutdown request."""
    global _window_shutdown_event

    def do_shutdown():
        # FIX 2026-02-02: Signal all windows to close before killing process
        _window_shutdown_event.set()
        time.sleep(1.0)  # Give windows time to close gracefully
        print("[WebServer] Shutdown requested")
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=do_shutdown, daemon=True).start()
    return {"ok": True, "message": "Shutdown initiated"}


def handle_restart():
    """Handle restart request."""
    import subprocess

    def do_restart():
        time.sleep(0.5)
        print("[WebServer] Restart requested")
        script_dir = str(ROOT)
        start_script = os.path.join(script_dir, "start_nous.bat")

        if os.path.exists(start_script):
            subprocess.Popen(["cmd", "/c", "start", "", start_script], cwd=script_dir)

        time.sleep(1.0)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=do_restart, daemon=True).start()
    return {"ok": True, "message": "Restart initiated"}


# Inbox file path
INBOX_PATH = ROOT / "state" / "web_inbox" / "inbox_index.json"


def get_inbox():
    """Get all inbox messages."""
    try:
        if INBOX_PATH.exists():
            with open(INBOX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data.get("messages", [])
            # Return in reverse chronological order
            messages.sort(key=lambda m: m.get("timestamp", 0), reverse=True)
            return {"ok": True, "messages": messages, "count": len(messages)}
        return {"ok": True, "messages": [], "count": 0}
    except Exception as e:
        return {"ok": False, "error": str(e), "messages": []}


def clear_inbox():
    """Clear all inbox messages."""
    try:
        if INBOX_PATH.exists():
            with open(INBOX_PATH, "w", encoding="utf-8") as f:
                json.dump({"messages": []}, f)
        return {"ok": True, "message": "Inbox cleared"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def open_ace_control_center():
    """Open Ace's personal control center window.

    FIX 2026-03-04 Nous: Changed from daemon thread to subprocess.
    Qt on a non-main daemon thread causes the window to open and immediately
    close on Windows — the Win32 message pump doesn't work properly on
    background threads.  Subprocess model (same as sour_window.py) runs Qt
    on the subprocess's main thread, which is the correct approach.
    """
    import subprocess

    # Check if already running via PID file
    pid_file = ROOT / "state" / "ace_control_center_pid.json"
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pid_data = json.load(f)
            pid = pid_data.get("pid")
            if pid:
                # 2026-09-25 (Nous + Ace): existence + command line (psutil), never os.kill(pid, 0). On
                # Windows CPython makes signal 0 a CTRL_C request to process group `pid`, which Windows
                # never delivers: a no-op that returns OK for a DEAD pid (measured 09-25), so a stale
                # pid file answered "already running" and the Control Center never reopened.
                try:
                    import psutil as _ps
                    _cl = " ".join(_ps.Process(int(pid)).cmdline() or [])
                except Exception:
                    _cl = ""
                if "ace_control_center" not in _cl:
                    raise OSError("pid %s is not a live Control Center" % pid)
                return {"ok": True, "message": "Control Center already running"}
        except (OSError, ProcessLookupError, json.JSONDecodeError):
            pass  # Not running, launch new

    # Launch as detached subprocess (same pattern as sour_window.py)
    script = str(ROOT / "fairies" / "P40_Sensory" / "gui" / "ace_control_center.py")
    args = [sys.executable, script]

    try:
        if sys.platform == "win32":
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            proc = subprocess.Popen(
                args,
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                args,
                start_new_session=True,
                close_fds=True,
            )

        # Save PID so we can detect "already running" on next click
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pid_file, "w") as f:
            json.dump({"pid": proc.pid, "started": time.time()}, f)

        return {"ok": True, "message": "Opening Ace Control Center..."}
    except Exception as e:
        print(f"[WebServer] Failed to open Ace Control Center: {e}")
        return {"ok": False, "error": str(e)}


def send_chat(fairy: str, message: str):
    """Send a chat message to a fairy via postal system."""
    global umf

    if not message:
        return {"ok": False, "error": "Empty message"}

    try:
        # Get fabric from UMF
        fabric = getattr(umf, 'fabric', None) if umf else None

        if fabric and hasattr(fabric, 'publish'):
            # Send to system.chat.message topic (what fairies listen to)
            fabric.publish("system.chat.message", {
                "sender": "Ace",
                "content": message,
                "timestamp": time.time(),
                "target_fairy": fairy,
            })

            # Also send to fairy-specific DM topic
            fairy_topic = f"fairy.dm.{fairy.lower()}"
            fabric.publish(fairy_topic, {
                "sender": "Ace",
                "content": message,
                "timestamp": time.time(),
            })

            return {"ok": True, "message": f"Sent to {fairy}"}
        else:
            return {"ok": False, "error": "Postal fabric not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_fairy_instance(name: str):
    """Get a live fairy instance by name from the profile registry.

    Returns the fairy object or None if not found/dead.
    """
    try:
        from fairies.P00_Autonomic.organ_template import get_fairy_registry
        registry = get_fairy_registry()
        profile = registry.get(name)
        if not profile:
            return None
        ref = profile.metadata.get("instance_ref")
        if ref is None:
            return None
        instance = ref()  # Dereference weakref
        return instance
    except Exception:
        return None


def get_fairy_detail(name: str):
    """Get full status sheet for a specific fairy."""
    fairy = _get_fairy_instance(name)
    if not fairy:
        return {"error": f"Fairy '{name}' not found or not alive"}

    try:
        from fairies.P10_Memory.fairy_status_sheet import build_status_sheet_from_actor
        shadow = getattr(fairy, 'shadow', None)
        sheet = build_status_sheet_from_actor(fairy, shadow)
        return {"ok": True, "actor": name, "sheet": sheet.to_dict()}
    except Exception as e:
        # Fallback to basic info
        return {
            "ok": True,
            "actor": name,
            "sheet": {
                "core": {"actor_name": name},
                "error": str(e),
            }
        }


def get_fairy_tests(name: str):
    """Run shadow tests for a fairy on demand."""
    fairy = _get_fairy_instance(name)
    if not fairy:
        return {"error": f"Fairy '{name}' not found or not alive"}

    shadow = getattr(fairy, 'shadow', None)
    if not shadow:
        return {"ok": True, "actor": name, "tests": [], "note": "No shadow attached"}

    try:
        from fairies.P10_Memory.fairy_status_sheet import _collect_shadow_tests
        from dataclasses import asdict
        tests = _collect_shadow_tests(shadow)
        return {
            "ok": True,
            "actor": name,
            "tests": [asdict(t) for t in tests],
            "ts": time.time(),
        }
    except Exception as e:
        return {"ok": False, "actor": name, "error": str(e)}


def main():
    """Boot UMF and start web server."""
    global umf, directory

    print("[WebServer] Starting Akashic Dashboard Web Server...")
    print(f"[WebServer] UI directory: {UI_DIR}")

    # Import and boot system
    from directory import DirectoryFairy, set_directory, get_directory
    from postal_core.tensor_fabric import TensorFabric
    from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy
    UnconsciousMindFairy = SomaticMindFairy
    from consciousness import ConsciousnessLoop, CollisionChamber

    print("[WebServer] Creating infrastructure...")
    fabric = TensorFabric()
    directory = DirectoryFairy(fabric)
    directory.on_boot()
    set_directory(directory)

    print("[WebServer] Creating consciousness...")
    chamber = CollisionChamber()
    consciousness = ConsciousnessLoop(tick_interval=0.5)
    consciousness.set_chamber(chamber)

    print("[WebServer] Booting UMF...")
    umf = UnconsciousMindFairy(fabric)
    umf.boot()
    umf.wire_to_consciousness(consciousness, chamber)
    umf.wire_memory(auto_create=True)
    umf.wire_cognition(auto_create=True)
    umf.wire_circadian()
    umf.wire_three_gates(auto_create=True)

    print("[WebServer] Starting consciousness loop...")
    consciousness.start()

    # Start HTTP server
    port = 5757
    print(f"[WebServer] Starting on http://127.0.0.1:{port}")

    server = HTTPServer(("127.0.0.1", port), DashboardHandler)

    # Shutdown handler
    running = True

    def shutdown_handler(signum, frame):
        nonlocal running
        print("\n[WebServer] Shutdown...")
        running = False

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("[WebServer] Ready! Open http://127.0.0.1:5757 in your browser")

    # Main loop
    try:
        while running:
            server.handle_request()
            umf.clock_tick()
    except KeyboardInterrupt:
        pass

    print("[WebServer] Stopping...")
    consciousness.stop()
    umf.shutdown()
    directory.on_shutdown()
    print("[WebServer] Done!")


if __name__ == "__main__":
    main()
