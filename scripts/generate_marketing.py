"""
Supplementary generator: marketing_spam in Indian languages, plus Tenglish.

Why this file exists
--------------------
The main generator (generate_synthetic.py) only produced legitimate/scam. When
the corpus was assembled into three classes, marketing_spam came out as 1,060
rows -- all English, zero in Hindi/Telugu/Hinglish/Tenglish. A class with no
multilingual coverage cannot support any per-language claim, and marketing_spam
is the class most likely to appear in real Indian inboxes.

Tenglish (Telugu in Roman letters) had exactly ONE row across the entire real
corpus, and zero generated rows. This file adds both.

Grounding: marketing_spam templates follow the structures actually observed in
the Indian 2011 crowdsourced corpus (quiz promos, TV channel offers, real
estate, project/consultancy offers, bulk rate-card ads) and in UCI spam
(referential ads, prize claims with no money demand, job offers).
"""
import argparse
import csv
import pathlib
import random
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Marketing templates. id -> category -> {lang: text}
# These are BULK PROMOTIONS: no OTP, no KYC, no account demand, no link that
# asks for credentials, no police. If a template ever needs a money demand it
# belongs in the scam set, not here.
MARKETING_TEMPLATES = [
    # quiz / horoscope style -- the single most common Indian bulk spam shape
    ("mk01", "quiz_promo", {
        "en": "FREE QUIZ! Reply 1 for Horoscope, 2 for Suvichar, 3 for Love, 4 for Career. Charges Rs 1 per SMS. Reply STOP to unsubscribe.",
        "hinglish": "FREE QUIZ! Reply karein - 1 Horoscope, 2 Suvichar, 3 Love, 4 Career. Rs 1 per SMS charge hoga. Unsubscribe ke liye STOP reply karein.",
        "hi": "मुफ्त क्विज! उत्तर दें: 1 कुंडली, 2 श्लोक, 3 प्रेम, 4 करियर। प्रति SMS 1 रुपया शुल्क। बंद करने के लिए STOP लिखें।",
        "te": "ఉచిత క్విజ్! సమాధానం ఇవ్వండి: 1 జాతక, 2 శ్లోకం, 3 ప్రేమ, 4 కెరీర్. ప్రతి SMS కు రూపాయలు 1 ఛార్జీ. ఆపడానికి STOP రాయండి.",
        "tenglish": "FREE QUIZ! Reply karo - 1 Horoscope, 2 Suvichar, 3 Love, 4 Career. SMS ki R1 charge avutundi. Unsub kooru ikkadiki STOP reply cheyandi.",
    }),
    # TV / channel subscription promo
    ("mk02", "tv_promo", {
        "en": "Enjoy unlimited movies on our OTT app. Get first month free. Download now and use code {code}. Not a bank transaction, just entertainment.",
        "hinglish": "Hamare OTT app par unlimited movies dekhiye. Pehla mahina free. Abhi download karein aur code {code} use karein. Entertainment ke liye, banking nahi.",
        "hi": "हमारे ऐप पर असीमित फिल्में देखें। पहला महीना निःशुल्क। अभी डाउनलोड करें और कोड {code} का उपयोग करें। यह केवल मनोरंजन है, बैंकिंग नहीं।",
        "te": "మా OTT యాప్‌లో అనిమిమిట ఫిల్మ్‌లు చూడండి. మొదటి నెల ఉచితం. ఇప్పుడే డౌన్‌లోడ్ చేసి కోడ్ {code} ఉపయోగించండి. ఇది వినోదం మాత్రమే, బ్యాంకింగ్ కాదు.",
        "tenglish": "Mee OTT app lo unlimited films choodandi. Pehla month free. Ippude download cheyandi, code {code} use cheyandi. Idi entertainment matrame, banking kaadu.",
    }),
    # real estate
    ("mk03", "real_estate", {
        "en": "PLOTS AVAILABLE near {city} main road, {sqft} sqft, ready to move. EMI from Rs {emi}. Call {phone} for site visit this weekend.",
        "hinglish": "{city} main road ke paas plots available hain, {sqft} sqft, ready to move. EMI Rs {emi} se. Site visit ke liye {phone} par call karein.",
        "hi": "{city} मुख्य सड़क के पास प्लॉट उपलब्ध, {sqft} वर्ग फुट, तैयार। EMI {emi} रुपये से। साइट विज़िट के लिए {phone} पर कॉल करें।",
        "te": "{city} మెయిన్ రోడ్ దగ్గర ప్లాట్స్ అందుబాటులో, {sqft} చ.అ.ఫా, సిద్ధం. EMI {emi} రూపాయల నుండి. సైట్ విజిట్ కోసం {phone} కు కాల్ చేయండి.",
        "tenglish": "{city} main road dukkunna plots unnayi, {sqft} sqft, ready. EMI {emi} rupees nundi. Site visit kosam {phone} ki call cheyandi.",
    }),
    # education / project consultancy
    ("mk04", "education", {
        "en": "Summer coaching batch starting Monday for Class 9 to 12. Free demo class on {date}. Limited seats, register now at {center}.",
        "hinglish": "Class 9 se 12 tak ke liye summer coaching batch Monday se shuru. {date} ko free demo class. Seats limited hain, abhi {center} par register karein.",
        "hi": "कक्षा 9 से 12 तक के लिए सीमmer कोचिंग बैच सोमवार से शुरू। {date} को निःशुल्क डेमो क्लास। सीटें सीमित हैं, अभी {center} में पंजीकरण करें।",
        "te": "తరగతి 9 నుండి 12 వరకు సమర్జన్ కోచింగ్ బ్యాచ్ సోమవారం నుండి. {date} న ఉచిత డెమో క్లాస్. సీట్లు పరిమితం, ఇప్పుడే {center} లో నమోదు చేసుకోండి.",
        "tenglish": "Class 9 nundi 12 variku summer coaching batch somavaram nundi. {date} na free demo class. Seitsu limited eh, ippude {center} lo register cheyandi.",
    }),
    # refer-and-earn (no fee, no credential theft)
    ("mk05", "referral", {
        "en": "Refer a friend to {platform} and both get {discount}% off your next order. Share this offer with your family group.",
        "hinglish": "{platform} par apne friend ko refer karein, dono ko next order par {discount}% off milega. Ye offer apne family group mein share karein.",
        "hi": "{platform} पर अपने मित्र को रेफर करें, दोनों को अगले ऑर्डर पर {discount}% छूट मिलेगी। यह ऑफर अपने परिवार समूह में साझा करें।",
        "te": "{platform} లో మీ స్నేహితుడిని రిఫర్ చేయండి, ఇద్దరికీ తదుపరి ఆర్డర్‌లో {discount}% తగ్గింపు. ఈ ఆఫర్ మీ కుటుంబ గ్రూపులో పంచుకోండి.",
        "tenglish": "{platform} lo mee friend ni refer cheyandi, iddariku tadinata order lo {discount}% off. Iidi offer mee family group lo share cheyandi.",
    }),
    # prize claim with NO fee (legit marketing, contrast with scam which demands fee)
    ("mk06", "prize_no_fee", {
        "en": "You have been selected for a {platform} lucky draw worth Rs {amount}. No purchase needed. Just collect at our store {city}.",
        "hinglish": "Aap {platform} lucky draw mein {amount} ke liye select hue hain. Koi khareedna nahi hai. Bas {city} store par collect karein.",
        "hi": "आप {platform} लकी ड्रॉ में {amount} रुपये के लिए चुने गए हैं। खरीदारी की आवश्यकता नहीं। बस {city} स्टोर पर लें।",
        "te": "మీరు {platform} లక్కీ డ్రాలో {amount} రూపాయల కోసం ఎంచుకోబార్డు. ఏదీ కొన్న అవసరం లేదు. {city} స్టోరులో తీసుకోండి.",
        "tenglish": "Nee {platform} lucky draw lo {amount} rupees kosam select ayinaavu. Emi koundera avasaram ledu. {city} store diki collect cheyandi.",
    }),
    # rate card / bulk offer
    ("mk07", "bulk_offer", {
        "en": "SMS marketing packages starting at Rs {emi} for 50,000 messages. Good for small businesses. Reply PACKAGE for a rate card.",
        "hinglish": "SMS marketing package Rs {emi} se shuru, 50,000 messages ke liye. Chhote business ke liye perfect. Rate card ke liye PACKAGE reply karein.",
        "hi": "SMS मार्केटिंग पैकेज {emi} रुपये से, 50,000 संदेशों के लिए। छोटे व्यवसायों के लिए उपयुक्त। रेट कार्ड के लिए PACKAGE लिखें।",
        "te": "SMS మార్కెటింగ్ ప్యాకేజ్ {emi} రూపాయల నుండి, 50,000 సందేశాల కోసం. చిన్న వ్యాపారాలకు అనుకూలం. రేట్ కార్డ్ కోసం PACKAGE రాయండి.",
        "tenglish": "SMS marketing package {emi} rupees nundi, 50,000 messages kosam. Chinna businesses ki vaadhu. Rate card kosam PACKAGE reply cheyandi.",
    }),
    # job / internship ad (no fee)
    ("mk08", "job_ad", {
        "en": "Work from home opportunity for students and freshers, no experience needed. Shortlisted candidates will be contacted. No registration fee ever.",
        "hinglish": "Students aur freshers ke liye work from home, koi experience nahi chahiye. Shortlisted candidates ko contact kiya jayega. Koi registration fee nahi, kabhi nahi.",
        "hi": "छात्रों और नौकरी-नवसीकों के लिए घर से काम, किसी अनुभव की आवश्यकता नहीं। चयनित उम्मीदवारों से संपर्क किया जाएगा। कोई पंजीकरण शुल्क कभी नहीं।",
        "te": "విద్యార్థులు మరియు ఫ్రెషర్ల కోసం ఇంటి నుండి పని, అనుభవం అవసరం లేదు. ఎంపికైన అభ్యర్థులను సంప్రదిస్తారు. నమోదు ఫీజు ఎప్పుడూ లేదు.",
        "tenglish": "Students, freshers kosam work from home, experience avasaram ledu. Shortlisted candidates ni contact chestaru. Registration fee emi na, kabhi na.",
    }),
    # travel / event promo
    ("mk09", "event_promo", {
        "en": "Weekend music festival at {city} on {date}, early bird tickets Rs {emi}. Family packages available. Organised by {center}.",
        "hinglish": "{city} mein {date} ko weekend music festival, early bird tickets Rs {emi}. Family package bhi hai. Organised by {center}.",
        "hi": "{city} में {date} को सप्ताहांत संगीत महोत्सव, अर्ली बर्ड टिकट {emi} रुपये। पारिवारिक पैकेज उपलब्ध। आयोजन {center} द्वारा।",
        "te": "{city} లో {date}న వారాంతష సంగీత మహోత్సవం, ఎర్లీ బర్డ్ టిక్కెట్ {emi} రూపాయలు. కుటుంబ ప్యాకేజీలు ఉన్నాయి. నిర్వాహకం {center}.",
        "tenglish": "{city} lo {date} na weekend music festival, early bird tickets {emi} rupees. Family package unnayi. {center} organize chestundi.",
    }),
    # health / supplement ad
    ("mk10", "supplement_ad", {
        "en": " Ayurvedic herbal supplement for joint pain and stiffness. 20% off for this week only. Free delivery across India. No prescription needed.",
        "hinglish": "Joints dard aur stiffness ke liye Ayurvedic herbal supplement. Is hafte 20% off. India bhar mein free delivery. Prescription ki zaroorat nahi.",
        "hi": "जोड़ों के दर्द और जकड़न के लिए आयुर्वेदिक हर्बल सप्लीमेंट। इस सप्ताह 20% छूट। भारत भर में निःशुल्क डिलीवरी। प्रिस्क्रिप्शन की आवश्यकता नहीं।",
        "te": "కడ్డు బాధ్య మరియు బిగుసుతనానికి ఆయుర్వేదిక హెర్బల్ సప్లిమెంట్. ఈ వారం 20% తగ్గింపు. భారతదేశ వ్యాప్తంగా ఉచిత డెలివరీ. ప్రిస్క్రిప్షన్ అవసరం లేదు.",
        "tenglish": "Knee baadha, stiff feel avtundi ayurvedic herbal supplement kosam. Ee varm 20% off. Bharat sarvela free delivery. Prescription avasaram ledu.",
    }),
("mk11", "discount_promo", {
        "en": "{platform}: Get {discount}% off up to Rs {amount} on your next order. Use code {code}. Valid for 48 hours only.",
        "hinglish": "{platform}: next order par {discount}% off, maximum {amount} tak. Code {code} use karein. Sirf 48 ghante ke liye.",
        "hi": "{platform}: अगले ऑर्डर पर {discount}% छूट, अधिकतम {amount} रुपये तक। कोड {code} का उपयोग करें। केवल 48 घंटे के लिए।",
        "te": "{platform}: తదుపరి ఆర్డర్‌లో {discount}% తగ్గింపు, గరిష్టంగా {amount} రూపాయల వరకు. కోడ్ {code} ఉపయోగించండి. 48 గంటలు మాత్రమే.",
        "tenglish": "{platform}: next order par {discount}% off, maximum {amount} tak. Code {code} use cheyandi. 48 hours matrame valid.",
    }),
]

LANGS = ["en", "hinglish", "hi", "te", "tenglish"]
SCRIPT = {"en": "latin", "hinglish": "latin", "hi": "devanagari",
          "te": "telugu", "tenglish": "latin"}


def slots(rng):
    # Slot pools are deliberately large. With only 10 templates x 5 languages,
    # small pools collapse 5,000 rows into ~2,400 unique (52% duplicates) because
    # every slot combination is reused. Wider pools raise real variety.
    return {
        "code": "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3)) +
                str(rng.randrange(10, 99)),
        "city": rng.choice([
            "Andhra Pradesh", "Telangana", "Vijayawada", "Visakhapatnam",
            "Hyderabad", "Warangal", "Tirupati", "Guntur", "Nellore",
            "Kurnool", "Rajahmundry", "Kakinada", "Karimnagar", "Warangal",
            "Nizamabad", "Khammam", "Ongole", "Eluru", "Machilipatnam",
            "Amalapuram", "Tadepalligudem", "Bhimavaram", "Tenali",
            "Chennai", "Pune", "Bengaluru", "Hyderabad metro",
            "Secunderabad", "Malkajgiri", "Kukatpally", "Madhapur",
        ]),
        "sqft": rng.choice(["600", "700", "900", "1200", "1500", "1800",
                            "2000", "2200", "2400", "2600", "3000", "3600"]),
        "emi": f"{rng.choice([399, 499, 599, 699, 799, 899, 999, 1099, 1250,
                             1499, 1500, 1999, 2250, 2500, 2999, 3500, 4999,
                             5500, 6000, 7500]):,}",
        "phone": f"{rng.choice(['Hyderabad', 'Vijayawada', 'Chennai', 'Pune',
                                'Secunderabad', 'Guntur', 'Nellore', 'Kurnool'])}-" +
                 f"{rng.randrange(10000, 99999)}",
        "amount": f"{rng.choice([199, 299, 399, 499, 599, 699, 799, 899, 999,
                                 1099, 1199, 1499, 1699, 1999, 2199, 2499, 2999,
                                 3499, 3999, 4499, 4999, 5999, 7499, 9999]):,}",
        "platform": rng.choice(["Amazon", "Flipkart", "Myntra", "Swiggy",
                                "Zomato", "Ola", "Uber", "PhonePe", "Paytm",
                                "Ajio", "Nykaa", "Tata CLiQ", "Snapdeal",
                                "BigBasket", "JioMart", "Tata Cliq"]),
        "discount": rng.choice([5, 10, 15, 20, 25, 30, 35, 40, 45, 50,
                                55, 60, 65, 70, 75, 80]),
        "date": rng.choice([
            "this Monday", "next Saturday", "this weekend", "15th March",
            "16th March", "17th March", "18th March", "19th March",
            "20th March", "21st March", "22nd March", "23rd March",
            "24th March", "25th March", "26th March", "27th March",
            "28th March", "29th March", "30th March", "next Monday",
            "next Tuesday", "next Wednesday", "tomorrow", "today",
        ]),
        "center": rng.choice([
            "Bright Future Academy", "Sri Coaching Centre", "Elite Learning Hub",
            "Green Valley School", "City Events and Management", "Apex Tutorials",
            "Vidya Mandir", "Sunrise Educational Institute", "Tech Skills Center",
            "Modern Public School", "Spark Digital Academy", "Vertex Training Center",
            "Indus Art Gallery", "Legend Fitness Studio", "Prime Dental Clinic",
            "Sunrise Hospital", "Apollo Pharmacy", "Star Realty",
            "Sai Real Estates", "Sri Sai Travels", "Anand Technologies",
        ]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "data/synthetic"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = []
    for _ in range(args.n):
        tid, cat, variants = rng.choice(MARKETING_TEMPLATES)
        lang = rng.choice(LANGS)
        rows.append({
            "text": variants[lang].format(**slots(rng)),
            "label": "marketing_spam",
            "template_id": tid,
            "category": cat,
            "lang": lang,
            "script": SCRIPT[lang],
            "source": "synthetic_marketing",
        })

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / "synthetic_marketing.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["text", "label", "template_id",
                                           "category", "lang", "script", "source"])
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    print(f"generated {len(rows):,} marketing_spam rows -> {p}")
    print(f"  templates: {len({r['template_id'] for r in rows})}")
    print(f"  by lang:   {dict(Counter(r['lang'] for r in rows))}")
    print(f"  unique:    {len({r['text'] for r in rows}):,}")


if __name__ == "__main__":
    main()