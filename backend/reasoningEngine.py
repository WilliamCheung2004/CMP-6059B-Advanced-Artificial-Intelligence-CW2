import requests
from intentClassifier import classify_intent 
from intent import detect_primary_intent, extract_entities, find_stations, extract_time_semantic, detect_intent, get_station_code
from APIData import print_journey_details,get_timestamp, get_ticket_prices
from knowledge_base import get_faq, KB
from delayPrediction import predict_arrival_delay
import re
from database import save_message, save_journey, init_db
from expertSystem import parse_traveller_info, RAILCARD_DISCOUNTS, TicketBot, Journey, TicketPreference, Railcard
import uuid
import json
from datetime import datetime

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
    "asking_for": None,  
}

ticket_state = {
    "last_journey_options" : None,
    "last_ticket_options" : None,
    "last_filtered_tickets" : None,
    "ticket_step":None,
    "ticket_state":False,
    "fare_class":None,
    "railcard":None,
    "ticket_preference":None
}

delay_state = {
    "current_station": None,
    "current_delay": None,
    "destination": None,
    "asking_for": None
}

session_id = str(uuid.uuid4())  

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
        "my train is delayed",
        "train is running late",
        "delayed by",
        "minutes late",
        "minutes delayed",
        "i am on a train",
        "on the train"
    ]
    return any(t in user_input.lower() for t in triggers)

def handle_delay_prediction(user_input: str) -> str:
    text = user_input.lower()
    asking_for = delay_state.get("asking_for")

    # If we know what we're waiting for, only extract that field
    if asking_for == "current_station":
        stations = find_stations(user_input)
        if stations:
            code = get_station_code(stations[0])
            if code:
                delay_state["current_station"] = code
                delay_state["asking_for"] = None

    elif asking_for == "current_delay":
        match = re.search(r"(\d+)\s*(min|minute|minutes)?", text)
        if match:
            delay_state["current_delay"] = int(match.group(1))
            delay_state["asking_for"] = None

    elif asking_for == "destination":
        if "waterloo" in text and "merseyside" not in text:
            delay_state["destination"] = "WAT"
            delay_state["asking_for"] = None
        else:
            stations = find_stations(user_input)
            for s in stations:
                code = get_station_code(s)
                if code and code != delay_state["current_station"]:
                    delay_state["destination"] = code
                    delay_state["asking_for"] = None
                    break

    else:
        # First message — try to extract everything at once
        stations = find_stations(user_input)
        if stations:
            code = get_station_code(stations[0])
            if code:
                delay_state["current_station"] = code

        match = re.search(r"(\d+)\s*(min|minute|minutes)", text)
        if match:
            delay_state["current_delay"] = int(match.group(1))

        if "waterloo" in text and "merseyside" not in text:
            delay_state["destination"] = "WAT"

    # Ask for whatever is still missing
    if delay_state["current_station"] is None:
        delay_state["asking_for"] = "current_station"
        return "Which station are you currently at?"

    if delay_state["current_delay"] is None:
        delay_state["asking_for"] = "current_delay"
        return "How many minutes is your train currently delayed?"

    if delay_state["destination"] is None:
        delay_state["asking_for"] = "destination"
        return "What is your destination station?"

    if delay_state["destination"] != "WAT":
        reset_delay_state()
        reset_state()
        return "I can currently only predict arrival delays for trains arriving at London Waterloo."

    # All info collected — run prediction
    result = predict_arrival_delay(
        current_station=delay_state["current_station"],
        current_delay_mins=delay_state["current_delay"]
    )
    if result["predicted_delay"] is None:
        #station not in model — ask again without resetting everything
        delay_state["current_station"] = None
        delay_state["asking_for"] = "current_station"
        return result["message"]  #shows the helpful list of known stations
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
    conversation_state["asking_for"] = None

def reset_ticket_state():
    ticket_state["last_journey_options"] = None
    ticket_state["last_ticket_options"] = None
    ticket_state["last_filtered_tickets"] = None
    ticket_state["ticket_step"] = None
    ticket_state["ticket_state"] = False
    ticket_state["fare_class"] = None
    ticket_state["railcard"] = None
    ticket_state["ticket_preference"] = None

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
def clarify_station(field, candidates):
    numbered = "\n".join(f"{i+1}. {s.title()}" for i, s in enumerate(candidates))
    prompt = f"""
You are a train assistant.

Ask the user to pick their {field} station from this list:
{numbered}

Rules:
- 1-2 sentences
- natural tone
- list the options numbered
- do not repond with anything to do with the rules
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
    prompts = {
        "origin": "Where are you travelling from?",
        "destination": "Where are you going to?",
        "date": "What date would you like to travel?",
        "time": "What time would you like to travel?"
    }
    conversation_state["asking_for"] = field
    return prompts.get(field, "Could you clarify?")


def plan_journey(user_input):
    ents = conversation_state["entities"]

    #Prevent Same origin and destination 
    if ents.get("origin") and ents.get("destination"):
        if ents["origin"] == ents["destination"]:
            del ents["destination"]
            conversation_state["asking_for"] = "destination"
            return "Your origin and destination can't be the same. Where would you like to travel to instead?"

    new_ents = extract_entities(user_input)
    asking_for = conversation_state.get("asking_for")

    print("DEBUG new_ents:", new_ents)
    print("DEBUG ents:", ents)
    print("DEBUG asking_for:", conversation_state.get("asking_for"))
    
    if asking_for:
        if "station_candidates" in new_ents:
            new_ents[f"{asking_for}_candidates"] = new_ents.pop("station_candidates")

        if "origin" in new_ents and asking_for == "destination":
            new_ents["destination"] = new_ents.pop("origin")

        if "destination" in new_ents and asking_for == "origin":
            new_ents["origin"] = new_ents.pop("destination")
            
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
                return clarify_station(slot, ents[candidate_key])

    for key, value in new_ents.items():
        if asking_for == key:
            ents[key] = value
        elif key not in ents:
            ents[key] = value

    for slot in ("origin", "destination"):
        candidate_key = f"{slot}_candidates"
        if candidate_key in ents and slot not in ents:
            return clarify_station(slot, ents[candidate_key])

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

    # Check if time is missing or invalid
    if not time:
        conversation_state["asking_for"] = "time"
        return reask_for_field("time")
    
    # Validate time format
    depart_time = get_timestamp(date, time)
    if not depart_time:
        conversation_state["asking_for"] = "time"
        return reask_for_field("time")

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

    # Fetch API Data
    journey_data = print_journey_details(origin_code, destination_code, depart_time)

    if not journey_data:
        return confirmation + "\n\nNo journeys found. Please try a different time,route or origin/destination."

    ticket_state["last_journey_options"] = journey_data

    flat_options = []

    for j in journey_data:
        try:
            service = j["services"][0]
            flat_options.append({
                "origin": j["origin"],
                "destination": j["destination"],
                "departure": service.get("departure") or service.get("realtime_departure"),
                "arrival": service.get("arrival") or service.get("realtime_arrival"),
                "operator": service.get("operator")
            })
        except:
            continue

    ticket_state["last_ticket_options"] = flat_options

    msg = "\n\nHere are some live times found:\n"

    for i, opt in enumerate(flat_options[:5], 1):
        msg += f"{i}. {opt['operator']}, {opt['departure']} → {opt['arrival']}\n"

    ticket_state["pending_ticket_offer"] = True
    ticket_state["ticket_step"] = "confirm"

    return msg + "\n\nWould you like to book a ticket for one of these times? (yes/no)"

def build_national_rail_link(origin_code, destination_code, date, time):
    """Build National Rail Enquiries journey planner link with journey details"""
    try:
        date_obj = datetime.strptime(date, "%d/%m/%Y")
        time_obj = datetime.strptime(time, "%H:%M")
        date_str = date_obj.strftime("%d%m%y")
        hour = time_obj.strftime("%H")
        minute = time_obj.strftime("%M")
        link = (
            f"https://www.nationalrail.co.uk/journey-planner/"
            f"?type=single&origin={origin_code}&destination={destination_code}"
            f"&leavingType=departing&leavingDate={date_str}"
            f"&leavingHour={hour}&leavingMin={minute}&adults=1&extraTime=0#O"
        )
        return link
    except:
        return None

def ticket_pricing():
    """Get ticket prices using expert system and filter by user preferences"""
    selected_journey = ticket_state.get("selected_journey")
    if not selected_journey:
        return "Error: No journey selected.", "error"
    
    origin = selected_journey["origin"]
    destination = selected_journey["destination"]
    
    # Get ticket details from ticket state
    num_adults = ticket_state.get("num_adults", 1)
    num_children = ticket_state.get("num_children", 0)
    fare_class_choice = ticket_state.get("fare_class", "standard")
    ticket_category_choice = ticket_state.get("ticket_category")
    railcard = ticket_state.get("railcard")
    ticket_preference = ticket_state.get("ticket_preference")  # cheapest, quickest, or None
    
    # Get date and time from selected journey departure
    departure_str = selected_journey.get("departure", "")
    if not departure_str:
        return "Error: No departure time in selected journey.", "error"
    
    try:
        parts = departure_str.split(" ")
        date_parts = parts[0].split("-")
        date = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
        time = parts[1][:5] if len(parts) > 1 else "09:00"
    except:
        return "Error: Could not parse departure time.", "error"
    
    # Format datetime for API
    depart_datetime = get_timestamp(date, time)
    if not depart_datetime:
        return "Error: Invalid date/time format.", "error"
    
    # Map fare_class to API format
    fare_class_api = "FIRST" if "first" in str(fare_class_choice).lower() else "STANDARD"
    
    # Map ticket_category to API format
    fare_category_map = {
        "advance": "ADVANCE",
        "off-peak": "OFF_PEAK",
        "anytime": "ANYTIME"
    }
    fare_category_api = fare_category_map.get(ticket_category_choice, None) if ticket_category_choice else None
    
    # Call API to get prices
    try:
        prices = get_ticket_prices(origin, destination, depart_datetime, 
                                   num_adults, num_children, fare_class_api)
    except Exception as e:
        print(f"Error fetching prices: {e}")
        prices = []
    
    # Filter tickets by fare class and category
    filtered_tickets = []
    for ticket in prices:
        ticket_class = ticket.get("fareClass", "").upper()
        ticket_category = ticket.get("fareCategory", "").upper()
        
        class_match = ticket_class == fare_class_api
        category_match = (fare_category_api is None) or (ticket_category == fare_category_api)
        
        if class_match and category_match:
            filtered_tickets.append(ticket)
    
    # Fallback if no exact matches
    if not filtered_tickets and fare_category_api:
        for ticket in prices:
            if ticket.get("fareClass", "").upper() == fare_class_api:
                filtered_tickets.append(ticket)
    
    if not filtered_tickets:
        filtered_tickets = prices
    
    # Generate booking link
    origin_code = origin
    destination_code = destination
    link = build_national_rail_link(origin_code, destination_code, date, time)
    
    if not filtered_tickets:
        ticket_desc = f"{fare_class_choice.lower()} class"
        if ticket_category_choice:
            ticket_desc = f"{ticket_category_choice} ({fare_class_choice.lower()} class)"
        msg = (f"I couldn't find any available {ticket_desc} tickets for "
               f"{origin.title()} to {destination.title()} on {date}.\n\n"
               f"Please search on National Rail Enquiries:\n{link}")
        return msg, "ticket_complete"
    
    # Store filtered tickets
    ticket_state["last_filtered_tickets"] = filtered_tickets
    
    # Select best ticket based on preference
    if ticket_preference == "cheapest" and filtered_tickets:
        selected_ticket = min(filtered_tickets, key=lambda t: int(t.get("totalPrice", 0)))
    elif ticket_preference == "quickest" and filtered_tickets:
        # For quickest, we'd need journey data; use first available as default
        selected_ticket = filtered_tickets[0]
    else:
        selected_ticket = filtered_tickets[0] if filtered_tickets else None
    
    if not selected_ticket:
        return "Error: Could not select a ticket.", "error"
    
    # Extract ticket price
    try:
        price_pence = int(selected_ticket.get("totalPrice", 0))
        price_pounds = price_pence / 100
    except:
        price_pounds = 0.0
    
    # Apply railcard discount if applicable
    final_price = price_pounds
    if railcard:
        discount_mult = RAILCARD_DISCOUNTS.get(railcard, {}).get("adult", 1.0)
        final_price = price_pounds * discount_mult
    
    # Display selected ticket
    output = f"\nSelected ticket (Expert System Recommendation):\n\n"
    output += f"  {origin.upper()} → {destination.upper()}\n"
    output += f"  Date: {date} | Time: {time}\n"
    output += f"  Passengers: {num_adults} adult{'s' if num_adults > 1 else ''}"
    if num_children:
        output += f", {num_children} child{'ren' if num_children > 1 else ''}"
    
    ticket_type_display = f"{ticket_category_choice} {fare_class_choice}" if ticket_category_choice else fare_class_choice
    output += f" ({ticket_type_display})\n\n"
    
    # Display the selected ticket details
    try:
        desc = selected_ticket.get("description", "Fare")
        output += f"  Selected: {desc}\n"
        output += f"  Base Price: £{price_pounds:.2f}\n"
        
        if railcard:
            output += f"  Railcard ({railcard}): £{final_price:.2f}\n"
        else:
            output += f"  Final Price: £{final_price:.2f}\n"
    except:
        output += f"  Selected: {selected_ticket.get('description', 'Fare')}\n"
    
    output += f"\n  Preference: {ticket_preference if ticket_preference else 'Best available'}\n"
    
    output += f"\n📍 Book on National Rail Enquiries:\n{link}\n"
    output += "You can complete your booking through the link above."
    
    return output, "ticket_complete"


def handle_ticket_flow(user_input):
    step = ticket_state.get("ticket_step")
    text = user_input.lower().strip()

    # Confirm for ticket
    if step == "confirm":
        if text in ["yes", "y", "yeah", "yep", "ok", "sure"] or "yes" in text:
            # Detect ticket preference from user input
            cheapest_keywords = ["cheapest", "cheap", "lowest price", "lowest", "minimum"]
            quickest_keywords = ["quickest", "quick", "fastest", "fast", "shortest"]
            
            if any(keyword in text for keyword in cheapest_keywords):
                ticket_state["ticket_preference"] = "cheapest"
            elif any(keyword in text for keyword in quickest_keywords):
                ticket_state["ticket_preference"] = "quickest"
            else:
                ticket_state["ticket_preference"] = None
            
            ticket_state["ticket_step"] = "select"
            options = ticket_state.get("last_journey_options", [])

            if not options:
                reset_ticket_state()
                reset_state()
                return "No journeys available to book.", "ticket_select"

            msg = f"Choose an available journey option from 1 to {len(options)}:\n"
            for i, j in enumerate(options, 1):
                try:
                    dep = j["services"][0]["departure"]
                    arr = j["services"][0]["arrival"]
                    op = j["services"][0]["operator"]
                    msg += f"{i}. {op}, {dep} → {arr}\n"
                except:
                    msg += f"{i}. Invalid journey format\n"

            return msg, "ticket_select"

        if text in ["no", "nope", "nah"]:
            reset_ticket_state()
            reset_state()
            return "Okay, let me know if you need anything else.", "end"

        return "Please answer yes or no.", "ticket_confirm"


    # Seelct journey 
    if step == "select":
        if not text.isdigit():
            return "Please choose a number.", "ticket_select"

        idx = int(text) - 1
        options = ticket_state.get("last_journey_options", [])

        if not (0 <= idx < len(options)):
            return f"Choose a number between 1 and {len(options)}.", "ticket_select"

        selected = options[idx]

        ticket_state["selected_journey"] = {
            "origin": selected["origin"],
            "destination": selected["destination"],
            "departure": selected["services"][0]["departure"],
            "arrival": selected["services"][0]["arrival"]
        }

        ticket_state["ticket_step"] = "traveller_info"

        return (
            "Great — who’s travelling?\n"
            "For example: '1 adult', '2 adults + 1 child', "
            "'1 adult with a 16–25 Railcard'.",
            "ticket_travellers"
        )


    # Info for ticket
    if step == "traveller_info":
        parsed = parse_traveller_info(text)

        # store parsed values in ticket_state
        ticket_state["num_adults"] = parsed["num_adults"]
        ticket_state["num_children"] = parsed["num_children"]
        ticket_state["ticket_category"] = parsed["ticket_category"]
        ticket_state["fare_class"] = parsed["fare_class"]
        ticket_state["railcard"] = parsed["railcard"]

        if not ticket_state["ticket_category"]:
            ticket_state["ticket_step"] = "ticket_category"
            return "You Can Choose A Ticket Type Of : [Advance]  [Off-Peak], or [Anytime]", "ticket_category"

        if not ticket_state["fare_class"]:
            ticket_state["ticket_step"] = "fare_class"
            return "Would you like a [Standard] or [First Class] seat?", "ticket_fare_class"

        if not ticket_state["railcard"]:
            ticket_state["ticket_step"] = "railcard"
            return "Would you also like to apply a Railcard option, we accept: [16-17], [16-25], [26-30], [Disabled] and [Senior] railcards", "ticket_railcard"

        return ticket_pricing()

    # Ticket type selection step
    if step == "ticket_category":
        valid_types = ["advance", "off-peak", "anytime"]
        user_type = text.lower().replace(" ", "")
        # Accept with or without dash
        if user_type in [t.replace("-", "") for t in valid_types]:
            ticket_state["ticket_category"] = [t for t in valid_types if user_type == t.replace("-", "")][0]
            # Move to next step
            if not ticket_state["fare_class"]:
                ticket_state["ticket_step"] = "fare_class"
                return "Would you like a [Standard] or [First Class] seat?", "ticket_fare_class"
            if not ticket_state["railcard"]:
                ticket_state["ticket_step"] = "railcard"
                return "Would you also like to apply a Railcard option, we accept: [16-17], [16-25], [26-30], [Disabled] and [Senior] railcards", "ticket_railcard"
            return ticket_pricing()
        else:
            ticket_state["ticket_step"] = "ticket_category"
            return "Please choose a valid ticket type: [Advance], [Off-Peak], or [Anytime]", "ticket_category"

    # Fare class selection step
    if step == "fare_class":
        valid_classes = ["standard", "first class", "first"]
        user_class = text.lower().replace(" ", "")
        if user_class in [c.replace(" ", "") for c in valid_classes]:
            ticket_state["fare_class"] = "standard" if user_class in ["standard"] else "first class"
            # Move to next step
            if not ticket_state["railcard"]:
                ticket_state["ticket_step"] = "railcard"
                return "Would you like to apply a Railcard option, we accept: [16-17], [16-25], [26-30], [Disabled] and [Senior] railcards", "ticket_railcard"
            return ticket_pricing()
        else:
            ticket_state["ticket_step"] = "fare_class"
            return "Please choose a valid seat class: [Standard] or [First Class]", "ticket_fare_class"

    # Railcard apply
    if step == "railcard":

        if text in ["no", "none", "nope", "nah", "no railcard", "don't have", "don't have one"]:
            ticket_state["railcard"] = None
            ticket_state["pending_ticket_offer"] = False
            return ticket_pricing()
        
        for rc in RAILCARD_DISCOUNTS.keys():
            if rc.lower() in text:
                ticket_state["railcard"] = rc
                ticket_state["pending_ticket_offer"] = False
                return ticket_pricing()

        return "I didn’t recognise that Railcard. Try again or say no to skip.", "ticket_railcard"
    # Cheapest choice
    if step == "cheapest_choice":
        if text in ["yes", "y", "yeah", "yep", "ok", "sure"]:
            # Get cheapest ticket and show booking link
            filtered_tickets = ticket_state.get("last_filtered_tickets", [])
            
            if not filtered_tickets:
                return "Error: No tickets available.", "error"
            
            # Sort by price and get the cheapest
            cheapest_ticket = min(filtered_tickets, key=lambda t: int(t.get("totalPrice", 0)))
            
            selected_journey = ticket_state.get("selected_journey")
            departure_str = selected_journey.get("departure", "")
            try:
                parts = departure_str.split(" ")
                date_parts = parts[0].split("-")
                date = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
                time = parts[1][:5] if len(parts) > 1 else "09:00"
            except:
                date = conversation_state["entities"].get("date", "")
                time = conversation_state["entities"].get("time", "09:00")
            origin_code = selected_journey["origin"]
            destination_code = selected_journey["destination"]
            
            # Generate booking link
            link = build_national_rail_link(origin_code, destination_code, date, time)
            
            # Format cheapest ticket info
            try:
                price_pence = int(cheapest_ticket.get("totalPrice", 0))
                price_pounds = price_pence / 100
                desc = cheapest_ticket.get("description", "Fare")
                
                output = f"\nCheapest option selected:\n\n"
                output += f"  {desc}: £{price_pounds:.2f}\n\n"
                
                # Apply railcard discount if applicable
                railcard = ticket_state.get("railcard")
                if railcard:
                    discount_mult = RAILCARD_DISCOUNTS.get(railcard, {}).get("adult", 1.0)
                    discounted_price = price_pounds * discount_mult
                    output += f"  With {railcard} railcard: £{discounted_price:.2f}\n\n"
            except:
                output = f"\nCheapest option selected: {cheapest_ticket.get('description', 'Fare')}\n\n"
            
            output += f"📍 Book on National Rail Enquiries:\n{link}\n"
            output += "You can complete your booking through the link above."
            
            ticket_state["ticket_step"] = None
            reset_ticket_state()
            return output, "ticket_complete"
        
        if text in ["no", "nope", "nah"]:
            # Show all tickets with booking link
            filtered_tickets = ticket_state.get("last_filtered_tickets", [])
            
            if not filtered_tickets:
                return "Error: No tickets available.", "error"
            
            selected_journey = ticket_state.get("selected_journey")
            date = conversation_state["entities"].get("date")
            time = conversation_state["entities"].get("time", "09:00")
            origin_code = selected_journey["origin"]
            destination_code = selected_journey["destination"]
            
            # Generate booking link
            link = build_national_rail_link(origin_code, destination_code, date, time)
            
            output = f"\nAll available tickets:\n\n"
            
            # Show all filtered tickets
            for i, ticket in enumerate(filtered_tickets[:5], 1):
                try:
                    price_pence = int(ticket.get("totalPrice", 0))
                    price_pounds = price_pence / 100
                    desc = ticket.get("description", "Fare")
                    
                    railcard = ticket_state.get("railcard")
                    if railcard:
                        discount_mult = RAILCARD_DISCOUNTS.get(railcard, {}).get("adult", 1.0)
                        discounted_price = price_pounds * discount_mult
                        output += f"  {i}. {desc}: £{price_pounds:.2f} → £{discounted_price:.2f} (with {railcard} railcard)\n"
                    else:
                        output += f"  {i}. {desc}: £{price_pounds:.2f}\n"
                except:
                    output += f"  {i}. {ticket.get('description', 'Fare')}: Price unavailable\n"
            
            output += f"\n📍 Book on National Rail Enquiries:\n{link}\n"
            output += "You can complete your booking through the link above."
            
            ticket_state["ticket_step"] = None
            reset_ticket_state()
            return output, "ticket_complete"
        
        return "Please answer yes or no.", "ticket_cheapest_choice"
    return None

#What happens after user is done with intent
def handle_post_completion(user_input):

    text = user_input.lower().strip()
    intent, _ = get_intent(user_input)

    if intent in ["plan_journey", "find_ticket", "refund_info", "delay_info"]:
        conversation_state["awaiting_next_action"] = False
        conversation_state["intent"] = intent
        return process_user_input_internal(user_input)

    if any(x in text for x in ["yes", "ok", "sure", "yeah", "yep"]):
        reset_state()
        return "What else can I help you with — journeys, tickets, delays, or refunds?", None

    reset_state()
    return "Anything else I can help with?", None

#Getting intent
def process_user_input_internal(user_input: str):

    # Handle post-completion
    if conversation_state["awaiting_next_action"]:
        return handle_post_completion(user_input)


    # Ticket Flow
    if ticket_state.get("pending_ticket_offer"):
        result = handle_ticket_flow(user_input)
        if result:
            return result
    
    if any(delay_state[k] is not None for k in ["current_station", "current_delay", "destination", "asking_for"]):
        conversation_state["intent"] = "delay_prediction"
        return handle_delay_prediction(user_input), "delay_prediction"

    if is_delay_prediction_request(user_input):
        conversation_state["intent"] = "delay_prediction"
        return handle_delay_prediction(user_input), "delay_prediction"


    kb_answer = get_kb_answer(user_input)
    if kb_answer:
        reset_state()
        return phrase_kb_answer(kb_answer, user_input), "knowledge_query"

    intent, confidence = get_intent(user_input)

    stations = find_stations(user_input)

    if stations and intent in ["unknown", "plan_journey"]:
        conversation_state["intent"] = "plan_journey"
    elif confidence > 0.6:
        conversation_state["intent"] = intent

    intent = conversation_state["intent"]


    if intent == "greeting":
        reset_state()
        return "Hi. How can I help?", "greeting"


    if intent in ["plan_journey", "find_ticket"]:
        return plan_journey(user_input), intent

    if intent in ["refund_info", "delay_info", "seat_info", "platform_info", "live_status"]:
        return handle_knowledge_query(user_input, intent), intent

    return "Sorry I can only help with: journey planning, tickets, disruptions, refunds.", intent

def process_user_input(user_input: str):
    response, intent = process_user_input_internal(user_input) or "Sorry, something went wrong."
    save_message(session_id, user_input, response, intent)
    return response

def main():
    init_db()
    print("Assistant: Hi! I can help with train journeys, tickets, disruptions, or refunds.")

    while True:
        user_input = input("User: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        response = process_user_input(user_input)
        print("Assistant:", response)


#Main Chatbot Start
if __name__ == "__main__":
    main()