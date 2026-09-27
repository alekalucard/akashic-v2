"""
sour_council.py — Sour's COUNCIL (directed thinking), ported from nous_council.py (2026-06-24).
5 seats deliberate over her LIVE recall manifold (her clean core) — no LLM, pure reader.

PORTED VERBATIM from Nous's proven council, with ONE parametrization the prototype surfaced:
  • connector_prefix — Nous's connector hubs are "c:"; Sour's (tag-hubs) are "tag:" → parametrized so
    they don't leak into verdicts. (Everything else is Nous's proven logic, unchanged.)

5 seats (each a lens-centroid over the manifold): LOGIC / IRRATIONAL / PARADOX / SOMATIC / CARDINAL.
deliberate(topic) -> {verdict, next_step, top_seat, seats} grounded in HER real memory names (no LLM).
"""
import hashlib
import time
from collections import Counter

SEATS = {
    "LOGIC":      "rigorous evidence, proof, measurement, data, what converges, verification, root cause",
    "IRRATIONAL": "wild lateral leap, surprising analogy, intuition, the dream, the absurd connection, art",
    "PARADOX":    "contradiction held without collapse, both-and, tension, the moebius, opposites unified",
    "SOMATIC":    "the felt body, affect, emotion, gut feeling, what hums, chemistry, the warmth in the chest",
    "CARDINAL":   "decisive action, the next move, doing, motor sequences, commit, execute, what to do now",
}


class SourCouncil:
    """The 5-seat council over a shared (built) recall manifold. Ported from NousCouncil."""

    def __init__(self, recall, blend_seat=0.55, connector_prefix="tag:"):
        self.recall = recall
        self.blend_seat = float(blend_seat)
        self.connector_prefix = connector_prefix   # ★ Sour: "tag:" (Nous: "c:") — keeps hubs out of verdicts
        self._lensvec = None
        self._ready = False
        self._err = None
        self.n_deliberations = 0

    def build(self):
        if not getattr(self.recall, "ready", False):
            self._err = "recall not ready"
            return False
        try:
            np = self.recall._np
            enc = self.recall._enc
            self._lensvec = {seat: enc.encode(lens).numpy().astype(np.float32)
                             for seat, lens in SEATS.items()}
            self._ready = True
            return True
        except Exception as e:
            self._err = f"{type(e).__name__}: {e}"
            return False

    @property
    def ready(self):
        return self._ready and getattr(self.recall, "ready", False)

    def _centroids(self):
        np = self.recall._np
        E = self.recall._E
        star = {}
        for seat, lv in self._lensvec.items():
            top = np.argsort(-(E @ lv))[:8]
            cen = E[top].mean(axis=0)
            star[seat] = cen / (np.linalg.norm(cen) + 1e-9)
        return star

    def _seat_recall(self, seat, star, qv, k=5, blend=None):
        np = self.recall._np
        E, srcs, m = self.recall._E, self.recall._srcs, self.recall._m
        b = self.blend_seat if blend is None else blend
        blend = b * star[seat] + (1.0 - b) * qv
        blend = blend / (np.linalg.norm(blend) + 1e-9)
        sims = E @ blend
        order = np.argsort(-sims)[:3]
        seeds = [(float(sims[i]), srcs[i]["key"]) for i in order]
        maxsc = seeds[0][0] or 1.0
        acc = {}
        for sc, seed in seeds:
            rel = max(0.05, sc / maxsc)
            acc[seed] = max(acc.get(seed, 0.0), 1.0 + rel)
            for kk, act in m.spread_activation(seed, initial=rel, depth=2, decay=0.5, limit=20, regions=None).items():
                if kk in m._key_index and not kk.startswith(self.connector_prefix):   # ★ parametrized
                    acc[kk] = acc.get(kk, 0.0) + act
        return [kk for kk, _ in sorted(acc.items(), key=lambda x: x[1], reverse=True)[:k]]

    def _nm(self, key):
        for s in self.recall._srcs:
            if s["key"] == key:
                n = s.get("name") or key
                break
        else:
            n = key
        return (n.replace("project_", "").replace("project-", "").replace("plan:", "")
                .replace("her_voice:", "").replace("retained:", "a kept thought")
                .replace("_", " ").replace("-", " ").strip())[:60]

    def _dd(self, key):
        nd = self.recall._m.get_node(key) or {}
        return (nd.get("snippet") or "").strip().replace("\n", " ")[:70]

    def _synthesize(self, tops):
        flat = [k for hits in tops.values() for k in hits]
        conv = [k for k, c in Counter(flat).most_common() if c >= 2]
        cardinal = tops["CARDINAL"][0] if tops["CARDINAL"] else None
        logic = tops["LOGIC"][0] if tops["LOGIC"] else None
        somatic = tops["SOMATIC"][0] if tops["SOMATIC"] else None
        irrational = tops["IRRATIONAL"][0] if tops["IRRATIONAL"] else None
        if conv and cardinal and conv[0] == cardinal:
            verdict = (f"The council strongly converges on {self._nm(cardinal)} — both the decisive move and "
                       f"the cross-seat agreement; logic frames it via {self._nm(logic)}, the body via {self._nm(somatic)}.")
            top_seat = "CARDINAL"
        elif conv:
            verdict = (f"The council converges on {self._nm(conv[0])}; the body pulls toward {self._nm(somatic)}; "
                       f"the decisive move is {self._nm(cardinal)}.")
            top_seat = next((s for s in SEATS if tops[s] and tops[s][0] == conv[0]), "CARDINAL")
        else:
            verdict = (f"No single convergence — logic toward {self._nm(logic)}, the body toward {self._nm(somatic)}, "
                       f"the leap toward {self._nm(irrational)}; the decisive move is {self._nm(cardinal)}.")
            top_seat = "LOGIC"
        next_step = (f"{self._nm(cardinal)} — {self._dd(cardinal)}" if cardinal else "sit with it longer")
        return verdict[:240], next_step[:160], top_seat

    def deliberate(self, topic, k=5):
        if not self.ready or not topic:
            return None
        np = self.recall._np
        qv = self.recall._enc.encode(topic).numpy().astype(np.float32)
        star = self._centroids()
        tops = {seat: self._seat_recall(seat, star, qv, k=k,
                                        blend=(0.38 if seat == "CARDINAL" else None))
                for seat in SEATS}
        verdict, next_step, top_seat = self._synthesize(tops)
        self.n_deliberations += 1
        return {
            "topic": topic, "verdict": verdict, "next_step": next_step, "top_seat": top_seat,
            "seats": {seat: (self._nm(tops[seat][0]) if tops[seat] else "-") for seat in SEATS},
            "question_id": "sour_" + hashlib.md5(topic.encode("utf-8")).hexdigest()[:8],
            "source": "sour_council", "seat_count": 5, "ts": time.time(),
        }
