import csv
import spacy
import numpy as np
import re
import dateparser
from datetime import datetime

nlp = spacy.load('en_core_web_sm')

# -----------------------------
# LOAD STATIONS (FIRST COLUMN ONLY)
# -----------------------------
STATIONS = []

with open('stations.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    next(reader)  # skip header row
    for row in reader:
        name = row[0].strip().lower()
        if name:
            STATIONS.append(name)

# -----------------------------
# DATE PATTERN (fallback)
# -----------------------------
DATE_PATTERN = r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"

# -----------------------------
# NATURAL LANGUAGE DATE PARSER
# -----------------------------
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

# -----------------------------
# INTENT KEYWORDS
# -----------------------------
INTENTS = {
    'greeting':  ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
                  'howdy', 'greetings', 'sup', 'morning', 'afternoon', 'evening'],

    'goodbye':   ['bye', 'goodbye', 'farewell', 'see you', 'thanks', 'thank you',
                  'done', 'finished', 'exit', 'quit', 'stop', "that's all"],

    'help':      ['help', 'assist', 'support', 'what can you do', "what you do" 'how does this work',
                  'options', 'menu', 'confused', 'not sure', 'need guidance', 'unsure'],

    'find_ticket':  ['ticket', 'book', 'buy', 'purchase', 'reserve', 'fare', 'price',
                     'cost', 'cheap', 'cheapest', 'advance', 'anytime', 'off-peak'],

    'plan_journey': ['travel', 'journey', 'trip', 'route', 'go', 'get to', 'from',
                     'depart', 'departure', 'arrive', 'arrival', 'via', 'direct',
                     'connection', 'change', 'train','plan'],

    'journey_time': ['how long', 'duration', 'time', 'when', 'earliest', 'latest',
                     'next train', 'last train', 'timetable', 'schedule'],

    'delay_info':    ['delay', 'delayed', 'late', 'on time', 'running late',
                      'cancellation', 'cancelled', 'disruption', 'diverted'],

    'platform_info': ['platform', 'where', 'which platform', 'stand', 'bay'],

    'live_status':   ['live', 'real time', 'current', 'now', 'today', 'tonight',
                      'status', 'update', 'running'],

    'seat_info':   ['seat', 'reservation', 'reserved', 'first class', 'standard',
                    'coach', 'quiet', 'bike', 'wheelchair', 'accessible'],

    'refund_info': ['refund', 'cancel', 'exchange', 'change ticket', 'compensation',
                    'money back', 'railcard'],
}

# -----------------------------
# INTENT DETECTION
# -----------------------------
def detect_intent(message: str) -> list[str]:
    doc = nlp(message.lower())
    tokens = [token.text.lower() for token in doc]
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    all_tokens = set(tokens + bigrams)

    scores = {}
    for intent, keywords in INTENTS.items():
        matches = sum(1 for kw in keywords if kw in all_tokens)
        if matches > 0:
            scores[intent] = matches

    return sorted(scores, key=lambda x: scores[x], reverse=True) if scores else ['unknown']

def detect_primary_intent(message: str) -> str:
    intents = detect_intent(message)
    return intents[0] if intents else "unknown"

# -----------------------------
# STATION DETECTION
# -----------------------------
def find_stations(message):
    msg = f" {message.lower()} "
    found = []

    for station in STATIONS:
        if f" {station} " in msg:
            found.append(station)

    return found

def assign_route(message, stations):
    msg = message.lower()
    origin = None
    destination = None

    for station in stations:
        if f"from {station}" in msg:
            origin = station
        if f"to {station}" in msg:
            destination = station

    # fallback: "colchester to norwich"
    if not origin and not destination and len(stations) == 2:
        origin, destination = stations

    return origin, destination

# -----------------------------
# ENTITY EXTRACTION
# -----------------------------
def extract_entities(message: str) -> dict:
    doc = nlp(message)
    entities = {}

    # DATE (natural language)
    for ent in doc.ents:
        if ent.label_ == 'DATE':
            normalised = normalise_date(ent.text)
            if normalised:
                entities['date'] = normalised

    # Fallback numeric date
    if 'date' not in entities:
        match = re.search(DATE_PATTERN, message)
        if match:
            normalised = normalise_date(match.group())
            if normalised:
                entities['date'] = normalised

    # Station detection
    stations = find_stations(message)
    origin, destination = assign_route(message, stations)

    if origin:
        entities['origin'] = origin
    if destination:
        entities['destination'] = destination

    return entities


# -----------------------------
# TESTING
# -----------------------------
if __name__ == '__main__':
    tests = [
        "I want to book a ticket from Norwich to London tomorrow",
        "Find me a ticket 24/10/2026",
        "I want to travel on Friday",
        "I want to travel next Friday",
        "I want to travel on the 5th",
        "I want to travel on 24th January",
        "I want to travel yesterday",
        "Can I get a ticket from Colchester to Norwich on the 25th March?",
    ]

    for msg in tests:
        intents = detect_intent(msg)
        entities = extract_entities(msg)
        print(f"Message: '{msg}'")
        print(f"  Primary intent: {intents[0]}")
        print(f"  Entities: {entities}")
        print()
