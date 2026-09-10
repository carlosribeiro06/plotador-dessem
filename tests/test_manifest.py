"""Tests for dessem_dashboard.manifest."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from dessem_dashboard.manifest import write_run_manifest

_GIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def _git(args: Sequence[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def test_write_run_manifest_creates_file_with_exact_key_order(tmp_path: Path) -> None:
    manifest_path = write_run_manifest(
        tmp_path, params={"casos": [Path("/a")], "referencia": "a"}, elapsed_s=1.23456
    )
    assert manifest_path == tmp_path / "run_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert list(data.keys()) == [
        "timestamp_utc",
        "git_sha",
        "git_dirty",
        "python",
        "platform",
        "package_version",
        "params",
        "data_volumes",
        "warnings",
        "elapsed_seconds",
    ]


def test_write_run_manifest_rounds_elapsed_seconds_and_serialises_path_param(
    tmp_path: Path,
) -> None:
    manifest_path = write_run_manifest(
        tmp_path, params={"casos": [Path("/a")], "referencia": "a"}, elapsed_s=1.23456
    )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["elapsed_seconds"] == 1.235
    assert data["params"]["casos"] == ["/a"]
    assert data["params"]["referencia"] == "a"


def test_write_run_manifest_creates_nested_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "nao" / "existe"
    manifest_path = write_run_manifest(output_dir, params={}, elapsed_s=0.0)
    assert manifest_path == output_dir / "run_manifest.json"
    assert manifest_path.is_file()


def test_write_run_manifest_defaults_data_volumes_and_warnings_to_empty(tmp_path: Path) -> None:
    manifest_path = write_run_manifest(tmp_path, params={}, elapsed_s=0.0)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["data_volumes"] == {}
    assert data["warnings"] == []


def test_write_run_manifest_keeps_accented_warnings_unescaped_in_raw_file(tmp_path: Path) -> None:
    manifest_path = write_run_manifest(
        tmp_path,
        params={},
        elapsed_s=0.0,
        data_volumes={"decks": 2},
        warnings=["Atenção: lacuna de datas encontrada"],
    )
    raw_text = manifest_path.read_text(encoding="utf-8")
    assert "Atenção" in raw_text
    data = json.loads(raw_text)
    assert data["data_volumes"] == {"decks": 2}
    assert data["warnings"] == ["Atenção: lacuna de datas encontrada"]


def test_write_run_manifest_serialises_nested_path_values_in_list_and_mapping(
    tmp_path: Path,
) -> None:
    manifest_path = write_run_manifest(
        tmp_path,
        params={
            "casos": [Path("/a"), Path("/b")],
            "extra": {"settings": Path("/c/settings.json")},
        },
        elapsed_s=0.0,
    )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["params"]["casos"] == ["/a", "/b"]
    assert data["params"]["extra"]["settings"] == "/c/settings.json"


def test_write_run_manifest_leaves_scalar_param_values_untouched(tmp_path: Path) -> None:
    manifest_path = write_run_manifest(
        tmp_path,
        params={"stages_per_deck": 48, "dry_run": False, "referencia": None},
        elapsed_s=0.0,
    )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["params"] == {"stages_per_deck": 48, "dry_run": False, "referencia": None}


def test_write_run_manifest_outside_git_checkout_yields_none_git_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest_path = write_run_manifest(tmp_path / "output", params={}, elapsed_s=0.0)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["git_sha"] is None
    assert data["git_dirty"] is None


def test_write_run_manifest_at_repository_root_has_valid_git_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # git_dirty is intentionally not asserted here: the real repository tree state is
    # ambient and non-deterministic across checkouts (see throwaway-repo test below).
    repo_root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(repo_root)
    manifest_path = write_run_manifest(tmp_path, params={}, elapsed_s=0.0)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert _GIT_SHA_PATTERN.fullmatch(data["git_sha"])
    assert isinstance(data["git_dirty"], bool)


def test_write_run_manifest_git_dirty_reflects_clean_then_modified_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "throwaway_repo"
    repo.mkdir()
    _git(["init"], cwd=repo)
    (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
    _git(["add", "tracked.txt"], cwd=repo)
    _git(
        ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "initial"],
        cwd=repo,
    )
    monkeypatch.chdir(repo)

    clean_manifest = write_run_manifest(repo / "out_clean", params={}, elapsed_s=0.0)
    clean_data = json.loads(clean_manifest.read_text(encoding="utf-8"))
    assert clean_data["git_dirty"] is False
    assert _GIT_SHA_PATTERN.fullmatch(clean_data["git_sha"])

    (repo / "tracked.txt").write_text("modified\n", encoding="utf-8")

    dirty_manifest = write_run_manifest(repo / "out_dirty", params={}, elapsed_s=0.0)
    dirty_data = json.loads(dirty_manifest.read_text(encoding="utf-8"))
    assert dirty_data["git_dirty"] is True
