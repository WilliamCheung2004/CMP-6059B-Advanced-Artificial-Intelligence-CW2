import requests
import time
from intentClassifier import classify_intent 
from intent import detect_primary_intent, extract_entities, find_stations, extract_time_semantic, detect_intent, get_station_code, get_intents_by_priority, validate_date_time
from APIData import print_journey_details,get_timestamp, get_ticket_prices
from knowledge_base import get_faq, KB
from delayPrediction import predict_arrival_delay
import re
from database import save_message, save_journey, init_db
from expertSystem import parse_traveller_info, RAILCARD_DISCOUNTS, TicketBot, Journey, TicketPreference, Railcard
import uuid
import json
from datetime import date, datetime, timedelta

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
    "awaiting_help_response": False,  # Flag for post-task help requests
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
        response = phrase_kb_answer(answer, user_input)
        response += "\n\nWould you like help with anything else?"
        conversation_state["awaiting_help_response"] = True
        reset_state()  
        return response
    
    #fallback to intent-mapped FAQ answer if no direct match in KB
    faq_key = intent_to_faq.get(intent)
    if faq_key:
        answer = get_faq(faq_key)
        if answer:
            response = answer
            response += "\n\nWould you like help with anything else?"
            conversation_state["awaiting_help_response"] = True
            reset_state()
            return response 

    #fall back to LLM if KB has nothing
    response = chatbot([{"role": "user", "content": user_input}]) or "Sorry, I don't have an answer for that right now."
    response += "\n\nWould you like help with anything else?"
    conversation_state["awaiting_help_response"] = True
    reset_state()
    return response

def ask_continue():
    ticket_state["ticket_step"] = "post_booking"
    ticket_state["pending_ticket_offer"] = True   
    return "Would you like me to help you with anything else?", "post_booking"

def reset_delay_state():
    delay_state["current_station"] = None
    delay_state["current_delay"] = None
    delay_state["destination"] = None
    delay_state["asking_for"] = None
    
def is_delay_prediction_request(user_input: str) -> bool:
    triggers = [
        "train is delayed",
        "train is running late",
        "delayed by",
        "minutes late",
        "minutes delayed"
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
        delay_state["current_station"] = None
        delay_state["asking_for"] = "current_station"
        return result["message"]  
    
    # Prediction complete 
    reset_delay_state()
    message = result["message"]
    message += "\n\nWould you like help with anything else?"
    conversation_state["awaiting_help_response"] = True
    reset_state() 
    
    return message

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
    conversation_state["awaiting_help_response"] = False


def resolve_intent_by_priority(message: str) -> tuple[str, float]:

    intents = get_intents_by_priority(message)
    if not intents:
        return "unknown", 0
    
    primary_intent = intents[0]
    ml_intent, ml_conf = classify_intent(message)
    
    if ml_conf >= confidence_threshold:
        return ml_intent, ml_conf
    
    return primary_intent, 0.5

def reset_ticket_state():
    ticket_state["last_journey_options"] = None
    ticket_state["last_ticket_options"] = None
    ticket_state["last_filtered_tickets"] = None
    ticket_state["ticket_step"] = None
    ticket_state["ticket_state"] = False
    ticket_state["pending_ticket_offer"] = False
    ticket_state["fare_class"] = None
    ticket_state["railcard"] = None
    ticket_state["ticket_preference"] = None

def reset_all_states():
    reset_state()
    reset_ticket_state()
    reset_delay_state()

def ask_continue_help():

    prompt = """You are a train assistant.

The user has completed their current task.

Ask if they would like help with anything else, and list the available options:
- Journey planning (routes, times, connections)
- Ticket booking (prices, types, railcards)
- Delay information and predictions
- Refunds and compensation

Rules:
- 2-3 sentences maximum
- Formal tone
- Natural and conversational
- Do not invent anything
- Ask yes or no response

Format: Start with asking if they need more help, then list: 'I can help with:'"""
    
    llm_response = chatbot([{"role": "user", "content": prompt}])
    
    if llm_response:
        # Set flag to await response
        conversation_state["awaiting_help_response"] = True
        reset_state() 
        reset_ticket_state()
        return llm_response, "help_options"
    else:
        # Fallback response
        conversation_state["awaiting_help_response"] = True
        reset_state()
        reset_ticket_state()
        return "Would you like help with anything else? I can help with: journey planning, tickets, delays, or refunds.", "help_options"

#Ollama Chatbot
def chatbot(messages):
    url = "http://localhost:11434/api/chat"

    payload = {
        "model": "mistral:7b",
        "messages": [{"role": "system", "content": BASE_SYSTEM_PROMPT}] + messages,
        "stream": False
    }

    try:
        start_time = time.time()
        r = requests.post(url, json=payload)
        elapsed_time = time.time() - start_time
        
        if not r.ok:
            print(f"[DEBUG] Chatbot request failed after {elapsed_time:.2f}s")
            return None
        
        response_text = r.json()["message"]["content"]
        print(f"[DEBUG] Chatbot responded in {elapsed_time:.2f} seconds")
        return response_text
    except Exception as e:
        print(f"[DEBUG] Chatbot error: {str(e)}")
        return None    
    
#Using intent keyword or classifier
def get_intent(message: str):
    return resolve_intent_by_priority(message)


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


def plan_journey(user_input, skip_ticket_ask=False):
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

    # Validate date and time if they exist
    if ents.get("date"):
        is_valid, error_msg = validate_date_time(ents["date"], ents.get("time"))
        if not is_valid:
            del ents["date"]
            if "time" in ents:
                del ents["time"]
            conversation_state["asking_for"] = "date"
            return error_msg + "\n" + reask_for_field("date")

    missing = get_missing_fields(ents)
    if missing:
        return reask_for_field(missing[0])

    return generate_journey_response(ents, skip_ticket_ask=skip_ticket_ask)

#User given that they gave all information 
def generate_journey_response(ents, skip_ticket_ask=False):
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

    confirm_prompt = f"""
You are a train assistant.

Confirm and summarise the journey.

Rules:
- 1–2 sentences
- no schedules
- no greeting
- formal
- do NOT invent times or prices, link or recommend anything
- The journey details are: from {origin} to {destination} on {date} at {time}.
"""

    confirmation = chatbot([{"role": "user", "content": confirm_prompt}]) 
    
    # Fallback if chatbot is unavailable
    if not confirmation:
        confirmation = f"Journey from {origin.title()} to {destination.title()} on {date} at {time}."

    # Getting station code for API
    origin_code = get_station_code(origin)
    destination_code = get_station_code(destination)

    if not origin_code or not destination_code:
        return confirmation + "\n\nError: could not find valid station codes."

    # Fetch API Data
    journey_data = print_journey_details(origin_code, destination_code, depart_time)

    if not journey_data:
        reset_state()
        reset_ticket_state()
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

    journey_tickets = []
    for opt in flat_options[:5]:
        journey_tickets.append({
            "origin": origin, 
            "destination": destination, 
            "departureTime": opt["departure"].split(" ")[1][:5] if " " in opt["departure"] else opt["departure"],
            "departureDate": date, 
            "changes": 0,
            "cheapest": False,
            "bookingUrl": "#"
        })

    # If skip_ticket_ask (find_ticket), go straight to asking traveller info (no journey times display)
    if skip_ticket_ask:
        options = ticket_state.get("last_journey_options", [])
        if options:
            selected = options[0]
            ticket_state["selected_journey"] = {
                "origin": selected["origin"],
                "destination": selected["destination"],
                "departure": selected["services"][0]["departure"],
                "arrival": selected["services"][0]["arrival"]
            }
        
        ticket_state["pending_ticket_offer"] = True
        ticket_state["ticket_step"] = "traveller_info"
        ticket_state["ticket_preference"] = None
        
        return confirmation + "\n\nWho's travelling?\nFor example: '1 adult', '2 adults + 1 child', '1 adult with a 16–25 Railcard', etc.", "traveller_info"
    
    msg = "\n\nHere are some live times found:\n"
    # for i, opt in enumerate(flat_options[:5], 1):
    #     msg += f"{i}. {opt['operator']}, {opt['departure']} → {opt['arrival']}\n"
    
    ticket_state["pending_ticket_offer"] = True
    ticket_state["ticket_step"] = "confirm"

    return confirmation + msg + "\n\nWould you like to book a ticket? (yes/no)", "journey_options", journey_tickets

RAILCARD_URL_CODES = {
    "16-17": "TSU",
    "16-25": "YNG",
    "26-30": "TST",
    "Disabled": "DIS",
    "Senior": "SRN",
}

def build_national_rail_link(origin_code, destination_code, date, time, ticket_state):
    try:
        date_obj = datetime.strptime(date, "%d/%m/%Y")
        time_obj = datetime.strptime(time, "%H:%M")

        dt = datetime.combine(date_obj.date(), time_obj.time())

        rounded_minute = (dt.minute // 15) * 15
        dt_rounded = dt.replace(minute=rounded_minute, second=0, microsecond=0)

        date_str = dt_rounded.strftime("%d%m%y")
        hour = dt_rounded.strftime("%H")
        minute = dt_rounded.strftime("%M")

        railcard_param = ""
        railcard_name = ticket_state.get("railcard")

        if railcard_name in RAILCARD_URL_CODES:
            code = RAILCARD_URL_CODES[railcard_name]
            railcard_param = f"&railcards={code}%7C1"

        link = (
            f"https://www.nationalrail.co.uk/journey-planner/"
            f"?type=single&origin={origin_code}&destination={destination_code}"
            f"&leavingType=departing&leavingDate={date_str}"
            f"&leavingHour={hour}&leavingMin={minute}&adults=1"
            f"{railcard_param}&extraTime=0#O"
        )

        return link

    except Exception as e:
        return None


def ticket_pricing():

    selected_journey = ticket_state.get("selected_journey")
    if not selected_journey:
        reset_state()
        reset_ticket_state()
        return "Error: No journey selected.", "error"
    
    origin = selected_journey["origin"]
    destination = selected_journey["destination"]
    
    # Get ticket details from ticket state
    num_adults = ticket_state.get("num_adults", 1)
    num_children = ticket_state.get("num_children", 0)
    fare_class_choice = ticket_state.get("fare_class")  
    ticket_category_choice = ticket_state.get("ticket_category") 
    railcard = ticket_state.get("railcard")  
    ticket_preference = ticket_state.get("ticket_preference")  
    
    # Get date and time from selected journey departure
    departure_str = selected_journey.get("departure", "")
    if not departure_str:
        reset_state()
        reset_ticket_state()
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
    
    # If fare_class not specified, fetch both Standard and First class
    all_prices = []
    if fare_class_choice is None:
        # Fetch Standard tickets
        try:
            standard_prices = get_ticket_prices(origin, destination, depart_datetime, 
                                               num_adults, num_children, "STANDARD")
            all_prices.extend(standard_prices)
        except Exception as e:
            print(f"Error fetching standard prices: {e}")
        
        # Fetch First class tickets
        try:
            first_prices = get_ticket_prices(origin, destination, depart_datetime, 
                                            num_adults, num_children, "FIRST")
            all_prices.extend(first_prices)
        except Exception as e:
            print(f"Error fetching first class prices: {e}")
        
        prices = all_prices if all_prices else []
    else:
        # Specific fare class requested
        fare_class_api = "FIRST" if "first" in str(fare_class_choice).lower() else "STANDARD"
        try:
            prices = get_ticket_prices(origin, destination, depart_datetime, 
                                       num_adults, num_children, fare_class_api)
        except Exception as e:
            print(f"Error fetching prices: {e}")
            prices = []
    
    # Map ticket_category to API format (for filtering)
    fare_category_map = {
        "advance": "ADVANCE",
        "off-peak": "OFF_PEAK",
        "anytime": "ANYTIME"
    }
    fare_category_api = fare_category_map.get(ticket_category_choice, None) if ticket_category_choice else None
    
    # Filter tickets by category if specified
    filtered_tickets = []
    for ticket in prices:
        ticket_category = ticket.get("fareCategory", "").upper()
        
        # If category filter specified, apply it; otherwise include all
        if fare_category_api is None or ticket_category == fare_category_api:
            filtered_tickets.append(ticket)
    
    # Fallback: if no matches after filtering, show all
    if not filtered_tickets:
        filtered_tickets = prices
    
    # Generate booking link
    origin_code = origin
    destination_code = destination
    link = build_national_rail_link(origin_code, destination_code, date, time, ticket_state)
    
    if not filtered_tickets:
        ticket_desc = f"{fare_class_choice.lower()} class" if fare_class_choice else "available"
        if ticket_category_choice:
            ticket_desc = f"{ticket_category_choice} ({ticket_desc})"
        msg = (f"I couldn't find any {ticket_desc} tickets for "
               f"{origin.title()} to {destination.title()} on {date}.\n\n"
               f"Please search on National Rail Enquiries:\n{link}")
        return msg, "ticket_complete"
    
    # Store filtered tickets
    ticket_state["last_filtered_tickets"] = filtered_tickets
    
    # Select best ticket based on preference
    if ticket_preference == "cheapest" and filtered_tickets:
        selected_ticket = min(filtered_tickets, key=lambda t: int(t.get("totalPrice", 0)))
    elif ticket_preference == "quickest" and filtered_tickets:
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
    
    # Apply railcard discount if explicitly mentioned by user
    final_price = price_pounds
    if railcard:
        discount_mult = RAILCARD_DISCOUNTS.get(railcard, {}).get("adult", 1.0)
        final_price = price_pounds * discount_mult
    
    # Display selected ticket
    output = f"\nSelected ticket:\n\n"
    output += f"  {origin.upper()} → {destination.upper()}\n"
    output += f"  Date: {date} | Time: {time}\n"
    output += f"  Passengers: {num_adults} adult{'s' if num_adults > 1 else ''}"
    if num_children:
        output += f", {num_children} child{'ren' if num_children > 1 else ''}"
    output += "\n"
    
    # Build ticket type display - handle None values gracefully
    ticket_type_parts = []
    if ticket_category_choice:
        ticket_type_parts.append(ticket_category_choice)
    if fare_class_choice:
        ticket_type_parts.append(fare_class_choice)
    ticket_type_display = " ".join(ticket_type_parts) if ticket_type_parts else "Standard"
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
    
    output += f"\n📍 You Can Book on The National Rail Link Below:\n"

    # Build the ticket object for frontend cards
    ticket = {
        "origin": origin, 
        "destination": destination, 
        "departureTime": time, 
        "departureDate": date, 
        "changes": 0, 
        "price": round(final_price, 2),
        "cheapest": ticket_preference == "cheapest",
        "bookingUrl": link
    }
    
    ticket_state["ticket_step"] = "post_booking"
    conversation_state["awaiting_help_response"] = True
    
    return output, "ticket_complete", ticket, "\n\nWould you like me to help with anything else?"  


def handle_ticket_flow(user_input):
    step = ticket_state.get("ticket_step")
    text = user_input.lower().strip()

    # Confirm for ticket 
    if step == "confirm":
        if text in ["yes", "y", "yeah", "yep", "ok", "sure"] or "yes" in text:
            # Detect ticket preference from user input in the confirmation
            cheapest_keywords = ["cheapest", "cheap", "lowest price", "lowest", "minimum"]
            quickest_keywords = ["quickest", "quick", "fastest", "fast", "shortest"]
            
            if any(keyword in text for keyword in cheapest_keywords):
                ticket_state["ticket_preference"] = "cheapest"
            elif any(keyword in text for keyword in quickest_keywords):
                ticket_state["ticket_preference"] = "quickest"
            else:
                ticket_state["ticket_preference"] = None
            
            # Select the first journey option
            options = ticket_state.get("last_journey_options", [])
            if not options:
                reset_ticket_state()
                reset_state()
                return "No journeys available to book.", "ticket_select"
            
            selected = options[0] 
            ticket_state["selected_journey"] = {
                "origin": selected["origin"],
                "destination": selected["destination"],
                "departure": selected["services"][0]["departure"],
                "arrival": selected["services"][0]["arrival"]
            }
            
            # Go directly to traveller info (skip the select step)
            ticket_state["ticket_step"] = "traveller_info"
            return (
                "Great — who's travelling?\n"
                "For example: '1 adult', '2 adults + 1 child', "
                "'1 adult with a 16–25 Railcard'.",
                "ticket_travellers"
            )

        if text in ["no", "nope", "nah"]:
            # Ask if user wants help with anything else
            ticket_state["ticket_step"] = "post_booking"
            reset_state()
            reset_ticket_state()
            return "Would you like me to help you with anything else?", "post_booking"

        return "Please answer yes or no.", "ticket_confirm"


    # Info for ticket - parse and infer from user input, then proceed to pricing
    if step == "traveller_info":
        parsed = parse_traveller_info(text)

        # Store parsed values in ticket_state
        ticket_state["num_adults"] = parsed["num_adults"]
        ticket_state["num_children"] = parsed["num_children"]
        ticket_state["ticket_category"] = parsed["ticket_category"]  # None if not specified
        ticket_state["fare_class"] = parsed["fare_class"]  # None if not specified
        ticket_state["railcard"] = parsed["railcard"]  # None if not mentioned (don't ask, just don't apply)
        
        # Detect preference keywords in traveller info (cheapest, quickest, etc.)
        cheapest_keywords = ["cheapest", "cheap", "lowest price", "lowest", "minimum"]
        quickest_keywords = ["quickest", "quick", "fastest", "fast", "shortest"]
        
        if any(keyword in text for keyword in cheapest_keywords):
            ticket_state["ticket_preference"] = "cheapest"
        elif any(keyword in text for keyword in quickest_keywords):
            ticket_state["ticket_preference"] = "quickest"
        else:
            # Use preference detected in confirm step, or default to None
            if not ticket_state.get("ticket_preference"):
                ticket_state["ticket_preference"] = None
        
        ticket_state["pending_ticket_offer"] = False
        return ticket_pricing()

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
            ticket_state["ticket_step"] = "post_booking"
            reset_state()
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
    
    # Post-booking state - ask if user wants help with anything else
    if step == "post_booking":
        text = user_input.lower().strip()
        
        # Check if this is the first time in post_booking (coming from ticket_pricing)
        # If so, ask if they want help
        if not conversation_state.get("post_booking_asked"):
            conversation_state["post_booking_asked"] = True
            return "Would you like me to help you with anything else?", "post_booking"
        
        # Handle response to the question
        if any(x in text for x in ["yes", "y", "yeah", "yep", "ok", "sure"]):
            # User wants more help
            conversation_state["post_booking_asked"] = False
            return ask_continue_help()
        
        if any(x in text for x in ["no", "nope", "nah"]):
            # User doesn't want more help - exit gracefully
            conversation_state["post_booking_asked"] = False
            reset_ticket_state()
            reset_state()
            return "Thank you for using the rail service. Goodbye!", "end"
        
        # Invalid response - ask again
        return "Please answer yes or no.", "post_booking"
    
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

def process_user_input_internal(user_input: str):

    if conversation_state["awaiting_next_action"]:
        return handle_post_completion(user_input)

    # Handle post-task help request responses
    if conversation_state.get("awaiting_help_response"):
        text = user_input.lower().strip()
        
        if any(x in text for x in ["yes", "y", "yeah", "yep", "ok", "sure"]):
            # User wants help - show options
            conversation_state["awaiting_help_response"] = False
            reset_state()
            options = ["Journey planning", "Ticket booking", "Delay information", "Refunds"]
            return "What would you like help with?\n- Journey planning\n- Ticket booking\n- Delay information\n- Refunds", "help_options"
        
        elif any(x in text for x in ["no", "nope", "nah"]):
            conversation_state["awaiting_help_response"] = False
            reset_state()
            reset_ticket_state()
            return "Thank you for using our service. Goodbye!", "end"
        
        else:
            # Invalid response
            return "Please answer yes or no - would you like more help?", "awaiting_help"

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

    intent, confidence = get_intent(user_input)
    stations = find_stations(user_input)

    # Resolve the current intent — update conversation_state FIRST
    if conversation_state.get("asking_for") in REQUIRED_FIELDS and conversation_state["entities"]:
        conversation_state["intent"] = "plan_journey"
    elif conversation_state["intent"] != "help":
        if stations and intent in ["unknown", "plan_journey"]:
            conversation_state["intent"] = "plan_journey"
        elif confidence > 0.6:
            conversation_state["intent"] = intent

    # Read the resolved intent once
    resolved_intent = conversation_state["intent"]

    if intent == "greeting":
        reset_state()
        return "Hi. How can I help?", "greeting"

    # KB mode: only if PREVIOUS turn set intent to "help" AND this turn isn't also "help"
    if resolved_intent == "help" and intent != "help":
        kb_answer = get_kb_answer(user_input)
        if kb_answer:
            reset_state()
            return phrase_kb_answer(kb_answer, user_input), "knowledge_query"
        faq_key = intent_to_faq.get(intent)
        if faq_key:
            answer = get_faq(faq_key)
            if answer:
                reset_state()
                return answer, "knowledge_query"
        reset_state()
        return chatbot([{"role": "user", "content": user_input}]) or "Sorry, I don't have details on that.", "knowledge_query"

    if intent == "help":
        conversation_state["intent"] = "help"
        return (
            "I can assist you with the following:\n"
            "- Journey planning (routes, times, connections)\n"
            "- Ticket booking (prices, types, railcards)\n"
            "- Delay information and predictions\n"
            "- Refunds and compensation\n\n"
            "What would you like to know more about?",
            "help"
        )

    if resolved_intent in ["plan_journey", "find_ticket"]:
        skip_ask = (resolved_intent == "find_ticket")
        return plan_journey(user_input, skip_ticket_ask=skip_ask), resolved_intent

    if resolved_intent in ["refund_info", "delay_info", "seat_info", "platform_info", "live_status"]:
        return handle_knowledge_query(user_input, resolved_intent), resolved_intent

    return "Sorry I can only help with: journey planning, tickets, disruptions, refunds.", resolved_intent

def process_user_input(user_input: str):
    result = process_user_input_internal(user_input)
    if result is None:
        response, intent = "Sorry, something went wrong.", "error"
        save_message(session_id, user_input, response, intent)
        return response
    elif len(result) == 4:
        response, intent, ticket, post_message = result
        save_message(session_id, user_input, str(response), intent)
        return response, intent, ticket, post_message
    elif len(result) == 3:
        response, intent, ticket = result
        save_message(session_id, user_input, str(response), intent)
        return response, intent, ticket
    else:
        response, intent = result
        save_message(session_id, user_input, str(response), intent)
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