import csv
import spacy
import re
import dateparser
from datetime import datetime
from difflib import get_close_matches

nlp = spacy.load('en_core_web_sm')

#Loading station names 
STATIONS = []

with open('stations.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    next(reader)  
    for row in reader:
        name = row[0].strip().lower()
        if name:
            STATIONS.append(name)

# date pattern for fallback parsing
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

# main intent classification  
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
        'travel', 'journey', 'trip', 'route', 'go', 'get to', 'from',
        'depart', 'departure', 'arrive', 'arrival', 'via', 'direct',
        'connection', 'change', 'train', 'plan'
    ],

    'journey_time': [
        'how long', 'duration', 'time', 'when', 'earliest', 'latest',
        'next train', 'last train', 'timetable', 'schedule'
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

#Add mroe definitions for handling missing entities 
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
        # direct match on tokens/bigrams
        for kw in keywords:
            if kw in all_tokens:
                matches += 1

        # fuzzy match on single tokens (for typos)
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


# station detection 
def find_stations(message):
    msg = message.lower()
    found = []

    for station in STATIONS:
        if re.search(rf"\b{re.escape(station)}\b", msg):
            found.append(station)

    return found


import re

def assign_route(message, stations):
    msg = message.lower()
    origin = None
    destination = None

    for station in stations:
        if re.search(rf"\bfrom\s+{station}\b", msg):
            origin = station

        if re.search(rf"\bto\s+{station}\b", msg):
            destination = station

    if not origin and not destination and len(stations) == 2:
        origin, destination = stations

    return origin, destination



# Extract entities like date, origin, destination from the message
def     extract_entities(message: str) -> dict:
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

# Testing 
if __name__ == '__main__':
    tests = [
        "I want to book a ticket from Norwich to London tomorrow",
        "Find me a tikcet 24/10/2026",  # typo
        "I need to purchase a pass to Manchester",
        "Is my train running late today?",
        "What platfrom is the service to Leeds on?",  # typo
        "Can I get a refund for a delayed train?",
        "I want to travel on Friday",
        "Can I get a ticket from Colchester to Norwich on the 25th March?",
    ]

    if __name__ == '__main__':
        tests = [
            "I want to book a ticket from Norwich to London tomorrow",
            "Find me a tikcet 24/10/2026",  # typo
            "I need to purchase a pass to Manchester",
            "Is my train running late today?",
            "What platfrom is the service to Leeds on?",  # typo
            "Can I get a refund for a delayed train?",
            "I want to travel on Friday",
            "Can I get a ticket from Colchester to Norwich on the 25th March?",
            "Hello, how are you?",  
            "What's the next train from Cambridge to Oxford?"
        ]

        for msg in tests:
            intent = detect_primary_intent(msg)
            entities = extract_entities(msg)
            print(f"Message: '{msg}'")
            print(f"  Intent: {intent}")
            print(f"  Entities: {entities}")
            print()

