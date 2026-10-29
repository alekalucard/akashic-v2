import os, subprocess, sys, tempfile
REPO="/home/user/akashic-v2"
SRC=REPO+"/code/infrastructure/manifold_memory.py"
TEST=REPO+"/code/tests/test_w15_edge_slot.py"
NE='_w15 = os.environ.get("AKASHIC_EDGE_SLOT_FIX", "0") == "1"'
M={
 "R1_nodeevict_default_on":[(NE,'_w15 = os.environ.get("AKASHIC_EDGE_SLOT_FIX", "1") == "1"')],
 "R2_nodeevict_always_on":[(NE,'_w15 = True')],
 "R3_nodeevict_never":[(NE,'_w15 = False')],
 "R4_one_orientation":[("                            (_er[0] == min_slot and _er[1] == neighbor_id) or\n                            (_er[1] == min_slot and _er[0] == neighbor_id)):",
                       "                            (_er[0] == min_slot and _er[1] == neighbor_id)):")],
 "R5_link_fix_pop_once":[("                    while slot in self._free_edge_slots:\n                        self._free_edge_slots.remove(slot)",
                          "                    self._free_edge_slots.pop()")],
 "R6_endpoint_any":[("                    if _er[4] == FLAG_DELETED or not (","                    if _er[4] == FLAG_DELETED or min_slot not in _er[:2] or not (")],
}
tmp=tempfile.mkdtemp(prefix="w15r_")
mp=os.path.join(tmp,"main.py"); open(mp,"wb").write(subprocess.check_output(["git","-C",REPO,"show","origin/main:code/infrastructure/manifold_memory.py"]))
src=open(SRC).read()
for n,subs in M.items():
    s=src
    for o,nw in subs:
        assert s.count(o)==1,(n,o); s=s.replace(o,nw)
    p=os.path.join(tmp,n+".py"); open(p,"w").write(s)
    env=dict(os.environ,W15_MM_PATH=p,W15_MAIN_PATH=mp); env.pop("AKASHIC_EDGE_SLOT_FIX",None)
    r=subprocess.run([sys.executable,"-W","ignore",TEST],env=env,capture_output=True,text=True)
    f=[l for l in r.stderr.splitlines() if l.startswith(("FAIL:","ERROR:"))]
    print(n,"rc=",r.returncode,f)
