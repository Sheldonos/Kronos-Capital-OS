#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(os.environ.get("KCOS_RELEASE_DIR", str(ROOT / "dist")))
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".git", ".mypy_cache", ".ruff_cache", ".venv", ".kcos", "dist", "build", "wheelhouse"}
EXCLUDED_FILES = {"PACKAGE_MANIFEST.json", "FILE_HASHES.json", "RELEASE_SHA256.txt"}


def included_files(include_generated: bool = True):
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if not include_generated and rel.name in EXCLUDED_FILES:
            continue
        yield rel, p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = meta["project"]["version"]
    for p in (ROOT / "PACKAGE_MANIFEST.json", ROOT / "FILE_HASHES.json", ROOT / "RELEASE_SHA256.txt"):
        p.unlink(missing_ok=True)
    for d in list(ROOT.rglob("__pycache__")) + [ROOT / ".pytest_cache"]:
        if d.exists():
            shutil.rmtree(d)

    source_files = [str(rel) for rel, _ in included_files(include_generated=False)]
    manifest = {
        "name": "Kronos Capital OS — Full Autonomous Quantitative Institution",
        "version": version,
        "scope": "full-system-not-genesis-only",
        "upstream": {
            "repository": "https://github.com/shiyu-coder/Kronos",
            "commit": "67b630e67f6a18c9e9be918d9b4337c960db1e9a",
        },
        "decision_state_max_age_seconds": 6,
        "planes": [
            "genesis", "realtime", "data", "market_graph", "context_memory", "models",
            "curiosity", "research", "alpha", "portfolio", "risk", "execution", "treasury",
            "learning", "control", "observability", "operator_gui", "recovery",
        ],
        "files": source_files,
    }
    (ROOT / "PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    hashes = {}
    for rel, p in included_files(include_generated=True):
        if rel.name == "FILE_HASHES.json":
            continue
        hashes[str(rel)] = sha256(p)
    (ROOT / "FILE_HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")

    archive = OUT_DIR / f"Kronos_Capital_OS_Full_v{version}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, p in included_files(include_generated=True):
            z.write(p, Path("kronos_capital_os") / rel)
    digest = sha256(archive)
    checksum = OUT_DIR / f"Kronos_Capital_OS_Full_v{version}.sha256"
    checksum.write_text(f"{digest}  {archive.name}\n")
    (ROOT / "RELEASE_SHA256.txt").write_text(f"{digest}  {archive.name}\n")
    print(json.dumps({"archive": str(archive), "sha256": digest, "source_files": len(source_files), "archive_files": len(zipfile.ZipFile(archive).namelist())}, indent=2))


if __name__ == "__main__":
    main()
