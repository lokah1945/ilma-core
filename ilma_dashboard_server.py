#!/usr/bin/env python3
"""
ilma_dashboard_server.py — ILMA realtime self-awareness Web GUI (2026-06-22)
=============================================================================
A zero-dependency (stdlib only) web dashboard for the WHOLE ILMA system: concept,
pipeline, capabilities + runtime status, SOT stats, and a searchable inventory of
every module / script / skill with descriptions and LIVE/ORPHAN wiring badges.

Data source: ilma_system_map.build() (regenerated on /api/refresh; cached otherwise).
This is the visible form of ILMA's system self-awareness.

Run:   python3 ilma_dashboard_server.py [--port 8765] [--host 0.0.0.0]
Open:  http://<host>:8765/
API:   /api/map  (cached JSON)   /api/refresh (regenerate + return)   /healthz
"""
from __future__ import annotations
import json, sys, argparse, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path("/root/.hermes/profiles/ilma")
MAP_JSON = ROOT / "data" / "ilma_system_map.json"
sys.path.insert(0, str(ROOT))

_lock = threading.Lock()


def get_map(refresh=False):
    if refresh or not MAP_JSON.exists():
        with _lock:
            try:
                import ilma_system_map
                return ilma_system_map.build()
            except Exception as e:
                return {"error": f"map build failed: {e}", "generated_at": ""}
    try:
        return json.loads(MAP_JSON.read_text())
    except Exception as e:
        return {"error": str(e)}


HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>ILMA System Map</title><style>
:root{--bg:#0b0f17;--panel:#131a26;--panel2:#1a2433;--ink:#e6edf3;--mut:#8aa0b8;--ac:#4ea1ff;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--line:#26324a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
header{padding:14px 20px;background:linear-gradient(90deg,#0b0f17,#13233f);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
h1{margin:0;font-size:18px;letter-spacing:.5px}h1 b{color:var(--ac)}.sub{color:var(--mut);font-size:12px;margin-top:3px}
.bar{display:flex;gap:8px;flex-wrap:wrap;padding:10px 20px;border-bottom:1px solid var(--line);background:var(--panel)}
.tab{padding:6px 12px;border:1px solid var(--line);border-radius:6px;cursor:pointer;color:var(--mut);user-select:none}
.tab.on{background:var(--ac);color:#04121f;border-color:var(--ac);font-weight:700}
.btn{padding:6px 12px;border:1px solid var(--ac);border-radius:6px;color:var(--ac);background:transparent;cursor:pointer;margin-left:auto}
main{padding:18px 20px;max-width:1280px;margin:0 auto}.view{display:none}.view.on{display:block}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi{font-size:30px;font-weight:800;color:var(--ac)}.kpi.s{font-size:20px}.lbl{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.6px}
.row{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px dashed var(--line)}
.pill{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;font-weight:700}
.live{background:#10331c;color:var(--ok)}.orph{background:#3a1d1d;color:var(--bad)}.free{background:#10331c;color:var(--ok)}
.v{color:var(--ok)}.w{color:var(--warn)}.b{color:var(--bad)}
table{width:100%;border-collapse:collapse;margin-top:8px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-size:11px;text-transform:uppercase;position:sticky;top:0;background:var(--panel2)}
td.doc{color:var(--mut);font-size:12px}input{width:100%;padding:9px 12px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;color:var(--ink);margin-bottom:10px}
.step{background:var(--panel2);border-left:3px solid var(--ac);padding:10px 12px;border-radius:0 8px 8px 0;margin-bottom:8px}
.step b{color:var(--ac)}.muted{color:var(--mut)}code{color:#9ecbff}.sc{max-height:60vh;overflow:auto;border:1px solid var(--line);border-radius:8px}
</style></head><body>
<header><h1><b>ILMA</b> System Map · self-awareness console</h1><div class=sub id=sub>loading…</div></header>
<div class=bar>
 <div class=tab data-v=ov>Overview</div><div class=tab data-v=cap>Capabilities</div>
 <div class=tab data-v=pipe>Pipeline</div><div class=tab data-v=sot>SOT</div>
 <div class=tab data-v=files>Files &amp; Wiring</div><div class=tab data-v=skills>Skills</div>
 <button class=btn id=refresh>↻ Refresh live</button>
</div>
<main>
 <div class=view id=ov></div><div class=view id=cap></div><div class=view id=pipe></div>
 <div class=view id=sot></div><div class=view id=files></div><div class=view id=skills></div>
</main>
<script>
let M=null;
const $=s=>document.querySelector(s), E=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e};
function statusClass(s){s=(s||'').toUpperCase();return s.includes('VERIFIED')?'v':s.includes('BLOCK')||s.includes('PENDING')?'w':s.includes('FACADE')?'b':'muted'}
async function load(refresh){
  $('#sub').textContent='fetching…';
  if(window.__PRELOAD__ && !refresh){M=window.__PRELOAD__;}
  else{try{M=await (await fetch(refresh?'/api/refresh':'/api/map')).json();}catch(e){if(window.__PRELOAD__){M=window.__PRELOAD__;}else{$('#sub').textContent='offline (no data)';return;}}}
  if(M.error){$('#sub').textContent='ERROR: '+M.error;return}
  const c=M.counts||{}, rt=M.runtime||{}, gw=(rt.gateway||{});
  $('#sub').innerHTML=`generated ${(''+M.generated_at).replace('T',' ').slice(0,19)} · gateway <span class=${gw.state=='running'?'v':'b'}>${gw.state}</span> · autonomy ${rt.autonomy_paused?'<span class=w>paused</span>':'<span class=v>live</span>'}`;
  renderOV();renderCAP();renderPIPE();renderSOT();renderFILES();renderSKILLS();
}
function renderOV(){
  const c=M.counts||{},s=M.sot||{},rt=M.runtime||{},gw=rt.gateway||{};
  const k=(n,l,cls)=>`<div class=card><div class="kpi ${cls||''}">${n}</div><div class=lbl>${l}</div></div>`;
  let h=`<div class=card><div class=lbl>Concept</div><p>${M.concept||''}</p></div>`;
  h+='<div class=grid style=margin:12px-0>'+
     k(c.modules_total,'modules')+k('<span class=v>'+c.live+'</span>','live (static-reach)')+
     k('<span class=b>'+c.orphan+'</span>','orphan candidates')+k(c.skills,'skills')+
     k(s.models_active||'–','active models')+k('<span class=v>'+(s.models_free||'–')+'</span>','free models')+
     k(s.providers||'–','providers')+'</div>';
  h+='<div class=grid>';
  h+=`<div class=card><div class=lbl>Gateway</div><div class="kpi s ${gw.state=='running'?'v':'b'}">${gw.state}</div>`+
     Object.entries(gw.platforms||{}).map(([p,st])=>`<div class=row><span>${p}</span><span class=${st=='connected'?'v':'b'}>${st}</span></div>`).join('')+'</div>';
  h+=`<div class=card><div class=lbl>Daemons / units</div>`+(rt.units||[]).map(u=>`<div class=row><span class=muted>${u}</span></div>`).join('')+'</div>';
  $('#ov').innerHTML=h;
}
function renderCAP(){
  const re=((M.sot||{}).capability_registry||{}).runtime_executors||{};
  const eh=(M.sot||{}).endpoint_histogram||{};
  let h='<div class=card><div class=lbl>Capability runtime executors (free-only)</div><table><tr><th>capability</th><th>status</th></tr>';
  for(const[k,v]of Object.entries(re))h+=`<tr><td>${k}</td><td class=${statusClass(v)}>${v}</td></tr>`;
  h+='</table></div><div class=card style=margin-top:12px><div class=lbl>SOT endpoint coverage (active / free)</div><table><tr><th>endpoint_type</th><th>models</th><th>free</th></tr>';
  for(const[k,v]of Object.entries(eh))h+=`<tr><td>${k}</td><td>${v.n}</td><td class=v>${v.free}</td></tr>`;
  $('#cap').innerHTML=h+'</table></div>';
}
function renderPIPE(){
  $('#pipe').innerHTML='<div class=card><div class=lbl>Realized runtime pipeline (entry → output)</div>'+
   (M.pipeline||[]).map((p,i)=>`<div class=step><b>${i+1}. ${p.stage}</b><br><span class=muted>${p.what}</span></div>`).join('')+'</div>';
}
function renderSOT(){
  const s=M.sot||{};let h='<div class=grid>'+
   `<div class=card><div class=kpi>${s.models_total||'–'}</div><div class=lbl>models total</div></div>`+
   `<div class=card><div class="kpi v">${s.models_free||'–'}</div><div class=lbl>free (is_free_final)</div></div>`+
   `<div class=card><div class=kpi s>${(s.fields||[]).length}</div><div class=lbl>fields/doc (deduped)</div></div></div>`;
  h+=`<div class=card style=margin-top:12px><div class=lbl>models fields (${(s.fields||[]).length})</div><div>`+
   (s.fields||[]).map(f=>`<span class=pill style=background:var(--panel2);margin:2px>${f}</span>`).join('')+'</div></div>';
  $('#sot').innerHTML=h;
}
function fileRows(filter){
  const f=M.files||{},live=new Set(M.live||[]);
  return Object.values(f).filter(m=>!filter||((m.rel+' '+m.doc+' '+(m.classes||[]).join(' ')).toLowerCase().includes(filter)))
   .sort((a,b)=>a.rel.localeCompare(b.rel))
   .map(m=>`<tr><td><span class="pill ${live.has(m.rel)?'live':'orph'}">${live.has(m.rel)?'LIVE':'orphan'}</span></td>
     <td>${m.rel}</td><td class=doc>${m.doc||'<span class=muted>—</span>'}</td>
     <td class=doc>${(m.classes||[]).slice(0,4).join(', ')}</td></tr>`).join('');
}
function renderFILES(){
  $('#files').innerHTML='<input id=q placeholder="search modules/scripts by name, purpose, class…">'+
   '<div class=muted style=margin-bottom:8px>LIVE = reachable from an entrypoint or referenced in config/cron/sh. orphan = static-unreachable (candidate for merge/delete; verify before removing).</div>'+
   '<div class=sc><table id=ft><tr><th>wiring</th><th>path</th><th>purpose</th><th>classes</th></tr>'+fileRows('')+'</table></div>';
  $('#q').oninput=e=>{$('#ft').innerHTML='<tr><th>wiring</th><th>path</th><th>purpose</th><th>classes</th></tr>'+fileRows(e.target.value.toLowerCase())};
}
function renderSKILLS(){
  const sk=M.skills||[];
  $('#skills').innerHTML=`<div class=muted style=margin-bottom:8px>${sk.length} skills</div><div class=sc><table><tr><th>skill</th><th>description</th><th>triggers</th></tr>`+
   sk.sort((a,b)=>a.name.localeCompare(b.name)).map(s=>`<tr><td>${s.name}</td><td class=doc>${s.description||'—'}</td><td class=doc>${(s.triggers||[]).slice(0,4).join(', ')}</td></tr>`).join('')+'</table></div>';
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));$('#'+t.dataset.v).classList.add('on');
});
document.querySelector('.tab').click();
$('#refresh').onclick=()=>load(true);
load(false);setInterval(()=>load(false),15000);
</script></body></html>"""


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True  # avoid "Address already in use" on quick restarts


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, HTML, "text/html; charset=utf-8")
        elif self.path == "/api/map":
            self._send(200, json.dumps(get_map(False), default=str))
        elif self.path == "/api/refresh":
            self._send(200, json.dumps(get_map(True), default=str))
        elif self.path == "/healthz":
            self._send(200, json.dumps({"ok": True, "ts": time.time()}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    # Serve immediately from the cached map (data/ilma_system_map.json). The
    # initial fresh build runs in the background so a slow Mongo connect can't
    # delay the bind. Refreshes every 10 min thereafter.
    if not MAP_JSON.exists():
        try:
            get_map(True)
        except Exception:
            pass

    def _refresher():
        try:
            get_map(True)   # first fresh build (async, non-blocking to bind)
        except Exception:
            pass
        while True:
            time.sleep(600)
            try:
                get_map(True)
            except Exception:
                pass
    threading.Thread(target=_refresher, daemon=True).start()

    srv = _Server((a.host, a.port), H)
    print(f"ILMA dashboard → http://{a.host}:{a.port}/  (map: {MAP_JSON})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
