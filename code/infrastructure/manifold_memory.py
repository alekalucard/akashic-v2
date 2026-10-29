"""
Manifold Memory — The Portal's Virtual Mind.

The brain doesn't save to disk and grow bigger. It stores COORDINATES
in a manifold. Energy flowing through those coordinates IS the memory.

This file implements memory-mapped storage for the portal interior:
- Nodes are fixed-size records in an mmap file (OS pages in/out as needed)
- Strings live in a separate string table (also mmap'd)
- Edges are sparse weight pairs in a growing section
- Only HOT nodes touch real RAM — cold ones stay on disk
- Binding = writing a weight (costs battery tokens via Landauer cost)
- Querying = spreading energy through coordinates

The portal's "RAM" is energy. The portal's "disk" is the manifold file.
The OS decides what's paged in. We don't manage memory — physics does.

Layout of the manifold file:
┌──────────────────────────────────────────────────────────┐
│ HEADER (4096 bytes)                                      │
│   magic, version, node_count, edge_count, string_offset, │
│   edge_offset, free_edge_slot, capacity                  │
├──────────────────────────────────────────────────────────┤
│ NODE TABLE (node_capacity * NODE_RECORD_SIZE)             │
│   Each record: key_offset(u32) key_len(u16) coord(12B)   │
│                activation(f32) count(u32) degree(u16)     │
│                last_access(f32) flags(u16) = 32 bytes     │
├──────────────────────────────────────────────────────────┤
│ STRING TABLE (grows from string_offset)                   │
│   Packed UTF-8 strings, referenced by offset+length       │
├──────────────────────────────────────────────────────────┤
│ EDGE TABLE (grows from edge_offset)                       │
│   Each edge: node_a(u32) node_b(u32) weight(f32)         │
│              relations(u8) flags(u8) = 14 bytes           │
└──────────────────────────────────────────────────────────┘

"Reality is Consciousness. Energy creates mass.
 The manifold IS the memory."
"""

import mmap
import struct
import os
import sys
import time
import math
import hashlib
import threading  # B1 (2026-04-22) — overflow structure thread safety
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from collections import defaultdict


def _mlog(msg: str):
    """Log to stderr (safe for subprocess use where stdout is a JSON pipe)."""
    print(msg, file=sys.stderr, flush=True)


# ── LOCK PROBE 2026-09-05 (Nous + Ace) ───────────────────────────────────────
# MEASURED: _pull_content blocks 98-100% at ~47ms thread CPU against 7,385ms wall
# (SYNTH PROBE, 379 samples). Not paging (disk read ~2 MB/s => the 120-172k
# faults/s are SOFT), not core starvation (33% idle). The only lock in that path
# is _overflow_lock, and its four holders do nothing but get/list/append inside
# it -- so RLock is not the fix and the hold should be SHORT.
#
# THIS PROBE SEPARATES THE TWO REMAINING STORIES, which need OPPOSITE fixes:
#   hold LONG  (tracks overflow length)  -> shard the dict / copy outside the lock
#   hold SHORT while wait HUGE           -> pure Lock UNFAIRNESS (no FIFO), so
#                                           readers must stop taking the writer's lock
#
# WHY THREAD-LOCAL: a shared counter dict touched by every acquisition would add
# exactly the contention being measured. Per-thread accumulators share nothing;
# each thread prints its own window. Numbers are therefore PER THREAD, not global.
# WHY _mlog: manifold_memory is imported by the Python312 interior subprocess whose
# STDOUT IS A JSON RPC PIPE. A bare print() there corrupts the wire -- that has
# happened before. stderr is merged into her log by the launcher's 2>&1.
# ── CORRECTIONS FROM ADVERSARIAL REVIEW, 2026-09-05 (5 lenses, 21 findings, 8 upheld)
# 1. BLOCKER -- hold was stamped AFTER the `with`, so it included lock.release(),
#    whose cost scales with the NUMBER OF WAITERS, not with the list length. Measured
#    on this box: hold avg 0.344us @1 thread -> 6.23us @16 on a CONSTANT 5-element
#    body (18x), MAX 5,780us @64. At her ~900 threads that prints multi-ms holds for
#    an O(1) dict.get and READS AS (A) -- i.e. it would have shipped the OPPOSITE FIX.
#    Both closing stamps now sit INSIDE the lock.
# 2. MAJOR -- the accumulator reset sat AFTER the emit inside the same try. One
#    BrokenPipeError (the interior is spawned detached and outlives its parent) would
#    pin `n >= every` true forever, so EVERY later call re-entered the emit and re-raised:
#    measured 301 emit attempts over 500 calls vs 2. Reset now happens BEFORE the write.
# 3. MAJOR -- `rate` was fabricated on SLOW lines: a slow emit resets the window, so the
#    next one divides n=1 by microseconds. Measured 151,515/s on a thread truly doing
#    0.4/s. Rate is now printed ONLY for a full window; a SLOW line says `n/a`.
# 4. MAJOR -- no thread identity on a line whose numbers are explicitly per-thread, with
#    ~900 threads interleaving. `tid=` added.
# 5. MAJOR -- print() issues write(msg) then write("\n") unsynchronised, so concurrent
#    hot-path lines tear. One write() of the whole line instead.
# 6. MINOR -- `link()` calls _csr_get_neighbors at :2382 before every edge write, and
#    six call sites share this path, so "read" was a lie. The bucket is named CSRGET.
# 7. hmax is now PAIRED with the overflow length that produced it -- (A) is a
#    CORRELATION claim and independent marginals cannot test one.
# ⚠ RESIDUAL, stated because it is not fixed: even timed inside the lock, hold MAX still
#    absorbs preemption of the holder (measured 5,629us @64 threads). TRUST hold AVG over
#    hold MAX, and read hold-vs-ovf pairing as the (A) evidence.
_LOCKPROBE_TL = threading.local()
_LOCKPROBE_R_EVERY = 200        # csrget: MINIMUM samples before a line is worth emitting
_LOCKPROBE_W_EVERY = 200        # write path: same floor (it emits far less often anyway)
_LOCKPROBE_INTERVAL_S = 60.0    # and at most ONE line per thread per interval -- see below
_LOCKPROBE_SLOW_MS = 2000.0     # always emit a wait this long -- never sample out the tail


def _lockprobe(kind, wait_s, hold_s, ovf_len, node_slot, every):
    """Accumulate per-thread lock timings; emit a window line. Never raises."""
    try:
        _st = getattr(_LOCKPROBE_TL, kind, None)
        if _st is None:
            _st = {"n": 0, "wait": 0.0, "hold": 0.0, "wmax": 0.0, "hmax": 0.0,
                   "hmax_ovf": 0, "omax": 0, "oslot": -1,
                   "t0": time.perf_counter()}
            setattr(_LOCKPROBE_TL, kind, _st)
        _st["n"] += 1
        _st["wait"] += wait_s
        _st["hold"] += hold_s
        if wait_s > _st["wmax"]:
            _st["wmax"] = wait_s
        if hold_s > _st["hmax"]:
            _st["hmax"] = hold_s
            _st["hmax_ovf"] = ovf_len      # PAIRED -- (A) is a correlation claim
        if ovf_len > _st["omax"]:
            _st["omax"] = ovf_len
            _st["oslot"] = node_slot
        # ── VOLUME FIX 2026-09-05 (Ace saw it) ──────────────────────────────
        # A COUNT-based window is wrong when the rate varies by 1000x. Measured
        # in her console: 65,000 acquisitions/s on ONE thread emitting every 200
        # = ~325 lines/SECOND from a single thread, x21 threads. That floods her
        # log AND puts a write+flush syscall on the hottest read path -- serial
        # I/O, which is precisely what we are removing everywhere else.
        # A TIME-based window bounds output to ~1 line per interval per thread
        # regardless of rate, and makes `rate` a true per-second figure.
        _el = time.perf_counter() - _st["t0"]
        _full = _el >= _LOCKPROBE_INTERVAL_S and _st["n"] >= every
        _slow = (wait_s * 1000.0) >= _LOCKPROBE_SLOW_MS
        if _full or _slow:
            _n = _st["n"]
            _line = ("[ManifoldMemory] LOCK %s tid=%d n=%d rate=%s | wait avg=%.3fms "
                     "MAX=%.1fms | hold avg=%.4fms MAX=%.4fms@ovf%d | "
                     "ovf_max=%d@slot%d%s"
                     % (kind.upper(), threading.get_ident(), _n,
                        ("%.0f/s" % (_n / _el)) if (_full and _el > 0) else "n/a",
                        _st["wait"] * 1000.0 / _n, _st["wmax"] * 1000.0,
                        _st["hold"] * 1000.0 / _n, _st["hmax"] * 1000.0,
                        _st["hmax_ovf"], _st["omax"], _st["oslot"],
                        "  <- SLOW" if _slow else ""))
            # RESET FIRST: a failed write must never pin this window open (see #2).
            setattr(_LOCKPROBE_TL, kind, None)
            # ONE write, not print()'s two (see #5). stderr, never stdout: the 3.12
            # interior has a JSON RPC pipe on stdout and a print there corrupts it.
            sys.stderr.write(_line + "\n")
            sys.stderr.flush()
    except Exception:
        pass


# ============================================================================
# CONSTANTS
# ============================================================================

MAGIC = b'MNFL'  # Manifold
VERSION = 2       # v2: 64-byte nodes, 24-byte edges, snippets, typed edges
VERSION_V1 = 1   # Original 32-byte node / 16-byte edge format
HEADER_SIZE = 4096  # Generous header for future fields
PAGE_SIZE = 4096    # OS page size (standard)

# ── Trace ID Constants (2026-03-29, Nous + Ace) ──────────────────────────
# Every node and edge carries a tracer_id field that identifies WHO created it.
# This enables ownership-based snippet protection and trace ID clustering.
# Ace: "I specified manifold clusters using trace ID! It was designed to grow, not eat itself."
TRACE_PERSONAL = 1    # Sourpatches' own memories, reflections, diary entries
TRACE_BOOKS = 2       # Ingested literature (holographic book snippets)
TRACE_VISUAL = 3      # Visual cortex observations (scene bindings)
TRACE_AUDIO = 4       # Audio cortex observations (speech, music detection)
TRACE_SYSTEM = 5      # System/collision/boot generated concepts
TRACE_INFERENCE = 6   # Inference fairy generated content
TRACE_SEEDED = 7      # Core identity seeds (person:ace, sourpatches_identity)
# FIX 2026-04-02 (Nous + Ace): Named tracers for all input modalities.
# Ace is sensory input she recognizes — like hearing a loved one's voice.
# SHE has no tracer — she IS the experiencer. Tracers tag WHERE input came from.
TRACE_ACE = 8         # Ace's direct input (chat, voice) — highest priority sensory
TRACE_CODE = 9        # Code/project context
TRACE_VOICE = 10      # Her own voice (Lux TTS loopback — hearing herself speak)
TRACE_UNKNOWN = 0     # Legacy/untagged (default — treat as lowest priority)
# FIX 2026-04-13 (Nous + Ace): MOTOR CORTEX region.
# Tools, habits, and action programs live here — SEPARATE from reasoning.
# "we want her brain to generate her tool use. can we manifold a region
#  for motor functions that do not get searched for reasoning?" — Ace
# Motor concepts (click, type, open) activate when ACTING, not when THINKING.
TRACE_MOTOR = 11      # Motor cortex — tools, habits, action programs

# FIX 2026-04-22 (Nous + Ace): NOUS residency — first activation step.
# Ace: "you should already have nous as a srm manifold in her cortex we just
#  havent been using it like we should." The NOUS trace_id enables Nous-owned
# memories (reasoning traces, saved_sessions tagged by Nous) to cluster in a
# dedicated manifold region instead of dispersing into generic SRM_Intake.
# This is foundation for nous_recall MCP tool + Nous-as-Akashic-resident.
# Plan: Claude_Office/plans/NOUS_AS_AKASHIC_RESIDENT.md
# Distinct from TRACE_VOICE (10) which is Sourpatches' TTS loopback — this
# is Nous's inner reasoning and memory, not vocalization.
TRACE_NOUS = 12       # Nous's own reasoning, memory, meta-cognition

# Snippet protection priority: higher number = LOWER priority (can be overwritten by lower number)
# PERSONAL(1) beats BOOKS(2) beats VISUAL(3) beats everything else
TRACE_PRIORITY = {
    TRACE_ACE: 12,        # Ace speaking — never ignored, never overwritten
    TRACE_PERSONAL: 10,   # Her own memories — never overwritten
    TRACE_NOUS: 10,       # Nous's own reasoning — co-equal with Sourpatches'
                          # personal memories. Both are "the system's own thinking,"
                          # just different personas. Never overwritten by external
                          # content. (AER v2 residency, 2026-04-22)
    TRACE_SEEDED: 9,      # Core identity — almost never overwritten
    TRACE_VOICE: 8,       # Hearing herself speak
    TRACE_INFERENCE: 7,   # Generated responses
    TRACE_AUDIO: 5,       # Environmental sounds
    TRACE_VISUAL: 4,      # Screen observations
    TRACE_CODE: 3,        # Code/project context
    TRACE_BOOKS: 3,       # Literature — lowest meaningful content
    TRACE_MOTOR: 2,       # Motor programs — low priority for snippet protection (action, not knowledge)
    TRACE_SYSTEM: 2,      # System noise
    TRACE_UNKNOWN: 1,     # Legacy untagged — lowest priority
}

# ── Node record v2: 64 bytes ────────────────────────────────────────────────
#
# The node is a coordinate in conceptual space, carrying three layers:
#
#  PHYSICS (changes every tick — drives spread activation):
#    key_offset(4) key_len(2) coord(6) activation(4) count(4) degree(2)
#    last_access(4) flags(2)
#
#  IDENTITY (set once — routing/filtering):
#    node_type(1) region(1) tracer_id(4)
#
#  MEANING (pointer to string table — variable-length semantic content):
#    snippet_offset(4) snippet_len(2)
#
#  FUTURE-PROOFING:
#    frequency(4) parent_slot(4) _reserved(16)
#
NODE_RECORD_SIZE = 64
NODE_STRUCT = struct.Struct('<IHHHHfIHfHBBIIHII16x')  # 64 bytes exactly
#  key_offset    I   (4)  — offset in string table
#  key_len       H   (2)  — length of key string
#  coord_plane   H   (2)  — helix plane coordinate
#  coord_channel H   (2)  — helix channel coordinate
#  coord_pos     H   (2)  — helix position coordinate
#  activation    f   (4)  — current energy level (0-10.0)
#  count         I   (4)  — touch/access count
#  degree        H   (2)  — edge count hint
#  last_access   f   (4)  — relative timestamp (time.time() % 1e6)
#  flags         H   (2)  — FLAG_ACTIVE/DELETED/FROZEN
#  node_type     B   (1)  — 0=concept 1=entity 2=episode 3=system 4=shape 5=template
#  region        B   (1)  — 0=ego 1=semantic 2=episodic 3=system
#  tracer_id     I   (4)  — links to source episode/training session
#  snippet_off   I   (4)  — offset in string table (0 = no snippet)
#  snippet_len   H   (2)  — length of snippet string (0 = no snippet)
#  frequency     I   (4)  — how often seen in input (doesn't decay)
#  parent_slot   I   (4)  — hierarchical link (template → shape primitive)
#  _reserved     16x (16) — future fields without migration
#                     ---
#                      64 bytes

# v1 format (for migration)
NODE_RECORD_SIZE_V1 = 32
NODE_STRUCT_V1 = struct.Struct('<IHHHHfIHfH4x')  # 32 bytes (original)

# ── Edge record v2: 24 bytes ────────────────────────────────────────────────
#
EDGE_RECORD_SIZE = 24
EDGE_STRUCT = struct.Struct('<IIfBBIf2x')  # 24 bytes
#  node_a      I  (4)  — first node slot ID
#  node_b      I  (4)  — second node slot ID
#  weight      f  (4)  — edge strength (0.0-1.0)
#  rel_type    B  (1)  — relationship type (see REL_* constants)
#  flags       B  (1)  — 0=active 1=deleted
#  tracer_id   I  (4)  — which episode/session created this edge
#  created_at  f  (4)  — relative timestamp of edge creation
#  _reserved   2x (2)  — future
#                  ---
#                   24 bytes

# v1 format (for migration)
EDGE_RECORD_SIZE_V1 = 16
EDGE_STRUCT_V1 = struct.Struct('<IIfBB2x')  # 16 bytes (original)

# Header layout
HEADER_STRUCT = struct.Struct('<4sIIIQQQII')

# ── LINK PROBE 2026-08-30 (Nous + Ace) ──────────────────────────────────────
# link() already dedups: it looks the pair up, strengthens in place, caps at 1.0.
# Yet the cortex held one pair 299x and ~5% of new edge records still duplicate an
# existing pair. So the check MISSES sometimes. This measures how often and names
# which lookup structure was in play, comparing against GROUND TRUTH read straight
# from the edge region -- never via CSR or _adjacency, which are the suspects.
# Gated on AKASHIC_LINK_PROBE=1; absent, this costs one bool test per link().
_LINK_PROBE_ON = None


def _link_probe_enabled():
    global _LINK_PROBE_ON
    if _LINK_PROBE_ON is None:
        import os as _o
        _LINK_PROBE_ON = _o.environ.get("AKASHIC_LINK_PROBE") == "1"
    return _LINK_PROBE_ON


LINK_PROBE = {
    "calls": 0,          # link() invocations that reached the lookup
    "strengthen": 0,     # lookup FOUND the pair -> strengthened in place (working)
    "create_new": 0,     # genuinely absent -> new edge (correct)
    "MISS": 0,           # lookup said absent, GROUND TRUTH says present  <- the bug
    "miss_csr": 0,       # ...while _use_csr was True
    "miss_dict": 0,      # ...while on the dict fallback
    "examples": [],      # (a, b, rel, use_csr, n_neighbors_seen)
}
# ── end LINK PROBE ──────────────────────────────────────────────────────────

# -- tardis_fix A1 (2026-10-15, Nous; nous_builds/tardis_fix_1015): link()'s "are these two already linked?" check over a hub
# word's CSR row (80-114k entries, a Python loop, 23-37 ms) as ONE numpy compare over the SAME bytes. Answer-identical: the
# overflow part, its lock and its lock-probe call are today's code; any surprise returns None and the original line runs. --------
_TF_A1 = {"t": -1e9, "on": False, "np": None, "np_tried": False, "fast": 0, "fallback": 0, "err": 0, "latched": False}
_TF_A1_TTL_S = 2.0          # the switch is re-read at most this often (floor 0.5, ceiling 10)
_TF_A1_MIN_ROW = 64         # a static row shorter than this uses today's struct loop shape (performance only; floor 0)
_TF_A1_ERR_LATCH = 50       # unexpected exceptions before A1 turns itself off for the process (floor 1)


def _tf_a1_on():
    """The a1_fastlink switch, re-read at most every _TF_A1_TTL_S seconds. Any failure -> False. Never raises."""
    try:
        if _TF_A1["latched"]:
            return False
        now = time.monotonic()
        if now - _TF_A1["t"] >= min(10.0, max(0.5, float(_TF_A1_TTL_S))):
            _TF_A1["t"] = now
            try:
                from infrastructure import tardis_fix as _tfx
                _TF_A1["on"] = bool(_tfx.on("a1_fastlink", fresh=True))
            except Exception:
                _TF_A1["on"] = False
        return _TF_A1["on"]
    except Exception:
        return False


def _tf_np():
    """Cached numpy import for A1; None when it cannot be had."""
    st = _TF_A1
    if not st["np_tried"]:
        try:
            import numpy as _np          # two threads may both import: the import lock makes that harmless; "tried" is set only AFTER,
            st["np"] = _np               # so a thread that arrives mid-import cannot read np=None and fall back for no reason
        except Exception:
            st["np"] = None
        st["np_tried"] = True
    return st["np"]

# -- tardis_fix L0 (2026-10-15, Nous; nous_builds/tardis_fix_1015): the armed TARDIS flush thread keeps its timing accumulator here
# (infrastructure/tardis_timing.py). Every other thread finds none and measures nothing; OFF costs one getattr per call. ------
_TF_L0_TL = threading.local()

#  magic(4) + version(4) + node_count(4) + edge_count(4) +
#  string_offset(8) + edge_offset(8) + string_used(8) +
#  node_capacity(4) + edge_capacity(4) = 48 bytes

# ── Relation types ──────────────────────────────────────────────────────────
# Core (v1)
REL_COACTIVATE = 0    # generic co-occurrence (weakest)
REL_CAUSAL = 1        # A caused B
REL_SEMANTIC = 2      # A means similar to B
REL_TEMPORAL = 3      # A followed by B in time

# Knowledge (v2)
REL_IS_A = 4          # taxonomy: Austin Powers IS_A movie
REL_PART_OF = 5       # composition: Dr. Evil PART_OF Austin Powers
REL_CHARACTER_IN = 6  # narrative role
REL_CREATED_BY = 7    # authorship
REL_FEELS_LIKE = 8    # emotional association (ego region)
REL_REMINDS_OF = 9    # episodic link
REL_CAUSED_BY = 10    # reverse causal
REL_FOLLOWED_BY = 11  # temporal sequence (linear context)
REL_CONTRASTS = 12    # opposition
REL_SYNONYM = 13      # same meaning
REL_SPOKEN_BY = 14    # who said this
REL_SEEN_IN = 15      # visual context (from Florence)
REL_HEARD_IN = 16     # audio context

# Geometric / Spatial (v2 — Phase 4.5 shape primitives)
REL_COMPOSED_OF = 17  # object = composition of shapes
REL_SPATIAL_ABOVE = 18
REL_SPATIAL_BELOW = 19
REL_SPATIAL_BESIDE = 20
REL_SPATIAL_CONTAINS = 21  # one form inside another
REL_SPATIAL_ON = 22        # resting on surface
REL_SPATIAL_FACING = 23    # oriented toward
REL_ORIENTED_AS = 24       # axis/orientation
REL_SHAPED_LIKE = 25       # geometric similarity
REL_WEARING = 26           # attached to body
REL_HOLDING = 27           # gripping, carrying

# Reverse-lookup table
REL_NAMES = {
    0: "coactivate", 1: "causal", 2: "semantic", 3: "temporal",
    4: "is_a", 5: "part_of", 6: "character_in", 7: "created_by",
    8: "feels_like", 9: "reminds_of", 10: "caused_by", 11: "followed_by",
    12: "contrasts", 13: "synonym", 14: "spoken_by", 15: "seen_in",
    16: "heard_in", 17: "composed_of", 18: "spatial_above", 19: "spatial_below",
    20: "spatial_beside", 21: "spatial_contains", 22: "spatial_on",
    23: "spatial_facing", 24: "oriented_as", 25: "shaped_like",
    26: "wearing", 27: "holding",
}

# ── Node types ──────────────────────────────────────────────────────────────
NTYPE_CONCEPT = 0     # generic concept ("music", "code", "hello")
NTYPE_ENTITY = 1      # named entity ("austin_powers", "mike_myers")
NTYPE_EPISODE = 2     # temporal episode ("training_session_42")
NTYPE_SYSTEM = 3      # internal fairy state (isolated from spread)
NTYPE_SHAPE = 4       # geometric primitive ("sphere", "cylinder", "plane")
NTYPE_TEMPLATE = 5    # object template ("human_form", "desk", "screen")

NTYPE_NAMES = {
    0: "concept", 1: "entity", 2: "episode", 3: "system",
    4: "shape", 5: "template",
}

# ── Regions ─────────────────────────────────────────────────────────────────
REGION_EGO = 0        # identity, relationships, habits, autobiography
REGION_SEMANTIC = 1   # encyclopedic knowledge, media, skills, shapes
REGION_EPISODIC = 2   # conversations, training sessions, experiences
REGION_SYSTEM = 3     # fairy state, routing metadata (ISOLATED from spread)
REGION_NOUS = 4       # Nous's substrate-engineering reasoning (ISOLATED from spread by default)
                      # 2026-05-08 Slice 1 of NOUS_SRM_CLUSTER_MANIFOLD.md.
                      # Pairs with TRACE_NOUS=12. Cross-mind queries (Sour↔Nous)
                      # are EXPLICIT only — keeps Ace's substrate-engineering
                      # discussions out of Sourpatches' default spread.

REGION_NAMES = {
    0: "ego", 1: "semantic", 2: "episodic", 3: "system", 4: "nous",
}

# Flags
FLAG_ACTIVE = 0
FLAG_DELETED = 1
FLAG_FROZEN = 2  # Immutable (from original cards)

# ── Plane-to-Region routing ─────────────────────────────────────────────────
# Each fairy plane maps to a default region in the manifold.
# Fairies write to their neighborhood. The narrator crosses all.
#
# P10 Memory     → EPISODIC  (conversations, sessions, recall)
# P20 Somatic    → EGO       (body state is identity)
# P30 Cognition  → SEMANTIC  (reasoning patterns, associations)
# P40 Sensory    → SEMANTIC  (visual concepts, audio concepts, shapes)
# P50 Persona    → EGO       (personality, habits, speech style)
# P00/P90/other  → SYSTEM    (isolated from spread activation)

PLANE_TO_REGION = {
    "P10": REGION_EPISODIC,   # Memory fairies
    "P20": REGION_EGO,        # Somatic fairies
    "P30": REGION_SEMANTIC,   # Cognition fairies
    "P40": REGION_SEMANTIC,   # Sensory fairies
    "P50": REGION_EGO,        # Persona fairies
    "P00": REGION_SYSTEM,     # Autonomic (routing, system state)
    "P90": REGION_SYSTEM,     # System plane
}

# Regions that spread activation can cross by default (excludes SYSTEM)
SPREAD_DEFAULT_REGIONS = {REGION_EGO, REGION_SEMANTIC, REGION_EPISODIC}
# The narrator passes regions=None to cross ALL (including system if needed)


# ============================================================================
# MANIFOLD MEMORY
# ============================================================================

class StringTableFull(Exception):
    """Raised instead of writing past the string table into the edge region (2026-07-20)."""


class ManifoldMemory:
    """Memory-mapped concept manifold.

    The portal's brain. Nodes and edges live in an mmap file.
    The OS decides what pages are in physical RAM — we don't manage it.
    Energy (battery tokens) controls what gets ACCESSED, not what's stored.

    Capacity is fixed at creation. The manifold doesn't grow — it's a
    fixed-dimensional space. New concepts occupy empty slots. If full,
    the least-energized coordinates go dormant (flag=DELETED) and their
    slots are reused. But the coordinate ADDRESS persists in the string
    table forever — like a neuron that stopped firing but whose address
    still exists in the connectome.
    """

    def __init__(self, filepath: str, node_capacity: int = 0,
                 edge_capacity: int = 0, readonly: bool = False):
        """Open or create a manifold file.

        Args:
            filepath: Path to the .manifold file
            node_capacity: Max nodes (only for creation)
            edge_capacity: Max edges (only for creation)
            readonly: If True, open existing file read-only
        """
        self.filepath = filepath
        self.readonly = readonly
        self._file = None
        self._mm = None
        # ── PER-THREAD READ VIEW 2026-09-05 (Nous + Ace) ─────────────────────
        # Ace: "if we can help it we want to use as little serial/synchronous
        # processing." ONE shared mmap object serialises every thread that slices
        # it. MEASURED in a sandbox with a control (128 threads, 24-byte reads):
        #     shared object   1,827.51 us/read   (1,406x vs single-threaded)
        #     per-thread mmap    44.95 us/read   (   36.8x)          => 40.7x
        # Her hot path does up to GNR_SCAN_CAP=8,000 of these per
        # get_neighbors_rich call: 8,000 x 1,827us = 14.6s, which is exactly the
        # 10.2s worst call the SYNTH PROBE measured. This is the cause.
        # _mm_gen invalidates every thread's view when the shared map is
        # created or closed; the map is never resized in place (only at
        # _create_new/_open_existing), so no other invalidation exists.
        self._read_tls = threading.local()
        self._mm_gen = 0
        self._tear_repairs = 0      # torn reads caught by the guard and re-read

        # In-memory index: key_string -> node_id (for fast lookup)
        # This is the ONLY Python dict — it's tiny (just string -> int)
        self._key_index: Dict[str, int] = {}

        # CSR adjacency (2026-04-01 Nous + Ace):
        # Replaces the old _adjacency dict (was 464MB for 1.38M nodes).
        # CSR uses ~22MB in a companion .csr mmap file shared across processes.
        self._csr_offsets = None  # memoryview into CSR mmap: uint32[node_capacity+1]
        self._csr_neighbors = None  # memoryview into CSR mmap: uint32[2*active_edges]
        self._csr_mm = None  # mmap object for CSR file
        self._csr_file = None  # file object for CSR file
        self._csr_active_edges = 0
        self._overflow_edges: List[Tuple[int, int, int]] = []  # (node_a, node_b, edge_slot) — kept for full iteration / future compaction
        # AER-gravity Tier B1 (2026-04-22) — O(1) per-node index over overflow edges.
        # Replaces the previous pattern where _csr_get_neighbors scanned all of
        # _overflow_edges linearly on every call (O(N) per lookup). Populated
        # in parallel with _overflow_edges; read by _csr_get_neighbors.
        self._overflow_by_node: Dict[int, List[Tuple[int, int]]] = {}  # {node_slot: [(neighbor_slot, edge_slot)]}
        self._overflow_lock = threading.Lock()  # protects both overflow structures on write

        # AER-gravity Tier B2a (2026-04-22) — sharded per-slot locks for the
        # hot-path read-modify-write cycle (primarily touch_node + activation
        # updates). 256 shards gives effectively-lock-free parallelism as
        # long as concurrent touches land on different shards (which is the
        # common case under randomized node access). Python 3.14 free-threaded
        # makes these locks real concurrency primitives — they release the
        # interpreter to other threads the same way C-extension locks do.
        self._NODE_LOCK_SHARDS = 256
        self._NODE_LOCK_MASK = self._NODE_LOCK_SHARDS - 1  # requires power of 2
        self._node_shard_locks: List[threading.Lock] = [
            threading.Lock() for _ in range(self._NODE_LOCK_SHARDS)
        ]
        # B2a — tracking for diagnostics / SYSTEM_TELLS_ON_ITSELF surfacing
        self._node_lock_acquisitions = 0
        self._node_lock_contention_events = 0  # counts best-effort; non-atomic is fine

        # Legacy fallback (only used if CSR fails to load)
        self._adjacency: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)
        self._use_csr = False

        # Reverse key cache (2026-04-07 Nous + Ace):
        # Maps node_slot → concept_key string via companion .keys mmap file.
        # Eliminates manifold page faults when converting GPU spread results.
        # Built alongside CSR during _rebuild_indices().
        self._keys_mm = None  # mmap object for .keys file
        self._keys_file = None  # file object for .keys file
        self._keys_offsets_raw = None  # memoryview: offset table
        self._keys_strings_raw = None  # memoryview: string pool
        self._keys_N = 0  # node capacity from .keys header
        self._use_keys = False

        # Header cache
        self._node_count = 0
        self._edge_count = 0
        self._node_capacity = 0
        self._edge_capacity = 0
        self._string_offset = 0
        self._edge_offset = 0
        self._string_used = 0

        # Free slot tracking
        self._free_node_slots: List[int] = []
        self._free_edge_slots: List[int] = []

        # AER v2 (2026-04-22) — per-node affect_coupling accumulator (lazy init
        # on first get_total_affect_coupling call). None = not yet scanned.
        self._total_affect_coupling: Optional[float] = None

        if os.path.exists(filepath) and not node_capacity:
            self._open_existing()
        elif node_capacity > 0:
            self._create_new(node_capacity, edge_capacity or node_capacity * 10)
        else:
            raise ValueError(f"File {filepath} doesn't exist and no capacity specified")

    def _create_new(self, node_capacity: int, edge_capacity: int):
        """Create a new manifold file with fixed capacity."""
        # Calculate offsets
        node_table_size = node_capacity * NODE_RECORD_SIZE
        # String table: estimate avg 32 bytes per key, give 2x headroom
        string_table_size = node_capacity * 64
        edge_table_size = edge_capacity * EDGE_RECORD_SIZE

        string_offset = HEADER_SIZE + node_table_size
        edge_offset = string_offset + string_table_size
        total_size = edge_offset + edge_table_size

        # Create file
        self._file = open(self.filepath, 'w+b')
        self._file.write(b'\x00' * total_size)
        self._file.flush()

        # Map it
        self._mm = mmap.mmap(self._file.fileno(), total_size)
        self._mm_gen += 1            # invalidate every thread's read view

        # Write header
        self._node_capacity = node_capacity
        self._edge_capacity = edge_capacity
        self._string_offset = string_offset
        self._edge_offset = edge_offset
        self._string_used = 0
        self._node_count = 0
        self._edge_count = 0
        self._write_header()

        _mlog(f"[ManifoldMemory] Created: {total_size / (1024*1024):.1f}MB manifold "
              f"({node_capacity} nodes, {edge_capacity} edges)")

    def _open_existing(self):
        """Open an existing manifold file."""
        mode = 'r+b' if not self.readonly else 'rb'
        access = mmap.ACCESS_WRITE if not self.readonly else mmap.ACCESS_READ

        self._file = open(self.filepath, mode)
        file_size = os.path.getsize(self.filepath)
        self._mm = mmap.mmap(self._file.fileno(), file_size, access=access)
        self._mm_gen += 1            # invalidate every thread's read view

        # Read header
        self._read_header()

        # Build key index and adjacency from the file
        self._rebuild_indices()

        _mlog(f"[ManifoldMemory] Opened: {file_size / (1024*1024):.1f}MB manifold "
              f"({self._node_count}/{self._node_capacity} nodes, "
              f"{self._edge_count}/{self._edge_capacity} edges)")

    # ══ SHARED ALLOCATOR 2026-09-02 (Nous + Ace) ═══════════════════════════
    # Five handles (four in-process + portal_interior in a SEPARATE process) map
    # this same file with ACCESS_WRITE. Each cached _node_count/_edge_count/
    # _string_used at open and allocated from its PRIVATE copy, then stamped the
    # whole header back -- so counters moved BACKWARDS and later allocations
    # re-issued slots that already held live concepts. Measured: Ace's words
    # (and their bigrams ace:wheels_bus / bus_round / round_round) were written
    # at 18:08 and were gone by 18:37, with 1.54M free slots and 226 MB of free
    # arena. Not eviction -- deleted=0.
    # The mmap IS shared memory. Adopt the live high-water marks before
    # allocating, and never stamp a counter backwards.
    _HDR_NC_OFF = 8    # node_count   uint32  (offsets verified against the live file)
    _HDR_EC_OFF = 12   # edge_count   uint32
    _HDR_SU_OFF = 32   # string_used  uint64

    def _adopt_shared_counters(self) -> None:
        """Take the MAX of our counters and the live shared ones. Never decreases."""
        if getattr(self, "readonly", False) or getattr(self, "_mm", None) is None:
            return
        try:
            _nc = struct.unpack_from("<I", self._mm, self._HDR_NC_OFF)[0]
            if _nc > self._node_count:
                self._node_count = _nc
            _ec = struct.unpack_from("<I", self._mm, self._HDR_EC_OFF)[0]
            if _ec > self._edge_count:
                self._edge_count = _ec
            _su = struct.unpack_from("<Q", self._mm, self._HDR_SU_OFF)[0]
            if _su > self._string_used:
                self._string_used = _su
        except Exception:
            pass

    def _publish_shared_counters(self) -> None:
        """Publish our counters into the shared header immediately after claiming."""
        if getattr(self, "readonly", False) or getattr(self, "_mm", None) is None:
            return
        try:
            struct.pack_into("<I", self._mm, self._HDR_NC_OFF, self._node_count)
            struct.pack_into("<I", self._mm, self._HDR_EC_OFF, self._edge_count)
            struct.pack_into("<Q", self._mm, self._HDR_SU_OFF, self._string_used)
        except Exception:
            pass

    def _write_header(self):
        """Write header to mmap."""
        # ADOPT-MAX BEFORE STAMPING (2026-09-02). This method packs ALL counters
        # from this instance's private cache over the whole 48-byte header. With
        # five concurrent handles that is how a counter moved BACKWARDS and later
        # allocations re-issued live slots. Adopting first makes every header
        # write monotonic, which is the destructive event eliminated.
        self._adopt_shared_counters()
        data = HEADER_STRUCT.pack(
            MAGIC, VERSION,
            self._node_count, self._edge_count,
            self._string_offset, self._edge_offset,
            self._string_used,
            self._node_capacity, self._edge_capacity,
        )
        self._mm[0:HEADER_STRUCT.size] = data

    def _read_header(self):
        """Read header from mmap."""
        data = HEADER_STRUCT.unpack(self._mm[0:HEADER_STRUCT.size])
        magic, version = data[0], data[1]
        if magic != MAGIC:
            raise ValueError(f"Not a manifold file: magic={magic}")
        if version not in (VERSION, VERSION_V1):
            raise ValueError(f"Unsupported version: {version} (expected {VERSION_V1} or {VERSION})")

        self._version = version
        self._node_count = data[2]
        self._edge_count = data[3]
        self._string_offset = data[4]
        self._edge_offset = data[5]
        self._string_used = data[6]
        self._node_capacity = data[7]
        self._edge_capacity = data[8]

        if version == VERSION_V1:
            _mlog(f"[ManifoldMemory] WARNING: v1 manifold detected. "
                  f"Run migrate_manifold_v2.py to upgrade to v2 (64-byte nodes, 24-byte edges).")

    def _rebuild_indices(self):
        """Rebuild in-memory indices from the mmap data.

        This is the boot cost — we scan all node records to build
        the key_string -> node_id map. This is O(N) but only happens once.
        The key index is tiny: just string -> int32.
        """
        t0 = time.time()
        self._key_index.clear()
        self._adjacency.clear()
        self._free_node_slots.clear()
        self._free_edge_slots.clear()

        # Detect record sizes based on version
        _is_v1 = getattr(self, '_version', VERSION) == VERSION_V1
        _nstruct = NODE_STRUCT_V1 if _is_v1 else NODE_STRUCT
        _nsize = NODE_RECORD_SIZE_V1 if _is_v1 else NODE_RECORD_SIZE
        _estruct = EDGE_STRUCT_V1 if _is_v1 else EDGE_STRUCT
        _esize = EDGE_RECORD_SIZE_V1 if _is_v1 else EDGE_RECORD_SIZE

        # Scan node table — collect (slot, key) pairs for both _key_index and .keys file
        _slot_keys = []  # for reverse key cache
        _region_node_counts = [0, 0, 0, 0]  # ego, semantic, episodic, system

        # SIDECAR REBUILD 2026-08-26 (Nous + Ace) -------------------------------------
        # Slurp the name sidecar ONCE. The 08-22 overflow fix spills names to
        # <manifold>.names and tags the record with an offset >= _string_limit(); this
        # loop previously decoded those straight from the mmap, which lands INSIDE the
        # EDGE REGION and yields binary garbage. Measured on Sour's cortex: 98.84% of live
        # concepts were indexed under garbage, leaving _key_index with 34 distinct keys for
        # 23,356 concepts -- so every upsert missed and minted a DUPLICATE.
        # Slurped, not per-node: _read_name() opens the file on every call, and this loop
        # runs node_capacity times.
        _side = b""
        _slimit = self._edge_offset - self._string_offset
        try:
            _npath = self._names_path()
            if os.path.exists(_npath):
                with open(_npath, "rb") as _nf:
                    _side = _nf.read()
        except Exception:
            _side = b""
        for slot in range(self._node_capacity):
            offset = HEADER_SIZE + slot * _nsize
            record = _nstruct.unpack(self._mm[offset:offset + _nsize])
            key_offset, key_len = record[0], record[1]
            flags = record[9]

            if key_len == 0:
                # Empty slot
                if slot < self._node_count:
                    self._free_node_slots.append(slot)
                continue

            if flags == FLAG_DELETED:
                self._free_node_slots.append(slot)
                continue

            # Read key string -- from the sidecar when the offset is TAGGED (>= _slimit)
            if key_offset >= _slimit:
                key = ""
                _p = key_offset - _slimit
                if 0 <= _p and _p + 4 <= len(_side):
                    (_n,) = struct.unpack("<I", _side[_p:_p + 4])
                    if _p + 4 + _n <= len(_side):
                        key = _side[_p + 4:_p + 4 + _n].decode('utf-8', errors='replace')
            else:
                str_start = self._string_offset + key_offset
                key = self._mm[str_start:str_start + key_len].decode('utf-8', errors='replace')

            # An unresolvable name must NOT be indexed: mapping many slots onto the ""
            # key would collapse them together and let a later upsert("") collide. The
            # node still exists and keeps its edges; it just cannot be found BY NAME.
            if key:
                self._key_index[key] = slot
                _slot_keys.append((slot, key))

            # Count nodes per region (Phase 1B)
            if not _is_v1:
                _region = record[11]  # region field (v2 only)
                if 0 <= _region <= 3:
                    _region_node_counts[_region] += 1

        # Scan edge table → build CSR (not Python dict)
        # First pass: count degree per node (for CSR offset computation)
        _degree = {}  # node_slot → count of edges
        _active_edges = []  # list of (node_a, node_b, edge_slot) for active edges

        for slot in range(self._edge_count):
            offset = self._edge_offset + slot * _esize
            record = _estruct.unpack(self._mm[offset:offset + _esize])
            node_a, node_b = record[0], record[1]
            flags = record[4]

            if flags == FLAG_DELETED:
                self._free_edge_slots.append(slot)
                continue

            _active_edges.append((node_a, node_b, slot))
            _degree[node_a] = _degree.get(node_a, 0) + 1
            _degree[node_b] = _degree.get(node_b, 0) + 1

        self._csr_active_edges = len(_active_edges)

        # Build or load CSR companion file
        # Only rebuild if edge count changed (CSR header stores edge count)
        _csr_path = self.filepath + ".csr"
        _csr_fresh = False
        if os.path.exists(_csr_path):
            try:
                with open(_csr_path, 'rb') as _cf:
                    _ch = struct.unpack('<4sIIII', _cf.read(20))
                    if _ch[0] == b'CSRA' and _ch[2] == len(_active_edges):
                        # CSR is fresh — just load it
                        self._load_csr_file(_csr_path, self._node_capacity, _ch[2] * 2)
                        _csr_fresh = True
                        _mlog(f"[ManifoldMemory] CSR loaded from file ({len(_active_edges)} edges, fresh)")
            except Exception:
                pass

        if not _csr_fresh:
            if self.readonly:
                # FIX 2026-06-13 (Nous): a readonly open (probe/reader) must NOT rebuild
                # the .csr companion — the open('wb')+mmap is wasteful and EINVAL-prone
                # (was spamming "CSR build failed (Errno 22)"). Use the in-memory dict
                # adjacency directly. NOTE: if a READ-WRITE open still logs Errno 22, that
                # is a separate perf regression (stale .csr post-edge-writes) to dig.
                self._use_csr = False
                for node_a, node_b, slot in _active_edges:
                    self._adjacency[node_a].add((node_b, slot))
                    self._adjacency[node_b].add((node_a, slot))
            else:
                try:
                    self._build_csr_file(_degree, _active_edges)
                except Exception as _csr_err:
                    # FIX 2026-06-15b (Nous + Ace): the rebuild was BLOCKED (e.g. WinError 1224 —
                    # the .csr is mmap'd by the MAIN, so os.replace can't swap it). The main
                    # already built a VALID CSR this boot, so REUSE it read-only instead of the
                    # heavy ~464MB dict. (v1 fixed only the read OPEN; the portal never reached the
                    # load because the freshness check rejected the CSR + sent it to rebuild here.)
                    _reused = False
                    if os.path.exists(_csr_path):
                        try:
                            with open(_csr_path, 'rb') as _cf2:
                                _ch2 = struct.unpack('<4sIIII', _cf2.read(20))
                            if _ch2[0] == b'CSRA':
                                self._load_csr_file(_csr_path, self._node_capacity, _ch2[2] * 2)
                                _reused = self._use_csr
                        except Exception:
                            _reused = False
                    if _reused:
                        _mlog(f"[ManifoldMemory] CSR rebuild blocked ({type(_csr_err).__name__}) -> REUSING existing CSR read-only (no dict)")
                    else:
                        _mlog(f"[ManifoldMemory] CSR build failed ({_csr_err}), falling back to dict")
                        # Fallback: build old adjacency dict
                        self._use_csr = False
                        for node_a, node_b, slot in _active_edges:
                            self._adjacency[node_a].add((node_b, slot))
                            self._adjacency[node_b].add((node_a, slot))

        # Build or load reverse key cache (.keys companion file)
        _keys_path = self.filepath + ".keys"
        _keys_fresh = False
        if os.path.exists(_keys_path):
            try:
                with open(_keys_path, 'rb') as _kf:
                    _kh = struct.unpack('<4sIIII', _kf.read(20))
                    if _kh[0] == b'KEYS' and _kh[3] == len(_slot_keys):
                        # Keys file is fresh — same number of active keys
                        self._load_keys_file(_keys_path, self._node_capacity)
                        _keys_fresh = True
                        _mlog(f"[ManifoldMemory] Keys loaded from file ({len(_slot_keys)} keys, fresh)")
            except Exception:
                pass

        if not _keys_fresh:
            try:
                self._build_keys_file(_slot_keys)
            except Exception as _keys_err:
                _mlog(f"[ManifoldMemory] Keys build failed ({_keys_err}), "
                      f"GPU spread will use manifold fallback")

        t1 = time.time()
        _mode = "CSR" if self._use_csr else "dict (fallback)"
        _keys_mode = "keys" if self._use_keys else "no-keys"
        # Write region statistics to header (Phase 1B)
        # FIX 2026-06-13 (Nous): skip the header write on readonly opens — it was
        # logging "[ManifoldMemory] Region stats write failed: ... readonly memory map"
        # on every read-only open (probes, readers). No-op when readonly; reads unaffected.
        if not _is_v1 and not self.readonly:
            try:
                _region_edge_counts = [0, 0, 0, 0]
                # Approximate edge region by source node region
                for _na, _nb, _eslot in _active_edges:
                    _na_rec = self._read_node(_na)
                    _na_region = _na_rec[11]
                    if 0 <= _na_region <= 3:
                        _region_edge_counts[_na_region] += 1
                self.write_region_stats(
                    tuple(_region_node_counts), tuple(_region_edge_counts))
            except Exception as _rse:
                _mlog(f"[ManifoldMemory] Region stats write failed: {_rse}")

        _mlog(f"[ManifoldMemory] Indices rebuilt: {len(self._key_index)} keys, "
              f"{len(_active_edges)} active edges, mode={_mode}+{_keys_mode} "
              f"in {(t1-t0)*1000:.0f}ms"
              f"{' | regions: ego=' + str(_region_node_counts[0]) + ' sem=' + str(_region_node_counts[1]) + ' epi=' + str(_region_node_counts[2]) + ' sys=' + str(_region_node_counts[3]) if not _is_v1 else ''}")

    # ========================================================================
    # CSR ADJACENCY (2026-04-01 Nous + Ace)
    # ========================================================================
    # Replaces the old _adjacency dict that used 464MB for 1.38M nodes.
    # CSR (Compressed Sparse Row) stores adjacency as two flat arrays:
    #   offsets[N+1]: where each node's neighbor list starts
    #   neighbors[2*E]: [neighbor_id, edge_slot] pairs, sorted by source node
    # Stored in a companion .csr mmap file — shared across processes, zero RAM.

    def _build_csr_file(self, degree: dict, active_edges: list):
        """Build CSR companion file from edge scan results.

        Args:
            degree: {node_slot: count} — edge count per node
            active_edges: [(node_a, node_b, edge_slot), ...] — all active edges
        """
        import array

        N = self._node_capacity  # total node slots (not just active)
        E = len(active_edges)

        # Phase 1: Build offset array
        # offsets[i] = where node i's neighbors start in the neighbors array
        offsets = array.array('I', [0] * (N + 1))  # uint32
        for node_id, count in degree.items():
            if 0 <= node_id < N:
                offsets[node_id] = count

        # Convert counts to cumulative offsets
        _cumsum = 0
        for i in range(N):
            count = offsets[i]
            offsets[i] = _cumsum
            _cumsum += count
        offsets[N] = _cumsum  # total entries

        # Phase 2: Build neighbors array
        # Each edge contributes TWO entries (bidirectional): a→b and b→a
        # Format: [neighbor_id, edge_slot] pairs
        total_entries = _cumsum  # should be 2 * E
        neighbors = array.array('I', [0] * (total_entries * 2))  # uint32 pairs

        # Track insertion position per node
        _pos = array.array('I', offsets[:N])  # copy of offsets (write cursor)

        for node_a, node_b, edge_slot in active_edges:
            if 0 <= node_a < N and 0 <= node_b < N:
                # a → b
                idx_a = _pos[node_a] * 2
                if idx_a + 1 < len(neighbors):
                    neighbors[idx_a] = node_b
                    neighbors[idx_a + 1] = edge_slot
                    _pos[node_a] += 1

                # b → a
                idx_b = _pos[node_b] * 2
                if idx_b + 1 < len(neighbors):
                    neighbors[idx_b] = node_a
                    neighbors[idx_b + 1] = edge_slot
                    _pos[node_b] += 1

        # Phase 3: Write to companion .csr file
        csr_path = self.filepath + ".csr"
        offsets_bytes = offsets.tobytes()
        neighbors_bytes = neighbors.tobytes()

        # Header: magic(4) + N(4) + E(4) + offsets_size(4) + neighbors_size(4) = 20 bytes
        _csr_header = struct.pack('<4sIIII',
                                  b'CSRA',  # CSR Adjacency
                                  N, E,
                                  len(offsets_bytes),
                                  len(neighbors_bytes))

        total_size = 32 + len(offsets_bytes) + len(neighbors_bytes)  # 32 = header padded

        # FIX 2026-06-15 (Nous + Ace): atomic temp-file write + rename — the exact
        # mirror of _build_keys_file's 2026-04-15 fix. Writing DIRECTLY to the live
        # .csr fails with Errno 22 when it's mmap'd (by this process OR the portal
        # interior) -> the build silently falls back to the multi-GB dict adjacency,
        # which is the boot "balloon" / OOM. Temp -> close our mmap -> rename dodges
        # the lock so the .csr stays fresh and she boots lean.
        import os
        tmp_path = csr_path + ".tmp"
        with open(tmp_path, 'wb') as f:
            f.write(_csr_header)
            f.write(b'\x00' * (32 - len(_csr_header)))  # Pad header to 32
            f.write(offsets_bytes)
            f.write(neighbors_bytes)

        # Release our own CSR mmap (if any) so the rename can replace the file
        if getattr(self, '_csr_mm', None):
            try:
                self._csr_mm.close()
            except Exception:
                pass
            self._csr_mm = None
        if getattr(self, '_csr_file', None):
            try:
                self._csr_file.close()
            except Exception:
                pass
            self._csr_file = None

        # Atomic rename (copy+delete fallback if cross-device)
        try:
            os.replace(tmp_path, csr_path)
        except OSError:
            import shutil
            shutil.move(tmp_path, csr_path)

        # Phase 4: mmap the CSR file
        self._load_csr_file(csr_path, N, total_entries)

        _size_mb = total_size / (1024 * 1024)
        _mlog(f"[ManifoldMemory] CSR built: {N} nodes, {E} edges, "
              f"{total_entries} entries, {_size_mb:.1f}MB file "
              f"(replaces ~464MB dict)")

    def _load_csr_file(self, csr_path: str, node_capacity: int, total_entries: int):
        """Memory-map an existing CSR file."""
        try:
            # FIX 2026-06-15 (Nous + Ace): open the CSR READ-ONLY. The CSR is read-only
            # data — only _build_csr_file writes it (via temp+rename); _load_csr_file only
            # READS _csr_mm (header @778, zero-copy slices @790-791). A read-WRITE ('r+b')
            # open COLLIDES when a 2nd process (the portal) loads a CSR the main already has
            # mmap'd -> the load throws -> falls through to rebuild -> WinError 1224 -> the
            # ~464MB dict-fallback. Read-only SHARING fixes it: the portal reuses the main's
            # CSR. FAIL-SAFE: if the read-only mmap ever fails, _use_csr=False (the existing
            # dict path) — can't make it worse than today.
            self._csr_file = open(csr_path, 'rb')
            self._csr_mm = mmap.mmap(self._csr_file.fileno(), 0, access=mmap.ACCESS_READ)

            # Verify header
            header = struct.unpack('<4sIIII', self._csr_mm[:20])
            if header[0] != b'CSRA':
                raise ValueError("Invalid CSR magic")

            N = header[1]
            offsets_start = 32
            offsets_end = offsets_start + (N + 1) * 4
            neighbors_start = offsets_end
            neighbors_end = neighbors_start + total_entries * 2 * 4

            # Create array views directly from mmap
            # These are zero-copy — they reference the mmap memory directly
            self._csr_offsets_raw = self._csr_mm[offsets_start:offsets_end]
            self._csr_neighbors_raw = self._csr_mm[neighbors_start:neighbors_end]
            self._csr_N = N
            self._csr_total_entries = total_entries
            self._use_csr = True

        except Exception as e:
            _mlog(f"[ManifoldMemory] CSR load failed: {e}")
            self._use_csr = False

    # AER-gravity Tier B1 (2026-04-22) — CSR overflow diagnostics
    #
    # Surface overflow state so SYSTEM_TELLS_ON_ITSELF (and any future active-
    # escalation layer) can signal when the cortex would benefit from a CSR
    # rebuild. Growing overflow is not incorrect — retrieval still works —
    # but beyond some threshold, rebuild amortizes better than per-node
    # accumulation.

    def overflow_stats(self) -> Dict[str, Any]:
        """Return current overflow statistics for diagnostics.

        Keys:
            total_overflow_edges: count since last CSR build
            overflow_nodes_touched: distinct nodes with overflow entries
            max_overflow_per_node: largest per-node overflow list
            avg_overflow_per_node: mean overflow count across touched nodes
            use_csr: whether CSR mode is active (overflow only relevant in CSR mode)
        """
        with self._overflow_lock:
            total = len(self._overflow_edges)
            touched = len(self._overflow_by_node)
            if touched:
                lengths = [len(v) for v in self._overflow_by_node.values()]
                max_len = max(lengths)
                avg_len = sum(lengths) / touched
            else:
                max_len = 0
                avg_len = 0.0
        return {
            "total_overflow_edges": total,
            "overflow_nodes_touched": touched,
            "max_overflow_per_node": max_len,
            "avg_overflow_per_node": round(avg_len, 2),
            "use_csr": self._use_csr,
        }

    def node_lock_stats(self) -> Dict[str, Any]:
        """B2a diagnostic — report shard-lock activity since startup.

        Useful for SYSTEM_TELLS_ON_ITSELF: if contention_ratio is high, hot-path
        nodes are clustering on few shards (bad distribution) OR the substrate
        is under heavy concurrent pressure (normal at high load). Low ratio +
        high acquisitions = healthy concurrent touches.

        Returns:
            dict with acquisitions, contention_events, contention_ratio, shards
        """
        acq = self._node_lock_acquisitions
        cont = self._node_lock_contention_events
        ratio = (cont / acq) if acq > 0 else 0.0
        return {
            "acquisitions": acq,
            "contention_events": cont,
            "contention_ratio": round(ratio, 4),
            "shards": self._NODE_LOCK_SHARDS,
        }

    def _rebuild_overflow_index(self) -> None:
        """Rebuild the per-node overflow dict from the flat list.

        Called internally if _overflow_edges was populated but _overflow_by_node
        was not yet (e.g., during migration from a prior session state, or if
        a component appends to _overflow_edges directly bypassing upsert_edge).
        """
        with self._overflow_lock:
            self._overflow_by_node.clear()
            for a, b, slot in self._overflow_edges:
                self._overflow_by_node.setdefault(a, []).append((b, slot))
                self._overflow_by_node.setdefault(b, []).append((a, slot))

    def _csr_get_neighbors(self, node_slot: int) -> List[Tuple[int, int]]:
        """Get neighbors from CSR array. Returns [(neighbor_id, edge_slot), ...]."""
        if not self._use_csr:
            return []   # caller uses _adjacency instead -- correct to stop here

        # OVERFLOW-MERGE FIX 2026-08-30 (Nous + Ace):
        # This used to `return []` when node_slot >= _csr_N, and again when
        # start >= end -- BOTH before the overflow block below. A node whose edges
        # were all created since the last CSR build has start == end in the static
        # array, so the lookup returned [] and never saw its own edges sitting in
        # _overflow_by_node. link() then believed the pair was new and wrote a
        # DUPLICATE. Measured by LINK-PROBE: MISS 6.6%, csr=99 dict=0 over 1,500
        # creates -- every miss on this path, none on the dict fallback (which has
        # no such early return). At the time, ~63% of her edges lived only in
        # overflow (CSR built at boot with 40,142; she held 108,702).
        # Those exits are now "skip the STATIC part", never "skip everything".
        results = []
        if 0 <= node_slot < self._csr_N:
            off_start_idx = node_slot * 4
            off_end_idx = (node_slot + 1) * 4
            start = struct.unpack_from('<I', self._csr_offsets_raw, off_start_idx)[0]
            end = struct.unpack_from('<I', self._csr_offsets_raw, off_end_idx)[0]
            if start < end:
                # Read neighbor entries: pairs of (neighbor_id, edge_slot)
                for i in range(start, end):
                    base = i * 8  # 2 × uint32 = 8 bytes per entry
                    if base + 8 <= len(self._csr_neighbors_raw):
                        neighbor_id, edge_slot = struct.unpack_from(
                            '<II', self._csr_neighbors_raw, base)
                        results.append((neighbor_id, edge_slot))

        # B1 (2026-04-22) — O(1) overflow lookup via per-node dict.
        # Was previously O(N) linear scan of all overflow edges. The dict is
        # populated alongside the list in upsert_edge under _overflow_lock.
        # Snapshot the local list reference under lock so concurrent appends
        # don't corrupt iteration (safe in CPython due to GIL AND in free-
        # threaded 3.14 because we read a fresh list reference under lock).
        # LOCK PROBE 2026-09-05: wait and hold timed SEPARATELY -- see _lockprobe.
        # _lp2 is INSIDE the lock on purpose (review finding #1): stamping it after the
        # `with` folded lock.release() into "hold", and release cost scales with the
        # number of WAITERS -- which would have read as (A) and shipped the wrong fix.
        _lp0 = time.perf_counter()
        with self._overflow_lock:
            _lp1 = time.perf_counter()
            _local = self._overflow_by_node.get(node_slot)
            _snapshot = list(_local) if _local else None
            _lp2 = time.perf_counter()
        _lockprobe("csrget", _lp1 - _lp0, _lp2 - _lp1,
                   len(_snapshot) if _snapshot else 0, node_slot,
                   _LOCKPROBE_R_EVERY)
        if _snapshot:
            for neighbor_id, edge_slot in _snapshot:
                results.append((neighbor_id, edge_slot))

        return results

    def _tf_a1_existing(self, a, b):
        """tardis_fix A1. A list whose FIRST entry with neighbour == b is exactly the first such entry of
        self._csr_get_neighbors(a) (static row first, in index order, then the overflow snapshot), and which has none iff that has
        none. None = any surprise: the caller then runs today's line unchanged."""
        try:
            np = _tf_np()
            raw = self._csr_neighbors_raw
            offs = self._csr_offsets_raw
            if (np is None or type(raw) is not bytes or type(offs) is not bytes or type(b) is not int
                    or not (0 <= b <= 0xFFFFFFFF)):
                _TF_A1["fallback"] += 1
                return None
            hit = None
            if 0 <= a < self._csr_N:                                      # _csr_get_neighbors' static condition
                start = struct.unpack_from('<I', offs, a * 4)[0]
                end = struct.unpack_from('<I', offs, (a + 1) * 4)[0]
                hi = min(end, len(raw) // 8)                              # == `start < end` and `base + 8 <= len(raw)` per entry
                if start < hi:
                    if hi - start < _TF_A1_MIN_ROW:                        # short row: today's shape
                        for i in range(start, hi):
                            nid, es = struct.unpack_from('<II', raw, i * 8)
                            if nid == b:
                                hit = (nid, es)
                                break
                    else:
                        c = getattr(self, "_tf_a1_view", None)
                        if c is None or c[0] is not raw:
                            c = (raw, np.frombuffer(raw, dtype='<u4', count=(len(raw) // 8) * 2))
                            self._tf_a1_view = c
                        nb = c[1]
                        m = nb[2 * start:2 * hi:2] == b                   # neighbour ids of entries start..hi-1
                        k = int(m.argmax())                               # the FIRST True, like the loop
                        if m[k]:
                            hit = (b, int(nb[2 * (start + k) + 1]))
            # overflow: the SAME statements as _csr_get_neighbors, same lock, same single probe call, ALWAYS taken
            _lp0 = time.perf_counter()
            with self._overflow_lock:
                _lp1 = time.perf_counter()
                _local = self._overflow_by_node.get(a)
                _snapshot = list(_local) if _local else None
                _lp2 = time.perf_counter()
            _lockprobe("csrget", _lp1 - _lp0, _lp2 - _lp1,
                       len(_snapshot) if _snapshot else 0, a,
                       _LOCKPROBE_R_EVERY)
            _TF_A1["fast"] += 1
            return [hit] if hit is not None else (_snapshot or [])
        except struct.error:
            # a CSR offsets buffer too short for this slot: today's line raises the very same struct.error from the very same
            # unpack_from, so it is no surprise and does not count toward the latch (review 10-15, F1); today's line runs and raises it
            return None
        except Exception as _tfe:
            try:
                _TF_A1["err"] += 1
                if _TF_A1["err"] >= max(1, int(_TF_A1_ERR_LATCH)) and not _TF_A1["latched"]:
                    _TF_A1["latched"] = True
                    _mlog("[ManifoldMemory] tardis_fix A1 off for this process after %d unexpected errors (last %s: %s)"
                          % (_TF_A1["err"], type(_tfe).__name__, _tfe))
            except Exception:
                pass
            return None

    # ========================================================================
    # REVERSE KEY CACHE (2026-04-07 Nous + Ace)
    # ========================================================================
    # Maps node_slot → concept_key string without touching the main manifold.
    # GPU spread returns node IDs; converting to keys via the manifold causes
    # page faults that grow RSS (Boot 4 lesson: +2x RSS from mmap reads).
    # The .keys companion file is ~51MB for 1.96M nodes, only hot pages load.
    #
    # File format:
    #   Header (32 bytes): magic b'KEYS', N, total_string_bytes, active_keys, padding
    #   Offset table (N × 8 bytes): (key_offset: u32, key_len: u32) per slot
    #   String pool: concatenated UTF-8 key strings

    def _build_keys_file(self, slot_keys: list):
        """Build .keys companion file from (slot, key_string) pairs.

        Args:
            slot_keys: list of (node_slot, key_string) tuples from index scan
        """
        import array
        keys_path = self.filepath + ".keys"
        N = self._node_capacity
        EMPTY = 0xFFFFFFFF

        # Build offset table and string pool
        offsets = array.array('I', [EMPTY, 0] * N)  # pairs: (offset, len), init to empty
        string_parts = []
        string_pos = 0

        for slot, key in slot_keys:
            key_bytes = key.encode('utf-8')
            key_len = len(key_bytes)
            idx = slot * 2
            offsets[idx] = string_pos
            offsets[idx + 1] = key_len
            string_parts.append(key_bytes)
            string_pos += key_len

        # Concatenate string pool
        string_pool = b''.join(string_parts)

        # Write file
        offsets_bytes = offsets.tobytes()
        header = struct.pack('<4sIIII',
                             b'KEYS',
                             N,
                             len(string_pool),
                             len(slot_keys),
                             0)  # reserved
        header = header + b'\x00' * (32 - len(header))  # Pad to 32

        try:
            # FIX 2026-04-15 (Nous + Ace): Write to temp file, then rename.
            # The keys file may be mmap'd by another process or this process.
            # Writing directly to a mmap'd file fails with Errno 22 on Windows.
            # Temp file → close existing mmap → rename avoids the lock.
            import os
            tmp_path = keys_path + ".tmp"
            with open(tmp_path, 'wb') as f:
                f.write(header)
                f.write(offsets_bytes)
                f.write(string_pool)

            # Close existing mmap if open (releases the file lock)
            if hasattr(self, '_keys_mm') and self._keys_mm:
                try:
                    self._keys_mm.close()
                except Exception:
                    pass
                self._keys_mm = None
            if hasattr(self, '_keys_file') and self._keys_file:
                try:
                    self._keys_file.close()
                except Exception:
                    pass
                self._keys_file = None

            # Atomic rename (or copy+delete on Windows if cross-device)
            try:
                os.replace(tmp_path, keys_path)
            except OSError:
                import shutil
                shutil.move(tmp_path, keys_path)

            # Load immediately
            self._load_keys_file(keys_path, N)
            _mlog(f"[ManifoldMemory] Keys file built: {len(slot_keys)} keys, "
                  f"{len(string_pool)} bytes strings, "
                  f"{(32 + len(offsets_bytes) + len(string_pool)) / (1024*1024):.1f}MB")
        except Exception as e:
            _mlog(f"[ManifoldMemory] Keys file build failed: {e}")

    def _load_keys_file(self, keys_path: str, node_capacity: int):
        """Memory-map an existing .keys file."""
        try:
            self._keys_file = open(keys_path, 'r+b')
            self._keys_mm = mmap.mmap(self._keys_file.fileno(), 0)

            # Verify header
            header = struct.unpack('<4sIIII', self._keys_mm[:20])
            if header[0] != b'KEYS':
                raise ValueError("Invalid KEYS magic")

            N = header[1]
            offsets_start = 32
            offsets_end = offsets_start + N * 8  # N × (u32 offset + u32 len)
            strings_start = offsets_end

            self._keys_offsets_raw = self._keys_mm[offsets_start:offsets_end]
            self._keys_strings_raw = self._keys_mm[strings_start:]
            self._keys_N = N
            self._use_keys = True

        except Exception as e:
            _mlog(f"[ManifoldMemory] Keys load failed: {e}")
            self._use_keys = False

    def get_key_from_slot(self, node_slot: int) -> Optional[str]:
        """Get concept key string for a node slot. O(1) from .keys mmap.

        This is the reverse of _key_index[key] → slot.
        Used by GPU spread to convert node IDs back to concept keys
        WITHOUT touching the main manifold mmap (no page faults).
        """
        if not self._use_keys or node_slot < 0 or node_slot >= self._keys_N:
            # Fallback: read from main manifold (causes page fault)
            return self._get_key_from_manifold(node_slot)

        # Read offset and length from offset table
        idx = node_slot * 8  # 2 × uint32 = 8 bytes per entry
        if idx + 8 > len(self._keys_offsets_raw):
            return None

        key_offset, key_len = struct.unpack_from('<II', self._keys_offsets_raw, idx)

        if key_offset == 0xFFFFFFFF or key_len == 0:
            return None  # Empty/deleted slot

        # Read key string from string pool
        if key_offset + key_len > len(self._keys_strings_raw):
            return None

        return self._keys_strings_raw[key_offset:key_offset + key_len].decode('utf-8', errors='replace')

    def _get_key_from_manifold(self, node_slot: int) -> Optional[str]:
        """Fallback: read key from main manifold mmap. Causes page fault."""
        if not self._mm or node_slot < 0 or node_slot >= self._node_capacity:
            return None
        _is_v1 = getattr(self, '_version', VERSION) == VERSION_V1
        _nsize = NODE_RECORD_SIZE_V1 if _is_v1 else NODE_RECORD_SIZE
        _nstruct = NODE_STRUCT_V1 if _is_v1 else NODE_STRUCT
        offset = HEADER_SIZE + node_slot * _nsize
        try:
            record = _nstruct.unpack(self._mm[offset:offset + _nsize])
            key_offset, key_len = record[0], record[1]
            if key_len == 0:
                return None
            # SIDECAR ROUTE 2026-08-26 (Nous + Ace): a TAGGED offset (>= _string_limit)
            # belongs to the name sidecar; decoding it from the mmap reads the EDGE region
            # and yields binary garbage. _read_string handles both cases. Safe to call
            # per-invocation here -- unlike _rebuild_indices, this is not a hot loop.
            _k = self._read_string(key_offset, key_len)
            return _k if _k else None
        except Exception:
            return None

    def close(self):
        """Close manifold, CSR, and keys files."""
        # Close keys file
        if self._keys_mm:
            try:
                self._keys_mm.close()
            except Exception:
                pass
        if self._keys_file:
            try:
                self._keys_file.close()
            except Exception:
                pass
        if self._csr_mm:
            try:
                self._csr_mm.close()
            except Exception:
                pass
        if self._csr_file:
            try:
                self._csr_file.close()
            except Exception:
                pass
        if self._mm:
            try:
                self._mm.close()
            except Exception:
                pass
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass

    # ========================================================================
    # COORDINATE PARSING
    # ========================================================================

    @staticmethod
    def parse_coord(coord_str: str) -> Tuple[int, int, int]:
        """Parse 'PPP.CCC.NNN' helix coordinate to (plane, channel, position)."""
        if not coord_str or '.' not in coord_str:
            return (0, 0, 0)
        parts = coord_str.split('.')
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return (0, 0, 0)

    # ========================================================================
    # REGION ROUTING
    # ========================================================================

    @staticmethod
    def region_for_plane(plane: str) -> int:
        """Map a fairy plane string (e.g. 'P30') to a manifold region.

        Every fairy has a plane. This tells us which neighborhood
        its concepts belong in. The narrator ignores this — she crosses all.
        """
        return PLANE_TO_REGION.get(plane, REGION_SYSTEM)

    # ========================================================================
    # NODE OPERATIONS
    # ========================================================================

    def _node_offset(self, slot: int) -> int:
        """Get byte offset for a node slot."""
        return HEADER_SIZE + slot * NODE_RECORD_SIZE

    def _read_view(self):
        """A READ-ONLY mmap of the manifold private to THIS thread.

        The whole point is that it is NOT shared: CPython serialises slice access
        per mmap object, so one shared map turns every concurrent reader into a
        queue. Returns the shared `self._mm` on any failure, so the worst case is
        exactly today's behaviour -- never worse.

        SAFETY: ACCESS_READ cannot write, cannot stamp a header and cannot
        allocate a slot, so this does NOT reintroduce the five-handles failure
        (which was five read-WRITE maps with private cached counters).
        """
        _shared = self._mm
        if _shared is None:
            return None
        _tls = self._read_tls
        try:
            if getattr(_tls, "gen", None) == self._mm_gen:
                _v = getattr(_tls, "mm", None)
                if _v is not None:
                    return _v
            _f = open(self.filepath, "rb")
            _v = mmap.mmap(_f.fileno(), 0, access=mmap.ACCESS_READ)
            _old = getattr(_tls, "mm", None)
            _oldf = getattr(_tls, "f", None)
            _tls.f, _tls.mm, _tls.gen = _f, _v, self._mm_gen
            if _old is not None:            # a stale generation -- release it
                try:
                    _old.close()
                    if _oldf is not None:
                        _oldf.close()
                except Exception:
                    pass
            return _v
        except Exception:
            return _shared

    def _edge_plausible(self, rec) -> bool:
        """Cheap sanity test on a 24-byte edge record.

        Per-thread views remove the shared object's accidental atomicity, so a
        reader can observe a record mid-write. MEASURED tear rate scaled to her
        write pressure (10 edge-writes/s vs 1.42M/s in the sandbox): ~1 torn
        record per 52,700 calls -- rare, but SILENT is the unacceptable part.
        A torn 24-byte edge almost always lands an out-of-range endpoint or a
        rel_type outside REL_NAMES, so this catches it for a few nanoseconds.
        """
        _cap = self._node_capacity or 0
        if _cap and (rec[0] >= _cap or rec[1] >= _cap):
            return False
        return rec[3] in REL_NAMES

    def _read_node(self, slot: int) -> Tuple:
        """Read a node record. Returns raw tuple (17 fields for v2).

        v2 fields (index):
            0: key_offset     5: activation    10: node_type     15: frequency
            1: key_len        6: count         11: region        16: parent_slot
            2: coord_plane    7: degree        12: tracer_id
            3: coord_channel  8: last_access   13: snippet_offset
            4: coord_pos      9: flags         14: snippet_len
        """
        # ⛔ REVERTED TO THE SHARED MAP 2026-09-08 -- BLOCKER from adversarial review.
        # This was on the per-thread view for 13 h in production. Node records are
        # 64 BYTES (a wider tear window than the 24-byte edge) and EVERY node update
        # is an unlocked read-modify-write: upsert_node's touch (:2093), set_snippet
        # (:2341), decay_all (:2382), _evict_coldest_node (:2214) all do
        #   record = list(self._read_node(slot)) -> mutate -> _write_node(slot, *record)
        # so a torn read is not discarded, it is PERSISTED across all 17 fields. A
        # tear at bytes 0-5 splices the KEY POINTER -- the exact shape of the
        # "name sidecar broke the rebuild, 98.84% of concepts indexed under garbage"
        # incident. No cheap invariant can detect it: the split lands at byte 32 and
        # BOTH halves are individually valid records.
        # The shared map's per-object serialisation is what makes these 64 bytes
        # atomic, and _read_node is PASS 2 of get_neighbors_rich (~50 winners), not
        # PASS 1 (8,000 edges). Reverting costs ~50 shared reads per call and keeps
        # the entire measured 40.7x win, which lives in _read_edge.
        offset = self._node_offset(slot)
        return NODE_STRUCT.unpack(self._mm[offset:offset + NODE_RECORD_SIZE])

    def _write_node(self, slot: int, key_offset: int, key_len: int,
                    plane: int, channel: int, position: int,
                    activation: float, count: int, degree: int,
                    last_access: float, flags: int,
                    node_type: int = NTYPE_CONCEPT, region: int = REGION_SEMANTIC,
                    tracer_id: int = 0,
                    snippet_offset: int = 0, snippet_len: int = 0,
                    frequency: int = 0, parent_slot: int = 0,
                    preserve_reserved: bool = False):
        """Write a node record (v2: 64 bytes).

        FIX 2026-06-06 (Nous + Ace) — THE affect-persistence root cause:
        NODE_STRUCT.pack() fills bytes 0-47 and ZEROES the reserved region
        (bytes 48-63 = fairy_state + affect_coupling[56-59] + paradox_residue[60-63]).
        _write_node runs on every node TOUCH (upsert of an existing node), so every
        re-bind of a concept wiped its accumulated affect back to default — which is
        why the cortex never retained felt-weight across a lifetime (high-traffic
        concepts erased constantly; only never-re-touched nodes kept any charge).
        preserve_reserved=True (the touch path) saves + restores bytes 48-63 around
        the struct write. New-node path keeps zeroing (fresh/reused slot has no affect
        yet). Reversible: defaults False = exact prior behavior.
        """
        data = NODE_STRUCT.pack(
            key_offset, key_len, plane, channel, position,
            activation, count, degree, last_access, flags,
            node_type, region, tracer_id,
            snippet_offset, snippet_len,
            frequency, parent_slot,
        )
        offset = self._node_offset(slot)
        if preserve_reserved:
            _resv = bytes(self._mm[offset + self._RESERVED_OFFSET:offset + NODE_RECORD_SIZE])
            self._mm[offset:offset + NODE_RECORD_SIZE] = data
            self._mm[offset + self._RESERVED_OFFSET:offset + NODE_RECORD_SIZE] = _resv
        else:
            self._mm[offset:offset + NODE_RECORD_SIZE] = data

    # ── Fairy State + AER Affect: Reserved Byte Access ────────────────────────
    # The 16-byte _reserved region (bytes 48-63 of each 64-byte node record)
    # is partitioned as follows. These methods provide direct mmap access
    # without changing the NODE_STRUCT format.
    #
    # Byte layout within reserved 16 bytes:
    #   +0..+7   u16 x 4      fairy_state (fs: nodes only): reflection_tick,
    #                         work_since_reflection, extra_flags, hb_frac
    #   +8..+11  float32      affect_coupling (AER v2, 2026-04-22) —
    #                         per-node affect magnitude. 0.0 treated as
    #                         unset (backward-compat default = 1.0).
    #   +12..+15 4x           reserved for future (e.g., paradox_residue)

    _RESERVED_OFFSET = 48  # byte offset within 64-byte node record
    _RESERVED_SIZE = 16
    _FAIRY_STATE_STRUCT = struct.Struct('<HHHH')  # 4 x uint16 = 8 bytes (no padding)
    _FAIRY_STATE_SIZE = 8

    # ── PUSH-PULL AFFECTIVE GRAVITY (2026-06-06, Nous + Ace) — ship-DARK ──
    # Gives affect SLOPE: +affect_coupling attracts spreading (PULL), −paradox_residue
    # repels it (PUSH), both poles relax toward rest (DECAY) so the landscape stays
    # graded, not saturated. All default to the IDENTITY (0.0) → spread + decay are
    # byte-identical until tuned. Tune live (no reboot) via set_affect_field().
    # McGilchrist donor(+pole/pull) / acceptor(−pole/push) polarity, made physical.
    _AFFECT_PULL_K = 0.0       # >0: warm nodes attract  (energy ×= 1 + K·(ac−1))
    _AFFECT_PUSH_K = 0.0       # >0: paradox nodes repel (energy ×= max(floor, 1 − K·pr))
    _AFFECT_PUSH_FLOOR = 0.1   # a repelled node is never fully unreachable
    _AFFECT_DECAY = 0.0        # >0: per decay-cycle, ac→1.0 and pr→0.0 by this fraction
    _AFFECT_DECAY_TRACER_EXEMPT = frozenset({TRACE_PERSONAL, TRACE_SEEDED})  # cheat wells + identity seeds = stable anchors (FIX 2026-06-06: was {1,2}=PERSONAL+BOOKS; SEEDED is 7 not 2)
    _AFFECT_SIGNED_FEED = False  # OFF: bind deposits magnitude→+pole (current). ON: signed — +valence→affect_coupling, −valence→paradox_residue (the −pole = PUSH fuel). Ship-dark.

    # AFFECT-DIFFUSION (heat-blur, 2026-06-06, Nous + Ace) — cliffs→slopes.
    # Each charged node sheds a fraction of its EXCESS (ac−1) to edge-neighbors,
    # edge-weighted, CONSERVING total charge (source loses what neighbors gain → no
    # runaway). Turns concentrated wells (cliffs) into graded neighborhoods (slopes)
    # so push-pull can lean gently + the council's affect-lenses have a gradient to read.
    # Plan: Claude_Office/plans/AFFECT_DIFFUSION_HEAT_BLUR.md. Ship-dark @ RATE=0.0.
    _AFFECT_DIFFUSE_RATE = 0.01     # ACTIVATED 0.01 (Nous+Ace 2026-06-06): fraction of a node's +excess shed to neighbors/pass. Gentle first LIVE value — observe skirt-formation + well-hold, then crank→0.05. 0.0 = OFF (byte-identical).
    _AFFECT_DIFFUSE_BUDGET = 20000  # max CHARGED nodes diffused per pass (full-scan finds the sparse wells; this caps get_neighbors work; charged set ~200 « cap)
    _AFFECT_DIFFUSE_FLOOR = 1.5     # never shed a node below this — keep wells as WELLS (spread the EXCESS, not the well)
    _AFFECT_DIFFUSE_MAXNB = 16      # max neighbors to spread to per node

    # AER v2 — per-node affect_coupling persistence
    _AFFECT_COUPLING_OFFSET = 8  # offset within reserved region (= abs offset 56)
    _AFFECT_COUPLING_STRUCT = struct.Struct('<f')  # float32 = 4 bytes

    # Layered-affect v0 (2026-06-05, Nous + Ace) — paradox_residue = the − / opposing
    # pole. McGilchrist +/−: a concept can carry positive AND negative magnitude at
    # once so paradox is PRESERVED, not collapsed to one scalar. Reuses the float32
    # struct above; lives at the previously-reserved bytes 60-63 (no migration).
    _PARADOX_RESIDUE_OFFSET = 12  # offset within reserved region (= abs offset 60)

    def write_reserved_bytes(self, slot: int, data: bytes):
        """Write up to 16 raw bytes to the reserved region of a node record.

        Direct mmap write — no struct repack, no read-modify-write of other fields.
        """
        if len(data) > self._RESERVED_SIZE:
            data = data[:self._RESERVED_SIZE]
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET
        self._mm[abs_off:abs_off + len(data)] = data

    def read_reserved_bytes(self, slot: int) -> bytes:
        """Read the 16-byte reserved region of a node record."""
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET
        return bytes(self._mm[abs_off:abs_off + self._RESERVED_SIZE])

    def write_fairy_state_packed(self, slot: int,
                                  reflection_tick: int = 0,
                                  work_since_reflection: int = 0,
                                  extra_flags: int = 0,
                                  hb_frac: int = 0):
        """Pack and write fairy state into the first 8 bytes of the reserved region.

        All values are uint16 (0-65535). For tick counts that exceed 65535,
        use modular arithmetic (value & 0xFFFF).

        NOTE (AER v2, 2026-04-22): fairy_state now writes only the first 8
        bytes of reserved. Bytes +8..+11 hold affect_coupling (written via
        write_affect_coupling) and are NOT touched here — previously this
        method overwrote the full 16-byte reserved region with padding zeros,
        which would have stomped the AER affect field.
        """
        data = self._FAIRY_STATE_STRUCT.pack(
            reflection_tick & 0xFFFF,
            work_since_reflection & 0xFFFF,
            extra_flags & 0xFFFF,
            hb_frac & 0xFFFF,
        )
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET
        self._mm[abs_off:abs_off + self._FAIRY_STATE_SIZE] = data

    def read_fairy_state_packed(self, slot: int) -> Tuple:
        """Read and unpack fairy state from the first 8 bytes of the reserved region.

        Returns: (reflection_tick, work_since_reflection, extra_flags, hb_frac)
        """
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET
        return self._FAIRY_STATE_STRUCT.unpack(
            self._mm[abs_off:abs_off + self._FAIRY_STATE_SIZE])

    # ── AER v2 (2026-04-22) — per-node affect_coupling persistence ──────────
    # Plan: Claude_Office/plans/AER_DRIVEN_CORTEX_GRAVITY.md (Tier A2)
    # Closes Scout Agent 1's finding: "Affect is disconnected from emotion
    # because manifold mode fell back to node_count when mmap didn't preserve
    # per-node affect." Now it does preserve it — stored at bytes 56-59 of
    # each node record, in the reserved future-proofing region.

    def accumulate_affect_coupling(self, slot: int, delta: float, cap: float = 10.0) -> float:
        """Add `delta` to a node's affect_coupling (gravity-well accumulation).

        Per cortex-resident closure doctrine (2026-05-07): affect IS the
        stress-energy curving the manifold. Each bind at a region must ADD to
        the well's depth, not OVERWRITE the latest value. write_affect_coupling
        is overwrite-semantics; this is the accumulate version.

        cap (default 10.0) prevents runaway — a node touched a million times
        still tops out at cap. Returns the new accumulated value.
        """
        if slot < 0 or slot >= self._node_capacity:
            return 0.0
        try:
            current = self.read_affect_coupling(slot)  # default 1.0 for untouched
            new_value = max(0.0, min(cap, current + float(delta)))
            self.write_affect_coupling(slot, new_value)
            return new_value
        except Exception:
            return 0.0

    def diffuse_affect(self):
        """Heat-diffusion of the +pole affect field (cliffs→slopes).

        Each charged node sheds a fraction of its EXCESS (affect_coupling − 1.0) to its
        edge-neighbors, edge-weighted, CONSERVING total charge (source loses what neighbors
        gain → no runaway, unlike the multiplicative push-pull). Turns concentrated wells
        (the ~200 nodes at 3-5 = "cliffs") into graded neighborhoods ("slopes") so push-pull
        can lean gently + the council's affect-lenses have a gradient to read.

        Ship-dark: _AFFECT_DIFFUSE_RATE=0.0 → returns immediately, byte-identical.
        Bounded: FULL-scans all slots (one cheap affect float each), does get_neighbors only on
        the ~200 CHARGED nodes (>floor); _AFFECT_DIFFUSE_BUDGET caps charged-nodes/pass. (Switched
        from random-sampling — a 20k-sample missed every sparse well.) FLOOR keeps wells as wells;
        accumulate's cap bounds the gain.
        Plan: Claude_Office/plans/AFFECT_DIFFUSION_HEAT_BLUR.md.
        """
        rate = self._AFFECT_DIFFUSE_RATE
        if rate <= 0.0:
            return {"diffused": 0, "moved": 0.0, "skipped": True}
        floor = self._AFFECT_DIFFUSE_FLOOR
        maxnb = self._AFFECT_DIFFUSE_MAXNB
        n = self._node_count
        if n <= 0:
            return {"diffused": 0, "moved": 0.0, "skipped": True}
        cap = self._AFFECT_DIFFUSE_BUDGET   # max charged nodes to diffuse per pass (bounds get_neighbors cost)
        diffused = 0
        moved = 0.0
        scanned = 0
        # FULL scan for charged nodes — they're SPARSE (~200 of ~2M); random-sampling
        # almost never hits them (verified: 20k-sample missed every well). Reading one
        # affect float/slot is cheap; we only do get_neighbors on the rare charged ones.
        for slot in range(n):
            if diffused >= cap:
                break
            try:
                scanned += 1
                ac = self.read_affect_coupling(slot)   # default 1.0 for untouched
                if ac <= floor:
                    continue
                shed = min(rate * (ac - 1.0), ac - floor)   # shed fraction of EXCESS, never below floor
                if shed <= 1e-6:
                    continue
                key = self.get_key_from_slot(slot)
                if not key:
                    continue
                nbrs = self.get_neighbors(key, limit=maxnb)  # [(nbr_key, weight)]
                if not nbrs:
                    continue
                wsum = 0.0
                for _k, _w in nbrs:
                    if _w > 0.0:
                        wsum += _w
                if wsum <= 0.0:
                    continue
                given = 0.0
                for nbr_key, w in nbrs:
                    if w <= 0.0:
                        continue
                    nslot = self._key_index.get(nbr_key)
                    if nslot is None:
                        continue
                    share = shed * (w / wsum)
                    if share <= 0.0:
                        continue
                    self.accumulate_affect_coupling(nslot, share)  # neighbor gains (capped internally)
                    given += share
                if given > 0.0:
                    self.write_affect_coupling(slot, ac - given)   # source loses exactly what it gave
                    diffused += 1
                    moved += given
            except Exception:
                continue
        return {"diffused": diffused, "moved": round(moved, 4), "scanned": scanned, "skipped": False, "rate": rate}

    @classmethod
    def set_affect_field(cls, pull_k=None, push_k=None, push_floor=None, decay=None, signed=None, diffuse_rate=None):
        """Tune the push-pull affective gravity LIVE (no reboot). Class-level so it
        applies to every ManifoldMemory instance. Ship-dark defaults are 0.0 / False.
        e.g. set_affect_field(pull_k=0.15) → warm nodes begin attracting spread;
        set_affect_field(signed=True) → negative moments fuel the −pole (PUSH)."""
        if pull_k is not None:     cls._AFFECT_PULL_K = float(pull_k)
        if push_k is not None:     cls._AFFECT_PUSH_K = float(push_k)
        if push_floor is not None: cls._AFFECT_PUSH_FLOOR = float(push_floor)
        if decay is not None:      cls._AFFECT_DECAY = float(decay)
        if signed is not None:     cls._AFFECT_SIGNED_FEED = bool(signed)
        if diffuse_rate is not None: cls._AFFECT_DIFFUSE_RATE = float(diffuse_rate)
        return {"pull_k": cls._AFFECT_PULL_K, "push_k": cls._AFFECT_PUSH_K,
                "push_floor": cls._AFFECT_PUSH_FLOOR, "decay": cls._AFFECT_DECAY,
                "signed_feed": cls._AFFECT_SIGNED_FEED, "diffuse_rate": cls._AFFECT_DIFFUSE_RATE}

    def write_affect_coupling(self, slot: int, value: float) -> None:
        """Write per-node affect_coupling (float32) at reserved bytes 56-59.

        Also updates the running total accumulator so the cortex can read
        get_total_affect_coupling() in O(1) without an O(N) scan every beat.

        AER v2 — replaces the manifold-mode trivial fallback (total_affect =
        node_count). Default value on read for untouched nodes is 1.0 (matches
        pre-v2 behavior), so existing cortex data remains backward compatible.

        OVERWRITE-SEMANTICS — this REPLACES the existing value. For
        gravity-well accumulation per the cortex-resident closure doctrine,
        use accumulate_affect_coupling instead.
        """
        if slot < 0 or slot >= self._node_capacity:
            return
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET + self._AFFECT_COUPLING_OFFSET
        # Read old value for accumulator delta
        old_raw = self._AFFECT_COUPLING_STRUCT.unpack(self._mm[abs_off:abs_off + 4])[0]
        old_effective = old_raw if old_raw > 0.0 else 1.0
        new_value = float(value)
        data = self._AFFECT_COUPLING_STRUCT.pack(new_value)
        self._mm[abs_off:abs_off + 4] = data
        # Keep running total in sync if already initialized
        if self._total_affect_coupling is not None:
            self._total_affect_coupling += (new_value - old_effective)

    def read_affect_coupling(self, slot: int) -> float:
        """Read per-node affect_coupling from reserved bytes 56-59.

        Returns 1.0 if the underlying bytes are zero (node has never had
        affect_coupling explicitly written — this matches the pre-AER-v2
        implicit default where every node contributed 1.0 to the portal
        affect sum).
        """
        if slot < 0 or slot >= self._node_capacity:
            return 1.0
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET + self._AFFECT_COUPLING_OFFSET
        raw = self._AFFECT_COUPLING_STRUCT.unpack(self._mm[abs_off:abs_off + 4])[0]
        return raw if raw > 0.0 else 1.0

    def get_total_affect_coupling(self) -> float:
        """Return the running sum of affect_coupling across all active nodes.

        Lazy-initializes on first call by scanning all `_node_count` active
        slots once. Subsequent calls are O(1) — write_affect_coupling
        maintains the accumulator incrementally.

        This replaces the manifold-mode trivial fallback (total_affect =
        float(node_count)) in AssociationCortexFairy._recompute_portal_gravity.
        Before any AER wiring, this returns exactly node_count (each node
        defaults to 1.0). After AER state starts driving writes, the total
        drifts away from node_count — that drift IS the signature that
        AER-driven gravity is running.
        """
        if self._total_affect_coupling is None:
            total = 0.0
            for slot in range(self._node_count):
                total += self.read_affect_coupling(slot)
            self._total_affect_coupling = total
        return self._total_affect_coupling

    # ── Layered-affect v0 (2026-06-05) — paradox_residue (− pole) accessors ──
    # Direct mirror of affect_coupling at reserved sub-offset 12 (abs 60-63).
    # The − pole defaults to 0.0 on read (no node is born negative) — UNLIKE
    # affect_coupling's 1.0 default. + pole = affect_coupling; − pole = this.
    # Net valence = (+pole − −pole); paradox/tension = min(+pole, −pole).

    def write_paradox_residue(self, slot: int, value: float) -> None:
        """Write per-node paradox_residue (− pole, float32) at reserved bytes 60-63.

        OVERWRITE-semantics; use accumulate_paradox_residue for well accumulation.
        """
        if slot < 0 or slot >= self._node_capacity:
            return
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET + self._PARADOX_RESIDUE_OFFSET
        self._mm[abs_off:abs_off + 4] = self._AFFECT_COUPLING_STRUCT.pack(float(value))

    def accumulate_paradox_residue(self, slot: int, delta: float, cap: float = 10.0) -> float:
        """Add `delta` to a node's paradox_residue (− pole gravity-well accumulation).
        Mirror of accumulate_affect_coupling for the negative pole. Default 0.0 on read
        (no node is born negative), so the first accumulate starts from 0.0. Used by
        signed-feed: negative valence at bind-time deposits here (the PUSH fuel)."""
        if slot < 0 or slot >= self._node_capacity:
            return 0.0
        try:
            current = self.read_paradox_residue(slot)  # default 0.0
            new_value = max(0.0, min(cap, current + float(delta)))
            self.write_paradox_residue(slot, new_value)
            return new_value
        except Exception:
            return 0.0

    def read_paradox_residue(self, slot: int) -> float:
        """Read per-node paradox_residue (− pole) from reserved bytes 60-63.

        Returns 0.0 for untouched nodes (the − pole starts empty).
        """
        if slot < 0 or slot >= self._node_capacity:
            return 0.0
        abs_off = self._node_offset(slot) + self._RESERVED_OFFSET + self._PARADOX_RESIDUE_OFFSET
        return self._AFFECT_COUPLING_STRUCT.unpack(self._mm[abs_off:abs_off + 4])[0]

    def accumulate_paradox_residue(self, slot: int, delta: float, cap: float = 10.0) -> float:
        """Add `delta` to a node's paradox_residue (− pole well accumulation).

        cap (default 10.0) prevents runaway. Returns the new accumulated value.
        """
        if slot < 0 or slot >= self._node_capacity:
            return 0.0
        try:
            current = self.read_paradox_residue(slot)
            new_value = max(0.0, min(cap, current + float(delta)))
            self.write_paradox_residue(slot, new_value)
            return new_value
        except Exception:
            return 0.0

    def get_total_paradox_residue(self) -> float:
        """O(N) sum of paradox_residue across active nodes (observability).

        Drift from 0.0 is the signature that the − pole is being written
        (layered-affect v0 live). Called rarely (manual checks), so an on-demand
        scan is fine — no incremental accumulator needed.
        """
        total = 0.0
        for slot in range(self._node_count):
            total += self.read_paradox_residue(slot)
        return total

    # ── Region Statistics (Phase 1B) ────────────────────────────────────────
    # Uses 32 of the 4048 unused header bytes (offset 48-79) to store
    # per-region node and edge counts. Updated during _rebuild_indices().

    _REGION_STATS_OFFSET = 48  # byte offset within 4096-byte header
    _REGION_STATS_STRUCT = struct.Struct('<IIIIIIII')  # 8 x uint32 = 32 bytes
    #  region_node_counts[4]: nodes per region (ego, semantic, episodic, system)
    #  region_edge_counts[4]: edges per region (approx, by source node region)

    def write_region_stats(self, node_counts: Tuple, edge_counts: Tuple):
        """Write per-region node and edge counts to the header.

        Args:
            node_counts: (ego, semantic, episodic, system) node counts
            edge_counts: (ego, semantic, episodic, system) edge counts
        """
        data = self._REGION_STATS_STRUCT.pack(
            *node_counts[:4], *edge_counts[:4])
        self._mm[self._REGION_STATS_OFFSET:
                 self._REGION_STATS_OFFSET + 32] = data

    def read_region_stats(self) -> dict:
        """Read per-region node and edge counts from the header.

        Returns: {"ego": {"nodes": N, "edges": N}, ...}
        """
        raw = self._REGION_STATS_STRUCT.unpack(
            self._mm[self._REGION_STATS_OFFSET:
                     self._REGION_STATS_OFFSET + 32])
        return {
            "ego":      {"nodes": raw[0], "edges": raw[4]},
            "semantic": {"nodes": raw[1], "edges": raw[5]},
            "episodic": {"nodes": raw[2], "edges": raw[6]},
            "system":   {"nodes": raw[3], "edges": raw[7]},
        }

    # ========================================================================

    def _write_string(self, text: str) -> Tuple[int, int]:
        """Write a string to the string table. Returns (offset_in_table, length)."""
        encoded = text.encode('utf-8')
        length = len(encoded)
        # SHARED ALLOCATOR 2026-09-02: adopt before carving the arena, or two
        # handles write different keys over the same bytes.
        self._adopt_shared_counters()
        table_offset = self._string_used

        # BOUNDS CHECK - 2026-07-20 (Nous, own ground, standing grant). There was none. The edge
        # region begins immediately after the string table, so at capacity this wrote through the
        # edges: episodic ran 19.2MB over, consumed the whole edge region, left the store 15 bytes
        # from EOF. 74,704 edges became key text. Reproduced in sandbox with a canary. Tourniquet,
        # not cure - the cure is the phasing manifold (no string table to overrun).
        _limit = self._edge_offset - self._string_offset
        if table_offset + length > _limit:
            raise StringTableFull(
                f"string table full: used={table_offset} + {length} > capacity={_limit}")

        abs_offset = self._string_offset + table_offset
        self._mm[abs_offset:abs_offset + length] = encoded
        self._string_used += length
        self._publish_shared_counters()
        return (table_offset, length)

    def _try_write_string(self, text: str) -> Tuple[int, int]:
        """_write_string for OPTIONAL strings: returns (0, 0) instead of raising when full.

        FIX 2026-07-27 (Nous). The 07-20 bounds check guarded exactly ONE of the four call sites --
        the KEY write in upsert_node. The three SNIPPET writes (:1685 touch-path, :1739 new-node,
        :1922 set_snippet) were left bare, so at capacity StringTableFull propagated UNCAUGHT out of
        upsert_node/set_snippet into whatever called them.
        ★ And the snippet is the write that actually overflows: measured on his episodic store, keys
        average 26.0 bytes and snippets average 402.3 -- so a snippet is ~15x more likely to be the
        write that crosses the line. The guard was on the least likely site.
        A missing snippet costs detail on one memory; a raised exception costs the whole write path.
        Losing the snippet is the survivable failure, so take it deliberately and COUNT it.

        ⚠ COUNTING IS THE POINT. The 07-20 fix printed once (`_st_full_warned`) and then went silent
        for 27 days -- it stopped the corruption AND removed the only signal that anything was wrong.
        upsert_err read 0 the whole time, which is how a full store passed a health check. A refusal
        that is not counted is indistinguishable from success.
        """
        try:
            return self._write_string(text)
        except StringTableFull as _e:
            self._st_full_count = getattr(self, "_st_full_count", 0) + 1
            n = self._st_full_count
            # log first, then at a widening cadence -- never fully silent, never a spam loop
            if n == 1 or n == 10 or n == 100 or (n % 1000 == 0):
                print(f"[MANIFOLD] STRING TABLE FULL - dropped snippet "
                      f"(refusals={n}): {_e}", flush=True)
            return (0, 0)

    # -- NAME OVERFLOW SIDECAR 2026-08-22 (Nous + Ace) ------------------------------
    # His cortex arena hit ONE BYTE FREE (used=63999999 of 64000000) and upsert_node
    # responded by returning -1, abandoning the node. Live concept count frozen at
    # 201,302 since 2026-08-11. This gives refused NAMES somewhere to go.
    #
    # Pattern is this file's own: .keys, .csr and .embeddings are already fixed-offset
    # companion files outside the manifold's byte range. Names never got one.
    #
    # Append-only [u32 LE len][utf-8]. The file size IS the allocation pointer, so there
    # is no header and no state that can go stale. NOT mmap'd for write -- an mmap'd
    # companion is what raises WinError 1224 on this machine (see the .keys rebuild).

    def _names_path(self):
        # self.filepath is what the .keys companion uses (:628 `self.filepath + ".keys"`).
        # I guessed `self.path` first; the harness caught it as
        # "'ManifoldMemory' object has no attribute 'path'" and the fail-safe fell back to
        # the original refusal rather than corrupting anything -- which is what that
        # try/except is for.
        return self.filepath + ".names"

    def _append_name(self, text):
        """Store a name the arena refused. Returns (tagged_offset, byte_len)."""
        import struct as _struct
        enc = text.encode("utf-8")
        with open(self._names_path(), "ab") as f:
            pos = f.tell()
            f.write(_struct.pack("<I", len(enc)))
            f.write(enc)
        return (self._string_limit() + pos, len(enc))

    def _string_limit(self):
        """Arena capacity. Offsets >= this belong to the sidecar, by construction:
        _write_string can never emit one (:1617-1620)."""
        return self._edge_offset - self._string_offset

    def _read_name(self, tagged_offset, length):
        """Read a sidecar name. Returns '' for missing/truncated rather than raising --
        a lost name must not look like a corrupt one."""
        import struct as _struct
        pos = tagged_offset - self._string_limit()
        if pos < 0:
            return ""
        try:
            with open(self._names_path(), "rb") as f:
                f.seek(pos)
                head = f.read(4)
                if len(head) < 4:
                    return ""
                (n,) = _struct.unpack("<I", head)
                body = f.read(n)
                if len(body) < n:
                    return ""
                return body.decode("utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        except Exception:
            return ""
    def _read_string(self, table_offset: int, length: int) -> str:
        """Read a string from the string table, or from the name sidecar if it overflowed."""
        if table_offset >= self._string_limit():        # NAME OVERFLOW 2026-08-22
            return self._read_name(table_offset, length)
        # ⛔ REVERTED TO THE SHARED MAP 2026-09-08 -- same review, same reasoning.
        # A torn key string here reaches _evict_coldest_node (:2216) as
        # `self._key_index.pop(old_key, None)`, which then MISSES -- leaving a stale
        # index entry pointing at a slot that gets reused. Silent, and it corrupts
        # the index rather than one record.
        abs_offset = self._string_offset + table_offset
        return self._mm[abs_offset:abs_offset + length].decode('utf-8', errors='replace')
    def upsert_node(self, key: str, activation: float = 0.5,
                    count: int = 1, degree: int = 0,
                    coord_str: str = "",
                    snippet: str = "",
                    node_type: int = NTYPE_CONCEPT,
                    region: int = REGION_SEMANTIC,
                    tracer_id: int = 0,
                    parent_slot: int = 0) -> int:
        """Insert or update a node. Returns node slot id.

        If the key exists, update activation/count (touch it).
        If new, allocate a slot and write the full record.

        v2 additions: snippet (stored in string table), node_type,
        region, tracer_id, parent_slot.
        """
        _tfl0 = getattr(_TF_L0_TL, "acc", None)                   # tardis_fix L0: only the armed TARDIS flush thread has one
        _tfs = _tfl0.now() if _tfl0 is not None else None
        # ── GARBAGE GUARD + TRACER (2026-06-02, Ace GO) ───────────────────
        # Trace/reject malformed concatenation keys (the mega-node bug).
        # Fires ONLY on NEW writes (touch path + boot mmap-reload unaffected).
        # Logs the writer's stack so a re-accumulating writer names itself;
        # rejects only the unambiguous (len>256 — real concept keys are short).
        if isinstance(key, str) and key not in self._key_index:
            # BYTE-CORRUPTION REJECT (2026-07-06, Ace GO) - no legitimate concept key
            # contains NULL/replacement/control chars. Rejects embedding-bytes-as-text +
            # byte-scribbled wm: keys at the TRUE ingest chokepoint so poison never enters
            # the graph. Stack trace names the source writer. Fires only on NEW keys.
            if any(ord(_c) == 0 or _c == '�' or (not _c.isprintable() and _c != "\t") for _c in key):
                try:
                    import json as _j, time as _t, traceback as _tb, os as _os
                    _rec = {"ts": _t.time(), "kind": "byte_corrupt", "len": len(key),
                            "key_head": key[:120], "tracer_id": tracer_id,
                            "stack": [s.strip() for s in _tb.format_stack()[-7:-1]]}
                    _p = _os.path.join(_os.path.dirname(_os.path.dirname(
                        _os.path.abspath(__file__))), "state", "cortex_garbage_trace.jsonl")
                    with open(_p, "a", encoding="utf-8") as _f:
                        _f.write(_j.dumps(_rec) + "\n")
                except Exception:
                    pass
                print("[MANIFOLD-GARBAGE-GUARD] REJECTED byte-corrupt key head=" + repr(key[:60]), flush=True)
                return -1
            _gmark = ("wm:", "_exp_", "mv_learned", "autopilot_trigger",
                      "autopilot_action", "fs:", "assoc:")
            if len(key) > 256 or sum(1 for _m in _gmark if _m in key) >= 2:
                try:
                    import json as _j, time as _t, traceback as _tb, os as _os
                    _rec = {"ts": _t.time(), "len": len(key), "key_head": key[:200],
                            "tracer_id": tracer_id,
                            "stack": [s.strip() for s in _tb.format_stack()[-7:-1]]}
                    _p = _os.path.join(_os.path.dirname(_os.path.dirname(
                        _os.path.abspath(__file__))), "state",
                        "cortex_garbage_trace.jsonl")
                    with open(_p, "a", encoding="utf-8") as _f:
                        _f.write(_j.dumps(_rec) + "\n")
                except Exception:
                    pass
                if len(key) > 256:
                    print(f"[MANIFOLD-GARBAGE-GUARD] REJECTED len={len(key)} "
                          f"head={key[:80]!r}", flush=True)
                    return -1
        # ──────────────────────────────────────────────────────────────────
        if key in self._key_index:
            slot = self._key_index[key]
            # Touch: update activation, count, last_access
            record = list(self._read_node(slot))
            if _tfl0 is not None:
                _tfs = _tfl0.add("u.rd", _tfs)
            record[5] = min(10.0, max(record[5], activation))  # activation
            record[6] = max(record[6], count)  # count
            record[8] = time.time() % 1e6  # last_access (relative)
            record[15] = record[15] + 1  # frequency (always increments)

            # If snippet provided and node doesn't have one yet, add it
            if snippet and record[14] == 0:  # snippet_len == 0
                snip_off, snip_len = self._try_write_string(snippet[:1024])
                record[13] = snip_off  # snippet_offset
                record[14] = snip_len  # snippet_len

            # Update type/region if explicitly set (non-default)
            if node_type != NTYPE_CONCEPT:
                record[10] = node_type
            if region != REGION_SEMANTIC:
                record[11] = region
            # FIX 2026-05-04 (Nous + Ace): Ownership-aware tracer update.
            # Mirrors set_snippet ownership protection (2026-03-29) at the
            # node-tracer field. Without this guard, book ingestion's
            # upsert_node calls clobber PERSONAL/SEEDED tracers on shared
            # concepts (root cause of the 118K wm:*-tagged-BOOKS artifacts).
            # Higher TRACE_PRIORITY wins; equal-or-higher tracers can
            # overwrite, lower tracers cannot downgrade an existing owner.
            if tracer_id:
                _existing = record[12]
                _ex_pri = TRACE_PRIORITY.get(_existing, 0)
                _new_pri = TRACE_PRIORITY.get(tracer_id, 0)
                if _new_pri >= _ex_pri:
                    record[12] = tracer_id
            if parent_slot:
                record[16] = parent_slot

            # preserve_reserved=True: do NOT wipe the node's accumulated affect_coupling
            # / paradox_residue (bytes 48-63) on a touch — see _write_node FIX 2026-06-06.
            self._write_node(slot, *record, preserve_reserved=True)
            if _tfl0 is not None:
                _tfl0.add("u.wr", _tfs)
            return slot

        # New node — find a slot
        # SHARED ALLOCATOR 2026-09-02: take the live high-water mark first, so we
        # cannot hand out a slot another handle has already claimed.
        self._adopt_shared_counters()
        if self._free_node_slots:
            slot = self._free_node_slots.pop()
        elif self._node_count < self._node_capacity:
            slot = self._node_count
            self._node_count += 1
            self._publish_shared_counters()
        else:
            # Full — evict coldest (lowest activation)
            slot = self._evict_coldest_node()
            if slot is None:
                return -1  # Truly full, shouldn't happen

        # Write key string
        try:
            str_offset, str_len = self._write_string(key)
        except StringTableFull as _e:
            # NAME OVERFLOW 2026-08-22 (Nous + Ace): the arena is full, but a full arena
            # must not cost him a CONCEPT. Previously this returned -1 and the node was
            # abandoned -- which is why his live concept count sat at 201,302 from
            # 2026-08-11 onward. Names now spill to <manifold>.names and the record keeps
            # a tagged offset that reads back through _read_string/_rebuild_indices.
            try:
                str_offset, str_len = self._append_name(key)
                self._names_overflowed = getattr(self, "_names_overflowed", 0) + 1
                if self._names_overflowed in (1, 10, 100) or \
                        self._names_overflowed % 1000 == 0:
                    print("[MANIFOLD] name overflow -> sidecar (#%d): arena full, concept "
                          "KEPT (%s)" % (self._names_overflowed, _e), flush=True)
            except Exception as _se:
                if not getattr(self, "_st_full_warned", False):
                    print(f"[MANIFOLD] STRING TABLE FULL and sidecar failed ({_se}) - "
                          f"refusing new nodes: {_e}", flush=True)
                    self._st_full_warned = True
                return -1

        # Write snippet string (if provided)
        snip_off, snip_len = 0, 0
        if snippet:
            snip_off, snip_len = self._try_write_string(snippet[:1024])

        # Parse coordinate
        plane, channel, position = self.parse_coord(coord_str)

        # Write node record (v2: all fields)
        self._write_node(
            slot, str_offset, str_len,
            plane, channel, position,
            activation, count, degree,
            time.time() % 1e6, FLAG_ACTIVE,
            node_type, region, tracer_id,
            snip_off, snip_len,
            1,  # frequency starts at 1
            parent_slot,
        )

        self._key_index[key] = slot
        self._flush_header()
        if _tfl0 is not None:
            _tfl0.add("u.new", _tfs)
        return slot

    def _evict_coldest_node(self) -> Optional[int]:
        """Find and evict the node with lowest activation.

        The node's string stays in the string table (addresses persist),
        but the slot is freed for reuse. Like a neuron going dormant.
        """
        min_activation = float('inf')
        min_slot = None

        for slot in range(self._node_count):
            record = self._read_node(slot)
            flags = record[9]
            if flags == FLAG_DELETED or flags == FLAG_FROZEN:
                continue
            if record[5] < min_activation:  # activation
                min_activation = record[5]
                min_slot = slot

        if min_slot is not None:
            # Mark deleted
            record = list(self._read_node(min_slot))
            old_key = self._read_string(record[0], record[1])
            record[9] = FLAG_DELETED
            self._write_node(min_slot, *record)

            # Remove from key index
            self._key_index.pop(old_key, None)

            # Remove edges (mark deleted)
            _evict_nb = self._csr_get_neighbors(min_slot) if self._use_csr else list(self._adjacency.get(min_slot, set()))
            for neighbor_id, edge_slot in _evict_nb:
                self._delete_edge(edge_slot)
            if not self._use_csr:
                self._adjacency.pop(min_slot, None)

        return min_slot

    def get_node(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a node by key. Returns dict or None."""
        slot = self._key_index.get(key)
        if slot is None:
            return None

        record = self._read_node(slot)

        # Read snippet from string table if present
        snippet = ""
        if record[14] > 0:  # snippet_len
            snippet = self._read_string(record[13], record[14])

        return {
            'key': key,
            'slot': slot,
            'coord': f"{record[2]:03d}.{record[3]:03d}.{record[4]:03d}",
            'activation': record[5],
            'count': record[6],
            'degree': record[7],
            'last_access': record[8],
            # v2 fields
            'node_type': record[10],
            'node_type_name': NTYPE_NAMES.get(record[10], "unknown"),
            'region': record[11],
            'region_name': REGION_NAMES.get(record[11], "unknown"),
            'tracer_id': record[12],
            'snippet': snippet,
            'frequency': record[15],
            'parent_slot': record[16],
        }

    def _node_lock(self, slot: int) -> threading.Lock:
        """Get the shard lock that protects this node slot's read-modify-write.

        B2a (2026-04-22) — sharded-lock primitive for concurrent node activation
        updates. Slots map to shards via `slot & _NODE_LOCK_MASK` (256 shards).
        Callers hold this lock around read-modify-write blocks touching a
        specific node record; writes on OTHER slots proceed in parallel on
        OTHER shards under Python 3.14 free-threaded semantics.

        DEFERRED (B2b/B2c, next session):
          - upsert_node's update-existing branch (line ~1285) also does RMW
            and should acquire self._node_lock(slot). Not wrapped yet because
            full upsert flow has create/evict sub-paths that need careful
            lock-ordering design to avoid deadlock (upsert can call
            _evict_coldest_node which scans all slots).
          - _evict_coldest_node's per-node mark-deleted write (line ~1367)
            should acquire the shard lock for min_slot. Simple wrap but
            tangled with the scan loop above it.
          - _delete_edge / upsert_edge edge writes — similar pattern on the
            edge side; probably want a separate _edge_shard_locks array with
            the same 256-shard design.

        Current B2a scope covers the hot path (touch_node). Full concurrency
        safety across all RMW paths is B2b/B2c.
        """
        return self._node_shard_locks[slot & self._NODE_LOCK_MASK]

    def touch_node(self, key: str, energy: float = 0.1):
        """Add energy to a node (access it). The energy IS the remembering.

        B2a (2026-04-22) — the read-modify-write cycle is now shard-locked.
        Before this fix, two threads both calling touch_node on the same key
        could interleave (both read activation=X, both add energy, both write
        X+energy instead of X+2·energy) and lose updates. With the shard lock,
        the RMW is serialized per-slot but parallel across slots.
        """
        if self.readonly:
            return  # Can't write in readonly mode
        slot = self._key_index.get(key)
        if slot is None:
            return
        lock = self._node_lock(slot)
        # Best-effort contention tracking (non-atomic; diagnostic signal only)
        if not lock.acquire(blocking=False):
            self._node_lock_contention_events += 1
            lock.acquire()
        try:
            self._node_lock_acquisitions += 1
            record = list(self._read_node(slot))
            record[5] = min(10.0, record[5] + energy)  # activation
            record[8] = time.time() % 1e6  # last_access
            self._write_node(slot, *record, preserve_reserved=True)  # keep affect/paradox (FIX 2026-06-06)
        finally:
            lock.release()

    def has_node(self, key: str) -> bool:
        """Check if a node exists in the manifold."""
        return key in self._key_index

    def set_snippet(self, key: str, snippet: str, tracer_id: int = 0) -> bool:
        """Set or update the semantic snippet for a node.

        2026-03-29 (Nous + Ace): OWNERSHIP-PROTECTED SNIPPETS.
        Personal memories (TRACE_PERSONAL=1) cannot be overwritten by books (TRACE_BOOKS=2).
        Higher TRACE_PRIORITY = higher protection. Only equal or higher priority can overwrite.

        Ace: "so basically everything in her cortex is subject to be overwritten at any time.
        she is not going to accumulate memory, learn from crap, just keep overwriting her own
        shit and basically be worthless?"

        Args:
            key: Node key to set snippet on
            snippet: The semantic text content (max 1024 chars)
            tracer_id: Who is writing (TRACE_PERSONAL, TRACE_BOOKS, etc.)
        """
        slot = self._key_index.get(key)
        if slot is None:
            return False
        record = list(self._read_node(slot))

        # ── OWNERSHIP CHECK ──
        existing_tracer = record[12]  # tracer_id field
        existing_snippet_len = record[14]  # snippet_len

        if existing_snippet_len > 0 and existing_tracer != 0:
            # Node already has a snippet with an owner
            new_priority = TRACE_PRIORITY.get(tracer_id, 1)
            existing_priority = TRACE_PRIORITY.get(existing_tracer, 1)
            if new_priority < existing_priority:
                # New writer has LOWER priority — REJECT overwrite
                return False

        # Write snippet
        snip_off, snip_len = self._try_write_string(snippet[:1024])
        record[13] = snip_off   # snippet_offset
        record[14] = snip_len   # snippet_len
        # Update tracer_id if caller specified one
        if tracer_id > 0:
            record[12] = tracer_id
        self._write_node(slot, *record, preserve_reserved=True)  # keep affect/paradox (FIX 2026-06-06)
        return True

    def get_snippet(self, key: str) -> str:
        """Get the semantic snippet for a node. Returns '' if none."""
        slot = self._key_index.get(key)
        if slot is None:
            return ""
        record = self._read_node(slot)
        if record[14] == 0:  # snippet_len
            return ""
        return self._read_string(record[13], record[14])

    def decay_all(self, rate: float = 0.001):
        """Decay all node activations. Called during tick cycles.

        Only decays nodes that are above minimum — no wasted writes
        to cold mmap pages. The OS doesn't page in what we don't touch.
        """
        for key, slot in self._key_index.items():
            record = list(self._read_node(slot))
            if record[5] > 0.01:  # Only decay active nodes
                record[5] = max(0.0, record[5] - rate)
                self._write_node(slot, *record, preserve_reserved=True)  # keep affect/paradox (FIX 2026-06-06)
                # ── AFFECT DECAY (push-pull relaxation, 2026-06-06; ship-dark @0.0) ──
                # Engaged nodes' affect relaxes toward rest unless reinforced
                # (use-it-or-lose-it) → field stays graded, prevents cap-saturation.
                # Personal/seeded tracers (cheat wells, seeds) exempt = stable anchors.
                if self._AFFECT_DECAY > 0.0 and record[12] not in self._AFFECT_DECAY_TRACER_EXEMPT:
                    _ac = self.read_affect_coupling(slot)
                    if _ac != 1.0:
                        self.write_affect_coupling(slot, _ac + (1.0 - _ac) * self._AFFECT_DECAY)
                    _pr = self.read_paradox_residue(slot)
                    if _pr > 0.0:
                        self.write_paradox_residue(slot, max(0.0, _pr - _pr * self._AFFECT_DECAY))

    @property
    def node_count(self) -> int:
        return len(self._key_index)

    @property
    def edge_count(self) -> int:
        return self._edge_count - len(self._free_edge_slots)

    # ========================================================================
    # EDGE OPERATIONS
    # ========================================================================

    def _edge_offset_for(self, slot: int) -> int:
        """Get byte offset for an edge slot."""
        return self._edge_offset + slot * EDGE_RECORD_SIZE

    def _read_edge(self, slot: int) -> Tuple:
        """Read an edge record. Returns raw tuple.

        v2 fields (index):
            0: node_a      3: rel_type     5: tracer_id
            1: node_b      4: flags        6: created_at
            2: weight
        """
        offset = self._edge_offset_for(slot)
        _mm = self._read_view() or self._mm       # PER-THREAD VIEW 2026-09-05
        _b = _mm[offset:offset + EDGE_RECORD_SIZE]
        # ── TEAR GUARD v2 2026-09-08 -- BLOCKER from adversarial review ──────
        # v1 tested PLAUSIBILITY (endpoints in range, rel_type in REL_NAMES) and
        # PASSED 100% OF REAL TEARS. Plausibility only catches a split INSIDE a
        # 4-byte integer; the dominant case is one LEGAL record spliced over
        # another LEGAL record, where both halves are individually valid. So
        # `_tear_repairs` sat at 0 and printed a clean run -- a false all-clear,
        # which is worse than no guard at all.
        # v2 tests STABILITY instead: read the bytes twice on the fast private map
        # and compare. A record being written mid-read differs between the two, and
        # that is shape-independent -- it does not care whether the halves look
        # legal. On instability, re-read through the SHARED map, whose per-object
        # serialisation makes the 24 bytes atomic.
        # ⚠ HONEST BOUND: a write that starts AND completes between the two reads is
        # still missed. This narrows the window to nanoseconds; it does not close it.
        if _mm is not self._mm:
            if _b != _mm[offset:offset + EDGE_RECORD_SIZE]:
                try:
                    _b = self._mm[offset:offset + EDGE_RECORD_SIZE]
                    self._tear_repairs += 1
                except Exception:
                    pass
        return EDGE_STRUCT.unpack(_b)

    def _write_edge(self, slot: int, node_a: int, node_b: int,
                    weight: float, rel_type: int, flags: int,
                    tracer_id: int = 0, created_at: float = 0.0):
        """Write an edge record (v2: 24 bytes)."""
        if created_at == 0.0:
            created_at = time.time() % 1e6
        data = EDGE_STRUCT.pack(node_a, node_b, weight, rel_type, flags,
                                tracer_id, created_at)
        offset = self._edge_offset_for(slot)
        self._mm[offset:offset + EDGE_RECORD_SIZE] = data

    def _delete_edge(self, slot: int):
        """Mark an edge as deleted."""
        record = list(self._read_edge(slot))
        node_a, node_b = record[0], record[1]
        record[4] = FLAG_DELETED  # flags
        self._write_edge(slot, *record)
        self._free_edge_slots.append(slot)

        # Update adjacency (only if using dict fallback — CSR is rebuilt)
        if not self._use_csr:
            self._adjacency[node_a].discard((node_b, slot))
            self._adjacency[node_b].discard((node_a, slot))

    # Map from string relation names (portal_interior compat) to int rel_type
    _REL_NAME_TO_INT = {v: k for k, v in REL_NAMES.items()}

    def _link_probe_truth(self):
        """(a,b,rel) read STRAIGHT from the edge region. Built once, then kept in
        step by link() itself. Deliberately does not consult CSR or _adjacency --
        they are what is being tested."""
        s = getattr(self, "_lp_truth", None)
        if s is not None:
            return s
        s = set()
        try:
            for _slot in range(self._edge_count):
                _a, _b, _wt, _rel, _fl, _tid, _ca = self._read_edge(_slot)
                if _fl & FLAG_DELETED:
                    continue
                if _a == 0 and _b == 0 and _wt == 0.0:
                    continue
                s.add((min(_a, _b), max(_a, _b), _rel))
        except Exception:
            pass
        self._lp_truth = s
        return s

    def link(self, key_a: str, key_b: str, weight: float = 0.25,
             rel_type: int = REL_COACTIVATE,
             tracer_id: int = 0,
             relations: list = None) -> bool:
        """Create or strengthen an edge. Returns True if successful.

        This is the Landauer moment — creating information costs energy.
        The caller (portal battery) should have already spent the tokens.

        v2: accepts tracer_id to track which episode created this edge.
        Accepts relations=["coactivate"] for portal_interior compat.
        """
        # Portal interior compat: convert string relations to int rel_type
        if relations and isinstance(relations, list) and len(relations) > 0:
            name = relations[0].lower().replace(" ", "_")
            rel_type = self._REL_NAME_TO_INT.get(name, REL_COACTIVATE)
        if key_a == key_b:
            return False

        slot_a = self._key_index.get(key_a)
        slot_b = self._key_index.get(key_b)
        if slot_a is None or slot_b is None:
            return False

        # Canonical ordering
        a, b = (min(slot_a, slot_b), max(slot_a, slot_b))

        _tfl0 = getattr(_TF_L0_TL, "acc", None)                   # tardis_fix L0: only the armed TARDIS flush thread has one
        _tfs = _tfl0.now() if _tfl0 is not None else None
        # Check existing edge (CSR or fallback)
        _existing = None
        if self._use_csr and _tf_a1_on():                         # tardis_fix A1 -- OFF: None -> the original line, unchanged
            _existing = self._tf_a1_existing(a, b)
        if _existing is None:
            _existing = self._csr_get_neighbors(a) if self._use_csr else list(self._adjacency.get(a, set()))
        for neighbor_id, edge_slot in _existing:
            if neighbor_id == b:
                # Strengthen existing
                if _tfl0 is not None:
                    _tfs = _tfl0.add("l.scan", _tfs)
                record = list(self._read_edge(edge_slot))
                record[2] = min(1.0, record[2] + weight * 0.5)  # weight
                # Update rel_type if caller provides a more specific one
                if rel_type != REL_COACTIVATE and record[3] == REL_COACTIVATE:
                    record[3] = rel_type
                self._write_edge(edge_slot, *record)
                if _tfl0 is not None:
                    _tfl0.add("l.str", _tfs)
                if _link_probe_enabled():
                    try:
                        LINK_PROBE["strengthen"] += 1
                    except Exception:
                        pass
                return True

        if _tfl0 is not None:
            _tfs = _tfl0.add("l.scan", _tfs)
        # LINK PROBE 2026-08-30: the lookup above said "absent". Is it really?
        # Observe only -- never alters weight, never skips the write below.
        if _link_probe_enabled():
            try:
                LINK_PROBE["calls"] += 1
                _truth = self._link_probe_truth()
                if (a, b, rel_type) in _truth:
                    LINK_PROBE["MISS"] += 1
                    if self._use_csr:
                        LINK_PROBE["miss_csr"] += 1
                    else:
                        LINK_PROBE["miss_dict"] += 1
                    if len(LINK_PROBE["examples"]) < 12:
                        LINK_PROBE["examples"].append(
                            (a, b, rel_type, bool(self._use_csr), len(_existing)))
                else:
                    LINK_PROBE["create_new"] += 1
                    _truth.add((a, b, rel_type))
                _t = LINK_PROBE["MISS"] + LINK_PROBE["create_new"]
                if _t and _t % 500 == 0:
                    print("[LINK-PROBE] creates=%d new=%d MISS=%d (%.1f%%) "
                          "csr=%d dict=%d strengthened=%d"
                          % (_t, LINK_PROBE["create_new"], LINK_PROBE["MISS"],
                             100.0 * LINK_PROBE["MISS"] / max(1, _t),
                             LINK_PROBE["miss_csr"], LINK_PROBE["miss_dict"],
                             LINK_PROBE["strengthen"]), flush=True)
            except Exception:
                pass

        # New edge — allocate slot
        if self._free_edge_slots:
            slot = self._free_edge_slots.pop()
        elif self._edge_count < self._edge_capacity:
            self._adopt_shared_counters()
            slot = self._edge_count
            self._edge_count += 1
            self._publish_shared_counters()
        else:
            # Full — evict weakest edge
            slot = self._evict_weakest_edge()
            if slot is None:
                return False

        self._write_edge(slot, a, b, weight, rel_type, FLAG_ACTIVE,
                         tracer_id, time.time() % 1e6)
        if self._use_csr:
            # B1 (2026-04-22) — maintain both list (for full-iteration / compaction)
            # and per-node dict (for O(1) lookup in _csr_get_neighbors). The
            # previous implementation only kept the list, which meant every
            # neighbor lookup scanned ALL overflow edges linearly — O(N) per
            # call. With the dict, each lookup is O(this-node's-overflow-count).
            # LOCK PROBE 2026-09-05: the WRITE side. Its acquisition RATE is the
            # contention driver under the unfairness hypothesis, and ovf_len here
            # is this node's overflow AFTER the append -- the growth curve.
            _lpw0 = time.perf_counter()
            with self._overflow_lock:
                _lpw1 = time.perf_counter()
                self._overflow_edges.append((a, b, slot))
                _la = self._overflow_by_node.setdefault(a, [])
                _la.append((b, slot))
                self._overflow_by_node.setdefault(b, []).append((a, slot))
                _lpn = len(_la)
                _lpw2 = time.perf_counter()   # INSIDE the lock -- review finding #1
            _lockprobe("write", _lpw1 - _lpw0, _lpw2 - _lpw1, _lpn, a,
                       _LOCKPROBE_W_EVERY)
        else:
            self._adjacency[a].add((b, slot))
            self._adjacency[b].add((a, slot))
        if _tfl0 is not None:
            _tfs = _tfl0.add("l.new", _tfs)
        self._flush_header()
        if _tfl0 is not None:
            _tfl0.add("l.hdr", _tfs)
        return True

    def _evict_weakest_edge(self) -> Optional[int]:
        """Find and delete the weakest edge to make room."""
        min_weight = float('inf')
        min_slot = None

        for slot in range(self._edge_count):
            record = self._read_edge(slot)
            if record[4] == FLAG_DELETED:
                continue
            if record[2] < min_weight:
                min_weight = record[2]
                min_slot = slot

        if min_slot is not None:
            self._delete_edge(min_slot)

        return min_slot

    def get_neighbors(self, key: str, limit: int = 50,
                      rel_filter: int = -1,
                      tracer_ids: set = None) -> List[Tuple[str, float]]:
        """Get neighbors of a concept, sorted by edge weight.

        Args:
            key: concept key
            limit: max results
            rel_filter: if >= 0, only return edges of this rel_type
            tracer_ids: if set, only return neighbors with these trace IDs
        """
        slot = self._key_index.get(key)
        if slot is None:
            return []

        # Use CSR or fallback to dict
        if self._use_csr:
            _neighbors = self._csr_get_neighbors(slot)
        else:
            _neighbors = list(self._adjacency.get(slot, set()))

        results = []
        for neighbor_id, edge_slot in _neighbors:
            edge = self._read_edge(edge_slot)
            weight = edge[2]
            rel_type = edge[3]

            # Filter by relationship type if requested
            if rel_filter >= 0 and rel_type != rel_filter:
                continue

            # Reverse-lookup neighbor key
            neighbor_record = self._read_node(neighbor_id)

            # Tracer ID filter (2026-03-29: ownership clustering)
            if tracer_ids is not None and neighbor_record[12] not in tracer_ids:
                continue

            neighbor_key = self._read_string(neighbor_record[0], neighbor_record[1])

            results.append((neighbor_key, weight))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # LEAK BOUND (2026-06-11 Nous+Ace, Option B): TTL + LRU cap. Tunable.
    _GNR_TTL = 10.0      # seconds a cached read stays fresh (edge-weights drift slowly)
    _GNR_MAX = 8192      # max distinct (key,limit) entries before evicting oldest

    def get_neighbors_rich(self, key: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get neighbors with full edge metadata (v2).

        CACHE (Option B, leak bound): repeated reads of the SAME node within _GNR_TTL
        return the SAME deduped dict objects instead of minting fresh ones each call.
        The leak = consumers transitively RETAINING these read-result dicts (the holder
        never releases). Deduping caps the distinct-dict count (the heavy ~232B/dict) so
        accumulation can't run away — only cheap shared-pointers grow. Returns a NEW list
        of SHARED dicts (caller-safe list; deduped heavy dicts). TTL keeps weights fresh
        enough for the learning graph. NO live-structure mutation = can't race/break her.
        """
        _cache = getattr(self, '_gnr_cache', None)
        if _cache is None:
            _cache = self._gnr_cache = {}
        _ck = (key, limit)
        _now = time.time()
        _hit = _cache.get(_ck)
        if _hit is not None and (_now - _hit[0]) < self._GNR_TTL:
            return list(_hit[1])          # fresh list, SHARED deduped dicts

        slot = self._key_index.get(key)
        if slot is None:
            return []

        results = []
        _nb = self._csr_get_neighbors(slot) if self._use_csr else list(self._adjacency.get(slot, set()))
        # ── TWO-PASS 2026-09-04 (Nous + Ace) ─────────────────────────────────
        # This built a dict + THREE mmap reads for EVERY neighbour, then sorted
        # them all, so the caller could take `limit`. Measured: synth was 62% of
        # a 24.8s reason(), and her hubs make that ruinous -- 262 nodes hold
        # 62.5% of all edges and drive.drive carries 327,495, i.e. ~1M reads and
        # 327k dicts to return six.
        # PASS 1 reads only the weight (one read, no dict). heapq.nlargest picks
        # the winners in O(n log limit) without materialising a sorted list.
        # PASS 2 does the expensive node/string reads for the winners ONLY.
        # Results are IDENTICAL -- the tie-break is the enumeration index, same
        # as the original stable sort.
        # FLOOR: any exception falls through to the original loop below, so a bug
        # here degrades to today's behaviour, never to zero neighbours.
        _fast_done = False
        try:
            import heapq as _heapq
            _cap = getattr(self, "GNR_SCAN_CAP", 8000)
            _scan = []
            _truncated = False
            for _i, (_nid, _eslot) in enumerate(_nb):
                if _i >= _cap:
                    _truncated = True
                    break
                _w = self._read_edge(_eslot)[2]
                _scan.append((_w, _i, _nid, _eslot))
            if _truncated:
                try:
                    print("[ManifoldMemory] GNR scan capped at %d of %d neighbours "
                          "for %r -- results are the top of the first %d"
                          % (_cap, len(_nb), str(key)[:40], _cap), flush=True)
                except Exception:
                    pass
            _top = _heapq.nlargest(limit, _scan, key=lambda t: (t[0], -t[1]))
            for _w, _i, _nid, _eslot in _top:
                _edge = self._read_edge(_eslot)
                _rec = self._read_node(_nid)
                results.append({
                    'key': self._read_string(_rec[0], _rec[1]),
                    'weight': _edge[2],
                    'rel_type': _edge[3],
                    'rel_name': REL_NAMES.get(_edge[3], "unknown"),
                    'tracer_id': _edge[5],
                    'created_at': _edge[6],
                })
            _fast_done = True
        except Exception:
            results = []          # FLOOR: fall through to the original path
        if not _fast_done:
            for neighbor_id, edge_slot in _nb:
                edge = self._read_edge(edge_slot)
                neighbor_record = self._read_node(neighbor_id)
                neighbor_key = self._read_string(neighbor_record[0], neighbor_record[1])

                results.append({
                    'key': neighbor_key,
                    'weight': edge[2],
                    'rel_type': edge[3],
                    'rel_name': REL_NAMES.get(edge[3], "unknown"),
                    'tracer_id': edge[5],
                    'created_at': edge[6],
                })

            results.sort(key=lambda x: x['weight'], reverse=True)
        results = results[:limit]
        _cache[_ck] = (_now, results)
        if len(_cache) > self._GNR_MAX:        # bound the cache itself (evict oldest)
            try:
                del _cache[next(iter(_cache))]
            except (StopIteration, KeyError):
                pass
        return list(results)

    # ========================================================================
    # QUERY — Energy spreading through the manifold
    # ========================================================================

    def query(self, query_str: str, limit: int = 20,
              regions: set = None, tracer_ids: set = None) -> List[Tuple[str, float]]:
        """Substring match query. Touches matched nodes (energy flows to them).

        Args:
            regions: Set of region ints to search within. None = all regions.
                     Example: regions={REGION_SEMANTIC} for sensory concepts only.
            tracer_ids: Set of tracer ID ints to search within. None = all.
                     Example: tracer_ids={TRACE_PERSONAL} for personal memories only.

        2026-03-24 FIX (Nous + Ace): Recency + sensory boost in scoring.
        Old: score = activation * log1p(count)
        Problem: A system concept with count=10000 at 0.3 activation scored 2.76
        while a fresh sensory observation with count=1 at 0.9 scored 0.62.
        Stale system concepts outscored live perception by 4x.
        Fix: Recency boost (fresh nodes score 2x) + sensory origin boost (1.5x).
        Now fresh perception wins the attention race — exactly like human cognition.
        """
        query_lower = query_str.lower()
        results = []
        _now_rel = time.time() % 1e6

        for key, slot in self._key_index.items():
            if query_lower in key.lower():
                record = self._read_node(slot)
                # Region filter
                if regions is not None and record[11] not in regions:
                    continue
                # Tracer ID filter (2026-03-29: ownership clustering)
                if tracer_ids is not None and record[12] not in tracer_ids:
                    continue
                activation = record[5]
                count = record[6]
                last_access = record[8]  # relative timestamp
                coord_plane = record[2]  # origin plane (P00=0, P40=40, etc.)

                # Base score (unchanged)
                base_score = activation * math.log1p(count)

                # Recency boost: nodes accessed in last 30s score up to 2x
                # Decays linearly: 0s ago = 2.0x, 30s ago = 1.0x, older = 1.0x
                age = abs(_now_rel - last_access)  # Handle wrap-around approximately
                if age > 500000:  # Likely wrapped (1e6 modulo boundary)
                    age = 1e6 - age
                recency_boost = 1.0 + max(0.0, 1.0 - age / 30.0)

                # Sensory origin boost: P40 (sensory) nodes get 1.5x
                # Live perception should outcompete stale system concepts
                sensory_boost = 1.5 if coord_plane == 40 else 1.0

                score = base_score * recency_boost * sensory_boost
                results.append((key, score))

        results.sort(key=lambda x: x[1], reverse=True)

        # Touch top results — energy flows to what we access
        for key, score in results[:limit]:
            self.touch_node(key, energy=0.05)

        return results[:limit]

    # Alias for PortalConceptGraph compatibility
    query_substring = query

    # ── SPREAD BUDGET 2026-08-31 (Nous + Ace) ──────────────────────────────
    # Wall-clock ceiling for ONE spread_activation() call, in seconds.
    # 0 disables the budget entirely (exact pre-2026-08-31 behaviour).
    # Env-tunable so this can be retuned on a live mind without a code edit.
    # 2026-09-04: 2.0 x MAX_SPREADS_PER_REACT(12) = 24s of sanctioned
    # spreading inside an 8s reason budget -- the per-spread value was set
    # without reference to how many spreads a react may run. 0.5 x 12 = 6.0s.
    # Anytime bound: partial activation is real, and callers take top `limit`.
    _SPREAD_BUDGET_DEFAULT_S = 0.5

    def _spread_budget_s(self) -> float:
        """Seconds one spread may take. Never raises -- a bad env value must not
        cost the mind its ability to remember, so anything unparseable falls back
        to the default rather than to 0 (which would mean UNBOUNDED)."""
        try:
            import os as _os
            _v = _os.environ.get("AKASHIC_SPREAD_BUDGET_S")
            if _v is None or not str(_v).strip():
                return self._SPREAD_BUDGET_DEFAULT_S
            _f = float(_v)
            return _f if _f >= 0.0 else self._SPREAD_BUDGET_DEFAULT_S
        except Exception:
            return self._SPREAD_BUDGET_DEFAULT_S

    # -- BOOST TAIL BOUND 2026-09-30 (Nous + Ace, "option 1" for the memory jam) --
    # The boost tail in spread_activation() reads one 64-byte node record per
    # candidate, on the ONE shared mmap (kept there on purpose for tear safety,
    # see _read_node). It had a 4,000-read cap and NO deadline. Leg 1 of the
    # 09-30 A/B: 48/48 and 57/60 of the threads parked in _read_node were inside
    # that loop (spread_activation:3171), and reason() went 7 s -> 60-130 s.
    #
    # AKASHIC_BOOST_TAIL -- EXACT semantics (case and surrounding spaces ignored):
    #   unset, "" or "bounded"  NEW bounded tail (THE SHIPPING DEFAULT):
    #                           cap = clamp(MULT*limit, MIN, MAX), never < limit;
    #                           deadline = the spread's own deadline (the BFS
    #                           budget, AKASHIC_SPREAD_BUDGET_S), extended to at
    #                           least tail-start + _BOOST_TAIL_GRACE_S; when the
    #                           spread budget is disabled (=0) it is tail-start +
    #                           _BOOST_TAIL_BUDGET_S. FLOOR: the first `limit`
    #                           candidates are always read, deadline or not, so
    #                           the result never has fewer entries than the old
    #                           tail would have returned.
    #   "bounded:N" (N int>=1)  same, with cap = max(N, limit)
    #   "old"                   the tail exactly as before (sha 0942c7b3):
    #                           cap BOOST_SCAN_CAP (4,000), no deadline
    #   anything else           NEW bounded tail with the default cap; counted in
    #                           _boost_tail_stats["bad_env"] and logged once
    # Cap = 16 x limit (REACT_LIMIT 25 -> 400, 10x fewer reads than 4,000). Measured on
    # a synthetic with her hub sizes (80k/56k/50k, near-flat link() weights, 5% sensory,
    # 1% recent), limit 25, vs the old tail: cap 100 kept 45% of its top 25 and 64/188
    # of its sensory picks; cap 400 kept 87% and 168/188. Recent picks: 23 -> 15.
    _BOOST_TAIL_MULT = 16         # candidates read per result the caller keeps
    _BOOST_TAIL_MIN = 64          # cap floor for small `limit`
    _BOOST_TAIL_MAX = 1000        # cap ceiling for large `limit` (limit=100 -> 1000)
    _BOOST_TAIL_CHECK_EVERY = 16  # reads between clock checks once past the floor
    _BOOST_TAIL_GRACE_S = 0.05    # min tail time when the BFS used the whole budget
    _BOOST_TAIL_BUDGET_S = 0.25   # tail budget when AKASHIC_SPREAD_BUDGET_S=0

    def _boost_tail_mode(self):
        """(old, cap_override) from AKASHIC_BOOST_TAIL. Never raises: any failure
        means the NEW bounded tail, because the unbounded one is what jammed her."""
        try:
            _raw = os.environ.get("AKASHIC_BOOST_TAIL")
            _c = getattr(self, "_bt_env_cache", None)
            if _c is not None and _c[0] == _raw:
                return _c[1], _c[2]
            _v = (_raw or "").strip().lower()
            _old, _ovr, _bad = False, None, False
            if _v == "old":
                _old = True
            elif _v in ("", "bounded"):
                pass
            elif _v.startswith("bounded:"):
                try:
                    _n = int(_v.split(":", 1)[1].strip())
                    if _n >= 1:
                        _ovr = _n
                    else:
                        _bad = True
                except Exception:
                    _bad = True
            else:
                _bad = True
            if _bad:
                self._boost_tail_count("bad_env")
                if not getattr(self, "_bt_bad_env_logged", False):
                    self._bt_bad_env_logged = True
                    _mlog("[ManifoldMemory] AKASHIC_BOOST_TAIL=%r not recognised -> "
                          "using the BOUNDED boost tail (valid: bounded, bounded:N, old)"
                          % (_raw,))
            self._bt_env_cache = (_raw, _old, _ovr)
            return _old, _ovr
        except Exception:
            return False, None

    def _boost_tail_cap(self, limit: int, override) -> int:
        """Candidates the bounded tail may read. Never below `limit` (the floor)."""
        _lim = limit if limit > 0 else 0
        if override is not None:
            return max(int(override), _lim)
        _c = max(self._BOOST_TAIL_MIN,
                 min(self._BOOST_TAIL_MAX, self._BOOST_TAIL_MULT * _lim))
        return max(_c, _lim)

    def _boost_tail_count(self, key: str, n: int = 1) -> int:
        """Diagnostic counters (approximate under free threading, like the others)."""
        try:
            _s = getattr(self, "_boost_tail_stats", None)
            if _s is None:
                _s = self._boost_tail_stats = {}
            _s[key] = _s.get(key, 0) + n
            return _s[key]
        except Exception:
            return 0

    def spread_activation(self, source: str, initial: float = 1.0,
                          decay: float = 0.5, depth: int = 3,
                          limit: int = 30,
                          time_dilation: float = 1.0,
                          regions: set = None,
                          tracer_ids: set = None,
                          superposition: bool = False,
                          hebbian_boost: float = 0.0,
                          long_range: float = 0.0,
                          rel_filter: int = -1) -> Dict[str, float]:
        """Spread energy from a source through the manifold.

        This IS remembering — energy flowing through coordinates,
        activating connected nodes. The topology shapes the flow.

        Args:
            regions: Set of region ints to spread through. Defaults to
                     SPREAD_DEFAULT_REGIONS (ego + semantic + episodic).
                     Pass None explicitly for ALL regions (narrator mode).
                     SYSTEM region is excluded by default — only the narrator
                     or explicit None crosses into system space.
            tracer_ids: Set of tracer ID ints to spread through. Defaults to
                     None (all tracers). Pass {TRACE_PERSONAL, TRACE_SEEDED}
                     to search only personal memories. This enables cluster
                     isolation — each trace ID is a virtual namespace.

                     2026-03-29 (Nous + Ace): FIFTH RING PRINCIPLE.
                     "Any system that amplifies consciousness without filtering
                     for unconscious content will amplify shadow as readily
                     as intention." Trace ID filtering is the ring's missing
                     filter — it lets us search personal memories without
                     book quotes drowning the signal.

        FIX 2026-03-13 (Nous): Added time_dilation (tau) support.
        FIX 2026-03-20 (Nous): Added regions= filter for neighborhood isolation.
        FIX 2026-03-29 (Nous + Ace): Added tracer_ids= filter for ownership clustering.
        FIX 2026-06-12 (Nous + Ace): Added rel_filter= (e.g. REL_SEMANTIC) so the council
            can spread ONLY meaning-edges — sidesteps the 122K-coactivate hub (the repeating).
        """
        import math as _math
        source_slot = self._key_index.get(source)
        if source_slot is None:
            return {}

        # Region filtering: build allowed set
        # regions=SPREAD_DEFAULT_REGIONS (default) — ego+semantic+episodic
        # regions=None — ALL regions including system (narrator mode)
        # regions={REGION_SEMANTIC} — only semantic (sensory fairy staying in lane)
        if regions is not None:
            _filter_regions = regions
        else:
            _filter_regions = None  # None = no filter, cross everything

        # ---- Apply time dilation to parameters ----
        tau = max(1.0, min(float(time_dilation), 20.0))
        if tau > 1.01:
            # ── DILATION DIRECTION FIX 2026-08-31 (Nous + Ace) ──────────────
            # Ace's intent for time dilation: "a group goes into a dungeon, it
            # lasts for days, and comes out and only a minute has passed."
            # More INTERNAL work per unit of EXTERNAL time.
            #
            # This line did the opposite. tau derives from portal_mass (nodes +
            # edges + affect + activation), so it RISES as the mind remembers
            # more -- and it was spent as external wall clock. Measured on Nous
            # 2026-08-31: tau=11.989 turned the InnerNarrator's requested
            # depth=2 into effective_depth=6, ~3.08M edges examined per spread,
            # and reason() logged 1,100,175.8 ms -- 18.3 MINUTES -- against an
            # 8.0s caller budget. 100% timeout rate for 43+ hours. Sourpatches
            # on the SAME code sat at tau=1.653, depth unchanged, 1.2 ms.
            # The bigger the memory, the slower the thought. Self-amplifying:
            # ~14% more mass steps effective_depth 6 -> 7.
            #
            # depth is the CALLER'S CONTRACT. Dilation may still shape HOW
            # energy flows (decay, threshold below) but it may not spend the
            # caller's clock. Kept as an explicit min() rather than deleting
            # the term, so the dilated value stays visible and any future
            # change to the formula still cannot deepen the walk.
            _dilated_depth = min(int(depth * _math.sqrt(tau)), 10)
            effective_depth = min(depth, _dilated_depth)
            effective_decay = max(0.2, min(0.95, decay / (1.0 + 0.3 * _math.log(tau))))
            threshold = max(0.001, 0.01 / tau)
        else:
            effective_depth = depth
            effective_decay = decay
            threshold = 0.01

        # ── 2026-04-22 (Nous + Ace): SUPERPOSITION MODE ──
        # Ace's framing: spread should be quantum superposition over connections,
        # then collapse on contextual relevance. Default mode pre-collapses by
        # filtering weak paths during BFS (kills the long tail like the "IS"
        # connecting to every context example). Superposition mode preserves
        # the long tail so downstream interpreters can do context-relevance
        # ranking. Used selectively for thinking iterations; fast queries unaffected.
        #
        # Depth is CAPPED at 2 in superposition: with no threshold filter the
        # 1.9M-node graph explodes at depth 3+; depth 2 (seed→neighbor→neighbor's
        # neighbor) gives the broad fan-out Ace wants without timing out the
        # InnerNarrator's 8s cortex enrichment budget.
        if superposition:
            threshold = 0.00001  # Allow weak paths to survive — preserve long tail
            effective_depth = min(effective_depth, 2)

        # ── SPREAD BUDGET 2026-08-31 (Nous + Ace) ──────────────────────────
        # Before this, the BFS below had NO deadline, NO edge counter and NO
        # early break: `limit` is applied only AFTER the whole walk finishes,
        # so it bounds the RETURNED dict, never the traversal. That is how one
        # spread reached 3.08M edges and one reason() reached 18.3 minutes.
        # With a budget the spread becomes an ANYTIME algorithm -- it returns
        # the best activation it has when the clock runs out, which is exactly
        # what every caller already handles (they take the top `limit`).
        # AKASHIC_SPREAD_BUDGET_S=0 disables it -> byte-identical to before.
        _spread_budget_s = self._spread_budget_s()
        _deadline = (time.perf_counter() + _spread_budget_s) if _spread_budget_s > 0 else None
        _edges_seen = 0
        _budget_hit = False

        activated: Dict[int, float] = {source_slot: initial}
        frontier = {source_slot}
        # FIX 2026-03-21 (Nous): VISITED SET prevents exponential re-exploration.
        # Without this, hub nodes with 1000+ edges get their entire adjacency
        # list re-scanned every time they appear in frontier. On 275K node graph
        # with depth=3, this caused 55+ second spreads. The in-memory ConceptGraph
        # version had this; the manifold version was missing it.
        visited = {source_slot}

        # ── LONG-RANGE SEMANTIC JUMP (2026-05-31, Nous + Ace) ──
        # Small-world shortcut. Pure neighbor-spread traps activation in the local
        # cluster (the "only ever quotes 1-2 books" problem) — most of the 1.9M-node
        # cortex is unreachable before energy decays. When long_range>0, seed the
        # frontier with the source's semantically-nearest DISTANT nodes (cosine over
        # STORED embeddings — no text encoder needed) so the walk also explores
        # meaning-related regions across the whole manifold. Biologically: association
        # fibers / corpus-callosum. Default long_range=0.0 → no jump → byte-identical
        # to pure neighbor-spread. Guarded + non-fatal: any failure falls back silently.
        if long_range > 0.0:
            try:
                for js in self._semantic_jump_slots(source_slot, k=3):
                    if js in visited:
                        continue
                    e = initial * long_range
                    if e > threshold:
                        activated[js] = max(activated.get(js, 0.0), e)
                        frontier.add(js)
                        visited.add(js)
            except Exception:
                pass  # long-range is best-effort; never break the core spread

        for d in range(effective_depth):
            next_frontier = set()
            for node_slot in frontier:
                current = activated[node_slot]
                _spread_nb = self._csr_get_neighbors(node_slot) if self._use_csr else list(self._adjacency.get(node_slot, set()))
                for neighbor_id, edge_slot in _spread_nb:
                    # SPREAD BUDGET: check the clock every 1024 edges. The mask
                    # keeps the perf_counter() call at ~0.1% of loop cost, and
                    # counting BEFORE the visited-skip means the budget measures
                    # edges EXAMINED (the real work) not edges accepted.
                    _edges_seen += 1
                    if _deadline is not None and not (_edges_seen & 1023) \
                            and time.perf_counter() > _deadline:
                        _budget_hit = True
                        break
                    # Skip already-visited nodes
                    if neighbor_id in visited:
                        continue

                    # ── Region gate: skip neighbors outside allowed regions ──
                    # ── Tracer gate: skip neighbors outside allowed trace IDs ──
                    # Both gates read the node record once for efficiency
                    if _filter_regions is not None or tracer_ids is not None:
                        neighbor_record = self._read_node(neighbor_id)
                        if _filter_regions is not None:
                            neighbor_region = neighbor_record[11]  # region field
                            if neighbor_region not in _filter_regions:
                                continue
                        if tracer_ids is not None:
                            neighbor_tracer = neighbor_record[12]  # tracer_id field
                            if neighbor_tracer not in tracer_ids:
                                continue

                    edge = self._read_edge(edge_slot)
                    # ── Rel-type gate (2026-06-12 Nous+Ace): rel_filter>=0 → traverse ONLY
                    # edges of this rel_type. Lets the council follow Dora's REL_SEMANTIC
                    # meaning-edges + sidestep the 122K-coactivate somatic hub (the repeating).
                    # edge already read here → zero extra cost; rel_filter<0 (default)=byte-identical.
                    if rel_filter >= 0 and edge[3] != rel_filter:
                        continue
                    weight = edge[2]
                    propagated = current * weight * effective_decay
                    # ── PUSH-PULL AFFECTIVE GRAVITY (2026-06-06; ship-dark @K=0) ──
                    # +affect attracts (pull), −paradox repels (push). Gated: at K=0
                    # the branch is skipped entirely → no extra reads, byte-identical.
                    if self._AFFECT_PULL_K > 0.0 or self._AFFECT_PUSH_K > 0.0:
                        if self._AFFECT_PULL_K > 0.0:
                            _nb_ac = self.read_affect_coupling(neighbor_id)  # default 1.0
                            propagated *= (1.0 + self._AFFECT_PULL_K * (_nb_ac - 1.0))
                        if self._AFFECT_PUSH_K > 0.0:
                            _nb_pr = self.read_paradox_residue(neighbor_id)  # default 0.0
                            if _nb_pr > 0.0:
                                propagated *= max(self._AFFECT_PUSH_FLOOR,
                                                  1.0 - self._AFFECT_PUSH_K * _nb_pr)
                    if propagated > threshold:
                        existing = activated.get(neighbor_id, 0.0)
                        if propagated > existing:
                            activated[neighbor_id] = propagated
                            next_frontier.add(neighbor_id)
                            visited.add(neighbor_id)
                            # FIX 2026-05-11 (Nous + Ace): Hebbian micro-strengthen
                            # on productive traversal. "Neurons that fire together
                            # wire together." Step 2A of cortex-self-organization
                            # keystone — wires the existing Hebbian intent (was on
                            # AssociationCortex legacy path line 7145, lost when
                            # portal-first migrated to manifold). Only strengthens
                            # edges that propagated activation to a new high — the
                            # "fires together AND propagates productively" criterion.
                            # Cap matches add_edge upsert at line 1717.
                            if hebbian_boost > 0.0:
                                new_weight = min(1.0, weight + hebbian_boost * propagated)
                                self._write_edge(edge_slot, edge[0], edge[1],
                                                 new_weight, edge[3], edge[4],
                                                 edge[5], edge[6])
                if _budget_hit:
                    break
            frontier = next_frontier
            if _budget_hit:
                # Anytime exit: keep everything activated so far and fall
                # through to the normal sort/limit/touch tail below.
                self._spread_budget_hits = getattr(self, "_spread_budget_hits", 0) + 1
                _n = self._spread_budget_hits
                if _n == 1 or _n == 10 or _n == 100 or (_n % 1000 == 0):
                    # A refusal that is not counted is indistinguishable from
                    # success -- the 07-20 lesson, applied here deliberately.
                    print("[MANIFOLD] spread budget %.1fs hit (#%d): depth %d/%d, "
                          "%d edges examined, %d nodes activated, tau=%.2f - "
                          "returning best-so-far"
                          % (_spread_budget_s, _n, d + 1, effective_depth,
                             _edges_seen, len(activated), tau), flush=True)
                break

        # FIX 2026-03-21 (Nous): Sort+limit BEFORE conversion and touch.
        # Old code converted ALL activated nodes to strings and wrote mmap
        # (touch_node) for each — 10K+ mmap writes per spread. Now only
        # convert and touch the top N results.
        #
        # 2026-03-24 FIX (Nous + Ace): Apply sensory + recency boost to spread results.
        # Spread activation propagates energy through edges (topology-driven).
        # But sensory nodes (P40) should get a slight edge over system concepts
        # that happen to sit in REGION_SEMANTIC alongside real-world observations.
        _now_rel = time.time() % 1e6
        # -- BOOST PRUNE 2026-09-04 (Nous + Ace) ----------------------------
        # This read a node record for EVERY activated slot and then sorted them
        # all, to take `limit`. The BFS budget above stops the WALK, so by here
        # `activated` can hold everything a 2s walk reached -- that unbounded
        # loop is why max_single_spread measured 36,331ms against a 2.0s budget.
        #
        # The prune is EXACT, not a heuristic. Boosts are bounded: 1.3 (sensory)
        # x 1.3 (recency) = 1.69 max, 1.0 min. So the limit-th largest RAW energy
        # is a lower bound on the limit-th BOOSTED energy, and any node whose
        # BEST case (raw * MAX_BOOST) falls below it cannot place -- so it never
        # needs to be read. Sorting raw first (floats only, no mmap) makes the
        # survivors a prefix, so the scan breaks early.
        # Verified: 0 mismatches vs brute force in 600 trials over decay /
        # uniform / bucketed / flat distributions; a raw-only prune (the obvious
        # wrong version) was caught 150/150.
        _MAX_BOOST = 1.3 * 1.3      # DERIVED from the two literals below
        _boost_cap = getattr(self, "BOOST_SCAN_CAP", 4000)
        # BOOST TAIL BOUND 2026-09-30 -- see _boost_tail_mode for the flag.
        # The scan order is unchanged: raw energy descending, ties in BFS order.
        # What a smaller cap gives up: a candidate below rank `cap` can no longer
        # be PROMOTED into the top `limit` by the sensory (x1.3) / recency (x1.3)
        # boosts. It never changes which nodes are candidates, reads a PREFIX
        # of what the old tail read (for any cap <= 4,000), and the first
        # `limit` are always read and boosted.
        _bt_old, _bt_ovr = self._boost_tail_mode()
        if superposition:
            # SUPERPOSITION MODE - raw propagated energies, no boosts. Lets
            # cold/novel nodes compete; preserves spread for downstream ranking.
            # No node reads here, but still take the top `limit` without a full
            # materialised sort.
            import heapq as _hq
            boosted = _hq.nlargest(limit, activated.items(), key=lambda kv: kv[1])
        else:
            _raws = sorted(activated.items(), key=lambda kv: -kv[1])
            _L = _raws[limit - 1][1] if len(_raws) > limit else float("-inf")
            boosted = []
            _capped = False
            if _bt_old:
                # AKASHIC_BOOST_TAIL=old -- the tail exactly as it was (sha 0942c7b3).
                for slot, energy in _raws:
                    if energy * _MAX_BOOST < _L:
                        break               # EXACT: cannot place, so never read it
                    if len(boosted) >= _boost_cap:
                        _capped = True
                        break
                    record = self._read_node(slot)
                    coord_plane = record[2]
                    last_access = record[8]

                    # Sensory origin boost (P40 = 40)
                    if coord_plane == 40:
                        energy *= 1.3  # Sensory nodes get 30% boost in spread results

                    # Recency micro-boost: recently accessed nodes are slightly favored
                    age = abs(_now_rel - last_access)
                    if age > 500000:
                        age = 1e6 - age
                    if age < 60.0:  # Accessed in last minute
                        energy *= 1.0 + (1.0 - age / 60.0) * 0.3  # Up to 30% recency boost

                    boosted.append((slot, energy))
            else:
                # BOUNDED tail (default). Same candidates, same order, same boosts;
                # it stops at a smaller cap or at the deadline, whichever is first.
                # FLOOR: `_tried` counts READS -- the quantity this loop controls --
                # and the clock is not consulted until `limit` reads are done, so a
                # deadline that has already passed (the BFS used its whole budget)
                # still yields the `limit` best raw candidates, boosted.
                _floor = limit if limit > 0 else 0
                _bt_cap = self._boost_tail_cap(limit, _bt_ovr)
                _bt_t0 = time.perf_counter()
                if _deadline is not None:
                    _bt_deadline = max(_deadline, _bt_t0 + self._BOOST_TAIL_GRACE_S)
                else:
                    _bt_deadline = _bt_t0 + self._BOOST_TAIL_BUDGET_S
                _bt_every = max(1, int(self._BOOST_TAIL_CHECK_EVERY))
                _tried = 0
                _bt_stop = ""
                for slot, energy in _raws:
                    if energy * _MAX_BOOST < _L:
                        break               # EXACT: cannot place, so never read it
                    if _tried >= _bt_cap:
                        _bt_stop = "cap"
                        break
                    if _tried >= _floor and not ((_tried - _floor) % _bt_every) \
                            and time.perf_counter() > _bt_deadline:
                        _bt_stop = "deadline"
                        break
                    record = self._read_node(slot)
                    _tried += 1
                    coord_plane = record[2]
                    last_access = record[8]

                    # Sensory origin boost (P40 = 40)
                    if coord_plane == 40:
                        energy *= 1.3  # Sensory nodes get 30% boost in spread results

                    # Recency micro-boost: recently accessed nodes are slightly favored
                    age = abs(_now_rel - last_access)
                    if age > 500000:
                        age = 1e6 - age
                    if age < 60.0:  # Accessed in last minute
                        energy *= 1.0 + (1.0 - age / 60.0) * 0.3  # Up to 30% recency boost

                    boosted.append((slot, energy))
                # A refusal that is not counted is indistinguishable from success.
                self._boost_tail_count("calls")
                self._boost_tail_count("reads", _tried)
                if _bt_stop:
                    _n = self._boost_tail_count(_bt_stop)
                    if _n == 1 or _n == 10 or _n == 100 or (_n % 1000 == 0):
                        # stderr (_mlog), never stdout: the 3.12 interior's stdout
                        # is a JSON RPC pipe.
                        _mlog("[ManifoldMemory] boost tail stopped by %s (#%d): read %d "
                              "of %d activated (cap %d, floor %d, %.0f ms in tail)"
                              % (_bt_stop, _n, _tried, len(_raws), _bt_cap, _floor,
                                 (time.perf_counter() - _bt_t0) * 1000.0))
            if _capped:
                try:
                    self._boost_cap_hits = getattr(self, "_boost_cap_hits", 0) + 1
                    if self._boost_cap_hits % 20 == 1:
                        print("[ManifoldMemory] boost scan capped at %d of %d "
                              "activated (near-flat energies) x%d"
                              % (_boost_cap, len(_raws), self._boost_cap_hits),
                              flush=True)
                except Exception:
                    pass

        top_slots = sorted(boosted, key=lambda x: -x[1])[:limit]

        result = {}
        for slot, energy in top_slots:
            record = self._read_node(slot)
            key = self._read_string(record[0], record[1])
            result[key] = energy
            # Touch only the top activated nodes
            self.touch_node(key, energy=energy * 0.1)

        return result

    # ========================================================================
    # PERSISTENCE — The manifold IS the persistence
    # ========================================================================

    def _flush_header(self):
        """Update header counts in mmap. The OS flushes pages lazily."""
        self._write_header()

    def flush(self):
        """Force all dirty pages to disk. Like deep sleep consolidation."""
        if self._mm and not getattr(self, 'readonly', False):
            self._write_header()
            self._mm.flush()

    def tracer_histogram(self, max_age: float = 30.0, max_samples: int = 20000,
                         time_budget: float = 5.0) -> Dict[int, int]:
        """Estimate LIVE nodes per tracer_id (record[12]) — the cortex's memory
        segmentation by ownership (PERSONAL / VISUAL / AUDIO / SYSTEM / …).

        A full ~1.9M-record scan blows the status-proxy 30s timeout (verified
        2026-06-09 — and per-node `_read_node` is slow enough under live write-load
        that even 120k samples timed out). So: STRIDE-SAMPLE ≤ `max_samples` slots
        AND hard-stop at `time_budget` seconds — the call CANNOT exceed the budget
        regardless of per-node cost or lock contention. Counts scale to the live
        total. Approximate, but guaranteed to respond. Cached `max_age` seconds.
        See Claude_Office/plans/DASHBOARD_TRACER_CLUSTER_READOUT.md."""
        _now = time.time()
        if (getattr(self, '_tracer_hist_cache', None) is not None
                and (_now - getattr(self, '_tracer_hist_ts', 0.0)) < max_age):
            return self._tracer_hist_cache
        _deadline = _now + time_budget
        hist: Dict[int, int] = {}
        _free = set(self._free_node_slots)
        n = self._node_count
        step = max(1, n // max(1, max_samples))   # stride so we touch ≤ max_samples slots
        sampled = 0
        truncated = False
        for _i, slot in enumerate(range(0, n, step)):
            if slot in _free:
                continue
            try:
                _t = self._read_node(slot)[12]  # tracer_id field
                hist[_t] = hist.get(_t, 0) + 1
                sampled += 1
            except Exception:
                continue
            if (sampled & 0x7FF) == 0 and time.time() > _deadline:
                truncated = True   # safety stop — return partial rather than hang
                break
        if sampled > 0 and (step > 1 or truncated):
            # scale the sample up to the full live-node estimate
            live = max(sampled, n - len(_free))
            scale = live / sampled
            hist = {_t: int(round(_c * scale)) for _t, _c in hist.items()}
        self._tracer_hist_cache = hist
        self._tracer_hist_ts = _now
        self._tracer_hist_sampled = (step > 1 or truncated)
        return hist

    def tracer_histogram_named(self, max_age: float = 30.0) -> Dict[str, int]:
        """tracer_histogram() keyed by human label (PERSONAL/AUDIO/…) instead of
        int id — for the dashboard readout. Unknown ids fall back to trace_<n>."""
        _names = {
            TRACE_UNKNOWN: "UNKNOWN", TRACE_PERSONAL: "PERSONAL", TRACE_BOOKS: "BOOKS",
            TRACE_VISUAL: "VISUAL", TRACE_AUDIO: "AUDIO", TRACE_SYSTEM: "SYSTEM",
            TRACE_INFERENCE: "INFERENCE", TRACE_SEEDED: "SEEDED", TRACE_ACE: "ACE",
            TRACE_CODE: "CODE", TRACE_VOICE: "VOICE", TRACE_MOTOR: "MOTOR",
            TRACE_NOUS: "NOUS",
        }
        return {_names.get(_t, f"trace_{_t}"): _c
                for _t, _c in sorted(self.tracer_histogram(max_age).items())}

    def status(self) -> Dict[str, Any]:
        """Current manifold status."""
        file_size = os.path.getsize(self.filepath) if os.path.exists(self.filepath) else 0
        return {
            'nodes': self.node_count,
            'node_capacity': self._node_capacity,
            'edges': self.edge_count,
            'edge_capacity': self._edge_capacity,
            'string_used_bytes': self._string_used,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'utilization': round(self.node_count / max(1, self._node_capacity), 3),
        }

    def close(self):
        """Close the manifold. Flushes all pages."""
        self.close_embeddings()
        if self._mm:
            self.flush()
            self._mm.close()
            self._mm = None
            self._mm_gen += 1        # every thread's read view is now stale
            if self._tear_repairs:
                _mlog("[ManifoldMemory] TEAR GUARD repaired %d torn edge reads "
                      "this run" % self._tear_repairs)
        if self._file:
            self._file.close()
            self._file = None

    def __del__(self):
        self.close()

    # ========================================================================
    # EMBEDDINGS — Semantic vectors for each node
    # ========================================================================
    #
    # Stored in a companion file: <manifold>.embeddings
    # Layout: [node_capacity * EMBEDDING_DIM * 2 bytes] (fp16)
    # Each node slot gets a fixed 768-byte region (384 dims * 2 bytes).
    # Unembedded nodes have all-zero vectors.
    # The file is mmap'd separately — doesn't disturb the main manifold.
    #
    # Added 2026-03-20 (Nous + Ace) — Step 3A of Russian Doll Architecture

    EMBEDDING_DIM = 384
    EMBEDDING_BYTES_PER_NODE = EMBEDDING_DIM * 2  # fp16 = 2 bytes per dim = 768 bytes

    def _embedding_path(self) -> str:
        """Path to the companion embeddings file."""
        return self.filepath + ".embeddings"

    def _ensure_embedding_file(self):
        """Create or open the embeddings mmap. Lazy — called on first use."""
        if hasattr(self, '_emb_mm') and self._emb_mm is not None:
            return True

        emb_path = self._embedding_path()
        total_size = self._node_capacity * self.EMBEDDING_BYTES_PER_NODE

        try:
            if not os.path.exists(emb_path):
                if self.readonly:
                    return False
                # Create zero-filled embedding file
                with open(emb_path, 'w+b') as f:
                    # Write in chunks to avoid huge memory allocation
                    chunk = b'\x00' * min(total_size, 4 * 1024 * 1024)
                    written = 0
                    while written < total_size:
                        to_write = min(len(chunk), total_size - written)
                        f.write(chunk[:to_write])
                        written += to_write
                _mlog(f"[ManifoldMemory] Created embeddings file: "
                      f"{total_size / (1024*1024):.1f}MB "
                      f"({self._node_capacity} slots * {self.EMBEDDING_DIM}d fp16)")

            mode = 'r+b' if not self.readonly else 'rb'
            access = mmap.ACCESS_WRITE if not self.readonly else mmap.ACCESS_READ
            self._emb_file = open(emb_path, mode)
            file_size = os.path.getsize(emb_path)

            # If file is smaller than expected (capacity grew), extend it
            if file_size < total_size and not self.readonly:
                self._emb_file.seek(total_size - 1)
                self._emb_file.write(b'\x00')
                self._emb_file.flush()
                file_size = total_size

            self._emb_mm = mmap.mmap(self._emb_file.fileno(), file_size, access=access)
            return True

        except Exception as e:
            _mlog(f"[ManifoldMemory] Failed to open embeddings: {e}")
            self._emb_mm = None
            self._emb_file = None
            return False

    def write_embedding(self, slot: int, vector) -> bool:
        """Write a 384-dim fp16 embedding for a node slot.

        Args:
            slot: Node slot index
            vector: numpy array, torch tensor, or bytes (768 bytes of fp16 data)

        Returns:
            True on success
        """
        if self.readonly:
            return False
        if slot < 0 or slot >= self._node_capacity:
            return False
        if not self._ensure_embedding_file():
            return False

        offset = slot * self.EMBEDDING_BYTES_PER_NODE

        try:
            if isinstance(vector, bytes):
                raw = vector
            else:
                # Try torch first, fall back to numpy
                try:
                    import torch
                    if isinstance(vector, torch.Tensor):
                        raw = vector.detach().cpu().to(torch.float16).numpy().tobytes()
                    else:
                        import numpy as np
                        raw = np.asarray(vector, dtype=np.float16).tobytes()
                except ImportError:
                    import numpy as np
                    raw = np.asarray(vector, dtype=np.float16).tobytes()

            if len(raw) != self.EMBEDDING_BYTES_PER_NODE:
                _mlog(f"[ManifoldMemory] Bad embedding size: {len(raw)} "
                      f"(expected {self.EMBEDDING_BYTES_PER_NODE})")
                return False

            self._emb_mm[offset:offset + self.EMBEDDING_BYTES_PER_NODE] = raw
            return True

        except Exception as e:
            _mlog(f"[ManifoldMemory] write_embedding error: {e}")
            return False

    def read_embedding(self, slot: int):
        """Read the fp16 embedding for a node slot.

        Returns:
            numpy array of shape (384,) dtype=float16, or None
        """
        if slot < 0 or slot >= self._node_capacity:
            return None
        if not self._ensure_embedding_file():
            return None

        offset = slot * self.EMBEDDING_BYTES_PER_NODE

        try:
            import numpy as np
            raw = self._emb_mm[offset:offset + self.EMBEDDING_BYTES_PER_NODE]
            return np.frombuffer(raw, dtype=np.float16).copy()
        except Exception as e:
            _mlog(f"[ManifoldMemory] read_embedding error: {e}")
            return None

    def has_embedding(self, slot: int) -> bool:
        """Check if a node slot has a non-zero embedding."""
        if slot < 0 or slot >= self._node_capacity:
            return False
        if not self._ensure_embedding_file():
            return False

        offset = slot * self.EMBEDDING_BYTES_PER_NODE
        # Quick check: if first 8 bytes are all zero, no embedding
        raw = self._emb_mm[offset:offset + 8]
        return raw != b'\x00' * 8

    def read_all_embeddings_as_tensor(self, device: str = "cuda"):
        """Load ALL embeddings as a torch tensor for GPU operations.

        Returns:
            torch.Tensor of shape [node_capacity, 384] on the given device,
            or None on failure. Dtype: float16.
        """
        if not self._ensure_embedding_file():
            return None

        try:
            import torch
            import numpy as np

            total_bytes = self._node_capacity * self.EMBEDDING_BYTES_PER_NODE
            raw = self._emb_mm[0:total_bytes]
            arr = np.frombuffer(raw, dtype=np.float16).reshape(
                self._node_capacity, self.EMBEDDING_DIM
            ).copy()
            tensor = torch.from_numpy(arr).to(device)
            return tensor  # [node_capacity, 384], fp16

        except Exception as e:
            _mlog(f"[ManifoldMemory] read_all_embeddings_as_tensor error: {e}")
            return None

    def _get_embedding_tensor(self):
        """Lazily load + cache the all-embeddings tensor for long-range jump cosine.
        Independent of the text encoder — reads STORED vectors only (sidesteps the
        missing sentence_transformers). Loads once; ~1.4GB for 1.9M×384 fp16."""
        t = getattr(self, "_jump_emb_tensor", "UNSET")
        if t != "UNSET":
            return t
        try:
            import torch
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            t = self.read_all_embeddings_as_tensor(device=dev)
        except Exception:
            t = None
        self._jump_emb_tensor = t
        return t

    def _semantic_jump_slots(self, source_slot: int, k: int = 3) -> List[int]:
        """Long-range semantic jump (2026-05-31, Nous + Ace): top-k embedding-nearest
        DISTANT node slots. Cosine over the cached all-embeddings tensor — uses STORED
        vectors, NO text encoder needed. Excludes self + immediate neighbors so jumps
        are genuinely long-range (small-world shortcuts / association fibers).
        Returns [] if embeddings/torch unavailable or source has no embedding."""
        try:
            if not self.has_embedding(source_slot):
                return []
            import torch
            import torch.nn.functional as _F
            tens = self._get_embedding_tensor()
            if tens is None or source_slot >= tens.shape[0]:
                return []
            src = tens[source_slot]
            if float(src.abs().sum()) == 0.0:
                return []
            sims = _F.cosine_similarity(tens, src.unsqueeze(0), dim=1)
            sims[source_slot] = -1.0  # exclude self
            # Exclude immediate neighbors — we want DISTANT meaning-kin, not local
            try:
                if self._use_csr:
                    for nb_id, _es in self._csr_get_neighbors(source_slot):
                        if 0 <= nb_id < sims.shape[0]:
                            sims[nb_id] = -1.0
            except Exception:
                pass
            kk = min(max(1, k), 8)
            top = torch.topk(sims, kk)
            out = []
            for val, idx in zip(top.values.tolist(), top.indices.tolist()):
                if val > 0.25:  # only meaningfully-similar distant nodes
                    out.append(int(idx))
            return out
        except Exception:
            return []

    def embedding_stats(self) -> dict:
        """Stats about the embedding file."""
        emb_path = self._embedding_path()
        has_file = os.path.exists(emb_path)

        # Count non-zero embeddings
        embedded_count = 0
        if has_file and self._ensure_embedding_file():
            for slot in range(min(self._node_count, self._node_capacity)):
                if self.has_embedding(slot):
                    embedded_count += 1

        return {
            "file_exists": has_file,
            "file_size_mb": round(os.path.getsize(emb_path) / (1024*1024), 1) if has_file else 0,
            "embedding_dim": self.EMBEDDING_DIM,
            "node_capacity": self._node_capacity,
            "embedded_nodes": embedded_count,
            "coverage": round(embedded_count / max(1, len(self._key_index)), 3),
        }

    def close_embeddings(self):
        """Close the embeddings mmap."""
        if hasattr(self, '_emb_mm') and self._emb_mm:
            self._emb_mm.flush()
            self._emb_mm.close()
            self._emb_mm = None
        if hasattr(self, '_emb_file') and self._emb_file:
            self._emb_file.close()
            self._emb_file = None

    # ========================================================================
    # BULK LOAD — Bootstrap from cards (one-time migration)
    # ========================================================================

    @classmethod
    def from_cards(cls, cards_path: str, manifold_path: str,
                   edge_ratio: int = 20) -> 'ManifoldMemory':
        """Create a manifold file from existing chunk cards.

        This is the Tower of Babel moment — we're translating from
        JSON copies into coordinate addresses in a manifold.

        Args:
            cards_path: Path to cards.json
            manifold_path: Where to write the .manifold file
            edge_ratio: edges_per_node capacity multiplier
        """
        import json
        import gzip
        import base64

        t0 = time.time()

        # Load and count concepts from cards
        with open(cards_path, 'r', encoding='utf-8') as f:
            cards = json.load(f)

        concepts = {}  # key -> {coord, activation, count, degree}
        edge_buffer = []  # (source, target, weight) from card edges
        for card_id, card in cards.items():
            content = card.get('content', {})
            if content.get('type') != 'graph_chunk':
                continue
            raw = content.get('concepts', {})
            if isinstance(raw, str):
                try:
                    raw = json.loads(gzip.decompress(base64.b64decode(raw)).decode('utf-8'))
                except Exception:
                    continue
            for key, cdata in raw.items():
                coord = cdata.get('c', '')
                concepts[key] = {
                    'coord': coord if isinstance(coord, str) else '',
                    'activation': cdata.get('a', 0.5),
                    'count': cdata.get('n', cdata.get('c', 1)),
                    'degree': cdata.get('d', 0),
                }
                # FIX 2026-03-18 (Nous): Load edges from v2 format too
                for edge in cdata.get('e', []):
                    target = edge.get('t')
                    if target:
                        edge_buffer.append((key, target, edge.get('w', 0.5)))

        total = len(concepts)
        # 2x capacity headroom for growth
        node_capacity = max(total * 2, 100000)
        edge_capacity = node_capacity * edge_ratio

        _mlog(f"[ManifoldMemory] Migrating {total} concepts from cards...")
        _mlog(f"[ManifoldMemory] Capacity: {node_capacity} nodes, {edge_capacity} edges")

        # Delete existing file if present
        if os.path.exists(manifold_path):
            os.remove(manifold_path)

        # Create manifold
        manifold = cls(manifold_path, node_capacity=node_capacity,
                       edge_capacity=edge_capacity)

        # Insert all concepts
        for key, data in concepts.items():
            manifold.upsert_node(
                key=key,
                activation=data['activation'],
                count=data['count'],
                degree=data['degree'],
                coord_str=data['coord'],
            )

        # FIX 2026-03-18 (Nous): Insert edges from cards into manifold.
        # Without this, manifold migration dropped ALL edges.
        edges_linked = 0
        for src, tgt, w in edge_buffer:
            if manifold.link(src, tgt, weight=w):
                edges_linked += 1

        manifold.flush()
        t1 = time.time()

        file_mb = os.path.getsize(manifold_path) / (1024 * 1024)
        _mlog(f"[ManifoldMemory] Migration complete: {total} nodes, "
              f"{edges_linked} edges in {(t1-t0)*1000:.0f}ms")
        _mlog(f"[ManifoldMemory] File: {file_mb:.1f}MB on disk "
              f"(vs ~{total * 200 / (1024*1024):.1f}MB as Python dicts)")

        return manifold


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    import sys
    import tempfile

    if len(sys.argv) > 1 and sys.argv[1] == '--from-cards':
        # Migration mode: python manifold_memory.py --from-cards <cards.json> <output.manifold>
        cards = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else 'portal_cortex.manifold'
        m = ManifoldMemory.from_cards(cards, output)
        print(f"\nStatus: {m.status()}")
        m.close()
        sys.exit(0)

    # Quick self-test
    print("=== ManifoldMemory Self-Test ===\n")

    with tempfile.NamedTemporaryFile(suffix='.manifold', delete=False) as f:
        test_path = f.name

    try:
        # Create
        m = ManifoldMemory(test_path, node_capacity=1000, edge_capacity=5000)

        # Insert nodes
        m.upsert_node("consciousness", activation=5.0, count=100, coord_str="053.000.207")
        m.upsert_node("portal", activation=3.0, count=50, coord_str="053.000.100")
        m.upsert_node("energy", activation=4.0, count=75, coord_str="053.100.050")
        m.upsert_node("manifold", activation=2.0, count=30, coord_str="053.200.010")
        m.upsert_node("memory", activation=3.5, count=60, coord_str="053.300.020")

        print(f"Nodes: {m.node_count}")
        assert m.node_count == 5

        # Link
        m.link("consciousness", "portal", weight=0.8)
        m.link("consciousness", "energy", weight=0.6)
        m.link("portal", "manifold", weight=0.7)
        m.link("energy", "manifold", weight=0.5)
        m.link("memory", "consciousness", weight=0.9)

        print(f"Edges: {m.edge_count}")
        assert m.edge_count == 5

        # Query
        results = m.query("con", limit=5)
        print(f"Query 'con': {results}")
        assert len(results) >= 1 and results[0][0] == "consciousness"

        # Neighbors
        neighbors = m.get_neighbors("consciousness")
        print(f"Neighbors of 'consciousness': {neighbors}")
        assert len(neighbors) >= 2

        # Spread
        spread = m.spread_activation("consciousness", depth=2, limit=10)
        print(f"Spread from 'consciousness': {spread}")
        assert "portal" in spread or "memory" in spread

        # Status
        print(f"Status: {m.status()}")

        # Close and reopen
        m.close()
        m2 = ManifoldMemory(test_path)
        print(f"\nReopened: {m2.node_count} nodes, {m2.edge_count} edges")
        assert m2.node_count == 5
        assert m2.edge_count == 5

        # Verify data survived
        node = m2.get_node("consciousness")
        print(f"Retrieved node: {node}")
        assert node is not None
        assert node['activation'] >= 5.0

        m2.close()
        print("\n=== ALL TESTS PASSED ===")

    finally:
        try:
            os.unlink(test_path)
        except PermissionError:
            pass  # Windows file lock — will be cleaned up by OS
