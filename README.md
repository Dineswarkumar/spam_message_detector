# RakshaSutra — Hybrid Multilingual Fraud Intelligence Platform

**Note: This project is a demo/prototype built for hackathon and exhibition purposes.** 

RakshaSutra is a hybrid multilingual platform designed to detect scam messages, decode psychological manipulation, and help map fraud patterns. It was built focusing on India's digital landscape where fraudsters exploit linguistic diversity and psychological vulnerabilities.

## 🚀 Features
- **Multilingual Fraud Detection**: Uses machine learning to detect scams in multiple languages (Hindi, English, Hinglish).
- **Rule-based & Psycholinguistic Analysis**: Looks for manipulation triggers (urgency, fear, impersonation, reward baiting).
- **Explainable Risk Scoring**: Generates an actionable risk score combining ML confidence and defined rules.
- **REST API**: Built with **FastAPI** to serve the `scikit-learn` prediction model.
- **Interactive UI**: A sleek, vanilla HTML/CSS/JS frontend to test messages in real-time.

## 🛠️ Technology Stack
- **Backend:** Python + FastAPI 
- **Machine Learning:** `scikit-learn` (Logistic Regression + TF-IDF Vectorizer) + `pandas`
- **Frontend:** HTML, CSS, JavaScript
- **Deployment:** Render (Web Service)

---
**deployed online---https://spam-message-detector-mk6g.onrender.com/static/index.html**
## 💻 How to Run Locally

### Prerequisites
Make sure you have Python 3 installed. 

### 1. Clone the repository
```bash
git clone https://github.com/Dineswarkumar/spam_message_detector.git
cd spam_message_detector
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. (Optional) Train the Model
If you need to regenerate the `model.pkl` file from the CSV datasets, run:
```bash
python train_model.py
```

### 4. Start the FastAPI Server
```bash
uvicorn main:app --reload
```
The server will start locally. By default, you can access the frontend by opening your browser to:
**http://127.0.0.1:8000**

---

## 🌐 Live Demo
The API model and frontend are currently serving live at:
(https://spam-message-detector-mk6g.onrender.com/static/index.html)

