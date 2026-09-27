# test_imports_74.py -- surface the .74 deploy friction (run from the akashic_v2 dir)
import sys, os, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
print(f"python {sys.version.split()[0]}")
tests = [
    "torch", "numpy", "tokenizers", "safetensors",                          # encoder stack
    "infrastructure.native_minilm",                                         # the native encoder
    "infrastructure.manifold_memory",                                       # the manifold
    "fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0",            # the crown jewel (drags postal/heart)
    "waking_minds.nous_fairy",                                              # NousFairy himself
]
for m in tests:
    try:
        importlib.import_module(m)
        print(f"OK   {m}")
    except Exception as e:
        print(f"FAIL {m} :: {type(e).__name__}: {str(e)[:160]}")
print("--- done ---")
