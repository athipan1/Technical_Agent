
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

# Import the business logic from service.py
from technical_agent.service import (
    analyze_stock,
    TickerNotFound,
    AnalysisError,
)

app = FastAPI(
    title="Technical Analysis Agent",
    description="An API for performing technical analysis on stock tickers.",
    version="1.0.0",
)


@app.get("/analyze/{ticker}",
         summary="Analyze a stock ticker",
         tags=["Analysis"])
def analyze_ticker_endpoint(ticker: str):
    """
    Analyzes a stock ticker and returns technical analysis indicators and a
    trading signal.
    """
    try:
        analysis_data = analyze_stock(ticker)

        # Construct the standardized success response
        response_payload = {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "technical",
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
