"""Build the public read-only page (index.html) from the war-room artifact source.
Usage: python3 scripts/build_public.py path/to/warroom.html
The war-room page reads a Claude artifact database; this build swaps that for the JSON files in data/."""
import sys, re, pathlib
src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
out = pathlib.Path(__file__).resolve().parent.parent / "index.html"

def sub(old, new, count=1):
    global src
    if src.count(old) != count:
        sys.exit(f"pattern found {src.count(old)}x, expected {count}: {old[:60]}")
    src = src.replace(old, new)

sub("<title>ห้องสั่งการน้ำหมู่บ้าน</title>", "<title>สถานการณ์น้ำ พฤกษ์ลดา ประชาอุทิศ 76</title>")
sub("<h1>ห้องสั่งการน้ำหมู่บ้าน</h1>", "<h1>สถานการณ์น้ำ พฤกษ์ลดา ประชาอุทิศ 76</h1>")
src = re.sub(r'<div id="noDb" hidden.*?</div>\n?', "", src, count=1, flags=re.S)
# Hide the data-entry drawer: the public page is read-only.
sub('<details class="drawer">\n      <summary><span class="plus">+</span>บันทึกค่าใหม่</summary>',
    '<details class="drawer" hidden>\n      <summary><span class="plus">+</span>บันทึกค่าใหม่</summary>')
# Simulation mode: pumps and gate can be tapped, but only change this viewer's screen.
sub('${canWrite?"":"disabled"} aria-label="${esc(p.name)}', '${canWrite||SIM_OK?"":"disabled"} aria-label="${esc(p.name)}')
sub('b.disabled=!canWrite});', 'b.disabled=!(canWrite||SIM_OK)});')
sub('const b=e.target.closest("button[data-p]");if(!b||!canWrite)return;', 'const b=e.target.closest("button[data-p]");if(!b||!(canWrite||SIM_OK))return;')
sub('const b=e.target.closest("button[data-g]");if(!b||!canWrite)return;', 'const b=e.target.closest("button[data-g]");if(!b||!(canWrite||SIM_OK))return;')
sub('async function saveState(){', 'async function saveState(){if(mode==="public"){SIM=true;showSim();render();return}')
sub('<div class="acts" id="actions" aria-live="polite"></div>',
    '<div id="simBar" style="display:none;position:fixed;left:12px;right:12px;bottom:max(12px,env(safe-area-inset-bottom));z-index:60;max-width:760px;margin:0 auto;box-shadow:0 6px 24px rgba(0,0,0,.25);gap:10px;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:12px;background:var(--panel);color:var(--ink);border:2px dashed var(--fc4);font-size:15px"><span><b>โหมดจำลอง</b> · ตัวเลขบนจอนี้เปลี่ยนตามที่คุณกด ไม่ใช่สถานะจริงของปั๊มและประตูน้ำ</span><button type="button" id="simReset" style="flex:none;padding:8px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;cursor:pointer">กลับค่าจริง</button></div>\n  <div class="acts" id="actions" aria-live="polite"></div>')

# Replace the artifact-database connection with a loader for data/*.json.
start = src.index("async function connect(){")
end = src.index("/* ---------- events ---------- */")
src = src[:start] + r'''let pubFirst=true,SIM=false,REAL=null;const SIM_OK=true;
function showSim(){const b=$("simBar");if(b)b.style.display=SIM?"flex":"none"}
document.addEventListener("click",e=>{if(e.target&&e.target.id==="simReset"){SIM=false;if(REAL){S.pumps=Object.assign({},REAL.pumps);S.gate=REAL.gate}showSim();render()}});
async function connect(){
  mode="public";canWrite=false;lockForm();
  const g=async f=>{try{const r=await fetch("data/"+f+"?v="+Date.now(),{cache:"no-store"});return r.ok?await r.json():null}catch(e){return null}};
  const [rd,fc,st,pr,meta]=await Promise.all([g("readings.json"),g("forecasts.json"),g("state.json"),g("params.json"),g("meta.json")]);
  META=meta;if(pr)P=mergeParams(pr);
  if(st){const keep=pubFirst?null:S.scI,keepH=S.scH,simP=S.pumps,simG=S.gate;REAL=mergeState(st);S=mergeState(st);S.scI=keep;if(!pubFirst)S.scH=keepH;if(SIM){S.pumps=simP;S.gate=simG}}
  if(Array.isArray(rd))R=rd.filter(r=>r&&num(r.t)!=null).sort((a,b)=>b.t-a.t);
  if(Array.isArray(fc))FC=fc.map(cleanFC);
  if(pubFirst){$("scI").value="";pubFirst=false}
  const up=meta&&meta.updatedAt?" · อัปเดตล่าสุด "+dhm(meta.updatedAt):"";
  $("storeTxt").textContent=(rd||fc)?"หน้านี้ดูอย่างเดียว · ดึงข้อมูลใหม่อัตโนมัติ"+up:"โหลดข้อมูลไม่สำเร็จ ลองรีเฟรชหน้าอีกครั้ง";
  drawParams();render();
}
setInterval(()=>{if(!document.hidden)connect()},5*60*1000);

''' + src[end:]
head = ('<!doctype html><html lang="th"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>html,body{margin:0;padding:0}</style></head><body>\n')
out.write_text(head + src + "\n</body></html>\n", encoding="utf-8")
print("wrote", out)
