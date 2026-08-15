import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")

TECHNICAL_AGENT_TYPE = "technical"
TECHNICAL_AGENT_VERSION = "1.6.0"
TECHNICAL_EVIDENCE_VERSION = "technical-evidence-v1"
LIQUIDITY_EVIDENCE_VERSION = "liquidity-evidence-v1"
SCHEMA_VERSION = "1.0"
SUPPORTED_TIMEFRAMES = ("1d", "1h", "30m", "15m")


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


class DataQualityReport(BaseModel):
    """Fail-closed quality assessment for market data and indicators."""

    status: Literal["complete", "partial", "insufficient"]
    completeness_score: float = Field(ge=0.0, le=1.0)
    timeframe: Optional[str] = None
    bars_available: int = Field(ge=0)
    minimum_bars_required: int = Field(ge=1)
    latest_observed_at: Optional[datetime] = None
    fresh: Optional[bool] = None
    freshness_max_age_seconds: Optional[int] = Field(default=None, ge=0)
    missing_fields: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class LiquidityEvidenceContract(BaseModel):
    """Versioned, non-binding market-liquidity evidence for Manager_Agent."""

    evidence_version: str = LIQUIDITY_EVIDENCE_VERSION
    evidence_status: Literal["complete", "partial", "unavailable"]
    evidence_completeness_score: float = Field(ge=0.0, le=1.0)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    available_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    evidence_reasons: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


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


class ProfitPolicyTechnicalContext(BaseModel):
    """Versioned technical inputs for Manager-owned adaptive profit policy."""

    context_version: str = "profit-technical-context.v1"
    atr_pct: Optional[float] = Field(default=None, ge=0.0)
    trend_strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    volume_strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    observed_at: Optional[datetime] = None
    evidence_status: Literal[
        "complete",
        "partial",
        "insufficient",
        "unavailable",
    ]
    source: Literal["technical-agent"] = "technical-agent"


class StandardAgentData(BaseModel):
    """Canonical technical-analysis result consumed by Manager_Agent."""

    action: Action
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reason: str
    current_price: Optional[float] = None
    indicators: Optional[Indicators] = None
    data_quality: Optional[DataQualityReport] = None
    liquidity_evidence: Optional[LiquidityEvidenceContract] = None
    technical_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    raw_scores: Dict[str, Any] = Field(default_factory=dict)
    technical_evidence: Optional[TechnicalEvidenceContract] = None
    profit_policy_context: Optional[ProfitPolicyTechnicalContext] = None
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
        if self.indicators is None:
            evidence = {
                "evidence_version": TECHNICAL_EVIDENCE_VERSION,
                "evidence_status": "insufficient",
                "evidence_completeness_score": 0.0,
                "raw_scores": {},
                "metrics": {},
                "available_fields": [],
                "missing_fields": [
                    "technical_score",
                    "trend_score",
                    "momentum_score",
                    "relative_strength_score",
                    "indicator_score",
                    "technical_vote_score",
                    "volatility_score",
                    "breakout_ratio",
                    "volume_ratio",
                    "current_price",
                    "support_level",
                    "resistance_level",
                    "timeframe",
                ],
                "evidence_reasons": ["technical_indicators_unavailable"],
                "provenance": {
                    "evidence_source": "unavailable",
                    "validation_status": "unavailable",
                    "liquidity_evidence_version": (
                        self.liquidity_evidence.evidence_version
                        if self.liquidity_evidence
                        else None
                    ),
                },
                "strategy_bucket_hint": None,
                "bucket_decision_authority": "manager",
                "manager_decision_required": True,
            }
        else:
            try:
                from .technical_evidence import build_technical_evidence
            except ImportError:
                from technical_evidence import build_technical_evidence

            evidence = build_technical_evidence(
                action=self.action.value,
                confidence_score=self.confidence_score,
                current_price=self.current_price,
                indicators=self.indicators,
                liquidity_evidence=self.liquidity_evidence,
            )

        if self.data_quality is not None:
            quality_status = self.data_quality.status
            evidence["provenance"]["data_quality_status"] = quality_status
            evidence["provenance"]["data_quality_completeness_score"] = (
                self.data_quality.completeness_score
            )
            if quality_status == "insufficient":
                evidence["evidence_status"] = "insufficient"
                evidence["evidence_reasons"].append(
                    "data_quality_gate:insufficient"
                )
            elif (
                quality_status == "partial"
                and evidence["evidence_status"] == "complete"
            ):
                evidence["evidence_status"] = "partial"
                evidence["evidence_reasons"].append(
                    "data_quality_gate:partial"
                )
            evidence["evidence_completeness_score"] = min(
                float(evidence["evidence_completeness_score"]),
                self.data_quality.completeness_score,
            )

        self.technical_evidence = TechnicalEvidenceContract.model_validate(
            evidence
        )
        try:
            from .profit_policy_context import build_profit_policy_context
        except ImportError:
            from profit_policy_context import build_profit_policy_context

        self.profit_policy_context = ProfitPolicyTechnicalContext.model_validate(
            build_profit_policy_context(
                technical_evidence=evidence,
                liquidity_evidence=self.liquidity_evidence,
            )
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
    """Strict request contract with compatibility fields for Manager_Agent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="The stock ticker symbol to be analyzed.",
        examples=["AOT.BK"],
    )
    timeframe: Literal["1d", "1h", "30m", "15m"] = Field(
        "1d",
        description="Candle timeframe. Unsupported values are rejected.",
        examples=["1d"],
    )
    period: Optional[str] = Field(
        default=None,
        exclude=True,
        description=(
            "Deprecated Manager_Agent compatibility field. It does not alter "
            "the candle timeframe."
        ),
    )
    account_id: Optional[Union[int, str]] = Field(
        default=None,
        exclude=True,
        description="Compatibility field accepted from Manager_Agent.",
    )

    @field_validator("ticker")
    @classmethod
    def normalize_and_validate_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=_-]{0,31}", ticker):
            raise ValueError("ticker contains unsupported characters")
        return ticker


class WalkForwardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ticker: str = Field(..., examples=["AAPL"])
    timeframe: Literal["1d", "1h", "30m", "15m"] = Field(
        "1d",
        examples=["1d"],
    )
    min_train_bars: int = Field(180, ge=60)
    test_bars: int = Field(30, ge=5)
    step_bars: int = Field(30, ge=5)

    @field_validator("ticker")
    @classmethod
    def normalize_walk_forward_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=_-]{0,31}", ticker):
            raise ValueError("ticker contains unsupported characters")
        return ticker


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
