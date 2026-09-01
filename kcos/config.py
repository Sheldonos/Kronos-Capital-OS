from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.runtime"), extra="ignore")

    environment: str = "development"
    kcos_instance_id: str = "kcos-01"
    runtime_dir: str = ".kcos/runtime"
    heartbeat_seconds: float = 6.0
    max_decision_staleness_seconds: float = 6.0
    max_concurrent_decisions: int = 16
    live_trading_enabled: bool = False
    auto_graduate_to_live: bool = False
    initial_capital: float = 1000.0
    base_currency: str = "USD"
    owner_jurisdiction: str = "US"

    database_url: str = "postgresql://kcos:kcos@localhost:5432/kcos"
    redis_url: str = "redis://localhost:6379/0"
    alert_webhook_url: str | None = None
    require_admin_token_remote: bool = True

    kronos_enabled: bool = True
    kronos_model: str = "NeoQuasar/Kronos-base"
    kronos_tokenizer: str = "NeoQuasar/Kronos-Tokenizer-base"
    kronos_device: str = "cpu"
    kronos_min_bars: int = 64
    kronos_interval_seconds: float = 60.0

    databento_api_key: str | None = None
    databento_dataset: str | None = None
    databento_schema: str = "trades"
    databento_symbols: str = ""
    fred_api_key: str | None = None
    sec_user_agent: str = "KCOS/1.0 owner@example.com"

    ibkr_enabled: bool = False
    ibkr_base_url: str = "https://localhost:5000/v1/api"
    ibkr_account_id: str | None = None
    ibkr_bearer_token: str | None = None
    ibkr_verify_tls: bool = False
    ibkr_instruments: str = ""

    coinbase_enabled: bool = False
    coinbase_api_key_name: str | None = None
    coinbase_api_private_key: str | None = None
    coinbase_portfolio_id: str | None = None
    coinbase_symbols: str = "BTC-USD"

    oanda_enabled: bool = False
    oanda_base_url: str = "https://api-fxtrade.oanda.com"
    oanda_stream_url: str = "https://stream-fxtrade.oanda.com"
    oanda_account_id: str | None = None
    oanda_access_token: str | None = None
    oanda_symbols: str = "EUR_USD"

    max_risk_per_trade_pct: float = 0.50
    max_aggregate_open_risk_pct: float = 2.0
    max_daily_loss_pct: float = 1.0
    max_weekly_loss_pct: float = 3.0
    hard_drawdown_stop_pct: float = 10.0
    max_gross_leverage: float = 1.0
    max_single_asset_notional_pct: float = 20.0
    max_venue_exposure_pct: float = 50.0
    min_signal_confidence: float = 0.60

    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None


settings = Settings()
