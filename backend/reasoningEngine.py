#reasoningEngine.py

#to start the model server before running this script, run:
#   ollama run mistral

import requests
from intentClassifier import classify_intent 
from intent import detect_primary_intent, extract_entities, find_stations, extract_time_semantic, detect_intent, get_station_code
from APIData import print_journey_details,get_ticket_prices,get_timestamp
import json
from knowledge_base import get_faq, get_booking_rule, KB
from delayPrediction import predict_arrival_delay
import re

confidence_threshold = 0.6


BASE_SYSTEM_PROMPT = """
You are a train assistant.

Rules:
- Only help with: journey planning, tickets, disruptions, refunds
- Max 2 short sentences
- Never invent times, prices, schedules
- Do not greet user unless specified
- Speak only in formal tone
"""

conversation_state = {
    "intent": None,
    "entities": {},
    "awaiting_next_action": False,
    "asking_for": None  
}

delay_state = {
    "current_station": None,
    "current_delay": None,
    "destination": None,
    "asking_for": None
}

REQUIRED_FIELDS = ["origin", "destination", "date", "time"]

#map intents to KB keywords
intent_to_faq = {
    "refund_info": "refund",
    "delay_info": "delay",
    "seat_info": "seat",
    "platform_info": "platform",
    "live_status": "live",
}

#map general phrases to KB sections
section_triggers = {
    "ticket_types": ["ticket type", "types of ticket", "ticket options", "kinds of ticket"],
    "railcards": ["railcard", "rail card", "discount card"],
    "booking_rules": ["when to book", "how to book", "split ticket", "split ticketing", "booking tips", "save money"],
    "faqs": ["faq", "frequently asked", "common questions"],
}

#format a KB section so that the chatbot can return it as a message
def format_section(section: str) -> str:
    return "\n".join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in KB[section].items())

#generic KB lookup across all sections
def get_kb_answer(user_input: str) -> str:
    user_input_lower = user_input.lower()
    
    #check for section-level match first
    for section, triggers in section_triggers.items():
        if any(trigger in user_input_lower for trigger in triggers):
            return format_section(section)
        
    sections = ["railcards", "ticket_types", "stations", "rules", "faqs", "delay_repay"]
    for section in sections:
        for key, value in KB.get(section, {}).items():
            if key in user_input_lower:
                return value
    return None

def phrase_kb_answer(raw_answer: str, user_input: str) -> str:
    prompt = f"""
You are a train assistant.

A user asked: "{user_input}"

Here is the relevant information from our knowledge base:
{raw_answer}

Rules:
- Rephrase this information naturally and conversationally
- Do NOT invent any additional information beyond what is provided
- Keep it concise, 2-4 sentences maximum
- Formal tone
"""
    return chatbot([{"role": "user", "content": prompt}]) or raw_answer

def handle_knowledge_query(user_input: str, intent: str) -> str:
    answer = get_kb_answer(user_input)
    if answer:
        reset_state()
        return phrase_kb_answer(answer, user_input)
    
    #fallback to intent-mapped FAQ answer if no direct match in KB
    faq_key = intent_to_faq.get(intent)
    if faq_key:
        answer = get_faq(faq_key)
        if answer:
            return answer  #return answer from the KB's FAQ if available

    #fall back to LLM if KB has nothing
    return chatbot([{"role": "user", "content": user_input}]) or "Sorry, I don't have an answer for that right now."

def reset_delay_state():
    delay_state["current_station"] = None
    delay_state["current_delay"] = None
    delay_state["destination"] = None
    delay_state["asking_for"] = None
    
def is_delay_prediction_request(user_input: str) -> bool:
    triggers = [
        "my train is delayed", "train is running late", "delayed by",
        "minutes late", "minutes delayed", "predict", "arrive at waterloo",
        "when will it arrive", "i am on a train", "on the train"
    ]
    return any(t in user_input.lower() for t in triggers)

def handle_delay_prediction(user_input: str) -> str:
    text = user_input.lower()
    
    #try to extract current station
    if delay_state["current_station"] is None:
        stations = find_stations(user_input)
        if stations:
            code = get_station_code(stations[0])
            if code:
                delay_state["current_station"] = code
                
    #then try to extract current delay in minutes
    elif delay_state["current_delay"] is None:
        match = re.search(r"(\d+)\s*(min|minute|minutes)?", text)
        if match:
            delay_state["current_delay"] = int(match.group(1))
                
    #then try to extract destination
    elif delay_state["destination"] is None:
        stations = find_stations(user_input)
        if stations and delay_state["current_station"] is not None:
            for s in stations:
                code = get_station_code(s)
                if code and code != delay_state["current_station"]:
                    delay_state["destination"] = code
                    break

    #ask for missing info step by step
    if delay_state["current_station"] is None:
        delay_state["asking_for"] = "current_station"
        return "Which station are you currently at?"

    if delay_state["current_delay"] is None:
        delay_state["asking_for"] = "current_delay"
        return "How many minutes is your train currently delayed?"
    
    if delay_state["destination"] is None:
        delay_state["asking_for"] = "destination"
        return "What is your destination station?"
    
    #check destination is Waterloo — model only works for this route
    if delay_state["destination"] != "WAT":
        reset_delay_state()
        reset_state()
        return "I can currently only predict arrival delays for trains arriving at London Waterloo."

    #all info collected — run prediction
    result = predict_arrival_delay(
        current_station=delay_state["current_station"],
        current_delay_mins=delay_state["current_delay"]
    )
    reset_delay_state()
    reset_state()
    return result["message"]

def get_missing_fields(entities):
    return [f for f in REQUIRED_FIELDS if f not in entities]

def is_uncertain(text):
    text = text.lower().strip()

    uncertain_phrases = [
        "not sure", "dont know", "don't know", "idk",
        "unsure", "no idea", "not really"
    ]

    weak_responses = ["no", "nope", "nah", "?", "??", "???"]

    return any(p in text for p in uncertain_phrases) or text in weak_responses

#Reset per finished topic
def reset_state():
    conversation_state["intent"] = None
    conversation_state["entities"] = {}
    conversation_state["awaiting_next_action"] = False

#Ollama Chatbot
def chatbot(messages):
    url = "http://localhost:11434/api/chat"

    payload = {
        "model": "mistral:7b",
        "messages": [{"role": "system", "content": BASE_SYSTEM_PROMPT}] + messages,
        "stream": False
    }

    try:
        r = requests.post(url, json=payload)
        if not r.ok:
            return None
        return r.json()["message"]["content"]
    except:
        return None    
    
#Using intent keyword or classifier
def get_intent(message: str):
    intent = detect_primary_intent(message)
    if intent != "unknown":
        return intent, 1.0

    ml_intent, ml_conf = classify_intent(message)
    if ml_conf >= confidence_threshold:
        return ml_intent, ml_conf

    return "unknown", ml_conf


#Pick one of the stations the user thinks 
def ask_user_to_clarify_station(field, candidates):
    numbered = "\n".join(f"{i+1}. {s.title()}" for i, s in enumerate(candidates))
    prompt = f"""
You are a train assistant.

Ask the user to pick their {field} station from this list:
{numbered}

Rules:
- 1-2 sentences
- natural tone
- list the options numbered
"""
    response = chatbot([{"role": "user", "content": prompt}])
    if response:
        return response
    # fallback
    options_str = "\n".join(f"{i+1}. {s.title()}" for i, s in enumerate(candidates))
    return f"Which {field} station did you mean?\n{options_str}"


#Given station wasn't in dataset
def ask_station_not_found(field):
    prompt = f"""
You are a train assistant.

Tell the user their {field} station wasn't recognised and ask them to try again.

Rules:
- 1 short sentence
- natural tone
"""
    response = chatbot([{"role": "user", "content": prompt}])
    if response:
        return response
    return f"Sorry, I couldn't find that {field} station — could you try again?"


#Given station name is similar to other ones
def resolve_candidate_from_input(user_input, candidates):

    text = user_input.strip().lower()

    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
        return None

    for candidate in candidates:
        if text in candidate or candidate.startswith(text):
            return candidate

    return None


#Keep asking given a detail not given yet
def reask_for_field(field):
    conversation_state["asking_for"] = field  # track what we're waiting for

    prompt = f"""
You are a train assistant.
Ask the user for their {field}.
- 1 short sentence
- natural tone
"""
    response = chatbot([{"role": "user", "content": prompt}])
    if response:
        return response

    fallback = {
        "origin": "Where are you travelling from?",
        "destination": "Where are you going to?",
        "date": "When would you like to travel?",
        "time": "What time would you like to travel?"
    }
    return fallback.get(field, "Could you clarify?")


def handle_plan_journey(user_input):
    ents = conversation_state["entities"]

    #Prevent Same origin and destination 
    if ents.get("origin") and ents.get("destination"):
        if ents["origin"] == ents["destination"]:
            del ents["destination"]
            conversation_state["asking_for"] = "destination"
            return "Your origin and destination can't be the same. Where would you like to travel to instead?"

    new_ents = extract_entities(user_input)
    asking_for = conversation_state.get("asking_for")

    if asking_for and asking_for not in ents:
        for candidate_key in ("origin_candidates", "destination_candidates", "station_candidates"):
            if candidate_key in new_ents:
                new_ents[f"{asking_for}_candidates"] = new_ents.pop(candidate_key)
                break

        for wrong_slot in ("origin", "destination"):
            if wrong_slot in new_ents and wrong_slot != asking_for:
                new_ents[asking_for] = new_ents.pop(wrong_slot)
                break

    for slot in ("origin", "destination"):
        candidate_key = f"{slot}_candidates"
        if candidate_key in ents:
            resolved = resolve_candidate_from_input(user_input, ents[candidate_key])
            if resolved:
                ents[slot] = resolved
                del ents[candidate_key]
                conversation_state["asking_for"] = None
            else:
                if candidate_key in new_ents:
                    ents[candidate_key] = new_ents[candidate_key]
                return ask_user_to_clarify_station(slot, ents[candidate_key])

    for key, value in new_ents.items():
        if key == asking_for:
            ents[key] = value
        elif key not in ents:
            ents[key] = value

    for slot in ("origin", "destination"):
        candidate_key = f"{slot}_candidates"
        if candidate_key in ents and slot not in ents:
            return ask_user_to_clarify_station(slot, ents[candidate_key])

    conversation_state["entities"] = ents

    raw_stations = find_stations(user_input)
    if not raw_stations and asking_for in ("origin", "destination"):
        return ask_station_not_found(asking_for)

    missing = get_missing_fields(ents)
    if missing:
        return reask_for_field(missing[0])

    return generate_journey_response(ents)

#User given that they gave all information 
def generate_journey_response(ents):
    origin = ents["origin"]
    destination = ents["destination"]
    date = ents["date"]
    time = ents.get("time")

    # 1. LLM confirmation message
    confirm_prompt = f"""
You are a train assistant.

Confirm and summarise the journey.

Rules:
- 1–2 sentences
- no schedules
- no greeting
- formal
- end with ONLY: "Here are some live times found:"
- do NOT invent times or prices, link or recommend anything

From: {origin}
To: {destination}
Date: {date}
Time: {time if time else "Not provided"}
"""

    confirmation = chatbot([{"role": "user", "content": confirm_prompt}]) 

    # Getting station code for API
    origin_code = get_station_code(origin)
    destination_code = get_station_code(destination)

    if not origin_code or not destination_code:
        return confirmation + "\n\nError: could not find valid station codes."

    #Getting Time in time format
    depart_time = get_timestamp(date, time)
    if not depart_time:
        return confirmation + "\n\nI need a valid date and time before I can fetch journey details."

    # Fetch API Data
    journey_data = print_journey_details(origin_code, destination_code, depart_time)

    journey_json = json.dumps(journey_data, indent=2)

    # Format data via LLM
    format_prompt = f"""
You are a train assistant.

Reformat the following journey data into a clean readable list.
Rules:
- Do NOT invent times, prices, or stations
- Only reformat what is provided
- Use bullet points or short lines
- Keep it formal

Journey data:
{journey_json}
"""

    formatted = chatbot([{"role": "user", "content": format_prompt}]) or "Unable to format journey details."

    return confirmation + "\n\n" + formatted


#What happens after user is done with intent
def handle_post_completion(user_input):

    text = user_input.lower().strip()

    intent, _ = get_intent(user_input)

    if intent in ["plan_journey", "find_ticket", "refund_info", "delay_info"]:
        conversation_state["awaiting_next_action"] = False
        conversation_state["intent"] = intent
        return process_user_input(user_input)

    if any(x in text for x in ["yes", "ok", "sure", "yeah", "yep"]):
        reset_state()
        return "What else can I help you with — journeys, tickets, delays, or refunds?"
    
    reset_state()
    return "Anything else I can help with?"

#Getting intent
def process_user_input(user_input: str):

    if conversation_state["awaiting_next_action"]:
        return handle_post_completion(user_input)
    
    #if already mid-delay prediction conversation, continue it
    if any(delay_state[k] is not None for k in ["current_station", "current_delay", "destination", "asking_for"]):
        return handle_delay_prediction(user_input)
    
    #check for delay prediction BEFORE station detection and KB lookup
    if is_delay_prediction_request(user_input):
        return handle_delay_prediction(user_input)
    
    stations = find_stations(user_input)
    if stations and conversation_state["intent"] is None:
        conversation_state["intent"] = "plan_journey"

    if conversation_state["intent"] in ["plan_journey", "find_ticket"]:
        intent = conversation_state["intent"]
    else:
        intent, confidence = get_intent(user_input)
        if confidence > 0.6:
            conversation_state["intent"] = intent

    intent = conversation_state["intent"]

    #handle greetings with fallback to next intent
    if intent == "greeting":
        all_intents = detect_intent(user_input)  #get the full ranked list
        non_greeting = [i for i in all_intents if i not in ("greeting", "unknown")]
        if non_greeting:
            intent = non_greeting[0]  #use the next best intent instead
            conversation_state["intent"] = intent
        else:
            reset_state()
            return "Hi! How can I help?"
        
    #check KB before routing to journey planning
    # - catches questions like "what types of ticket are there?"
    kb_answer = get_kb_answer(user_input)
    if kb_answer:
        reset_state()
        return phrase_kb_answer(kb_answer, user_input)
    
    if intent in ["plan_journey", "find_ticket"]:
        return handle_plan_journey(user_input)

    if intent in ["refund_info", "delay_info", "seat_info", "platform_info", "live_status"]:
        return handle_knowledge_query(user_input, intent)
    
    return "Sorry I can only help with: journey planning, tickets, disruptions, refunds."


#Main Chatbot Start
if __name__ == "__main__":
    print("Assistant: Hi! I can help with train journeys, tickets, disruptions, or refunds.")

    while True:
        user_input = input("User: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        response = process_user_input(user_input)
        print("Assistant:", response)