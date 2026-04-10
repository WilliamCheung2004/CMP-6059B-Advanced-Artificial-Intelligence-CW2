import spacy
import numpy as np
import re

# spacy.cli.download('en_core_web_sm')
nlp = spacy.load('en_core_web_sm')

STATIONS = []

# Read stations.csv and add to station list
with open('stations.csv', 'r') as f:
    for line in f:
        STATIONS.append(line.strip().lower())

DATE_PATTERN = r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"

INTENTS = {
    # Conversation
    'greeting':  ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
                  'howdy', 'greetings', 'sup', 'morning', 'afternoon', 'evening'],
    'goodbye':   ['bye', 'goodbye', 'farewell', 'see you', 'thanks', 'thank you',
                  'done', 'finished', 'exit', 'quit', 'stop', "that's all"],
    'help':      ['help', 'assist', 'support', 'what can you do', 'how does this work',
                  'options', 'menu', 'confused'],

    # Ticket & journey
    'find_ticket':  ['ticket', 'book', 'buy', 'purchase', 'reserve', 'fare', 'price',
                     'cost', 'cheap', 'cheapest', 'advance', 'anytime', 'off-peak','find'],
    'plan_journey': ['travel', 'journey', 'trip', 'route', 'go', 'get to', 'from',
                     'depart', 'departure', 'arrive', 'arrival', 'via', 'direct',
                     'connection', 'change', 'train','plan'],
    'journey_time': ['how long', 'duration', 'time', 'when', 'earliest', 'latest',
                     'next train', 'last train', 'timetable', 'schedule'],

    # Disruptions & status
    'delay_info':    ['delay', 'delayed', 'late', 'on time', 'running late',
                      'cancellation', 'cancelled', 'disruption', 'diverted'],
    'platform_info': ['platform', 'where', 'which platform', 'stand', 'bay'],
    'live_status':   ['live', 'real time', 'current', 'now', 'today', 'tonight',
                      'status', 'update', 'running'],

    # Passenger info
    'seat_info':   ['seat', 'reservation', 'reserved', 'first class', 'standard',
                    'coach', 'quiet', 'bike', 'wheelchair', 'accessible'],
    'refund_info': ['refund', 'cancel', 'exchange', 'change ticket', 'compensation',
                    'money back', 'railcard'],
}

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

def find_stations(message):
    msg = message.lower()
    found = []

    for station in STATIONS:
        if station in msg:
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

    # fallback logic
    if len(stations) >= 2:
        if not origin and not destination:
            origin, destination = stations[0], stations[1]
        elif not origin:
            origin = stations[0]
        elif not destination:
            destination = stations[1]

    return origin, destination


def extract_entities(message: str) -> dict:
    doc = nlp(message)
    entities = {}

    # DATE & TIME
    for ent in doc.ents:
        if ent.label_ == 'DATE':
            entities['date'] = ent.text
        elif ent.label_ == 'TIME':
            entities['time'] = ent.text

    # Fallback for numeric dates
    if 'date' not in entities:
        match = re.search(DATE_PATTERN, message)
        if match:
            entities['date'] = match.group()

    # Station detection
    stations = find_stations(message)
    origin, destination = assign_route(message, stations)

    if origin:
        entities['origin'] = origin
    if destination:
        entities['destination'] = destination

    return entities


if __name__ == '__main__':
    tests = [
        # Single intent
        "Good morning!",
        "Goodbye!",
        "random gibberish blah blah",
        # Multi-intent
        "I want to book a cheap ticket from Norwich to London tomorrow, what time does it depart?",
        "Can I get a ticket from Norwich to Oxford on the 25th March?",
        "Is my train delayed and what platform is it on?",
        "Will my train arrive on time?",
        "What platform is the next train to Manchester?",
        "Can I get a refund on my ticket?",
        "Is there a quiet coach on the 9am from Leeds?",
        "Find me a ticket 24/10/2026"
    ]

    for msg in tests:
        intents = detect_intent(msg)
        entities = extract_entities(msg)
        primary = intents[0]
        print(f"Message:  '{msg}'")
        print(f"  Primary intent:  {primary}")
        print(f"  All intents:     {intents}")
        print(f"  Entities:        {entities}")
        print()