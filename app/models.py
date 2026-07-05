from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Literal, Optional, TypeVar, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

T = TypeVar('T')

TECHNICAL_AGENT_TYPE = "technical"
TECHNICAL_AGENT_VERSION = "1.3.0"
SCHEMA_VERSION = "1.0"


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Indicators(BaseModel):
    """Defines the structure for the technical indicators data."""
    trend: str
    rsi: float
    macd_line: float
    macd_signal: float
    atr: Optional[float] = None
    atr_percent: Optional[float] = None
    atr_stop_long: Optional[float] = None
    atr_stop_short: Optional[float] = None
    swing_low: Optional[float] = None
    swing_high: Optional[float] = None
    stop_loss: Optional[float] = None
    stop_method: Optional[str] = None
    volatility_regime: Optional[str] = None
    timeframe: Optional[str] = None
    confidence_cap: Optional[float] = None
    raw_confidence_score: Optional[float] = None
    validation_status: Optional[str] = None
    walk_forward_passed: Optional[bool] = None


class StandardAgentData(BaseModel):
    """
    Defines the canonical data structure for the analysis result.
    This model is used for both success and business logic failures.
    """
    action: Action
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reason: str
    current_price: Optional[float] = None
    indicators: Optional[Indicators] = None


class StandardAgentResponse(BaseModel, Generic[T]):
    """The final response schema expected by the Orchestrator."""
    status: Literal["success", "error"]
    agent_type: str = TECHNICAL_AGENT_TYPE
    version: str = TECHNICAL_AGENT_VERSION
    schema_version: str = SCHEMA_VERSION
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    data: Optional[T] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[dict] = None
    confidence_score: Optional[float] = None

    @field_validator("schema_version")
    @classmethod
    def schema_version_must_be_semantic(cls, value: str) -> str:
        parts = value.split(".")
        if not all(part.isdigit() for part in parts):
            raise ValueError('Schema version must be in semantic format (e.g., "1.0")')
        return value


class AnalyzeRequest(BaseModel):
    """Defines the structure for the incoming request body."""
    ticker: str = Field(..., description="The stock ticker symbol to be analyzed.", example="AOT.BK")
    timeframe: str = Field("1d", description="Candle timeframe such as 1d, 1h, 30m, or 15m.", example="1d")


class WalkForwardRequest(BaseModel):
    ticker: str = Field(..., example="AAPL")
    timeframe: str = Field("1d", example="1d")
    min_train_bars: int = Field(180, ge=60)
    test_bars: int = Field(30, ge=5)
    step_bars: int = Field(30, ge=5)


class WalkForwardWindow(BaseModel):
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe: float
    passed: bool


class WalkForwardReport(BaseModel):
    ticker: str
    timeframe: str
    windows: int
    avg_win_rate: float
    avg_profit_factor: float
    avg_max_drawdown: float
    avg_sharpe: float
    passed: bool
    confidence_cap: float
    criteria: Dict[str, Any]
    window_results: List[WalkForwardWindow]
