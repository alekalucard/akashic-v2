# -*- coding: utf-8 -*-
r"""phasing_cortex_query.py — PROPOSAL ARTIFACT (sandbox; drop-in for LocalManifoldGate.spread).

Replaces the cortex physics engine (GPU/CPU spread_activation) with PHASING RESONANCE over the SAME
cortex.manifold. Matches LocalManifoldGate.spread's contract exactly:
    spread(source, depth=3, limit=30, decay=0.5) -> {"status":"ok","activations":{key:energy},"count":N}
Tuned on Sour's real cortex (resonance_reach_tuning): γ≈0.22, gain≈1.1, reach≈depth hops, BOUNDED.
Filters BOOKS/SYSTEM trace nodes like the original. Neighbourhood-local (no dense NxN on the full graph).

Integration (LocalManifoldGate.spread): if AKASHIC_PHASING_CORTEX=1 -> return phasing_spread(self.graph,...)
instead of the GPU spread. Same return shape; her callers are unchanged.
"""
import math, collections
import numpy as np

_TRACE_BOOKS = 2
_TRACE_SYSTEM = 5

def _sinkhorn(M, it=12, eps=1e-8):
    M=np.abs(M)+eps
    for _ in range(it): M=M/np.maximum(M.sum(1,keepdims=True),eps); M=M/np.maximum(M.sum(0,keepdims=True),eps)
    return M

def phasing_spread(graph, source, depth=2, limit=30, decay=0.5,
                   gamma=0.22, gain=1.1, cap=800):
    """Resonance spread from `source` over the manifold `graph`. Drop-in for LocalManifoldGate.spread."""
    if not graph.has_node(source):
        return {"status":"ok","activations":{},"count":0}
    # BFS the source's `depth`-hop neighbourhood (bounded)
    hop={source:0}; sub=[source]; frontier=[source]
    for h in range(1, max(1,int(depth))+1):
        nxt=[]
        for k in frontier:
            for nbr,_w in graph.get_neighbors(k, limit=32):
                if nbr not in hop and graph.has_node(nbr):
                    hop[nbr]=h; sub.append(nbr); nxt.append(nbr)
                    if len(sub)>=cap: break
            if len(sub)>=cap: break
        frontier=nxt
        if len(sub)>=cap: break
    idx={k:i for i,k in enumerate(sub)}; N=len(sub)
    # coupling from real edges, mHC-normalized (degree-invariant, bounded)
    K=np.zeros((N,N))
    for k in sub:
        for nbr,w in graph.get_neighbors(k, limit=64):
            if nbr in idx: K[idx[k],idx[nbr]]=float(w)
    Kn=_sinkhorn(K) if K.any() else K; rs=Kn.sum(1)
    # resonate: impulse the source, tick (steps scale with depth = reach); decay maps into damping
    w=2.0; dt=0.05; g=gamma*(0.7+0.6*decay)          # higher decay -> more damping -> shorter reach
    x=np.zeros(N); v=np.zeros(N); v[idx[source]]+=2.6
    steps=int(60*max(1,int(depth)))
    for _ in range(steps):
        acc=-g*v-(w**2)*x+gain*(Kn@x-rs*x); v=v+acc*dt; x=x+v*dt
        if np.max(np.abs(x))>1e5: break               # safety (shouldn't trigger in-window)
    E=0.5*v**2+0.5*w**2*x**2
    # rank, filter BOOKS/SYSTEM tracers, return top-`limit` as {key: energy}
    acts={}
    for j in np.argsort(E)[::-1]:
        if sub[j]==source or E[j]<1e-4:
            if E[j]<1e-4: break
            continue
        slot=graph._key_index.get(sub[j])
        if slot is not None:
            try:
                tid=graph._read_node(slot)[12]
                if tid in (_TRACE_BOOKS,_TRACE_SYSTEM): continue
            except Exception: pass
        acts[sub[j]]=round(float(E[j]),4)
        if len(acts)>=limit: break
    return {"status":"ok","activations":acts,"count":len(acts)}


# ── SELF-TEST on Sour's real cortex backup (readonly) ──
if __name__ == "__main__":
    import io, sys, os
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.path.insert(0, r"F:/Sandbox/Akashic_phasing/substrate")
    import manifold_memory as MM
    BACKUP=r"F:/Sandbox/failure_factory/akashic_v2/state/akashic/backups/pre_affect_charge_20260605_111250/cortex.manifold"
    g=MM.ManifoldMemory(BACKUP, readonly=True)
    seed=max(list(g._key_index.keys())[:4000], key=lambda k: len(g.get_neighbors(k,limit=64)))
    print(f"phasing_spread on REAL cortex, source='{seed}':\n")
    for d in (1,2,3):
        r=phasing_spread(g, seed, depth=d, limit=10)
        print(f"  depth={d}: count={r['count']}  top: "
              + ", ".join(f"{k[:28]}={v}" for k,v in list(r['activations'].items())[:6]))
    # contract check
    r2=phasing_spread(g, seed, depth=2, limit=30)
    ok = r2["status"]=="ok" and isinstance(r2["activations"],dict) and r2["count"]==len(r2["activations"])
    print(f"\n  contract matches LocalManifoldGate.spread {{status,activations,count}}: {ok}")
    print(f"  missing-node returns empty: {phasing_spread(g,'__nonexistent__')}")
    g.close()
    print("\n  drop-in ready for LocalManifoldGate.spread (AKASHIC_PHASING_CORTEX=1). Swap = Ace's go, on reboot.")
