"""
main.py  Phase 2 — RakshaSutra FastAPI Backend
Full explainability + language detection + real-time prediction
"""
import joblib, os, re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from scoring import compute_risk

app = FastAPI(title="RakshaSutra API", version="2.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── Load model ────────────────────────────────────────────────────────────────
model_payload  = None
embedder       = None

try:
    model_payload = joblib.load("model.pkl")
    if model_payload.get("use_transformers"):
        embedder = joblib.load("embedder.pkl")
    print("[OK] Model loaded")
except Exception as e:
    print(f"[WARN] Model not loaded: {e}. Run train_model.py first.")

# ── Static frontend ──────────────────────────────────────────────────────────
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model_payload is not None,
            "transformer_mode": model_payload.get("use_transformers", False) if model_payload else False}

# ── Request schema ────────────────────────────────────────────────────────────
class Message(BaseModel):
    text: str

# ── Simple language detector ──────────────────────────────────────────────────
def detect_language(text: str) -> str:
    ranges = {
        "Hindi":    (0x0900, 0x097F),
        "Bengali":  (0x0980, 0x09FF),
        "Gujarati": (0x0A80, 0x0AFF),
        "Punjabi":  (0x0A00, 0x0A7F),
        "Telugu":   (0x0C00, 0x0C7F),
        "Kannada":  (0x0C80, 0x0CFF),
        "Tamil":    (0x0B80, 0x0BFF),
        "Malayalam":(0x0D00, 0x0D7F),
    }
    counts = {lang: 0 for lang in ranges}
    for ch in text:
        cp = ord(ch)
        for lang, (lo, hi) in ranges.items():
            if lo <= cp <= hi:
                counts[lang] += 1
    best_lang = max(counts, key=counts.get)
    if counts[best_lang] > 2:
        return best_lang
    return "English/Hinglish"

# ── Predict endpoint ──────────────────────────────────────────────────────────
@app.post("/api/predict")
def predict(msg: Message):
    if not model_payload:
        raise HTTPException(status_code=503, detail="Model not loaded. Run train_model.py first.")

    text = msg.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text cannot be empty.")

    try:
        clf = model_payload["classifier"]
        le  = model_payload["label_encoder"]

        if model_payload.get("use_transformers") and embedder:
            vec  = embedder.encode([text])
            pred = clf.predict(vec)[0]
            prob = clf.predict_proba(vec)[0]
        else:
            vec  = [text]
            pred = clf.predict(vec)[0]
            prob = clf.predict_proba(vec)[0]

        spam_idx     = list(le.classes_).index("spam")
        ml_confidence = float(prob[spam_idx])

        report = compute_risk(ml_confidence, text)

        return {
            "status":        report.status,
            "risk_score":    report.risk_score,
            "ml_confidence": report.ml_confidence,
            "rule_score":    report.rule_score,
            "flags":         report.flags,
            "reasons":       report.reasons,
            "breakdown":     report.breakdown,
            "verdict":       report.verdict,
            "language":      detect_language(text),
            "text":          text,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

# ── Batch analysis endpoint (for demo) ───────────────────────────────────────
class BatchRequest(BaseModel):
    messages: list[str]

@app.post("/api/batch_predict")
def batch_predict(req: BatchRequest):
    if not model_payload:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    if len(req.messages) > 50:
        raise HTTPException(status_code=400, detail="Max 50 messages per batch.")

    results = []
    for text in req.messages:
        try:
            r = predict(Message(text=text))
            results.append(r)
        except Exception as e:
            results.append({"error": str(e), "text": text})
    return {"results": results, "total": len(results),
            "fraud_count": sum(1 for r in results if r.get("status")=="Fraud"),
            "suspicious_count": sum(1 for r in results if r.get("status")=="Suspicious")}
