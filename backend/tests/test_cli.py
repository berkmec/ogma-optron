"""CLI smoke tests.

We do NOT call HF or agent.exe from pytest — those are exercised by the
manual smoke scripts. These tests cover:

  - the argparse plumbing (`--help`, `--version`, subcommands resolve)
  - the offline `health` subcommand
  - input-validation exits before any network/subprocess call:
      * `analyze` with a missing image -> exit 2
      * `review`  with a missing workspace -> exit 2
  - the new file_store helper `save_upload_from_path` round-trips a PNG.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import cli
from app.services import file_store


def _tiny_png_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color=(220, 60, 60))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_build_parser_has_all_subcommands() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["health"])
    assert args.command == "health"
    for sub in ("analyze", "review", "chat", "eval"):
        # build_parser must accept each subcommand without raising.
        # We rely on each having at least the `func` attribute set via set_defaults.
        ns = parser.parse_args(
            {
                "analyze": ["analyze", "dummy.png"],
                "review": ["review", "--workspace", "."],
                "chat": ["chat", "obs_id_x", "hello"],
                "eval": ["eval"],
            }[sub]
        )
        assert ns.command == sub
        assert callable(getattr(ns, "func", None))


def test_version_flag_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "optron" in out


def test_health_prints_settings_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["health"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    for key in (
        "vision_model",
        "openai_base_url",
        "hf_token_configured",
        "agent_code_bin_set",
        "agent_code_model",
    ):
        assert key in payload, f"missing key in health payload: {key}"


def test_analyze_missing_image_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.png"
    rc = cli.main(["analyze", str(missing)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "image not found" in err


def test_review_missing_workspace_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "no_such_dir"
    rc = cli.main(["review", "--workspace", str(missing)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "workspace not found" in err


def test_save_upload_from_path_roundtrips_a_png(tmp_path: Path) -> None:
    src = tmp_path / "tiny.png"
    src.write_bytes(_tiny_png_bytes())

    asset = file_store.save_upload_from_path(src)

    assert asset.asset_id
    assert asset.mime_type == "image/png"
    assert asset.width == 4 and asset.height == 4
    assert asset.size_bytes == src.stat().st_size
    full = file_store.asset_full_path(asset.storage_path)
    assert full.exists()
    assert full.read_bytes() == src.read_bytes()
