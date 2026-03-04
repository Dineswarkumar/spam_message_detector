from rules import rule_score

def compute_risk(ml_confidence,text):

    ml_score = ml_confidence * 100
    rule = rule_score(text)

    # Allow ML score to stand out while rules boost it. Cap at 100.
    risk = min(100, ml_score + rule)

    return round(risk)