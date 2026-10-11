# Spam Shield API contract

The FastAPI service loads the fitted pipeline from `backend/artifacts/model.joblib`.
`backend/train.py` exports the model and its metadata to that location; runtime
predictions use that same artifact through `backend/predictor.py`.

## Run locally

Run `start_spam_shield.ps1` from the project root to start the backend and open
the frontend automatically. Keep the launcher window open while using the app.

For manual startup, from `backend/`:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` to use the frontend and API on the same origin.
`/app` remains an alias for the same page; `/api` shows service information.

## `POST /predict`

Request:

```json
{"text":"Your OTP is 482910. Do not share it with anyone."}
```

Text is trimmed, must be non-empty, and is limited to 10,000 characters.
Whitespace-only or malformed input returns `422`; overlong input returns `413`.
Request bodies and validation input are not included in application responses or
application-generated logs.

Successful response fields:

| Field | Meaning |
|---|---|
| `verdict` | `legitimate`, `marketing_spam`, or `scam` — model's highest-probability class |
| `confidence` | Probability of the winning class; this is not scam probability |
| `probabilities` | Per-class probabilities, including `scam`; the frontend uses `probabilities.scam` for its threat bar |
| `signals` | Model/rule/system explanations with label, severity, weight, source, and description |
| `language`, `script` | Runtime language/script estimate |
| `distractor_keywords` | Risky-looking terms reported separately from the verdict |
| `rules_fired` | Names of additive rule signals |
| `model_version`, `latency_ms`, `evaluation_status` | Artifact identity, inference duration, and evaluation caveat |

The frontend trusts the returned three-class verdict. It does not reinterpret
the winning-class confidence as a scam score. If the API cannot be reached or
the model is unavailable, the page clearly labels its local keyword estimate as
demo heuristics.

## `GET /health`

Returns `model_loaded`, `model_version`, supported classes, training row count,
and `evaluation_status`. It returns HTTP `503` if the model artifact failed to load.
The UI only labels the backend live when the model is loaded.

## `GET /app`

Serves `design/index.html` from the API service at the main URL, so local use and
a single-service deployment keep the page and prediction API on one origin.
The same page is served at `/`.

The design assets folder is served at `/assets/` (including `/assets/logo.png`).

## `GET /api`

Returns service information (model loaded, version, and evaluation status).

## Deployment notes

Set `CORS_ORIGINS` to a comma-separated list of exact frontend origins only when
the frontend is hosted separately. Same-origin use through `/app` does not need
CORS. The service does not publish final-test accuracy as a health/API metric;
the model metadata explicitly records that the human-labelled evaluation remains
indicative and requires review.
