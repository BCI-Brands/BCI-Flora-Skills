import floralib
import json
import os


def test_output_variants_imagekit_tries_orig_true_first():
    url = "https://ik.imagekit.io/flora/run_abc/output_3.png"
    assert floralib.output_variants(url) == [url + "?tr=orig-true", url]


def test_output_variants_media_flora_is_bare_only():
    url = "https://media.flora.ai/node-inputs/2026/7/22/anonymous/abc.png"
    assert floralib.output_variants(url) == [url]


def test_output_variants_compressed_is_always_bare():
    url = "https://ik.imagekit.io/flora/run_abc/output_3.png"
    assert floralib.output_variants(url, compressed=True) == [url]


def test_output_variants_imagekit_with_existing_query_uses_ampersand():
    url = "https://ik.imagekit.io/flora/x.png?v=2"
    assert floralib.output_variants(url) == [url + "&tr=orig-true", url]


def test_plan_downloads_names_by_output_id():
    outputs = [
        {"output_id": "full-1", "url": "https://media.flora.ai/a.png"},
        {"output_id": "top-detail-2", "url": "https://media.flora.ai/b.png"},
    ]
    assert floralib.plan_downloads(outputs, "/out") == [
        ("https://media.flora.ai/a.png", "/out/full-1.png"),
        ("https://media.flora.ai/b.png", "/out/top-detail-2.png"),
    ]


def test_estimate_cost_is_flat_per_run():
    assert floralib.estimate_cost(4.32, 1) == 4.32     # one compose look
    assert floralib.estimate_cost(0.72, 10) == 7.2     # ten per-image runs
    assert floralib.estimate_cost(4.32, 0) == 0.0


def test_map_files_to_roles_look9_maps_cleanly():
    files = [
        "91526272_143_OATMEAL_061226_5564.jpg",
        "PROP_DENIM_JEANS_01_050526_9884.jpg",
        "PROP_SHOE_01_050526_9890.jpg",
    ]
    res = floralib.map_files_to_roles(files, ["top", "bottom", "shoes"])
    assert res["mapping"] == {
        "top": "91526272_143_OATMEAL_061226_5564.jpg",
        "bottom": "PROP_DENIM_JEANS_01_050526_9884.jpg",
        "shoes": "PROP_SHOE_01_050526_9890.jpg",
    }
    assert res["unmatched_files"] == []
    assert res["unfilled_roles"] == []


def test_map_files_to_roles_flags_ambiguity():
    files = ["a_shirt.jpg", "b_tee.jpg", "x_jean.jpg"]
    res = floralib.map_files_to_roles(files, ["top", "bottom", "shoes"])
    assert res["mapping"] == {"bottom": "x_jean.jpg"}
    assert set(res["unmatched_files"]) == {"a_shirt.jpg", "b_tee.jpg"}
    assert set(res["unfilled_roles"]) == {"top", "shoes"}


GOOD_RES = {
    "url": "https://storage.googleapis.com/flora-assets-prod/",
    "form_fields": {
        "Content-Type": "image/jpeg",
        "key": "mcp-uploads/x.jpg",
        "x-goog-date": "20260722T144942Z",
        "x-goog-credential": "svc/20260722/auto/storage/goog4_request",
        "x-goog-algorithm": "GOOG4-RSA-SHA256",
        "policy": "eyJhIjoxfQ==",
        "x-goog-signature": "ab" * 256,   # 512 lowercase hex chars
    },
}


def test_validate_good_reservation_has_no_problems():
    assert floralib.validate_gcs_reservation(GOOD_RES) == []


def test_validate_catches_non_hex_signature():
    bad = {"url": GOOD_RES["url"], "form_fields": dict(GOOD_RES["form_fields"])}
    bad["form_fields"]["x-goog-signature"] = "zz" + "ab" * 255
    assert any("hex" in p for p in floralib.validate_gcs_reservation(bad))


def test_validate_catches_missing_field():
    bad = {"url": GOOD_RES["url"], "form_fields": dict(GOOD_RES["form_fields"])}
    del bad["form_fields"]["policy"]
    assert any("policy" in p for p in floralib.validate_gcs_reservation(bad))


def test_build_compose_state_shape():
    st = floralib.build_compose_state(
        "/looks/LOOK 9", "tech_x", {"top": "a.jpg", "bottom": "b.jpg"}, 4.32)
    assert st["mode"] == "compose"
    assert st["technique"] == "tech_x"
    assert st["run_cost"] == 4.32
    assert st["run_id"] is None and st["run_stage"] == "pending"
    assert st["outputs"] == []
    assert st["inputs"]["top"] == {"file": "a.jpg", "asset_id": None, "stage": "pending"}
    assert set(st["inputs"]) == {"top", "bottom"}


def test_compose_state_in_progress():
    fresh = floralib.build_compose_state("/x", "tech_x", {"top": "a.jpg"}, 4.32)
    assert floralib.compose_state_in_progress(fresh) is False
    up = floralib.build_compose_state("/x", "tech_x", {"top": "a.jpg"}, 4.32)
    up["inputs"]["top"]["stage"] = "uploaded"; up["inputs"]["top"]["asset_id"] = "asset_1"
    assert floralib.compose_state_in_progress(up) is True
    started = floralib.build_compose_state("/x", "tech_x", {"top": "a.jpg"}, 4.32)
    started["run_stage"] = "run_started"
    assert floralib.compose_state_in_progress(started) is True


def test_resolve_qa_pairs_maps_outputs_to_inputs():
    state = {
        "input": "/photos",
        "items": [
            {"rel": "shirt.jpg", "stem": "shirt", "files": [
                "/out/shirt_MCP_1.png", "/out/shirt_MCP_2.png"]},
            {"rel": "sub/pants.jpg", "stem": "pants", "files": [
                "/out/sub/pants_MCP_1.png"]},
        ],
    }
    result = floralib.resolve_qa_pairs(state, ["shirt_MCP_1.png", "pants_MCP_1.png"])
    assert result["pairs"] == [
        {"output": "/out/shirt_MCP_1.png", "input": "/photos/shirt.jpg"},
        {"output": "/out/sub/pants_MCP_1.png", "input": "/photos/sub/pants.jpg"},
    ]
    assert result["unresolved"] == []


def test_resolve_qa_pairs_flags_unresolved_selection():
    state = {
        "input": "/photos",
        "items": [{"rel": "shirt.jpg", "stem": "shirt", "files": ["/out/shirt_MCP_1.png"]}],
    }
    result = floralib.resolve_qa_pairs(state, ["shirt_MCP_1.png", "ghost_MCP_9.png"])
    assert result["pairs"] == [{"output": "/out/shirt_MCP_1.png", "input": "/photos/shirt.jpg"}]
    assert result["unresolved"] == ["ghost_MCP_9.png"]


def test_resolve_qa_pairs_flags_ambiguous_basename_collision():
    """A recursive batch (init.py --recurse) can produce two different input
    photos that both output the same basename (e.g. red/shirt.jpg and
    blue/shirt.jpg both yield shirt_MCP_1.png in their own subfolders). Picking
    that basename is inherently ambiguous -- it must be reported, not guessed."""
    state = {
        "input": "/photos",
        "items": [
            {"rel": "red/shirt.jpg", "stem": "shirt", "files": [
                "/out/red/shirt_MCP_1.png"]},
            {"rel": "blue/shirt.jpg", "stem": "shirt", "files": [
                "/out/blue/shirt_MCP_1.png"]},
        ],
    }
    result = floralib.resolve_qa_pairs(state, ["shirt_MCP_1.png"])
    assert result["pairs"] == []
    assert result["ambiguous"] == ["shirt_MCP_1.png"]
    assert result["unresolved"] == []


def test_qa_overall_flag_clean_match_is_not_flagged():
    assert floralib.qa_overall_flag("match", "match") is False


def test_qa_overall_flag_any_non_match_is_flagged():
    assert floralib.qa_overall_flag("minor_shift", "match") is True
    assert floralib.qa_overall_flag("match", "mismatch") is True
    assert floralib.qa_overall_flag("minor_shift", "minor_deviation") is True


def test_render_qa_report_md_builds_table_with_flag_column():
    results = [
        {
            "output": "/out/shirt_MCP_1.png", "input": "/in/shirt.jpg",
            "color": {"verdict": "match", "notes": "navy matches"},
            "construction": {"verdict": "match", "notes": "all buttons present"},
            "overall_flag": False,
        },
        {
            "output": "/out/shirt_MCP_2.png", "input": "/in/shirt.jpg",
            "color": {"verdict": "mismatch", "notes": "navy rendered bright blue"},
            "construction": {"verdict": "match", "notes": "ok"},
            "overall_flag": True,
        },
    ]
    md = floralib.render_qa_report_md(results)
    assert md.splitlines()[0].startswith("| Output |")
    assert "shirt_MCP_1.png" in md
    assert "shirt_MCP_2.png" in md
    assert "mismatch" in md
    assert "navy rendered bright blue" in md


def test_render_qa_report_md_escapes_pipe_in_notes():
    """Pipe characters in notes must be escaped to avoid splitting columns."""
    results = [
        {
            "output": "/out/test_MCP_1.png", "input": "/in/test.jpg",
            "color": {"verdict": "match", "notes": "collar | cuffs mismatched"},
            "construction": {"verdict": "match", "notes": "ok"},
            "overall_flag": False,
        },
    ]
    md = floralib.render_qa_report_md(results)
    # Verify escaped pipe appears in output
    assert "\\|" in md
    # Verify that the escaped pipe is present instead of raw pipe in notes
    assert "collar \\| cuffs mismatched" in md


def test_render_qa_report_md_replaces_newline_in_notes():
    """Newlines in notes must be replaced to maintain one-row-per-line structure."""
    results = [
        {
            "output": "/out/test_MCP_1.png", "input": "/in/test.jpg",
            "color": {"verdict": "match", "notes": "line1\nline2"},
            "construction": {"verdict": "match", "notes": "ok"},
            "overall_flag": False,
        },
    ]
    md = floralib.render_qa_report_md(results)
    # Verify no raw newline inside the data row
    lines = md.splitlines()
    assert len(lines) == 3  # header + separator + 1 data row (not 4+)
    assert "line1 line2" in md  # newline replaced with space


def test_render_qa_report_md_escapes_backslash_before_pipe():
    """Pre-existing backslash-pipe sequences must be escaped correctly.
    Backslashes must be escaped first to prevent \\| from becoming an
    unescaped pipe after pipe-escaping (which would leave a literal |
    that Markdown parsers read as a column delimiter).

    When _sanitize_table_cell processes "S\\|M" (S, backslash, pipe, M):
    1. Replace \ with \\: produces S\\|M (doubled backslash, then pipe)
    2. Replace | with \\|: produces S\\\|M (triple backslash, then pipe)
    3. Result contains: three backslashes, one pipe

    This test directly asserts the fully-escaped form to catch any reversion.
    """
    results = [
        {
            "output": "/out/test_MCP_1.png", "input": "/in/test.jpg",
            "color": {"verdict": "match", "notes": "S\\|M"},
            "construction": {"verdict": "match", "notes": "ok"},
            "overall_flag": False,
        },
    ]
    md = floralib.render_qa_report_md(results)
    # Assert the exact escaped sequence is present in the output.
    # The string "S\\\\\\|M" is a Python literal representing:
    # S, backslash, backslash, backslash, pipe, M
    # This is the ONLY safe form that prevents Markdown from reading the pipe
    # as a column delimiter. Any deviation (e.g., S\\|M with only 2 backslashes)
    # means the bug is back.
    assert "S\\\\\\|M" in md, f"Expected fully-escaped S\\\\\\|M not found in: {md}"


def test_render_qa_report_md_replaces_carriage_return_in_notes():
    """A lone \\r (e.g. from \\r\\n line endings) must not survive into the
    rendered cell -- it would leave a stray carriage return in the table."""
    results = [
        {
            "output": "/out/test_MCP_1.png", "input": "/in/test.jpg",
            "color": {"verdict": "match", "notes": "line1\rline2"},
            "construction": {"verdict": "match", "notes": "ok"},
            "overall_flag": False,
        },
    ]
    md = floralib.render_qa_report_md(results)
    assert "\r" not in md
    assert "line1 line2" in md


def test_save_json_atomic_writes_valid_json_and_leaves_no_tmp(tmp_path):
    p = str(tmp_path / "state.json")
    floralib.save_json_atomic({"a": 1}, p)
    assert json.load(open(p)) == {"a": 1}
    assert sorted(os.listdir(str(tmp_path))) == ["state.json"]  # no .tmp left behind


def test_save_json_atomic_replaces_existing_file(tmp_path):
    p = str(tmp_path / "state.json")
    open(p, "w").write("old garbage")
    floralib.save_json_atomic([1, 2], p)
    assert json.load(open(p)) == [1, 2]


def test_is_output_artifact_matches_suffix_number_pattern():
    assert floralib.is_output_artifact("shirt_MCP_1.png", "_MCP") is True
    assert floralib.is_output_artifact("shirt_MCP_12.PNG", "_MCP") is True


def test_is_output_artifact_ignores_plain_inputs():
    assert floralib.is_output_artifact("shirt.jpg", "_MCP") is False
    assert floralib.is_output_artifact("shirt_MCP_1_final.jpg", "_MCP") is False  # pattern not at end


def test_is_output_artifact_respects_the_configured_suffix():
    assert floralib.is_output_artifact("shirt_MCP_1.png", "_AI") is False


def test_match_reservations_matches_pending_items_by_rel():
    items = [
        {"rel": "a.jpg", "stage": "pending"},
        {"rel": "b.jpg", "stage": "uploaded"},
    ]
    res = {"a.jpg": {"asset_id": "as_1", "url": "https://u", "form_fields": {}}}
    m = floralib.match_reservations(res, items)
    assert m["matched"] == {"a.jpg": res["a.jpg"]}
    assert m["missing_rels"] == []
    assert m["unknown_rels"] == []


def test_match_reservations_flags_missing_pending_and_unknown_keys():
    items = [
        {"rel": "a.jpg", "stage": "pending"},
        {"rel": "b.jpg", "stage": "pending"},
    ]
    res = {"a.jpg": {"asset_id": "as_1", "url": "https://u", "form_fields": {}},
           "ghost.jpg": {"asset_id": "as_9", "url": "https://u", "form_fields": {}}}
    m = floralib.match_reservations(res, items)
    assert m["missing_rels"] == ["b.jpg"]
    assert m["unknown_rels"] == ["ghost.jpg"]


def test_match_reservations_uploaded_items_need_no_reservation():
    items = [{"rel": "done.jpg", "stage": "uploaded"}]
    m = floralib.match_reservations({}, items)
    assert m == {"matched": {}, "missing_rels": [], "unknown_rels": []}
