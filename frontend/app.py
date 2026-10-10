"""
CivicAssist - Streamlit Frontend for Greenfield Municipal Corporation.
Provides a clean, professional municipal portal UI with quick demo scenario triggers,
interactive chat, source citation drawers, confidence indicators, and knowledge base explorers.
"""

import os
import sys
import json

# Ensure project root in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.response_generator import CivicResponseGenerator

def run_streamlit_app():
    try:
        import streamlit as st
    except ImportError:
        print("Streamlit not installed. Run 'pip install streamlit' to launch this UI.")
        return

    st.set_page_config(
        page_title="CivicAssist — Greenfield Municipal Corporation",
        page_icon="🏛️",
        layout="wide"
    )

    # Custom styling
    st.markdown("""
        <style>
        .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0px; }
        .sub-header { font-size: 1rem; color: #4B5563; margin-bottom: 20px; }
        .metric-card { background-color: #F3F4F6; padding: 15px; border-radius: 8px; border-left: 4px solid #2563EB; }
        .source-box { background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 10px; border-radius: 6px; margin-top: 8px; font-size: 0.85rem; }
        .confidence-high { color: #16A34A; font-weight: 600; }
        .confidence-med { color: #D97706; font-weight: 600; }
        .confidence-low { color: #DC2626; font-weight: 600; }
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "generator" not in st.session_state:
        st.session_state.generator = CivicResponseGenerator()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = "streamlit_citizen_session"
    if "selected_language" not in st.session_state:
        st.session_state.selected_language = "en"

    # Sidebar: Knowledge Base & Quick Demo Scenarios
    with st.sidebar:
        st.image("https://images.unsplash.com/photo-1577495508048-b635879837f1?auto=format&fit=crop&w=300&q=80", caption="City Hall - Greenfield", use_container_width=True)
        st.title("🏛️ CivicAssist Portal")
        st.markdown("**Greenfield Municipal Corporation**")
        st.caption("AI-Powered Public Service FAQ & Information System")
        st.divider()

        # Language Selector
        lang_choice = st.selectbox(
            "🌐 Language / भाषा / ಭಾಷೆ",
            options=["English", "हिन्दी (Hindi)", "ಕನ್ನಡ (Kannada)"],
            index=0 if st.session_state.selected_language == "en" else (1 if st.session_state.selected_language == "hi" else 2)
        )
        current_lang = "en" if "English" in lang_choice else ("hi" if "Hindi" in lang_choice else "kn")
        st.session_state.selected_language = current_lang

        st.subheader("🎯 Guided Demo Scenarios")
        st.caption("Click to test the TCS Technology Day demo sequence:")

        if current_lang == "kn":
            if st.button("1️⃣ ಕಸ ಸಂಗ್ರಹ: ವಲಯ ಎ", use_container_width=True):
                st.session_state.preset_query = "ವಲಯ ಎ ನಲ್ಲಿ ಕಸ ಯಾವಾಗ ಸಂಗ್ರಹಿಸಲಾಗುತ್ತದೆ?"
            if st.button("2️⃣ ಮುಂದಿನ ವಿಚಾರಣೆ: ಮುಂದಿನ ವಾರ?", use_container_width=True):
                st.session_state.preset_query = "ಮುಂದಿನ ವಾರದ ಬಗ್ಗೆ ಏನು?"
            if st.button("3️⃣ ಪರವಾನಗಿ: ಆಹಾರ ವ್ಯಾಪಾರ", use_container_width=True):
                st.session_state.preset_query = "ಆಹಾರ ವ್ಯಾಪಾರ ಪರವಾನಗಿಗೆ ಯಾವ ದಾಖಲೆಗಳು ಬೇಕು?"
            if st.button("4️⃣ ಕಾರ್ಯಕ್ರಮ: ನಗರದ ಮ್ಯಾರಥಾನ್", use_container_width=True):
                st.session_state.preset_query = "ನಗರದ ಮ್ಯಾರಥಾನ್ ಎಲ್ಲಿ ನಡೆಯಲಿದೆ?"
            if st.button("5️⃣ ಹವಾಮಾನ: ಮ್ಯಾರಥಾನ್ ಸಲಹೆ", use_container_width=True):
                st.session_state.preset_query = "ಹವಾಮಾನವು ಸಿಟಿ ಮ್ಯಾರಥಾನ್ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರುತ್ತದೆಯೇ?"
            if st.button("6️⃣ ಭ್ರಮೆ ತಡೆ: ವಲಯ ಝಡ್", use_container_width=True):
                st.session_state.preset_query = "ವಲಯ ಝಡ್ (Zone Z) ನ ಬಗ್ಗೆ ಏನು?"
        elif current_lang == "hi":
            if st.button("1️⃣ Waste Schedule: Zone A (कचरा)", use_container_width=True):
                st.session_state.preset_query = "ज़ोन ए में कचरा कब उठाया जाता है?"
            if st.button("2️⃣ Follow-Up: अगले हफ़्ते?", use_container_width=True):
                st.session_state.preset_query = "अगले हफ़्ते के बारे में क्या?"
            if st.button("3️⃣ Permit: खाद्य व्यापार परमिट", use_container_width=True):
                st.session_state.preset_query = "खाद्य व्यवसाय परमिट के लिए कौन से दस्तावेज़ चाहिए?"
            if st.button("4️⃣ Event: सिटी मैराथन", use_container_width=True):
                st.session_state.preset_query = "सिटी मैराथन कहाँ आयोजित होगी?"
            if st.button("5️⃣ Weather: मैराथन मौसम सलाह", use_container_width=True):
                st.session_state.preset_query = "क्या मौसम सिटी मैराथन को प्रभावित करेगा?"
            if st.button("6️⃣ Edge Case: ज़ोन ज़ेड (Zone Z)", use_container_width=True):
                st.session_state.preset_query = "ज़ोन ज़ेड (Zone Z) के बारे में क्या?"
        else:
            if st.button("1️⃣ Waste Schedule: Zone A", use_container_width=True):
                st.session_state.preset_query = "When is garbage collected in Zone A?"
            if st.button("2️⃣ Follow-Up: Next Week?", use_container_width=True):
                st.session_state.preset_query = "What about next week?"
            if st.button("3️⃣ Permit: Food Business", use_container_width=True):
                st.session_state.preset_query = "What documents do I need for a food business permit?"
            if st.button("4️⃣ Event: City Marathon", use_container_width=True):
                st.session_state.preset_query = "Where is the city marathon?"
            if st.button("5️⃣ Weather: Marathon Advisory", use_container_width=True):
                st.session_state.preset_query = "Will the weather affect the city marathon?"
            if st.button("6️⃣ Edge Case: Zone Z", use_container_width=True):
                st.session_state.preset_query = "What about Zone Z?"

        st.divider()
        if st.button("🗑️ Clear Conversation History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.generator.clear_session(st.session_state.session_id)
            st.rerun()

    # Main Area
    st.markdown('<div class="main-header">Greenfield Municipal Citizen Services</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Official FAQ Chatbot for Residential Waste, Commercial Permits, Community Events & Live Weather Advisories</div>', unsafe_allow_html=True)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**Waste Management**\n11 Service Zones (A–K)")
    with col2:
        st.markdown("**Permits & Licensing**\n12 Regulated Categories")
    with col3:
        st.markdown("**Public Schedules**\n16 Verified City Events")
    with col4:
        st.markdown("**Engine Accuracy**\n96.88% Benchmark Score")

    st.divider()

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander("📚 Sources Used & Confidence Details"):
                    st.write(f"**Confidence**: {msg.get('confidence', 'N/A')}")
                    st.write(f"**Detected Intent**: `{msg.get('intent', 'UNKNOWN')}`")
                    st.write(f"**Response Latency**: {msg.get('latency', 0.0)}s")
                    for s in msg["sources"]:
                        st.markdown(f"• **{s['title']}** (`{s['source_file']}`) — Relevance: {int(s['relevance_score'] * 100)}%")
                        st.caption(f"Snippet: {s['text_snippet']}")

            if "weather" in msg and msg["weather"]:
                w = msg["weather"]
                st.info(f"⛅ **Weather Advisory**: {w['forecast_summary']} | Rain Probability: {w['rain_probability']}%\n\n{w['advisory_note']}")

    # Handle Input
    placeholder_text = (
        "ಕಸ ಸಂಗ್ರಹ, ಪರವಾನಗಿಗಳು ಅಥವಾ ನಗರ ಕಾರ್ಯಕ್ರಮಗಳ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ..."
        if st.session_state.selected_language == "kn"
        else (
            "कचरा संग्रह, परमिट या शहर के कार्यक्रमों के बारे में प्रश्न पूछें..."
            if st.session_state.selected_language == "hi"
            else "Ask a question about garbage collection, building/food permits, or city events..."
        )
    )
    query_input = st.chat_input(placeholder_text)

    active_query = None
    if query_input:
        active_query = query_input
    elif "preset_query" in st.session_state and st.session_state.preset_query:
        active_query = st.session_state.preset_query
        st.session_state.preset_query = None

    if active_query:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": active_query})
        with st.chat_message("user"):
            st.markdown(active_query)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Searching Greenfield Municipal Knowledge Base..."):
                response = st.session_state.generator.process_query(
                    active_query,
                    session_id=st.session_state.session_id,
                    language=st.session_state.selected_language
                )

            st.markdown(response.answer)

            # Sources drawer
            if response.sources:
                with st.expander("📚 Sources Used & Confidence Details"):
                    st.write(f"**Confidence**: {response.confidence.value}")
                    st.write(f"**Detected Intent**: `{response.detected_intent.value}`")
                    st.write(f"**Response Latency**: {round(response.response_latency_seconds, 3)}s")
                    for s in response.sources:
                        st.markdown(f"• **{s.title}** (`{s.source_file}`) — Relevance: {int(s.relevance_score * 100)}%")
                        st.caption(f"Snippet: {s.text_snippet}")

            # Weather info
            if response.weather_info:
                w = response.weather_info
                st.info(f"⛅ **Weather Advisory**: {w.forecast_summary} | Rain Probability: {w.rain_probability}%\n\n{w.advisory_note}")

            st.session_state.messages.append({
                "role": "assistant",
                "content": response.answer,
                "confidence": response.confidence.value,
                "intent": response.detected_intent.value,
                "latency": round(response.response_latency_seconds, 3),
                "sources": [s.to_dict() for s in response.sources],
                "weather": response.weather_info.to_dict() if response.weather_info else None
            })

if __name__ == "__main__":
    run_streamlit_app()
