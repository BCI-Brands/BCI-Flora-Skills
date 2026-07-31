import os
import contact_sheet


def test_render_contains_inputs_outputs_and_devmode():
    html = contact_sheet.render_contact_sheet(
        title="LOOK 9",
        subtitle="3 inputs -> 24 outputs",
        inputs=[("TOP", "top.jpg"), ("BOTTOM", "jeans.jpg")],
        groups=[("Full", ["full-1.png", "full-2.png"])],
    )
    assert "LOOK 9" in html
    assert 'src="top.jpg"' in html
    assert 'src="full-1.png"' in html
    assert "DEV MODE" in html            # press-D developer mode present
    assert "<!doctype html>" not in html.lower()  # fragment; opened directly is fine


def test_render_escapes_html_metacharacters():
    html = contact_sheet.render_contact_sheet(
        title="<script>alert(1)</script>",
        subtitle='a & b "c"',
        inputs=[("<b>", 'x".jpg')],
        groups=[("g", ["full-1.png"])],
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_groups_from_state_groups_done_items_by_out_subdir():
    state = {"output": "/out", "items": [
        {"rel": "a.jpg", "out_subdir": "", "files": ["/out/a_MCP_1.png", "/out/a_MCP_2.png"]},
        {"rel": "s/b.jpg", "out_subdir": "s_MCP", "files": ["/out/s_MCP/b_MCP_1.png"]},
        {"rel": "c.jpg", "out_subdir": "", "files": []},   # not downloaded -> excluded
    ]}
    assert contact_sheet.groups_from_state(state) == [
        ("(root)", ["a_MCP_1.png", "a_MCP_2.png"]),
        ("s_MCP", [os.path.join("s_MCP", "b_MCP_1.png")]),
    ]


def test_render_annotates_outputs_with_qa_findings():
    qa = {
        "full-1.png": [{"input": "top.jpg", "dimension": "construction",
                        "verdict": "mismatch", "notes": 'placket <omitted> & cuffs missing'}],
        "full-2.png": [],
    }
    html = contact_sheet.render_contact_sheet(
        title="L", subtitle="s", inputs=[],
        groups=[("Full", ["full-1.png", "full-2.png", "full-3.png"])],
        qa_index=qa,
    )
    assert "top.jpg" in html and "construction: mismatch" in html
    assert "placket &lt;omitted&gt; &amp; cuffs missing" in html      # notes escaped
    assert "sev-high" in html                                        # mismatch styled as high severity
    assert "no issues found" in html                                 # judged-clean gets a green tick
    assert html.count("no issues found") == 1                        # full-3 unjudged -> no annotation


def test_render_without_qa_index_is_unannotated():
    html = contact_sheet.render_contact_sheet(
        title="L", subtitle="s", inputs=[], groups=[("Full", ["full-1.png"])])
    assert "no issues found" not in html          # no green tick
    assert '<div class="qa-finding' not in html   # no finding blocks (CSS rules alone are fine)
