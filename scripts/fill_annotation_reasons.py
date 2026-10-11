"""
Fill human_reason in data/annotation_blinded_145.csv from the message evidence.

Rules honoured:
  * human_label is NEVER modified. The annotator's label stays exactly as-is.
  * The sheet keeps its agreed four columns: review_id, text, human_label,
    human_reason. No new columns.
  * Reasons are written from the text itself, not to justify the existing label.
  * Where the annotator's label conflicts with the evidence, the reason says so
    explicitly and is prefixed CONFLICT:.
  * Where human_label is blank, no label is written. The reason states the
    evidence and a SUGGESTED label only, which is a recommendation for the
    annotator to accept or reject -- not an assignment.

Run:  python scripts/fill_annotation_reasons.py
"""
import csv
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHEET = ROOT / "data/annotation_blinded_145.csv"

C = "CONFLICT: "
B = "SUGGESTED LABEL (cell left blank for you): "

REASONS = {
    # ---------------- legitimate, label agrees with evidence -----------------
    "R000-ce60ecac2c": "Ride-completion notification with the fare already settled, from a known ride-hailing sender ID. No demand, no link, no credential request. Matches 'legitimate'.",
    "R021-0f3b0d0005": "One person telling another their own name and new phone number. Ordinary personal contact, single-participant conversation, nothing asked of the reader.",
    "R022-a836eb4bf8": "Recipient does not recognise the sender and says so, apologising for the wrong number. Everyday misdirected-SMS case, no solicitation.",
    "R023-401a339f59": "Peers arranging whether to attend a class at a specific time. Ordinary two-way personal logistics.",
    "R024-90c28277f7": "Casual chat about what someone meant by an expression, between familiar interlocutors. No offer, no request.",
    "R030-61c36792f3": C + "A broadcast prompt about low confidence, asking the recipient to reply Yes or No to receive tips. That is an engagement solicitation sent at scale, not a message expected by this recipient. Your label says legitimate; I lean marketing_spam, though it could be a legitimate wellness-brand campaign. Low-stakes either way.",
    "R040-5e7f9d3ba0": "Bare greeting with no commercial or coercive content. Standard legitimate personal message.",
    "R044-823a27dbe1": "One person asking another to call on arrival home. Implied existing relationship, no commercial content.",
    "R060-922fc074d0": "Personal request to be called at a set time so the sender knows the recipient is awake. Ordinary social arrangement.",
    "R061-996ba68d7d": "One person asking another for their phone model number. Everyday conversation, no solicitation.",
    "R062-81029d35b5": "Opponent complaining about the rules of a game in progress. Conversational, no offer or demand.",
    "R063-855ed94b69": "Recipient telling the sender to ask someone else. Ordinary conversational deflection.",
    "R064-8c41ce6cd6": "Instruction between acquaintances about preparing their belongings for travel. Personal in nature.",
    "R113-8c41ce6cd6": "Instruction between acquaintances about preparing their belongings for travel. Personal in nature.",
    "R110-42f999fa45": "Recipient asking whether it is acceptable to send a resume to an address. Personal correspondence.",
    "R111-f26199c47b": "Affectionate goodnight message between two people who know each other. No commercial content.",
    "R112-e0ea54ef9b": "Sender reassuring a family member they have reached home. Personal, single-recipient.",
    "R114-a0e1a21580": "Peer asking whether someone is coming to class today. Ordinary social logistics.",
    "R122-6ee6a409a0": "One person giving another practical advice about pain and when to see a doctor. Personal, well-meant, no ask.",
    "R130-ffbb4c22ef": "Driver contacting a rider about imminent arrival. Standard ride-hailing operational message, no request for money or credentials.",
    "R131-fb2a5fc41e": "Delivery confirmation asking for feedback after an order is complete. Routine e-commerce transactional message, not an unsolicited offer.",
    "R132-553bfcc372": "Person arriving home and asking a family member to open the door. Ordinary personal message.",
    "R133-089b4eafc4": "Colleague confirming a project review meeting time. Internal work coordination, no solicitation.",
    "R134-e517c4650b": "Child notifying a parent they are on a train and will arrive safely. Personal reassurance.",

    # ---------------- legitimate: correct hard negatives ----------------------
    "R082-89675e0eba": "Canonical genuine OTP: bank names itself, gives the code and a validity window, and explicitly warns not to share it with anyone including bank staff. Contains the word OTP but asks for nothing back. Correctly legitimate.",
    "R083-82c54eeb8d": "Genuine security alert: bank states the account was temporarily restricted, explicitly says no money was debited, and directs the customer to call the helpline rather than click anything. Scary vocabulary, no coercion, no link, no payment demand. Correctly legitimate.",
    "R084-ce8d5f3b5c": "Routine telecom data-addition notification stating validity and that plan charges apply. Informational, no action demanded.",

    # ---------------- legitimate: CONFLICTS ----------------------------------
    "R017-38bd913612": C + "A bank-styled demand to pay a fine immediately for a non-maintained minimum balance. No real bank assesses a penalty this way or demands instant payment by SMS, and no official helpline is given. Reads as a phishing lure rather than a notification. Your label says legitimate; I read this as scam.",
    "R045-46a345aef2": C + "A promise to double money in 7 days is a guaranteed-return investment claim, which is the defining feature of an investment scam. There is no legitimate product that can guarantee a multiple in a fixed short period. Your label says legitimate; I read this as scam. (Also note this exact message appears 5 times in the sheet - see duplicates.)",
    "R046-46a345aef2": C + "Duplicate of the same guaranteed-doubling investment claim. See R045. I read this as scam.",
    "R047-46a345aef2": C + "Duplicate of the same guaranteed-doubling investment claim. See R045. I read this as scam.",
    "R048-46a345aef2": C + "Duplicate of the same guaranteed-doubling investment claim. See R045. I read this as scam.",
    "R049-46a345aef2": C + "Duplicate of the same guaranteed-doubling investment claim. See R045. I read this as scam.",
    "R077-f006672ecb": C + "Threatens to hold a Paytm balance and demands KYC completion at a personal phone number. Fake-KYC account-takeover pattern: an urgent hold, a KYC pretext, and a mobile number instead of an official channel. Your label says legitimate; I read this as scam.",
    "R099-f339c62193": C + "A discounted commercial health product with free delivery. It is an advertisement, not an expected account or personal notification. Your label says legitimate; I read this as marketing_spam.",
    "R103-360c05dc11": C + "An advertisement selling bulk SMS-marketing packages for a fee. Commercial service promotion, not a notification to an existing customer. Your label says legitimate; I read this as marketing_spam. Note R101 is the Hindi version of this same template and is blank - worth labelling consistently.",
    "R123-24ea5fcbee": C + "'Final contact attempt' plus 'important messages waiting' is the standard pressure formulation used by debt-recovery and premium-subscription services. The message never states what the messages are or who is waiting. Borderline; I lean marketing_spam rather than legitimate, but it is arguable.",
    "R125-b3ae6a7ac7": C + "Prize claim that requires phoning a premium-rate number and entering all personal details. Explicit credential solicitation plus a paid call. Clear scam. Your label says legitimate; I read this as scam.",
    "R135-946d24e655": C + "Impersonates the National Cyber Cell and alleges obscene messages were sent from the recipient's WhatsApp. This is the blackmail pattern (accusation + implied consequence + no official contact route). Your label says legitimate; I read this as scam.",
    "R136-ba7e54949b": C + "Impersonates Delhi Police and the Crime Branch, alleging suspicious transactions from the account. Same digital-arrest/blackmail family as the rest of this group. Your label says legitimate; I read this as scam.",
    "R137-2fcec645ad": C + "Impersonates an authority claiming a misuse report has been filed against a SIM registered to the recipient. Accusation-first framing with no way to verify through an official channel. Your label says legitimate; I read this as scam.",
    "R138-b4b6361fae": C + "Impersonates an authority alleging a money-laundering case has been registered in the recipient's name. No case number, no official channel. Digital-arrest opener. Your label says legitimate; I read this as scam.",
    "R139-3ebac70821": C + "Impersonates the Crime Branch alleging suspicious transactions. Same pattern as R136. Your label says legitimate; I read this as scam.",
    "R144-9db84d529e": C + "Impersonates the CBI and threatens that legal action has been initiated. A bare legal threat with no reference number or official route is the textbook advance-fee scam opener. Your label says legitimate; I read this as scam.",
    "R080-6a0eef3094": "Agrees with your label. Genuine-looking credit-card due-date reminder: names the bank, states the minimum due and warns about a late fee, and offers no link or credential request. Flagging only that a Rs 1,000,000 balance with a Rs 99 minimum due is implausible, which suggests a generated example rather than a real alert.",

    # ---------------- marketing_spam: agree ----------------------------------
    "R025-241785aafe": "Commercial promotion for banking cord-blood stem cells, using a 'pregnant?' hook and a free-offer claim. Advertising, with no attempt to take payment or credentials in-message.",
    "R026-46c3f53967": "Carrier offer advertising discounted STD minutes on recharge. Ordinary telecom tariff promotion.",
    "R027-d8a747a9bc": "Retail clearance sale advertising 60% off with a deadline. Standard promotional advertising.",
    "R028-4d05b01943": "Brand-campaign solicitation inviting participation via a Times of India property URL. Advertising rather than fraud - no payment or credential demand.",
    "R029-096bc0c0d3": "Carrier recharge offer promising full talktime credit for a fixed top-up. Commercial tariff promotion.",
    "R031-70c0ab0eb0": "Greeting-card campaign asking the recipient to send a named SMS to a father. Bulk engagement advertising, no financial ask.",
    "R032-200ede2522": "Entertainment campaign tied to an X-Men film, inviting a reply to see a personalised result. Advertising.",
    "R033-06848c8337": "Real-estate launch advertisement for a Gurgaon tower with a home-loan teaser. Property advertising, no credential or payment demand in-message.",
    "R034-30ba6d1221": "Real-estate advertisement for a Noida residential project. Commercial property promotion.",
    "R036-50dde2ba27": "Carrier announcement of a pay-per-call package with free minutes. Tariff promotion.",
    "R037-e57ef82286": "Real-estate rate revision advertisement for Noida projects. Property promotion.",
    "R038-f668b290ce": "Sports quiz asking the recipient to reply Yes/No within 24 hours to receive a free video. Engagement advertising; the reply prompt is a marketing mechanic, not fraud.",
    "R039-da1271efbc": "Sports multiple-choice quiz with four options, promoting prize eligibility. Engagement advertising.",
    "R052-8f2d95aa02": "Work-from-home job advertisement stating an earning figure and a WhatsApp contact. Recruitment marketing; it solicits contact but demands no fee or credentials.",
    "R054-f59111fc42": "Work-from-home job advertisement stating an earning figure and a WhatsApp contact. Recruitment marketing, no fee demanded.",
    "R066-94011c86ae": "Hotel-draw promotion announcing selection for a stay, with no fee or payment step. Prize marketing.",
    "R067-b4978ea51b": "Weekly cash competition advertised with a keyword to text and published terms. SMS-competition marketing.",
    "R070-d3fbb619c3": "Horoscope or lifestyle content sent as bulk SMS. Engagement advertising.",
    "R071-ff209e61ef": "Dating or adult-entertainment solicitation inviting a reply. Premium messaging spam, but no fraud mechanism - commercial, not deceptive.",
    "R072-c78f019e4d": "Teaser engagement spam inviting a reply keyword. Advertising with no financial ask.",
    "R076-88277e0c7c": "Prize promotion for a free week of membership, activated by texting a keyword. No fee demanded, so marketing rather than fraud.",
    "R095-a4c60ae229": "Referral offer giving both parties a discount on a known retailer. Standard affiliate marketing.",
    "R096-7b2a7b66d7": "Charged quiz service advertising horoscope, shloka, love and career results at Rs 1 per SMS. Bulk entertainment marketing; the per-SMS charge is disclosed.",
    "R097-eed78af539": "Streaming-app promotion offering a free first month with a promo code. Advertising, explicitly non-financial.",
    "R098-3c3db8a68b": "Charged quiz service with four reply options and a disclosed Rs 1 charge. Bulk entertainment marketing.",
    "R115-98efc1ae78": "Carrier customer announcement pointing to a website. Advertising with a link but no credential or payment demand.",
    "R117-f3ccb5ed43": "Carrier retention offer of half-price rental and a free handset. Telecom promotion.",
    "R118-f85f33a5e3": "Unsecured-loan advertisement offering sums from GBP 500 to 75,000. Financial product marketing; no fee requested in-message, though advance-fee loans are common in this genre.",
    "R119-218fb13303": "Competition promotion offering entry to a weekly draw for a device, with a standard-rate disclosure. Advertising.",
    "R120-4eeb5e2c9b": "Dating or 'secret admirer' solicitation with a premium-rate number and an opt-out keyword. Premium messaging spam, commercial rather than deceptive.",
    "R126-a7f3ba5542": "Concert ticket promotion offering priority seats or an alternative gift. Prize and product marketing, no fee.",

    # ---------------- marketing_spam: CONFLICTS --------------------------------
    "R001-3aa8a6a9cb": C + "A confirmation that a marathon registration succeeded, giving a bib number. It confirms an action the recipient already took and contains no offer. That is a transactional message. Your label says marketing_spam; I read this as legitimate.",
    "R002-145f6b31bf": C + "An automated platform notification that a profile was viewed. Sent by a service the recipient uses, reporting activity, with no offer attached. Your label says marketing_spam; I read this as legitimate.",
    "R003-286e86937a": C + "An automated end-of-day mutual-fund NAV notification from an investment the recipient holds. Standard transactional alert. Your label says marketing_spam; I read this as legitimate.",
    "R005-37ef2a825f": C + "Prize claim that requires clicking a link and registering. Prize bait plus a registration step is materially closer to the scam boundary than to a plain advertisement, because the register step is where credentials get harvested. Your label says marketing_spam; I lean scam but it is genuinely arguable.",
    "R007-d913294358": C + "'You are the lucky winner, claim your device now' with no qualification and no fee. Claim pressure on a high-value prize. Your label says marketing_spam; I lean scam but this is a boundary case.",
    "R008-30755dff0e": C + "A 0% car loan advertised with a same-day deadline. Zero-interest-for-three-years plus deadline pressure is the standard vehicle for advance-fee loan fraud, although no fee is demanded in this message. Your label says marketing_spam; arguable either way.",
    "R009-13fb917f00": C + "Free year of streaming via a link plus registration. Same prize-plus-registration pattern as R005. Your label says marketing_spam; I lean scam but arguable.",
    "R018-e4848e2571": C + "Recruitment advertising that asks for a Rs 500 form-submission fee. Any employer charging candidates to apply is conducting advance-fee fraud. Your label says marketing_spam; I read this as scam.",
    "R020-61083c9ceb": C + "A romantic message written in SMS shorthand, evidently continuing a personal relationship. There is no offer, no promotion and no request. Your label says marketing_spam; I read this as legitimate.",
    "R035-81a3eeabdc": C + "Claim of selection for a GBP 650,000 oil-industry draw, to be claimed by contacting a named 'Dr'. International prize scams use exactly this doctor/agent framing to extract an advance fee. Your label says marketing_spam; I read this as scam.",
    "R053-10a18b5114": C + "Offers a Rs 25 lakh prize contingent on sending Rs 13,724 by UPI. A prize made conditional on a payment is the advance-fee pattern, and your own rule says promotional-plus-fraudulent resolves to scam. Your label says marketing_spam; I read this as scam.",
    "R065-e514441973": C + "'Today is your lucky day, log onto this URL to find out why' with no stated prize and a shortened link. Undisclosed-reward teaser driving to an unknown destination. Your label says marketing_spam; I lean scam but arguable.",
    "R075-7b5e4a550a": C + "Congratulations on a Rs 12.6 lakh Tata Safari draw, contact this number. Prize claim with a contact number but no fee, so the fraud mechanism is incomplete. Your label says marketing_spam; defensible, though it sits close to the R053/R093 pattern.",
    "R085-ac0bc28709": C + "A 'free gift' contingent on paying a Rs 99 registration fee to a UPI handle. This is exactly the promotional-plus-fraudulent case your rule assigns to scam. Your label says marketing_spam; I read this as scam.",
    "R093-273ebf8c5c": C + "A Rs 25,000 lucky-draw win contingent on a Rs 99 processing fee by UPI. Same as R085: a fee demanded to release a prize. Your label says marketing_spam; I read this as scam. Note the equivalent Telugu message R102 is blank - these are the same template in different languages and should get the same label.",
    "R127-a800514879": C + "'URGENT ... you have won a GBP 800 prize GUARANTEED, call 090...' - urgency, a guaranteed prize and a premium-rate number, but no fee demanded. Your label says marketing_spam, which is defensible. Flagging that the near-identical R079 is blank and should get the same label.",

    # ---------------- scam: agree --------------------------------------------
    "R006-3b53a7907b": "Bank-styled alert announcing a large debit, then demanding a click if the debit was not authorised. Classic smishing structure: alarming balance change plus a link. Scam.",
    "R011-113dbe2d44": "Claims selection for a half-million-dollar UN grant and urges an immediate reply. Unsolicited grant bait with no application process. Scam.",
    "R012-eebb30be0d": "Brand-styled prize award requiring account verification. Prize bait wrapped in a trusted brand name. Scam.",
    "R013-4dd2ecefdb": "Brand impersonation directing the recipient to enter login credentials on a 'secure page'. Explicit credential harvesting. Scam.",
    "R015-d714767355": "Warns of a Rs 45,000 card transaction and asks the recipient to send the OTP to block it. Asking for an OTP is the credential-theft step itself. Scam.",
    "R016-4c0f9a1635": "Payment-app impersonation directing a UPI PIN reset through a link. PIN reset via link is direct account takeover. Scam.",
    "R019-ede589cf6b": "Bank impersonation claiming a card was blocked by an 'RBI circular', with a link to update and unblock. Fake regulatory pretext plus link. Scam.",
    "R055-778e028184": "Urgency plus an expired-KYC pretext demanding immediate verification. Bank KYC threats are the highest-volume Indian SMS scam. Scam.",
    "R058-778e028184": "Duplicate of the same expired-KYC urgency message as R055. Scam.",
    "R087-7c5edc0b7a": "Poses as a known person who 'lost his phone' and needs Rs 25,000 by UPI immediately. Relative-emergency impersonation with an urgent payment demand. Scam.",
    "R091-526e0c9094": "Crime Branch impersonation alleging recovered obscene videos and threatening disclosure. Extortion by police impersonation. Scam.",
    "R140-a1258f3026": "Poses as an inspector and Amazon simultaneously, claiming a held parcel and demanding a clearance charge. Double impersonation plus a payment demand. Scam.",
    "R141-40f3d5cfa0": "National Cyber Cell impersonation claiming pending KYC, a two-hour block deadline, and an OTP request. All three scam mechanisms in one message. Scam.",
    "R142-9caa36081a": "Crime Branch and Amazon impersonation with a held parcel and a Rs 499 clearance charge. Scam.",
    "R143-70bf2980a0": "Congratulations on a Rs 40 lakh lottery win, then a demand for a processing fee. Fee-to-release-prize is the archetypal scam. Scam.",

    # ---------------- scam: CONFLICTS (look like marketing to me) -------------
    "R068-ef48740117": C + "Offers a free colour handset plus 200 free minutes, delivered tomorrow. That is carrier handset marketing, with no credential request and no payment demand. Your label says spam/scam; I read this as marketing_spam.",
    "R069-c7ff18b33a": C + "Adult-entertainment solicitation from a bulk SMS sender, claiming the recipient's area code. Premium messaging spam, not a fraud mechanism. Your label says spam/scam; I read this as marketing_spam.",
    "R073-e12a6e42e5": C + "Sex-chat solicitation inviting the recipient to call a premium-rate number. Commercial adult spam; the number is paid, but nothing is being deceived about money or credentials. I read this as marketing_spam.",
    "R078-b12050383f": C + "Prize claim to be collected by phoning a premium-rate number, with no fee requested. Incomplete fraud mechanism, so this is closer to a prize promotion than a scam. I read this as marketing_spam, though the boundary is close.",
    "R100-9cffcdd077": C + "A lucky-draw win that explicitly states no purchase is needed, to be collected at a store. This is the 'no fee' prize template, i.e. genuine prize marketing. Your label says spam/scam; I read this as marketing_spam. Note the same template in Telugu (R102) is blank - they should match.",
    "R105-bdd9c0df19": C + "Work-from-home recruitment advertising and explicitly stating no registration fee. That is recruitment marketing, not fraud. I read this as marketing_spam.",
    "R106-cc48c36f68": C + "Hinglish version of the same work-from-home recruitment ad with no registration fee. Recruitment marketing. I read this as marketing_spam.",
    "R107-2a6db45b7c": C + "Tenglish version of the same work-from-home recruitment ad with no registration fee. Recruitment marketing. I read this as marketing_spam.",
    "R108-2a6db45b7c": C + "Duplicate of R107, same work-from-home recruitment ad in Tenglish. Recruitment marketing.",
    "R109-2a6db45b7c": C + "Duplicate of R107, same work-from-home recruitment ad in Tenglish. Recruitment marketing.",
    "R116-3c8f8bcd6c": C + "Adult chat solicitation at 25p with a search-postcode prompt. Premium messaging spam with no fraud mechanism. I read this as marketing_spam.",
    "R121-aec1d78cca": C + "Personal-looking adult solicitation inviting a chat. Bulk spam, commercially motivated, no credential or payment deception. I read this as marketing_spam.",
    "R124-7616900a33": C + "Charity music request asking the recipient to text a short code to donate 5p. Commercial charity solicitation with a disclosed charge. Marketing.",
    "R128-31339b33d3": C + "Carrier offer of three hours of talktime for texting a short code. Tariff promotion, the fee is disclosed and it is a real service. Marketing.",
    "R129-51b9480b44": C + "Subscription-service promotion directing the user to a WAP link to redeem credit. Content-subscription marketing. I read this as marketing_spam, though WAP billing links are a known billing-fraud vector, so this one deserves a second look.",

    # ---------------- blank label: suggestions only ---------------------------
    "R004-ca7d4824f7": B + "legitimate - passive notice that a passport is ready for collection. No demand, no link, no urgency.",
    "R010-4fbbb7f6c3": B + "scam - a fake UIDAI update warning, with service disruption used as the threat. Wording matches real UIDAI notices but genuine notices do not carry this shape, and no official link or branch route is given.",
    "R014-1e6e30d10f": B + "scam - threatens a fine for not linking a PAN card to Aadhaar. PAN-Aadhaar linking is a real process but it carries no penalty threat and no payment demand; this is regulatory impersonation.",
    "R041-65d708f6a2": B + "legitimate - Telugu for 'I will come tomorrow'. Pure personal statement, no solicitation. Duplicate of R042.",
    "R042-65d708f6a2": B + "legitimate - same Telugu sentence, 'I will come tomorrow'. Duplicate of R041.",
    "R043-ffb617cf6d": B + "legitimate - Hindi for 'I am coming tomorrow'. Personal statement.",
    "R050-ccc6572d50": B + "scam - announces a prize win then demands immediate payment ('pay now') in Telugu. Prize contingent on a payment is the advance-fee pattern.",
    "R051-11396974a3": B + "scam - same Telugu prize-then-pay-now message with a different amount. Duplicate template of R050.",
    "R056-90567c979f": B + "scam - announces a prize win and asks for the OTP to be shared. Explicit credential solicitation on a promised prize.",
    "R057-a7b07eedd3": B + "scam - same prize-plus-OTP-share message with a different amount. Duplicate template of R056.",
    "R059-8b80875ed8": B + "scam - same prize-plus-OTP-share message with a different amount. Duplicate template of R056.",
    "R074-8ae2ee91d2": B + "marketing_spam - premium-rate call to claim a holiday or cash prize, no fee demanded. Note R127, the near-identical English version, is labelled marketing_spam, so these should match.",
    "R079-1b05b48f65": B + "marketing_spam - urgent guaranteed GBP 800 prize, call a premium-rate number, no fee demanded. This is effectively the same message as R127, which is labelled marketing_spam.",
    "R081-4797aafa5e": B + "legitimate - Telugu credit-card due-date reminder with a minimum-due figure and a late-fee warning. Matches the R080 pattern you already labelled legitimate. The Rs 100,000 balance is implausible, suggesting a generated example.",
    "R086-bd2c0a0645": B + "scam - Cyber Crime Department impersonation telling the recipient not to switch off their phone while claiming an investigation into an illegal transaction. Matches the digital-arrest family you labelled scam in R141.",
    "R088-fec9e5ca0d": B + "scam - poses as the recipient's mother in hospital and demands Rs 50,000 to a UPI handle. Relative-emergency impersonation, same family as R087.",
    "R089-583fc99672": B + "scam - Myntra-branded 'free gift' contingent on a Rs 25 registration fee by UPI. Identical pattern to R085 and R093, which you labelled marketing_spam - all three should get the same label.",
    "R090-207c483d47": B + "scam - fake customs hold on an Uber parcel, a 24-hour deadline, a payment demand and a look-alike 'rbi-verify' domain. Every scam mechanism at once.",
    "R092-3634aa41f4": B + "scam - UIDAI impersonation claiming a fraudulent account was opened in the recipient's name, demanding Aadhaar number and OTP. Matches the aadhaar category.",
    "R094-e4cd09ad70": B + "scam - bank impersonation threatening net-banking deactivation over alleged money laundering, with a document-submission link. Matches R055's expired-KYC family.",
    "R101-79f5ac0a5d": B + "marketing_spam - Hindi version of the bulk SMS-marketing package advertisement. Note R103, the English version of this same template, is labelled legitimate; these should match.",
    "R102-b97c1d52d9": B + "marketing_spam - Telugu lucky-draw win that explicitly requires no purchase, collected at a store. Same 'no fee' template as R100, which you labelled spam/scam; these should match.",
    "R104-9f425e84aa": B + "marketing_spam - Hindi real-estate advertisement for a plot with an EMI figure and a site-visit number. Property marketing, no credential or payment demand.",
}


def main():
    if not SHEET.exists():
        print(f"ERROR: {SHEET} not found")
        sys.exit(1)

    with SHEET.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    if cols != ["review_id", "text", "human_label", "human_reason"]:
        print(f"ERROR: unexpected columns {cols}")
        sys.exit(1)

    labels_before = [r["human_label"] for r in rows]

    missing = []
    for r in rows:
        rid = r["review_id"]
        if rid not in REASONS:
            missing.append(rid)
            continue
        if r["human_reason"].strip():      # never overwrite an existing reason
            continue
        r["human_reason"] = REASONS[rid]

    if missing:
        print(f"ERROR: no reason authored for {len(missing)} rows: {missing[:10]}")
        sys.exit(1)

    # write via a temp file then replace, so the original is never left truncated
    tmp = SHEET.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(SHEET)

    labels_after = [r["human_label"] for r in rows]
    assert labels_before == labels_after, "human_label changed - aborting"

    filled = sum(1 for r in rows if r["human_reason"].strip())
    conflicts = sum(1 for r in rows if r["human_reason"].startswith("CONFLICT"))
    blanks = sum(1 for r in rows if r["human_reason"].startswith("SUGGESTED"))
    print(f"rows: {len(rows)}")
    print(f"human_reason filled : {filled}")
    print(f"  agrees with label : {filled - conflicts - blanks}")
    print(f"  CONFLICT flagged : {conflicts}")
    print(f"  blank label, suggestion given: {blanks}")
    print(f"human_label cells changed: 0 (verified by assertion)")
    print(f"columns unchanged: {cols}")


if __name__ == "__main__":
    main()