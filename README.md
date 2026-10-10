# 🏛️ CivicAssist – Greenfield Municipal Corporation AI Assistant

CivicAssist is an enterprise-grade, retrieval-augmented AI public service assistant built for **Greenfield Municipal Corporation**. It provides verified municipal information for waste collection, permits & licensing, city events, and live weather advisories with **trilingual support (English, हिन्दी, ಕನ್ನಡ)** and 0% hallucination guarantees.

---

## 🌟 Key Features

- **🌐 Trilingual Support**: Seamless English (`en`), Hindi (`hi`), and Kannada (`kn`) across the entire stack.
- **🗑️ Waste Management**: 11 residential & commercial waste collection zones (Zones A–K) with pickup schedules, material restrictions, and zone clarification handling.
- **📋 Permits & Licensing**: 12 municipal permits with exact fees, required documents, SLAs, and official departments.
- **📅 City Public Events**: 16 civic events, street closures, and cultural festivals with integrated live & seasonal weather forecasts.
- **🛡️ Robust Security Guardrails**: Prompt injection defense, out-of-scope service redirection (Passport, DMV), and zero hallucination on unlisted entities.
- **⚡ Dual Frontend Options**:
  - **Modern React + Vite UI**: Responsive interface with translation pills, interactive scenario shortcuts, citation drawer, and live system status badges.
  - **Streamlit Demo App**: Lightweight Python portal with preset demo flows.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+**

### 2. Environment Setup
Copy the example environment file:
```bash
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

Configure `.env` as needed:
```env
LLM_PROVIDER=gemini          # 'gemini', 'openai', or leave blank for deterministic fallback
GEMINI_API_KEY=              # Optional
OPENAI_API_KEY=              # Optional
WEATHERAPI_KEY=              # Optional
OPENWEATHER_API_KEY=         # Optional
VITE_API_BASE_URL=http://localhost:8000
```
> **Note**: Even without external API keys, CivicAssist operates out-of-the-box with a 100% grounded deterministic fallback engine and seasonal weather simulation.

### 3. Install Dependencies
```bash
# Python backend dependencies
pip install -r requirements.txt
pip install streamlit

# Node frontend dependencies
npm install
```

---

## 💻 Running the Application

### Option A: Full-Stack Web App (FastAPI + React)
1. **Start the FastAPI Backend**:
   ```bash
   python -m uvicorn backend.main:app --port 8000 --reload
   ```
2. **Start the React Frontend** (in a new terminal):
   ```bash
   npm run dev
   ```
3. Open `http://localhost:5173` in your browser.

### Option B: Streamlit Demo App
```bash
python -m streamlit run frontend/app.py
```
Open `http://localhost:8501` in your browser.

---

## 🧪 Testing & Evaluation

### Run Unit & Integration Tests (100% Passing)
```bash
python -m pytest tests/
```

### Run Benchmark Evaluation Suite (38 Queries)
```bash
python tests/test_queries.py
```
Outputs benchmark report to `evaluation/report.txt` and metric data to `evaluation/results.json`.

---

## 📁 Repository Structure

```text
├── backend/
│   └── main.py              # FastAPI REST API endpoints
├── data/
│   ├── waste_schedule.json  # 11 Municipal waste zones (A-K)
│   ├── permits.csv          # 12 Municipal permits & licensing rules
│   ├── events.json          # 16 City public events
│   └── validate_data.py     # Data integrity validator
├── evaluation/              # Benchmark reports & evaluation metrics
├── frontend/
│   └── app.py               # Streamlit application
├── src/
│   ├── conversation_memory.py # Multi-turn conversational session memory
│   ├── intent_router.py     # Indic cross-lingual intent classification
│   ├── llm_provider.py      # Gemini, OpenAI, & Grounded Fallback
│   ├── logger.py            # Audit & structured request logging
│   ├── rag.py               # Vector semantic retrieval pipeline
│   ├── response_generator.py# Main orchestrator & security guardrails
│   ├── schemas.py           # Pydantic data schemas
│   └── weather_service.py   # Meteorological API & fallback service
├── tests/                   # Pytest test suite & evaluation queries
├── .env.example             # Safe template for environment variables
├── .gitignore               # Comprehensive Git ignore rules (secrets protected)
└── package.json             # NPM dependencies & scripts
```
