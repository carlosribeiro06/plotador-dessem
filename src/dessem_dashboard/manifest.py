"""Write run_manifest.json so a dashboard HTML can be traced back to its inputs.

Records the UTC timestamp, git state, interpreter/platform, invocation parameters, data
volumes and elapsed time of a run. Must stay importable without the data stack (no pandas).
"""

from __future__ import annotations

import json
import platform
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from dessem_dashboard import __version__

# Git provenance is resolved against the installed package, never against the caller's working
# directory: a run started from an unrelated repository must not record that repository's sha as
# the provenance of this dashboard. Tests override this to point at a throwaway repository.
_GIT_ANCHOR = Path(__file__).resolve().parent


def _git_output(args: Sequence[str]) -> str | None:
    """Return the stripped stdout of `git <args>`, or None outside a git checkout."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=_GIT_ANCHOR,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip()


def _git_sha() -> str | None:
    """Return the 40-character HEAD commit sha, or None outside a git checkout."""
    return _git_output(["rev-parse", "HEAD"])


def _git_dirty() -> bool | None:
    """Return whether the working tree has uncommitted changes, or None outside a git checkout."""
    status = _git_output(["status", "--porcelain"])
    return None if status is None else len(status) > 0


def _jsonable(value: object) -> object:
    """Recursively convert Path values to POSIX strings; leave other scalars untouched."""
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, Sequence):
        return [_jsonable(item) for item in value]
    return value


def write_run_manifest(
    output_dir: Path | str,
    *,
    params: Mapping[str, object],
    elapsed_s: float,
    data_volumes: Mapping[str, int] | None = None,
    warnings: Sequence[str] = (),
) -> Path:
    """Write run_manifest.json inside output_dir (created if needed); return the written path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    git_sha = _git_sha()
    manifest: dict[str, object] = {
        "timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "git_sha": git_sha,
        "git_dirty": _git_dirty() if git_sha is not None else None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_version": __version__,
        "params": _jsonable(params),
        "data_volumes": dict(data_volumes) if data_volumes is not None else {},
        "warnings": list(warnings),
        "elapsed_seconds": round(elapsed_s, 3),
    }
    target = output_dir / "run_manifest.json"
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
