from fastapi import FastAPI, Header
from typing import Optional

from service import analyze_stock, walk_forward_validate
from models import (
    AnalyzeRequest,
    StandardAgentData,
    StandardAgentResponse,
    Action,
    WalkForwardRequest,
    WalkForwardReport,
)

app = FastAPI(
    title="Technical Analysis Agent",
    description="An API for performing technical analysis on stock tickers, conforming to the Orchestrator's canonical schema.",
    version="1.3.0",
)


@app.post("/analyze", summary="Analyze a stock ticker for the Orchestrator", tags=["Analysis"], response_model=StandardAgentResponse[StandardAgentData])
def analyze_ticker_endpoint(request: AnalyzeRequest, x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")):
    service_result = analyze_stock(ticker=request.ticker, timeframe=request.timeframe, correlation_id=x_correlation_id)
    raw_data = service_result["data"]
    analysis_data = StandardAgentData(
        action=Action(raw_data["action"].lower()),
        confidence_score=raw_data["confidence_score"],
        reason=raw_data["reason"],
        current_price=raw_data.get("current_price"),
        indicators=raw_data.get("indicators"),
    )
    return StandardAgentResponse(status=service_result["status"], agent_type="technical", version="1.3.0", data=analysis_data, error=service_result.get("error"))


@app.post("/validate/walk-forward", summary="Run walk-forward validation", tags=["Validation"], response_model=StandardAgentResponse[WalkForwardReport])
def walk_forward_validation_endpoint(request: WalkForwardRequest):
    try:
        report = walk_forward_validate(
            ticker=request.ticker,
            timeframe=request.timeframe,
            min_train_bars=request.min_train_bars,
            test_bars=request.test_bars,
            step_bars=request.step_bars,
        )
        return StandardAgentResponse(status="success", agent_type="technical", version="1.3.0", data=WalkForwardReport(**report), error=None)
    except Exception as exc:
        return StandardAgentResponse(status="error", agent_type="technical", version="1.3.0", data=None, error={"code": "WALK_FORWARD_VALIDATION_FAILED", "message": str(exc), "retryable": True})


@app.get("/health", summary="Health Check", tags=["Health"], response_model=StandardAgentResponse[dict])
def health_check():
    return StandardAgentResponse(status="success", agent_type="technical", version="1.3.0", data={"status": "ok", "confidence_cap": 0.80, "walk_forward_endpoint": "/validate/walk-forward"})


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Technical Analysis Agent is running."}
