"""Check GGUF tensor shapes to verify dimension assumptions for LoRA weights."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

from gguf import GGUFReader

reader = GGUFReader(GGUF_PATH)

# Focus on layer 0 to understand dimensions
print("=== Layer 0 Tensor Shapes ===")
print("(GGUF ne[0]=fast/inner dim, ne[1]=slow/outer dim)")
print("(Physical flat layout: [ne[1], ne[0]] row-major)\n")

interesting = {}
for tensor_info in reader.tensors:
    name = tensor_info.name
    if name.startswith("blk.0.") or name in ["token_embd.weight", "output.weight",
                                                "token_embd_norm.weight", "output_norm.weight"]:
        shape = list(tensor_info.shape)
        interesting[name] = shape

# Sort and print
for name in sorted(interesting.keys()):
    shape = interesting[name]
    total = 1
    for s in shape:
        total *= s

    # For 2D: physical = [ne[1], ne[0]] row-major
    if len(shape) == 2:
        phys = f"Physical: [{shape[1]}, {shape[0]}] row-major"
    elif len(shape) == 1:
        phys = f"Physical: [{shape[0]}]"
    else:
        phys = f"Physical: {shape}"

    print(f"  {name:45s} ne={shape}  {phys}  ({total:,} params)")

# Specific analysis for LoRA weights
print("\n=== LoRA Weight Dimension Analysis ===")
print("For matmul y = x @ W where x=[C=2048]:\n")

lora_weights = {
    "blk.0.time_mix_w1.weight": "W decay LoRA1 (x @ w1 → inner)",
    "blk.0.time_mix_w2.weight": "W decay LoRA2 (inner @ w2 → output)",
    "blk.0.time_mix_a1.weight": "A assoc LoRA1",
    "blk.0.time_mix_a2.weight": "A assoc LoRA2",
    "blk.0.time_mix_v1.weight": "V bonus LoRA1",
    "blk.0.time_mix_v2.weight": "V bonus LoRA2",
    "blk.0.time_mix_g1.weight": "G gate LoRA1",
    "blk.0.time_mix_g2.weight": "G gate LoRA2",
}

for tensor_info in reader.tensors:
    if tensor_info.name in lora_weights:
        name = tensor_info.name
        desc = lora_weights[name]
        shape = list(tensor_info.shape)

        print(f"  {name}")
        print(f"    ne = {shape}")
        print(f"    Physical flat: [{shape[1] if len(shape)==2 else '?'}, {shape[0] if len(shape)==2 else '?'}] row-major")

        if len(shape) == 2:
            # ne[0] = fast dim, ne[1] = slow dim
            # Physical: [ne[1], ne[0]] = rows=ne[1], cols=ne[0]
            #
            # Regular weights (like receptance): ne=(2048, 2048)
            #   Physical [2048, 2048] = [out, in] like PyTorch
            #   matmul_vec reads transpose: logical[i,j] = phys[j*k+i]
            #   So x[in] @ logical[in, out] = correct
            #
            # LoRA w1: if ne=(rank, 2048), physical = [2048, rank]
            #   This is [in_dim, rank] = already x @ w1 layout!
            #   matmul_vec would read transpose: logical[i,j] = phys[j*rank+i]
            #     = logical is [rank, 2048] → x[2048] @ [rank, 2048] = WRONG (dim mismatch)
            #   matmul_vec_direct reads direct: [2048, rank] → x[2048] @ [2048, rank] = CORRECT!

            ne0, ne1 = shape[0], shape[1]
            print(f"    {desc}")
            if ne0 < ne1:
                print(f"    LoRA: ne[0]={ne0} (rank), ne[1]={ne1} (C)")
                print(f"    Physical layout: [{ne1}, {ne0}] = [C, rank]")
                print(f"    For x[C] @ w → inner[rank]: physical IS already [C, rank]")
                print(f"    → matmul_vec_direct reads [C, rank] directly ✓")
            elif ne0 > ne1:
                print(f"    LoRA: ne[0]={ne0} (C), ne[1]={ne1} (rank)")
                print(f"    Physical layout: [{ne1}, {ne0}] = [rank, C]")
                print(f"    For inner[rank] @ w → output[C]: physical IS already [rank, C]")
                print(f"    → matmul_vec_direct reads [rank, C] directly ✓")
            else:
                print(f"    Square matrix: ne={ne0}x{ne1}")
        print()

# Also check the regular weights for comparison
print("=== Regular Weight Shapes (for comparison) ===")
regular_weights = [
    "blk.0.time_mix_receptance.weight",
    "blk.0.time_mix_key.weight",
    "blk.0.time_mix_value.weight",
    "blk.0.time_mix_output.weight",
    "blk.0.channel_mix_key.weight",
    "blk.0.channel_mix_value.weight",
]
for tensor_info in reader.tensors:
    if tensor_info.name in regular_weights:
        shape = list(tensor_info.shape)
        print(f"  {tensor_info.name}: ne={shape} physical=[{shape[1]},{shape[0]}]")

print("\n=== Embedding ===")
for tensor_info in reader.tensors:
    if tensor_info.name == "token_embd.weight":
        shape = list(tensor_info.shape)
        print(f"  token_embd.weight: ne={shape} physical=[{shape[1]},{shape[0]}]")
        print(f"  Embedding lookup: row token_id → emb[token_id * {shape[0]} .. (token_id+1) * {shape[0]}]")

print("\n=== Done ===")
