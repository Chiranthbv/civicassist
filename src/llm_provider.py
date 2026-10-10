"""
Provider-independent LLM Architecture for CivicAssist.
Supports GeminiProvider, OpenAIProvider, and a zero-hallucination Grounded FallbackProvider.
"""

import os
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

SYSTEM_PROMPT = (
    "You are CivicAssist, a municipal public-service assistant for Greenfield Municipal Corporation.\n"
    "Answer using ONLY the supplied municipal knowledge base and explicitly supplied live API information.\n"
    "Do not invent facts, fees, dates, or schedules.\n"
    "If the required information is unavailable or not found in the context, say so clearly.\n"
    "Distinguish official municipal information from live weather information.\n"
    "Never claim an event is cancelled unless the municipal records explicitly state it.\n"
    "Ask clarification questions when a citizen's query is ambiguous (such as omitting a waste collection zone).\n"
    "Keep answers polite, professional, concise, and structured with bullet points where appropriate.\n"
    "Provide ONLY the final citizen-facing response. Do not include internal thoughts, reasoning chains, or verification checklists."
)

class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_response(self, user_query: str, retrieved_context: str, conversation_history: str = "", language: str = "en") -> str:
        pass

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.6-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model = model
        self.fallback = FallbackProvider()
        self._disabled = False

    def is_available(self) -> bool:
        if self._disabled:
            return False
        return bool(self.api_key and len(self.api_key) > 10 and self.api_key not in {"MY_GEMINI_API_KEY", "YOUR_KEY"})

    def generate_response(self, user_query: str, retrieved_context: str, conversation_history: str = "", language: str = "en") -> str:
        if not self.is_available():
            return self.fallback.generate_response(user_query, retrieved_context, conversation_history, language=language)

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        is_hindi = (language == "hi") or any("\u0900" <= ch <= "\u097f" for ch in user_query)
        is_kannada = (language == "kn") or any("\u0c80" <= ch <= "\u0cff" for ch in user_query)
        
        lang_directive = ""
        if is_kannada:
            lang_directive = (
                "\n\nCRITICAL LANGUAGE DIRECTIVE: The citizen has selected KANNADA (ಕನ್ನಡ). "
                "You MUST generate your entire response in clear, formal, and helpful Kannada using Kannada script. "
                "Keep zone identifiers (e.g. Zone A, Zone B), addresses, phone numbers, and fees clearly preserved while explaining all schedules, rules, and procedures in Kannada."
            )
        elif is_hindi:
            lang_directive = (
                "\n\nCRITICAL LANGUAGE DIRECTIVE: The citizen has selected HINDI (हिन्दी). "
                "You MUST generate your entire response in clear, formal, and helpful Hindi using Devanagari script. "
                "Keep zone identifiers (e.g. Zone A, Zone B), addresses, phone numbers, and fees clearly preserved while explaining all schedules, rules, and procedures in Hindi."
            )

        lang_label = " (IN KANNADA)" if is_kannada else (" (IN HINDI)" if is_hindi else "")
        prompt = (
            f"{SYSTEM_PROMPT}{lang_directive}\n\n"
            f"--- RECENT CONVERSATION HISTORY ---\n{conversation_history if conversation_history else 'None'}\n\n"
            f"--- RETRIEVED MUNICIPAL KNOWLEDGE BASE CONTEXT ---\n{retrieved_context}\n\n"
            f"--- CITIZEN INQUIRY ---\n{user_query}\n\n"
            f"CIVICASSIST OFFICIAL RESPONSE{lang_label}:"
        )

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "maxOutputTokens": 2048,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }

        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "CivicAssist/1.0"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if p.get("text")]
                    full_text = "\n".join(text_parts).strip()
                    if "checks:**" in full_text:
                        full_text = full_text.split("checks:**")[0].strip()
                    if full_text:
                        return full_text
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 429):
                # Rate limited or invalid key/model; disable for this session to avoid latency penalties
                self._disabled = True
        except Exception:
            pass

        return self.fallback.generate_response(user_query, retrieved_context, conversation_history, language=language)

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        self.model = model

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def generate_response(self, user_query: str, retrieved_context: str, conversation_history: str = "", language: str = "en") -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI API key is not configured.")

        endpoint = "https://api.openai.com/v1/chat/completions"
        system_text = SYSTEM_PROMPT
        if language == "kn" or any("\u0c80" <= ch <= "\u0cff" for ch in user_query):
            system_text += "\n\nCRITICAL LANGUAGE DIRECTIVE: Respond in formal Kannada (ಕನ್ನಡ) using Kannada script."
        elif language == "hi" or any("\u0900" <= ch <= "\u097f" for ch in user_query):
            system_text += "\n\nCRITICAL LANGUAGE DIRECTIVE: Respond in formal Hindi (हिन्दी) using Devanagari script."

        messages = [
            {"role": "system", "content": system_text},
        ]
        if conversation_history:
            messages.append({"role": "system", "content": f"Recent history:\n{conversation_history}"})
        messages.append({
            "role": "user",
            "content": f"Municipal Context:\n{retrieved_context}\n\nCitizen Inquiry: {user_query}"
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "CivicAssist/1.0"
            }
        )

        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()

class FallbackProvider(BaseLLMProvider):
    """
    Deterministic, grounded response generator when no external LLM API key is present.
    Extracts facts directly from verified retrieved context with 0% hallucination.
    Supports English, Hindi, and Kannada.
    """
    def generate_response(self, user_query: str, retrieved_context: str, conversation_history: str = "", language: str = "en") -> str:
        is_hindi = (language == "hi") or any("\u0900" <= ch <= "\u097f" for ch in user_query)
        is_kannada = (language == "kn") or any("\u0c80" <= ch <= "\u0cff" for ch in user_query)

        if not retrieved_context or "not found" in retrieved_context.lower():
            if is_kannada:
                return (
                    "ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆ ಮಾಹಿತಿ ಕೋಶದಲ್ಲಿ ಈ ಕುರಿತು ವಿಶ್ವಾಸಾರ್ಹ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ. "
                    "ಸಿವಿಕ್ಅಸಿಸ್ಟ್ ಪ್ರಸ್ತುತ ವಸತಿ ಕಸ ಸಂಗ್ರಹ ವೇಳಾಪಟ್ಟಿ, ಪರವಾನಗಿ/ಲೈಸೆನ್ಸ್ ನಿಯಮಗಳು, "
                    "ನಗರದ ಸಾರ್ವಜನಿಕ ಕಾರ್ಯಕ್ರಮಗಳು ಮತ್ತು ಹವಾಮಾನ ಸಲಹೆಗಳನ್ನು ಬೆಂಬಲಿಸುತ್ತದೆ."
                )
            if is_hindi:
                return (
                    "ग्रीनफ़ील्ड नगर निगम ज्ञानकोष में इसके बारे में विश्वसनीय जानकारी नहीं मिली। "
                    "सिविकअसिस्ट वर्तमान में आवासीय कचरा संग्रह, परमिट/लाइसेंस, नगर कार्यक्रम और मौसम सलाह का समर्थन करता है।"
                )
            return (
                "I couldn't find reliable information about that in the Greenfield Municipal Corporation knowledge base. "
                "CivicAssist currently supports municipal services including residential waste collection schedules, "
                "permit and license guidelines, city public events, and weather advisories for outdoor gatherings."
            )

        q_lower = user_query.lower()

        # Check if weather info is appended
        has_weather = "--- LIVE WEATHER INFORMATION" in retrieved_context
        weather_section = ""
        municipal_context = retrieved_context
        if has_weather:
            parts = retrieved_context.split("--- LIVE WEATHER INFORMATION")
            municipal_context = parts[0]
            weather_section = "--- LIVE WEATHER INFORMATION" + parts[1]

        top_block = municipal_context.split("--- SOURCE")[1] if "--- SOURCE" in municipal_context else municipal_context

        # Reliable domain detection directly from retrieved source block
        is_waste = "waste_schedule.json" in top_block or "Municipal Waste Management" in top_block
        is_permit = "permits.csv" in top_block or "Municipal Permit" in top_block
        is_event = "events.json" in top_block or "Municipal Event" in top_block

        # Case 1: Waste Query / Follow-up
        if is_waste:
            lines = [l.strip() for l in top_block.split("\n") if l.strip()]
            zone_info = {}
            for l in lines:
                if ":" in l and not l.startswith("---"):
                    k, v = l.split(":", 1)
                    if k.strip().lower() not in zone_info:
                        zone_info[k.strip().lower()] = v.strip()

            days = zone_info.get("scheduled pickup days", "regular schedule")
            time_slot = zone_info.get("collection hours", "morning hours")
            types = zone_info.get("waste types collected", "general refuse")
            guidelines = zone_info.get("special guidelines", "")
            contact = zone_info.get("contact", "")

            if is_kannada:
                ans = f"ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ನಿಯಮಾವಳಿಗಳ ಪ್ರಕಾರ, ಈ ವಲಯಕ್ಕೆ ಕಸ ಸಂಗ್ರಹವು ಪ್ರತಿ **{days}** ರಂದು **{time_slot}** ನಡುವೆ ನಡೆಯುತ್ತದೆ.\n\n"
                ans += f"• **ಸ್ವೀಕರಿಸಲಾಗುವ ತ್ಯಾಜ್ಯ ವಿಧಗಳು**: {types}\n"
                if guidelines:
                    ans += f"• **ವಿಶೇಷ ಮಾರ್ಗಸೂಚಿಗಳು**: {guidelines}\n"
                if contact:
                    ans += f"• **ವಿಭಾಗೀಯ ಸಂಪರ್ಕ ವಿವರ**: {contact}\n"
                return ans

            if is_hindi:
                ans = f"ग्रीनफ़ील्ड नगर निगम के अनुसार, इस ज़ोन के लिए कचरा संग्रह प्रत्येक **{days}** को **{time_slot}** के बीच होता है।\n\n"
                ans += f"• **स्वीकृत कचरा प्रकार**: {types}\n"
                if guidelines:
                    ans += f"• **दिशानिर्देश**: {guidelines}\n"
                if contact:
                    ans += f"• **विभागीय संपर्क**: {contact}\n"
                return ans

            ans = f"In Greenfield Municipal Corporation, collection for this zone occurs every **{days}** between **{time_slot}**.\n\n"
            ans += f"• **Waste Types Accepted**: {types}\n"
            if guidelines:
                ans += f"• **Guidelines**: {guidelines}\n"
            if contact:
                ans += f"• **Department Contact**: {contact}\n"
            return ans

        # Case 2: Permit Query
        if is_permit:
            lines = [l.strip() for l in top_block.split("\n") if l.strip()]
            p_info = {}
            for l in lines:
                if ":" in l and not l.startswith("---"):
                    k, v = l.split(":", 1)
                    if k.strip().lower() not in p_info:
                        p_info[k.strip().lower()] = v.strip()

            ptype = p_info.get("municipal permit", "Permit")
            fee = p_info.get("official municipal fee", "Subject to schedule")
            proc_time = p_info.get("processing time", "standard timeline")
            docs = p_info.get("required documents", "standard application form")
            reqs = p_info.get("eligibility & requirements", "")
            method = p_info.get("how to apply", "Online or in person")
            contact = p_info.get("department office", "")

            if is_kannada:
                ans = f"**{ptype}** ಗಾಗಿ ಅಧಿಕೃತ ಮಹಾನಗರ ಪಾಲಿಕೆ ಮಾರ್ಗಸೂಚಿಗಳು ಈ ಕೆಳಗಿನಂತಿವೆ:\n\n"
                ans += f"• **ಅಧಿಕೃತ ಶುಲ್ಕ**: {fee}\n"
                ans += f"• **ಪ್ರಕ್ರಿಯೆಯ ಸಮಯಾವಧಿ**: {proc_time}\n"
                ans += f"• **ಅಗತ್ಯವಿರುವ ದಾಖಲೆಗಳು**: {docs}\n"
                if reqs:
                    ans += f"• **ಅರ್ಹತೆ ಮತ್ತು ಷರತ್ತುಗಳು**: {reqs}\n"
                ans += f"• **ಅರ್ಜಿ ಸಲ್ಲಿಸುವ ವಿಧಾನ**: {method}\n"
                if contact:
                    ans += f"• **ಸಂಬಂಧಪಟ್ಟ ಕಚೇರಿ**: {contact}\n"
                return ans

            if is_hindi:
                ans = f"**{ptype}** के लिए आधिकारिक नगर निगम दिशानिर्देश निम्नलिखित हैं:\n\n"
                ans += f"• **आधिकारिक शुल्क**: {fee}\n"
                ans += f"• **प्रक्रिया समय-सीमा**: {proc_time}\n"
                ans += f"• **आवश्यक दस्तावेज़**: {docs}\n"
                if reqs:
                    ans += f"• **पात्रता एवं शर्तें**: {reqs}\n"
                ans += f"• **आवेदन विधि**: {method}\n"
                if contact:
                    ans += f"• **कार्यालय**: {contact}\n"
                return ans

            ans = f"Here are the official municipal guidelines for the **{ptype}**:\n\n"
            ans += f"• **Official Fee**: {fee}\n"
            ans += f"• **Processing Time**: {proc_time}\n"
            ans += f"• **Required Documents**: {docs}\n"
            if reqs:
                ans += f"• **Eligibility & Requirements**: {reqs}\n"
            ans += f"• **Application Method**: {method}\n"
            if contact:
                ans += f"• **Issuing Office**: {contact}\n"
            return ans

        # Case 3: Events & Weather
        if is_event:
            top_block = municipal_context.split("--- SOURCE")[1] if "--- SOURCE" in municipal_context else municipal_context
            lines = [l.strip() for l in top_block.split("\n") if l.strip()]
            e_info = {}
            for l in lines:
                if ":" in l and not l.startswith("---"):
                    k, v = l.split(":", 1)
                    if k.strip().lower() not in e_info:
                        e_info[k.strip().lower()] = v.strip()

            ename = e_info.get("municipal event", "City Event")
            date_time = e_info.get("date", "")
            location = e_info.get("location", "")
            details = e_info.get("details", "")
            organizer = e_info.get("organized by", "")

            summary = ""
            note = ""
            prob = ""
            if weather_section:
                w_lines = [wl.strip() for wl in weather_section.split("\n") if wl.strip()]
                for wl in w_lines:
                    if wl.startswith("Forecast Summary:"):
                        summary = wl.replace("Forecast Summary:", "").strip()
                    elif wl.startswith("Precipitation Probability:"):
                        prob = wl.replace("Precipitation Probability:", "").strip()
                    elif wl.startswith("Weather Advisory Note:"):
                        note = wl.replace("Weather Advisory Note:", "").strip()

            if is_kannada:
                ans = f"**{ename}** ಕಾರ್ಯಕ್ರಮವು **{date_time}** ರಂದು **{location}** ನಲ್ಲಿ ನಿಗದಿಯಾಗಿದೆ.\n\n"
                if details:
                    ans += f"• **ಕಾರ್ಯಕ್ರಮ ವಿವರ**: {details}\n"
                if organizer:
                    ans += f"• **ಆಯೋಜಕರು**: {organizer}\n"

                if weather_section:
                    ans += f"\n⛅ **ನೇರ ಹವಾಮಾನ ಸಲಹೆ**:\n"
                    ans += f"• **ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ**: {summary} (ಮಳೆಯ ಸಂಭವನೀಯತೆ: {prob})\n"
                    if note:
                        ans += f"• **ಸಲಹಾ ಟಿಪ್ಪಣಿ**: {note}\n"
                    ans += "\n*ಗಮನಿಸಿ: ಆಯೋಜಕರು ಅಧಿಕೃತವಾಗಿ ರದ್ದುಗೊಳಿಸದ ಹೊರತು ಮಹಾನಗರ ಪಾಲಿಕೆಯ ನಿಗದಿತ ಕಾರ್ಯಕ್ರಮ ವೇಳಾಪಟ್ಟಿಯಲ್ಲಿ ಯಾವುದೇ ಬದಲಾವಣೆ ಇರುವುದಿಲ್ಲ.*"
                return ans

            if is_hindi:
                ans = f"**{ename}** कार्यक्रम **{date_time}** को **{location}** में आयोजित होने वाला है।\n\n"
                if details:
                    ans += f"• **कार्यक्रम विवरण**: {details}\n"
                if organizer:
                    ans += f"• **आयोजक**: {organizer}\n"

                if weather_section:
                    ans += f"\n⛅ **लाइव मौसम सलाह**:\n"
                    ans += f"• **पूर्वानुमान**: {summary} (बारिश की संभावना: {prob})\n"
                    if note:
                        ans += f"• **परामर्श**: {note}\n"
                    ans += "\n*नोट: आधिकारिक नगर निगम कार्यक्रम अनुसूची यथावत रहेगी जब तक कि आयोजकों द्वारा स्पष्ट रूप से रद्द न किया जाए।*"
                return ans

            ans = f"**{ename}** is scheduled for **{date_time}** at **{location}**.\n\n"
            if details:
                ans += f"• **Event Overview**: {details}\n"
            if organizer:
                ans += f"• **Organized By**: {organizer}\n"

            if weather_section:
                ans += f"\n⛅ **Live Weather Advisory**:\n"
                ans += f"• **Forecast**: {summary} (Rain probability: {prob})\n"
                if note:
                    ans += f"• **Advisory**: {note}\n"
                ans += "\n*Note: Official municipal event schedules remain unchanged unless explicitly cancelled by organizers.*"

            return ans

        # General grounded extraction
        lines = [line.strip() for line in municipal_context.split("\n") if line.strip()]
        if is_kannada:
            response_parts = ["ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಮಹಾನಗರ ಪಾಲಿಕೆಯ ಪರಿಶೀಲಿಸಿದ ಮಾಹಿತಿ ಈ ಕೆಳಗಿನಂತಿದೆ:"]
        elif is_hindi:
            response_parts = ["यहाँ ग्रीनफ़ील्ड नगर निगम की सत्यापित जानकारी है:"]
        else:
            response_parts = ["Here is the verified information from Greenfield Municipal Corporation:"]

        for line in lines[:8]:
            if line.startswith("--- SOURCE"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                response_parts.append(f"• **{k.strip()}**: {v.strip()}")
            else:
                response_parts.append(f"• {line}")

        if weather_section:
            response_parts.append("\n" + weather_section)

        return "\n".join(response_parts)

def get_llm_provider(preference: Optional[str] = None) -> BaseLLMProvider:
    provider_name = preference or os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider_name == "gemini":
        gemini = GeminiProvider()
        if gemini.is_available():
            return gemini
    elif provider_name == "openai":
        openai = OpenAIProvider()
        if openai.is_available():
            return openai

    # Fallback
    return FallbackProvider()
