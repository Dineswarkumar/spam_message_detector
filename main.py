import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from scoring import compute_risk

app = FastAPI()

# Enable CORS
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load trained model

try:
    model = joblib.load("model.pkl")
    print("Model loaded successfully")
except:
    model = None
    print("Model not found. Train model first.")

# Serve frontend files

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    return FileResponse("static/index.html")


# Request schema

class Message(BaseModel):
    text: str


# Fraud prediction API

@app.post("/api/predict")
def predict(msg: Message):

    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        prediction = model.predict([msg.text])[0]
        probabilities = model.predict_proba([msg.text])[0]

        spam_index = list(model.classes_).index('spam')
        ml_confidence = probabilities[spam_index]

        risk = compute_risk(ml_confidence, msg.text)

        if risk > 70:
            status = "Fraud"
        elif risk > 40:
            status = "Suspicious"
        else:
            status = "Safe"

        return {
            "status": status,
            "risk_score": risk,
            "confidence": float(ml_confidence),
            "text": msg.text
        }

    except Exception as e:
        print("Prediction error:", e)
        raise HTTPException(status_code=500, detail="Prediction failed")