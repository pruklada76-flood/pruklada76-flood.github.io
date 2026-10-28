"""Copy the war-room artifact database (dumped with ArtifactData out_dir) into data/*.json.
Usage: python3 -I scripts/sync_from_db.py DUMP_DIR
DUMP_DIR holds war/state.json, war/params.json (optional), readings/*.json, forecasts/*.json.
Readings written by the GitHub job (src starting "gh:") are kept; everything else mirrors the war room."""
import sys, json, pathlib, time
dump = pathlib.Path(sys.argv[1]); data = pathlib.Path(__file__).resolve().parent.parent / "data"
KEEP_DAYS = 122

def load_dir(p):
    return [dict(json.loads(f.read_text(encoding="utf-8")), id=f.stem) for f in sorted(p.glob("*.json"))] if p.is_dir() else []

def write(name, obj):
    (data / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

cut = (time.time() - KEEP_DAYS * 86400) * 1000
old = json.loads((data / "readings.json").read_text(encoding="utf-8")) if (data / "readings.json").exists() else []
mine = [r for r in old if str(r.get("src", "")).startswith("gh:")]
war = [r for r in load_dir(dump / "readings") if isinstance(r.get("t"), (int, float))]
ids = {r["id"] for r in war}
bkk_day = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t / 1000 + 7 * 3600))
station_days = {bkk_day(r["t"]) for r in war if not r.get("est") and r.get("rain") is not None}
mine = [m for m in mine if bkk_day(m["t"]) not in station_days]  # real station data wins over model estimates
readings = sorted([r for r in war + [m for m in mine if m["id"] not in ids] if r["t"] >= cut], key=lambda r: r["t"])
write("readings.json", readings)
for name in ("state", "params"):
    f = dump / "war" / f"{name}.json"
    if f.exists(): write(f"{name}.json", json.loads(f.read_text(encoding="utf-8")))
fc = load_dir(dump / "forecasts")
if fc:  # keep whichever copy of each source is newer
    cur = {x["id"]: x for x in json.loads((data / "forecasts.json").read_text(encoding="utf-8"))} if (data / "forecasts.json").exists() else {}
    for x in fc:
        if x.get("issuedAt", 0) >= cur.get(x["id"], {}).get("issuedAt", 0): cur[x["id"]] = x
    write("forecasts.json", sorted(cur.values(), key=lambda x: x["id"]))
meta = json.loads((data / "meta.json").read_text(encoding="utf-8")) if (data / "meta.json").exists() else {}
meta.update(updatedAt=int(time.time() * 1000), warroomSyncAt=int(time.time() * 1000))
write("meta.json", meta)
print(f"readings {len(readings)}, forecasts {len(fc)}")
