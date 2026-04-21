import csv
import spacy
import re
import dateparser
from dateparser.search import search_dates
from datetime import datetime, timedelta
from difflib import get_close_matches

nlp = spacy.load('en_core_web_sm')

#Loading station names 
STATIONS = []
STATION_CODE = {}

with open('stations.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        raw = row[0].strip()
        name = raw.split(',')[0].strip().lower()
        code = row[1].strip().upper() if len(row) > 1 else None

        if name:
            STATIONS.append(name)
            STATION_CODE[name] = code

def get_station_code(station_name: str):
    if not station_name:
        return None
    key = station_name.strip().lower()
    return STATION_CODE.get(key)


# normalise station list once after loading
def _normalise_station_name(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

STATIONS = [_normalise_station_name(s) for s in STATIONS]
DATE_PATTERN = r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"

# parsing dates from text
def normalise_date(text):
    parsed = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now()
        }
    )
    if not parsed:
        return None
    return parsed.strftime("%d/%m/%Y")

def is_future_date(date_str):
    try:
        d = datetime.strptime(date_str, "%d/%m/%Y")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return d >= today
    except:
        return False

def extract_time(text):
    results = search_dates(text)
    if not results:
        return None
    dt = results[0][1]
    return dt.strftime("%H:%M")

TIME_RANGES = {
    "early morning": "06:00",
    "morning": "09:00",
    "late morning": "11:00",
    "afternoon": "12:00",
    "early afternoon": "13:00",
    "late afternoon": "16:00",
    "early evening": "18:00",
    "evening": "19:00",
    "late evening": "21:00",
    "night": "22:00",
    "midnight": "00:00",
    "lunchtime": "12:00",
}

#Handling of if user does pm or am in time 
def extract_time_semantic(text):
    text_l = text.lower().strip()

    if "12pm" in text_l or "12 pm" in text_l:
        return "12:00"   
    if "12am" in text_l or "12 am" in text_l:
        return "00:00"   

    for phrase, hhmm in TIME_RANGES.items():
        if phrase in text_l:
            return hhmm

    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text_l)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        ampm = m.group(3)

        if ampm:
            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0

        return f"{hour:02d}:{minute:02d}"

    # 2. H am/pm (e.g., 7pm, 6am)
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text_l)
    if m:
        hour = int(m.group(1))
        ampm = m.group(2)

        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:00"

    return None


# main intents  
INTENTS = {
    'greeting':  [
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
        'howdy', 'greetings', 'sup', 'morning', 'afternoon', 'evening'
    ],

    'goodbye':   [
        'bye', 'goodbye', 'farewell', 'see you', 'thanks', 'thank you',
        'done', 'finished', 'exit', 'quit', 'stop', "that's all"
    ],

    'help':      [
        'help', 'assist', 'support', 'what can you do', 'what you do',
        'how does this work', 'options', 'menu', 'confused', 'not sure',
        'need guidance', 'unsure'
    ],

    'find_ticket':  [
        'ticket', 'book', 'buy', 'purchase', 'reserve', 'fare', 'price',
        'cost', 'cheap', 'cheapest', 'advance', 'anytime', 'off-peak'
    ],

    'plan_journey': [
        'travel', 'journey', 'trip', 'route', 'get to', 'from',
        'depart', 'departure', 'arrive', 'arrival', 'via', 'direct',
        'connection', 'change', 'plan'
    ],

    'journey_time': [
        'how long', 'duration', 'time', 'when', 'earliest', 'latest',
        'next train', 'last train', 'timetable', 'schedule', "pm", "am"
    ],

    'delay_info':    [
        'delay', 'delayed', 'late', 'on time', 'running late',
        'cancellation', 'cancelled', 'disruption', 'diverted'
    ],

    'platform_info': [
        'platform', 'where', 'which platform', 'stand', 'bay'
    ],

    'live_status':   [
        'live', 'real time', 'current', 'now', 'today', 'tonight',
        'status', 'update', 'running'
    ],

    'seat_info':   [
        'seat', 'reservation', 'reserved', 'first class', 'standard',
        'coach', 'quiet', 'bike', 'wheelchair', 'accessible'
    ],

    'refund_info': [
        'refund', 'cancel', 'exchange', 'change ticket', 'compensation',
        'money back', 'railcard'
    ],
}

#Synonyms for keywords
SYNONYMS = {
    "book": ["reserve", "purchase", "buy", "obtain"],
    "ticket": ["fare", "pass", "booking"],
    "travel": ["journey", "trip", "commute", "go"],
    "delay": ["late", "behind schedule", "running late"],
    "platform": ["stand", "bay", "track"],
    "refund": ["compensation", "money back", "reimbursement"],
    "seat": ["chair", "place"],
    "train": ["service"],
}

#Adding more definitions for handling missing entities 
def expand_intents(intents, synonyms):
    expanded = {}
    for intent, keywords in intents.items():
        expanded[intent] = set(keywords)
        for kw in keywords:
            if kw in synonyms:
                expanded[intent].update(synonyms[kw])
    return expanded

INTENTS = expand_intents(INTENTS, SYNONYMS)

#Fuzzy matching - if no direct keyword matches, check for close matches to handle typos and variations.
def fuzzy_match(word, keywords, cutoff=0.8):
    matches = get_close_matches(word, keywords, n=1, cutoff=cutoff)
    return matches[0] if matches else None

# Intent detection based on keyword matching, bigrams, and fuzzy matching
def detect_intent(message: str) -> list[str]:
    doc = nlp(message.lower())
    tokens = [token.text.lower() for token in doc]
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    all_tokens = set(tokens + bigrams)

    scores = {}

    for intent, keywords in INTENTS.items():
        matches = 0
        for kw in keywords:
            if kw in all_tokens:
                matches += 1

        if matches == 0: 
            for token in tokens:
                if fuzzy_match(token, keywords):
                    matches += 1
                    break

        if matches > 0:
            scores[intent] = matches

    return sorted(scores, key=lambda x: scores[x], reverse=True) if scores else ['unknown']

def detect_primary_intent(message: str) -> str:
    intents = detect_intent(message)
    return intents[0] if intents else "unknown"


def find_stations(message):
    msg = re.sub(r"[^a-z\s]", " ", message.lower())
    words = msg.split()
    found = []

    for i in range(len(words)):
        for j in range(i + 1, min(i + 4, len(words) + 1)):
            phrase = " ".join(words[i:j])
            if phrase in STATIONS and phrase not in found:
                found.append(phrase)

    for w in words:
        if w in STATIONS and w not in found:
            found.append(w)

    if not found:
        for token in words:
            if len(token) < 3:
                continue
            prefix_matches = [s for s in STATIONS if s == token or s.startswith(token + " ")]
            for m in prefix_matches:
                if m not in found:
                    found.append(m)

    return found

#Finding origin to destination or the possible ones
def assign_route(message, stations, intent_hint=None):
    msg = message.lower()
    origin = None
    destination = None
    candidates = None

    for station in stations:
        if re.search(rf"\bfrom\s+{re.escape(station)}\b", msg):
            origin = station
        if re.search(rf"\bto\s+{re.escape(station)}\b", msg):
            destination = station

    if origin or destination:
        return origin, destination, None

    if len(stations) >= 2:
        prefixes = {s.split()[0] for s in stations if s}
        if len(prefixes) == 1:
            return None, None, stations
        return stations[0], stations[1], None

    if len(stations) == 1:
        token = stations[0]
        if re.search(r"\b(to|for|towards|ticket|pass|fare|buy|purchase)\b", msg) or intent_hint == "find_ticket":
            return None, token, None
        return token, None, None

    return None, None, None

def ensure_future_date(dt):
    today = datetime.now().date()
    if dt.date() <= today:
        return dt + timedelta(days=7)
    return dt

def user_provided_time(text):
    return bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b", text.lower()))


# Extract entities like date, origin, destination from the message
def extract_entities(message: str):
    doc = nlp(message)
    entities = {}

    date_found = None

    results = search_dates(message)
    if results:
        dt = results[0][1]              
        dt = ensure_future_date(dt)     
        date_found = dt.date().strftime("%d/%m/%Y")


    if not date_found:
        for ent in doc.ents:
            if ent.label_ == 'DATE':
                normalised = normalise_date(ent.text)
                if normalised:
                    date_found = normalised
                    break

    if not date_found:
        match = re.search(DATE_PATTERN, message)
        if match:
            normalised = normalise_date(match.group())
            if normalised:
                date_found = normalised

    if date_found:
        entities["date"] = date_found

    
    t = extract_time_semantic(message)

    if t == "00:00" and not user_provided_time(message):
        t = None

    if t:
        entities["time"] = t


    intent_hint = detect_primary_intent(message)

    stations = find_stations(message)
    origin, destination, candidates = assign_route(message, stations, intent_hint=intent_hint)

    if origin:
        entities['origin'] = origin
    if destination:
        entities['destination'] = destination

    if candidates:
        if re.search(r"\b(to|for|towards|ticket|pass|fare|buy|purchase)\b", message.lower()) or intent_hint == "find_ticket":
            entities['destination_candidates'] = candidates
        else:
            entities['station_candidates'] = candidates

    return entities  

# Testing 
if __name__ == '__main__':
    # tests = [
    #         "I want to book a ticket from Norwich to London tomorrow",
    #         "Find me a tikcet 24/10/2026",  # typo
    #         "I need to purchase a pass to Manchester",
    #         "Is my train running late today?",
    #         "What platfrom is the service to Leeds on?",  # typo
    #         "Can I get a refund for a delayed train?",
    #         "I want to travel on Friday",
    #         "Can I get a ticket from Colchester to Norwich on the 25th March?",
    #         "Hello, how are you?",  
    #         "What's the next train from Cambridge to Oxford?"
    #     ]

    # for msg in tests:
    #         intent = detect_primary_intent(msg)
    #         entities = extract_entities(msg)
    #         print(f"Message: '{msg}'")
    #         print(f"  Intent: {intent}")
    #         print(f"  Entities: {entities}")
    #         print()
    # print(get_station_code("Norwich"))
    pass

