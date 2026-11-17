#!/usr/bin/env python3
"""Canal level WL.RJK.01 and rain RF.TKU.01 from the BMA drainage site, for the village server.

The BMA site blocks cloud machines, so this runs on the village's own Linux server (cron) and the
result is pushed to this repo as data/canal-rjk.json. Python 3.6+ standard library only.

  python3 bma_canal.py fetch [--kind canal|rain] [--url URL] [--html FILE] [--ca-file PEM]  > rows.json
  python3 bma_canal.py merge [--kind canal|rain] rows.json path/to/data/canal-rjk.json   (prints number of new rows)

--kind canal (default): StationDetail?id=103 -> data/canal-rjk.json, readings wl-YYYYMMDDHHMM {wlIn, wlOut}.
--kind rain: rain/StationDetail?id=42 (สนข.ทุ่งครุ) -> data/rain-tku.json, readings rf-YYYYMMDDHHMM
  {rain = mm since 00:00 Bangkok (sum of 5-min values, same meaning and ids as the war room's CSV import), rain5}.
  A day is used only from a row at 00:00-00:15 onward and stops at a gap over 30 min or an implausible value.

fetch: reads table id="example" (48 h at 5 min: Thai date-time in the Buddhist year, inner level,
outer level in m MSL, "-" = no reading). TLS certificates are always verified; if the server's
chain is incomplete, pass the missing intermediate with --ca-file instead of turning checks off.
merge: adds new rows by id ("wl-YYYYMMDDHHMM", Bangkok time, same ids as the war room's CSV import),
keeps the last KEEP_DAYS days, and leaves the file untouched when nothing is new."""
import sys, json, re, ssl, time, argparse, datetime as dt, urllib.request, http.cookiejar
from html.parser import HTMLParser

URL = "https://weather.bangkok.go.th/water/StationDetail?id=103"
STATION, NAME = "WL.RJK.01", "ปตร.คลองรางจาก-ประชาอุทิศ"
THRESH = {"warnIn": 0.55, "critIn": 0.60, "warnOut": 1.0, "critOut": 1.2}
SRC, KEEP_DAYS = "bma-server:WL.RJK.01", 7
RAIN_URL, RAIN_STATION, RAIN_NAME, RAIN_SRC = "https://weather.bangkok.go.th/rain/StationDetail?id=42", "RF.TKU.01", "สนข.ทุ่งครุ", "bma-server:rain"
BKK = dt.timezone(dt.timedelta(hours=7))
TH_MONTHS = {m: i + 1 for i, ms in enumerate([
    "ม.ค. มกราคม", "ก.พ. กุมภาพันธ์", "มี.ค. มีนาคม", "เม.ย. เมษายน", "พ.ค. พฤษภาคม", "มิ.ย. มิถุนายน",
    "ก.ค. กรกฎาคม", "ส.ค. สิงหาคม", "ก.ย. กันยายน", "ต.ค. ตุลาคม", "พ.ย. พฤศจิกายน", "ธ.ค. ธันวาคม"]) for m in ms.split()}


class TableRows(HTMLParser):
    """Collects the text of every <td>/<th> cell, row by row, inside <table id="example"> (table_id=None: any table)."""
    def __init__(self, table_id="example"):
        super().__init__(convert_charrefs=True)
        self.tid, self.depth, self.rows, self.row, self.cell = table_id, 0, [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.depth or self.tid is None or dict(attrs).get("id") == self.tid: self.depth += 1
        elif self.depth == 1 and tag == "tr": self.row = []
        elif self.depth == 1 and tag in ("td", "th") and self.row is not None: self.cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self.depth: self.depth -= 1
        elif self.depth == 1 and tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split())); self.cell = None
        elif self.depth == 1 and tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)


def parse_time(s):
    """'15/10/2569 00:20' or '15 ต.ค. 2569 00:20' (Bangkok time, Buddhist year) -> aware datetime."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\D+(\d{1,2})[:.](\d{2})", s)
    if m: d, mo, y, hh, mi = map(int, m.groups())
    else:
        m = re.search(r"(\d{1,2})\s*([ก-๙.]+)\s*(\d{4})\D+(\d{1,2})[:.](\d{2})", s)
        if not m or m[2] not in TH_MONTHS: return None
        d, mo, y, hh, mi = int(m[1]), TH_MONTHS[m[2]], int(m[3]), int(m[4]), int(m[5])
    if y > 2400: y -= 543
    try: return dt.datetime(y, mo, d, hh, mi, tzinfo=BKK)
    except ValueError: return None


def level(s):
    s = (s or "").strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s): return None   # "-" or blank = no reading
    v = float(s)
    return v if -2 <= v <= 4 else None


def rows_from_html(html):
    p = TableRows(); p.feed(html); out = {}
    for cells in p.rows:
        for i, c in enumerate(cells):
            t = parse_time(c)
            if t: break
        else: continue
        win, wout = (level(cells[i + 1]) if len(cells) > i + 1 else None), (level(cells[i + 2]) if len(cells) > i + 2 else None)
        if win is None and wout is None: continue
        rid = "wl-" + t.strftime("%Y%m%d%H%M")
        out[rid] = {"id": rid, "t": int(t.timestamp() * 1000), "wlIn": win, "wlOut": wout, "est": False, "src": SRC}
    return sorted(out.values(), key=lambda r: r["t"]), len(p.rows)


def rain_rows_from_html(html):
    """5-min rain rows -> cumulative mm since 00:00 for each Bangkok day that starts at 00:00-00:15."""
    p = TableRows(None); p.feed(html); five = {}   # any table: rows without a date or a 5-min number are skipped
    for cells in p.rows:
        for i, c in enumerate(cells):
            t = parse_time(c)
            if t: break
        else: continue
        v = (cells[i + 1] if len(cells) > i + 1 else "").strip()
        if re.fullmatch(r"\d+(\.\d+)?", v): five[t] = float(v)
    out, days = [], {}
    for t in sorted(five): days.setdefault(t.date(), []).append(t)
    for ts in days.values():
        if ts[0].hour or ts[0].minute > 15: continue          # partial day: running total would be wrong
        cum, prev = 0.0, None
        for t in ts:
            if (prev and t - prev > dt.timedelta(minutes=30)) or not 0 <= five[t] <= 50: break
            cum += five[t]; prev = t
            rid = "rf-" + t.strftime("%Y%m%d%H%M")
            out.append({"id": rid, "t": int(t.timestamp() * 1000), "rain": round(cum, 1), "rain5": five[t], "est": False, "src": RAIN_SRC})
    return sorted(out, key=lambda r: r["t"]), len(p.rows)


def fetch(url, ca_file=None):
    ctx = ssl.create_default_context()          # verifies certificates and host name
    if ca_file: ctx.load_verify_locations(ca_file)
    op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                     urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml", "Accept-Language": "th,en;q=0.8"})
    last = None
    for attempt in range(3):
        try:
            with op.open(req, timeout=40) as r:
                return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
        except Exception as e:
            last = e; time.sleep(5 * (attempt + 1))
    raise SystemExit(f"fetch failed: {last}")


def cmd_fetch(a):
    rain = a.kind == "rain"
    html = open(a.html, encoding="utf-8").read() if a.html else fetch(a.url or (RAIN_URL if rain else URL), a.ca_file)
    rows, n = (rain_rows_from_html if rain else rows_from_html)(html)
    if not rows:
        raise SystemExit(f"no readings found (table rows seen: {n}). The page layout may have changed or a bot check was shown.")
    if not a.html and time.time() * 1000 - rows[-1]["t"] > 6 * 3600 * 1000:
        print(f"warning: newest reading is old ({dt.datetime.fromtimestamp(rows[-1]['t'] / 1000, BKK):%d/%m %H:%M})", file=sys.stderr)
    json.dump(rows, sys.stdout, ensure_ascii=False); print()
    last = f"rain today {rows[-1]['rain']} mm" if rain else f"in {rows[-1]['wlIn']} out {rows[-1]['wlOut']}"
    print(f"{a.kind}: {len(rows)} readings, newest {dt.datetime.fromtimestamp(rows[-1]['t'] / 1000, BKK):%Y-%m-%d %H:%M} {last}", file=sys.stderr)


def cmd_merge(a):
    rows = json.load(open(a.rows, encoding="utf-8"))
    try: cur = json.load(open(a.target, encoding="utf-8"))
    except FileNotFoundError: cur = {}
    have = {r["id"]: r for r in cur.get("readings", [])}
    new = [r for r in rows if have.get(r["id"]) != r]
    if not new: print(0); return
    have.update({r["id"]: r for r in new})
    cut = (time.time() - KEEP_DAYS * 86400) * 1000
    head = ({"station": RAIN_STATION, "name": RAIN_NAME, "source": RAIN_URL} if a.kind == "rain"
            else dict({"station": STATION, "name": NAME, "source": URL}, **THRESH))
    out = {**head, "fetchedAt": int(time.time() * 1000),
           "readings": sorted((r for r in have.values() if r["t"] >= cut), key=lambda r: r["t"])}
    with open(a.target, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":")); f.write("\n")
    print(len(new))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd")   # no required=True: Python 3.6 (CentOS 7) lacks it
    f = sp.add_parser("fetch"); f.add_argument("--url"); f.add_argument("--html"); f.add_argument("--ca-file")
    m = sp.add_parser("merge"); m.add_argument("rows"); m.add_argument("target")
    for x in (f, m): x.add_argument("--kind", choices=("canal", "rain"), default="canal")
    a = ap.parse_args()
    if not a.cmd: ap.error("choose fetch or merge")
    cmd_fetch(a) if a.cmd == "fetch" else cmd_merge(a)
