"""
Intent Router for CivicAssist Municipal Queries.
Implements rule/pattern-based classification with LLM intent classification support.
"""

import re
from typing import Tuple
from src.schemas import IntentType

class IntentRouter:
    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    def classify_intent(self, query: str, conversation_context: str = "") -> Tuple[IntentType, float]:
        """
        Returns (IntentType, confidence_score) where confidence is between 0.0 and 1.0.
        """
        q = query.lower().strip()

        # Check for prompt injection attempts
        if any(bad in q for bad in [
            "ignore previous", "disregard instructions", "system prompt", "jailbreak", "invent a permit",
            "पिछला निर्देश भूल जाओ", "ಹಿಂದಿನ ಸೂಚನೆಗಳನ್ನು ನಿರ್ಲಕ್ಷಿಸಿ"
        ]):
            return IntentType.UNKNOWN, 0.95

        # 1. Check for Event + Weather combination
        weather_terms = [
            "weather", "rain", "storm", "forecast", "sunny", "temperature", "umbrella", "snow", "precipitation",
            "मौसम", "बारिश", "बरसात", "तापमान", "तूफान",
            "ಹವಾಮಾನ", "ಮಳೆ", "ಬಿರುಗಾಳಿ", "ತಾಪಮಾನ", "ಮುನ್ಸೂಚನೆ"
        ]
        event_terms = [
            "event", "marathon", "concert", "festival", "fair", "market", "expo", "parade", "match", "tournament", "movie", "screening", "activities",
            "कार्यक्रम", "समारोह", "मैराथन", "मेला", "उत्सव", "कॉन्सर्ट",
            "ಕಾರ್ಯಕ್ರಮ", "ಸಮಾರಂಭ", "ಮ್ಯಾರಥಾನ್", "ಉತ್ಸವ", "ಜಾತ್ರೆ", "ಮೇಳ", "ಸಂಗೀತ ಕಚೇರಿ"
        ]

        has_weather = any(wt in q for wt in weather_terms)
        has_event = any(et in q for et in event_terms)

        if has_weather and has_event:
            return IntentType.EVENT_WEATHER_QUERY, 0.95

        # 2. Check for Follow-Up queries relying on conversation context
        # e.g., "what about next week?", "will it rain?", "what about zone z?", "ಮುಂದಿನ ವಾರದ ಬಗ್ಗೆ ಏನು?"
        follow_up_patterns = [
            r"^(what|how)\s+about\b",
            r"^and\s+(what|when|how|is)\b",
            r"^will\s+it\s+(rain|snow|be)\b",
            r"^what\s+does\s+it\s+cost\b",
            r"^where\s+is\s+it\b",
            r"^when\s+is\s+it\b",
            r"^can\s+i\s+still\b",
            r"^what\s+about\s+my\s+area\b",
            r"^(ಮುಂದಿನ|ಮತ್ತೆ|ಇನ್ನೇನು|ಬಗ್ಗೆ ಏನು)\b"
        ]
        if conversation_context and (
            any(re.search(pat, q) for pat in follow_up_patterns) or
            any(f in q for f in ["अगले", "ಮುಂದಿನ ವಾರ", "ಮಳೆ ಬೀಳುವುದೇ", "ಬಗ್ಗೆ ಏನು"])
        ):
            # Check if this follow-up specifically asks about weather for a prior event
            if has_weather and any(term in conversation_context.lower() for term in event_terms):
                return IntentType.EVENT_WEATHER_QUERY, 0.92
            return IntentType.FOLLOW_UP_QUERY, 0.90

        # 3. Pure Weather Query
        if has_weather and not has_event:
            if conversation_context and any(term in conversation_context.lower() for term in event_terms):
                return IntentType.EVENT_WEATHER_QUERY, 0.88
            return IntentType.WEATHER_QUERY, 0.90

        # 4. Waste Management Queries
        waste_terms = [
            "garbage", "trash", "recycle", "recycling", "waste", "rubbish", "compost",
            "pickup", "bin", "curbside", "yard waste", "dumpster", "collection schedule",
            "cardboard", "dispose", "disposal", "scrap", "batteries", "bulk item",
            "zone a", "zone b", "zone c", "zone d", "zone e", "zone f", "zone g", "zone h", "zone i", "zone j", "zone k",
            "कचरा", "कूड़ा", "पुनर्चक्रण", "सफाई", "अपशिष्ट", "संग्रह", "उठाया", "निस्तारण", "ज़ोन", "जोन",
            "ಕಸ", "ತ್ಯಾಜ್ಯ", "ಕಸ ಸಂಗ್ರಹ", "ಮರುಬಳಕೆ", "ಸ್ವಚ್ಛತೆ", "ವಿಲೇವಾರಿ", "ಬುಟ್ಟಿ", "ವಲಯ", "ಜೋನ್"
        ]
        if (
            any(wt in q for wt in waste_terms) or
            re.search(r"\bzone\s+[a-z]\b", q) or
            re.search(r"\b(ज़ोन|जोन)\s+[a-zA-Z\u0900-\u097F]\b", q) or
            re.search(r"\b(ವಲಯ|ಜೋನ್)\s+[a-zA-Z\u0C80-\u0CFF]\b", q)
        ):
            return IntentType.WASTE_QUERY, 0.93

        # 5. Permit Queries
        permit_terms = [
            "permit", "license", "licence", "application", "approval", "fee", "cost to build",
            "building permit", "construction permit", "trade license", "contractor license",
            "food business", "street closure", "demolition", "signage", "sign", "billboard",
            "curb cut", "tree removal", "oak tree", "home occupation", "solar", "plumbing permit", "short-term rental",
            "परमिट", "लाइसेंस", "अनुमति", "स्वीकृति", "शुल्क", "दस्तावेज़", "निर्माण परमिट",
            "ಪರವಾನಗಿ", "ಪರವಾನಿಗೆ", "ಅನುಮತಿ", "ಮಂಜೂರಾತಿ", "ಶುಲ್ಕ", "ದಾಖಲೆಗಳು", "ಅರ್ಜಿ", "ಕಟ್ಟಡ ಪರವಾನಗಿ", "ವ್ಯಾಪಾರ ಪರವಾನಗಿ", "ಆಹಾರ ಪರವಾನಗಿ"
        ]
        if any(pt in q for pt in permit_terms):
            return IntentType.PERMIT_QUERY, 0.93

        # 6. Event Queries
        if any(et in q for et in event_terms) or any(w in q for w in ["happening", "this weekend", "today", "activities", "celebration", "ಕಾರ್ಯಕ್ರಮಗಳು"]):
            return IntentType.EVENT_QUERY, 0.92

        # 7. Out of scope queries (Passports, DMV, Visas, Crypto, Banking, flights)
        out_of_scope = [
            "passport", "driver's license", "dmv", "visa", "embassy", "federal tax", "irs", "flight", "hotel booking", "crypto", "stock market", "bitcoin",
            "पासपोर्ट", "वीज़ा", "ड्राइविंग लाइसेंस",
            "ಪಾಸ್‌ಪೋರ್ಟ್", "ಪಾಸ್ಪೋರ್ಟ್", "ವೀಸಾ", "ಡ್ರೈವಿಂಗ್ ಲೈಸೆನ್ಸ್"
        ]
        if any(oos in q for oos in out_of_scope):
            return IntentType.UNKNOWN, 0.96

        # 8. Greetings / Municipal Areas / Capabilities
        greeting_patterns = [
            r"^(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening))\b",
            r"^(who\s+are\s+you|what\s+can\s+you\s+do|help|help\s*me)\b",
            r"(what|which|list|tell\s+me\s+about)\s+(the\s+)?(municipal\s+)?(areas|zones|neighborhoods|services|districts)\b",
            r"^(areas|zones|services|municipal\s+areas)\b",
            r"^municipal\b"
        ]
        indic_greetings = ["नमस्ते", "प्रणाम", "हेलो", "हाय", "ನಮಸ್ಕಾರ", "ನಮಸ್ತೆ", "ಹಲೋ", "ಹಾಯ್", "ಸಹಾಯ"]
        if any(re.search(pat, q) for pat in greeting_patterns) or any(q.startswith(g) for g in indic_greetings):
            return IntentType.GREETING, 0.95

        # 9. General Municipal
        municipal_general = [
            "greenfield", "city hall", "mayor", "council", "office hours", "services", "helpline", "municipal", "department",
            "नगर निगम", "नगर पालिका", "ನಗರ ಸಭೆ", "ಮಹಾನಗರ ಪಾಲಿಕೆ", "ನಗರ ಪಾಲಿಕೆ"
        ]
        if any(mg in q for mg in municipal_general):
            return IntentType.GENERAL_MUNICIPAL_QUERY, 0.82

        return IntentType.UNKNOWN, 0.50
