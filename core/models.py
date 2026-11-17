from typing import Optional
from pydantic import BaseModel, Field

class ManualTradePayload(BaseModel):
    ticker: str
    action: str  # "buy", "sell", "short", "cover", "close"
    amount_type: Optional[str] = "max"
    percent: Optional[int] = 100
    pct: Optional[int] = None
    amount: Optional[str] = None
    is_max: Optional[bool] = None

class SettingsPayload(BaseModel):
    max_positions: int = Field(default=5, ge=1, le=15)
    stop_loss_enabled: bool = True
    stop_loss_pct: float = Field(default=15.0, ge=0.0, le=100.0)
    take_profit_enabled: bool = True
    min_profit_pct: float = Field(default=6.0, ge=0.0, le=100.0)
    auto_time_limit_hours: float = Field(default=0.0, ge=0.0, le=48.0)
    tech_target_x: float = Field(default=16.0, ge=10.0, le=60.0)
    max_alloc_pct: float = Field(default=40.0, ge=5.0, le=100.0)
    background_tracking: bool = False
    close_to_tray: bool = True
    theme: str = "dark"

class PresetPayload(BaseModel):
    preset: str
