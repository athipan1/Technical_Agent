
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse

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


class TickerRequest(BaseModel):
    """Defines the shape of the request body for the /analyze endpoint."""
    ticker: str


@app.post("/analyze",
          summary="Analyze a stock ticker",
          tags=["Analysis"])
def analyze_ticker_endpoint(request: TickerRequest):
    """
    Analyzes a stock ticker and returns technical analysis indicators and a
    trading signal.
    """
    try:
        analysis_data = analyze_stock(request.ticker)

        # Construct the response in the format expected by the Orchestrator
        response_payload = {
            "agent_type": "technical",
            "ticker": request.ticker.upper(),
            "status": "success",
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
    # Correct the port to 8002 to match docker-compose
    uvicorn.run(app, host="0.0.0.0", port=8002)
