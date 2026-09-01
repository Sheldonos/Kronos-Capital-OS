from pathlib import Path
from kcos.runtime_config import RuntimeConfigStore


def test_runtime_state_and_secrets_survive_restart(tmp_path: Path):
    store = RuntimeConfigStore(tmp_path)
    saved = store.complete_genesis(
        {"owner": {"initial_capital": 2500}, "connectors": {"databento": {"enabled": True}}},
        {"databento_api_key": "unit-test-secret"},
    )
    assert saved["genesis_complete"] is True
    assert saved["owner"]["initial_capital"] == 2500
    assert "unit-test-secret" not in store.state_path.read_text()
    restarted = RuntimeConfigStore(tmp_path)
    assert restarted.load()["connectors"]["databento"]["enabled"] is True
    assert restarted.vault.get("databento_api_key") == "unit-test-secret"
    assert restarted.generate_admin_token() == restarted.generate_admin_token()
