"""
rules.py  Phase 2 — Enhanced multilingual rule engine with full explainability
Languages: English, Hindi, Hinglish, Marathi, Telugu, Tamil, Bengali, Gujarati
"""
import re
from dataclasses import dataclass, field
from typing import List


PATTERNS = [
    {"regex": r"(lottery|lucky draw|jackpot|prize|winner|won|reward|jeeta|inaam|jeekla|bahumaan|venchurukkeerkal|jitya)",
     "score": 15, "category": "prize_bait", "reason": "Lottery / prize bait detected"},

    {"regex": r"(otp|pin\b|password|bank details|account number|cvv|card number|bank info|bank mahiti|bank detail)",
     "score": 20, "category": "credential_phishing", "reason": "Requesting sensitive financial credentials (OTP/PIN/bank details)"},

    {"regex": r"(urgent|immediately|within 24 hour|today only|act fast|hurry|last chance|expires today|turant|tatkal|abhi\b|jaldi|aaj hi|AVASARAM|ekhoni|taatkaL|ippudu|ippave|tatkalik|24 manikku|24 ghontay|24 kaLak|24 taasant)",
     "score": 12, "category": "urgency", "reason": "High-pressure urgency / time-limit tactics"},

    {"regex": r"(account.{0,12}block|account.{0,12}suspend|account.{0,12}band|kyc.{0,10}expir|khate band|band hoil|band hoga|band avutundi|block aagidum|band thase|band hoye)",
     "score": 15, "category": "account_threat", "reason": "Account blocking / suspension threat"},

    {"regex": r"(kyc|aadhaar|aadhar|pan card|pan.{0,6}expir|pan.{0,6}cancel|pan.{0,6}deactivat)",
     "score": 12, "category": "kyc_lure", "reason": "KYC / Aadhaar / PAN card scam"},

    {"regex": r"(https?://|bit\.ly|tinyurl|rb\.gy|cutt\.ly|t\.me/|wa\.me/|click here|click the link|click now|click karo|is link par)",
     "score": 18, "category": "suspicious_link", "reason": "Suspicious shortened URL or phishing link"},

    {"regex": r"(whatsapp.{0,10}\d{10}|\b\d{10}\b|call karein abhi|call karo abhi|call pannunga tatkal|call cheyyandi tatkal)",
     "score": 10, "category": "phone_lure", "reason": "Suspicious phone / WhatsApp contact request"},

    {"regex": r"(guaranteed return|100%.{0,10}return|double.{0,12}money|paise double|double karein|double karo|returns guaranteed|profit guaranteed)",
     "score": 14, "category": "investment_fraud", "reason": "'Guaranteed returns' investment fraud pattern"},

    {"regex": r"(government scheme|sarkar yojana|pm.{0,10}yojana|govt scheme|pradhan mantri|prime minister.{0,10}scheme)",
     "score": 12, "category": "govt_impersonation", "reason": "Government impersonation scam"},

    {"regex": r"(electricity.{0,15}cut|bijli.{0,10}kat|power.{0,10}disconnect|vij.{0,10}tutil|bijli connection|light.{0,10}katase)",
     "score": 12, "category": "utility_threat", "reason": "Fake electricity / utility disconnection threat"},

    {"regex": r"(police.{0,15}complaint|police.{0,15}case|fir.{0,10}register|arrest|legal notice|court notice|police farad)",
     "score": 15, "category": "legal_threat", "reason": "Fake police / legal threat"},

    {"regex": r"(free iphone|free mobile|free smartphone|muft mobile|muft iphone|free.{0,10}gift|free milega|get free now)",
     "score": 10, "category": "free_offer", "reason": "'Free gift' bait offer"},

    {"regex": r"(no documents|document nahi|document laagat nahi|document nathi|instant loan|loan.{0,15}minute|loan.{0,15}approve|without.{0,10}document)",
     "score": 12, "category": "loan_fraud", "reason": "No-document instant loan scam"},

    {"regex": r"(work from home|ghar baithe|ghar se kaam|ghar basat|intilo unchi|veedu irundhe|ghare baesine|per month.{0,20}earn|earn.{0,20}per month|rs.{0,8}\d+.{0,8}per hour)",
     "score": 10, "category": "wfh_fraud", "reason": "Suspicious work-from-home income offer"},
]


@dataclass
class RuleResult:
    score:      int       = 0
    flags:      List[str] = field(default_factory=list)
    reasons:    List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)


def analyze(text: str) -> RuleResult:
    t      = text.lower()
    result = RuleResult()
    seen   = set()
    for p in PATTERNS:
        if p["category"] in seen:
            continue
        if re.search(p["regex"], t, re.IGNORECASE):
            result.score += p["score"]
            result.flags.append(p["category"])
            result.reasons.append(p["reason"])
            result.categories.append(p["category"])
            seen.add(p["category"])
    result.score = min(result.score, 60)
    return result
