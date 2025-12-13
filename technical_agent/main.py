
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from pydantic import BaseModel

# Import the business logic from service.py
from service import (
    analyze_stock,
    TickerNotFound,
    AnalysisError,
)

app = FastAPI(
    title="Technical Analysis Agent",
    description="An API for performing technical analysis on stock tickers.",
    version="1.0.0",
)

class AnalyzeRequest(BaseModel):
    ticker: str

@app.post("/analyze",
         summary="Analyze a stock ticker",
         tags=["Analysis"])
def analyze_ticker_endpoint(request: AnalyzeRequest):
    """
    Analyzes a stock ticker and returns technical analysis indicators and a
    trading signal, conforming to the Orchestrator's expected schema.
    """
    try:
        analysis_data = analyze_stock(request.ticker)

        # Construct the standardized success response for the Orchestrator
        response_payload = {
            "status": "success",
            "agent_type": "technical",
            "ticker": request.ticker,
            "data": analysis_data
        }
        return JSONResponse(content=response_payload)

    except TickerNotFound as e:
        # Handle cases where the ticker is not found
        raise HTTPException(status_code=404, detail=str(e))

    except AnalysisError as e:
        # Handle cases where analysis cannot be performed
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        # Handle any other unexpected errors
        raise HTTPException(status_code=500,
                            detail=f"An internal error occurred: {e}")


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Technical Analysis Agent is running."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
