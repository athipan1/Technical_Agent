
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

# Import the business logic and custom exceptions from the service module
from .service import (
    analyze_stock,
    TickerNotFound,
    AnalysisError,
)

# --- API Metadata ---
app = FastAPI(
    title="Technical Analysis Agent",
    description="An API for performing technical analysis on stock tickers.",
    version="1.0.0",
)


# --- Pydantic Models for Data Structuring ---

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
    """Defines the structure for the core analysis data."""
    current_price: float
    action: Literal["buy", "sell", "hold"]
    confidence_score: float
    indicators: Indicators


class SuccessResponse(BaseModel):
    """Defines the standardized success response schema."""
    status: Literal["success"]
    agent_type: Literal["technical"]
    ticker: str
    data: AnalysisData


# --- API Endpoints ---

@app.post(
    "/analyze",
    summary="Analyze a stock ticker",
    tags=["Analysis"],
    response_model=SuccessResponse
)
def analyze_ticker_endpoint(request: AnalyzeRequest):
    """
    Analyzes a stock ticker and returns technical analysis indicators and a
    trading signal, conforming to the Orchestrator's expected schema.
    """
    try:
        # Call the core business logic from the service module
        analysis_data = analyze_stock(request.ticker)

        # Construct the standardized success response using Pydantic models
        response_payload = SuccessResponse(
            status="success",
            agent_type="technical",
            ticker=request.ticker,
            data=analysis_data
        )
        return response_payload

    except TickerNotFound as e:
        # Handle cases where the ticker is not found with a 404 error
        raise HTTPException(status_code=404, detail=str(e))

    except AnalysisError as e:
        # Handle cases where analysis cannot be performed with a 422 error
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        # Handle any other unexpected errors with a 500 internal server error
        raise HTTPException(status_code=500,
                            detail=f"An internal error occurred: {e}")


@app.get("/", include_in_schema=False)
def root():
    """A simple root endpoint to confirm the API is running."""
    return {"message": "Technical Analysis Agent is running."}
