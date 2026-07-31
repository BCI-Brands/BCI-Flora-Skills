#!/usr/bin/env python3
"""Portable, self-contained review gallery for a finished run. Relative <img>
refs (works by double-click, no server, no headless Chrome). Press D for a
developer mode that copies a tile's name on click.

Usage:
  contact_sheet.py --state batch_state.json          (per-image batch)
  contact_sheet.py --dir DIR --outputs OUTPUTS.json \
      [--title T] [--subtitle S] [--inputs role=FILE,role=FILE]   (compose)
Writes _contact_sheet.html into the output folder.
"""
import argparse, os, json, re, sys, html as _html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import qa_findings_index

_CSS = """
:root{--bg:#f6f6f4;--panel:#fff;--ink:#1b221d;--muted:#6b7168;--line:#e3e3de;--accent:#2743E3;}
@media (prefers-color-scheme:dark){:root{--bg:#14150f;--panel:#1c1e18;--ink:#f2f2ec;--muted:#9a9f92;--line:#2c2f27;}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,sans-serif}
header{padding:22px 26px 8px}h1{margin:0;font-size:20px}.sub{color:var(--muted);margin-top:4px;font-size:13px}
h2{margin:26px 26px 10px;font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);border-top:1px solid var(--line);padding-top:18px}
.grid{display:grid;gap:12px;padding:0 26px;grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
figure img{display:block;width:100%;height:auto;background:#fff}
figcaption{padding:7px 9px;font-size:12px;color:var(--muted)}.inputs figure{border-color:var(--accent)}
.qa-finding{margin:0 9px 8px;padding:6px 8px;border-radius:6px;background:rgba(127,127,127,.08);font-size:12px;line-height:1.4}
.qa-finding b{display:block;margin-bottom:2px}
.sev-high{border-left:3px solid #d94f4f}.sev-high b{color:#d94f4f}
.sev-med{border-left:3px solid #d99a2b}.sev-med b{color:#d99a2b}
.qa-ok{margin:0 9px 8px;font-size:12px;color:#3d9a52}
body.dev [data-el]{outline:1px dashed rgba(39,67,227,.4)}body.dev [data-el]:hover{outline:2px solid #2743E3;cursor:crosshair}
.dev-badge{position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9;display:none;padding:7px 14px;font:600 11px/1 system-ui;letter-spacing:.14em;text-transform:uppercase;color:#fff;background:#2743E3;border-radius:999px}
body.dev .dev-badge{display:block}.dev-toast{position:fixed;bottom:70px;left:50%;transform:translateX(-50%);z-index:9;opacity:0;padding:9px 16px;font:600 12px/1 system-ui;color:#fff;background:#1B2FA8;border-radius:999px;transition:opacity .2s}.dev-toast.show{opacity:1}
"""

_JS = """
(function(){var toast=document.getElementById('t'),tT=null;
function isDev(){return document.body.classList.contains('dev');}
function msg(m){toast.textContent=m;toast.classList.add('show');clearTimeout(tT);tT=setTimeout(function(){toast.classList.remove('show');},1400);}
function copy(x){
  function fb(){var a=document.createElement('textarea');a.value=x;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();var ok=false;try{ok=document.execCommand('copy');}catch(e){}document.body.removeChild(a);msg(ok?'Copied: '+x:'Copy failed');}
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(x).then(function(){msg('Copied: '+x);},fb);}else{fb();}
}
document.addEventListener('keydown',function(e){if(e.key==='d'||e.key==='D')document.body.classList.toggle('dev');});
document.addEventListener('click',function(e){if(!isDev())return;var el=e.target.closest('[data-el]');if(!el)return;e.preventDefault();e.stopPropagation();copy(el.getAttribute('data-el'));},true);})();
"""


def _fig(src, caption, el, extra=""):
    return ('<figure data-el="%s"><img src="%s"><figcaption>%s</figcaption>%s</figure>'
            % (_html.escape(el, quote=True), _html.escape(src, quote=True), _html.escape(caption), extra))


def _qa_annotation(findings):
    """HTML block for one output's QA findings ([] = judged clean)."""
    if not findings:
        return '<div class="qa-ok">✓ no issues found</div>'
    parts = []
    for f in findings:
        sev = "sev-high" if f["verdict"] == "mismatch" else "sev-med"
        parts.append('<div class="qa-finding %s"><b>%s · %s: %s</b>%s</div>'
                     % (sev, _html.escape(f["input"]), _html.escape(f["dimension"]),
                        _html.escape(f["verdict"]), _html.escape(f["notes"])))
    return "".join(parts)


def render_contact_sheet(title, subtitle, inputs, groups, qa_index=None):
    """inputs: [(label, filename)]; groups: [(heading, [filename, ...])]. Returns HTML.
    qa_index (optional): output basename -> findings list from
    floralib.qa_findings_index; annotates judged outputs with plain-language
    QA notes (green tick when judged clean, nothing when never judged)."""
    parts = ["<meta charset='utf-8'><title>%s</title><style>%s</style>" % (_html.escape(title), _CSS)]
    parts.append("<header><h1>%s</h1><div class='sub'>%s</div></header>"
                 % (_html.escape(title), _html.escape(subtitle)))
    if inputs:
        parts.append("<h2>Inputs</h2><div class='grid inputs'>")
        for label, fn in inputs:
            parts.append(_fig(fn, label + " — " + fn, "input " + label))
        parts.append("</div>")
    for heading, files in groups:
        parts.append("<h2>%s</h2><div class='grid'>" % _html.escape(heading))
        for fn in files:
            extra = ""
            if qa_index is not None:
                base = os.path.basename(fn)
                if base in qa_index:
                    extra = _qa_annotation(qa_index[base])
            parts.append(_fig(fn, fn, "output " + fn, extra))
        parts.append("</div>")
    parts.append('<div class="dev-badge">DEV MODE · click a tile to copy its name · press D to exit</div>')
    parts.append('<div class="dev-toast" id="t"></div>')
    parts.append("<script>%s</script>" % _JS)
    return "\n".join(parts)


def groups_from_state(state):
    """Per-image mode: [(heading, [img path relative to state['output'], ...])]
    for every item with downloaded files, grouped by out_subdir. Relative paths
    keep the gallery portable (it lives at state['output']/_contact_sheet.html)."""
    out = state["output"]
    groups = {}
    for it in state.get("items", []):
        if not it.get("files"):
            continue
        heading = it.get("out_subdir", "") or "(root)"
        for f in it["files"]:
            groups.setdefault(heading, []).append(os.path.relpath(f, out))
    return [(h, groups[h]) for h in sorted(groups)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--outputs")
    ap.add_argument("--state")
    ap.add_argument("--title", default="Contact sheet")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--inputs", default="", help="role=FILE,role=FILE (optional)")
    ap.add_argument("--qa-results", help="qa_results.json — annotate outputs with QA findings")
    a = ap.parse_args()

    qa_index = None
    if a.qa_results:
        qa_index = qa_findings_index(json.load(open(a.qa_results)))

    if a.state:
        s = json.load(open(a.state))
        groups = groups_from_state(s)
        title = a.title if a.title != "Contact sheet" else os.path.basename(s["output"])
        n = sum(len(files) for _h, files in groups)
        sub = a.subtitle or "%d outputs · technique %s" % (n, s.get("technique", ""))
        html = render_contact_sheet(title, sub, [], groups, qa_index=qa_index)
        out = os.path.join(s["output"], "_contact_sheet.html")
        open(out, "w").write(html)
        print("wrote", out)
        return
    if not (a.dir and a.outputs):
        ap.error("provide --state (per-image) or --dir + --outputs (compose)")

    inputs = []
    if a.inputs:
        for pair in a.inputs.split(","):
            role, fn = pair.split("=", 1)
            inputs.append((role.strip(), fn.strip()))

    outs = json.load(open(a.outputs))
    groups_map = {}
    for o in outs:
        oid = o["output_id"]
        prefix = oid.rsplit("-", 1)[0] if "-" in oid else oid   # full / top-crop / top-detail
        groups_map.setdefault(prefix, []).append(oid + ".png")
    def _num(fn):
        m = re.search(r"(\d+)\.png$", fn)
        return (int(m.group(1)) if m else 0, fn)
    groups = [(k, sorted(v, key=_num)) for k, v in sorted(groups_map.items())]

    html = render_contact_sheet(a.title, a.subtitle, inputs, groups, qa_index=qa_index)
    out = os.path.join(a.dir, "_contact_sheet.html")
    open(out, "w").write(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
