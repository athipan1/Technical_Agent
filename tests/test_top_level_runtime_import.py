import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_standard_agent_data_builds_evidence_in_docker_top_level_import_mode():
    script = """
from models import StandardAgentData

result = StandardAgentData(
    action="buy",
    confidence_score=0.75,
    reason="runtime import regression",
    current_price=108.0,
    indicators={
        "trend": "Uptrend",
        "rsi": 62.0,
        "macd_line": 2.0,
        "macd_signal": 1.0,
        "atr": 2.5,
        "atr_percent": 0.025,
        "swing_low": 90.0,
        "swing_high": 110.0,
        "timeframe": "1d",
    },
)

assert result.technical_evidence is not None
assert result.raw_scores["candidate_technical_max_points"] == 4
assert result.technical_evidence.provenance["candidate_scorecard"]["scope"] == "technical"
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        "Docker-style top-level import failed:\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
