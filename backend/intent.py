import csv
import spacy
import re
import dateparser
from dateparser.search import search_dates
from datetime import datetime, timedelta
from difflib import get_close_matches


nlp = spacy.load('en_core_web_sm')

# Common English stopwords to avoid as station matches
STOPWORDS = set([
    'how', 'about', 'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'when', 'where', 'which', 'what', 'who', 'whom',
    'this', 'that', 'these', 'those', 'on', 'in', 'at', 'by', 'for', 'with', 'of', 'to', 'from', 'as', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'do', 'does', 'did', 'have', 'has', 'had', 'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might',
    'must', 'not', 'so', 'just', 'now', 'today', 'tomorrow', 'yesterday', 'please', 'let', 'me', 'you', 'i', 'we', 'they', 'he', 'she', 'it',
    'my', 'your', 'our', 'their', 'his', 'her', 'its', 'mine', 'yours', 'ours', 'theirs', 'him', 'them', 'ourselves', 'yourself', 'yourselves',
    'ourselves', 'themselves', 'myself', 'yourself', 'himself', 'herself', 'itself', 'ourselves', 'themselves', 'also', 'too', 'up', 'down', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'only', 'own', 'same', 'than', 'very', 's', 't', 'can', 'will', 'don', 'should', 'now'
])

date_keywords = [
    "today", "tomorrow", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "next", "jan", "feb", "mar", "apr", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec", "st", "nd", "rd", "th"
]

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
            # Only adjust for am/pm if hour is in 12-hour format (1-12)
            if hour <= 12:
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

        # Only adjust for am/pm if hour is in 12-hour format (1-12)
        if hour <= 12:
            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
        # If hour > 12 and ampm provided, ignore ampm (user mixed formats)

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
    if(len(word) < 3): 
        return None
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
    """Returns the primary intent, deprioritizing greeting if other intents exist."""
    intents = detect_intent(message)
    if not intents:
        return "unknown"
    
    # If only greeting is found, return it
    if len(intents) == 1:
        return intents[0]
    
    # If multiple intents and greeting is in the list, skip it
    if "greeting" in intents:
        non_greeting = [i for i in intents if i != "greeting"]
        return non_greeting[0] if non_greeting else "greeting"
    
    return intents[0]


def get_intents_by_priority(message: str) -> list[str]:
    """Returns all detected intents sorted by priority (greeting deprioritized)."""
    intents = detect_intent(message)
    if not intents:
        return ["unknown"]
    
    # Move greeting to the end if it exists with other intents
    if "greeting" in intents and len(intents) > 1:
        non_greeting = [i for i in intents if i != "greeting"]
        non_greeting.append("greeting")
        return non_greeting
    
    return intents


def validate_date_time(date_str: str, time_str: str = None) -> tuple[bool, str]:

    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check if date is in the past
        if dt.date() < today.date():
            return False, "That date is in the past. Please provide a future date."
        
        # If today's date, check if time is provided and in the past
        if dt.date() == today.date() and time_str:
            try:
                time_obj = datetime.strptime(time_str, "%H:%M").time()
                current_time = datetime.now().time()
                if time_obj <= current_time:
                    return False, "That time has already passed today. Please provide a future time."
            except:
                pass
        
        return True, ""
    except:
        return False, "Invalid date format. Please use DD/MM/YYYY."


def find_stations(message):
    msg = re.sub(r"[^a-z\s]", " ", message.lower())
    words = msg.split()
    found = []

    # Filter out stopwords from words
    filtered_words = [w for w in words if w not in STOPWORDS]

    for i in range(len(filtered_words)):
        for j in range(i + 1, min(i + 4, len(filtered_words) + 1)):
            phrase = " ".join(filtered_words[i:j])
            if phrase in STATIONS and phrase not in found:
                found.append(phrase)
            #check reversed order to catch "London Waterloo" as well as "Waterloo London"
            reversed_phrase = " ".join(reversed(filtered_words[i:j]))
            if reversed_phrase in STATIONS and reversed_phrase not in found:
                found.append(reversed_phrase)

    for w in filtered_words:
        if w in STATIONS and w not in found:
            found.append(w)

    if not found:
        for token in filtered_words:
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
        matched_text = results[0][0].lower().strip()
        # Only accept if the matched text looks like an actual date reference
        has_digit = any(c.isdigit() for c in matched_text)
        has_keyword = any(kw in matched_text for kw in date_keywords)

        if has_digit or has_keyword:
            dt = results[0][1]
            dt = ensure_future_date(dt)
            date_found = dt.date().strftime("%d/%m/%Y")

    if not date_found:
        for ent in doc.ents:
            if ent.label_ == 'DATE':
                ent_text = ent.text.lower().strip()
                has_digit = any(c.isdigit() for c in ent_text)
                has_keyword = any(kw in ent_text for kw in date_keywords)
                if not has_digit and not has_keyword:
                    continue
                normalised = normalise_date(ent_text)
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

    words = re.findall(r"\b[a-z]{3,}\b", message.lower())

    extra_candidates = []

    for word in words:
        if word in stations or word in STOPWORDS:
            continue

        possible = [s for s in STATIONS if s.startswith(word)]

        if len(possible) > 1:
            extra_candidates.extend(possible[:8])

    # merge before route assignment
    all_stations = list(set(stations + extra_candidates))

    # Prevent spurious station assignment if only a date is present and no clear station
    origin, destination, candidates = assign_route(
        message,
        all_stations,
        intent_hint=intent_hint
    )

    # Only assign origin/destination if not just a date and the station is not a stopword
    if origin and origin not in STOPWORDS:
        entities['origin'] = origin
    if destination and destination not in STOPWORDS:
        entities['destination'] = destination

    if candidates:
        if re.search(r"\b(to|for|towards|ticket|pass|fare|buy|purchase)\b", message.lower()) or intent_hint == "find_ticket":
            entities['destination_candidates'] = candidates
        else:
            entities['station_candidates'] = candidates

    for word in words:
        if word in stations or word in STOPWORDS:
            continue

        possible = [s for s in STATIONS if s.startswith(word)]

        if len(possible) > 1:
            if re.search(rf"\bto\s+{word}\b", message.lower()):
                entities["destination_candidates"] = list(set(possible))[:8]
            elif re.search(rf"\bfrom\s+{word}\b", message.lower()):
                entities["origin_candidates"] = list(set(possible))[:8]

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

