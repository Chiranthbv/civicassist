import express from "express";
import { createServer as createViteServer } from "vite";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

async function startServer() {
  const app = express();
  const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

  app.use(express.json());

  // Health check - query FastAPI if available, else local fallback
  app.get("/api/health", async (req, res) => {
    try {
      const response = await fetch(`${FASTAPI_URL}/api/health`);
      if (response.ok) {
        const data = await response.json();
        return res.json(data);
      }
    } catch (e) {}

    res.json({
      status: "healthy",
      service: "CivicAssist Municipal AI Engine",
      municipality: "Greenfield Municipal Corporation",
      version: "1.0.0",
      backend: "fastapi-proxy"
    });
  });

  // Chat endpoint proxying to FastAPI backend
  app.post("/api/chat", async (req, res) => {
    try {
      const { query, session_id = "civicassist_default", language = "en" } = req.body;
      if (!query || typeof query !== "string") {
        return res.status(400).json({ error: "Query is required" });
      }

      const response = await fetch(`${FASTAPI_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, session_id, language })
      });

      const data = await response.json();
      return res.status(response.status).json(data);
    } catch (err) {
      console.error("FastAPI backend connection error:", err);
      const isKn = req.body?.language === "kn";
      const isHi = req.body?.language === "hi";
      const errMsg = isKn
        ? "ನಗರ ಪಾಲಿಕೆ ದಾಖಲೆಗಳ ಮಾಹಿತಿ ಕೋಶವನ್ನು ಸಂಪರ್ಕಿಸಲು ತಾತ್ಕಾಲಿಕ ಅಡಚಣೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು FastAPI ಬ್ಯಾಕೆಂಡ್ ಚಾಲನೆಯಲ್ಲಿದೆಯೇ ಎಂದು ಪರಿಶೀಲಿಸಿ, ಅಥವಾ ಗ್ರೀನ್‌ಫೀಲ್ಡ್ ಸಿಟಿ ಹಾಲ್ (555) 019-3000 ಗೆ ಕರೆ ಮಾಡಿ."
        : isHi
        ? "नगर निगम रिकॉर्ड तक पहुँचने में अस्थायी समस्या आ रही है। कृपया सत्यापित करें कि फ़ास्टएपीआई बैकएंड चल रहा है, या सिटी हॉल से (555) 019-3000 पर संपर्क करें।"
        : "I am having temporary trouble accessing municipal records. Please verify the FastAPI backend is running on port 8000, or contact Greenfield City Hall directly at (555) 019-3000.";

      return res.json({
        answer: errMsg,
        detected_intent: "UNKNOWN",
        confidence: "🔴 Low Confidence",
        confidence_score: 0.1,
        sources: [],
        response_latency_seconds: 0.05,
        session_id: req.body?.session_id || "web_session",
        language: req.body?.language || "en"
      });
    }
  });

  // Reset session endpoint proxying to FastAPI
  app.post("/api/reset-session", async (req, res) => {
    try {
      const { session_id = "civicassist_default" } = req.body;
      const response = await fetch(`${FASTAPI_URL}/api/reset-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id })
      });
      const data = await response.json();
      return res.json(data);
    } catch (e) {
      res.json({ status: "success", message: `Session reset.` });
    }
  });

  // Knowledge base endpoints
  app.get("/api/waste-schedule", async (req, res) => {
    try {
      const response = await fetch(`${FASTAPI_URL}/api/waste-schedule`);
      if (response.ok) {
        return res.json(await response.json());
      }
    } catch (e) {}

    try {
      const data = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "waste_schedule.json"), "utf-8"));
      res.json(data);
    } catch (err) {
      res.status(500).json({ error: "Failed to read waste schedule" });
    }
  });

  app.get("/api/waste-schedule/:zone", async (req, res) => {
    try {
      const response = await fetch(`${FASTAPI_URL}/api/waste-schedule/${encodeURIComponent(req.params.zone)}`);
      if (response.ok) {
        return res.json(await response.json());
      }
    } catch (e) {}

    res.status(404).json({ error: `Zone ${req.params.zone} not found` });
  });

  app.get("/api/permits", async (req, res) => {
    try {
      const response = await fetch(`${FASTAPI_URL}/api/permits`);
      if (response.ok) {
        return res.json(await response.json());
      }
    } catch (e) {}

    try {
      const csvData = fs.readFileSync(path.join(__dirname, "data", "permits.csv"), "utf-8");
      const lines = csvData.trim().split("\n");
      const headers = lines[0].split(",");
      const permits = lines.slice(1).map((line) => {
        const match = line.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g);
        const row: Record<string, string> = {};
        headers.forEach((h, i) => {
          row[h.trim()] = (match && match[i] ? match[i].replace(/^"|"$/g, "") : "").trim();
        });
        return row;
      });
      res.json(permits);
    } catch (err) {
      res.status(500).json({ error: "Failed to read permits" });
    }
  });

  app.get("/api/events", async (req, res) => {
    try {
      const response = await fetch(`${FASTAPI_URL}/api/events`);
      if (response.ok) {
        return res.json(await response.json());
      }
    } catch (e) {}

    try {
      const data = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "events.json"), "utf-8"));
      res.json(data);
    } catch (err) {
      res.status(500).json({ error: "Failed to read events" });
    }
  });

  app.get("/api/evaluation", async (req, res) => {
    try {
      const response = await fetch(`${FASTAPI_URL}/api/evaluation`);
      if (response.ok) {
        return res.json(await response.json());
      }
    } catch (e) {}

    try {
      const jsonResults = JSON.parse(fs.readFileSync(path.join(__dirname, "evaluation", "results.json"), "utf-8"));
      const reportTxt = fs.readFileSync(path.join(__dirname, "evaluation", "report.txt"), "utf-8");
      res.json({ results: jsonResults, report: reportTxt });
    } catch (err) {
      res.status(500).json({ error: "Evaluation data not found" });
    }
  });

  // Mount Vite middleware in development
  const vite = await createViteServer({
    server: { middlewareMode: true },
    appType: "spa"
  });
  app.use(vite.middlewares);

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`CivicAssist Municipal Server listening on port ${PORT} (FastAPI proxy: ${FASTAPI_URL})`);
  });
}

startServer();
