"""Rapport HTML autonome : les vues, les calques à cocher, la liste des liaisons et les alertes."""
from __future__ import annotations

import json
from html import escape

from .model import CATEGORIES, LINK_KINDS, Synoptic
from .render_drawio import render_drawio
from .render_svg import render_svg
from .scene import Scene

CSS = """
:root{--bg:#f4f6f5;--paper:#fff;--ink:#1c272b;--muted:#5a696d;--rule:#d5dddb;--accent:#1d67c9}
@media (prefers-color-scheme:dark){:root{--bg:#121819;--paper:#1a2325;--ink:#e2ebe9;--muted:#97a6a5;--rule:#2f3c3d;--accent:#5d9ff2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px max(16px,env(safe-area-inset-left))}
main{max-width:1200px;margin:0 auto;display:grid;gap:16px}
h1{font-size:26px;margin:0}h2{font-size:17px;margin:0 0 8px}.muted{color:var(--muted)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid var(--rule)}
.tab{font:600 14px system-ui;padding:8px 14px;border:1px solid transparent;border-bottom:none;border-radius:6px 6px 0 0;background:none;color:var(--muted);cursor:pointer;margin-bottom:-1px}
.tab[aria-selected=true]{background:var(--paper);color:var(--ink);border-color:var(--rule)}
.panel{background:var(--paper);border:1px solid var(--rule);border-top:none;border-radius:0 0 8px 8px}
.bar{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--rule);font-size:13px}
.bar label{display:inline-flex;gap:5px;align-items:center;cursor:pointer}
.canvas{overflow:auto;background:#fff;padding:8px}.canvas svg{display:block;max-width:100%;height:auto;margin:0 auto}
.view[hidden]{display:none}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:800px){.grid{grid-template-columns:1fr}}
.card{background:var(--paper);border:1px solid var(--rule);border-radius:8px;padding:14px;min-width:0;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}code{font-size:12px}
.warn li{margin:4px 0}.ok{color:#3f8a1f;font-weight:600}
.exp{margin-left:auto;display:inline-flex;gap:6px;align-items:center}
.exp button{font:600 12px system-ui;padding:4px 10px;border:1px solid var(--rule);border-radius:5px;background:var(--bg);color:var(--ink);cursor:pointer}
.exp button:hover{border-color:var(--accent)}
.blk{cursor:pointer}.blk:hover rect{stroke:#1d67c9;stroke-width:2.5}
#detail ul{margin:6px 0 0;padding-left:18px}
"""


def render_report(syn: Synoptic, scenes: dict[str, Scene], stem: str = "synoptique") -> str:
    names = {"fonctionnel": "Fonctionnelle", "complet": "Complète", "alimentation": "Alimentation", "bus": "Bus"}
    tabs, views = [], []
    for i, (key, sc) in enumerate(scenes.items()):
        tabs.append(f'<button class="tab" role="tab" aria-selected="{"true" if i == 0 else "false"}" data-view="{key}">'
                    f'{escape(names.get(key, key))}</button>')
        kinds = sorted({e.kind for e in sc.edges if e.kind != "legend"}, key=lambda k: list(LINK_KINDS).index(k) if k in LINK_KINDS else 99)
        boxes = "".join(f'<label><input type="checkbox" checked data-kind="{k}"> {escape(LINK_KINDS.get(k, k))}</label>' for k in kinds)
        views.append(f'<section class="view" data-view="{key}"{"" if i == 0 else " hidden"}><div class="bar"><b>Calques</b>{boxes}'
                     f'<span class="exp"><b>Exporter</b><button type="button" data-exp="svg">SVG</button>'
                     f'<button type="button" data-exp="png">PNG</button><button type="button" data-exp="drawio">draw.io</button>'
                     f'</span></div>'
                     f'<div class="canvas">{render_svg(sc, "svg-" + key)}</div></section>')

    names_of = {b.id: b.name for b in syn.blocks}
    dir_txt = {"ab": "→", "ba": "←", "both": "↔", "none": "—"}
    rows = "".join(
        f"<tr><td>{escape(names_of.get(lk.a, lk.a))} {dir_txt.get(lk.direction, '')} {escape(names_of.get(lk.b, lk.b))}</td>"
        f"<td><b>{escape(lk.label)}</b></td><td>{lk.width}</td><td><code>{escape(', '.join(lk.nets))}</code></td></tr>"
        for lk in syn.links)
    bus_rows = "".join(
        f"<tr><td><b>{escape(b.label)}</b></td><td>{escape(b.master)}</td><td>"
        + ", ".join(escape(f"{d.ref} {d.value}" + (f" @ {d.address}" if d.address else "")) for d in b.devices)
        + "</td></tr>" for b in syn.buses)
    warn = ("<ul class='warn'>" + "".join(f"<li>⚠ {escape(w)}</li>" for w in syn.warnings) + "</ul>") if syn.warnings \
        else "<p class='ok'>✓ Aucune alerte</p>"
    data = {b.id: {"name": b.name, "category": CATEGORIES.get(b.category, ("",))[0], "sheet": b.sheet,
                   "items": [f"{it.ref} — {it.value}" for it in b.items], "rails": b.rails} for b in syn.blocks}
    script = """
const DATA = %s;
const DRAWIO = %s;
const STEM = %s;
function save(name, blob) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
function svgText(svg) {  // exporte ce qui est affiché (calques masqués compris)
  const clone = svg.cloneNode(true);
  clone.querySelectorAll('[style*="display: none"]').forEach(n => n.remove());
  return '<?xml version="1.0" encoding="UTF-8"?>\\n' + new XMLSerializer().serializeToString(clone);
}
document.querySelectorAll('.view').forEach(v => v.querySelectorAll('[data-exp]').forEach(btn => btn.addEventListener('click', () => {
  const svg = v.querySelector('svg'), name = STEM + '-' + v.dataset.view, kind = btn.dataset.exp;
  if (kind === 'drawio') return save(STEM + '.drawio', new Blob([DRAWIO], {type: 'application/xml'}));
  const text = svgText(svg);
  if (kind === 'svg') return save(name + '.svg', new Blob([text], {type: 'image/svg+xml'}));
  const img = new Image(), scale = 2;
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = svg.viewBox.baseVal.width * scale; c.height = svg.viewBox.baseVal.height * scale;
    const ctx = c.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(img, 0, 0, c.width, c.height);
    c.toBlob(b => save(name + '.png', b), 'image/png');
  };
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text);
})));
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.setAttribute('aria-selected', x === t));
  document.querySelectorAll('.view').forEach(v => v.hidden = v.dataset.view !== t.dataset.view);
}));
document.querySelectorAll('.view').forEach(v => v.querySelectorAll('input[data-kind]').forEach(cb => cb.addEventListener('change', () => {
  v.querySelectorAll('.edge.k-' + cb.dataset.kind).forEach(e => e.style.display = cb.checked ? '' : 'none');
})));
document.querySelectorAll('.blk').forEach(g => g.addEventListener('click', () => {
  const b = DATA[g.dataset.block]; if (!b) return;
  const el = document.getElementById('detail');
  el.innerHTML = '<h2></h2><p class="muted"></p><ul></ul>';
  el.querySelector('h2').textContent = b.name;
  el.querySelector('p').textContent = b.category + (b.sheet ? ' · feuille ' + b.sheet : '') + (b.rails.length ? ' · alimenté par ' + b.rails.join(', ') : '');
  const ul = el.querySelector('ul'); b.items.forEach(i => { const li = document.createElement('li'); li.textContent = i; ul.appendChild(li); });
}));
""" % (json.dumps(data, ensure_ascii=False), json.dumps(render_drawio(list(scenes.values()))).replace("</", "<\\/"),
       json.dumps(stem))
    title = escape(syn.title or syn.project)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · EasyNoptique</title><style>{CSS}</style></head><body><main>
<header><div class="muted">EasyNoptique · synoptique généré automatiquement</div><h1>{title}</h1>
<div class="muted">Rév. {escape(syn.rev or '—')} · {escape(syn.date or '')} · {len(syn.blocks)} blocs · {len(syn.links)} liaisons</div></header>
<div><div class="tabs" role="tablist">{''.join(tabs)}</div><div class="panel">{''.join(views)}</div></div>
<div class="grid"><div class="card" id="detail"><h2>Détail d'un bloc</h2><p class="muted">Cliquez sur un bloc dans le synoptique.</p></div>
<div class="card"><h2>Alertes</h2>{warn}</div></div>
<div class="card"><h2>Liaisons détectées</h2><table><thead><tr><th>Blocs</th><th>Liaison</th><th>Fils</th><th>Nets</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="card"><h2>Bus</h2><table><thead><tr><th>Bus</th><th>Maître</th><th>Composants</th></tr></thead><tbody>{bus_rows}</tbody></table></div>
</main><script>{script}</script></body></html>
"""
