"""
Spam Shield API.

Contract consumed by design/index.html:
    GET  /            frontend (served from this same service)
    GET  /health
    POST /predict   {"text": "..."}
        -> confidence, verdict, signals[{label, severity, weight}],
           model_version, latency_ms

Additive fields the current UI ignores but a future version can render:
    language, script, distractor_keywords, probabilities, rules_fired

PRIVACY: message bodies are processed in memory only. Application code does not
write them to disk or include them in responses/errors. Uvicorn access logs may
record request paths and status codes, but not request bodies.

Deploy: Render Web Service.
    build:  pip install -r backend/requirements.txt
    start:  uvicorn main:app --host 0.0.0.0 --port $PORT   (from backend/)
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from predictor import get_predictor  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = FastAPI(
    title="Spam Shield API",
    version="1.0",
    description="Multilingual SMS / OTP scam and spam classifier "
                "(English, Hinglish, Hindi, Tenglish).",
)


@app.get("/assets/logo.png", include_in_schema=False)
def logo_asset():
    """Serve the brand logo from a stable root-relative URL."""
    return FileResponse(os.path.join(ROOT, "design", "assets", "logo.png"),
                        media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})

# The frontend may be served from a different origin than the API during
# development; tighten to the deployed origin once the Render URL is known.
_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,"
    "http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class MessageIn(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    text: str = Field(...,
                      description="Raw SMS / message text to classify")

    @field_validator("text", mode="before")
    @classmethod
    def enforce_length_limit(cls, value):
        if isinstance(value, str) and len(value) > 10_000:
            raise HTTPException(status_code=413, detail="message too long")
        return value

    @field_validator("text")
    @classmethod
    def trim_and_reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must be a non-empty string")
        return value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, _exc):
    # Do not echo submitted message text in validation responses.
    return JSONResponse({"detail": "text must be a non-empty string"}, status_code=422)


@app.on_event("startup")
def load_model():
    p = get_predictor()
    if p.loaded:
        print(f"[startup] model loaded: {p.meta.get('model_version')} "
              f"({p.meta.get('training_rows')} training rows)")
    else:
        print(f"[startup] MODEL FAILED TO LOAD: {p.load_error}")


@app.get("/health")
def health():
    p = get_predictor()
    return JSONResponse(p.health(), status_code=200 if p.loaded else 503)


@app.post("/predict")
def predict(msg: MessageIn):
    p = get_predictor()
    started = time.perf_counter()
    try:
        result = p.predict(msg.text)
    except Exception:                            # noqa: BLE001
        return JSONResponse(
            {"error": "prediction_failed", "detail": "Prediction unavailable"},
            status_code=500,
        )
    result.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 2))
    status = 200 if result.get("verdict") is not None else 503
    return JSONResponse(result, status_code=status)


@app.get("/api", include_in_schema=False)
def api_info():
    p = get_predictor()
    return {
        "service": "spam-shield-api",
        "model_loaded": p.loaded,
        "model_version": p.meta.get("model_version", "unknown"),
        "evaluation_status": p.meta.get(
            "evaluation_status", "indicative_single_annotator_reviewed"),
        "endpoints": ["/health", "/predict"],
        "note": "No accuracy figure is published. The reported score comes from "
                "a human-labelled test set that no model was tuned on.",
    }


@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
def frontend():
    """Serve the frontend at the server's main address and at the legacy /app path."""
    return FileResponse(os.path.join(ROOT, "design", "index.html"),
                        media_type="text/html")
