"""
FastAPI Backend for CivicAssist Greenfield Municipal Corporation.
Exposes RESTful endpoints for chat, knowledge base exploration, weather advisories, and system diagnostics.
"""

import os
import sys
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Ensure project root in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from src.response_generator import CivicResponseGenerator
from src.schemas import ChatResponse, ConfidenceLevel, IntentType

app = FastAPI(
    title="CivicAssist API - Greenfield Municipal Corporation",
    description="Enterprise AI-Powered FAQ and Municipal Services Assistant API",
    version="1.0.0"
)

# Enable CORS for React frontend (Vite port 5173, express port 3000, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize single instance of CivicResponseGenerator
generator = CivicResponseGenerator()

class ChatRequest(BaseModel):
    query: str = Field(..., example="When is garbage collected in Zone A?")
    session_id: str = Field(default="civicassist_default", example="civicassist_session_123")
    language: Optional[str] = Field(default="en", example="en, hi, or kn")

class ResetSessionRequest(BaseModel):
    session_id: str = Field(default="civicassist_default", example="civicassist_session_123")

@app.get("/api/health")
def health_check():
    """System health check and diagnostic inspection."""
    llm_name = generator.llm.__class__.__name__.replace("Provider", "").lower()
    return {
        "status": "healthy",
        "backend": "online",
        "rag": "ready",
        "vector_store": "ready",
        "municipal_data": "loaded",
        "llm_provider": llm_name,
        "supported_languages": ["en", "hi", "kn"],
        "weather_api": "configured" if generator.weather.is_configured() else "unconfigured (using forecast simulation)",
        "zones_loaded": len(generator.rag.get_all_waste_zones()),
        "permits_loaded": len(generator.rag.get_all_permits()),
        "events_loaded": len(generator.rag.get_all_events())
    }

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest) -> Dict[str, Any]:
    """
    Main citizen chat query endpoint.
    Performs intent detection, RAG retrieval, optional weather lookups, and response generation.
    Supports English (en), Hindi (hi), and Kannada (kn).
    """
    cleaned_query = (request.query or "").strip()
    lang = request.language or "en"
    if not cleaned_query:
        if lang == "kn":
            empty_msg = "ದಯವಿಟ್ಟು ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಸೇವೆಗಳ ಕುರಿತು ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ, ಉದಾಹರಣೆಗೆ ಕಸ ಸಂಗ್ರಹ ವೇಳಾಪಟ್ಟಿ, ಪರವಾನಗಿಗಳು ಅಥವಾ ನಗರದ ಸಾರ್ವಜನಿಕ ಕಾರ್ಯಕ್ರಮಗಳು."
        elif lang == "hi":
            empty_msg = "कृपया ग्रीनफ़ील्ड नगर निगम सेवाओं के बारे में प्रश्न पूछें, जैसे कचरा संग्रह अनुसूची, परमिट या आगामी कार्यक्रम।"
        else:
            empty_msg = "Please ask a question about Greenfield municipal services, such as waste collection schedules, permits, or upcoming city events."

        return {
            "answer": empty_msg,
            "detected_intent": "UNKNOWN",
            "confidence": "🔴 Low Confidence",
            "confidence_score": 0.0,
            "sources": [],
            "response_latency_seconds": 0.001,
            "weather_info": None,
            "clarification_needed": True,
            "session_id": request.session_id,
            "language": lang
        }

    try:
        resp = generator.process_query(cleaned_query, session_id=request.session_id, language=lang)
        return resp.to_dict()
    except Exception as e:
        # Prevent server crashes on unhandled errors; return graceful response
        if lang == "kn":
            err_msg = "ನಗರ ಪಾಲಿಕೆ ದಾಖಲೆಗಳ ಮಾಹಿತಿ ಕೋಶವನ್ನು ಸಂಪರ್ಕಿಸಲು ತಾತ್ಕಾಲಿಕ ಅಡಚಣೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಪುನಃ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಸಿಟಿ ಹಾಲ್ ಕಚೇರಿಯನ್ನು (555) 019-3000 ನಲ್ಲಿ ಸಂಪರ್ಕಿಸಿ."
        elif lang == "hi":
            err_msg = "नगर निगम रिकॉर्ड डेटाबेस तक पहुँचने में अस्थायी कठिनाई हो रही है। कृपया पुनः प्रयास करें या ग्रीनफ़ील्ड सिटी हॉल से (555) 019-3000 पर संपर्क करें।"
        else:
            err_msg = "I am experiencing temporary difficulty accessing the municipal records database. Please try again or contact Greenfield City Hall directly at (555) 019-3000."

        return {
            "answer": err_msg,
            "detected_intent": "UNKNOWN",
            "confidence": "🔴 Low Confidence",
            "confidence_score": 0.1,
            "sources": [],
            "response_latency_seconds": 0.05,
            "weather_info": None,
            "clarification_needed": False,
            "session_id": request.session_id,
            "language": lang
        }

@app.post("/api/reset-session")
def reset_session(request: ResetSessionRequest):
    """Clears conversation memory and cached context for a given citizen session."""
    generator.clear_session(request.session_id)
    return {"status": "success", "message": f"Session '{request.session_id}' cleared."}

@app.get("/api/waste-schedule")
def get_waste_schedule(zone: Optional[str] = None):
    """Retrieve waste management schedule for all zones or a specific zone."""
    if zone:
        res = generator.rag.get_waste_by_zone(zone)
        if not res:
            raise HTTPException(status_code=404, detail=f"Zone '{zone}' not found in municipal records.")
        return res
    return generator.rag.get_all_waste_zones()

@app.get("/api/waste-schedule/{zone}")
def get_waste_schedule_by_zone(zone: str):
    """Retrieve waste management schedule for a specific zone."""
    res = generator.rag.get_waste_by_zone(zone)
    if not res:
        raise HTTPException(status_code=404, detail=f"Zone '{zone}' not found in municipal records.")
    return res

@app.get("/api/permits")
def get_permits():
    """Retrieve full registry of municipal permits and licensing requirements."""
    return generator.rag.get_all_permits()

@app.get("/api/events")
def get_events():
    """Retrieve verified city public events schedule."""
    return generator.rag.get_all_events()

@app.get("/api/weather/{event_name}")
def get_weather_for_event(event_name: str):
    """Retrieve meteorological advisory for a specific city event."""
    event = generator.rag.get_event_by_name(event_name)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event '{event_name}' not found in city event records.")

    advisory = generator.weather.get_weather_for_event(
        event_name=event.get("name", event_name),
        event_date=event.get("date", "2026-10-12"),
        location=event.get("location", "Greenfield"),
        is_outdoor=event.get("outdoor", True)
    )
    return advisory.to_dict()

@app.get("/api/evaluation-metrics")
def get_evaluation_metrics():
    """Retrieve 30-query synthetic benchmark results and performance metrics."""
    eval_path = os.path.join(ROOT_DIR, "evaluation", "results.json")
    if os.path.exists(eval_path):
        import json
        with open(eval_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "Evaluation report not generated yet."}

@app.get("/api/evaluation")
def get_evaluation_full():
    """Retrieve both JSON results and text report for the frontend Benchmark tab."""
    eval_path = os.path.join(ROOT_DIR, "evaluation", "results.json")
    report_path = os.path.join(ROOT_DIR, "evaluation", "report.txt")
    results_data = {}
    report_text = ""
    if os.path.exists(eval_path):
        import json
        with open(eval_path, "r", encoding="utf-8") as f:
            results_data = json.load(f)
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report_text = f.read()
    return {"results": results_data, "report": report_text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
