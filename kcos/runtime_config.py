from __future__ import annotations

import json
import os
import secrets
from copy import deepcopy
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


SECRET_FIELDS = {
    "ibkr_bearer_token",
    "coinbase_api_key_name",
    "coinbase_api_private_key",
    "oanda_access_token",
    "databento_api_key",
    "fred_api_key",
    "llm_api_key",
    "alert_webhook_url",
}

DEFAULT_DESIRED_STATE: dict[str, Any] = {
    "schema_version": 1,
    "revision": 0,
    "genesis_complete": False,
    "owner": {
        "jurisdiction": "US",
        "base_currency": "USD",
        "initial_capital": 1000.0,
    },
    "autonomy": {
        "live_trading_enabled": False,
        "auto_graduate_to_live": False,
        "max_decision_staleness_seconds": 6.0,
        "heartbeat_seconds": 6.0,
    },
    "risk": {
        "max_risk_per_trade_pct": 0.50,
        "max_aggregate_open_risk_pct": 2.0,
        "max_daily_loss_pct": 1.0,
        "max_weekly_loss_pct": 3.0,
        "hard_drawdown_stop_pct": 10.0,
        "max_gross_leverage": 1.0,
        "max_single_asset_notional_pct": 20.0,
        "max_venue_exposure_pct": 50.0,
        "min_signal_confidence": 0.60,
    },
    "connectors": {
        "ibkr": {"enabled": False, "base_url": "https://localhost:5000/v1/api", "account_id": "", "verify_tls": False, "instruments": ""},
        "coinbase": {"enabled": False, "portfolio_id": "", "symbols": "BTC-USD"},
        "oanda": {
            "enabled": False,
            "base_url": "https://api-fxtrade.oanda.com",
            "stream_url": "https://stream-fxtrade.oanda.com",
            "account_id": "",
            "symbols": "EUR_USD",
        },
        "databento": {"enabled": False, "dataset": "", "schema": "trades", "symbols": ""},
        "fred": {"enabled": False},
        "sec_edgar": {"enabled": True, "user_agent": "KCOS/1.0 owner@example.com"},
        "reasoning": {"enabled": False, "base_url": "", "model": ""},
    },
    "notifications": {"webhook_enabled": False},
    "universe": {"symbols": []},
}


class LocalSecretVault:
    """Encrypted local secret backend for first-run simplicity.

    Production deployments can replace this backend with Vault/KMS without changing
    the desired-state contract. The key and encrypted blob live on a persistent volume.
    """

    def __init__(self, root: Path):
        self.root = root
        self.key_path = root / "local_vault.key"
        self.data_path = root / "local_vault.enc"
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(self) -> bytes:
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            os.chmod(self.key_path, 0o600)
        return self.key_path.read_bytes().strip()

    def _read(self) -> dict[str, str]:
        if not self.data_path.exists():
            return {}
        try:
            raw = Fernet(self._key()).decrypt(self.data_path.read_bytes())
            return json.loads(raw.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError) as exc:
            raise RuntimeError("KCOS local secret vault cannot be decrypted") from exc

    def _write(self, data: dict[str, str]) -> None:
        blob = Fernet(self._key()).encrypt(json.dumps(data, sort_keys=True).encode("utf-8"))
        tmp = self.data_path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        os.chmod(tmp, 0o600)
        tmp.replace(self.data_path)

    def set_many(self, values: dict[str, str | None]) -> None:
        data = self._read()
        for key, value in values.items():
            if value is None:
                continue
            value = str(value)
            if value == "":
                data.pop(key, None)
            else:
                data[key] = value
        self._write(data)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._read().get(key, default)

    def presence(self) -> dict[str, bool]:
        return {k: bool(v) for k, v in self._read().items()}


class RuntimeConfigStore:
    """Authoritative persisted desired state, independent of agent/model memory."""

    def __init__(self, root: str | Path | None = None):
        base = root or os.environ.get("KCOS_RUNTIME_DIR") or ("/app/runtime" if Path("/app").exists() and os.access("/app", os.W_OK) else ".kcos/runtime")
        self.root = Path(base)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "desired_state.json"
        self.vault = LocalSecretVault(self.root)
        self.bootstrap()

    def bootstrap(self) -> None:
        if not self.state_path.exists():
            self._atomic_json(DEFAULT_DESIRED_STATE)

    def _atomic_json(self, value: dict[str, Any]) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.state_path)

    def load(self) -> dict[str, Any]:
        self.bootstrap()
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    @property
    def revision(self) -> int:
        return int(self.load().get("revision", 0))

    def save(self, desired: dict[str, Any], secrets_payload: dict[str, str | None] | None = None) -> dict[str, Any]:
        current = self.load()
        merged = self._deep_merge(current, desired)
        merged["schema_version"] = 1
        merged["revision"] = int(current.get("revision", 0)) + 1
        if secrets_payload:
            self.vault.set_many({k: v for k, v in secrets_payload.items() if k in SECRET_FIELDS})
        self._atomic_json(merged)
        return self.redacted(merged)

    def complete_genesis(self, desired: dict[str, Any], secrets_payload: dict[str, str | None] | None = None) -> dict[str, Any]:
        desired = deepcopy(desired)
        desired["genesis_complete"] = True
        return self.save(desired, secrets_payload)

    def redacted(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        out = deepcopy(state or self.load())
        out["secret_presence"] = self.vault.presence()
        return out

    @staticmethod
    def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        out = deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = RuntimeConfigStore._deep_merge(out[key], value)
            else:
                out[key] = deepcopy(value)
        return out

    def effective_flat(self) -> dict[str, Any]:
        s = self.load()
        o, a, r = s["owner"], s["autonomy"], s["risk"]
        c = s["connectors"]
        flat: dict[str, Any] = {
            "owner_jurisdiction": o.get("jurisdiction", "US"),
            "base_currency": o.get("base_currency", "USD"),
            "initial_capital": float(o.get("initial_capital", 1000)),
            "live_trading_enabled": bool(a.get("live_trading_enabled", False)),
            "auto_graduate_to_live": bool(a.get("auto_graduate_to_live", False)),
            "max_decision_staleness_seconds": float(a.get("max_decision_staleness_seconds", 6)),
            "heartbeat_seconds": float(a.get("heartbeat_seconds", 6)),
            **{k: v for k, v in r.items()},
            "ibkr_enabled": bool(c["ibkr"].get("enabled", False)),
            "ibkr_base_url": c["ibkr"].get("base_url"),
            "ibkr_account_id": c["ibkr"].get("account_id") or None,
            "ibkr_verify_tls": bool(c["ibkr"].get("verify_tls", False)),
            "ibkr_instruments": c["ibkr"].get("instruments", ""),
            "coinbase_enabled": bool(c["coinbase"].get("enabled", False)),
            "coinbase_portfolio_id": c["coinbase"].get("portfolio_id") or None,
            "coinbase_symbols": c["coinbase"].get("symbols", "BTC-USD"),
            "oanda_enabled": bool(c["oanda"].get("enabled", False)),
            "oanda_base_url": c["oanda"].get("base_url"),
            "oanda_stream_url": c["oanda"].get("stream_url"),
            "oanda_account_id": c["oanda"].get("account_id") or None,
            "oanda_symbols": c["oanda"].get("symbols", "EUR_USD"),
            "databento_dataset": c["databento"].get("dataset") or None,
            "databento_schema": c["databento"].get("schema", "trades"),
            "databento_symbols": c["databento"].get("symbols", ""),
            "sec_user_agent": c["sec_edgar"].get("user_agent", "KCOS/1.0 owner@example.com"),
            "llm_api_base": c["reasoning"].get("base_url") or None,
            "llm_model": c["reasoning"].get("model") or None,
        }
        for key in SECRET_FIELDS:
            flat[key] = self.vault.get(key)
        return flat

    def apply_to(self, settings_obj: Any) -> int:
        for key, value in self.effective_flat().items():
            if hasattr(settings_obj, key) and value is not None:
                setattr(settings_obj, key, value)
        return self.revision

    def generate_admin_token(self) -> str:
        existing = self.vault.get("admin_token")
        if existing:
            return existing
        token = secrets.token_urlsafe(32)
        # admin_token is a system-generated key, not a user-supplied credential,
        # so it is written directly rather than through set_many / SECRET_FIELDS.
        data = self.vault._read()
        data["admin_token"] = token
        self.vault._write(data)
        return token
