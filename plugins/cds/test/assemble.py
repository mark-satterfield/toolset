#!/usr/bin/env python3
"""
CDS render-proof gallery assembler.

NOT a generator of CSS or markup. It only *views* the real pregenerated
artifacts that the cds-render-proof workflow wrote into the gitignored
``visual-proof-out/`` directory beside this script. It inlines the live
generated stylesheet set and wraps the component fragments
(``visual-proof-out/components/*.html``) and shape fragments
(``visual-proof-out/shapes/*.html``) into two browsable gallery pages with a
theme/mode switch bar driven by the real ``switcher.js``. The sample landing
page (``visual-proof-out/landing.html``) is already a full standalone document
and is linked as-is.

Everything this script presents is DISCOVERED, never hardcoded:
  * the theme list comes from the bare class selectors in ``themes.css``
  * the mode list comes from the ``[data-mode="..."]`` selectors in ``themes.css``
  * the shape order + names come from ``reference/shapes.md`` Part A
So the galleries stay correct for ANY elements YAML — no frozen snapshot.

Edit an artifact, re-run this, re-screenshot — that is the iteration loop.

Usage: python3 assemble.py
Reads + writes inside ``visual-proof-out/`` (index.html, components.html,
shapes.html). Exits non-zero if the artifacts are not present.
"""
import os
import sys
import glob
import html
import re

HERE = os.path.dirname(os.path.abspath(__file__))
# All generated output lives in the gitignored visual-proof-out/ (never the
# committed tree). This script is committed tooling; its output is not.
OUT = os.path.join(HERE, "visual-proof-out")
STYLES = os.path.join(OUT, "styles")
COMPONENTS = os.path.join(OUT, "components")
SHAPES = os.path.join(OUT, "shapes")
# The shape catalog's single source of truth: <plugin>/reference/shapes.md.
REFERENCE = os.path.abspath(os.path.join(HERE, "..", "reference"))

# Populated by main() from the live artifacts before any page is built.
THEMES = []
MODES = []
SHAPE_NAMES = {}
SHAPE_ORDER = []


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def discover_themes():
    """Theme names = the bare top-level class selectors in themes.css, in
    document order. Aliases (emitted as grouped ``.default, .editorial {``)
    are recovered by splitting each selector group on commas across newlines.
    Compound selectors (``:root[data-mode] .x``), ``::selection`` and ``@media``
    blocks never match a lone ``.name`` and are skipped."""
    p = os.path.join(STYLES, "themes.css")
    if not os.path.exists(p):
        return []
    css = re.sub(r"/\*.*?\*/", "", read(p), flags=re.S)  # strip comments
    themes, seen = [], set()
    for sel_group in re.findall(r"([^{}]+)\{", css):
        for sel in sel_group.split(","):
            sel = sel.strip()
            m = re.fullmatch(r"\.([a-z][a-z0-9-]*)", sel)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                themes.append(m.group(1))
    return themes


def discover_modes():
    """Modes = the data-mode values themes.css actually uses (the foundations
    contract is light/dark/system; we read them back rather than assume)."""
    p = os.path.join(STYLES, "themes.css")
    modes, seen = [], set()
    if os.path.exists(p):
        # Strip comments first: the file's header prose mentions data-mode="dark"
        # / "system" before the real rules, which would otherwise skew the order.
        css = re.sub(r"/\*.*?\*/", "", read(p), flags=re.S)
        for m in re.findall(r'data-mode="([a-z]+)"', css):
            if m not in seen:
                seen.add(m)
                modes.append(m)
    return modes or ["light", "dark", "system"]


def discover_shapes():
    """(name, description) for every shape in shapes.md Part A, in document
    order. Single source of truth — no duplicated catalog lives in this viewer,
    and the retired S0-S28 ids cannot reappear because only the semantic names
    are in the reference."""
    p = os.path.join(REFERENCE, "shapes.md")
    specs = []
    if not os.path.exists(p):
        return specs
    in_part_a = False
    for ln in read(p).splitlines():
        if ln.startswith("## Part A"):
            in_part_a = True
            continue
        if in_part_a and (ln.startswith("---") or ln.startswith("## ")):
            break
        if in_part_a and ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 2 and re.fullmatch(r"[a-z][a-z0-9-]*", cells[0]):
                specs.append((cells[0], cells[1]))
    return specs


def inlined_css():
    css = []
    for name in ("tokens.css", "components.css", "themes.css"):
        p = os.path.join(STYLES, name)
        if os.path.exists(p):
            css.append("/* === %s === */\n%s" % (name, read(p)))
    return "\n".join(css)


def switcher_js():
    p = os.path.join(STYLES, "switcher.js")
    if not os.path.exists(p):
        return ""
    # Defense in depth: never let an inlined </script> close our <script> early.
    return read(p).replace("</script>", "<\\/script>")


CHROME = """
  :root { color-scheme: light dark; }
  body { margin:0; font:14px/1.5 system-ui,-apple-system,sans-serif;
         background:var(--role-surface-primary,#fff); color:var(--role-text-primary,#111); }
  .galbar { position:sticky; top:0; z-index:9999; display:flex; flex-wrap:wrap; gap:6px;
            align-items:center; padding:8px 14px; background:#0d1117f2; color:#e6edf3;
            backdrop-filter:blur(8px); border-bottom:1px solid #30363d; font-size:13px; }
  .galbar a { color:#9ecbff; text-decoration:none; margin-right:8px; }
  .galbar strong { opacity:.55; font-weight:600; margin:0 4px 0 10px; text-transform:uppercase; letter-spacing:.04em; font-size:11px; }
  .galbar button { font:inherit; padding:3px 9px; border-radius:6px; border:1px solid #30363d;
                   background:transparent; color:inherit; cursor:pointer; }
  .galbar button.on { outline:2px solid #9ecbff; border-color:#9ecbff; }
  .galbar .sep { flex:1; }
  .galwrap { max-width:1440px; margin:0 auto; padding:0 0 80px; }
  .galhead { padding:24px 24px 8px; }
  .galhead h1 { font-size:18px; margin:0 0 4px; }
  .galhead p { margin:0; opacity:.6; font-size:13px; }
  .gal-item { border-top:1px solid var(--role-border-subtle,#8883); }
  .gal-label { position:sticky; top:41px; z-index:5; padding:8px 24px;
               background:var(--role-surface-secondary,#f3f3f3ee); backdrop-filter:blur(4px);
               font:600 12px/1.4 ui-monospace,monospace; color:var(--role-text-secondary,#555);
               border-bottom:1px solid var(--role-border-subtle,#8882); display:flex; gap:10px; align-items:baseline; }
  .gal-label .nm { color:var(--role-text-tertiary,#888); font-weight:400; font-family:system-ui; }
  /* component stage: show each specimen on a real surface */
  .stage { padding:32px 24px; }
"""


def page(title, lede, active, body):
    nav = ('<a href="index.html">overview</a><a href="components.html">components</a>'
           '<a href="shapes.html">shapes</a><a href="landing.html">landing&nbsp;page</a>')
    # Open on the conventional principal view when present (a theme literally
    # named "default", light mode), else the first discovered. This is a soft
    # preference for the initial selection only — every discovered theme/mode
    # is still listed and selectable.
    first_theme = "default" if "default" in THEMES else (THEMES[0] if THEMES else "default")
    first_mode = "light" if "light" in MODES else (MODES[0] if MODES else "light")
    tbtns = "".join('<button data-theme="%s"%s>%s</button>'
                    % (t, ' class="on"' if t == first_theme else "", t) for t in THEMES)
    mbtns = "".join('<button data-mode="%s"%s>%s</button>'
                    % (m, ' class="on"' if m == first_mode else "", m) for m in MODES)
    bar = ('<div class="galbar">' + nav + '<span class="sep"></span>'
           '<strong>theme</strong>' + tbtns + '<strong>mode</strong>' + mbtns + '</div>')
    # The wire script gets the DISCOVERED theme list injected — no hardcoded copy.
    themes_js = "[" + ",".join("'%s'" % t for t in THEMES) + "]"
    wire = """
    <script>
    (function(){
      var THEMES = %s;
      function mark(attr,val){
        document.querySelectorAll('.galbar button[data-'+attr+']').forEach(function(b){
          b.classList.toggle('on', b.getAttribute('data-'+attr)===val);
        });
      }
      function applyTheme(t){
        THEMES.forEach(function(c){ document.body.classList.remove(c); });
        document.body.classList.add(t);
        mark('theme',t);
      }
      function applyMode(m){
        document.documentElement.setAttribute('data-mode',m);
        mark('mode',m);
      }
      document.querySelectorAll('.galbar button[data-theme]').forEach(function(b){
        b.addEventListener('click',function(){ applyTheme(b.getAttribute('data-theme')); });
      });
      document.querySelectorAll('.galbar button[data-mode]').forEach(function(b){
        b.addEventListener('click',function(){ applyMode(b.getAttribute('data-mode')); });
      });
      applyTheme(%s);
      applyMode(%s);
    })();
    </script>""" % (themes_js, "'%s'" % first_theme, "'%s'" % first_mode)
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>%s</title><script>%s</script><style>%s\n%s</style></head><body>%s"
            "<div class=\"galwrap\"><div class=\"galhead\"><h1>%s</h1><p>%s</p></div>%s</div>%s"
            "</body></html>"
            % (html.escape(title), switcher_js(), inlined_css(), CHROME, bar,
               html.escape(title), lede, body, wire))


def build_components():
    files = sorted(glob.glob(os.path.join(COMPONENTS, "*.html")))
    items = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        items.append('<section class="gal-item"><div class="gal-label"><code>%s</code></div>'
                     '<div class="stage">%s</div></section>' % (html.escape(name), read(f)))
    return page("CDS — components (%d)" % len(files),
                "Every component family, rendered from its real markup fragment and the live generated CSS. Switch theme/mode above — the whole page re-skins.",
                "components", "".join(items)), len(files)


def shape_key(f):
    sid = os.path.splitext(os.path.basename(f))[0]
    return SHAPE_ORDER.index(sid) if sid in SHAPE_ORDER else 999


def build_shapes():
    files = sorted(glob.glob(os.path.join(SHAPES, "*.html")), key=shape_key)
    items = []
    for f in files:
        sid = os.path.splitext(os.path.basename(f))[0]
        nm = SHAPE_NAMES.get(sid, "")
        items.append('<section class="gal-item"><div class="gal-label"><code>%s</code>'
                     '<span class="nm">%s</span></div>%s</section>'
                     % (html.escape(sid), html.escape(nm), read(f)))
    return page("CDS — shapes (%d)" % len(files),
                "Every pre-defined shape, rendered with sample content. A shape is an organized arrangement of components for one landing-page section; each is identified by a semantic name describing its composition.",
                "shapes", "".join(items)), len(files)


def build_index(ncomp, nshape):
    body = ('<div class="stage"><ul style="line-height:2;font-size:15px">'
            '<li><a href="components.html"><strong>Components</strong></a> &mdash; %d families</li>'
            '<li><a href="shapes.html"><strong>Shapes</strong></a> &mdash; %d pre-defined shapes</li>'
            '<li><a href="landing.html"><strong>Sample landing page</strong></a> &mdash; alternating sections, full page</li>'
            '</ul><p style="opacity:.6">Themes (%d) and shapes (%d) are discovered from the live artifacts '
            'and reference — switch theme/mode in the bar above.</p></div>'
            % (ncomp, nshape, len(THEMES), nshape))
    return page("CDS render proof", "Real artifacts from the live config. Edit an artifact, re-run assemble.py, re-screenshot.", "index", body)


def main():
    if not os.path.isdir(STYLES) or not os.path.exists(os.path.join(STYLES, "themes.css")):
        sys.stderr.write(
            "assemble.py: no render artifacts found in %s\n"
            "  Generate them first with the cds-render-proof workflow, then re-run.\n" % OUT)
        sys.exit(1)

    global THEMES, MODES, SHAPE_NAMES, SHAPE_ORDER
    THEMES = discover_themes()
    MODES = discover_modes()
    shape_specs = discover_shapes()
    SHAPE_NAMES = dict(shape_specs)
    SHAPE_ORDER = [sid for sid, _ in shape_specs]

    comp_html, ncomp = build_components()
    shape_html, nshape = build_shapes()
    with open(os.path.join(OUT, "components.html"), "w", encoding="utf-8") as f:
        f.write(comp_html)
    with open(os.path.join(OUT, "shapes.html"), "w", encoding="utf-8") as f:
        f.write(shape_html)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index(ncomp, nshape))
    print("assembled: components.html (%d), shapes.html (%d), index.html — themes=%d modes=%d shapes-cataloged=%d"
          % (ncomp, nshape, len(THEMES), len(MODES), len(SHAPE_ORDER)))


if __name__ == "__main__":
    main()
