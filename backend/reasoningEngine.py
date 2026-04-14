import spacy

from intent import detect_primary_intent, extract_entities
from expertSystem import *
from intentClassifier import classify_intent
from datetime import datetime
import sklearn

#python -m spacy download en_core_web_sm

if not spacy.util.is_package("en_core_web_sm"):
    spacy.cli.download("en_core_web_sm")

# -----------------------------
# CONVERSATION STATE
# -----------------------------
current_intent = None
pending_entities = {}

# -----------------------------
# GREETING
# -----------------------------
def determine_greeting():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "Good morning! "
    elif 12 <= hour < 18:
        return "Good afternoon! "
    else:
        return "Good evening! "

# -----------------------------
# EXPERT SYSTEM WRAPPER
# -----------------------------
def run_journey(origin, destination, date, preference):
    engine = TrainChatbot()
    engine.reset()
    engine.declare(Journey(origin=origin, destination=destination, date=date))
    engine.declare(TicketPreference(type=preference))
    engine.run()

# -----------------------------
# TICKET MANAGER (MISSING INFO)
# -----------------------------
def ticket_manager(entities):
    required = ["origin", "destination", "date"]
    missing = [e for e in required if e not in entities]

    if not missing:
        return None  # ready

    if len(missing) == 3:
        return "Where are you travelling from and to, and when?"
    if "origin" in missing and "destination" in missing:
        return "Where are you travelling from and to?"
    if "origin" in missing:
        return "Where are you travelling from?"
    if "destination" in missing:
        return "Where are you travelling to?"
    if "date" in missing:
        return "When do you want to travel?"

# -----------------------------
# INTENT HANDLERS
# -----------------------------
def handle_greeting(entities):
    print("Hi! I can help you find train tickets, check delays, or plan a journey.")

def handle_help(entities):
    print("You can ask me to find tickets, check delays, get platform info, or plan a journey.")

def handle_find_ticket(entities):
    global pending_entities, current_intent

    # Check if anything is missing
    missing_msg = ticket_manager(pending_entities)
    if missing_msg:
        print(missing_msg)
        return  # stay in this intent

    # All info collected → ask preference
    print("Do you want the cheapest, quickest, or any ticket?")
    pref = input("> ").strip().lower()

    run_journey(
        pending_entities["origin"],
        pending_entities["destination"],
        pending_entities["date"],
        pref
    )

    # Reset state after completion
    pending_entities = {}
    current_intent = None

def handle_plan_journey(entities):
    print("Tell me where you're travelling from and to.")

def handle_journey_time(entities):
    print("Which route do you want the journey time for?")

def handle_delay_info(entities):
    print("Delay prediction isn't fully implemented yet — coming soon.")

def handle_platform_info(entities):
    print("Tell me the station and destination, and I can check platform info soon.")

def handle_live_status(entities):
    print("Live status checking is coming soon.")

def handle_seat_info(entities):
    print("Seat information includes quiet coaches, first class, and accessibility. What do you need?")

def handle_refund_info(entities):
    print("Refunds depend on ticket type. Advance tickets are usually non-refundable.")

# -----------------------------
# INTENT → HANDLER MAP
# -----------------------------
INTENT_HANDLERS = {
    "greeting": handle_greeting,
    "help": handle_help,
    "find_ticket": handle_find_ticket,
    "plan_journey": handle_plan_journey,
    "journey_time": handle_journey_time,
    "delay_info": handle_delay_info,
    "platform_info": handle_platform_info,
    "live_status": handle_live_status,
    "seat_info": handle_seat_info,
    "refund_info": handle_refund_info,
}

# -----------------------------
# MAIN LOOP
# -----------------------------
if __name__ == "__main__":
    print(determine_greeting() + "What would you like to do?")

    while True:
        user = input("> ")

        # If we are already in a multi-turn intent, stay in it
        if current_intent == "find_ticket":
            intent = "find_ticket"
        else:
            # RULE-BASED INTENT
            rule_intent = detect_primary_intent(user)

            # ML INTENT
            ml_intent, ml_conf = classify_intent(user)

            # FINAL INTENT DECISION
            if rule_intent != "unknown":
                intent = rule_intent
            elif ml_conf >= 0.55:
                intent = ml_intent
            else:
                intent = "unknown"

            # Lock multi-turn intent
            if intent == "find_ticket":
                current_intent = "find_ticket"

        # Extract entities
        entities = extract_entities(user)

        # Merge entities into conversation state if in multi-turn intent
        if current_intent == "find_ticket":
            pending_entities.update(entities)

        # Exit
        if intent == "goodbye":
            print("Goodbye! Have a great journey.")
            break

        # Find handler
        handler = INTENT_HANDLERS.get(intent)

        if handler:
            handler(entities)
        else:
            print("I'm not sure I understood that. You can ask about tickets, delays, or journey planning.")
