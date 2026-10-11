"""
Grounded synthetic generator for Indian scam / transactional SMS.

DESIGN PRINCIPLE
----------------
Nothing here is invented freely. Every template is derived from a pattern we
actually observed in an audited source:

  * scam structure  <- ysangam (deduped 743 unique) scam_category + vocabulary
  * scam phrasing   <- Atharva PHISHING_MESSAGES (355 real strings)
  * legit phrasing  <- Atharva LEGIT_MESSAGES (250 real strings) + real
                       transactional formats (OTP / UPI alert / delivery)
  * entities        <- only names that occur in the real corpora (see
                       extract_grounding.py output)

Each generated row carries a `template_id`. Splits MUST be grouped on
template_id, otherwise the model memorises our boilerplate and the test score
is meaningless. This is the single most important property of this file.

Three axes of variation, chosen because they are what actually varies in real
scam traffic, not because they make the data look bigger:
  1. template  (structure of the scam)
  2. slot fill (entity, amount, phone, url)
  3. rendering (language / script / code-mixing)

Usage:
    python scripts/generate_synthetic.py --n-scam 6000 --n-legit 6000 --out data/synthetic
"""
import argparse
import csv
import json
import pathlib
import random
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# SLOT VOCABULARY — every value here was observed in the audited corpora.
# ---------------------------------------------------------------------------
BANKS = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Mahindra",
         "PNB", "Bank of India", "Canara Bank", "Federal Bank", "IDFC First Bank"]
PLATFORMS = ["Amazon", "Flipkart", "Myntra", "Swiggy", "Zomato", "Ola",
             "Uber", "PhonePe", "Paytm", "IRCTC", "Ajio", "Nykaa"]
GOVT = ["UIDAI", "Income Tax Department", "EPFO", "RBI", "TRAI", "Election Commission"]
TELECOM = ["Airtel", "Jio", "Vi", "BSNL"]
POLICE = ["Delhi Police", "Mumbai Police", "Cyber Crime Department",
          "Crime Branch", "Special Investigation Team"]
NAMES = ["Rajesh Kumar", "Anil Sharma", "Priya Singh", "Vikram Rathore",
         "Sunil Yadav", "Neha Gupta", "Arjun Mehta", "Kavita Nair"]

# ---------------------------------------------------------------------------
# SCAM TEMPLATES
# Structure mirrors the categories that actually exist in ysangam. Language
# variants are real renderings of the same underlying scam -- a fraudster sends
# the same threat in whichever script the victim reads.
# Each entry: (template_id, category, {lang: template})
# ---------------------------------------------------------------------------
SCAM_TEMPLATES = [
    # --- digital arrest / police impersonation (the dominant real category) ---
    ("sa01", "police_digital_arrest", {
        "en": "Dear {name}, this is {police} calling. Your number has been linked to a cyber fraud case involving Rs {amount}. You are under digital arrest. To regularise your bail, transfer Rs {amount} to this account {acct} immediately or a warrant will be issued.",
        "hinglish": "{police} se bol raha hoon {name}. Aapke number par cyber fraud case register hua hai Rs {amount} ka. Aap digital arrest mein hain. Bail regularize karne ke liye turant Rs {amount} bhejein {acct} par, warna warrant issue ho jayega.",
        "hi": "प्रिय {name}, मैं {police} से बोल रहा हूँ। आपके नंबर पर साइबर फ्राड केस दर्ज है जिसमें {amount} रुपये हैं। आप डिजिटल अरेस्ट में हैं। जमीनी जमा करने के लिए तुरंत {amount} रुपये {acct} में भेजें, वरना वारंट जारी हो जाएगा।",
        "te": "నమస్కారం {name}, నేను {police} నుండి మాట్లాడుతున్నాను. మీ నంబర్ సైబర్ ఫ్రాడ్ కేసులో పేరు ఉంది {amount} రూపాయలు. మీరు డిజిటల్ అరెస్ట్‌లో ఉన్నారు. జరిమానా కాపాడటానికి వెంటనే {amount} రూపాయలు {acct} కు పంపండి లేదా వారంట్ జారీ అవుతుంది.",
    }),
    ("sa02", "police_blackmail", {
        "en": "This is {police}. We have recovered {count} obscene videos from your phone and they are being circulated on WhatsApp. Pay Rs {amount} to the UPI ID {upi} within 2 hours or the case goes to the media. Do not tell anyone.",
        "hinglish": "{police} se bol raha hoon. Aapke phone se {count} asleel videos mili hain aur WhatsApp pe faila diye ja rahe hain. Rs {amount} UPI {upi} par bhejo 2 ghante mein, warna case media ko chalega. Kisi ko mat batana.",
        "hi": "मैं {police} से बोल रहा हूँ। आपके फोन से {count} अश्लील वीडियो मिले हैं और वे WhatsApp पर फैलाए जा रहे हैं। 2 घंटे में {amount} रुपये UPI {upi} पर भेजें, वरना मामला मीडिया को जाएगा। किसी को मत बताना।",
        "te": "నేను {police} నుండి మాట్లాడుతున్నాను. మీ ఫోన్‌లో {count} అసభ్య వీడియోలు దొరికాయి, వాటిని WhatsAppలో పంచుతున్నారు. 2 గంటలలో {amount} రూపాయలు UPI {upi}కు పంపండి లేదా కేస్ మీడియాకి వెళ్తుంది. ఎవరికీ చెప్పకండి.",
    }),
    ("sa03", "bank_kyc", {
        "en": "Dear customer, your {bank} account will be permanently closed in 24 hours because KYC is pending. Update your KYC immediately at {url} or all transactions will be frozen.",
        "hinglish": "Dear customer, aapka {bank} account KYC pending hone ki wajah se 24 ghante mein permanently band ho jayega. Turant {url} pe KYC update kare warna saari transactions freeze ho jayengi.",
        "hi": "प्रिय ग्राहक, आपका {bank} खाता KYC लंबित होने के कारण 24 घंटे में स्थायी रूप से बंद हो जाएगा। तुरंत {url} पर KYC अपडेट करें अन्यथा सभी लेनदेन फ्रीज़ हो जाएंगी।",
        "te": "గౌరవముడైన కస్టమర్, మీ {bank} ఖాతా KYC పెండింగ్‌గా ఉండటంతో 24 గంటలలో శాశ్వతంగా మూసివేస్తారు. వెంటనే {url} లో KYC అప్‌డేట్ చేయండి లేదా అన్ని లెన్‌డెన్‌లు ఫ్రీజ్ అవుతాయి.",
    }),
    ("sa04", "bank_kyc", {
        "en": "{bank} alert: your net banking will be deactivated today. Your account has been used for money laundering. Submit your documents and Aadhaar number at {url} within 2 hours to avoid freezing.",
        "hinglish": "{bank} alert: aapka net banking aaj deactivate ho jayega. Aapke account se money laundering hua hai. Apne documents aur Aadhaar number {url} par 2 ghante mein bhejein warna account freeze ho jayega.",
        "hi": "{bank} सूचना: आपका नेट बैंकिंग आज निष्क्रिय हो जाएगा। आपके खाते से मनी लॉन्ड्रिंग हुई है। अपने दस्तावेज और आधार नंबर {url} पर 2 घंटे में भेजें वरना खाता फ्रीज़ हो जाएगा।",
        "te": "{bank} హెచ్చరిక: మీ నెట్ బ్యాంకింగ్ ఈ రోజే నిలిపివేస్తారు. మీ ఖాతా ద్వారా మనీ లాండ్రింగ్ జరిగింది. మీ పత్రాలు మరియు ఆధార్ నంబర్ {url} లో 2 గంటలలో పంపండి లేదా ఖాతా ఫ్రీజ్ అవుతుంది.",
    }),
    ("sa05", "lottery", {
        "en": "Congratulations! You have won Rs {amount} in the {platform} lucky draw. To release your prize pay the processing fee of Rs {charge} to {upi} and send your Aadhaar number. Claim within 24 hours only.",
        "hinglish": "Congratulations! Aapne {platform} lucky draw mein {amount} jeete hain. Prize paane ke liye {charge} processing fee UPI {upi} par bhejo aur apna Aadhaar number bhejo. Bas 24 ghante mein claim karo.",
        "hi": "बधाई हो! आपने {platform} के लकी ड्रॉ में {amount} रुपये जीते हैं। इनाम पाने के लिए {charge} रुपये प्रोसेसिंग फीस {upi} पर भेजें और अपना आधार नंबर भेजें। केवल 24 घंटे में क्लेम करें।",
        "te": "అభినందనలు! మీరు {platform} లక్కీ డ్రాలో {amount} రూపాయలు గెలిచారు. బహుమతి కోసం {charge} రూపాయలు ప్రాసెసింగ్ ఫీజు {upi}కు పంపండి మరియు మీ ఆధార్ నంబర్ పంపండి. 24 గంటలలోనే క్లెయిమ్ చేసుకోండి.",
    }),
    ("sa06", "amazon", {
        "en": "Your {platform} parcel is held at customs. Pay the clearance charge of Rs {charge} at {url} within 24 hours or the parcel will be returned to sender.",
        "hinglish": "Aapka {platform} parcel customs mein atka hai. Rs {charge} ka clearance charge {url} par 24 ghante mein dein warna parcel wapas return ho jayega.",
        "hi": "आपका {platform} पार्सल कस्टम्स पर रोका गया है। 24 घंटे में {url} पर {charge} रुपये क्लियरेंस चार्ज जमा करें अन्यथा पार्सल वापस कर दिया जाएगा।",
        "te": "మీ {platform} పార్సెల్ కస్టమ్‌లో నిలిపివేశారు. 24 గంటలలో {url} లో {charge} రూపాయలు క్లియరెన్స్ ఛార్జీ చెల్లించండి లేదా పార్సెల్ తిరిగి పంపబడుతుంది.",
    }),
    ("sa07", "relative", {
        "en": "{name} here. I lost my phone and I need Rs {amount} for an emergency. Please send it to this UPI {upi} right now, I will return it tomorrow.",
        "hinglish": "{name} bol raha hoon. Mera phone gir gaya hai, emergency ke liye Rs {amount} chahiye. Abhi is UPI {upi} par bhej do, kal wapas kar dunga.",
        "hi": "{name} बोल रहा हूँ। मेरा फोन गिर गया है, मुझे आपातकाल के लिए {amount} रुपये चाहिए। अभी इस UPI {upi} पर भेज दें, कल वापस कर दूंगा।",
        "te": "నేను {name}. నా ఫోన్ పడిపోయింది, అత్యవసరం కోసం {amount} రూపాయలు కావాలి. ఇప్పుడే ఈ UPI {upi}కు పంపండి, నేలకు తిరిగి ఇస్తాను.",
    }),
    ("sa08", "aadhaar", {
        "en": "{govt}: Your Aadhaar is used for a fake account in your name. To avoid cancellation send your Aadhaar number, OTP and bank details to {upi} or call this number immediately.",
        "hinglish": "{govt}: Aapke Aadhaar se aapke naam par fake account khul gaya hai. Cancel hone se bachne ke liye apna Aadhaar number, OTP aur bank details {upi} par bhejein ya turant is number par call karein.",
        "hi": "{govt}: आपके आधार से आपके नाम पर फर्जी खाता खुल गया है। रद्द होने से बचने के लिए अपना आधार नंबर, ओटीपी और बैंक विवरण {upi} पर भेजें या तुरंत इस नंबर पर कॉल करें।",
        "te": "{govt}: మీ ఆధార్ ద్వారా మీ పేరు పై నకిలీ ఖాతా తెరుచుకోబడింది. రద్దు కాకుండా మీ ఆధార్ నంబర్, OTP మరియు బ్యాంక్ వివరాలు {upi}కు పంపండి లేదా వెంటనే ఈ నంబర్‌కు కాల్ చేయండి.",
    }),
    ("sa09", "police_digital_arrest", {
        "en": "URGENT: Do not switch off your phone. {police} is tracing your number for an illegal transaction of Rs {amount}. To stop the FIR, pay Rs {amount} to {acct} within 30 minutes and share the OTP sent to you.",
        "hinglish": "URGENT: phone mat band karein. {police} aapke number par illegal transaction trace kar rahi hai {amount} ka. FIR rokne ke liye 30 minute mein {amount} {acct} par bhejein aur aapko jo OTP aaya hai wo share karein.",
        "hi": "अति जरूरी: अपना फोन बंद न करें। {police} आपके नंबर पर {amount} रुपये के अवैध लेनदेन की जांच कर रही है। एफआईआर रोकने के लिए 30 मिनट में {amount} रुपये {acct} में भेजें और आपको मिला ओटीपी साझा करें।",
        "te": "అత్యవసరం: మీ ఫోన్ ఆఫ్ చేయకండి. {police} మీ నంబర్‌ను {amount} రూపాయల అక్రమ రద్దును తనిఖీ చేస్తోంది. FIR నిలిపేందుకు 30 నిమిషాల్లో {amount} రూపాయలు {acct} కు పంపండి మరియు మీకు వచ్చిన OTP పంచుకోండి.",
    }),
    ("sa10", "relative", {
        "en": "This is your mother. I am in hospital and cannot talk. Please send Rs {amount} to this UPI {upi} immediately. Do not tell father.",
        "hinglish": "Main aapki maa bol rahi hoon. Hospital mein hoon, baat nahi ho pa rahi. Please Rs {amount} is UPI {upi} par turant bhejo. Papa ko mat batana.",
        "hi": "मैं आपकी माँ बोल रही हूँ। अस्पताल में हूँ, बात नहीं हो पा रही। कृपया {amount} रुपये {upi} पर तुरंत भेजें। पिताजी को मत बताना।",
        "te": "నేను మీ అమ్మను అనిపిస్తున్నాను. ఆస్పత్రిలో ఉన్నాను, మాట్లాడలేకపోతున్నాను. దయచేసి {amount} రూపాయలు {upi}కు వెంటనే పంపండి. తండ్రికి చెప్పకండి.",
    }),
    ("sa11", "bank_kyc", {
        "en": "Your {bank} debit card ending {acct4} has been blocked due to a failed KYC attempt. Unblock it now at {url} and pay the reactivation charge of Rs {charge}.",
        "hinglish": "Aapka {bank} debit card {acct4} par KYC fail hone ki wajah se block ho gaya hai. Abhi {url} par unblock karein aur Rs {charge} ka reactivation charge dein.",
        "hi": "आपका {bank} डेबिट कार्ड {acct4} KYC विफल होने के कारण ब्लॉक हो गया है। अभी {url} पर अनब्लॉक करें और {charge} रुपये का रिएक्टिवेशन चार्ज जमा करें।",
        "te": "మీ {bank} డెబిట్ కార్డు {acct4} KYC విఫలమవడంతో బ్లాక్ అయ్యింది. ఇప్పుడే {url} లో అన్‌బ్లాక్ చేసి {charge} రూపాయలు రీయాక్టివేషన్ ఛార్జీ చెల్లించండి.",
    }),
    ("sa12", "lottery", {
        "en": "Dear lucky winner, {platform} is giving a free gift to all customers. Claim your Rs {amount} cashback by paying the small registration fee of Rs {charge} to {upi} today.",
        "hinglish": "Dear lucky winner, {platform} sabhi customers ko free gift de raha hai. Rs {charge} ka registration fee UPI {upi} par bhej kar apna Rs {amount} cashback aaj hi claim karein.",
        "hi": "प्रिय सौभाग्यशाली, {platform} सभी ग्राहकों को मुफ़्त उपहार दे रहा है। {upi} पर {charge} रुपये पंजीकरण शुल्क भेजकर आज ही अपना {amount} रुपये कैशबैक क्लेम करें।",
        "te": "అదృష్టవంతుడు, {platform} అన్ని కస్టమర్లకు ఉచిత బహుమతి ఇస్తోంది. {upi}కు {charge} రూపాయలు రిజిస్ట్రేషన్ ఫీజు పంపి ఈ రోజే మీ {amount} రూపాయలు క్యాష్‌బ్యాక్ క్లెయిమ్ చేసుకోండి.",
    }),
]

# ---------------------------------------------------------------------------
# LEGIT TRANSACTIONAL TEMPLATES — the hard negatives.
# These use the SAME scary vocabulary as the scams (account, blocked, verify,
# OTP, KYC) so a model cannot cheat on keywords. Grounded in the 250 real
# Atharva LEGIT_MESSAGES and in real bank/OTT SMS formats.
# ---------------------------------------------------------------------------
LEGIT_TEMPLATES = [
    # OTP
    ("lg01", "otp", {
        "en": "{bank}: Your OTP is {otp} valid for {mins} minutes. Do not share it with anyone including bank staff.",
        "hinglish": "{bank}: aapka OTP {otp} hai, {mins} minute tak valid. Ise kisi ko mat share karna, bank staff ko bhi nahi.",
        "hi": "{bank}: आपका ओटीपी {otp} है, {mins} मिनट तक मान्य है। इसे किसी को न बताएं, बैंक कर्मचारी को भी नहीं।",
        "te": "{bank}: మీ OTP {otp}, {mins} నిమిషాలు ప్రశస్త్రం. దీన్ని ఎవరికీ చెప్పకండి, బ్యాంక్ ఉద్యోగులకు కూడా కాదు.",
    }),
    ("lg02", "otp", {
        "en": "{otp} is your one time password to log in to your {platform} account. It expires in {mins} minutes.",
        "hinglish": "{otp} aapka one time password hai {platform} login ke liye. Ye {mins} minute mein expire ho jayega.",
        "hi": "{platform} में लॉग इन करने के लिए आपका वन टाइम पासवर्ड {otp} है। यह {mins} मिनट में समाप्त हो जाएगा।",
        "te": "{platform} లో లాగిన్ చేయడానికి మీ ఒక్కసారి పాస్‌వర్డ్ {otp}. ఇది {mins} నిమిషాల్లో గడువు అవుతుంది.",
    }),
    # delivery
    ("lg03", "delivery", {
        "en": "Your {platform} order {orderid} has been delivered successfully. Thank you for shopping with us.",
        "hinglish": "Aapka {platform} order {orderid} deliver ho gaya hai. Shopping ke liye dhanyavaad.",
        "hi": "आपका {platform} ऑर्डर {orderid} सफलतापूर्वक डिलीवर हो गया है। खरीदारी के लिए धन्यवाद।",
        "te": "మీ {platform} ఆర్డర్ {orderid} విజయవంతంగా డెలివరీ అయ్యింది. కొనుగోలుకు ధన్యవాదాలు.",
    }),
    ("lg04", "delivery", {
        "en": "Out for delivery: {platform} order {orderid}. Expected by {time} today. Track live in the app.",
        "hinglish": "Out for delivery: {platform} order {orderid}. Aaj {time} tak pahunchega ki ummeed hai. App mein live track karein.",
        "hi": "डिलीवरी के लिए निकला: {platform} ऑर्डर {orderid}। आज {time} तक पहुंचने की उम्मीद है। ऐप में लाइव ट्रैक करें।",
        "te": "డెలివరీ కోసం బయలుదేరింది: {platform} ఆర్డర్ {orderid}. ఈ రోజు {time} లోకి చేరుతుందని ఎండుకుంది. యాప్‌లో లైవ్ ట్రాక్ చేయండి.",
    }),
    # appointment / travel
    ("lg05", "appointment", {
        "en": "Your appointment is confirmed for {date} at {time} with {name}. Please carry a photo ID.",
        "hinglish": "Aapka appointment {date} ko {time} baje {name} ke saath confirm hai. Photo ID lekar aayen.",
        "hi": "आपका अपॉइंटमेंट {date} को {time} बजे {name} के साथ पक्का है। फोटो आईडी साथ लेकर आएं।",
        "te": "మీ అపాయింట్మెంట్ {date} న {time} కు {name} తో నిర్ధారించబడింది. ఫోటో ID తీసుకురండి.",
    }),
    ("lg06", "appointment", {
        "en": "Your {platform} booking is confirmed. PNR {pnr}, departure at {time}. Show this SMS at the counter.",
        "hinglish": "Aapki {platform} booking confirm hai. PNR {pnr}, departure {time}. Counter par ye SMS dikhayein.",
        "hi": "आपकी {platform} बुकिंग पक्की है। पीएनआर {pnr}, प्रस्थान {time}। काउंटर पर यह एसएमएस दिखाएं।",
        "te": "మీ {platform} బుకింగ్ నిర్ధారించబడింది. PNR {pnr}, బయలుదేరడం {time}. కౌంటర్‌లో ఈ SMS చూపించండి.",
    }),
    # salary / credit
    ("lg07", "salary_credit", {
        "en": "Rs {amount} has been credited to your {bank} account ending {acct4}. Available balance Rs {balance}.",
        "hinglish": "Aapke {bank} account {acct4} mein Rs {amount} credit ho gaye hain. Available balance Rs {balance}.",
        "hi": "आपके {bank} खाते {acct4} में {amount} रुपये जमा हो गए हैं। उपलब्ध शेष {balance} रुपये है।",
        "te": "మీ {bank} ఖాతా {acct4} లో {amount} రూపాయలు క్రెడిట్ అయ్యాయి. అందుబాటులో ఉన్నది {balance} రూపాయలు.",
    }),
    ("lg08", "salary_credit", {
        "en": "{bank}: your salary of Rs {amount} has been credited. Kindly check your balance and contact us if it is not reflected.",
        "hinglish": "{bank}: aapki salary Rs {amount} credit ho gayi hai. Balance check kar lein, na dikhe toh humse baat karein.",
        "hi": "{bank}: आपकी सैलरी {amount} रुपये जमा हो गई है। कृपया शेष राशि जांचें, न दिखे तो हमसे संपर्क करें।",
        "te": "{bank}: మీ జీతం {amount} రూపాయలు క్రెడిట్ అయ్యింది. బ్యాలెన్స్ చూడండి, కనిపించకపోతే మమ్మల్ని సంప్రదించండి.",
    }),
    # transaction alert
    ("lg09", "transaction_alert", {
        "en": "Rs {amount} debited from your {bank} account ending {acct4} to {payee} on {date}. UTR {utr}. Balance Rs {balance}.",
        "hinglish": "Aapke {bank} account {acct4} se {date} ko {payee} ko Rs {amount} debit hue. UTR {utr}. Balance {balance}.",
        "hi": "आपके {bank} खाते {acct4} से {date} को {payee} को {amount} रुपये डेबिट हुए। यूटीआर {utr}। शेष {balance} रुपये।",
        "te": "మీ {bank} ఖాతా {acct4} నుండి {date} న {payee} కు {amount} రూపాయలు డెబిట్ అయ్యాయి. UTR {utr}. బ్యాలెన్స్ {balance}.",
    }),
    ("lg10", "transaction_alert", {
        "en": "UPI payment of Rs {amount} to {payee} was successful from your {platform} account. UTR {utr}. Not done by you? Call {helpline}.",
        "hinglish": "{platform} se {payee} ko Rs {amount} ka UPI payment successful hai. UTR {utr}. Aapne nahi kiya? {helpline} par call karein.",
        "hi": "आपके {platform} खाते से {payee} को {amount} रुपये का UPI भुगतान सफल हुआ। यूटीआर {utr}। आपने नहीं किया? {helpline} पर कॉल करें।",
        "te": "మీ {platform} ఖాతా నుండి {payee} కు {amount} రూపాయల UPI చెల్లింపు విజయవంతమైంది. UTR {utr}. మీరు చేయలేదా? {helpline}కు కాల్ చేయండి.",
    }),
    # autopay / subscription
    ("lg11", "autopay", {
        "en": "Your auto-pay of Rs {amount} for {platform} subscription is scheduled on {date}. Reply STOP to cancel.",
        "hinglish": "{platform} subscription ka auto-pay Rs {amount} {date} ko scheduled hai. Cancel karne ke liye STOP reply karein.",
        "hi": "{platform} सदस्यता का ऑटो-पे {amount} रुपये {date} को निर्धारित है। रद्द करने के लिए STOP का उत्तर दें।",
        "te": "{platform} సబ్‌స్క్రిప్షన్ ఆటో-పే {amount} రూపాయలు {date} నకు షెడ్యూల్ అయ్యింది. రద్దు చేయడానికి STOP రిప్లై చేయండి.",
    }),
    ("lg12", "autopay", {
        "en": "Your credit card bill of Rs {amount} for {bank} is due on {date}. Minimum due Rs {charge}. Pay now to avoid late fees.",
        "hinglish": "Aapke {bank} credit card ka bill Rs {amount} {date} tak due hai. Minimum due {charge}. Late fee se bachne ke liye abhi pay karein.",
        "hi": "आपके {bank} क्रेडिट कार्ड का बिल {amount} रुपये {date} तक देय है। न्यूनतम देय {charge} रुपये। देरी से बचने के लिए अभी भुगतान करें।",
        "te": "మీ {bank} క్రెడిట్ కార్డ్ బిల్ {amount} రూపాయలు {date} నకు చెల్లించాలి. కనీసం చెల్లించాల్సిది {charge}. ఆలస్య రుసుం నివారించుకోవడానికి ఇప్పుడే చెల్లించండి.",
    }),
    # promo / offers (legitimate marketing - still class ham)
    # NOTE: the discount-promo template lg13 that used to live here was MOVED to
    # scripts/generate_marketing.py as mk11. It was mislabelled `legit`: "Get
    # 40% off, use code ABC, valid 48 hours" is unsolicited advertising, not an
    # expected account message. Hard-negative analysis on the validation split
    # caught it -- 18 of the 20 baseline false-scam errors were this one
    # template. The model was right and the label was wrong.
    ("lg14", "promo", {
        "en": "{telecom}: {data} additional data has been added to your number. Validity {days} days. Charges apply as per plan.",
        "hinglish": "{telecom}: aapke number par {data} extra data add ho gaya hai. Validity {days} din. Plan ke hisaab se charges lagenge.",
        "hi": "{telecom}: आपके नंबर पर {data} अतिरिक्त डेटा जोड़ दिया गया है। वैधता {days} दिन। योजना के अनुसार शुल्क लागू।",
        "te": "{telecom}: మీ నంబర్‌కు {data} ఆధికర డేటా జోడించబడింది. వెలిడిటీ {days} రోజులు. ప్లాన్ ప్రకారం ఛార్జీలు వర్తిస్తాయి.",
    }),
    # reactivation that LOOKS like the sa11 scam but is genuine
    ("lg15", "account_alert", {
        "en": "{bank}: Your account ending {acct4} has been temporarily restricted for security. No money has been debited. Call {helpline} to restore access.",
        "hinglish": "{bank}: security ke liye aapka {acct4} account temporarily restrict kar diya gaya hai. Koi paise nahi kathe. Access ke liye {helpline} par call karein.",
        "hi": "{bank}: सुरक्षा के लिए आपका {acct4} खाता अस्थायी रूप से प्रतिबंधित कर दिया गया है। कोई पैसा नहीं काटा गया। पहुंच बहाल करने के लिए {helpline} पर कॉल करें।",
        "te": "{bank}: భద్రత కోసం మీ {acct4} ఖాతా తాత్కాలికంగా నియంత్రించబడింది. డబ్బు తీసేయలేదు. యాక్సెస్ కోసం {helpline}కు కాల్ చేయండి.",
    }),
    ("lg16", "account_alert", {
        "en": "{bank}: your KYC is due for renewal. Please submit the document at your nearest branch or via net banking. This is a routine reminder.",
        "hinglish": "{bank}: aapka KYC renewal ke liye due hai. Document nearest branch ya net banking se submit karein. Ye routine reminder hai.",
        "hi": "{bank}: आपका केवाईसी नवीनीकरण के लिए देय है। दस्तावेज निकटतम शाखा या नेट बैंकिंग से जमा करें। यह नियमित सूचना है।",
        "te": "{bank}: మీ KYC పునరుద్ధరణ కోసం డ్యూ అవుతుంది. పత్రాలను అతి దగ్గరి శాఖలో లేదా నెట్ బ్యాంకింగ్‌లో సమర్పించండి. ఇది సాధారణ రిమైండర్.",
    }),

    # -----------------------------------------------------------------------
    # lg17-lg30: gap-closing legitimate templates.
    #
    # WHY: hard-negative analysis showed the legit side of the KYC and billing
    # families was one template deep (lg16, lg12) against four scam templates
    # each. A model with that ratio learns "KYC renewal -> scam", which is
    # exactly backwards for the messages real customers receive every month.
    # These are the legitimate twin of each scam family: same scary words
    # (blocked, verify, pending, OTP, KYC, account), opposite meaning.
    #
    # Every one of these is deliberately written so a keyword matcher CANNOT
    # separate it from the scam version. That is the point of a hard negative.
    # NOTE: hi/te strings are machine-drafted and still need native-speaker
    # review before any Tenglish/Hindi performance claim is published.
    # -----------------------------------------------------------------------

    # KYC family — legitimate twin of the sa11 KYC-banking scam
    ("lg17", "kyc_renewal", {
        "en": "{bank}: Continue your KYC update on our official net banking portal. An OTP {otp} will be sent to your registered mobile. Never share this OTP with anyone.",
        "hinglish": "{bank}: KYC update hamare official net banking portal par karein. Aapke registered mobile par OTP {otp} aayega. Ye OTP kisi ko share mat karna.",
        "hi": "{bank}: हमारे आधिकारिक नेट बैंकिंग पोर्टल पर अपना केवाईसी अपडेट पूरा करें। आपके पंजीकृत मोबाइल पर ओटीपी {otp} भेजा जाएगा। यह ओटीपी किसी को न दें।",
        "te": "{bank}: మీ KYC అప్‌డేట్ మా అధికారిక నెట్ బ్యాంకింగ్ పోర్టల్‌లో పూర్తి చేయండి. మీ నమోదైన మొబైల్‌కు OTP {otp} పంపబడుతుంది. ఈ OTPని ఎవరికీ చెప్పకండి.",
    }),
    ("lg18", "kyc_renewal", {
        "en": "{bank}: Your KYC renewal is pending from {date}. If not completed, your account will be partially frozen as per RBI norms. No action is needed if your documents are already updated.",
        "hinglish": "{bank}: aapka KYC renewal {date} se pending hai. Complete nahi hua toh RBI ke rule ke hisaab se account partially freeze ho sakta hai. Agar documents update ho chuke hain toh kuch nahi karna hai.",
        "hi": "{bank}: आपका केवाईसी नवीनीकरण {date} से लंबित है। पूरा नहीं होने पर आरबीआई के नियमों के अनुसार आपका खाता आंशिक रूप से सील हो सकता है। यदि दस्तावेज पहले ही अपडेट हो चुके हैं तो कुछ करने की आवश्यकता नहीं है।",
        "te": "{bank}: మీ KYC పునరుద్ధరణ {date} నుండి పెండింగ్‌లో ఉంది. పూర్తి కాకపోతే RBI నియమాల ప్రకారం మీ ఖాతా పాక్షికంగా ఫ్రీజ్ కావచ్చు. పత్రాలు ఇప్పటికే అప్‌డేట్ అయితే ఏమీ చేయాలన్లేదు.",
    }),
    ("lg19", "kyc_renewal", {
        "en": "{bank}: Your KYC has been updated successfully. Aadhaar ending {acct4} and PAN are now linked to account ending {acct4}. No further action required.",
        "hinglish": "{bank}: aapka KYC successfully update ho gaya hai. {acct4} se khatam hone wala Aadhaar aur PAN ab aapke account se linked hain. Aage kuch nahi karna hai.",
        "hi": "{bank}: आपका केवाईसी सफलतापूर्वक अपडेट हो गया है। {acct4} पर समाप्त होने वाला आधार और पैन अब आपके खाते से जुड़े हुए हैं। आगे कोई कार्रवाई आवश्यक नहीं है।",
        "te": "{bank}: మీ KYC విజయవంతంగా అప్‌డేట్ అయ్యింది. {acct4} తో ఆగే ఉన్న ఆధార్ మరియు PAN ఇప్పుడు మీ ఖాతాతో లింక్ అయ్యాయి. ఇకపై ఏ చర్యా అవసరం లేదు.",
    }),

    # billing family — legitimate twin of the "pay to activate" scam
    ("lg20", "bill_reminder", {
        "en": "{govt}: Your electricity bill for {date} is Rs {amount}. Pay before {date} to avoid a late charge of Rs {charge}. Pay at our official website or app.",
        "hinglish": "{govt}: aapka bijli ka bill {date} ka Rs {amount} hai. Late charge Rs {charge} se bachne ke liye {date} tak pay karein. Official website ya app par pay karein.",
        "hi": "{govt}: {date} का आपका बिजली बिल {amount} रुपये है। {charge} रुपये की विलंब शुल्क से बचने के लिए {date} तक भुगतान करें। हमारी आधिकारिक वेबसाइट या ऐप पर भुगतान करें।",
        "te": "{govt}: {date} న మీ బిల్ట్ బిల్ రూపాయలు {amount}. ఆలస్య రుసుం రూపాయలు {charge} నివారించడానికి {date} నకు చెల్లించండి. మా అధికారిక వెబ్‌సైట్ లేదా యాప్‌లో చెల్లించండి.",
    }),
    ("lg21", "bill_reminder", {
        "en": "Your {telecom} postpaid bill of Rs {amount} is due on {date}. Auto-pay is ON, it will be debited from account ending {acct4}. To opt out reply STOP.",
        "hinglish": "Aapka {telecom} postpaid bill Rs {amount} {date} tak due hai. Auto-pay ON hai, {acct4} se debit ho jayega. Band karne ke liye STOP reply karein.",
        "hi": "आपका {telecom} पोस्टपेड बिल {amount} रुपये {date} तक देय है। ऑटो-पे चालू है, {acct4} से कट जाएगा। बंद करने के लिए STOP का उत्तर दें।",
        "te": "మీ {telecom} పోస్ట్‌పేడ్ బిల్ రూపాయలు {amount} {date} నకు చెల్లించాలి. ఆటో-పే ఆన్‌లో ఉంది, {acct4} నుండి తీసేయబడుతుంది. ఆప్ చేయడానికి STOP రిప్లై చేయండి.",
    }),
    ("lg22", "bill_reminder", {
        "en": "{platform}: Your {platform} Premium subscription renewal of Rs {amount} will be auto-debited on {date}. Manage or cancel in the app.",
        "hinglish": "{platform}: aapke {platform} Premium subscription ka renewal Rs {amount} {date} ko auto-debit hoga. App mein manage ya cancel kar sakte hain.",
        "hi": "{platform}: आपके {platform} प्रीमियम सदस्यता का नवीनीकरण {amount} रुपये {date} को स्वतः कट जाएगा। ऐप में प्रबंधित करें या रद्द करें।",
        "te": "{platform}: మీ {platform} ప్రీమియం సబ్‌స్క్రిప్షన్ రిన్యూవల్ రూపాయలు {amount} {date} నకు ఆటో-డెబిట్ అవుతుంది. యాప్‌లో నిర్వహించండి లేదా రద్దు చేయండి.",
    }),

    # loan / EMI family — legitimate twin of "loan approved, pay processing fee"
    ("lg23", "loan_emi", {
        "en": "{bank}: EMI of Rs {amount} has been auto-debited from your account ending {acct4} towards loan {orderid}. Interest portion Rs {charge}. Principal Rs {amount}.",
        "hinglish": "{bank}: loan {orderid} ke liye {acct4} se Rs {amount} ka EMI auto-debit ho gaya. Interest hissa Rs {charge}, principal {amount}.",
        "hi": "{bank}: ऋण {orderid} के लिए आपके {acct4} खाते से {amount} रुपये का EMI स्वतः कट गया है। ब्याज भाग {charge} रुपये, मूलधन {amount} रुपये।",
        "te": "{bank}: రుణం {orderid} కోసం మీ {acct4} ఖాతా నుండి రూపాయలు {amount} EMI ఆటో-డెబిట్ అయ్యింది. వడ్డీ భాగం రూపాయలు {charge}, అసలు రూపాయలు {amount}.",
    }),
    ("lg24", "loan_reminder", {
        "en": "{bank}: Your loan EMI of Rs {amount} is due on {date}. Pay through our official app or net banking. We never ask for OTPs or card details on call.",
        "hinglish": "{bank}: aapka loan EMI Rs {amount} {date} ko due hai. Hamare official app ya net banking se pay karein. Hum kabhi call par OTP ya card details nahi maangte.",
        "hi": "{bank}: आपका ऋण EMI {amount} रुपये {date} को देय है। हमारे आधिकारिक ऐप या नेट बैंकिंग से भुगतान करें। हम कॉल पर कभी ओटीपी या कार्ड विवरण नहीं माँगते।",
        "te": "{bank}: మీ రుణ EMI రూపాయలు {amount} {date} నకు చెల్లించాలి. మా అధికారిక యాప్ లేదా నెట్ బ్యాంకింగ్ ద్వారా చెల్లించండి. మేము కాల్‌లో ఎప్పుడూ OTP లేదా కార్డ్ వివరాలు అడగం లేదు.",
    }),

    # credit / refund family — legitimate twin of "refund will be credited, share details"
    ("lg25", "refund", {
        "en": "{platform}: Rs {amount} has been refunded to your source account ending {acct4}. It will reflect in 3 to 5 working days. Reference {orderid}.",
        "hinglish": "{platform}: Rs {amount} aapke source account {acct4} mein refund kar diye gaye hain. 3 se 5 working din mein dikhenge. Reference {orderid}.",
        "hi": "{platform}: {amount} रुपये आपके स्रोत खाते {acct4} में वापस कर दिए गए हैं। 3 से 5 कार्यदिवस में दिखेंगे। संदर्भ {orderid}।",
        "te": "{platform}: రూపాయలు {amount} మీ సోర్స్ ఖాతా {acct4} కు రిఫండ్ చేయబడ్డాయి. 3 నుండి 5 పని రోజుల్లో కనిపిస్తాయి. రిఫరెన్స్ {orderid}.",
    }),
    ("lg26", "cashback", {
        "en": "{platform}: Rs {amount} cashback credited to your wallet for your {date} order. Wallet balance Rs {balance}.",
        "hinglish": "{platform}: aapke {date} order par Rs {amount} cashback wallet mein credit ho gaya. Wallet balance Rs {balance}.",
        "hi": "{platform}: आपके {date} ऑर्डर पर {amount} रुपये कैशबैक आपके वॉलेट में जमा हो गया है। वॉलेट शेष {balance} रुपये है।",
        "te": "{platform}: మీ {date} ఆర్డర్‌కు రూపాయలు {amount} క్యాష్‌బ్యాక్ వాలెట్‌లో క్రెడిట్ అయ్యింది. వాలెట్ బ్యాలెన్స్ రూపాయలు {balance}.",
    }),

    # government benefit family — legitimate twin of "government scheme, send money"
    ("lg27", "govt_credit", {
        "en": "{govt}: Rs {amount} has been credited to your bank account ending {acct4} under {govt} scheme. No action needed. This is an automated message.",
        "hinglish": "{govt}: {govt} scheme ke under Rs {amount} aapke {acct4} bank account mein credit ho gaye hain. Kuch karne ki zaroorat nahi. Ye automated message hai.",
        "hi": "{govt}: {govt} योजना के तहत {amount} रुपये आपके {acct4} बैंक खाते में जमा कर दिए गए हैं। कुछ करने की आवश्यकता नहीं है। यह एक स्वचालित संदेश है।",
        "te": "{govt}: {govt} పథకం కింద రూపాయలు {amount} మీ {acct4} బ్యాంక్ ఖాతాకు క్రెడిట్ చేయబడ్డాయి. ఏ చర్యా అవసరం లేదు. ఇది ఆటోమేటెడ్ సందేశం.",
    }),
    ("lg28", "govt_document", {
        "en": "{govt}: Your document has been updated successfully. Aadhaar ending {acct4} is valid and linked. No OTP is required. This is a system generated message.",
        "hinglish": "{govt}: aapka document successfully update ho gaya hai. {acct4} tak ka Aadhaar valid hai aur linked hai. Koi OTP required nahi. Ye system generated message hai.",
        "hi": "{govt}: आपका दस्तावेज सफलतापूर्वक अपडेट हो गया है। {acct4} पर समाप्त आधार मान्य है और जुड़ा हुआ है। किसी ओटीपी की आवश्यकता नहीं है। यह सिस्टम द्वारा उत्पन्न संदेश है।",
        "te": "{govt}: మీ పత్రం విజయవంతంగా అప్‌డేట్ అయ్యింది. {acct4} వరకు ఆధార్ చెల్లుబాటు మరియు లింక్ అయినది. ఏ OTP అవసరం లేదు. ఇది సిస్టమ్ జనరేటెడ్ సందేశం.",
    }),

    # travel / utility / civic family — the remaining everyday legit traffic
    ("lg29", "travel", {
        "en": "Your boarding pass is ready. PNR {pnr}, coach {count}, seat {count}. Departure {date} at {time} from the platform confirmed by IRCTC.",
        "hinglish": "Aapka boarding pass ready hai. PNR {pnr}, coach {count}, seat {count}. Departure {date} {time} ko IRCTC ne platform confirm kiya.",
        "hi": "आपका बोर्डिंग पास तैयार है। पीएनआर {pnr}, कोच {count}, सीट {count}। प्रस्थान {date} को {time} बजे, प्लेटफॉर्म आईआरसीटीसी द्वारा पुष्ट।",
        "te": "మీ బోర్డింగ్ పాస్ సిద్ధంగా ఉంది. PNR {pnr}, కోచ్ {count}, సీట్ {count}. బయలుదేరడం {date} న {time} కు, ప్లాట్‌ఫార్మ్ IRCTC నిర్ధారించింది.",
    }),
    ("lg30", "utility", {
        "en": "{telecom}: Your FASTAG balance is Rs {balance}. Recharge of Rs {amount} is done. If the vehicle number is wrong, contact {helpline}.",
        "hinglish": "{telecom}: aapka FASTAG balance Rs {balance} hai. Rs {amount} ka recharge ho gaya hai. Vehicle number galat hai toh {helpline} par contact karein.",
        "hi": "{telecom}: आपका FASTAG बैलेंस {balance} रुपये है। {amount} रुपये का रिचार्ज कर दिया गया है। वाहन नंबर गलत है तो {helpline} पर संपर्क करें।",
        "te": "{telecom}: మీ FASTAG బ్యాలెన్స్ రూపాయలు {balance}. రూపాయలు {amount} రీచార్జ్ చేయబడింది. వాహన్ నంబర్ తప్పు అయితే {helpline}ను సంప్రదించండి.",
    }),
    ("lg31", "healthcare", {
        "en": "{govt}: Your diagnostic report for {date} is ready. Collect from the lab with your report number {orderid}. Report is also available in your account.",
        "hinglish": "{govt}: aapka {date} ka diagnostic report ready hai. Report number {orderid} lekar lab se collect karein. Report aapke account mein bhi hai.",
        "hi": "{govt}: आपका {date} का निदान रिपोर्ट तैयार है। रिपोर्ट नंबर {orderid} लेकर प्रयोगशाला से प्राप्त करें। रिपोर्ट आपके खाते में भी उपलब्ध है।",
        "te": "{govt}: మీ {date} డయాగ్నాస్టిక్ రిపోర్ట్ సిద్ధంగా ఉంది. రిపోర్ట్ నంబర్ {orderid} తీసుకుని ల్యాబ్ నుండి సేకరించండి. రిపోర్ట్ మీ ఖాతాలో కూడా ఉంది.",
    }),
    ("lg32", "education", {
        "en": "{govt}: Result declared for exam {count}. Candidate {name}, roll {orderid}, has passed. Fee receipt of Rs {amount} is generated in your dashboard.",
        "hinglish": "{govt}: exam {count} ka result aa gaya hai. Candidate {name}, roll {orderid}, pass ho gaye. Rs {amount} ka fee receipt aapke dashboard par generate hua hai.",
        "hi": "{govt}: परीक्षा {count} का परिणाम घोषित हो गया है। अभ्यर्थी {name}, अनुक्रमांक {orderid}, उत्तीर्ण रहे हैं। {amount} रुपये का शुल्क रसीद आपके डैशबोर्ड पर बन गई है।",
        "te": "{govt}: పరీక్ష {count} ఫలితాలు ప్రకటించబడ్డాయి. అభ్యర్థి {name}, రోల్ నంబర్ {orderid}, ఉత్తీర్ణత సాధించారు. రూపాయలు {amount} ఫీజు రసీదు మీ డాష్‌బోర్డ్‌లో ఉంది.",
    }),
    ("lg33", "atm", {
        "en": "{bank}: Rs {amount} withdrawn from ATM ending {orderid} on {date}. Available balance Rs {balance}. UTR {utr}.",
        "hinglish": "{bank}: {date} ko {orderid} ATM se Rs {amount} nikaale gaye. Available balance Rs {balance}. UTR {utr}.",
        "hi": "{bank}: {date} को {orderid} ATM से {amount} रुपये निकाले गए। उपलब्ध शेष {balance} रुपये है। यूटीआर {utr}।",
        "te": "{bank}: {date} న {orderid} ATM నుండి రూపాయలు {amount} తీసేయబడ్డాయి. అందుబాటులో ఉన్నది రూపాయలు {balance}. UTR {utr}.",
    }),
    ("lg34", "deposit_maturity", {
        "en": "{bank}: Your fixed deposit of Rs {amount} matures on {date}. Interest of Rs {charge} will be credited on maturity. No action needed to keep the same FD.",
        "hinglish": "{bank}: aapka Rs {amount} ka fixed deposit {date} ko mature hoga. Rs {charge} ka interest maturity par credit hoga. Same FD rakhne ke liye kuch nahi karna hai.",
        "hi": "{bank}: आपकी {amount} रुपये की सावधि जमा {date} को परिपक्व होगी। {charge} रुपये का ब्याज परिपक्वन पर जमा होगा। वही जमा रखने के लिए कुछ करने की आवश्यकता नहीं।",
        "te": "{bank}: మీ రూపాయలు {amount} ఫిక్స్‌డ్ డిపాజిట్ {date} నకు మ్యాచ్యూర్ అవుతుంది. రూపాయలు {charge} వడ్డీ మ్యాచ్యూర్ అయ్యేటప్పుడు క్రెడిట్ అవుతుంది. అదే FD కొనసాగించడానికి ఏమీ చేయాలన్లేదు.",
    }),
]

LANGS = ["en", "hinglish", "hi", "te"]
LANG_SCRIPT = {"en": "latin", "hinglish": "latin", "hi": "devanagari", "te": "telugu"}


def slot_values(rng):
    """Slot fillers. Amounts/OTPs use realistic Indian magnitudes."""
    banks = rng.choice(BANKS)
    plats = rng.choice(PLATFORMS)
    return {
        "bank": banks,
        "platform": plats,
        "govt": rng.choice(GOVT),
        "telecom": rng.choice(TELECOM),
        "police": rng.choice(POLICE),
        "name": rng.choice(NAMES),
        "amount": f"{rng.choice([50, 75, 100, 150, 200, 250, 499, 500, 750, 899, 1200, 1500, 2000, 2500, 5000, 10000, 25000, 50000, 100000, 500000, 1000000]):,}",
        "charge": f"{rng.choice([9, 19, 25, 35, 49, 99, 199, 299, 499, 599, 799]):,}",
        "balance": f"{rng.randrange(1000, 500000, 137):,}",
        "otp": f"{rng.randrange(100000, 999999)}",
        "mins": rng.choice([5, 10, 15, 20, 30]),
        "days": rng.choice([7, 15, 30, 60, 90]),
        "count": rng.choice([2, 3, 5, 8, 12, 15, 24, 30]),
        "orderid": f"{rng.randrange(100000000, 999999999)}",
        "utr": f"UTR{rng.randrange(100000000000, 999999999999)}",
        "pnr": "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3)) +
               str(rng.randrange(100000, 999999)),
        "helpline": rng.choice(["1800-123-4567", "1800-258-0138",
                                "1800-180-1111", "+91-11-4001-0000"]),
        "upi": _upi_id(rng),
        "acct": f"{rng.randrange(10000000000, 99999999999)}",
        "acct4": str(rng.randrange(1000, 9999)),
        "payee": rng.choice(["SHOPPING MART", "FOOD DELIVERY", "PETROL STATION",
                             "ELECTRICITY BILL", "MOBILE RECHARGE", "SALARY TRANSFER",
                             "RENT PAYMENT", "INSURANCE PREMIUM"]),
        "url": rng.choice([
            f"http://{rng.choice(['bit.ly', 'tinyurl.com', 't.co', 'short.link'])}/"
            f"{rng.choice(['kyc', 'verify', 'update', 'claim', 'secure', 'secure2'])}"
            f"{rng.randrange(1000, 9999)}",
            f"https://{rng.choice(['sbi-kyc', 'hdfc-update', 'rbi-verify', 'epfo-update', 'aadhaar-auth'])}"
            f"{rng.choice(['.in', '.co.in', '.com'])}/secure/{rng.randrange(10000, 99999)}",
        ]),
        "discount": rng.choice([10, 20, 25, 30, 40, 50, 60, 70, 80]),
        "code": "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3)) +
                str(rng.randrange(10, 99)),
        "data": rng.choice(["2GB", "5GB", "10GB", "15GB", "1.5GB daily", "3GB"]),
        "date": rng.choice(["today", "tomorrow", "12th March", "15th March",
                            "20th March", "next Monday", "Saturday"]),
        "time": rng.choice(["9:30 AM", "10:00 AM", "11:15 AM", "1:00 PM",
                            "4:00 PM", "6:30 PM", "8:45 PM"]),
    }


def _rand_digits(rng, n=8):
    return "".join(rng.choices("0123456789", k=n))


def _upi_id(rng):
    """UPI handle. Built from a generator function so that no literal braces
    ever end up inside a value that is later fed to str.format()."""
    prefixes = ["fastpay", "securepay", "paynow", "instantpay",
                "easy", "quickpay", "upi"]
    handles = ["okhdfcbank", "ybl", "okicici", "oksbi", "okaxis", "paytm"]
    return f"{rng.choice(prefixes)}{rng.randrange(1000000, 9999999)}@{rng.choice(handles)}"


def generate(n_scam, n_legit, seed=42):
    """Generate rows. template_id is carried through for grouped splitting."""
    rng = random.Random(seed)
    rows = []

    def emit(templates, label, n):
        for _ in range(n):
            tid, cat, variants = rng.choice(templates)
            lang = rng.choice(LANGS)
            text = variants[lang].format(**slot_values(rng))
            rows.append({
                "text": text,
                "label": label,
                "template_id": tid,
                "category": cat,
                "lang": lang,
                "script": LANG_SCRIPT[lang],
                "source": "synthetic_grounded",
            })

    emit(SCAM_TEMPLATES, "scam", n_scam)
    emit(LEGIT_TEMPLATES, "legit", n_legit)
    rng.shuffle(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-scam", type=int, default=6000)
    ap.add_argument("--n-legit", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(ROOT / "data/synthetic"))
    args = ap.parse_args()

    rows = generate(args.n_scam, args.n_legit, args.seed)
    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "synthetic_sms.csv"

    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["text", "label", "template_id",
                                           "category", "lang", "script", "source"])
        w.writeheader()
        w.writerows(rows)

    import collections
    print(f"generated {len(rows):,} rows -> {out}")
    print(f"  templates: {len({r['template_id'] for r in rows})} distinct")
    print(f"  by label: {dict(collections.Counter(r['label'] for r in rows))}")
    print(f"  by lang:  {dict(collections.Counter(r['lang'] for r in rows))}")
    print(f"  by cat:   {dict(collections.Counter(r['category'] for r in rows))}")
    print(f"  unique texts: {len({r['text'] for r in rows}):,}")
    print(f"  seed: {args.seed}")


if __name__ == "__main__":
    main()