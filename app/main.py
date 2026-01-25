
from datetime import datetime
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field
from typing import Literal, Optional

# Import the business logic from the service module
from service import analyze_stock

# --- API Metadata ---
app = FastAPI(
    title="Technical Analysis Agent",
    description="An API for performing technical analysis on stock tickers, "
    "conforming to the Orchestrator's canonical schema.",
    version="1.1.0",
)


# --- Pydantic Models for New Orchestrator Schema ---

class AnalyzeRequest(BaseModel):
    """Defines the structure for the incoming request body."""
    ticker: str = Field(...,
                        description="The stock ticker symbol to be analyzed.",
                        example="AOT.BK")


class Indicators(BaseModel):
    """Defines the structure for the technical indicators data."""
    trend: str
    rsi: float
    macd_line: float
    macd_signal: float


class AnalysisData(BaseModel):
    """
    Defines the canonical data structure for the analysis result.
    This model is used for both success and business logic failures.
    """
    action: Literal["buy", "sell", "hold"]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reason: str
    current_price: Optional[float] = None
    indicators: Optional[Indicators] = None


class OrchestratorResponse(BaseModel):
    """The final response schema expected by the Orchestrator."""
    status: Literal["success", "error"]
    agent_type: str = "technical"
    version: str = "1.1.0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: AnalysisData
    error: Optional[dict] = None


# --- API Endpoints ---

@app.post(
    "/analyze",
    summary="Analyze a stock ticker for the Orchestrator",
    tags=["Analysis"],
    response_model=OrchestratorResponse
)
def analyze_ticker_endpoint(
    request: AnalyzeRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
):
    """
    Analyzes a stock ticker and returns a result conforming to the
    Orchestrator's canonical schema.

    - **Receives**: A stock `ticker` and an optional `X-Correlation-ID` header.
    - **Returns**: A structured JSON response with an `action`, `confidence_score`,
      `reason`, and other relevant data.
    - **Error Handling**: Business logic errors (e.g., ticker not found) are
      handled gracefully and returned with an HTTP 200 status code,
      with the error details encoded in the `reason` field.
    """
    # The service function now handles internal errors and returns the
    # appropriate dictionary structure for both success and failure cases.
    service_result = analyze_stock(
        ticker=request.ticker,
        correlation_id=x_correlation_id
    )

    # Instantiate the Pydantic model directly.
    # Populating agent_type and version from the model defaults.
    return OrchestratorResponse(
        status=service_result["status"],
        agent_type="technical",
        version="1.1.0",
        data=service_result["data"],
        error=service_result.get("error")
    )


@app.get("/health", summary="Health Check", tags=["Health"])
def health_check():
    """Returns a 200 OK status if the service is healthy."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    """A simple root endpoint to confirm the API is running."""
    return {"message": "Technical Analysis Agent is running."}
