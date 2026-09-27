import mmap, os, sys, time, threading
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m.bin")
with open(p,"wb") as f: f.write(b"\x00"*(1<<20))
f = open(p,"r+b"); mm = mmap.mmap(f.fileno(), 0)   # shared RW map, like self._mm
# thread-local read view
f2 = open(p,"rb"); v2 = mmap.mmap(f2.fileno(), 0, access=mmap.ACCESS_READ)
print("py", sys.version.split()[0], "gil?", getattr(sys,"_is_gil_enabled",lambda:True)())
for op,fn in [("remove", lambda: os.remove(p)), ("rename", lambda: os.rename(p, p+".x"))]:
    try:
        fn(); print(op, "SUCCEEDED")
    except Exception as e:
        print(op, "BLOCKED:", type(e).__name__, e)
# cost of a failing open+mmap
bad = p + ".nonexistent"
t=time.perf_counter()
N=20000
for _ in range(N):
    try:
        _f=open(bad,"rb"); _v=mmap.mmap(_f.fileno(),0,access=mmap.ACCESS_READ)
    except Exception:
        pass
print("failing open+mmap: %.1f us/attempt" % ((time.perf_counter()-t)/N*1e6))
# cost of a SUCCEEDING slice read through shared map (baseline single thread)
t=time.perf_counter()
for _ in range(N): b=mm[100:124]
print("shared slice read : %.2f us/read" % ((time.perf_counter()-t)/N*1e6))
mm.close(); v2.close(); f.close(); f2.close()
