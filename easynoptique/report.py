"""Interface HTML autonome (style néo-brutaliste sombre) : vues, calques, export, détail des blocs, alertes."""
from __future__ import annotations

import json
from html import escape

from . import __version__
from .model import CATEGORIES, LINK_KINDS, Synoptic
from .render_drawio import render_drawio
from .render_svg import render_svg
from .scene import Scene

VIEW_NAMES = {"fonctionnel": "Fonctionnel", "complet": "Complet", "alimentation": "Alimentation", "bus": "Bus"}

# Petites icônes inline (pas de dépendance externe : le rapport marche hors ligne)
ICONS = {
    "logo": '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><rect x="2" y="2" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"/><rect x="9" y="9" width="6" height="6" fill="currentColor"/><path d="M5 6h3M16 6h3M5 18h3M16 18h3M8 6l1 4M16 6l-1 4M8 18l1-4M16 18l-1-4" stroke="currentColor" stroke-width="2"/></svg>',
    "eye": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>',
    "layers": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M12 3l10 5-10 5L2 8z M2 13l10 5 10-5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    "download": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M12 3v12M6 10l6 6 6-6M4 21h16" fill="none" stroke="currentColor" stroke-width="2.4"/></svg>',
    "info": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v6M12 7v1" stroke="currentColor" stroke-width="2.4"/></svg>',
    "warn": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M12 3l10 18H2z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 10v5M12 17v1" stroke="currentColor" stroke-width="2.4"/></svg>',
    "link": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M3 12h7M14 12h7M10 8v8M14 8v8" stroke="currentColor" stroke-width="2"/></svg>',
    "bus": '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M3 6h18M7 6v5M12 6v5M17 6v5" stroke="currentColor" stroke-width="2"/><rect x="4" y="11" width="6" height="7" fill="none" stroke="currentColor" stroke-width="2"/><rect x="14" y="11" width="6" height="7" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
}

CSS = """
:root{--bg:#121212;--surface:#1e1e1e;--text:#ffffff;--muted:#b3b3b3;--border:2px solid #ffffff;--shadow:4px 4px 0 #ffffff;
--accent:#1db954;--accent-hover:#1ed760;--danger:#ff5555;--font:"Space Mono",ui-monospace,"Cascadia Mono",Consolas,monospace}
*{box-sizing:border-box}
html,body{height:100%}
body{font-family:var(--font);background:var(--bg);color:var(--text);margin:0;display:flex;flex-direction:column;font-size:14px}
::-webkit-scrollbar{width:12px;height:12px}::-webkit-scrollbar-track{background:#111;border-left:2px solid #333}
::-webkit-scrollbar-thumb{background:#444;border:2px solid #111}::-webkit-scrollbar-thumb:hover{background:var(--accent)}
button{font-family:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

.top-bar{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding:14px max(20px,env(safe-area-inset-right));
padding-left:max(20px,env(safe-area-inset-left));background:var(--surface);border-bottom:var(--border)}
.logo-group{display:flex;align-items:center;gap:16px;min-width:0}
.logo{font-weight:700;font-size:1.15rem;letter-spacing:-1px;text-transform:uppercase;display:flex;align-items:center;gap:10px}
.logo svg{color:var(--accent)}
.project{font-weight:700;border-left:2px solid #fff;padding-left:16px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.project small{display:block;font-weight:400;color:var(--muted);font-size:.72rem}
.tag{font-size:.75rem;font-weight:700;border:1px solid #fff;padding:5px 10px;white-space:nowrap}

.main{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:20px;padding:20px max(20px,env(safe-area-inset-right)) 20px max(20px,env(safe-area-inset-left))}
.viewer{background:#222;border:var(--border);box-shadow:var(--shadow);display:flex;flex-direction:column;min-height:0;min-width:0}
.tabs{display:flex;border-bottom:var(--border);background:var(--surface);flex-wrap:wrap}
.tab{flex:1;min-width:110px;padding:12px 10px;background:transparent;color:var(--text);border:none;border-right:2px solid #fff;font-weight:700;
text-transform:uppercase;font-size:.8rem;cursor:pointer;transition:background .1s}
.tab:last-child{border-right:none}
.tab:hover{background:rgba(255,255,255,.08)}
.tab[aria-selected=true]{background:var(--accent);color:#000}
.zoom{display:flex;gap:8px;padding:8px 10px;border-bottom:2px solid #333;align-items:center;background:#1a1a1a}
.zoom span{font-size:.72rem;color:var(--muted);text-transform:uppercase;margin-right:auto}
.zoom button{width:34px;height:30px;border:1px solid #fff;background:transparent;color:#fff;font-weight:700;cursor:pointer}
.zoom button:hover{background:#fff;color:#000}
.zoom #fit{width:auto;padding:0 10px;font-size:.72rem;text-transform:uppercase}
.canvas{flex:1;overflow:auto;background:radial-gradient(circle at center,#2a2a2a 0%,#111 100%);padding:24px;min-height:320px}
.view[hidden]{display:none}
.paper{background:#fff;border:2px solid #000;box-shadow:6px 6px 0 #000;margin:0 auto;width:fit-content}
.paper svg{display:block;height:auto}

.controls{display:flex;flex-direction:column;gap:20px;overflow-y:auto;padding:0 8px 8px 0;min-height:0}
.panel{background:var(--surface);border:var(--border);padding:18px;box-shadow:var(--shadow)}
h3{margin:0 0 14px;font-size:.85rem;text-transform:uppercase;border-bottom:2px solid var(--text);padding-bottom:6px;display:flex;align-items:center;gap:8px}
h3 svg{color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stat{border:1px solid #fff;padding:10px;text-align:center}
.stat b{display:block;font-size:1.4rem;color:var(--accent);font-variant-numeric:tabular-nums}
.stat span{font-size:.65rem;text-transform:uppercase;color:var(--muted)}
.checkbox-wrapper{display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px;background:rgba(255,255,255,.05);padding:10px;border:1px solid #fff}
.checkbox-wrapper:last-child{margin-bottom:0}
.checkbox-wrapper input{cursor:pointer;accent-color:var(--accent);transform:scale(1.2)}
.checkbox-wrapper span{font-size:.78rem;font-weight:700;text-transform:uppercase}
.empty{font-size:.78rem;color:var(--muted);margin:0}
.btn-big{display:flex;align-items:center;justify-content:center;gap:10px;padding:15px;border:var(--border);background:var(--surface);color:var(--text);
font-weight:700;font-size:1rem;cursor:pointer;box-shadow:var(--shadow);transition:all .1s;text-transform:uppercase;width:100%}
.btn-big:hover{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #fff}
.btn-big:active{transform:translate(2px,2px);box-shadow:0 0 0 #fff}
.btn-accent{background:var(--accent);color:#000;border-color:#000;box-shadow:4px 4px 0 #000}
.btn-accent:hover{background:var(--accent-hover);box-shadow:6px 6px 0 #000}
.btn-group{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:14px}
.btn-small{padding:10px 6px;font-size:.78rem;border:1px solid #fff;background:transparent;color:#fff;cursor:pointer;font-weight:700;text-transform:uppercase;transition:.2s}
.btn-small:hover{background:#fff;color:#000}
.status{font-size:.75rem;margin-top:12px;min-height:16px;color:var(--accent);font-weight:700}
.detail-name{font-size:1.05rem;font-weight:700;margin:0 0 4px}
.detail-meta{font-size:.72rem;color:var(--muted);text-transform:uppercase;margin:0 0 10px}
.parts{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.parts li{border:1px solid #444;padding:6px 8px;font-size:.78rem;display:flex;gap:8px}
.parts li b{color:var(--accent);min-width:42px}
.rail{display:inline-block;background:#b85450;color:#fff;font-size:.68rem;font-weight:700;padding:1px 7px;margin:0 4px 10px 0}
.warn{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.warn li{border:1px solid var(--danger);color:#ffd2d2;padding:8px;font-size:.76rem;display:flex;gap:8px}
.warn li svg{color:var(--danger);flex:none;margin-top:2px}
.ok{color:var(--accent);font-weight:700;font-size:.8rem;margin:0}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.74rem;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px;border-bottom:1px solid #333;vertical-align:top}
th{font-size:.64rem;text-transform:uppercase;color:var(--muted)}
td b{color:var(--accent)}
.blk{cursor:pointer}.blk:hover rect{stroke:#1db954;stroke-width:3}
.blk.sel rect{stroke:#1db954;stroke-width:3.5}
@media (max-width:980px){body{height:auto}.main{grid-template-columns:1fr}.canvas{min-height:0;flex:none}.controls{overflow:visible;padding:0}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = r"""
const KINDS = __KINDS__;
const DATA = __DATA__;
const DRAWIO = __DRAWIO__;
const STEM = __STEM__;
const JSONDATA = __JSON__;
let current = document.querySelector('.view').dataset.view;
let zoom = 1;

function status(msg) { document.getElementById('status').textContent = msg; }
function save(name, blob) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  status('✓ ' + name);
}
function view() { return document.querySelector('.view[data-view="' + current + '"]'); }
function svg() { return view().querySelector('svg'); }

function applyZoom() {
  document.querySelectorAll('.view svg').forEach(s => { s.style.width = (s.viewBox.baseVal.width * zoom) + 'px'; });
  document.getElementById('zoomval').textContent = Math.round(zoom * 100) + ' %';
}
function fit() {
  const box = document.querySelector('.canvas'), w = svg().viewBox.baseVal.width;
  zoom = Math.max(0.3, Math.min(2, (box.clientWidth - 56) / w)); applyZoom();
}
document.getElementById('zin').onclick = () => { zoom = Math.min(3, zoom * 1.2); applyZoom(); };
document.getElementById('zout').onclick = () => { zoom = Math.max(0.3, zoom / 1.2); applyZoom(); };
document.getElementById('fit').onclick = fit;

function renderLayers() {
  const box = document.getElementById('layers'); box.innerHTML = '';
  const kinds = [...new Set([...svg().querySelectorAll('.edge')].map(e => e.dataset.kind).filter(k => k !== 'legend'))];
  if (!kinds.length) { box.innerHTML = '<p class="empty">Aucune liaison dans cette vue.</p>'; return; }
  kinds.sort((a, b) => Object.keys(KINDS).indexOf(a) - Object.keys(KINDS).indexOf(b));
  kinds.forEach(k => {
    const id = 'layer-' + current + '-' + k;
    const visible = !view().dataset['hide' + k];
    const label = document.createElement('label'); label.className = 'checkbox-wrapper';
    label.innerHTML = '<input type="checkbox" id="' + id + '"' + (visible ? ' checked' : '') + '><span></span>';
    label.querySelector('span').textContent = KINDS[k] || k;
    label.querySelector('input').addEventListener('change', e => {
      view().dataset['hide' + k] = e.target.checked ? '' : '1';
      svg().querySelectorAll('.edge.k-' + k).forEach(el => el.style.display = e.target.checked ? '' : 'none');
    });
    box.appendChild(label);
  });
}

function show(v) {
  current = v;
  document.querySelectorAll('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.view === v));
  document.querySelectorAll('.view').forEach(s => s.hidden = s.dataset.view !== v);
  renderLayers();
  try { localStorage.setItem('easynoptique-view', v); } catch (e) {}
}
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => show(t.dataset.view)));

function svgText(s) {
  const clone = s.cloneNode(true);
  clone.removeAttribute('style');
  clone.querySelectorAll('[style*="display: none"]').forEach(n => n.remove());
  clone.querySelectorAll('.sel').forEach(n => n.classList.remove('sel'));
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
}
document.querySelectorAll('[data-exp]').forEach(btn => btn.addEventListener('click', () => {
  const kind = btn.dataset.exp, name = STEM + '-' + current;
  if (kind === 'drawio') return save(STEM + '.drawio', new Blob([DRAWIO], {type: 'application/xml'}));
  if (kind === 'json') return save(STEM + '.json', new Blob([JSON.stringify(JSONDATA, null, 2)], {type: 'application/json'}));
  const s = svg(), text = svgText(s);
  if (kind === 'svg') return save(name + '.svg', new Blob([text], {type: 'image/svg+xml'}));
  status('Rendu PNG…');
  const img = new Image(), scale = 2;
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = s.viewBox.baseVal.width * scale; c.height = s.viewBox.baseVal.height * scale;
    const ctx = c.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(img, 0, 0, c.width, c.height);
    c.toBlob(b => save(name + '.png', b), 'image/png');
  };
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text);
}));

document.querySelectorAll('.blk').forEach(g => g.addEventListener('click', () => {
  const b = DATA[g.dataset.block]; if (!b) return;
  document.querySelectorAll('.blk.sel').forEach(n => n.classList.remove('sel'));
  document.querySelectorAll('.blk[data-block="' + g.dataset.block + '"]').forEach(n => n.classList.add('sel'));
  const el = document.getElementById('detail');
  el.innerHTML = '<p class="detail-name"></p><p class="detail-meta"></p><div class="rails"></div><ul class="parts"></ul>';
  el.querySelector('.detail-name').textContent = b.name;
  el.querySelector('.detail-meta').textContent = b.category + (b.sheet ? ' · ' + b.sheet : '');
  b.rails.forEach(r => { const s = document.createElement('span'); s.className = 'rail'; s.textContent = r; el.querySelector('.rails').appendChild(s); });
  const ul = el.querySelector('.parts');
  b.items.forEach(([ref, value]) => {
    const li = document.createElement('li'), r = document.createElement('b'), v = document.createElement('span');
    r.textContent = ref; v.textContent = value; li.append(r, v); ul.appendChild(li);
  });
}));

let start = current;
try { const s = localStorage.getItem('easynoptique-view'); if (s && document.querySelector('.view[data-view="' + s + '"]')) start = s; } catch (e) {}
show(start);
fit();
window.addEventListener('resize', () => { if (zoom <= 2) fit(); });
"""


def _js_value(v) -> str:
    return json.dumps(v, ensure_ascii=False).replace("</", "<\\/")


def render_report(syn: Synoptic, scenes: dict[str, Scene], stem: str = "synoptique") -> str:
    tabs, views = [], []
    for i, (key, sc) in enumerate(scenes.items()):
        tabs.append(f'<button class="tab" role="tab" aria-selected="{"true" if i == 0 else "false"}" data-view="{key}">'
                    f'{escape(VIEW_NAMES.get(key, key))}</button>')
        views.append(f'<section class="view" data-view="{key}"{"" if i == 0 else " hidden"}>'
                     f'<div class="paper">{render_svg(sc, "svg-" + key)}</div></section>')

    names_of = {b.id: b.name for b in syn.blocks}
    arrow = {"ab": "→", "ba": "←", "both": "↔", "none": "—"}
    link_rows = "".join(
        f"<tr><td>{escape(names_of.get(lk.a, lk.a))} {arrow.get(lk.direction, '')} {escape(names_of.get(lk.b, lk.b))}</td>"
        f"<td><b>{escape(lk.label)}</b></td><td>/{lk.width}</td></tr>"
        for lk in syn.links)
    bus_rows = "".join(
        f"<tr><td><b>{escape(b.label)}</b></td><td>"
        + "<br>".join(escape(f"{d.ref} {d.value}" + (f" @ {d.address}" if d.address else "")) for d in b.devices)
        + "</td></tr>" for b in syn.buses)
    if syn.warnings:
        warn = "<ul class='warn'>" + "".join(f"<li>{ICONS['warn']}<span>{escape(w)}</span></li>" for w in syn.warnings) + "</ul>"
    else:
        warn = "<p class='ok'>✓ AUCUNE ALERTE</p>"
    data = {b.id: {"name": b.name, "category": CATEGORIES.get(b.category, ("",))[0], "sheet": b.sheet,
                   "items": [[it.ref, it.value] for it in b.items], "rails": b.rails} for b in syn.blocks}

    js = (JS.replace("__KINDS__", _js_value(LINK_KINDS)).replace("__DATA__", _js_value(data))
          .replace("__DRAWIO__", _js_value(render_drawio(list(scenes.values()))))
          .replace("__STEM__", _js_value(stem)).replace("__JSON__", _js_value(syn.to_dict())))
    title = escape(syn.title or syn.project)
    sub = " · ".join(x for x in [f"Rév. {syn.rev}" if syn.rev else "", syn.date, syn.company] if x)

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title} · EasyNoptique</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>
<header class="top-bar">
  <div class="logo-group">
    <div class="logo">{ICONS['logo']} EASYNOPTIQUE</div>
    <div class="project">{title}<small>{escape(sub) or "Synoptique généré automatiquement"}</small></div>
  </div>
  <div class="tag">V{__version__}</div>
</header>
<main class="main">
  <div class="viewer">
    <div class="tabs" role="tablist" aria-label="Vues">{''.join(tabs)}</div>
    <div class="zoom"><span>Zoom <b id="zoomval">100 %</b></span>
      <button type="button" id="zout" aria-label="Dézoomer">−</button><button type="button" id="zin" aria-label="Zoomer">+</button>
      <button type="button" id="fit">Ajuster</button></div>
    <div class="canvas">{''.join(views)}</div>
  </div>
  <aside class="controls">
    <section class="panel"><h3>{ICONS['info']} Projet</h3>
      <div class="stats"><div class="stat"><b>{len(syn.blocks)}</b><span>Blocs</span></div>
      <div class="stat"><b>{len(syn.links)}</b><span>Liaisons</span></div>
      <div class="stat"><b>{len(syn.buses)}</b><span>Bus</span></div></div></section>
    <section class="panel"><h3>{ICONS['download']} Exporter</h3>
      <button type="button" class="btn-big btn-accent" data-exp="png">{ICONS['download']} PNG</button>
      <div class="btn-group"><button type="button" class="btn-small" data-exp="svg">SVG</button>
      <button type="button" class="btn-small" data-exp="drawio">draw.io</button>
      <button type="button" class="btn-small" data-exp="json">JSON</button></div>
      <div class="status" id="status" role="status">Prêt.</div></section>
    <section class="panel"><h3>{ICONS['layers']} Calques</h3><div id="layers"></div></section>
    <section class="panel"><h3>{ICONS['eye']} Bloc sélectionné</h3>
      <div id="detail"><p class="empty">Cliquez sur un bloc du synoptique.</p></div></section>
    <section class="panel"><h3>{ICONS['warn']} Alertes</h3>{warn}</section>
    <section class="panel"><h3>{ICONS['link']} Liaisons</h3><div class="scroll"><table>
      <thead><tr><th>Blocs</th><th>Liaison</th><th>Fils</th></tr></thead><tbody>{link_rows}</tbody></table></div></section>
    <section class="panel"><h3>{ICONS['bus']} Bus</h3><div class="scroll"><table>
      <thead><tr><th>Bus</th><th>Composants</th></tr></thead><tbody>{bus_rows}</tbody></table></div></section>
  </aside>
</main>
<script>{js}</script>
</body></html>
"""
