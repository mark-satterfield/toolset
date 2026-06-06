#!/usr/bin/env python3
"""
CDS render-proof gallery assembler.

NOT a generator of CSS or markup. It only *views* the real pregenerated
artifacts: it inlines the live generated stylesheet set and wraps the
component fragments (../../components/*.html) and shape fragments
(../../shapes/*.html) into two browsable gallery pages with a theme/mode
switch bar driven by the real switcher.js. The sample landing page
(landing.html) is already a full standalone document and is linked as-is.

Edit an artifact, re-run this, re-screenshot — that is the iteration loop.

Usage: python3 assemble.py
Outputs (next to this file): components.html, shapes.html, index.html
"""
import os, glob, html, re

HERE = os.path.dirname(os.path.abspath(__file__))
# Artifacts live alongside this script (test/render/), consolidated here so the
# plugin tree is not fragmented. styles/ components/ shapes/ landing.html are the
# real pregenerated artifacts; this script only assembles a viewer over them.
STYLES = os.path.join(HERE, "styles")
COMPONENTS = os.path.join(HERE, "components")
SHAPES = os.path.join(HERE, "shapes")

THEMES = ["default", "clarity", "editorial", "punctuation", "statement",
          "feature-dark", "code", "deep"]
MODES = ["light", "dark", "system"]

SHAPE_NAMES = {
    "S0": "Standalone heading strip", "S1": "Centered text + visual below",
    "S2": "Two-column text/visual", "S3": "Centered text + embedded affordance",
    "S4": "Static card grid", "S5": "Tagged card grid",
    "S6": "Tabs with one panel per tab", "S7": "Alternating image+text rows",
    "S8": "Horizontal carousel", "S9": "Marquee strip", "S10": "Numbered step row",
    "S11": "3-up stacked pull-quotes", "S12": "Quote swiper with logos",
    "S13": "Single hero quote", "S14": "Accordion list",
    "S15": "Tier card row + segment toggle", "S16": "Rate table",
    "S17": "Banner strip", "S18": "Full-width CTA panel",
    "S19": "CTA panel + newsletter form", "S20": "Path picker (2-card fork)",
    "S21": "Pictogram + nested sub-cards", "S22": "Pill/tag cloud columns",
    "S23": "Lead card + companion carousel", "S24": "Resource grid with source tags",
    "S25": "Two-column prompt/artifact panel", "S26": "Download/install button strip",
    "S27": "Footer navigation grid", "S28": "Sub-hero with video + CTA pair",
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


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
    tbtns = "".join('<button data-theme="%s"%s>%s</button>'
                    % (t, ' class="on"' if t == "default" else "", t) for t in THEMES)
    mbtns = "".join('<button data-mode="%s"%s>%s</button>'
                    % (m, ' class="on"' if m == "light" else "", m) for m in MODES)
    bar = ('<div class="galbar">' + nav + '<span class="sep"></span>'
           '<strong>theme</strong>' + tbtns + '<strong>mode</strong>' + mbtns + '</div>')
    wire = """
    <script>
    (function(){
      var THEMES = ['default','clarity','editorial','punctuation','statement','feature-dark','code','deep'];
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
      applyTheme('default');
      applyMode('light');
    })();
    </script>"""
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
    m = re.match(r"S(\d+)", os.path.basename(f))
    return int(m.group(1)) if m else 999


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
                "Every pre-defined shape (S0-S28), rendered with sample content. A shape is an organized arrangement of components for one landing-page section.",
                "shapes", "".join(items)), len(files)


def build_index(ncomp, nshape):
    body = ('<div class="stage"><ul style="line-height:2;font-size:15px">'
            '<li><a href="components.html"><strong>Components</strong></a> &mdash; %d families</li>'
            '<li><a href="shapes.html"><strong>Shapes</strong></a> &mdash; %d pre-defined shapes</li>'
            '<li><a href="landing.html"><strong>Sample landing page</strong></a> &mdash; alternating sections, full page</li>'
            '</ul><p style="opacity:.6">Gaps reported by generate-stylesheets: see <code>styles/GAPS.md</code>.</p></div>'
            % (ncomp, nshape))
    return page("CDS render proof", "Real artifacts from the live config. Edit an artifact, re-run assemble.py, re-screenshot.", "index", body)


def main():
    comp_html, ncomp = build_components()
    shape_html, nshape = build_shapes()
    with open(os.path.join(HERE, "components.html"), "w", encoding="utf-8") as f:
        f.write(comp_html)
    with open(os.path.join(HERE, "shapes.html"), "w", encoding="utf-8") as f:
        f.write(shape_html)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index(ncomp, nshape))
    print("assembled: components.html (%d), shapes.html (%d), index.html" % (ncomp, nshape))


if __name__ == "__main__":
    main()
