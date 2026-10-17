"""Remove team notes before the war-room db goes to the public site (user's choice 2026-10-14: send without notes).
Usage: python3 -I strip_notes.py DUMP_DIR [SITE_DATA_DIR]
Drops the `note` field from DUMP_DIR/readings/*.json, and from SITE_DATA_DIR/readings.json if given."""
import sys, json, pathlib
dump = pathlib.Path(sys.argv[1])
n = 0
for f in (dump / "readings").glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.pop("note", None) is not None: n += 1
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
if len(sys.argv) > 2:
    p = pathlib.Path(sys.argv[2]) / "readings.json"
    if p.exists():
        rows = json.loads(p.read_text(encoding="utf-8"))
        for r in rows:
            if r.pop("note", None) is not None: n += 1
        p.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("notes removed:", n)
