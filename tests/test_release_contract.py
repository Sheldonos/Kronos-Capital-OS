from pathlib import Path
import tomllib
from kcos import __version__
from kcos.config import Settings
from kcos.risk_kernel import RiskKernel


def test_release_version_and_six_second_contract():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    assert version == __version__
    cfg = Settings(_env_file=None)
    assert cfg.heartbeat_seconds <= 6
    assert cfg.max_decision_staleness_seconds <= 6
    assert RiskKernel.HARD_CEILINGS["max_risk_per_trade_pct"] <= 2
