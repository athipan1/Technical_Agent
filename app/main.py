from typing import Optional

from fastapi import FastAPI, Header

try:
    from .service import analyze_stock, walk_forward_validate
    from .models import (
        Action,
        AnalyzeRequest,
        SCHEMA_VERSION,
        StandardAgentData,
        StandardAgentResponse,
        TECHNICAL_AGENT_TYPE,
        TECHNICAL_AGENT_VERSION,
        TECHNICAL_EVIDENCE_VERSION,
        WalkForwardReport,
        WalkForwardRequest,
    )
except ImportError:
    from service import analyze_stock, walk_forward_validate
    from models import (
        Action,
        AnalyzeRequest,
        SCHEMA_VERSION,
        StandardAgentData,
        StandardAgentResponse,
        TECHNICAL_AGENT_TYPE,
        TECHNICAL_AGENT_VERSION,
        TECHNICAL_EVIDENCE_VERSION,
        WalkForwardReport,
        WalkForwardRequest,
    )

app = FastAPI(
    title="Technical Analysis Agent",
    description=(
        "An API for technical analysis and non-binding evidence for "
        "Manager_Agent."
    ),
    version=TECHNICAL_AGENT_VERSION,
)


def build_response(
    status: str,
    data=None,
    error=None,
    metadata=None,
    correlation_id: Optional[str] = None,
    confidence_score=None,
):
    return StandardAgentResponse(
        status=status,
        agent_type=TECHNICAL_AGENT_TYPE,
        version=TECHNICAL_AGENT_VERSION,
        schema_version=SCHEMA_VERSION,
        correlation_id=correlation_id,
        data=data,
        metadata=metadata or {},
        error=error,
        confidence_score=confidence_score,
    )


@app.get(
    "/version",
    summary="Version Check",
    tags=["System"],
    response_model=StandardAgentResponse[dict],
)
def version_check():
    return build_response(
        status="success",
        data={
            "agent_type": TECHNICAL_AGENT_TYPE,
            "version": TECHNICAL_AGENT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "api_contract": "multi-agent-trading-api-contract",
            "evidence_version": TECHNICAL_EVIDENCE_VERSION,
        },
        metadata={
            "required_operational_endpoints": [
                "/health",
                "/ready",
                "/version",
            ],
            "bucket_decision_authority": "manager",
        },
    )


@app.get(
    "/ready",
    summary="Readiness Check",
    tags=["System"],
    response_model=StandardAgentResponse[dict],
)
def readiness_check():
    return build_response(
        status="success",
        data={
            "ready": True,
            "analysis_endpoint": "/analyze",
            "walk_forward_endpoint": "/validate/walk-forward",
            "supported_actions": ["buy", "sell", "hold"],
            "confidence_cap": 0.80,
            "evidence_version": TECHNICAL_EVIDENCE_VERSION,
            "bucket_decision_authority": "manager",
            "manager_decision_required": True,
        },
        metadata={"contract_source": "technical-agent-runtime-contract"},
    )


@app.post(
    "/analyze",
    summary="Analyze a stock ticker for the Orchestrator",
    tags=["Analysis"],
    response_model=StandardAgentResponse[StandardAgentData],
)
def analyze_ticker_endpoint(
    request: AnalyzeRequest,
    x_correlation_id: Optional[str] = Header(
        None,
        alias="X-Correlation-ID",
    ),
):
    service_result = analyze_stock(
        ticker=request.ticker,
        timeframe=request.timeframe,
        correlation_id=x_correlation_id,
    )
    raw_data = service_result["data"]
    analysis_data = StandardAgentData(
        action=Action(raw_data["action"].lower()),
        confidence_score=raw_data["confidence_score"],
        reason=raw_data["reason"],
        current_price=raw_data.get("current_price"),
        indicators=raw_data.get("indicators"),
    )
    return build_response(
        status=service_result["status"],
        data=analysis_data,
        error=service_result.get("error"),
        correlation_id=x_correlation_id,
        confidence_score=raw_data.get("confidence_score"),
        metadata={
            "evidence_version": TECHNICAL_EVIDENCE_VERSION,
            "bucket_decision_authority": "manager",
            "manager_decision_required": True,
        },
    )


@app.post(
    "/validate/walk-forward",
    summary="Run walk-forward validation",
    tags=["Validation"],
    response_model=StandardAgentResponse[WalkForwardReport],
)
def walk_forward_validation_endpoint(
    request: WalkForwardRequest,
    x_correlation_id: Optional[str] = Header(
        None,
        alias="X-Correlation-ID",
    ),
):
    try:
        report = walk_forward_validate(
            ticker=request.ticker,
            timeframe=request.timeframe,
            min_train_bars=request.min_train_bars,
            test_bars=request.test_bars,
            step_bars=request.step_bars,
        )
        return build_response(
            status="success",
            data=WalkForwardReport(**report),
            error=None,
            correlation_id=x_correlation_id,
            metadata={
                "evidence_version": TECHNICAL_EVIDENCE_VERSION,
                "validation_role": "confidence_calibration",
            },
        )
    except Exception as exc:
        return build_response(
            status="error",
            data=None,
            error={
                "code": "WALK_FORWARD_VALIDATION_FAILED",
                "message": str(exc),
                "retryable": True,
            },
            correlation_id=x_correlation_id,
            confidence_score=0.0,
        )


@app.get(
    "/health",
    summary="Health Check",
    tags=["Health"],
    response_model=StandardAgentResponse[dict],
)
def health_check():
    return build_response(
        status="success",
        data={
            "status": "ok",
            "confidence_cap": 0.80,
            "walk_forward_endpoint": "/validate/walk-forward",
            "evidence_version": TECHNICAL_EVIDENCE_VERSION,
            "bucket_decision_authority": "manager",
        },
    )


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Technical Analysis Agent is running."}
