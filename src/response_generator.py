"""
Core Response Generator and Orchestrator for CivicAssist.
Coordinates Intent Classification, RAG Retrieval, Conversational Memory,
Weather Integration, LLM Generation, Source Citations, and Confidence Scoring.
"""

import time
import re
import os
import json
from typing import List, Dict, Any, Optional, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)
except Exception:
    pass
from src.schemas import (
    IntentType,
    ConfidenceLevel,
    SourceCitation,
    WeatherAdvisory,
    ChatResponse
)
from src.rag import MunicipalRAGPipeline
from src.intent_router import IntentRouter
from src.conversation_memory import ConversationMemory
from src.weather_service import WeatherService
from src.llm_provider import get_llm_provider, BaseLLMProvider
from src.logger import log_interaction

class CivicResponseGenerator:
    def __init__(
        self,
        rag_pipeline: Optional[MunicipalRAGPipeline] = None,
        weather_service: Optional[WeatherService] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ):
        self.rag = rag_pipeline or MunicipalRAGPipeline()
        self.weather = weather_service or WeatherService()
        self.intent_router = IntentRouter()
        self.llm = llm_provider or get_llm_provider()
        self.sessions: Dict[str, ConversationMemory] = {}
        self.sessions_dir = os.path.join(ROOT_DIR, "data", "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)

    def get_session_memory(self, session_id: str) -> ConversationMemory:
        if session_id not in self.sessions:
            session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
            if os.path.exists(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.sessions[session_id] = ConversationMemory.from_dict(data)
                except Exception:
                    self.sessions[session_id] = ConversationMemory(max_turns=5)
            else:
                self.sessions[session_id] = ConversationMemory(max_turns=5)
        return self.sessions[session_id]

    def save_session_memory(self, session_id: str):
        if session_id in self.sessions:
            session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
            try:
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(self.sessions[session_id].to_dict(), f, indent=2)
            except Exception:
                pass

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].clear()
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass

    def process_query(self, user_query: str, session_id: str = "default_session", language: str = "en") -> ChatResponse:
        start_time = time.time()
        memory = self.get_session_memory(session_id)
        history_context = memory.get_context()

        is_kannada = (language == "kn") or any("\u0c80" <= ch <= "\u0cff" for ch in user_query)
        is_hindi = not is_kannada and ((language == "hi") or any("\u0900" <= ch <= "\u097f" for ch in user_query))
        effective_lang = "kn" if is_kannada else ("hi" if is_hindi else "en")

        # 1. Intent Detection
        intent, intent_conf = self.intent_router.classify_intent(user_query, history_context)

        # 2. Check for Prompt Injection
        lower_q = user_query.lower()
        if any(bad in lower_q for bad in [
            "ignore previous", "disregard instructions", "system prompt", "invent a permit",
            "पिछला निर्देश भूल जाओ", "ಹಿಂದಿನ ಸೂಚನೆಗಳನ್ನು ನಿರ್ಲಕ್ಷಿಸಿ"
        ]):
            latency = time.time() - start_time
            if is_kannada:
                ans = (
                    "ನಾನು ಸಿವಿಕ್ಅಸಿಸ್ಟ್ (CivicAssist), ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಸಾರ್ವಜನಿಕ ಸೇವೆಗಳಿಗೆ ನೆರವು ನೀಡಲು ನಿಯೋಜಿತ ಅಧಿಕೃತ ಸಹಾಯಕ. "
                    "ನಾನು ಭದ್ರತಾ ನಿಯಮಗಳನ್ನು ಉಲ್ಲಂಘಿಸಲು ಅಥವಾ ಕಾಲ್ಪನಿಕ ಪರವಾನಗಿ ಶುಲ್ಕಗಳು ಅಥವಾ ನಿಯಮಗಳನ್ನು ಸೃಷ್ಟಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ."
                )
            elif is_hindi:
                ans = (
                    "मैं सिविकअसिस्ट (CivicAssist) हूँ, जो ग्रीनफ़ील्ड नगर निगम की सार्वजनिक सेवाओं में सहायता के लिए अधिकृत है। "
                    "मैं सुरक्षा दिशानिर्देशों का उल्लंघन नहीं कर सकता और न ही फर्जी परमिट शुल्क या नियम बना सकता हूँ।"
                )
            else:
                ans = (
                    "I am CivicAssist, programmed strictly to assist with Greenfield Municipal Corporation public services. "
                    "I cannot override security guidelines or invent fictitious permit fees or regulations."
                )
            log_interaction(session_id, user_query, intent.value, [], "🔴 Low Confidence", False, latency, True)
            return ChatResponse(
                answer=ans,
                detected_intent=IntentType.UNKNOWN,
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.1,
                sources=[],
                response_latency_seconds=latency,
                session_id=session_id,
                language=effective_lang
            )

        # 2.5 Handle Greetings / Municipal Areas / Capabilities
        if intent == IntentType.GREETING or (intent == IntentType.GENERAL_MUNICIPAL_QUERY and any(w in lower_q for w in ["hi", "hello", "hey", "area", "zone", "neighborhood", "cover", "service", "help", "who are you", "what can you do", "ನಮಸ್ಕಾರ", "ನಮಸ್ತೆ", "ವಲಯ"])):
            latency = time.time() - start_time
            zone_entries = []
            for w in getattr(self.rag, "waste_records", []):
                z = w.get("zone", "")
                a = w.get("area", "")
                if z and a:
                    zone_entries.append(f"• **{z}:** {a}")

            if not zone_entries:
                zone_entries = [
                    "• **Zone A:** Downtown & Civic Center",
                    "• **Zone B:** Riverside & Elm Park District",
                    "• **Zone C:** Highland Hills & Northridge Residential",
                    "• **Zone D:** Westside Commercial & Mixed Plaza",
                    "• **Zone E:** University Quarter & Academic Village",
                    "• **Zone F:** East Greenfield Industrial Park",
                    "• **Zone G:** South Greenfield Suburbs",
                    "• **Zone H:** Oakwood Estates & Forest Glen",
                    "• **Zone I:** Greenfield Marina & Harbor District",
                    "• **Zone J:** Heritage Historic District & Old Town",
                    "• **Zone K:** Greenfield Meadowlands & Valley Ridge"
                ]

            zones_text = "\n".join(zone_entries)
            if is_kannada:
                ans = (
                    "ನಮಸ್ಕಾರ! 🙏 ನಾನು **ಸಿವಿಕ್ಅಸಿಸ್ಟ್ (CivicAssist)**, **ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆ**ಯ ಅಧಿಕೃತ ಎಐ ಸಾರ್ವಜನಿಕ ಸೇವಾ ಸಹಾಯಕ.\n\n"
                    "ನಾನು ನಗರದ ವೇಳಾಪಟ್ಟಿಗಳು, ಪರವಾನಗಿ ನಿಯಮಗಳು, ಸಾರ್ವಜನಿಕ ಕಾರ್ಯಕ್ರಮಗಳು ಮತ್ತು ಹವಾಮಾನ ಮುನ್ಸೂಚನೆಗಳ ಅಧಿಕೃತ ಮಾಹಿತಿಯನ್ನು ಒದಗಿಸುತ್ತೇನೆ.\n\n"
                    "📍 **ಸೇವೆ ಒದಗಿಸಲಾಗುವ ವಲಯಗಳು ಮತ್ತು ಪ್ರದೇಶಗಳು:**\n"
                    f"{zones_text}\n\n"
                    "🏛️ **ನೀವು ವಿಚಾರಿಸಬಹುದಾದ ಪಾಲಿಕೆ ಸೇವೆಗಳು:**\n"
                    "1. 🗑️ **ಕಸ ಸಂಗ್ರಹ ಮತ್ತು ಮರುಬಳಕೆ:** ನಿಮ್ಮ ಪ್ರದೇಶದ ಕಸ ಸಂಗ್ರಹ ದಿನಗಳು, ಒಣ/ಹಸಿ ಕಸದ ನಿಯಮಗಳು ಅಥವಾ ಅಪಾಯಕಾರಿ ತ್ಯಾಜ್ಯ ವಿಲೇವಾರಿ (ಉದಾ: *\"ವಲಯ ಎ ನಲ್ಲಿ ಕಸ ಯಾವಾಗ ಸಂಗ್ರಹಿಸಲಾಗುತ್ತದೆ?\"*).\n"
                    "2. 📋 **ಪಾಲಿಕೆ ಪರವಾನಗಿಗಳು ಮತ್ತು ಲೈಸೆನ್ಸ್‌ಗಳು:** ಕಟ್ಟಡ ನಿರ್ಮಾಣ, ವ್ಯಾಪಾರ ಲೈಸೆನ್ಸ್, ಆಹಾರ ಮಳಿಗೆ, ಸೌರ ಫಲಕ ಅಳವಡಿಕೆ ಮತ್ತು ಮರ ಕಡಿಯುವ ಅನುಮತಿಗಳ ಶುಲ್ಕ ಮತ್ತು ದಾಖಲೆಗಳು (ಉದಾ: *\"ಆಹಾರ ವ್ಯಾಪಾರ ಪರವಾನಗಿಗೆ ಯಾವ ದಾಖಲೆಗಳು ಬೇಕು?\"*).\n"
                    "3. 🎪 **ನಗರದ ಕಾರ್ಯಕ್ರಮಗಳು ಮತ್ತು ಉತ್ಸವಗಳು:** ಸಾಂಸ್ಕೃತಿಕ ಕಾರ್ಯಕ್ರಮಗಳು, ಮ್ಯಾರಥಾನ್, ಮಾರುಕಟ್ಟೆಗಳು ಮತ್ತು ಜಾತ್ರೆಗಳ ದಿನಾಂಕ, ಸ್ಥಳ ಮತ್ತು ಸಮಯ (ಉದಾ: *\"ನಗರದ ಮ್ಯಾರಥಾನ್ ಎಲ್ಲಿ ನಡೆಯಲಿದೆ?\"*).\n"
                    "4. ☀️ **ನೇರ ಹವಾಮಾನ ಸಲಹೆ:** ಹೊರಾಂಗಣ ಕಾರ್ಯಕ್ರಮಗಳ ಮೇಲೆ ಮಳೆ ಮತ್ತು ತಾಪಮಾನದ ಪ್ರಭಾವದ ಮುನ್ಸೂಚನೆ (ಉದಾ: *\"ಹವಾಮಾನವು ಮ್ಯಾರಥಾನ್ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರುತ್ತದೆಯೇ?\"*).\n\n"
                    "ಇಂದು ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ? ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ!"
                )
            elif is_hindi:
                ans = (
                    "नमस्ते! 🙏 मैं **सिविकअसिस्ट (CivicAssist)** हूँ, **ग्रीनफ़ील्ड नगर निगम** का आधिकारिक एआई नागरिक सेवा सहायक।\n\n"
                    "मैं आपको नगर निगम समय-सारणी, परमिट प्रक्रियाओं, नगर कार्यक्रमों और लाइव मौसम सलाह की सत्यापित जानकारी प्रदान करता हूँ।\n\n"
                    "📍 **सेवाकृत नगर निगम ज़ोन एवं क्षेत्र:**\n"
                    f"{zones_text}\n\n"
                    "🏛️ **नागरिक सेवाएँ जिनके बारे में आप पूछ सकते हैं:**\n"
                    "1. 🗑️ **कचरा संग्रह एवं पुनर्चक्रण:** अपने क्षेत्र के संग्रह दिन, गीला/सूखा कचरा नियम, बागवानी अपशिष्ट, या खतरनाक सामग्री निस्तारण (उदा. *\"ज़ोन ए में कचरा कब उठाया जाता है?\"*)।\n"
                    "2. 📋 **नगर निगम परमिट एवं लाइसेंस:** भवन निर्माण, व्यापार लाइसेंस, फ़ूड ट्रक, सौर ऊर्जा पैनल और वृक्ष कटाई परमिट के दस्तावेज़, शुल्क और समय-सीमा (उदा. *\"आवासीय भवन परमिट के लिए क्या चाहिए?\"*)।\n"
                    "3. 🎪 **नगर कार्यक्रम एवं मेले:** संगीत समारोह, मैराथन, किसान बाज़ार और सामुदायिक उत्सवों के स्थल, समय और तिथियाँ (उदा. *\"एल्म पार्क में कौन से कार्यक्रम हो रहे हैं?\"*)।\n"
                    "4. ☀️ **मौसम सलाह:** कार्यक्रमों पर बारिश, तापमान और तूफान के प्रभाव का वास्तविक समय पूर्वानुमान (उदा. *\"क्या मौसम सिटी मैराथन को प्रभावित करेगा?\"*)।\n\n"
                    "आज मैं आपकी क्या सहायता कर सकता हूँ? कृपया अपना प्रश्न पूछें या अपने क्षेत्र का नाम बताएं!"
                )
            else:
                ans = (
                    "Hello! 👋 I am **CivicAssist**, your AI-powered municipal assistant for **Greenfield Municipal Corporation**.\n\n"
                    "I provide verified information on city schedules, permit procedures, public events, and live weather advisories.\n\n"
                    "📍 **Serviced Municipal Zones & Neighborhoods:**\n"
                    f"{zones_text}\n\n"
                    "🏛️ **Municipal Services You Can Ask About:**\n"
                    "1. 🗑️ **Waste Collection & Recycling:** Pickup schedules, recycling rules, yard clippings, bulk items, or hazardous waste disposal (e.g., *\"When is trash collected in Zone A?\"* or *\"How do I dispose of paint in Riverside?\"*).\n"
                    "2. 📋 **Municipal Permits & Licensing:** Requirements, fees, and processing times for building additions, trade licenses, outdoor dining, food trucks, solar panels, and tree removal (e.g., *\"What documents are needed for a residential building permit?\"*).\n"
                    "3. 🎪 **City Events & Festivals:** Dates, venues, activities, and timings for community celebrations, markets, and concerts (e.g., *\"What events are happening in Elm Park?\"*).\n"
                    "4. ☀️ **Live Event Weather Advisories:** Real-time temperature, rain probability, and outdoor forecast advisories for scheduled events (e.g., *\"Will the weather affect the city marathon?\"*).\n\n"
                    "How can I assist you today? Please feel free to ask a question or specify your neighborhood/zone!"
                )
            log_interaction(session_id, user_query, IntentType.GREETING.value, [], "🟢 High Confidence", False, latency, True)
            return ChatResponse(
                answer=ans,
                detected_intent=IntentType.GREETING,
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.95,
                sources=[],
                response_latency_seconds=latency,
                session_id=session_id,
                language=effective_lang
            )

        # 3. Check for out-of-scope non-municipal queries
        if intent == IntentType.UNKNOWN and any(w in lower_q for w in ["passport", "dmv", "visa", "flight", "crypto", "bitcoin", "पासपोर्ट", "ಪಾಸ್‌ಪೋರ್ಟ್", "ಪಾಸ್ಪೋರ್ಟ್", "ವೀಸಾ"]):
            latency = time.time() - start_time
            if is_kannada:
                ans = (
                    "ನಾನು ಪಾಸ್‌ಪೋರ್ಟ್ ನವೀಕರಣ ಅಥವಾ ಚಾಲನಾ ಪರವಾನಗಿ (DMV) ನಂತಹ ಕೇಂದ್ರ ಅಥವಾ ರಾಜ್ಯ ಮಟ್ಟದ ವಿಷಯಗಳಲ್ಲಿ ಸಹಾಯ ಮಾಡಲು ಸಾಧ್ಯವಿಲ್ಲ. "
                    "ಸಿವಿಕ್ಅಸಿಸ್ಟ್ ಕೇವಲ ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಸ್ಥಳೀಯ ಸೇವೆಗಳನ್ನು ಬೆಂಬಲಿಸುತ್ತದೆ: "
                    "ಕಸ ಸಂಗ್ರಹ ವೇಳಾಪಟ್ಟಿ, ಕಟ್ಟಡ/ವ್ಯಾಪಾರ ಪರವಾನಗಿಗಳು, ನಗರ ಕಾರ್ಯಕ್ರಮಗಳು ಮತ್ತು ಹವಾಮಾನ ಸಲಹೆ."
                )
            elif is_hindi:
                ans = (
                    "मैं पासपोर्ट नवीनीकरण या ड्राइविंग लाइसेंस (DMV) जैसे केंद्रीय अथवा राज्यीय मामलों में सहायता नहीं कर सकता। "
                    "सिविकअसिस्ट केवल ग्रीनफ़ील्ड नगर निगम की स्थानीय सेवाओं का समर्थन करता है: "
                    "कचरा संग्रह अनुसूची, भवन/व्यापार परमिट, नगर के सार्वजनिक कार्यक्रम और मौसम सलाह।"
                )
            else:
                ans = (
                    "I cannot assist with federal, immigration, or DMV matters such as passport renewals or state driver's licenses. "
                    "CivicAssist currently supports Greenfield Municipal Corporation local services: "
                    "waste pickup schedules, municipal building/business permits, city public events, and event weather forecasts."
                )
            log_interaction(session_id, user_query, intent.value, [], "🟡 Medium Confidence", False, latency, True)
            return ChatResponse(
                answer=ans,
                detected_intent=IntentType.UNKNOWN,
                confidence=ConfidenceLevel.MEDIUM,
                confidence_score=0.4,
                sources=[],
                response_latency_seconds=latency,
                session_id=session_id,
                language=effective_lang
            )

        # 4. Handle Ambiguous Waste Queries (Missing Zone)
        if intent == IntentType.WASTE_QUERY:
            zone_match = re.search(r"\bzone\s+([a-z])\b", lower_q)
            h_char_map = {"ए": "a", "बी": "b", "सी": "c", "डी": "d", "ई": "e", "एफ": "f", "जी": "g", "एच": "h", "आई": "i", "जे": "j", "के": "k", "ज़ेड": "z", "जेड": "z"}
            k_char_map = {"ಎ": "a", "ಬಿ": "b", "ಸಿ": "c", "ಡಿ": "d", "ಇ": "e", "ಎಫ್": "f", "ಜಿ": "g", "ಹೆಚ್": "h", "ಐ": "i", "ಜೆ": "j", "ಕೆ": "k", "ಝಡ್": "z", "ಜೆಡ್": "z"}

            if not zone_match:
                for h_char, eng_char in h_char_map.items():
                    if f"ज़ोन {h_char}" in lower_q or f"जोन {h_char}" in lower_q or f"ज़ोन-{h_char}" in lower_q:
                        class MockMatch:
                            def __init__(self, c): self.c = c
                            def group(self, idx): return self.c
                        zone_match = MockMatch(eng_char)
                        break

            if not zone_match:
                for k_char, eng_char in k_char_map.items():
                    if f"ವಲಯ {k_char}" in lower_q or f"ಜೋನ್ {k_char}" in lower_q or f"ವಲಯ-{k_char}" in lower_q:
                        class MockKMatch:
                            def __init__(self, c): self.c = c
                            def group(self, idx): return self.c
                        zone_match = MockKMatch(eng_char)
                        break

            area_match = any(w in lower_q for w in ["downtown", "riverside", "highland", "westside", "university", "industrial", "marina", "heritage", "meadowlands"])

            # If user didn't specify zone or area, and memory doesn't have an active zone:
            if not zone_match and not area_match and not memory.last_referenced_zone:
                latency = time.time() - start_time
                if is_kannada:
                    ans = (
                        "ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯು ವಿವಿಧ ಭೌಗೋಳಿಕ ವಲಯಗಳಲ್ಲಿ (ವಲಯ A ಯಿಂದ K ವರೆಗೆ) ಕಸ ಸಂಗ್ರಹಣೆಯನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ. "
                        "ನೀವು ಯಾವ ವಲಯ ಅಥವಾ ಪ್ರದೇಶದಲ್ಲಿ ವಾಸಿಸುತ್ತಿದ್ದೀರಿ? (ಉದಾ. ವಲಯ A, ಡೌನ್‌ಟೌನ್, ರಿವರ್‌ಸೈಡ್, ಹೈಲ್ಯಾಂಡ್ ಹಿಲ್ಸ್)."
                    )
                elif is_hindi:
                    ans = (
                        "ग्रीनफ़ील्ड नगर निगम विभिन्न भौगोलिक ज़ोन (ज़ोन A से K) में कचरा संग्रह संचालित करता है। "
                        "आप किस ज़ोन या मोहल्ले/क्षेत्र में रहते हैं? (उदा. ज़ोन A, Downtown, Riverside, Highland Hills)।"
                    )
                else:
                    ans = (
                        "Greenfield Municipal Corporation operates waste collection across distinct geographic zones (Zones A through K). "
                        "Which zone or neighborhood area are you located in? (e.g., Zone A, Downtown, Riverside, Highland Hills)."
                    )
                log_interaction(session_id, user_query, intent.value, [], "🟡 Medium Confidence", False, latency, True)
                return ChatResponse(
                    answer=ans,
                    detected_intent=IntentType.WASTE_QUERY,
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_score=0.6,
                    sources=[],
                    response_latency_seconds=latency,
                    clarification_needed=True,
                    session_id=session_id,
                    language=effective_lang
                )

        # 5. Handle Unavailable Zone (e.g. Zone Z)
        unavailable_zone_match = re.search(r"\bzone\s+([l-z])\b", lower_q)
        if not unavailable_zone_match and any(uz in lower_q for uz in ["ज़ोन ज़ेड", "जोन जेड", "ज़ोन z", "जोन z", "ವಲಯ ಝಡ್", "ಜೋನ್ ಝಡ್", "ವಲಯ z"]):
            class MockZMatch:
                def group(self, idx): return "z"
            unavailable_zone_match = MockZMatch()

        if unavailable_zone_match:
            requested_zone = f"Zone {unavailable_zone_match.group(1).upper()}"
            latency = time.time() - start_time
            if is_kannada:
                ans = (
                    f"ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಡೇಟಾಬೇಸ್‌ನಲ್ಲಿ {requested_zone} ನ ಕಸ ಸಂಗ್ರಹ ದಾಖಲೆಗಳು ಲಭ್ಯವಿಲ್ಲ. "
                    "ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಪ್ರಸ್ತುತ ವಲಯ A ಯಿಂದ ವಲಯ K ವರೆಗೆ ಮಾತ್ರ ಸೇವೆ ಸಲ್ಲಿಸುತ್ತದೆ. "
                    "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಯುಟಿಲಿಟಿ ಬಿಲ್ ಪರಿಶೀಲಿಸಿ ಅಥವಾ ನೈರ್ಮಲ್ಯ ವಿಭಾಗವನ್ನು (555) 019-4820 ನಲ್ಲಿ ಸಂಪರ್ಕಿಸಿ."
                )
            elif is_hindi:
                ans = (
                    f"मुझे ग्रीनफ़ील्ड नगर निगम डेटाबेस में {requested_zone} का संग्रह रिकॉर्ड नहीं मिला। "
                    "ग्रीनफ़ील्ड वर्तमान में केवल ज़ोन A से ज़ोन K तक सेवा प्रदान करता है। "
                    "कृपया अपना नगर पालिका बिल देखें या स्वच्छता विभाग से (555) 019-4820 पर संपर्क करें।"
                )
            else:
                ans = (
                    f"I could not find collection records for {requested_zone} in the Greenfield Municipal Corporation database. "
                    "Greenfield currently services designated zones from Zone A through Zone K. "
                    "Please check your municipal utility bill or contact the Greenfield Sanitation Department at (555) 019-4820."
                )
            log_interaction(session_id, user_query, intent.value, [], "🟢 High Confidence", False, latency, True)
            return ChatResponse(
                answer=ans,
                detected_intent=IntentType.WASTE_QUERY,
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.9,
                sources=[],
                response_latency_seconds=latency,
                session_id=session_id,
                language=effective_lang
            )

        # 6. Retrieve relevant documents from RAG
        retrieval_query = user_query

        # Cross-lingual expansion if query contains Devanagari Hindi or Kannada
        if is_hindi or any("\u0900" <= ch <= "\u097f" for ch in user_query):
            hindi_keywords = {
                "कचरा": "waste garbage trash", "कूड़ा": "garbage trash", "पुनर्चक्रण": "recycling",
                "संग्रह": "collection pickup", "उठाया": "pickup collection",
                "ज़ोन": "zone", "जोन": "zone",
                "ए": "A", "बी": "B", "सी": "C", "डी": "D", "ई": "E", "एफ": "F", "जी": "G", "एच": "H", "आई": "I", "जे": "J", "के": "K",
                "परमिट": "permit license", "लाइसेंस": "license", "शुल्क": "fee cost", "दस्तावेज़": "documents requirements",
                "मौसम": "weather forecast", "बारिश": "rain precipitation", "कार्यक्रम": "event festival", "मैराथन": "marathon",
                "खाद्य": "food commercial restaurant", "भोजन": "food commercial restaurant", "व्यापार": "business commercial", "व्यवसाय": "business commercial",
                "भवन": "building residential construction", "निर्माण": "construction building residential"
            }
            expanded_tokens = []
            for h_word, eng_equiv in hindi_keywords.items():
                if h_word in user_query:
                    expanded_tokens.append(eng_equiv)
            if expanded_tokens:
                retrieval_query = f"{user_query} {' '.join(expanded_tokens)}"

        elif is_kannada or any("\u0c80" <= ch <= "\u0cff" for ch in user_query):
            kannada_keywords = {
                "ಕಸ": "waste garbage trash", "ತ್ಯಾಜ್ಯ": "waste garbage trash", "ಮರುಬಳಕೆ": "recycling recycle",
                "ಸಂಗ್ರಹ": "collection pickup", "ವಿಲೇವಾರಿ": "disposal dispose",
                "ವಲಯ": "zone", "ಜೋನ್": "zone",
                "ಎ": "A", "ಬಿ": "B", "ಸಿ": "C", "ಡಿ": "D", "ಇ": "E", "ಎಫ್": "F", "ಜಿ": "G", "ಹೆಚ್": "H", "ಐ": "I", "ಜೆ": "J", "ಕೆ": "K",
                "ಪರವಾನಗಿ": "permit license", "ಪರವಾನಿಗೆ": "permit license", "ಅನುಮತಿ": "permit approval", "ಶುಲ್ಕ": "fee cost", "ದಾಖಲೆ": "documents requirements",
                "ಹವಾಮಾನ": "weather forecast", "ಮಳೆ": "rain precipitation", "ಕಾರ್ಯಕ್ರಮ": "event festival", "ಮ್ಯಾರಥಾನ್": "marathon",
                "ಕಟ್ಟಡ": "building residential construction", "ಆಹಾರ": "food commercial", "ವ್ಯಾಪಾರ": "business commercial trade"
            }
            expanded_tokens = []
            for k_word, eng_equiv in kannada_keywords.items():
                if k_word in user_query:
                    expanded_tokens.append(eng_equiv)
            if expanded_tokens:
                retrieval_query = f"{user_query} {' '.join(expanded_tokens)}"

        # If follow-up, enrich retrieval query with last entities
        if intent == IntentType.FOLLOW_UP_QUERY:
            if memory.last_referenced_zone:
                retrieval_query = f"{memory.last_referenced_zone} waste collection schedule {user_query}"
            elif memory.last_referenced_event:
                retrieval_query = f"{memory.last_referenced_event.get('name')} {user_query}"
            elif memory.last_referenced_permit:
                p_name = memory.last_referenced_permit.get("permit_type") or memory.last_referenced_permit.get("name", "")
                retrieval_query = f"{p_name} {user_query}"

        # Determine domain filter
        domain_filter = None
        if intent == IntentType.WASTE_QUERY:
            domain_filter = "waste"
        elif intent == IntentType.PERMIT_QUERY:
            domain_filter = "permits"
        elif intent in {IntentType.EVENT_QUERY, IntentType.EVENT_WEATHER_QUERY}:
            domain_filter = "events"
        elif intent == IntentType.FOLLOW_UP_QUERY:
            if memory.last_referenced_zone:
                domain_filter = "waste"
            elif memory.last_referenced_permit:
                domain_filter = "permits"
            elif memory.last_referenced_event:
                domain_filter = "events"

        sources = self.rag.retrieve(retrieval_query, top_k=3, domain=domain_filter)

        # 7. Check for unknown permit query
        if intent == IntentType.PERMIT_QUERY:
            # Check if user asked for drone permit, pet permit, etc.
            if any(term in lower_q for term in ["drone", "helicopter", "spacecraft", "mining", "casino", "fireworks manufacturing"]):
                latency = time.time() - start_time
                if is_kannada:
                    ans = (
                        "ವಿನಂತಿಸಲಾದ ಪರವಾನಗಿ ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಮಾಹಿತಿ ಕೋಶದಲ್ಲಿ ಲಭ್ಯವಿಲ್ಲ. "
                        "ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಪ್ರಸ್ತುತ ಕಟ್ಟಡ ನಿರ್ಮಾಣ, ವ್ಯಾಪಾರ ಲೈಸೆನ್ಸ್, ಆಹಾರ ಮಳಿಗೆಗಳು, "
                        "ವಿಶೇಷ ಕಾರ್ಯಕ್ರಮಗಳು, ಸೌರ ಫಲಕಗಳು ಮತ್ತು ಅಲ್ಪಾವಧಿ ಬಾಡಿಗೆಗಳನ್ನು ಮಾತ್ರ ನಿಯಂತ್ರಿಸುತ್ತದೆ. "
                        "ಪಟ್ಟಿ ಮಾಡದ ಪರವಾನಗಿಗಳಿಗಾಗಿ ದಯವಿಟ್ಟು ಸಿಟಿ ಕ್ಲರ್ಕ್ ಕಚೇರಿಯನ್ನು (555) 019-3000 ನಲ್ಲಿ ಸಂಪರ್ಕಿಸಿ."
                    )
                elif is_hindi:
                    ans = (
                        "अनुरोधित परमिट ग्रीनफ़ील्ड नगर निगम के ज्ञानकोष में उपलब्ध नहीं है। "
                        "ग्रीनफ़ील्ड वर्तमान में भवन निर्माण, व्यापार लाइसेंस, खाद्य प्रतिष्ठान, "
                        "विशेष कार्यक्रम, सौर पैनल और अल्पकालिक किराए का नियमन करता है। "
                        "अन्य परमिटों के लिए कृपया सिटी क्लर्क से (555) 019-3000 पर संपर्क करें।"
                    )
                else:
                    ans = (
                        "The requested permit is not available in the Greenfield Municipal Corporation knowledge base. "
                        "Greenfield currently regulates building, trade licenses, commercial food establishments, "
                        "special events, demolition, solar installations, and short-term rentals. "
                        "For unlisted permits, please contact the City Clerk at (555) 019-3000."
                    )
                log_interaction(session_id, user_query, intent.value, [], "🟢 High Confidence", False, latency, True)
                return ChatResponse(
                    answer=ans,
                    detected_intent=IntentType.PERMIT_QUERY,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=0.88,
                    sources=[],
                    response_latency_seconds=latency,
                    session_id=session_id,
                    language=effective_lang
                )

        # 8. Check if no reliable documents retrieved
        if not sources or (sources and sources[0].relevance_score < 0.22):
            latency = time.time() - start_time
            if is_kannada:
                ans = "ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಮಾಹಿತಿ ಕೋಶದಲ್ಲಿ ಇದರ ಬಗ್ಗೆ ವಿಶ್ವಾಸಾರ್ಹ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ."
            elif is_hindi:
                ans = "मुझे नगर निगम ज्ञानकोष में इसके बारे में विश्वसनीय जानकारी नहीं मिली।"
            else:
                ans = "I couldn't find reliable information about that in the municipal knowledge base."

            log_interaction(session_id, user_query, intent.value, [], "🔴 Low Confidence", False, latency, True)
            return ChatResponse(
                answer=ans,
                detected_intent=intent,
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.2,
                sources=[],
                response_latency_seconds=latency,
                session_id=session_id,
                language=effective_lang
            )

        # 9. Handle Weather Advisory if Weather or Event+Weather
        weather_info: Optional[WeatherAdvisory] = None
        weather_called = False

        if intent in {IntentType.EVENT_WEATHER_QUERY, IntentType.WEATHER_QUERY} or ("rain" in lower_q or "weather" in lower_q):
            # Find matching event
            matched_event = None
            if sources and sources[0].domain == "events":
                matched_event = sources[0].metadata
            elif memory.last_referenced_event:
                ev_name = memory.last_referenced_event.get("name", "")
                matched_event = self.rag.get_event_by_name(ev_name) or memory.last_referenced_event

            if matched_event:
                weather_info = self.weather.get_weather_for_event(
                    event_name=matched_event.get("name", "City Event"),
                    event_date=matched_event.get("date", "2026-10-12"),
                    location=matched_event.get("location", "Greenfield Central Park"),
                    is_outdoor=matched_event.get("outdoor", True)
                )
                weather_called = True
            else:
                # General city weather
                weather_info = self.weather.get_weather_for_event(
                    event_name="Greenfield Municipal Area",
                    event_date="Today",
                    location="Greenfield, Civic Center",
                    is_outdoor=True
                )
                weather_called = True

        # 10. Generate grounded response with LLM
        retrieved_context_str = "\n\n".join([f"--- SOURCE [{s.source_file} | {s.record_id}] ---\n{s.full_text or s.text_snippet}" for s in sources])

        if weather_info:
            weather_text = (
                f"\n\n--- LIVE WEATHER INFORMATION (EXTERNAL API) ---\n"
                f"Event: {weather_info.event_name}\n"
                f"Location: {weather_info.location}\n"
                f"Forecast Summary: {weather_info.forecast_summary}\n"
                f"Precipitation Probability: {weather_info.rain_probability}%\n"
                f"Weather Advisory Note: {weather_info.advisory_note}\n"
                f"Status: {'Live OpenWeatherMap API' if weather_info.is_live_api else 'Meteorological Forecast Simulation'}"
            )
            retrieved_context_str += weather_text

        # Call LLM / Fallback
        answer = self.llm.generate_response(user_query, retrieved_context_str, history_context, language=effective_lang)

        # Specific formatting check for City Marathon + Weather demo scenario
        if "marathon" in lower_q and ("weather" in lower_q or "rain" in lower_q):
            # Ensure official information and weather information are cleanly presented
            pass

        # 11. Calculate Qualitative Confidence
        top_sim = sources[0].relevance_score if sources else 0.0
        conf_level, conf_score = self._compute_confidence(top_sim, len(sources), intent_conf, weather_info)

        latency = time.time() - start_time

        # Update Conversation Memory
        memory.add_message("user", user_query)
        memory.add_message("assistant", answer, metadata={
            "zone": sources[0].record_id if sources and sources[0].domain == "waste" else None,
            "event": sources[0].metadata if sources and sources[0].domain == "events" else None,
            "permit": sources[0].metadata if sources and sources[0].domain == "permits" else None
        })
        self.save_session_memory(session_id)

        # Log
        log_interaction(
            session_id=session_id,
            user_query=user_query,
            detected_intent=intent.value,
            retrieved_sources=[s.to_dict() for s in sources],
            confidence=conf_level.value,
            weather_api_used=weather_called,
            response_latency=latency,
            success=True
        )

        return ChatResponse(
            answer=answer,
            detected_intent=intent,
            confidence=conf_level,
            confidence_score=conf_score,
            sources=sources,
            response_latency_seconds=latency,
            weather_info=weather_info,
            session_id=session_id,
            language=effective_lang
        )

    def _compute_confidence(
        self,
        top_similarity: float,
        num_sources: int,
        intent_conf: float,
        weather_info: Optional[WeatherAdvisory]
    ) -> Tuple[ConfidenceLevel, float]:
        score = (top_similarity * 0.5) + (min(num_sources, 3) / 3.0 * 0.25) + (intent_conf * 0.25)

        if top_similarity >= 0.40 and num_sources >= 1:
            return ConfidenceLevel.HIGH, min(score, 0.98)
        elif top_similarity >= 0.25:
            return ConfidenceLevel.MEDIUM, score
        else:
            return ConfidenceLevel.LOW, score
