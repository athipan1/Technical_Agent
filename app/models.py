from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

T = TypeVar("T")

TECHNICAL_AGENT_TYPE = "technical"
TECHNICAL_AGENT_VERSION = "1.4.0"
TECHNICAL_EVIDENCE_VERSION = "technical-evidence-v1"
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


class TechnicalEvidenceContract(BaseModel):
    evidence_version: str = TECHNICAL_EVIDENCE_VERSION
    evidence_status: Literal["complete", "partial", "insufficient"]
    evidence_completeness_score: float = Field(ge=0.0, le=1.0)
    raw_scores: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    available_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    evidence_reasons: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    strategy_bucket_hint: Literal[None] = None
    bucket_decision_authority: Literal["manager"] = "manager"
    manager_decision_required: bool = True


class StandardAgentData(BaseModel):
    """Canonical technical-analysis result consumed by Manager_Agent."""

    action: Action
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reason: str
    current_price: Optional[float] = None
    indicators: Optional[Indicators] = None
    technical_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    raw_scores: Dict[str, Any] = Field(default_factory=dict)
    technical_evidence: Optional[TechnicalEvidenceContract] = None
    evidence_version: str = TECHNICAL_EVIDENCE_VERSION
    evidence_status: Literal[
        "complete",
        "partial",
        "insufficient",
        "unavailable",
    ] = "unavailable"
    evidence_completeness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    strategy_bucket_hint: Literal[None] = None
    bucket_decision_authority: Literal["manager"] = "manager"
    manager_decision_required: bool = True

    @model_validator(mode="after")
    def populate_technical_evidence(self):
        from technical_evidence import build_technical_evidence

        evidence = build_technical_evidence(
            action=self.action.value,
            confidence_score=self.confidence_score,
            current_price=self.current_price,
            indicators=self.indicators,
        )
        self.technical_evidence = TechnicalEvidenceContract.model_validate(
            evidence
        )
        self.raw_scores = dict(evidence["raw_scores"])
        self.technical_score = evidence["raw_scores"].get(
            "technical_score"
        )
        self.evidence_version = evidence["evidence_version"]
        self.evidence_status = evidence["evidence_status"]
        self.evidence_completeness_score = evidence[
            "evidence_completeness_score"
        ]
        return self


class StandardAgentResponse(BaseModel, Generic[T]):
    """The final response schema expected by the Orchestrator."""

    status: Literal["success", "error"]
    agent_type: str = TECHNICAL_AGENT_TYPE
    version: str = TECHNICAL_AGENT_VERSION
    schema_version: str = SCHEMA_VERSION
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
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
            raise ValueError(
                'Schema version must be in semantic format (e.g., "1.0")'
            )
        return value


class AnalyzeRequest(BaseModel):
    """Defines the structure for the incoming request body."""

    ticker: str = Field(
        ...,
        description="The stock ticker symbol to be analyzed.",
        examples=["AOT.BK"],
    )
    timeframe: str = Field(
        "1d",
        description="Candle timeframe such as 1d, 1h, 30m, or 15m.",
        examples=["1d"],
    )


class WalkForwardRequest(BaseModel):
    ticker: str = Field(..., examples=["AAPL"])
    timeframe: str = Field("1d", examples=["1d"])
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
