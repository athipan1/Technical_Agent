# Technical Analysis Agent

This project provides a FastAPI-based API for performing technical analysis on stock tickers. It calculates key indicators like SMA, RSI, and MACD to generate a trading signal (buy, sell, or hold).

## Project Structure

- `app/`: Contains the main application code.
  - `main.py`: FastAPI application, defines API endpoints and Pydantic models.
  - `service.py`: Core business logic for stock analysis.
- `Dockerfile`: Defines the Docker container for deploying the application.
- `requirements.txt`: Lists the Python dependencies for the project.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

### Running with Docker

1.  Build the Docker image:
    ```bash
    sudo docker build -t technical-agent .
    ```

2.  Run the Docker container:
    ```bash
    sudo docker run -d -p 8002:8002 --name technical-agent-container technical-agent
    ```

The API will be available at `http://localhost:8002`.

## API Usage

### POST /analyze

Analyzes a stock ticker and returns technical analysis data.

-   **URL:** `/analyze`
-   **Method:** `POST`
-   **Request Body:**
    ```json
    {
      "ticker": "AOT.BK"
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
      "status": "success",
      "agent_type": "technical",
      "ticker": "AOT.BK",
      "data": {
        "current_price": 64.75,
        "action": "hold",
        "confidence_score": 0.5,
        "indicators": {
          "trend": "Uptrend",
          "rsi": 64.38,
          "macd_line": 2.91,
          "macd_signal": 2.08
        }
      }
    }
    ```
-   **Error Responses:**
    -   `404 Not Found`: If the ticker does not exist.
    -   `422 Unprocessable Entity`: If analysis cannot be performed (e.g., insufficient data).
    -   `500 Internal Server Error`: For any other unexpected errors.
