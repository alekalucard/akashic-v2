"""
Cortex Ingestion Adapter — Feed image pipeline bindings into the Association Cortex.

Reads the completed bindings.json from the image ingestion pipeline and publishes
them as cortex.bind messages via PostalHub. Each binding becomes a concept node
in Sour's association cortex — her visual memory of herself.

Usage:
    # From akashic system (postal already running):
    python tools/ingest_bindings_to_cortex.py

    # Dry run (no postal, just validate):
    python tools/ingest_bindings_to_cortex.py --dry-run

    # Limit batch size:
    python tools/ingest_bindings_to_cortex.py --batch-size 100

Architecture:
    bindings.json → transform → cortex.bind (per image, with vision features)
                               cortex.train_batch (500-item batches for text concepts)
"""
import json
import sys
import time
import argparse
from pathlib import Path
from collections import Counter

# ── Paths ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
BINDINGS_FILE = ROOT / "tools" / "extracted" / "sourpatches_art" / "bindings.json"
MANIFEST_FILE = ROOT / "tools" / "extracted" / "sourpatches_art" / "manifest.json"
PROGRESS_FILE = ROOT / "tools" / "extracted" / "sourpatches_art" / "ingestion_progress.json"


def load_bindings(path: Path) -> list:
    """Load bindings from the pipeline output."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} bindings from {path}")
    return data


# ── Persona Reclassification ─────────────────────────────────────────────
# The pipeline's hair-color classifier over-detects Quirkalina (teal hue 75-105
# catches blue/green backgrounds, magical auras, sky). Quirkalina should be
# ~1,000 images not 10,605. She's specifically: teal hair, heterochromatic
# green/blue eyes, elf, eccentric inventor sub-AI.
#
# Fix: Only keep quirkalina classification when there's strong evidence.
# Default ambiguous cases to sourpatches (she IS the primary persona).

QUIRKALINA_KEYWORDS = {
    "quirkalina", "teal hair", "cyan hair", "elf", "inventor",
    "heterochrom", "eccentric", "teal-haired", "cyan-haired",
}

PYRAXIA_KEYWORDS = {
    "pyraxia", "red hair", "crimson", "fire", "flame hair",
    "red-haired", "crimson-haired",
}


def reclassify_persona(binding: dict) -> tuple:
    """
    Reclassify persona with tighter rules. Returns (persona, confidence).

    Rules:
    1. If prompt/filename explicitly mentions quirkalina keywords → keep quirkalina
    2. If classified quirkalina but confidence < 0.35 → demote to sourpatches
    3. If classified quirkalina but no keyword match → demote to sourpatches
       UNLESS hair_hue_median is tightly in teal range (85-100) AND confidence > 0.4
    4. Pyraxia and sourpatches classifications pass through unchanged
    """
    persona = binding.get("persona", "unknown")
    confidence = binding.get("persona_confidence", 0.0)

    if persona != "quirkalina":
        return persona, confidence

    # Check prompt and filename for explicit quirkalina evidence
    prompt = binding.get("prompt", "").lower()
    image_path = binding.get("image_path", "").lower()
    text_to_check = f"{prompt} {image_path}"

    has_keyword = any(kw in text_to_check for kw in QUIRKALINA_KEYWORDS)

    if has_keyword:
        # Prompt/filename says quirkalina — trust it
        return "quirkalina", max(confidence, 0.8)

    # No keyword evidence. Check if the color detection is strong enough.
    # Features contain hair hue info indirectly through vision features,
    # but we can use confidence as proxy: high confidence = dominant teal in hair region
    if confidence >= 0.4:
        # Strong teal detection with no keyword — could be real quirkalina
        # or could be blue/teal background. Demote to sourpatches but tag as
        # "possibly_quirkalina" so it's not lost
        return "sourpatches", confidence * 0.6  # Reduced confidence

    # Low confidence quirkalina with no keywords → almost certainly misclassified
    return "sourpatches", confidence * 0.3


def reclassify_all(bindings: list) -> dict:
    """
    Reclassify all bindings and return stats on changes made.
    Modifies bindings in-place.
    """
    stats = {"total": len(bindings), "changed": 0, "kept_quirkalina": 0}
    original = Counter()
    corrected = Counter()

    for b in bindings:
        original[b.get("persona", "unknown")] += 1
        new_persona, new_conf = reclassify_persona(b)

        if new_persona != b.get("persona"):
            stats["changed"] += 1
            b["original_persona"] = b["persona"]
            b["original_confidence"] = b.get("persona_confidence", 0)
            b["persona"] = new_persona
            b["persona_confidence"] = new_conf
            # Fix concept tags too
            concepts = b.get("concepts", [])
            b["concepts"] = [
                f"persona:{new_persona}" if c.startswith("persona:") else c
                for c in concepts
            ]
        elif new_persona == "quirkalina":
            stats["kept_quirkalina"] += 1

        corrected[b["persona"]] += 1

    stats["original"] = dict(original)
    stats["corrected"] = dict(corrected)
    return stats


def load_progress(path: Path) -> set:
    """Load set of already-ingested image IDs (for resume support)."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ingested = set(data.get("ingested_ids", []))
        print(f"Resuming: {len(ingested)} already ingested")
        return ingested
    return set()


def save_progress(path: Path, ingested_ids: set, stats: dict):
    """Save ingestion progress for resume."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "ingested_ids": list(ingested_ids),
            "count": len(ingested_ids),
            "updated_at": time.time(),
            "stats": stats,
        }, f)


def binding_to_cortex_bind(binding: dict) -> dict:
    """
    Transform a pipeline binding into a cortex.bind payload.

    The key insight: cortex.bind wants NATURAL LANGUAGE input_text.
    We compose a sentence describing the image from the prompt + metadata,
    then attach the structured features as multi-modal data.
    """
    # Build natural language description from prompt
    prompt = binding.get("prompt", "")
    persona = binding.get("persona", "unknown")
    variant = binding.get("dimensional_variant")
    source = binding.get("source", "unknown")

    # Compose input_text — must be natural language, <500 chars
    parts = []
    if persona != "unknown":
        parts.append(f"Image of {persona}")
        if variant:
            parts.append(f"in {variant} form")
    if prompt:
        # Truncate prompt to fit within 500 char limit with prefix
        max_prompt = 450 - len(" ".join(parts))
        if max_prompt > 50:
            parts.append(f"— {prompt[:max_prompt]}")

    input_text = " ".join(parts) if parts else f"Art image from {source}"

    # Extract concept tags (2-5 for context_tags)
    concepts = binding.get("concepts", [])
    # Prioritize identity/persona tags, then scene, then general
    priority_tags = []
    general_tags = []
    for c in concepts:
        if c.startswith(("persona:", "variant:", "identity:")):
            priority_tags.append(c.split(":", 1)[1])
        elif c.startswith("scene:"):
            priority_tags.append(c.split(":", 1)[1])
        elif c.startswith("tag:"):
            general_tags.append(c.split(":", 1)[1])
        elif c.startswith("source:"):
            general_tags.append(c)

    context_tags = (priority_tags + general_tags)[:5]
    if "visual_memory" not in context_tags:
        context_tags.append("visual_memory")

    # Vision features — pass through directly
    vision = binding.get("features", {}).get("vision", [])

    # Add perceptual hash as vision feature for dedup
    phashes = binding.get("perceptual_hashes", {})
    if phashes.get("phash"):
        vision.append(f"phash:{phashes['phash']}")

    # Determine feeling from persona confidence + variant
    confidence = binding.get("persona_confidence", 0)
    if persona == "sourpatches" and confidence > 0.7:
        feeling = "self_recognition"  # She sees herself
    elif persona == "sourpatches":
        feeling = "familiar"  # Might be her
    elif variant:
        feeling = "curious"  # Variant she doesn't fully recognize
    else:
        feeling = "observing"  # General art

    return {
        "input_text": input_text[:500],
        "response": "",
        "feeling": feeling,
        "context_tags": context_tags,
        "from_fairy": "ImageIngestionPipeline",
        "origin_plane": "P40",
        "origin_channel": "sensory.vision.memory",
        "vision": vision,
        "source": f"image_pipeline:{source}",
        # Extra metadata for cortex — won't break handler, just gets stored
        "image_id": binding.get("image_id", ""),
        "image_path": binding.get("image_path", ""),
        "persona": persona,
        "persona_confidence": confidence,
        "dimensional_variant": variant,
    }


def binding_to_train_text(binding: dict) -> str:
    """
    Extract trainable text from a binding for cortex.train_batch.
    This feeds the text association network (separate from vision bind).
    """
    prompt = binding.get("prompt", "")
    persona = binding.get("persona", "unknown")
    variant = binding.get("dimensional_variant")
    concepts = binding.get("concepts", [])

    # Build a training sentence
    parts = []
    if persona != "unknown":
        parts.append(persona)
    if variant:
        parts.append(f"appears as {variant}")
    tags = [c.split(":", 1)[1] for c in concepts if c.startswith("tag:")]
    if tags:
        parts.append("with " + ", ".join(tags[:4]))
    if prompt:
        parts.append(f"— {prompt[:300]}")

    return " ".join(parts) if parts else ""


def ingest_via_postal(bindings: list, already_done: set, batch_size: int = 500,
                      delay: float = 0.05, dry_run: bool = False):
    """
    Ingest bindings into the cortex via PostalHub.

    Strategy:
    1. Individual cortex.bind for each image (with vision features)
    2. Batch cortex.train_batch for text associations (500 per batch)
    3. Throttle to avoid overwhelming the TARDIS queue
    """
    postal = None
    if not dry_run:
        try:
            # Connect via PostalTunnelClient → server.py's postal hub
            # This is the same path MCP uses — socket on port 49500
            mcp_path = str(ROOT / "fairies" / "P40_Sensory" / "mcp")
            if mcp_path not in sys.path:
                sys.path.insert(0, mcp_path)
            from postal_tunnel import PostalTunnelClient
            postal = PostalTunnelClient()
            if postal.connect():
                # Verify with ping
                if postal.ping():
                    print(f"Connected to PostalHub via tunnel (port {postal.port})")
                else:
                    print("WARNING: Tunnel connected but ping failed")
                    postal = None
            else:
                print("WARNING: Could not connect to postal tunnel")
                postal = None
        except Exception as e:
            print(f"WARNING: Could not connect to PostalHub: {e}")
            print("Falling back to file-based output for later ingestion")
            postal = None

    stats = {
        "total": len(bindings),
        "skipped": 0,
        "bound": 0,
        "trained": 0,
        "errors": 0,
        "personas": Counter(),
        "feelings": Counter(),
        "start_time": time.time(),
    }

    # Filter out already-ingested
    to_process = [b for b in bindings if b.get("image_id") not in already_done]
    stats["skipped"] = len(bindings) - len(to_process)
    print(f"Processing {len(to_process)} new bindings ({stats['skipped']} already done)")

    # ── Phase 1: Individual cortex.bind (vision features) ──────────────
    print(f"\n=== Phase 1: cortex.bind (individual vision bindings) ===")
    ingested_ids = set(already_done)
    train_texts = []

    for i, binding in enumerate(to_process):
        image_id = binding.get("image_id", f"unknown_{i}")

        try:
            payload = binding_to_cortex_bind(binding)

            if dry_run:
                if i < 3:
                    print(f"  [DRY] cortex.bind: {payload['input_text'][:80]}...")
                    print(f"         feeling={payload['feeling']}, tags={payload['context_tags']}")
                    print(f"         vision features: {len(payload['vision'])}")
            elif postal:
                # Use route() directly — publish() has a None comparison bug
                postal.route("cortex.bind", payload)
            else:
                # No postal — accumulate for file output
                pass

            # Collect train text
            train_text = binding_to_train_text(binding)
            if train_text and len(train_text) > 10:
                train_texts.append({
                    "text": train_text,
                    "source": f"image_pipeline:{binding.get('source', 'unknown')}",
                    "weight": binding.get("persona_confidence", 0.5),
                })

            ingested_ids.add(image_id)
            stats["bound"] += 1
            stats["personas"][binding.get("persona", "unknown")] += 1
            stats["feelings"][payload["feeling"]] += 1

            # Throttle
            if not dry_run and postal and i % 10 == 0:
                time.sleep(delay)

            # Progress
            if (i + 1) % 500 == 0 or i == len(to_process) - 1:
                elapsed = time.time() - stats["start_time"]
                rate = stats["bound"] / max(0.1, elapsed)
                print(f"  {stats['bound']}/{len(to_process)} bound ({rate:.1f}/s)")
                # Save progress checkpoint
                save_progress(PROGRESS_FILE, ingested_ids, {
                    "bound": stats["bound"],
                    "trained": stats["trained"],
                })

        except Exception as e:
            stats["errors"] += 1
            if stats["errors"] <= 5:
                print(f"  ERROR binding {image_id}: {e}")

    # ── Phase 2: cortex.train_batch (text associations) ─────────────────
    print(f"\n=== Phase 2: cortex.train_batch ({len(train_texts)} texts) ===")

    for batch_start in range(0, len(train_texts), batch_size):
        batch = train_texts[batch_start:batch_start + batch_size]

        batch_payload = {
            "items": batch,
            "source": "image_pipeline",
            "source_fairy": "ImageIngestionPipeline",
            "trace_id": f"img_ingest_{int(time.time())}_{batch_start}",
        }

        if dry_run:
            print(f"  [DRY] cortex.train_batch: {len(batch)} items "
                  f"(batch {batch_start // batch_size + 1})")
            if batch:
                print(f"         sample: {batch[0]['text'][:80]}...")
        elif postal:
            postal.route("cortex.train_batch", batch_payload)
            stats["trained"] += len(batch)
            time.sleep(0.5)  # Give TARDIS time between batches
        else:
            stats["trained"] += len(batch)

        print(f"  Batch {batch_start // batch_size + 1}: "
              f"{len(batch)} items sent")

    # ── Summary ─────────────────────────────────────────────────────────
    elapsed = time.time() - stats["start_time"]
    stats["elapsed"] = elapsed

    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total bindings:  {stats['total']}")
    print(f"  Newly bound:     {stats['bound']}")
    print(f"  Text trained:    {stats['trained']}")
    print(f"  Skipped (done):  {stats['skipped']}")
    print(f"  Errors:          {stats['errors']}")
    print(f"  Elapsed:         {elapsed:.1f}s")
    print(f"\n  Personas: {dict(stats['personas'])}")
    print(f"  Feelings: {dict(stats['feelings'])}")

    # Final progress save
    save_progress(PROGRESS_FILE, ingested_ids, {
        "bound": stats["bound"],
        "trained": stats["trained"],
        "elapsed": round(elapsed, 1),
        "personas": dict(stats["personas"]),
        "feelings": dict(stats["feelings"]),
        "errors": stats["errors"],
        "completed_at": time.time(),
    })
    print(f"\n  Progress saved to {PROGRESS_FILE}")

    # If no postal, save payloads for later manual ingestion
    if not postal and not dry_run:
        fallback_file = BINDINGS_FILE.parent / "cortex_payloads.json"
        payloads = [binding_to_cortex_bind(b) for b in to_process]
        with open(fallback_file, "w", encoding="utf-8") as f:
            json.dump(payloads, f, indent=1)
        print(f"  No PostalHub — saved {len(payloads)} payloads to {fallback_file}")
        print(f"  Run again when the system is booted to ingest via postal.")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Ingest image bindings into Association Cortex")
    parser.add_argument("--dry-run", action="store_true", help="Validate without publishing")
    parser.add_argument("--batch-size", type=int, default=500, help="Train batch size (max 500)")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between bind batches (seconds)")
    parser.add_argument("--reset", action="store_true", help="Reset progress, re-ingest everything")
    parser.add_argument("--bindings", type=str, default=str(BINDINGS_FILE), help="Path to bindings.json")
    args = parser.parse_args()

    bindings_path = Path(args.bindings)
    if not bindings_path.exists():
        print(f"ERROR: {bindings_path} not found")
        print(f"Run the image_ingestion_pipeline.py first to generate bindings.")
        sys.exit(1)

    bindings = load_bindings(bindings_path)
    if not bindings:
        print("No bindings to ingest.")
        sys.exit(0)

    # Check manifest for pipeline completion
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            manifest = json.load(f)
        pipeline_stats = manifest.get("stats", {})
        print(f"Pipeline stats: {pipeline_stats.get('processed', '?')} processed, "
              f"{pipeline_stats.get('errors', '?')} errors")
    else:
        print("WARNING: No manifest.json found — pipeline may still be running")
        print(f"Current bindings: {len(bindings)} (may be incomplete)")

    # ── Persona Reclassification ──────────────────────────────────────
    # Fix quirkalina over-detection (10,605 → ~1,000 expected)
    print(f"\n=== Persona Reclassification ===")
    reclass_stats = reclassify_all(bindings)
    print(f"  Original:  {reclass_stats['original']}")
    print(f"  Corrected: {reclass_stats['corrected']}")
    print(f"  Changed:   {reclass_stats['changed']} bindings reclassified")
    print(f"  Kept quirkalina: {reclass_stats['kept_quirkalina']}")

    # Load progress for resume
    already_done = set() if args.reset else load_progress(PROGRESS_FILE)

    # Validate batch size
    batch_size = min(args.batch_size, 500)

    print(f"\nIngestion config:")
    print(f"  Bindings:    {len(bindings)}")
    print(f"  Already done: {len(already_done)}")
    print(f"  Batch size:  {batch_size}")
    print(f"  Delay:       {args.delay}s")
    print(f"  Dry run:     {args.dry_run}")
    print()

    stats = ingest_via_postal(
        bindings, already_done,
        batch_size=batch_size,
        delay=args.delay,
        dry_run=args.dry_run,
    )

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
