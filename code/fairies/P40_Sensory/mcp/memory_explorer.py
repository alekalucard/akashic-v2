import os, json, glob, argparse, time
from pathlib import Path

def list_records(root, kinds=None, limit=50):
    root = Path(root)
    day_dirs = sorted((root / "SRM_Intake").glob("*/"))
    if not day_dirs:
        print("No SRM_Intake found under", root)
        return []
    latest = day_dirs[-1]
    files = sorted(latest.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    recs = []
    for f in files:
        if len(recs) >= limit:
            break
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            kind = data.get("kind") or (data.get("data") or {}).get("kind")
            if kinds and kind not in kinds:
                continue
            recs.append({"path": str(f), "kind": kind, "meta": data.get("meta"), "data": data.get("data")})
        except Exception:
            continue
    return recs

def summarize(rec):
    kind = rec.get("kind")
    data = rec.get("data") or {}
    if kind in ("ebook.scan.index", "ebook.process.summary"):
        title = data.get("title") or data.get("meta", {}).get("title") or data.get("source_path")
        return f"{kind}: {title} -> {data.get('output_dir')}"
    if kind in ("ebook.scan.asset", "ebook.process.asset"):
        return f"{kind}: {data.get('image_path')} page={data.get('page')} hash={data.get('hash')}"
    if kind == "coordinate.card":
        helix = data.get("helix", {})
        return f"coordinate.card: {helix.get('echo_left')} | {helix.get('echo_right')}"
    return f"{kind}: {str(data)[:120]}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.getenv("AKASHIC_ROOT") or str(Path(__file__).resolve().parents[1]), help="Project root where SRM_Intake lives")
    ap.add_argument("--limit", type=int, default=50, help="Max records to show")
    ap.add_argument("--kinds", nargs="*", help="Kinds to filter (e.g., ebook.scan.index coordinate.card)")
    args = ap.parse_args()

    kinds = args.kinds or [
        "ebook.scan.index",
        "ebook.scan.asset",
        "ebook.process.summary",
        "ebook.process.asset",
        "coordinate.card",
    ]

    recs = list_records(args.root, kinds=kinds, limit=args.limit)
    if not recs:
        print("No records found for kinds", kinds)
        return
    for rec in recs:
        print(summarize(rec))
        print("  path:", rec.get("path"))

if __name__ == "__main__":
    main()
