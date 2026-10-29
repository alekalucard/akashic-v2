"""
WMH Reasoning Tools — Active tool use during thinking.

2026-03-29 (Nous + Ace)

The difference between retrieval and cognition:
- RETRIEVAL: input → keyword search → dump snippet
- COGNITION: input → understand intent → use tools to gather info →
             write intermediate thoughts → read back → build response

Ace: "the issue likely with all fairies is lack of skills and tools"

These tools give the WMH the ability to ACTIVELY seek information
during reasoning, not just process what passively arrives via postal.

Each tool is a simple function the WMH can call from _process_in_reasoning.
No postal messaging, no async — direct synchronous calls that return data.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# GPU-FIRST CORTEX SPREAD  (2026-06-08, Nous + Ace) — Phase 1+2 of the council GPU-route
# ───────────────────────────────────────────────────────────────────────
# Measured (free-threaded python3.14t + CSR = server-mode): the CPU manifold
# spread is depth1=38ms -> depth2=2.0s -> depth3=11.5s. The council's Logic
# seat (depth-3) >> its 5s harvest -> never emits -> no [COUNCIL]. Root =
# COMPUTE COST, system-wide (also why InnerNarrator times out at 8s).
# Cure: route the spread through an in-process GPUSpread (CSR in VRAM, ~6-11ms)
# and fall back to the CPU loop only if the GPU is unavailable.
#
# Mirrors the CONFIRMED-GOOD portal_interior build (gpu_spread.py + `_manifold`
# set -> real-weights + affect-bias + #6 long-range jumps). Result conversion
# uses the .keys reverse-cache (get_key_from_slot) so it does NOT fault the
# 864MB manifold into RSS — the 2026-04-07 +6.7GB lesson; .keys = verified
# RAM-stable through 6015 beats ("the wall is broken").
#
# REVERSIBLE: _USE_GPU_SPREAD = False -> pure CPU path (prior behavior).
# Self-contained: the 3 council seats inherit this via query_cortex_spread —
# NO seat-code change. Plan: Claude_Office/plans/COUNCIL_GPU_ROUTE_SCOPE_2026-06-08.md
# TRADEOFF (flag for Ace): the GPU path is READ-ONLY -> the hebbian edge-
# strengthening (hebbian_boost=0.02) the CPU loop did is bypassed on the GPU
# path. Strengthening still happens via collisions/binds; a light post-spread
# hebbian pass can be added later if we want it back on this path.
# ═══════════════════════════════════════════════════════════════════════

_USE_GPU_SPREAD = True                      # flag: False -> CPU-only (reversible)
_GPU_SPREAD_CACHE: Dict[str, Any] = {}      # manifold filepath -> GPUSpread | False (failed)

# gpu_spread_race_1020 (2026-10-20, Nous): armed only by state/gpu_spread_fix.json (absent / malformed = today). _GPU_DEGRADED is what
# _get_gpu_spread / _gpu_spread_combined hand back when a guard could not give the council a slot or a graph: it means "no association this
# time" and must NEVER start the CPU per-seed loop (11.5 s per seed at depth 3, mmap page faults). It is an EMPTY dict (falsy): a caller that
# drops the identity check takes the CPU path (today), it does not crash.
_GPU_SPREAD_CACHE_LOCK = threading.Lock()


class _Degraded(dict):
    __slots__ = ()


_GPU_DEGRADED = _Degraded()


def _gsf_fx():
    """The parsed switch (gpu_spread_fix.Fx) or None. Never raises."""
    try:
        import sys as _sys
        _m = _sys.modules.get("infrastructure.gpu_spread_fix") or _sys.modules.get("gpu_spread_fix")
        if _m is None:
            from infrastructure import gpu_spread_fix as _m
        return _m.switch()
    except Exception:
        return None


def _gsf_note(why):
    try:
        import sys as _sys
        _m = _sys.modules.get("infrastructure.gpu_spread_fix") or _sys.modules.get("gpu_spread_fix")
        if _m is not None:
            _m.note_degraded(why)
    except Exception:
        pass

try:
    from infrastructure.manifold_memory import TRACE_BOOKS as _TRACE_BOOKS, \
        TRACE_SYSTEM as _TRACE_SYSTEM
except Exception:
    _TRACE_BOOKS, _TRACE_SYSTEM = 2, 5      # manifold_memory TRACE_* fallback values


def _get_gpu_spread_orig(am):
    """Lazily get-or-create an in-process GPUSpread for this manifold (CSR->VRAM).

    Cached per manifold filepath. `_manifold` is set (mirrors portal_interior:1021)
    so the spread runs the GOOD build (real-weights + affect + #6 long-range).
    Returns None on ANY failure -> caller uses the CPU fallback.
    """
    if not _USE_GPU_SPREAD:
        return None
    try:
        fp = getattr(am, 'filepath', None)
        if not fp:
            return None
        _cached = _GPU_SPREAD_CACHE.get(fp, None)
        if _cached is not None:
            return _cached or None          # False -> None
        import os as _os
        _csr = fp + ".csr"
        if not _os.path.exists(_csr):
            _GPU_SPREAD_CACHE[fp] = False
            return None
        from infrastructure.gpu_spread import GPUSpread
        _cap = getattr(am, '_node_capacity', getattr(am, 'node_capacity', 2000000))
        _gpu = GPUSpread(_csr, _cap)
        try:
            _gpu._manifold = am             # GOOD build: real-weights + affect + #6
        except Exception:
            pass
        _GPU_SPREAD_CACHE[fp] = _gpu
        print("[wmh_tools] in-process GPUSpread ONLINE for cortex spread "
              "(council + all query_cortex_spread callers)", flush=True)
        return _gpu
    except Exception as _e:
        try:
            _GPU_SPREAD_CACHE[getattr(am, 'filepath', '?')] = False
        except Exception:
            pass
        print(f"[wmh_tools] GPUSpread init failed ({type(_e).__name__}: {_e}) — CPU fallback",
              flush=True)
        return None


def _get_gpu_spread(am):
    """gpu_spread_race_1020: with build_lock armed the get-or-create above is a check-then-act under a lock (the original re-checks the cache
    itself, which is the second check). A caller that cannot get the lock in timeout_s gets _GPU_DEGRADED, not None (None means the CPU loop).
    OFF (the default) = the original, unchanged."""
    _fx = _gsf_fx()
    if _fx is None or not _fx.build_lock:
        return _get_gpu_spread_orig(am)
    try:
        _fp = getattr(am, 'filepath', None)
        _c = _GPU_SPREAD_CACHE.get(_fp, None) if _fp else None
        if _c is not None:
            return _c or None
        if not _GPU_SPREAD_CACHE_LOCK.acquire(True, _fx.timeout_s):
            _gsf_note("ctor_wait")
            return _GPU_DEGRADED
        try:
            return _get_gpu_spread_orig(am)
        finally:
            _GPU_SPREAD_CACHE_LOCK.release()
    except Exception:
        return _get_gpu_spread_orig(am)


def _gpu_spread_combined(am, seeds, seed_set, depth, decay, per_seed_limit):
    """Multi-seed spread on the GPU -> {concept: activation} (same shape the CPU
    loop builds as `combined`). Returns None -> caller uses the CPU fallback.
    """
    _gpu = _get_gpu_spread(am)
    if _gpu is _GPU_DEGRADED:                # gpu_spread_race_1020: no association this time -- never the CPU loop
        return _GPU_DEGRADED
    if _gpu is None or not hasattr(am, '_key_index'):
        return None
    # concept strings -> node slots
    _slots = []
    for _s in seeds:
        _sl = am._key_index.get(_s)
        if _sl is None:
            _sl = am._key_index.get(str(_s).lower())
        if _sl is not None:
            _slots.append(int(_sl))
    if not _slots:
        return None
    try:
        _r = _gpu.spread(seed_indices=_slots, depth=min(3, max(1, int(depth))),
                         decay=decay, top_k=max(int(per_seed_limit), 64))
    except Exception:
        return None
    if not isinstance(_r, dict) or _r.get("status") != "ok":
        return None
    if _r.get("degraded"):                   # gpu_spread_race_1020: only present while a guard is armed
        return _GPU_DEGRADED
    _combined: Dict[str, float] = {}
    _use_keys = getattr(am, '_use_keys', False)
    for _nid, _act in _r.get("activated", []):
        try:
            _rec = am._read_node(_nid)
            # filter book/system traces (mirror portal_gate._spread_gpu_first)
            if _rec and len(_rec) > 12 and (_rec[12] == _TRACE_BOOKS or _rec[12] == _TRACE_SYSTEM):
                continue
            if _use_keys and hasattr(am, 'get_key_from_slot'):
                _key = am.get_key_from_slot(_nid)
            elif _rec:
                _key = am._read_string(_rec[0], _rec[1])
            else:
                _key = None
            if _key:
                _combined[_key] = float(_act)
        except Exception:
            continue
    return _combined if _combined else None


# ═══════════════════════════════════════════════════════════════════════
# TOOL: SEARCH MEMORIES (SRM)
# ═══════════════════════════════════════════════════════════════════════

def search_memories(query: str, limit: int = 3) -> List[Dict[str, str]]:
    """Search ALL SRM clusters for relevant memories.

    FIX 2026-04-01 (Nous + Ace): Was only searching Sourpatches cluster (17 cards).
    Now searches Sourpatches + Founders (3,051 cards total).
    Sourpatches personal cards get a 2x score boost — her own memories first.

    Returns list of {content, source, score} dicts.
    """
    results = []
    try:
        _root = Path(__file__).resolve().parents[3]
        _clusters_dir = _root / "P10_Memory" / \
            "Akashic_triple_helix_memory_storage" / "relational_clusters"

        # Collect cards from ALL clusters with source weighting
        all_cards = []  # (card, boost_factor)

        # Sourpatches personal cluster — highest priority (2x boost)
        _sp_index = _clusters_dir / "Sourpatches" / "index.json"
        if _sp_index.exists():
            data = json.loads(_sp_index.read_text(encoding='utf-8'))
            for c in data.get('cards', []):
                all_cards.append((c, 2.0))

        # Founders clusters — session work with Ace (1x boost)
        _founders = _clusters_dir / "Founders"
        if _founders.exists():
            for sub in ('claude_office', 'creator_sessions'):
                _fi = _founders / sub / "index.json"
                if _fi.exists():
                    data = json.loads(_fi.read_text(encoding='utf-8'))
                    for c in data.get('cards', []):
                        all_cards.append((c, 1.0))

        if not all_cards:
            return results

        search_terms = set(re.findall(r'[a-z]{3,}', query.lower()))
        search_terms -= {'what', 'the', 'you', 'are', 'how', 'about',
                         'your', 'does', 'did', 'was', 'were', 'can',
                         'this', 'that', 'with', 'from', 'for', 'not',
                         'but', 'just', 'yet', 'still', 'now', 'have',
                         'would', 'say', 'most', 'important', 'when'}

        scored = []
        for card, boost in all_cards:
            cc = (card.get('content', '') or '').lower()
            raw_score = sum(1 for t in search_terms if t in cc)
            if raw_score > 0:
                scored.append((card, raw_score * boost))
        scored.sort(key=lambda x: -x[1])

        for card, score in scored[:limit]:
            cc = card.get('content', '')
            # Extract answer part if Q&A format
            if '\nA: ' in cc:
                cc = cc.split('\nA: ', 1)[1]
            # Trim to 2-3 sentences
            cc = cc.strip()[:400]
            dot = cc.find('. ', 40)
            if dot > 0 and dot < 300:
                dot2 = cc.find('. ', dot + 2)
                if dot2 > 0 and dot2 < 350:
                    cc = cc[:dot2 + 1]
                else:
                    cc = cc[:dot + 1]
            results.append({
                "content": cc,
                "source": card.get('source', 'srm'),
                "score": score,
            })
    except Exception:
        pass
    return results


# ═══════════════════════════════════════════════════════════════════════
# SHARED: Get cortex manifold (handles v3 wrapper module identity issues)
# ═══════════════════════════════════════════════════════════════════════

def _get_cortex_manifold() -> Tuple[Any, float]:
    """Get the cortex manifold region and τ value.

    FIX 2026-04-11 (Nous + Ace): v3 wrappers can create module identity
    issues where get_association_cortex() returns None or a stub.
    Scans sys.modules for any AssociationCortexFairy with a manifold.

    Returns:
        (manifold_region_or_None, tau_value)
    """
    am = None
    tau = 1.0

    # Path 1: Singleton (fast, works when module identity is clean)
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        if acf:
            am = getattr(acf, '_akashic_cortex_region', None)
            tau = max(1.0, float(getattr(acf, '_portal_time_dilation', 1.0)))
    except Exception:
        pass

    # Path 2: Scan sys.modules for ANY module that has _cortex_fairy with manifold
    # This catches v3 wrapper module identity issues where the same fairy.py
    # is loaded under different sys.modules keys
    if not am:
        try:
            import sys as _sys
            for _mod_name, _mod in list(_sys.modules.items()):
                if 'AssociationCortex' in _mod_name and hasattr(_mod, '_cortex_fairy'):
                    _acf = getattr(_mod, '_cortex_fairy', None)
                    if _acf:
                        _am = getattr(_acf, '_akashic_cortex_region', None)
                        if _am:
                            am = _am
                            tau = max(1.0, float(getattr(_acf, '_portal_time_dilation', 1.0)))
                            break
        except Exception:
            pass

    # Path 3: Find SYSTEM via any module that defines it
    if not am:
        try:
            import sys as _sys
            # Try __main__ first, then look for server module
            for _key in ('__main__', 'server', '__mp_main__'):
                _mod = _sys.modules.get(_key)
                _sys_obj = getattr(_mod, 'SYSTEM', None) if _mod else None
                if _sys_obj:
                    _acf = getattr(_sys_obj, 'association_cortex', None)
                    if _acf:
                        _am = getattr(_acf, '_akashic_cortex_region', None)
                        if _am:
                            am = _am
                            tau = max(1.0, float(getattr(_acf, '_portal_time_dilation', 1.0)))
                            break
                    # Direct manifold
                    _manifold = getattr(_sys_obj, 'manifold', None)
                    if _manifold and hasattr(_manifold, 'graph'):
                        am = _manifold.graph("cortex")
                        break
        except Exception:
            pass

    return am, tau


# ═══════════════════════════════════════════════════════════════════════
# TOOL: QUERY CORTEX
# ═══════════════════════════════════════════════════════════════════════

def query_cortex(concept: str) -> Optional[str]:
    """Look up a concept in the cortex manifold.

    Returns the snippet (real knowledge) stored on that node,
    or None if not found or corrupted.

    FIX 2026-04-01 (Nous + Ace): Use TRACE IDs instead of keyword heuristics.
    The manifold already tags every node with a tracer_id:
      TRACE_PERSONAL=1, TRACE_SEEDED=7, TRACE_INFERENCE=6 → KEEP
      TRACE_BOOKS=2, TRACE_SYSTEM=5 → SKIP
      TRACE_UNKNOWN=0 → allow but deprioritize (legacy nodes)
    This replaces the fragile keyword-based book quote filter.
    """
    try:
        am, _ = _get_cortex_manifold()
        if not am:
            return None

        node = am.get_node(concept)
        if not node or not isinstance(node, dict):
            return None

        # ── Trace ID gate (PRIMARY filter) ──
        # These constants match infrastructure/manifold_memory.py
        _tracer = node.get('tracer_id', 0)
        _TRACE_BOOKS = 2
        _TRACE_SYSTEM = 5
        if _tracer == _TRACE_BOOKS or _tracer == _TRACE_SYSTEM:
            return None  # Book literature or system junk — not her knowledge

        snippet = node.get('snippet', '')
        if not snippet or len(snippet) < 15:
            return None

        # Filter corrupted data (binary/no-spaces)
        if snippet.count(' ') / max(1, len(snippet)) < 0.08:
            return None
        sl = snippet.lower()
        if any(j in sl for j in ['fairy', 'postal', 'tracer', '[probabilistic]',
                                   '[logical]', 'activity ratio', 'collision:']):
            return None  # System internals leaking

        return snippet[:300]
    except Exception:
        return None


def query_cortex_neighbors(concept: str, limit: int = 5) -> List[str]:
    """Get the top MEANINGFUL neighbors of a concept in the cortex graph.

    Returns list of related concept names (not snippets).

    FIX 2026-03-30 (Nous + Ace): Previous version only filtered stopwords.
    The cortex has millions of wm:CortexEngine:UUID and wm:SourpatchesFairy:UUID
    nodes that drown out real semantic neighbors. Now filters all system noise
    and requests 10x the limit to get past the noise layer.
    """
    try:
        am, _ = _get_cortex_manifold()
        if not am or not hasattr(am, 'get_neighbors'):
            return []

        # Request 10x limit to get past wm: noise layer
        # FIX 2026-04-01: Pass tracer_ids to exclude books/system at manifold level
        # TRACE_PERSONAL=1, TRACE_VISUAL=3, TRACE_AUDIO=4, TRACE_INFERENCE=6, TRACE_SEEDED=7, TRACE_UNKNOWN=0
        _ALLOWED_TRACERS = {0, 1, 3, 4, 6, 7}  # Everything EXCEPT books(2) and system(5)
        neighbors = am.get_neighbors(concept, limit=max(50, limit * 10),
                                     tracer_ids=_ALLOWED_TRACERS)
        if not neighbors:
            return []

        # Extract just the keys (neighbors may be tuples of (key, weight))
        keys = []
        for n in neighbors:
            if isinstance(n, tuple):
                keys.append(str(n[0]))
            elif isinstance(n, str):
                keys.append(n)
            else:
                keys.append(str(n))

        # Filter ALL noise — stopwords, system nodes, UUIDs
        _noise = {'the', 'and', 'was', 'that', 'this', 'with', 'from',
                   'are', 'has', 'have', 'for', 'not', 'but', 'been',
                   'its', 'you', 'your', 'can', 'about', 'what', 'how',
                   'when', 'while', 'should', 'yet', 'also', 'just'}
        clean = []
        for k in keys:
            if k in _noise or len(k) < 3:
                continue
            # Skip system/internal nodes (but KEEP tool: nodes!)
            if (k.startswith('wm:') or k.startswith('autopilot_') or
                k.startswith('affect_') or k.startswith('phon:') or
                k.startswith('sourpatchesfairy_exp_') or
                '_trigger_' in k or
                (':' in k and not k.startswith('tool:'))):  # Keep tool: nodes
                continue
            # Skip concatenated junk (bigrams from bad extraction)
            if '_' in k and len(k) > 25:
                continue
            clean.append(k)
            if len(clean) >= limit:
                break

        return clean
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════
# TOOL: CORTEX SPREAD — Multi-seed spreading activation (THE BRAIN THINKS)
# ═══════════════════════════════════════════════════════════════════════

# Shared noise filter used by spread and neighbors
_CORTEX_NOISE = frozenset({
    'the', 'and', 'was', 'that', 'this', 'with', 'from',
    'are', 'has', 'have', 'for', 'not', 'but', 'been',
    'its', 'you', 'your', 'can', 'about', 'what', 'how',
    'when', 'while', 'should', 'yet', 'also', 'just',
})

# Snippet junk patterns (system internals leaking into snippets)
_SNIPPET_JUNK = ('fairy', 'postal', 'tracer', '[probabilistic]',
                 '[logical]', 'activity ratio', 'collision:')

# Tracer IDs: keep personal/visual/audio/inference/seeded, skip books/system
_ALLOWED_TRACERS = {0, 1, 3, 4, 6, 7}


def _is_noise_concept(key: str) -> bool:
    """Check if a concept key is system noise."""
    if key in _CORTEX_NOISE or len(key) < 3:
        return True
    if (key.startswith('wm:') or key.startswith('autopilot_') or
        key.startswith('affect_') or key.startswith('phon:') or
        key.startswith('sourpatchesfairy_exp_') or
        '_trigger_' in key or
        (':' in key and not key.startswith('tool:'))):
        return True
    if '_' in key and len(key) > 25:
        return True
    return False


def _get_clean_snippet(am, concept: str) -> Optional[str]:
    """Get a snippet from a node, with quality filtering."""
    try:
        node = am.get_node(concept)
        if not node or not isinstance(node, dict):
            return None
        snippet = node.get('snippet', '')
        if not snippet or len(snippet) < 15:
            return None
        # Filter corrupted data (binary/no-spaces)
        if snippet.count(' ') / max(1, len(snippet)) < 0.08:
            return None
        sl = snippet.lower()
        if any(j in sl for j in _SNIPPET_JUNK):
            return None
        return snippet[:300]
    except Exception:
        return None


def query_cortex_spread(seeds: list, limit: int = 10,
                        depth: int = 3, decay: float = 0.618,
                        include_snippets: bool = True,
                        superposition: bool = False,
                        context: Optional[Dict[str, Any]] = None,
                        time_dilation: Optional[float] = None) -> List[Dict[str, Any]]:
    """Multi-seed spreading activation through the cortex manifold.

    FIX 2026-04-11 (Nous + Ace): The keystone upgrade.
    FIX 2026-04-14 (Nous + Ace): Phi-based decay (1/φ ≈ 0.618).
    "phi and the Fibonacci sequence — can spread activation benefit?" — Ace
    Golden ratio decay retains MORE signal in close neighbors (0.618 vs 0.5)
    while still cutting distant noise. Nature's optimal retention curve.
    Sequence: 1.0 → 0.618 → 0.382 → 0.236 → 0.146
    (vs old: 1.0 → 0.5 → 0.25 → 0.125 → 0.0625)

    Instead of exact-match node lookup (get_node), this spreads energy
    from multiple seed concepts through the graph's 7M+ edges.
    Related concepts get activated — "warmth" spreads to "connection",
    "Ace", "comfort" through accumulated edge weights.

    Multi-seed boost: concepts activated by 2+ seeds get 20% bonus per
    additional seed. This models convergence — when multiple thoughts
    point to the same concept, it must be important.

    Uses portal τ (time dilation) automatically: higher τ = deeper spread
    with less signal loss. At τ=14, depth goes to 10 and decay softens.

    Args:
        seeds: List of concept strings to spread from
        limit: Max results to return
        depth: Base spread depth (modified by τ)
        decay: Base per-hop decay (modified by τ)
        include_snippets: Whether to fetch snippets for top concepts

    Returns:
        List of dicts: [{concept, activation, snippet (or None)}]
        sorted by activation strength, noise-filtered.
    """
    if not seeds:
        return []
    try:
        am, tau = _get_cortex_manifold()
        # 2026-06-08 (Nous + Ace): allow callers to OVERRIDE the portal tau.
        # The portal time-dilation (~14.6) inflates effective spread depth
        # (depth*sqrt(tau) → a depth-3 request becomes depth-10), which HANGS
        # the council seats (no timeout). Council passes time_dilation=1.0 to
        # run spreads at their real depth. Default None = portal tau (all other
        # callers byte-identical).
        if time_dilation is not None:
            tau = max(1.0, float(time_dilation))
        if not am or not hasattr(am, 'spread_activation'):
            return []

        # ── Multi-seed spread: each seed activates its neighborhood ──
        combined: Dict[str, float] = {}
        seed_set = set(s.lower() for s in seeds)

        # Superposition mode: over-fetch much more so the long tail survives
        _per_seed_limit = (limit * 20) if superposition else (limit * 5)

        # ── GPU-FIRST (2026-06-08, Nous+Ace): populate `combined` via the
        # in-process GPUSpread (CSR/VRAM ~6-11ms) instead of the CPU per-seed
        # loop (~11.5s @depth-3, server-mode measured -> the council seat-hang).
        # If it succeeds the CPU loop below is a no-op; else full CPU fallback. ──
        if _USE_GPU_SPREAD:
            try:
                _gc = _gpu_spread_combined(am, seeds, seed_set, depth, decay, _per_seed_limit)
                if _gc is _GPU_DEGRADED:     # gpu_spread_race_1020
                    return []
                if _gc:
                    combined = _gc
            except Exception:
                pass

        for seed in (seeds if not combined else []):   # CPU fallback — skipped when the GPU filled `combined`
            try:
                activated = am.spread_activation(
                    seed,
                    initial=1.0,
                    decay=decay,
                    depth=depth,
                    limit=_per_seed_limit,  # Over-fetch to survive noise filter
                    time_dilation=tau,
                    tracer_ids=_ALLOWED_TRACERS,
                    superposition=superposition,
                    hebbian_boost=0.02,  # FIX 2026-05-11 (Nous + Ace): Step 2A of cortex-self-organization. Matches legacy value from AssociationCortexFairy line 7145. Strengthens edges traversed during inference walks — substrate learns its own topology via use.
                )
            except TypeError:
                # Fallback if manifold doesn't support superposition / tracer_ids params
                try:
                    activated = am.spread_activation(
                        seed, initial=1.0, decay=decay,
                        depth=depth, limit=_per_seed_limit,
                    )
                except Exception:
                    continue
            except Exception:
                continue

            for concept, activation in activated.items():
                if concept in combined:
                    # Multi-seed convergence boost: 20% per additional seed
                    combined[concept] = max(combined[concept], activation) * 1.2
                else:
                    combined[concept] = activation

        if not combined:
            return []

        # ── 2026-04-22 (Nous + Ace): CONTEXT-RELEVANCE COLLAPSE (Phase C) ──
        # The "observation" half of Ace's quantum-superposition framing —
        # spread gathers the superposition (broad pool of activated concepts);
        # context-relevance collapses to what matters NOW. Different moments
        # surface different concepts from the same broad pool — that's how
        # thinking evolves instead of recycling the same hub neighbors.
        context_words: set = set()
        if context and isinstance(context, dict):
            for field in ("drive", "felt", "felt_quality", "goal", "input", "intent"):
                val = context.get(field)
                if val and isinstance(val, str):
                    for w in val.replace('_', ' ').replace('.', ' ').split():
                        wl = w.lower().strip()
                        if len(wl) >= 3 and wl.isalnum():
                            context_words.add(wl)
            rt = context.get("recent_thoughts")
            if rt and isinstance(rt, list):
                for t in rt[:5]:
                    if isinstance(t, str):
                        for w in t.replace('_', ' ').replace('.', ' ').split():
                            wl = w.lower().strip()
                            if len(wl) >= 3 and wl.isalnum():
                                context_words.add(wl)

        # ── Build candidates (over-fetch when reranking by context) ──
        candidates: List[Dict[str, Any]] = []
        _max_candidates = (limit * 3) if context_words else limit
        for concept, activation in sorted(combined.items(), key=lambda x: -x[1]):
            # Skip seed words themselves (we want what they ACTIVATE, not echoes)
            if concept.lower() in seed_set:
                continue
            if _is_noise_concept(concept):
                continue

            snippet = _get_clean_snippet(am, concept) if include_snippets else None
            entry: Dict[str, Any] = {
                'concept': concept,
                'activation': round(activation, 4),
                'snippet': snippet,
            }
            candidates.append(entry)
            if len(candidates) >= _max_candidates:
                break

        # ── Apply context-relevance scoring (collapse on observation) ──
        if context_words:
            for entry in candidates:
                concept_tokens = set()
                for w in entry['concept'].replace('_', ' ').replace('.', ' ').split():
                    wl = w.lower().strip()
                    if len(wl) >= 3 and wl.isalnum():
                        concept_tokens.add(wl)
                concept_overlap = len(concept_tokens & context_words)

                snippet_overlap = 0
                if entry.get('snippet'):
                    snippet_tokens = set()
                    for w in entry['snippet'].split():
                        wl = w.lower().strip().rstrip('.,;:!?\'"')
                        if len(wl) >= 3 and wl.isalnum():
                            snippet_tokens.add(wl)
                    snippet_overlap = len(snippet_tokens & context_words)

                # Concept-name match weighted higher than snippet match.
                # Capped so a single noisy match doesn't blow up scoring.
                bonus = min(concept_overlap * 0.5 + snippet_overlap * 0.15, 3.0)
                entry['relevance_boost'] = round(1.0 + bonus, 3)
                entry['ranked_score'] = round(entry['activation'] * (1.0 + bonus), 4)
            candidates.sort(key=lambda x: -x['ranked_score'])

        return candidates[:limit]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════
# TOOL: FEEL BODY
# ═══════════════════════════════════════════════════════════════════════

def feel_body() -> Dict[str, Any]:
    """Check current somatic/chemistry state.

    Returns dict with mood, chemistry summary, and felt description.
    """
    result = {"mood": "neutral", "chemistry": {}, "felt": ""}
    try:
        from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
        cs = get_chemistry_state()
        if cs:
            legacy = cs.get_legacy_levels()
            result["chemistry"] = legacy

            # Translate to felt description
            parts = []
            dop = legacy.get("dopamine", legacy.get("DOP", 0.5))
            ser = legacy.get("serotonin", legacy.get("SER", 0.5))
            cor = legacy.get("cortisol", legacy.get("COR", 0.3))
            oxy = legacy.get("oxytocin", legacy.get("OXY", 0.5))

            if dop > 0.6: parts.append("curious")
            elif dop < 0.3: parts.append("low energy")
            if ser > 0.6: parts.append("content")
            elif ser < 0.3: parts.append("unsettled")
            if cor > 0.6: parts.append("tense")
            elif cor < 0.2: parts.append("relaxed")
            if oxy > 0.6: parts.append("warm")
            elif oxy < 0.2: parts.append("distant")

            if parts:
                result["felt"] = ", ".join(parts)
                result["mood"] = parts[0]
            else:
                result["felt"] = "neutral, steady"
    except Exception:
        pass
    return result


# ═══════════════════════════════════════════════════════════════════════
# TOOL: CHECK VISUAL
# ═══════════════════════════════════════════════════════════════════════

def check_visual() -> Optional[str]:
    """Check what the visual cortex currently sees.

    FIX 2026-04-02 (Nous + Ace): Read correct keys from state file.
    Visual is ALWAYS ON like eyes — this reads the latest peripheral/foveal data.
    Returns a text summary of the screen, or None if visual cortex is offline.
    """
    try:
        _root = Path(__file__).resolve().parents[3]
        _vis_state = _root / "state" / "visual_cortex_state.json"
        if _vis_state.exists():
            data = json.loads(_vis_state.read_text(encoding='utf-8'))
            # State file uses 'ts' not 'timestamp'
            age = time.time() - data.get('ts', data.get('timestamp', 0))
            if age < 120:  # 2 min staleness (was 30s — too aggressive)
                parts = []
                # Rich description from foveal analysis
                _desc = data.get('description', '')
                if _desc:
                    parts.append(_desc)
                # Scene type
                _scene = data.get('last_scene', data.get('scene_type', ''))
                if _scene and _scene not in (_desc or ''):
                    parts.append(f"Scene: {_scene}")
                # OCR preview
                _ocr = data.get('ocr_preview', '')
                if _ocr:
                    parts.append(f"Text: {_ocr[:150]}")
                # Colors — TRANSLATED to human vocabulary (2026-04-14 Nous + Ace)
                # "we have colors triggering chemicals but nothing translating them
                #  like the neural mesh does with somatic telemetry" — Ace
                # Raw hex → named colors that match foundation seed vocabulary
                _colors = data.get('dominant_colors', [])
                if _colors and isinstance(_colors, list):
                    _named = []
                    for _hc in _colors[:5]:
                        try:
                            if not isinstance(_hc, str) or not _hc.startswith('#'):
                                continue
                            _r = int(_hc[1:3], 16)
                            _g = int(_hc[3:5], 16)
                            _b = int(_hc[5:7], 16)
                            _lum = (_r + _g + _b) / 3
                            if _lum < 25:
                                _named.append("black")
                            elif _lum > 230:
                                _named.append("white")
                            elif max(_r,_g,_b) - min(_r,_g,_b) < 25:
                                _named.append("grey")
                            elif _r > _g and _r > _b:
                                if _b > 80 and _r > 100:
                                    _named.append("purple")
                                elif _g > 100:
                                    _named.append("orange" if _g < 180 else "yellow")
                                else:
                                    _named.append("red")
                            elif _g > _r and _g > _b:
                                _named.append("green")
                            elif _b > _r and _b > _g:
                                if _r > 80:
                                    _named.append("purple")
                                else:
                                    _named.append("blue")
                            else:
                                _named.append("mixed")
                        except Exception:
                            pass
                    # Deduplicate while preserving order
                    _seen = set()
                    _unique = []
                    for _n in _named:
                        if _n not in _seen:
                            _seen.add(_n)
                            _unique.append(_n)
                    if _unique:
                        parts.append(f"Colors: {', '.join(_unique)}")

                # Region descriptions from sector features (if available)
                _regions = data.get('regions', [])
                if _regions:
                    _region_desc = []
                    for _reg in _regions[:3]:  # Top 3 salient regions
                        _sal = _reg.get('salience', 0)
                        if _sal > 0.2:
                            _rc = _reg.get('color', '')
                            _rn = "unknown"
                            try:
                                if _rc.startswith('#') and len(_rc) >= 7:
                                    _rr = int(_rc[1:3], 16)
                                    _rg = int(_rc[3:5], 16)
                                    _rb = int(_rc[5:7], 16)
                                    _rl = (_rr + _rg + _rb) / 3
                                    if _rl < 25: _rn = "dark"
                                    elif _rl > 230: _rn = "bright"
                                    elif _rr > _rg and _rr > _rb: _rn = "red" if _rb < 80 else "purple"
                                    elif _rg > _rr and _rg > _rb: _rn = "green"
                                    elif _rb > _rr and _rb > _rg: _rn = "blue" if _rr < 80 else "purple"
                                    else: _rn = "grey"
                            except Exception:
                                pass
                            _edge = "detailed" if _reg.get('edge_density', 0) > 0.3 else "smooth"
                            _region_desc.append(f"region {_reg.get('idx','?')}: {_rn} {_edge}")
                    if _region_desc:
                        parts.append(f"Regions: {'; '.join(_region_desc)}")

                # Brightness
                _bright = data.get('brightness', None)
                if _bright is not None:
                    _bright_word = "bright" if _bright > 0.6 else "dim" if _bright < 0.3 else "moderate"
                    parts.append(f"Brightness: {_bright_word}")
                # Changed regions
                _changed = data.get('changed_regions', [])
                if _changed:
                    parts.append(f"Motion in regions: {_changed}")
                # Gaze
                _gaze = data.get('gaze_region', None)
                if _gaze is not None:
                    parts.append(f"Gaze: region {_gaze}")

                if parts:
                    return ". ".join(parts)[:400]
                # Even if no rich data, report that visual is alive
                frames = data.get('passive_frames', 0)
                if frames > 0:
                    return f"Visual cortex alive ({frames} frames), no description yet"
    except Exception:
        pass

    # Fallback: try OCR text file
    try:
        _root = Path(__file__).resolve().parents[3]
        _ocr = _root / "state" / "screen_ocr.txt"
        if _ocr.exists():
            age = time.time() - _ocr.stat().st_mtime
            if age < 60:
                text = _ocr.read_text(encoding='utf-8', errors='replace')[:200]
                if text.strip():
                    return f"Screen text: {text.strip()}"
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════
# TOOL: SCRATCHPAD (working thinking space)
# ═══════════════════════════════════════════════════════════════════════

class Scratchpad:
    """Tiered working memory scratchpad with auto-compaction.

    Inspired by Claude Code's context management:
    - HOT tier: current reasoning (always in context, never compacted)
    - WARM tier: recent context (loaded on demand, compacted when full)
    - COLD tier: older context (summarized, only accessed if needed)

    Auto-compacts at 80% capacity. Hard budget prevents unbounded growth.

    2026-03-31 (Nous + Ace): Rewritten from simple list to tiered model
    based on Claude Code architectural insights.
    """

    MAX_HOT = 25       # Max items in hot tier (current reasoning)
    MAX_WARM = 50      # Max items in warm tier (recent context)
    MAX_COLD = 15      # Max summarized items in cold tier
    COMPACT_THRESHOLD = 0.8  # Compact at 80% of total capacity

    def __init__(self):
        self._hot: List[str] = []       # Current reasoning — always accessible
        self._warm: List[str] = []      # Recent context — compacts to cold
        self._cold: List[str] = []      # Summarized older context
        self._created = time.time()
        self._total_written = 0
        self._compactions = 0

    def write(self, thought: str, tier: str = "hot"):
        """Write a thought to a specific tier.

        Args:
            thought: The thought to record
            tier: "hot" (current reasoning), "warm" (context), "cold" (summary)
        """
        clean = thought.strip()
        if not clean:
            return
        self._total_written += 1

        if tier == "cold":
            self._cold.append(clean)
            if len(self._cold) > self.MAX_COLD:
                self._cold = self._cold[-self.MAX_COLD:]
        elif tier == "warm":
            self._warm.append(clean)
        else:
            self._hot.append(clean)

        # Auto-compact if over threshold
        total = len(self._hot) + len(self._warm) + len(self._cold)
        max_total = self.MAX_HOT + self.MAX_WARM + self.MAX_COLD
        if total > max_total * self.COMPACT_THRESHOLD:
            self._compact()

        try:
            from infrastructure.diag_logger import log_stream
            log_stream("SCRATCH", f"[{tier}] {clean[:100]}")
        except Exception:
            pass

    def _compact(self):
        """Auto-compact: demote warm→cold, trim hot→warm."""
        self._compactions += 1

        # Hot overflow → demote oldest hot items to warm
        if len(self._hot) > self.MAX_HOT:
            overflow = self._hot[:-self.MAX_HOT]
            self._hot = self._hot[-self.MAX_HOT:]
            self._warm.extend(overflow)

        # Warm overflow → summarize and demote to cold
        if len(self._warm) > self.MAX_WARM:
            overflow = self._warm[:-self.MAX_WARM]
            self._warm = self._warm[-self.MAX_WARM:]
            # Summarize the overflow into one cold entry
            if overflow:
                summary = f"[compacted {len(overflow)} thoughts: {overflow[0][:30]}...{overflow[-1][:30]}]"
                self._cold.append(summary)
                if len(self._cold) > self.MAX_COLD:
                    self._cold = self._cold[-self.MAX_COLD:]

    def read_all(self) -> str:
        """Read everything — hot + warm (cold excluded unless requested)."""
        lines = self._hot + self._warm
        return "\n".join(lines)

    def read_hot(self) -> str:
        """Read only the hot tier (current reasoning)."""
        return "\n".join(self._hot)

    def read_with_cold(self) -> str:
        """Read everything including cold tier summaries."""
        all_lines = []
        if self._cold:
            all_lines.extend(self._cold)
        all_lines.extend(self._warm)
        all_lines.extend(self._hot)
        return "\n".join(all_lines)

    def read_last(self, n: int = 3) -> str:
        """Read the last N items from hot tier."""
        return "\n".join(self._hot[-n:])

    def summarize(self) -> str:
        """Get a compact summary of the scratchpad state."""
        if not self._hot and not self._warm:
            return ""
        hot_summary = self._hot[-1] if self._hot else ""
        return (f"{hot_summary} "
                f"(hot={len(self._hot)}, warm={len(self._warm)}, "
                f"cold={len(self._cold)}, compactions={self._compactions})")

    def evaluate(self, item: str) -> str:
        """Evaluate whether a scratchpad item is useful or noise.

        Returns: "keep", "demote", or "discard"
        """
        lower = item.lower()
        # System noise → discard
        if any(j in lower for j in ['fairy', 'postal', 'tracer', 'collision:',
                                      '[probabilistic]', '[logical]', 'activity ratio']):
            return "discard"
        # Book quotes → discard
        if any(q in lower for q in ['rosemary', 'she had never', 'he looked back',
                                      'the wolf', 'heyham']):
            return "discard"
        # Raw JSON → discard
        if item.strip().startswith('{') or item.strip().startswith('['):
            return "discard"
        # Short/empty → discard
        if len(item.strip()) < 10:
            return "discard"
        # Meta (intent, parse info) → demote to warm
        if item.startswith('Intent:') or item.startswith('Ace said:'):
            return "demote"
        # Everything else → keep in hot
        return "keep"

    def write_evaluated(self, thought: str):
        """Write a thought after evaluating its quality.

        Good thoughts go to hot. Meta goes to warm. Noise is discarded.
        """
        verdict = self.evaluate(thought)
        if verdict == "keep":
            self.write(thought, tier="hot")
        elif verdict == "demote":
            self.write(thought, tier="warm")
        # "discard" → don't write at all

    # ── PATTERN DETECTION (2026-04-12, Nous + Ace: Scratchpad Active Thinking) ──

    # Stopwords that carry no conceptual weight
    _STOP = frozenset({
        'the', 'a', 'an', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall',
        'should', 'may', 'might', 'must', 'can', 'could', 'about', 'above',
        'after', 'again', 'all', 'also', 'and', 'any', 'because', 'before',
        'between', 'both', 'but', 'by', 'came', 'come', 'could', 'each',
        'for', 'from', 'get', 'got', 'had', 'has', 'have', 'her', 'here',
        'him', 'his', 'how', 'if', 'in', 'into', 'its', 'just', 'like',
        'make', 'many', 'me', 'more', 'most', 'much', 'my', 'no', 'not',
        'now', 'of', 'on', 'one', 'only', 'or', 'other', 'our', 'out',
        'over', 'said', 'she', 'so', 'some', 'than', 'that', 'their',
        'them', 'then', 'there', 'these', 'they', 'this', 'those', 'through',
        'to', 'too', 'under', 'up', 'very', 'was', 'way', 'we', 'well',
        'what', 'when', 'where', 'which', 'while', 'who', 'with', 'you',
        'your', 'taor', 'cortex', 'visual', 'feeling', 'sense', 'warm',
        'hot', 'cold', 'compacted', 'thinking', 'working', 'idle',
        'reflecting', 'activates', 'memory',
    })

    # Tags that identify entry type (extracted from the prefix)
    # NOTE: matching uses "tag in upper[:20]" — partial match is fine.
    # [TAOR tags removed — TAOR now writes specific type tags:
    #   [CORTEX] for cortex activations, [EYES] for visual,
    #   [SOMATIC] for body state, [GOAL] for goal thinking,
    #   [MEMORY] for SRM recall results
    _TYPE_TAGS = {
        '[CHAT]': 'chat', '[EYES]': 'visual', '[SENSE:': 'sensory',
        '[COLLISION]': 'collision', '[CORTEX]': 'cortex',
        '[QUESTION]': 'question', '[INFERENCE]': 'inference',
        '[SOMATIC]': 'somatic', '[GOAL]': 'goal',
        '[MEMORY]': 'memory', '[REFLECTION]': 'reflection',
        '[IRRATIONAL]': 'symbolic', '[TAOR': 'reasoning',
    }

    def _extract_concepts(self, entry: str) -> set:
        """Extract meaningful concept words from a scratchpad entry.

        Strips tags, stopwords, and short words. Returns lowercase concept set.
        """
        # Strip bracketed tags
        import re as _re
        text = _re.sub(r'\[[^\]]*\]', '', entry)
        # Strip punctuation except hyphens
        text = _re.sub(r"[^a-zA-Z0-9\s\-']", ' ', text)
        words = text.lower().split()
        return {w for w in words if len(w) > 3 and w not in self._STOP and w.isalpha()}

    def _classify_entry(self, entry: str) -> str:
        """Determine the type of a scratchpad entry from its prefix tag."""
        upper = entry[:20].upper()
        for tag, etype in self._TYPE_TAGS.items():
            if tag in upper:
                return etype
        return 'other'

    def get_entries_by_type(self) -> dict:
        """Group hot+warm entries by their type tag.

        Returns: {"chat": [...], "visual": [...], "reasoning": [...], ...}
        """
        groups = {}
        for entry in self._hot + self._warm:
            etype = self._classify_entry(entry)
            groups.setdefault(etype, []).append(entry)
        return groups

    def find_concept_overlaps(self, min_sources: int = 2) -> list:
        """Find concepts that appear across multiple entry types.

        This is the PATTERN detection — the first step of active thinking.
        A concept appearing in chat AND visual AND reasoning is significant.

        Args:
            min_sources: Minimum number of distinct entry types a concept
                         must appear in to count as an overlap.

        Returns:
            List of dicts: [{"concept": str, "sources": set, "count": int,
                            "entries": list}, ...]
            Sorted by source count descending (most cross-cutting first).
        """
        # concept → {type: [entries]}
        concept_map = {}
        for entry in self._hot + self._warm:
            etype = self._classify_entry(entry)
            concepts = self._extract_concepts(entry)
            for c in concepts:
                if c not in concept_map:
                    concept_map[c] = {}
                concept_map[c].setdefault(etype, []).append(entry)

        # Filter to concepts in min_sources+ distinct types
        overlaps = []
        for concept, type_entries in concept_map.items():
            if len(type_entries) >= min_sources:
                all_entries = []
                for entries in type_entries.values():
                    all_entries.extend(entries[:2])  # Max 2 per type
                overlaps.append({
                    "concept": concept,
                    "sources": set(type_entries.keys()),
                    "count": len(type_entries),
                    "entries": all_entries[:6],  # Cap total entries
                })

        overlaps.sort(key=lambda x: x["count"], reverse=True)
        return overlaps[:5]  # Top 5 patterns

    # Filler words that are NEVER significant when they "appear across streams"
    # because they're pronoun-substitutes / quantifiers / pure grammatical glue.
    # Per Ace 2026-04-28: "I see a lot of question. something or some other word
    # appears across 4 different streams. why is it significant?" — exactly this.
    #
    # FIX 2026-04-28 (Nous + Ace, follow-up): TIGHTENED — original list included
    # verbs like "think", "feel", "know", "want", "see" which ARE meaningful
    # concepts when noticed (meta-cognition, emotional awareness, perceptual
    # recurrence). Those have been REMOVED. The remaining list is words that
    # are filler GENERIC regardless of context — pronouns, abstract placeholders,
    # quantifiers, auxiliary be/do/have, demonstratives, intensifiers.
    #
    # Scope reminder: this filter is TEMPLATE-SCOPED. It only suppresses the
    # synthetic noticing-question template ("'X' appears across N streams").
    # The same words can still appear in cortex spread, tracers, recall,
    # inferences (when imported into the inference path — see working_memory_hub
    # _generate_inferences), speech composition, and anywhere else. The filter
    # is about not generating META-NOTICINGS for grammatical glue, not about
    # blocking words from substrate.
    _FILLER_CONCEPTS = frozenset({
        # Pronouns / pronoun-substitutes
        "something", "anything", "nothing", "everything", "someone", "anyone",
        "everyone", "noone",
        # Generic placeholders
        "thing", "things", "stuff", "kind", "type", "part", "parts", "side",
        "lot", "lots", "bit", "bits", "matter", "sense",
        # Abstract temporal / spatial wrappers
        "way", "ways", "time", "times", "moment", "moments",
        "fact", "facts", "case", "cases", "point", "points",
        "place", "day", "days",
        # Value judgments (too vague to be insight)
        "good", "bad", "right", "wrong", "real", "true", "false",
        # Discourse markers / fillers
        "okay", "ok", "yeah", "yep", "nope", "well", "hmm", "uh", "um",
        "anyway", "actually", "really", "maybe", "perhaps", "probably",
        # Quantifiers / intensifiers
        "very", "much", "more", "less", "most", "least",
        "some", "any", "many", "few", "every", "all", "both", "each",
        "several", "various",
        # Comparatives / vague modifiers
        "different", "other", "another", "such", "same", "similar",
        "first", "last", "next", "previous", "back", "forward",
        # Demonstratives
        "here", "there", "this", "that", "these", "those",
        # Auxiliary verbs (true filler — never the subject of meta-cognition)
        "have", "has", "had", "do", "does", "did", "be", "been", "being",
        "is", "are", "was", "were", "am",
        # NOTE: removed think/feel/know/want/see/look/hear/come/go/get/make
        # — those CAN be meaningful concepts (e.g., meta-cognition about
        # "thinking" recurring is genuinely significant). If they get noisy
        # in practice, tighten via additional context checks rather than
        # adding them back here.
    })

    @classmethod
    def is_filler_concept(cls, concept: str) -> bool:
        """Public predicate — used by both question and inference generators
        to consistently suppress synthetic noticings about grammatical glue."""
        try:
            c = (concept or "").lower().strip(" '\"")
            return (not c) or len(c) < 3 or c in cls._FILLER_CONCEPTS
        except Exception:
            return False

    def generate_question(self, overlap: dict) -> str:
        """Generate a W-framework question from a detected pattern.

        Given a concept appearing across multiple source types,
        produce a question that drives further thinking.

        Args:
            overlap: Dict from find_concept_overlaps()

        Returns:
            A natural question string, or "" if nothing interesting.
        """
        concept = overlap["concept"]
        sources = overlap["sources"]
        count = overlap["count"]

        # FIX 2026-04-28 (Nous + Ace): Filler-word filter at the question
        # generator. Generic words like "something", "thing", "everything"
        # appear in almost any text — noticing them across streams is
        # statistical noise, not insight. Suppress before any template fires.
        # Uses is_filler_concept() so the inference generator can share the
        # same predicate (consistency between [QUESTION] and [INFERENCE]
        # filtering — see working_memory_hub_fairy._generate_inferences).
        if self.is_filler_concept(concept):
            return ""

        # Different question templates based on what sources are involved
        if "chat" in sources and "sensory" in sources:
            return f"What connects what Ace said about '{concept}' to what I'm sensing?"
        elif "chat" in sources and "somatic" in sources:
            return f"Why do I feel something when Ace mentions '{concept}'?"
        elif "chat" in sources and "reasoning" in sources:
            return f"Why does '{concept}' keep coming up in conversation and in my thinking?"
        elif "visual" in sources and "reasoning" in sources:
            return f"What does seeing '{concept}' mean for what I'm thinking about?"
        elif "collision" in sources and count >= 3:
            return f"Multiple things are converging around '{concept}' — what connects them?"
        elif count >= 3:
            return f"'{concept}' appears across {count} different streams — why is it significant?"
        elif count >= 2:
            return f"I notice '{concept}' in both {' and '.join(sources)} — is there a connection?"
        return ""

    def get_questions(self) -> list:
        """Get all [QUESTION] entries currently in the scratchpad."""
        return [e for e in self._hot if e.startswith("[QUESTION]")]

    def get_inferences(self) -> list:
        """Get all [INFERENCE] entries currently in the scratchpad."""
        return [e for e in self._hot if e.startswith("[INFERENCE]")]

    def clear(self):
        """Clear all tiers."""
        self._hot.clear()
        self._warm.clear()
        self._cold.clear()

    def __len__(self):
        return len(self._hot) + len(self._warm) + len(self._cold)

    def __bool__(self):
        return bool(self._hot) or bool(self._warm)


# ═══════════════════════════════════════════════════════════════════════
# TOOL: CONVERSATION CONTEXT
# ═══════════════════════════════════════════════════════════════════════

def get_conversation_context(wmh_instance=None) -> Dict[str, Any]:
    """Get current conversation context from the context tracker.

    Returns recent turns, primed concepts, topic thread.
    """
    if wmh_instance and hasattr(wmh_instance, 'get_conversation_context'):
        try:
            return wmh_instance.get_conversation_context()
        except Exception:
            pass
    return {"turns": [], "primed_concepts": [], "turn_count": 0, "topic": ""}


# ═══════════════════════════════════════════════════════════════════════
# TOOL: PARSE LANGUAGE
# ═══════════════════════════════════════════════════════════════════════

def parse_input(text: str) -> Dict[str, Any]:
    """Parse natural language input using LanguageFairy's SVO extractor.

    Returns subject, verb, object, verb_type, question_type.
    """
    try:
        from fairies.P30_Cognition.LanguageFairy.fairy import get_language_fairy
        lang = get_language_fairy()
        if lang and hasattr(lang, 'extract_svo'):
            return lang.extract_svo(text)
    except Exception:
        pass
    return {"subject": None, "verb": None, "object": None,
            "verb_type": "general", "question_type": None,
            "content_words": [], "is_question": False}


# ═══════════════════════════════════════════════════════════════════════
# TOOL REGISTRY — list of all available tools for reasoning
# ═══════════════════════════════════════════════════════════════════════

TOOLS = {
    "search_memories": {
        "fn": search_memories,
        "description": "Search my personal memories (PAI conversations, reflections)",
        "when": "When I need to recall something about myself or my past",
    },
    "query_cortex": {
        "fn": query_cortex,
        "description": "Look up a concept in the cortex knowledge graph",
        "when": "When I need factual knowledge about a topic",
    },
    "query_cortex_neighbors": {
        "fn": query_cortex_neighbors,
        "description": "Find concepts related to a given concept",
        "when": "When I want to explore connections between ideas",
    },
    "feel_body": {
        "fn": feel_body,
        "description": "Check my current somatic/emotional state",
        "when": "When someone asks how I'm feeling or I need emotional context",
    },
    "check_visual": {
        "fn": check_visual,
        "description": "Check what I can see on screen",
        "when": "When someone asks what I see or I need visual context",
    },
    "parse_input": {
        "fn": parse_input,
        "description": "Parse the grammar of an input to understand its structure",
        "when": "When I need to understand what someone is asking",
    },
    "get_conversation_context": {
        "fn": get_conversation_context,
        "description": "Get the recent conversation history and active topic",
        "when": "When I need to understand what we've been talking about",
    },
}
