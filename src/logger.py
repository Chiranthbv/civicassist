"""
Audit and diagnostic logger for CivicAssist.
Ensures privacy-preserving logs without storing PII.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
AUDIT_LOG_FILE = os.path.join(LOGS_DIR, "civic_assist.log")

# Setup python logging
logger = logging.getLogger("CivicAssist")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(AUDIT_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

def log_interaction(
    session_id: str,
    user_query: str,
    detected_intent: str,
    retrieved_sources: List[Dict[str, Any]],
    confidence: str,
    weather_api_used: bool,
    response_latency: float,
    success: bool,
    error_message: str = None
):
    """
    Structured JSON log entry strictly excluding citizen personal identifiable info.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "user_query_length": len(user_query),
        "sanitized_query_preview": user_query[:120],
        "detected_intent": detected_intent,
        "source_count": len(retrieved_sources),
        "sources": [
            {"file": s.get("source_file"), "record_id": s.get("record_id"), "relevance": s.get("relevance_score")}
            for s in retrieved_sources
        ],
        "confidence": confidence,
        "weather_api_used": weather_api_used,
        "response_latency_sec": round(response_latency, 4),
        "success": success,
        "error": error_message
    }

    logger.info(json.dumps(entry))
    return entry
