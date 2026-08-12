#!/usr/bin/env python3
"""
build-review-harness.py — emit a self-contained visual review harness for a
composed Configurable Design System mock.

usage: build-review-harness.py <mock.html> [--wireframe <path>] [--decisions <path>] [--out <path>]

The harness is one HTML file (no external requests; all CSS/JS inline) that
embeds the mock in an <iframe srcdoc> so it renders exactly as shipped, maps
the wireframe sidecar's Section blocks onto the mock's top-level structural
regions, and lets a reviewer pin numbered comments per region and copy out a
single natural-language change request for compose-page iteration.

Deterministic and idempotent: the same inputs always produce the same output
file, and nothing is written except the output file. Building Blocks
vocabulary: each labeled region is a Section; a dynamic Section received its
layout contract from a Shape at build time — the harness reads that identity
from the wireframe sidecar, it never re-derives it.

Exit status: 0 on success; non-zero with a message on stderr when an input
cannot be read or the output cannot be written.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path


def fail(message):
    print(f"build-review-harness: error: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path, label):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"cannot read {label} {path}: {exc}")


def parse_wireframe(text):
    """Parse the wireframe sidecar into Section identity entries, in order.

    The sidecar carries one block per Section: an identity line
    (`ID · section · shape · ground`) plus an ASCII arrangement sketch.
    Key-value lines (`id: hero-1`) are accepted too. Blocks that yield no
    identity (pure sketch fragments) are skipped; the harness falls back to
    Region 1..N labels whenever the block count does not match the mock.
    """
    entries = []
    key_re = re.compile(r"^\s*(id|section|shape|ground)\s*[:=]\s*(.+?)\s*$", re.IGNORECASE)
    for block in re.split(r"\n\s*\n", text.strip()):
        entry = {}
        for line in block.splitlines():
            match = key_re.match(line)
            if match:
                entry.setdefault(match.group(1).lower(), match.group(2).strip())
        if not entry:
            for line in block.splitlines():
                if "·" not in line:
                    continue
                parts = [p.strip() for p in line.split("·") if p.strip()]
                if len(parts) >= 2 and all(len(p) <= 80 for p in parts):
                    entry = dict(zip(("id", "section", "shape", "ground"), parts))
                    break
        if entry.get("id") or entry.get("section"):
            shape = entry.get("shape", "")
            if shape.lower() in {"-", "–", "—", "none", "n/a"}:
                shape = ""  # deterministic Section — no Shape was received
            entries.append({
                "id": entry.get("id") or entry.get("section", ""),
                "section": entry.get("section", ""),
                "shape": shape,
                "ground": entry.get("ground", ""),
            })
    return entries


def resolve_sidecar(explicit, default_path, label):
    """Explicit path must be readable; a default path is optional."""
    if explicit:
        return read_text(explicit, label)
    if default_path.is_file():
        return read_text(default_path, label)
    return None


def js_json(data):
    """JSON safe for embedding inside an inline <script> block."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")


def build_harness(mock_html, data):
    payload = {
        "mockPath": data["mock_path"],
        "wireframe": data["wireframe"],
        "decisions": data["decisions"],
    }
    return (
        HARNESS_TEMPLATE
        .replace("__TITLE__", html.escape(f"CDS review — {data['mock_name']}"))
        .replace("__MOCK_NAME__", html.escape(data["mock_name"]))
        .replace("__MOCK_SRCDOC__", html.escape(mock_html, quote=True))
        .replace("__RVW_DATA__", js_json(payload))
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="build-review-harness.py",
        description="Emit a self-contained visual review harness for a composed CDS mock.",
    )
    parser.add_argument("mock", help="path to the composed mock HTML file")
    parser.add_argument("--wireframe", help="wireframe sidecar (default: <basename>.wireframe.txt beside the mock)")
    parser.add_argument("--decisions", help="decisions sidecar (default: <basename>.decisions.md beside the mock)")
    parser.add_argument("--out", help="output path (default: <basename>.review.html beside the mock)")
    args = parser.parse_args(argv)

    mock_path = Path(args.mock).expanduser().resolve()
    if not mock_path.is_file():
        fail(f"mock not found: {mock_path}")
    mock_html = read_text(mock_path, "mock")
    if not mock_html.strip():
        fail(f"mock is empty: {mock_path}")

    base = mock_path.stem
    wf_text = resolve_sidecar(args.wireframe, mock_path.with_name(f"{base}.wireframe.txt"), "wireframe sidecar")
    dec_text = resolve_sidecar(args.decisions, mock_path.with_name(f"{base}.decisions.md"), "decisions sidecar")
    wireframe = parse_wireframe(wf_text) if wf_text else []

    out_path = Path(args.out).expanduser().resolve() if args.out else mock_path.with_name(f"{base}.review.html")
    harness = build_harness(mock_html, {
        "mock_path": str(mock_path),
        "mock_name": mock_path.name,
        "wireframe": wireframe,
        "decisions": dec_text,
    })
    try:
        out_path.write_text(harness, encoding="utf-8")
    except OSError as exc:
        fail(f"cannot write output {out_path}: {exc}")

    labels = (
        f"{len(wireframe)} wireframe Section block(s) parsed"
        if wireframe else "no wireframe sidecar — Region 1..N fallback labels"
    )
    print(f"review harness written: {out_path} ({labels})")
    return 0


HARNESS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --rvw-bg: #f2f4f7; --rvw-panel: #ffffff; --rvw-text: #1b2430; --rvw-muted: #5b6572;
  --rvw-line: #d8dde4; --rvw-accent: #3b7bd8; --rvw-marker: #d64545; --rvw-chip: #e8ecf2;
}
@media (prefers-color-scheme: dark) {
  :root {
    --rvw-bg: #14181d; --rvw-panel: #1c222a; --rvw-text: #e8ecf1; --rvw-muted: #98a3b0;
    --rvw-line: #313a45; --rvw-accent: #6ea8ff; --rvw-marker: #e2574c; --rvw-chip: #262e38;
  }
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0; background: var(--rvw-bg); color: var(--rvw-text);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
#rvw-app { display: flex; flex-direction: column; height: 100vh; }
#rvw-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 8px 14px; background: var(--rvw-panel); border-bottom: 1px solid var(--rvw-line);
}
#rvw-top .rvw-mock-name { color: var(--rvw-muted); margin-left: 8px; }
#rvw-top-right { display: flex; align-items: center; gap: 14px; color: var(--rvw-muted); }
.rvw-switch { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
#rvw-main { display: flex; flex: 1; min-height: 0; }
#rvw-stage { flex: 1; min-width: 0; background: var(--rvw-bg); }
#rvw-frame { display: block; width: 100%; height: 100%; border: 0; background: #ffffff; }
#rvw-side {
  width: 340px; flex: none; overflow-y: auto; padding: 12px;
  background: var(--rvw-panel); border-left: 1px solid var(--rvw-line);
}
#rvw-side h2 { margin: 0 0 8px; font-size: 14px; }
#rvw-empty { color: var(--rvw-muted); }
.rvw-card {
  border: 1px solid var(--rvw-line); border-radius: 8px; padding: 8px 10px; margin-bottom: 10px;
  background: var(--rvw-bg);
}
.rvw-card.rvw-active { border-color: var(--rvw-accent); }
.rvw-card-head { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.rvw-card-num {
  flex: none; width: 20px; height: 20px; border-radius: 50%; background: var(--rvw-marker);
  color: #fff; font-size: 11px; font-weight: 600; line-height: 20px; text-align: center;
}
.rvw-card-region { flex: 1; font-size: 12px; color: var(--rvw-muted); overflow-wrap: anywhere; }
.rvw-del {
  flex: none; border: 0; background: none; color: var(--rvw-muted); font-size: 16px;
  cursor: pointer; padding: 0 2px;
}
.rvw-del:hover { color: var(--rvw-marker); }
.rvw-card textarea {
  width: 100%; min-height: 56px; margin-top: 8px; resize: vertical;
  border: 1px solid var(--rvw-line); border-radius: 6px; padding: 6px 8px;
  background: var(--rvw-panel); color: var(--rvw-text); font: inherit;
}
.rvw-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.rvw-tag {
  border: 1px solid var(--rvw-line); border-radius: 999px; background: var(--rvw-chip);
  color: var(--rvw-muted); font-size: 11px; padding: 2px 9px; cursor: pointer; user-select: none;
}
.rvw-tag.rvw-on { background: var(--rvw-accent); border-color: var(--rvw-accent); color: #fff; }
.rvw-card.rvw-collapsed textarea, .rvw-card.rvw-collapsed .rvw-tags { display: none; }
#rvw-decisions { margin-top: 14px; font-size: 12px; }
#rvw-decisions summary { cursor: pointer; color: var(--rvw-muted); }
#rvw-decisions pre { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--rvw-muted); }
#rvw-prompt {
  flex: none; max-height: 30vh; display: flex; flex-direction: column;
  padding: 10px 14px; background: var(--rvw-panel); border-top: 1px solid var(--rvw-line);
}
.rvw-prompt-head { display: flex; align-items: center; justify-content: space-between; }
.rvw-prompt-head span { font-weight: 600; }
#rvw-copy {
  border: 1px solid var(--rvw-accent); border-radius: 6px; background: var(--rvw-accent);
  color: #fff; font: inherit; padding: 4px 14px; cursor: pointer;
}
#rvw-copy:disabled { opacity: 0.45; cursor: default; }
#rvw-prompt-text {
  margin: 8px 0 0; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit;
}
#rvw-prompt-text.rvw-placeholder { color: var(--rvw-muted); }
</style>
</head>
<body>
<div id="rvw-app">
  <header id="rvw-top">
    <div><strong>CDS review harness</strong><span class="rvw-mock-name">__MOCK_NAME__</span></div>
    <div id="rvw-top-right">
      <label class="rvw-switch"><input type="checkbox" id="rvw-mode" checked> Review mode</label>
      <span id="rvw-region-count"></span>
    </div>
  </header>
  <div id="rvw-main">
    <div id="rvw-stage">
      <iframe id="rvw-frame" title="Mock under review" srcdoc="__MOCK_SRCDOC__"></iframe>
    </div>
    <aside id="rvw-side">
      <h2>Comments</h2>
      <p id="rvw-empty">Hover a region to see its Section identity; click to pin a comment. Esc collapses the open card.</p>
      <div id="rvw-cards"></div>
      <details id="rvw-decisions" hidden><summary>Decision log</summary><pre id="rvw-decisions-text"></pre></details>
    </aside>
  </div>
  <footer id="rvw-prompt">
    <div class="rvw-prompt-head">
      <span>Change request</span>
      <button id="rvw-copy" type="button" disabled>Copy</button>
    </div>
    <pre id="rvw-prompt-text"></pre>
  </footer>
</div>
<script>
'use strict';
const RVW = __RVW_DATA__;
const TAGS = ['copy', 'layout', 'color', 'spacing', 'swap-shape', 'remove', 'add'];
const state = { comments: [], nextId: 1, activeId: null };
let regions = [];
let frameDoc = null;
let frameWin = null;
let badge = null;
let reviewMode = true;

const frame = document.getElementById('rvw-frame');
const cardsEl = document.getElementById('rvw-cards');
const emptyEl = document.getElementById('rvw-empty');
const promptEl = document.getElementById('rvw-prompt-text');
const copyBtn = document.getElementById('rvw-copy');
const modeBox = document.getElementById('rvw-mode');

frame.addEventListener('load', () => {
  frameDoc = frame.contentDocument;
  frameWin = frame.contentWindow;
  collectRegions();
  injectFrameStyle();
  wireFrameEvents();
  renderAll();
});

function collectRegions() {
  regions = [];
  const structural = new Set(['SECTION', 'HEADER', 'FOOTER', 'NAV']);
  const body = frameDoc.body;
  if (!body) return;
  for (const child of Array.from(body.children)) {
    if (structural.has(child.tagName)) regions.push({ el: child, tag: child.tagName.toLowerCase() });
    else if (child.tagName === 'MAIN') {
      for (const grand of Array.from(child.children)) {
        if (structural.has(grand.tagName)) regions.push({ el: grand, tag: grand.tagName.toLowerCase() });
      }
    }
  }
  const wf = RVW.wireframe || [];
  // A View's regions include the Shell's Sections (header, footer, nav), which a
  // Page's wireframe sidecar never describes. Map the sidecar onto the Page's
  // Sections and leave the Shell's regions generically labelled, so a View maps
  // as well as a bare Page HTML does. Requiring an exact match against every
  // structural region made a View fall back to Region 1..N in every case.
  const pageRegions = regions.filter(r => r.tag === 'section');
  const mapped = wf.length > 0 && wf.length === pageRegions.length;
  const wfFor = new Map();
  if (mapped) pageRegions.forEach((r, n) => wfFor.set(r, wf[n]));
  const tagTotals = {};
  regions.forEach(r => { tagTotals[r.tag] = (tagTotals[r.tag] || 0) + 1; });
  const tagSeen = {};
  regions.forEach((r, i) => {
    r.index = i;
    r.num = i + 1;
    r.wf = wfFor.get(r) || null;
    tagSeen[r.tag] = (tagSeen[r.tag] || 0) + 1;
    r.shellOrdinal = (!r.wf && r.tag !== 'section' && tagTotals[r.tag] > 1) ? tagSeen[r.tag] : 0;
    r.el.setAttribute('data-rvw-region', String(i));
  });
  document.getElementById('rvw-region-count').textContent =
    regions.length + ' region' + (regions.length === 1 ? '' : 's') +
    (mapped ? ' \\u00b7 wireframe mapped' : ' \\u00b7 fallback labels');
  const dec = document.getElementById('rvw-decisions');
  if (RVW.decisions) {
    dec.hidden = false;
    document.getElementById('rvw-decisions-text').textContent = RVW.decisions;
  }
}

function badgeLabel(r) {
  if (r.wf) return 'Section ' + r.wf.id + (r.wf.shape ? ' - Shape ' + r.wf.shape : '');
  if (r.tag !== 'section') return 'Shell ' + r.tag + (r.shellOrdinal ? ' ' + r.shellOrdinal : '');
  return 'Region ' + r.num;
}

function injectFrameStyle() {
  const style = frameDoc.createElement('style');
  style.textContent = [
    'html { position: relative !important; }',
    '.rvw-hover-outline { outline: 2px solid #4c8dff !important; outline-offset: -2px; }',
    '#rvw-badge { position: absolute; z-index: 2147483647; display: none; pointer-events: none;',
    '  background: #1c2733; color: #fff; padding: 3px 9px; border-radius: 4px;',
    '  font: 12px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }',
    '.rvw-marker { position: absolute; z-index: 2147483646; width: 22px; height: 22px;',
    '  margin: -11px 0 0 -11px; border-radius: 50%; background: #d64545; color: #fff;',
    '  font: 600 12px/22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
    '  text-align: center; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,0.4); }',
    '.rvw-marker.rvw-active { background: #3b7bd8; }',
  ].join('\\n');
  frameDoc.head.appendChild(style);
  badge = frameDoc.createElement('div');
  badge.id = 'rvw-badge';
  frameDoc.body.appendChild(badge);
}

function showHover(el) {
  const region = regions[Number(el.getAttribute('data-rvw-region'))];
  if (!region) return;
  el.classList.add('rvw-hover-outline');
  const rect = el.getBoundingClientRect();
  badge.textContent = badgeLabel(region);
  badge.style.left = (rect.left + frameWin.scrollX + 8) + 'px';
  badge.style.top = (rect.top + frameWin.scrollY + 8) + 'px';
  badge.style.display = 'block';
}

function hideHover() {
  if (!frameDoc) return;
  frameDoc.querySelectorAll('.rvw-hover-outline').forEach(el => el.classList.remove('rvw-hover-outline'));
  if (badge) badge.style.display = 'none';
}

function wireFrameEvents() {
  frameDoc.addEventListener('mouseover', e => {
    hideHover();
    if (!reviewMode || !e.target.closest) return;
    const el = e.target.closest('[data-rvw-region]');
    if (el) showHover(el);
  });
  frameDoc.addEventListener('mouseleave', hideHover);
  frameDoc.addEventListener('click', e => {
    if (!reviewMode || !e.target.closest) return;
    const marker = e.target.closest('.rvw-marker');
    if (marker) {
      e.preventDefault();
      e.stopPropagation();
      focusComment(Number(marker.getAttribute('data-rvw-id')));
      return;
    }
    const el = e.target.closest('[data-rvw-region]');
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();
    addComment(Number(el.getAttribute('data-rvw-region')), e.pageX, e.pageY, regionPercent(el, e.pageX, e.pageY));
  }, true);
  frameDoc.addEventListener('keydown', e => { if (e.key === 'Escape') dismissActive(); });
}

function sortedComments() {
  return state.comments.slice().sort((a, b) => a.regionIndex - b.regionIndex || a.id - b.id);
}

// Where the pin sits inside its own region, as whole percentages. Stored at pin
// time because the copied change request is read by an agent that cannot see the
// screen: when a Section holds several elements, the position is the only thing
// that resolves a deictic comment ("this is too far left") to one of them.
function regionPercent(el, pageX, pageY) {
  const rect = el.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const clamp = v => Math.min(100, Math.max(0, Math.round(v)));
  return {
    px: clamp(((pageX - (rect.left + frameWin.scrollX)) / rect.width) * 100),
    py: clamp(((pageY - (rect.top + frameWin.scrollY)) / rect.height) * 100),
  };
}

function addComment(regionIndex, x, y, pct) {
  const comment = {
    id: state.nextId++, regionIndex, x, y,
    px: pct ? pct.px : null, py: pct ? pct.py : null,
    text: '', tags: [],
  };
  state.comments.push(comment);
  state.activeId = comment.id;
  renderAll();
  focusCard(comment.id);
}

function deleteComment(id) {
  state.comments = state.comments.filter(c => c.id !== id);
  if (state.activeId === id) state.activeId = null;
  renderAll();
}

function focusComment(id) {
  state.activeId = id;
  renderAll();
  focusCard(id);
}

function focusCard(id) {
  const card = cardsEl.querySelector('.rvw-card[data-id="' + id + '"]');
  if (!card) return;
  card.scrollIntoView({ block: 'nearest' });
  const area = card.querySelector('textarea');
  if (area) area.focus();
}

function dismissActive() {
  if (state.activeId === null) return;
  state.activeId = null;
  renderAll();
}

function renderAll() {
  renderMarkers();
  renderCards();
  renderPrompt();
}

function renderMarkers() {
  if (!frameDoc || !frameDoc.body) return;
  frameDoc.querySelectorAll('.rvw-marker').forEach(el => el.remove());
  sortedComments().forEach((c, i) => {
    const marker = frameDoc.createElement('div');
    marker.className = 'rvw-marker' + (c.id === state.activeId ? ' rvw-active' : '');
    marker.setAttribute('data-rvw-id', String(c.id));
    marker.textContent = String(i + 1);
    marker.style.left = c.x + 'px';
    marker.style.top = c.y + 'px';
    frameDoc.body.appendChild(marker);
  });
}

function renderCards() {
  cardsEl.textContent = '';
  const ordered = sortedComments();
  emptyEl.hidden = ordered.length > 0;
  ordered.forEach((c, i) => {
    const region = regions[c.regionIndex];
    const card = document.createElement('div');
    card.className = 'rvw-card'
      + (c.id === state.activeId ? ' rvw-active' : '')
      + (c.id === state.activeId ? '' : ' rvw-collapsed');
    card.setAttribute('data-id', String(c.id));

    const head = document.createElement('div');
    head.className = 'rvw-card-head';
    const num = document.createElement('span');
    num.className = 'rvw-card-num';
    num.textContent = String(i + 1);
    const label = document.createElement('span');
    label.className = 'rvw-card-region';
    label.textContent = (region ? badgeLabel(region) : 'Region ?')
      + (c.text.trim() && c.id !== state.activeId ? ' \\u2014 ' + c.text.trim() : '');
    const del = document.createElement('button');
    del.className = 'rvw-del';
    del.type = 'button';
    del.title = 'Delete comment';
    del.textContent = '\\u00d7';
    del.addEventListener('click', e => { e.stopPropagation(); deleteComment(c.id); });
    head.append(num, label, del);
    head.addEventListener('click', () => {
      state.activeId = (state.activeId === c.id) ? null : c.id;
      renderAll();
      if (state.activeId === c.id) focusCard(c.id);
    });
    card.appendChild(head);

    const area = document.createElement('textarea');
    area.placeholder = 'Describe the change\\u2026';
    area.value = c.text;
    area.addEventListener('input', () => { c.text = area.value; renderPrompt(); });
    area.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); dismissActive(); } });
    card.appendChild(area);

    const tags = document.createElement('div');
    tags.className = 'rvw-tags';
    TAGS.forEach(tag => {
      const chip = document.createElement('span');
      chip.className = 'rvw-tag' + (c.tags.includes(tag) ? ' rvw-on' : '');
      chip.textContent = tag;
      chip.addEventListener('click', () => {
        c.tags = c.tags.includes(tag) ? c.tags.filter(t => t !== tag) : c.tags.concat(tag);
        renderAll();
      });
      tags.appendChild(chip);
    });
    card.appendChild(tags);
    cardsEl.appendChild(card);
  });
}

// The region heading carries the same Section identity the reviewer saw on hover,
// so a comment in the copied text and a pin on the screen name the same thing.
function promptHeading(index) {
  const region = regions[index];
  return region ? badgeLabel(region) : 'Region ' + (index + 1);
}

function pinLocator(c) {
  if (typeof c.px !== 'number' || typeof c.py !== 'number') return '';
  return ' at ' + c.px + '% across, ' + c.py + '% down';
}

function buildPrompt() {
  const byRegion = new Map();
  // Number every pin, empty ones included, so the numbers match the badges the
  // reviewer sees; only then drop the pins that carry no comment.
  sortedComments().forEach((c, i) => {
    if (!c.text.trim()) return;
    let item = '[' + (i + 1) + ']' + pinLocator(c) + ' \\u2014 '
      + c.text.trim().replace(/\\s+/g, ' ').replace(/[.;]+$/, '');
    if (c.tags.length) item += ' (' + c.tags.join(', ') + ')';
    if (!byRegion.has(c.regionIndex)) byRegion.set(c.regionIndex, []);
    byRegion.get(c.regionIndex).push(item);
  });
  if (byRegion.size === 0) return '';
  const lines = [
    'Iterate on ' + RVW.mockPath + '. Each [n] below is a numbered pin I placed on that '
    + 'artifact, grouped under the region it sits in; the percentages give the pin\\u2019s '
    + 'position within that region, so "this" in a comment means the element at that spot.',
  ];
  for (const [index, items] of Array.from(byRegion.entries()).sort((a, b) => a[0] - b[0])) {
    lines.push('', promptHeading(index) + ':');
    for (const item of items) lines.push('  ' + item);
  }
  return lines.join('\\n');
}

function renderPrompt() {
  const text = buildPrompt();
  copyBtn.disabled = !text;
  promptEl.classList.toggle('rvw-placeholder', !text);
  promptEl.textContent = text ||
    'No change request yet \\u2014 add a non-empty comment and the request builds here, grouped by region.';
}

copyBtn.addEventListener('click', () => {
  const text = buildPrompt();
  if (!text) return;
  const done = () => {
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
});

function fallbackCopy(text, done) {
  const area = document.createElement('textarea');
  area.value = text;
  document.body.appendChild(area);
  area.select();
  try { document.execCommand('copy'); } finally { area.remove(); }
  done();
}

modeBox.addEventListener('change', () => {
  reviewMode = modeBox.checked;
  hideHover();
});

document.addEventListener('keydown', e => { if (e.key === 'Escape') dismissActive(); });
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
