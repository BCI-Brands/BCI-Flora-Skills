import floralib


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
