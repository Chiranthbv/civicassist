"""
Data schemas and type models for CivicAssist.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class IntentType(str, Enum):
    WASTE_QUERY = "WASTE_QUERY"
    PERMIT_QUERY = "PERMIT_QUERY"
    EVENT_QUERY = "EVENT_QUERY"
    WEATHER_QUERY = "WEATHER_QUERY"
    EVENT_WEATHER_QUERY = "EVENT_WEATHER_QUERY"
    FOLLOW_UP_QUERY = "FOLLOW_UP_QUERY"
    GENERAL_MUNICIPAL_QUERY = "GENERAL_MUNICIPAL_QUERY"
    GREETING = "GREETING"
    UNKNOWN = "UNKNOWN"

class ConfidenceLevel(str, Enum):
    HIGH = "🟢 High Confidence"
    MEDIUM = "🟡 Medium Confidence"
    LOW = "🔴 Low Confidence"

@dataclass
class SourceCitation:
    source_file: str
    record_id: str
    domain: str
    title: str
    relevance_score: float
    text_snippet: str
    full_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "record_id": self.record_id,
            "domain": self.domain,
            "title": self.title,
            "relevance_score": round(self.relevance_score, 3),
            "text_snippet": self.text_snippet,
            "full_text": self.full_text,
            "metadata": self.metadata
        }

@dataclass
class WeatherAdvisory:
    location: str
    event_name: Optional[str]
    forecast_summary: str
    temperature_f: Optional[float]
    condition: str
    rain_probability: int
    is_live_api: bool
    advisory_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "event_name": self.event_name,
            "forecast_summary": self.forecast_summary,
            "temperature_f": self.temperature_f,
            "condition": self.condition,
            "rain_probability": self.rain_probability,
            "is_live_api": self.is_live_api,
            "advisory_note": self.advisory_note
        }

@dataclass
class ChatResponse:
    answer: str
    detected_intent: IntentType
    confidence: ConfidenceLevel
    confidence_score: float
    sources: List[SourceCitation]
    response_latency_seconds: float
    weather_info: Optional[WeatherAdvisory] = None
    clarification_needed: bool = False
    session_id: str = "default_session"
    language: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "detected_intent": self.detected_intent.value if isinstance(self.detected_intent, IntentType) else self.detected_intent,
            "confidence": self.confidence.value if isinstance(self.confidence, ConfidenceLevel) else self.confidence,
            "confidence_score": round(self.confidence_score, 3),
            "sources": [s.to_dict() for s in self.sources],
            "response_latency_seconds": round(self.response_latency_seconds, 3),
            "weather_info": self.weather_info.to_dict() if self.weather_info else None,
            "clarification_needed": self.clarification_needed,
            "session_id": self.session_id,
            "language": self.language
        }
