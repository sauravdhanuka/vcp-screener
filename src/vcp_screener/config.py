"""Application configuration using Pydantic settings.

Optimized config based on parameter sweep across 6 market periods (2022-2026).
Best config: G3 (Fast SMA + Wide Trail + Breakout Confirmation)
Avg return: +18.2% per period | Sharpe: 1.55 | Profit Factor: 4.24
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = project_root / "data"
    db_path: Path = data_dir / "vcp_screener.db"

    # Database
    db_url: str = ""

    # Data fetching
    batch_size: int = 50
    batch_delay_seconds: float = 2.0
    history_period: str = "5y"

    # Pre-filter
    min_price: float = 50.0
    max_price: float = 0  # 0 = no cap
    min_avg_volume: int = 100_000
    min_trading_days: int = 200

    # Relative Strength weights (recency-biased for Indian market)
    rs_weight_3m: float = 0.50
    rs_weight_6m: float = 0.25
    rs_weight_9m: float = 0.15
    rs_weight_12m: float = 0.10

    # Trend Template (fast SMAs for Indian mid/small caps)
    sma_short: int = 20
    sma_mid: int = 50
    sma_long: int = 100
    min_above_52w_low_pct: float = 30.0
    max_below_52w_high_pct: float = 25.0
    min_rs_percentile: float = 70.0
    sma_long_trend_days: int = 22

    # VCP Detection
    swing_order: int = 5
    min_base_correction_pct: float = 10.0
    min_contractions: int = 2
    max_contractions: int = 6

    # Breakout Confirmation
    breakout_volume_mult: float = 1.3  # 1.3x avg volume on breakout day
    breakout_watchlist_expiry_days: int = 20

    # Portfolio (optimized for Rs 1 lakh, G3 config)
    account_size: float = 100_000.0
    risk_per_trade_pct: float = 2.5
    max_positions: int = 5
    default_stop_loss_pct: float = 10.0
    breakeven_trigger_pct: float = 15.0
    trailing_stop_trigger_pct: float = 30.0  # Wide: let winners run
    trailing_stop_pct: float = 12.0          # Wide trail

    # Telegram Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scheduler
    screen_time: str = "16:15"

    # Top N results
    top_n: int = 50

    model_config = {"env_prefix": "VCP_"}

    def model_post_init(self, __context):
        # self.data_dir.mkdir(parents=True, exist_ok=True)
        import tempfile
        try:
            self.data_dir.mkdir(parents=True,exist_ok = True)
            test_file = self.data_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except(PermissionError,OSError):
            self.data_dir = Path(tempfile.gettempdir())
            self.data_dir.mkdir(parents=True,exist_ok=True)
            self.db_path = self.data_dir / "vcp_screener.db"
        if not self.db_url:
            self.db_url = f"sqlite:///{self.db_path}"


settings = Settings()
