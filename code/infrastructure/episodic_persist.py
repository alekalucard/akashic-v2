"""
episodic_persist.py — episodic LINEAR persistence (Ace 2026-06-26 "save linear persistence").

PRODUCTION home of the EpisodicPersister, promoted from sandbox/episodic_linear/ after
proof_episodic_persist.py (13/13) + proof_episodic_integration.py (18/18, real deque eviction +
real MomentBinder moment-dict adapter + real AkashicManifold federation handle).

As a moment rolls off the specious-present buffer (the OLDEST, evicted), persist it to a per-mind
episodic manifold — every moment, in temporal order = the unbroken lived thread (STM->LTM handoff at
eviction). GIST not raw. significance -> WEIGHT not GATE (Ace's correction: keep all, the charged ones
are more salient; the mundane fade but are SAVED). Temporal edge prev->this = the linear thread,
walkable. Reuses the proven ManifoldMemory recipe. Pure: a buffer + a manifold region. No model calls.
"""


def moment_gist(moment, max_len=1024):
    """Gist-over-raw (DialogueTimeline principle): a compact node text, NOT the raw bundle.
    v1 template-gist (a GistFairy / Florence enricher can enrich later)."""
    ts = float(moment.get("ts", 0.0))
    feeling = str(moment.get("feeling", "neutral"))
    gist = moment.get("gist") or moment.get("input_text", "")
    concepts = moment.get("concepts") or []
    sources = moment.get("sources") or []
    sig = float(moment.get("significance", 0.0))
    snip = ("mom1\nts: %.3f\ngist: %s\nfeel: %s\nsig: %.3f\nconcepts: %s\nsrc: %s"
            % (ts, str(gist)[:300], feeling, sig,
               ",".join(str(c) for c in concepts[:8]),
               ",".join(str(s) for s in sources[:6])))
    return snip[:max_len]


class EpisodicPersister:
    """Linear-persists evicted moments to a per-mind episodic manifold via the proven recipe:
    upsert_node(moment_key, activation=weight, snippet=gist, tracer, region=EPISODIC) + temporal edge."""

    def __init__(self, region, mind="nous", tracer_personal=1, region_episodic=2,
                 rel_temporal=3):
        self.region = region
        self.mind = str(mind).lower()
        self.tracer = tracer_personal
        self.region_episodic = region_episodic
        # TYPED LINK 2026-08-26 (Nous + Ace): REL_TEMPORAL. link() defaults to
        # REL_COACTIVATE=0 ('generic co-occurrence, weakest'), so the temporal edge
        # below was silently recorded as the WEAKEST relation. Measured on her live
        # node: 43 of 43 new edges rel_type=0, while the rebuild's 68,326 were type 3.
        # Kept as a plain int like tracer_personal/region_episodic so this module stays
        # import-free of manifold_memory; the fairy may pass the named REL_TEMPORAL.
        self.rel_temporal = rel_temporal
        self._last_key = None
        self.persisted = 0
        self.order = []          # the linear thread of keys, in persist order

    def _key(self, moment):
        return "moment:%s:%.3f" % (self.mind, float(moment.get("ts", 0.0)))

    def persist(self, moment):
        """Persist ONE evicted moment (linear, lossless, affect-weighted). Returns the key."""
        key = self._key(moment)
        if self.region.has_node(key):                 # idempotent — never double-persist a moment
            return key
        # significance -> activation WEIGHT: charged moments more salient; mundane still SAVED (floor 0.05)
        weight = max(0.05, min(1.0, float(moment.get("significance", 0.0)) or 0.05))
        self.region.upsert_node(key, activation=weight, snippet=moment_gist(moment),
                                tracer_id=self.tracer, region=self.region_episodic)
        if self._last_key:                             # temporal edge prev->this = the linear thread
            # AFFECT-WEIGHTED 2026-08-31 (Nous + Ace): `weight` is this moment's
            # significance, computed above for upsert_node's activation and then
            # dropped here in favour of link()'s default 0.25. Verified on Nous's
            # live store: the typed temporal edges all read w=0.25 while the old
            # fossil thread was written at w=1.0. Ace: "when her system learns to
            # map context like this the AFFECT of the system gets weight." The
            # affect is already in scope; spend it. Her VERB was already correct
            # (TYPED LINK 2026-08-26) -- this is the second half of that fix.
            self.region.link(self._last_key, key, weight=weight,
                             rel_type=self.rel_temporal, tracer_id=self.tracer)
        self._last_key = key
        self.order.append(key)
        self.persisted += 1
        return key
