import os, sys, tempfile, importlib.util
os.environ["AKASHIC_EDGE_SLOT_FIX"]="1"
def load(p,n):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); sys.modules[n]=m; s.loader.exec_module(m); m._mlog=lambda *a,**k:None; return m
mod=load(sys.argv[1],"mm")
k=lambda i:"n%03d"%i
# P1: node evict where evicted node is the LARGER endpoint (CSR path)
d=tempfile.mkdtemp(prefix="w15p_"); p=d+"/t.manifold"
mm=mod.ManifoldMemory(p,node_capacity=16,edge_capacity=40)
for i in range(16): mm.upsert_node(k(i),activation=(0.0 if i==5 else 1.0))
mm.link(k(2),k(5),weight=0.5); mm.link(k(5),k(9),weight=0.5)
mm.close(); mm=mod.ManifoldMemory(p); print("csr",mm._use_csr)
s5=mm._key_index[k(5)]
ev=mm._evict_coldest_node(); print("evicted",ev==s5)
live=[mm._read_edge(s)[:2] for s in range(mm._edge_count) if mm._read_edge(s)[4]==0]
print("P1 live edges touching evicted node:",[e for e in live if s5 in e])
mm.close()
# P2: CSR path at capacity, link() on an evicted pair aliases via stale CSR entry
d=tempfile.mkdtemp(prefix="w15p_"); p=d+"/t.manifold"
mm=mod.ManifoldMemory(p,node_capacity=16,edge_capacity=2)
for i in range(16): mm.upsert_node(k(i))
mm.link(k(0),k(1),weight=0.1); mm.link(k(2),k(3),weight=0.2)
mm.close(); mm=mod.ManifoldMemory(p)
mm.link(k(4),k(5),weight=0.9)   # evicts (0,1) slot 0, reuses it
before=[mm._read_edge(s)[:3] for s in range(2)]
r=mm.link(k(0),k(1),weight=0.1)
after=[mm._read_edge(s)[:3] for s in range(2)]
print("P2 before",before,"after",after,"ret",r)
print("P2 get_neighbors(n000)",mm.get_neighbors(k(0)))
mm.close()
