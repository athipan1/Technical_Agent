from datetime import datetime
from enum import Enum
from typing import Generic, Literal, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')


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
    agent_type: str = "technical"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[T] = None
    error: Optional[dict] = None


class AnalyzeRequest(BaseModel):
    """Defines the structure for the incoming request body."""
    ticker: str = Field(..., description="The stock ticker symbol to be analyzed.", example="AOT.BK")
    timeframe: str = Field("1d", description="Candle timeframe such as 1d, 1h, 30m, or 15m.", example="1d")
