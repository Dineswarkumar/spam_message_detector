# RakshaSutra v2 — Hybrid Multilingual Fraud Intelligence Platform

> Phase 2 | IIT Hackathon | Fraud Detection for India's Digital Landscape

## What's New in Phase 2

| Feature | Phase 1 | Phase 2 |
|---|---|---|
| Languages | 3 (EN, HI, TE) | **8** (EN, HI, HI-EN, MR, TE, TA, BN, GU) |
| ML Model | TF-IDF + LogReg | **Multilingual Transformer + XGBoost** |
| Dataset | ~420 samples | **1200+ samples** |
| Explainability | None | **Full — shows WHY flagged** |
| Rule engine | 6 keywords | **15 pattern categories** |
| API endpoints | 1 | **3 (predict, batch, health)** |

## Architecture

```
User Message
    │
    ▼
┌─────────────────────────────────────────────────┐
│         FEATURE EXTRACTION                       │
│  paraphrase-multilingual-MiniLM-L12-v2           │
│  (384-dim embeddings — handles all Indian langs) │
└───────────────────┬─────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    ▼                               ▼
┌─────────────┐           ┌─────────────────────┐
│  XGBoost    │           │  Rule Engine (15     │
│  Classifier │           │  categories, 8 langs)│
│  (ML Score) │           │  (Rule Score 0-60)   │
└──────┬──────┘           └──────────┬──────────┘
       │                             │
       └──────────┬──────────────────┘
                  ▼
        ┌──────────────────┐
        │  Hybrid Scorer   │
        │  risk = ML*55 +  │
        │  rule_score      │
        └────────┬─────────┘
                 │
        ┌────────┴────────┐
        │  RiskReport      │
        │  • status        │
        │  • risk_score    │
        │  • reasons[]     │ ← Explainability
        │  • flags[]       │
        │  • verdict       │
        └──────────────────┘
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train model (first time only, ~2-3 minutes)
python train_model.py

# 3. Start server
uvicorn main:app --reload
```

Open browser: http://127.0.0.1:8000

## API Endpoints

### POST /api/predict
```json
{
  "text": "Aapka SBI account band hoga. OTP share karein abhi"
}
```
Response:
```json
{
  "status": "Fraud",
  "risk_score": 87,
  "ml_confidence": 0.94,
  "rule_score": 47,
  "flags": ["account_threat", "credential_phishing", "urgency"],
  "reasons": [
    "Account blocking / suspension threat",
    "Requesting sensitive financial credentials (OTP/PIN/bank details)",
    "High-pressure urgency / time-limit tactics"
  ],
  "breakdown": {"ml_component": 52, "rule_component": 47, "total": 87},
  "verdict": "This message shows strong signs of fraud. Do NOT share any details.",
  "language": "Hindi"
}
```

### POST /api/batch_predict
Analyze up to 50 messages at once (for demo purposes).

### GET /health
Returns model status.

## Supported Languages
English · Hindi · Hinglish · Marathi · Telugu · Tamil · Bengali · Gujarati

## Tech Stack
- **Backend**: Python + FastAPI
- **ML**: sentence-transformers (multilingual MiniLM) + XGBoost
- **Rule Engine**: 15 fraud pattern categories, regex-based, multilingual
- **Frontend**: HTML/CSS/JS (unchanged from Phase 1)
- **Deployment**: Render / Railway / any Python host
