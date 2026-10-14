"""Run by .github/workflows/fetch.yml every 15 minutes. Standard library only.
Updates data/forecasts.json (Open-Meteo models), adds yesterday's model rain total to
data/readings.json, and saves the canal gauge (thaiwater) to data/canal.json when available.
Each source fails on its own; failures are listed in data/meta.json."""
import json, math, pathlib, time, urllib.request, datetime as dt
LAT, LON = 13.6185, 100.4806
CANAL = ("RMN.01", "รางแม่น้ำ")          # BMA WL.RMN.01 คลองรางแม่น้ำ ช่วงซอยประชาอุทิศ 76 (confirmed by the village)
H = 3600_000; BKK = dt.timezone(dt.timedelta(hours=7))
data = pathlib.Path(__file__).resolve().parent.parent / "data"
now = int(time.time() * 1000); fails = []

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "village-flood-dashboard (github.com/wwwiiiwww-collab/village-flood)"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
def load(name, default):
    p = data / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
def save(name, obj):
    (data / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

# 1) Forecasts: one line per model. Open-Meteo's value at hour T is rain during the hour before T.
BASE = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=precipitation&forecast_days=2&past_days=1&timezone=GMT&models="
fc = {x["id"]: x for x in load("forecasts.json", [])}
for doc, label, model in [("openmeteo-best", "Open-Meteo (best match)", "best_match"),
                          ("openmeteo-ecmwf", "ECMWF IFS 0.25° (ยุโรป) ผ่าน Open-Meteo", "ecmwf_ifs025"),
                          ("openmeteo-gfs", "GFS (NOAA สหรัฐฯ) ผ่าน Open-Meteo", "gfs_seamless")]:
    try:
        d = get(BASE + model); hr = []
        for t, v in zip(d["hourly"]["time"], d["hourly"]["precipitation"]):
            ts = int(dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc).timestamp() * 1000) - H
            if v is not None and ts >= now - 2 * H: hr.append({"t": ts, "mm": round(v, 2)})
        fc[doc] = {"id": doc, "label": label, "source": "https://open-meteo.com/en/docs", "issuedAt": now, "lat": LAT, "lon": LON, "hourly": hr}
        if doc == "openmeteo-best":  # yesterday's (Bangkok) model total, as an estimated daily reading
            y = (dt.datetime.now(BKK) - dt.timedelta(days=1)).date(); tot = 0.0
            for t, v in zip(d["hourly"]["time"], d["hourly"]["precipitation"]):
                loc = (dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc) - dt.timedelta(hours=1)).astimezone(BKK)
                if loc.date() == y and v is not None: tot += v
            rid = "om" + y.strftime("%Y%m%d")  # same id the war-room feed uses, so the two never double up
            rd = [r for r in load("readings.json", []) if r.get("id") != rid]
            t_end = int(dt.datetime.combine(y, dt.time(23, 59), BKK).timestamp() * 1000)
            rd.append({"id": rid, "t": t_end, "rain": round(tot, 1), "est": True, "src": "gh:openmeteo",
                       "note": "ฝนรวมทั้งวันจากแบบจำลอง Open-Meteo ไม่ใช่ค่าสถานีวัด"})
            save("readings.json", sorted(rd, key=lambda r: r["t"]))
    except Exception as e: fails.append(f"forecast {doc}: {e}")
save("forecasts.json", sorted(fc.values(), key=lambda x: x["id"]))

# 2) Canal level from thaiwater (HII). Field names vary, so keep the matching station record as-is.
def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)
try:
    d = get("https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load")
    hits = [o for o in walk(d) if isinstance(o.get("station"), dict)
            and any(k in json.dumps(o["station"], ensure_ascii=False) for k in CANAL)]
    if hits:
        canal = load("canal.json", {"station": "WL.RMN.01", "series": []})
        canal["latest"] = hits[0]; canal["fetchedAt"] = now
        save("canal.json", canal)
    else: fails.append("canal: station not in thaiwater waterlevel_load")
except Exception as e: fails.append(f"canal thaiwater: {e}")

# 3) Fallback for the canal: the BMA drainage site's water-level table (may be behind a bot check).
try:
    import re, html as H_
    req = urllib.request.Request("https://weather.bangkok.go.th/water", headers={"User-Agent": "Mozilla/5.0 (village-flood dashboard)"})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    row = next((r for r in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S) if "WL.RMN.01" in r), None)
    if row:
        cells = [H_.unescape(re.sub(r"<[^>]+>", " ", c)).split() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        canal = load("canal.json", {"station": "WL.RMN.01", "series": []})
        canal.update(bma=[" ".join(c) for c in cells], bmaFetchedAt=now, source="https://weather.bangkok.go.th/water")
        save("canal.json", canal)
    else: fails.append("canal BMA: WL.RMN.01 row not found (bot check?)")
except Exception as e: fails.append(f"canal BMA: {e}")

meta = load("meta.json", {}); meta.update(updatedAt=now, fetchFails=fails); save("meta.json", meta)
print(json.dumps({"fails": fails}, ensure_ascii=False))
