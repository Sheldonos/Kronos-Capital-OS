#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TRANSIENT_PARTS = {"__pycache__", ".pytest_cache", ".git", ".mypy_cache", ".ruff_cache", ".venv", "runtime", ".kcos", "dist", "build", "wheelhouse"}


def fail(message: str) -> None:
    raise AssertionError(message)


def files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in TRANSIENT_PARTS or part.endswith(".egg-info") for part in rel.parts):
            continue
        yield rel, p


def main() -> int:
    checks: list[str] = []
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = pyproject["project"]["version"]
    init_text = (ROOT / "kcos/__init__.py").read_text()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)', init_text)
    if not m or m.group(1) != version:
        fail(f"version mismatch: pyproject={version}, kcos.__version__={m.group(1) if m else 'missing'}")
    checks.append(f"version={version}")

    required = [
        "README.md", "SECURITY.md", "LICENSE", "Dockerfile", "docker-compose.yml",
        "kcos/autonomous_runtime.py", "kcos/genesis_os.py", "kcos/runtime_config.py",
        "kcos/web/static/index.html", "kcos/web/static/app.js", "kcos/web/static/app.css",
        "kcos/risk_kernel.py", "kcos/research/worker.py", "kcos/execution/position_manager.py",
        "config/constitution.yaml", "config/promotion_gates.yaml", "db/init.sql", "UPSTREAM.lock",
    ]
    missing = [x for x in required if not (ROOT / x).exists()]
    if missing:
        fail("missing required release files: " + ", ".join(missing))
    checks.append(f"required_files={len(required)}")

    for rel, p in files():
        if p.suffix in {".yaml", ".yml"}:
            yaml.safe_load(p.read_text())
        elif p.suffix == ".json":
            json.loads(p.read_text())
    checks.append("config_parse=ok")

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose.get("services", {})
    for service in ("postgres", "redis", "runtime", "research"):
        if service not in services:
            fail(f"compose missing {service}")
    port = str((services["runtime"].get("ports") or [""])[0])
    if not port.startswith("127.0.0.1:"):
        fail("runtime GUI must bind loopback by default")
    for service in ("postgres", "redis", "runtime", "research"):
        if services[service].get("restart") != "unless-stopped":
            fail(f"{service} must restart unless-stopped")
    checks.append("compose_24_7_contract=ok")

    from kcos.config import Settings
    from kcos.risk_kernel import RiskKernel
    from kcos.runtime_config import DEFAULT_DESIRED_STATE

    cfg = Settings(_env_file=None)
    if cfg.heartbeat_seconds > 6 or cfg.max_decision_staleness_seconds > 6:
        fail("default six-second contract violated")
    auto = DEFAULT_DESIRED_STATE["autonomy"]
    if float(auto["heartbeat_seconds"]) > 6 or float(auto["max_decision_staleness_seconds"]) > 6:
        fail("desired-state six-second contract violated")
    expected_ceilings = {
        "max_risk_per_trade_pct", "max_aggregate_open_risk_pct", "hard_drawdown_stop_pct",
        "max_gross_leverage", "max_venue_exposure_pct", "max_single_asset_notional_pct",
    }
    if not expected_ceilings.issubset(RiskKernel.HARD_CEILINGS):
        fail("risk constitutional ceilings incomplete")
    checks.append("risk_constitution=ok")

    upstream = (ROOT / "UPSTREAM.lock").read_text()
    pinned = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
    if pinned not in upstream or pinned not in (ROOT / "Dockerfile").read_text():
        fail("upstream Kronos commit is not consistently pinned")
    checks.append("upstream_pin=ok")

    forbidden_names = {".env.runtime", "local_vault.key", "local_vault.enc"}
    for rel, p in files():
        if p.name in forbidden_names:
            fail(f"secret/runtime artifact present in release: {rel}")
        if p.stat().st_size > 5_000_000:
            continue
        text = p.read_text(errors="ignore")
        # Detect actual embedded private-key material or common live-token shapes, not documentation words.
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
            fail(f"private key material found in {rel}")
        if re.search(r"\bsk-[A-Za-z0-9_-]{24,}\b", text):
            fail(f"possible live API token found in {rel}")
    checks.append("secret_scan=ok")

    package_data = pyproject.get("tool", {}).get("setuptools", {}).get("package-data", {})
    if "static/*" not in package_data.get("kcos.web", []):
        fail("GUI static files are not declared as package data")
    checks.append("gui_package_data=ok")

    manifest_path = ROOT / "PACKAGE_MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("version") != version:
            fail("PACKAGE_MANIFEST version is stale")
        if manifest.get("scope") != "full-system-not-genesis-only":
            fail("PACKAGE_MANIFEST scope is not full-system")
    checks.append("manifest=ok")

    print("KCOS RELEASE AUDIT PASS")
    for item in checks:
        print(f"  ✓ {item}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"KCOS RELEASE AUDIT FAIL: {exc}", file=sys.stderr)
        raise
