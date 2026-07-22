#!/usr/bin/env python3
"""Build a review gallery for a flora-batch (for headless-Chrome screenshotting).

Usage: review.py --state STATE [--out gallery.html]
Renders one thumbnail per source image (output #1), grouped by output subfolder,
labelled with the source stem. Uses the bare (compressed) output URLs so the page is
light to load. Then screenshot it:
  chrome --headless=new --hide-scrollbars --virtual-time-budget=25000 \
         --window-size=1600,2600 --screenshot=gallery.png file://<out>
"""
import argparse, os, json, html
from collections import Counter

CSS = """<style>
body{margin:0;background:#0f0f11;color:#fafafa;font:13px system-ui,sans-serif;padding:24px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:14px;color:#a1a1aa;margin:22px 0 10px;border-bottom:1px solid #27272a;padding-bottom:6px}
.sub{color:#71717a;font-size:12px;margin:0 0 6px}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.t{background:#18181b;border:1px solid #27272a;border-radius:8px;overflow:hidden}
.t img{width:100%;aspect-ratio:2/3;object-fit:cover;display:block;background:#000}
.t div{font-size:10px;color:#a1a1aa;padding:5px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    s = json.load(open(a.state))
    out_html = a.out or os.path.join(s["output"], "review_gallery.html")

    groups = {}
    done = [it for it in s["items"] if it.get("outputs")]
    for it in done:
        groups.setdefault(it.get("out_subdir", ""), []).append(it)

    parts = [CSS, f"<h1>{html.escape(os.path.basename(s['output']))}</h1>",
             f"<p class='sub'>{len(done)} images &middot; technique {html.escape(s.get('technique',''))} &middot; output #1 shown</p>"]
    for g in sorted(groups):
        parts.append(f"<h2>{html.escape(g or '(root)')} &mdash; {len(groups[g])}</h2><div class='grid'>")
        for it in groups[g]:
            url = it["outputs"][0]
            parts.append(f"<div class='t'><img src='{url}'><div>{html.escape(it['stem'][:34])}</div></div>")
        parts.append("</div>")
    open(out_html, "w").write("".join(parts))
    print("gallery:", out_html, "| tiles:", len(done))
    print("stages:", dict(Counter(i["stage"] for i in s["items"])))

if __name__ == "__main__":
    main()
