import re

fraud_keywords = [
"lottery","reward","prize","upi","otp","kyc","urgent",
"verify","account blocked","click link","job offer",
"लाख","जीते","तुरंत","भेजो","గెలిచారు","డబ్బు",
"లాటరీ","గెలుచుకున్నారు","బ్యాంక్","వివరాలను","పంపండి","బహుమతి"
]

def rule_score(text):

    text = text.lower()
    score = 0

    for word in fraud_keywords:
        if word in text:
            score += 10

    if re.search(r"http", text):
        score += 20

    if re.search(r"\b\d{10}\b", text):
        score += 15

    return min(score,50)