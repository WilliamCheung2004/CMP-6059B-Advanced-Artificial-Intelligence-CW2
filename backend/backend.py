from intent import detect_intent, detect_primary_intent, extract_entities
from intentClassifier import classify_intent
from expertSystem import TrainChatbot, Journey, TicketPreference
from database import init_db, save_message, save_journey
from knowledge_base import get_faq, get_rule

#global session state
SESSION_ID = "session1"

conversation_state = {
    "awaiting": None,
    "entities": {},
    "awaiting_preference": False   # True once all slots filled, waiting for ticket choice
}

INTENT_TO_FAQ_KEY = {
    "refund_info": "refund",
    "seat_info": "luggage",
    "journey_time": "peak",
    "delay_info": "refund",  # placeholder until you add delay_repay to KB
}

#save journey (only when all 3 fields present)
def safe_save_journey(entities):
    if entities.get("origin") and entities.get("destination") and entities.get("date"):
        save_journey(
            SESSION_ID,
            entities["origin"],
            entities["destination"],
            entities["date"]
        )
        
# reset state for a new journey
def reset_state():
    conversation_state["awaiting"] = None
    conversation_state["entities"] = {}
    conversation_state["awaiting_preference"] = False

#run expert system, capture printed output as a string
import io
import sys

def run_expert_system(entities, preference=None):
    engine = TrainChatbot()
    engine.reset()

    journey_facts = dict(
        origin=entities["origin"],
        destination=entities["destination"],
        date=entities["date"]
    )
    if preference:
        journey_facts["preference"] = "pending"

    engine.declare(Journey(**journey_facts))
    
    if preference:
        engine.declare(TicketPreference(type=preference))

    #capture any print() output from the expert system
    captured = io.StringIO()
    sys.stdout = captured
    engine.run()
    sys.stdout = sys.__stdout__

    return captured.getvalue().strip()


#ask for next missing slot (origin/destination/date) if any
def ask_for_missing(entities):
    if not entities.get("origin"):
        conversation_state["awaiting"] = "origin"
        return "Where are you travelling from?"

    if not entities.get("destination"):
        conversation_state["awaiting"] = "destination"
        return "Where are you travelling to?"

    if not entities.get("date"):
        conversation_state["awaiting"] = "date"
        return "What date are you travelling?"

    conversation_state["awaiting"] = None
    return None

#detect ticket preference keyword in input
def extract_preference(user_input):
    msg = user_input.lower()
    if "cheapest" in msg or "cheap" in msg:
        return "cheapest"
    if "quickest" in msg or "quick" in msg or "fastest" in msg or "fast" in msg:
        return "quickest"
    if "any" in msg:
        return "any"
    return None

def process_user_input(user_input):
    user_input = user_input.strip()
    entities = conversation_state["entities"]

    # =========================================================
    # STEP 1: All slots filled, waiting for ticket preference
    # =========================================================
    if conversation_state["awaiting_preference"]:
        preference = extract_preference(user_input)

        if not preference:
            return "Please say cheapest, quickest, or any."

        conversation_state["awaiting_preference"] = False
        response = run_expert_system(entities, preference=preference)
        save_message(SESSION_ID, user_input, response, "ticket_selected")
        reset_state()
        return response + "\n\nIf you want to plan another journey, just let me know!"

    # =========================================================
    # STEP 2: Filling journey slots (origin / destination / date)
    # =========================================================
    if conversation_state["awaiting"]:
        missing = conversation_state["awaiting"]

        extracted = extract_entities(user_input)
        value = extracted.get(missing) or user_input.strip() or None

        if not value:
            return f"I still need your {missing}. Please try again."

        entities[missing] = value
        conversation_state["awaiting"] = None

        next_question = ask_for_missing(entities)
        if next_question:
            save_message(SESSION_ID, user_input, next_question, "slot_filling")
            return next_question

        # All slots now filled — ask for preference via expert system
        safe_save_journey(entities)
        conversation_state["awaiting_preference"] = True
        response = run_expert_system(entities, preference=None)
        save_message(SESSION_ID, user_input, response, "ask_preference")
        return response

    # =========================================================
    # STEP 3: Normal flow — extract entities from opening message
    # =========================================================
    rule_intent = detect_primary_intent(user_input)

    ml_intent, ml_conf = classify_intent(user_input)

    if rule_intent != "unknown":
        intent = rule_intent
    elif ml_conf >= 0.55:
        intent = ml_intent
    else:
        intent = "unknown"
    
    kb_key = INTENT_TO_FAQ_KEY.get(intent, intent)
    kb_response = get_faq(user_input) or get_faq(kb_key) or get_rule(kb_key)
    if kb_response and intent not in ("find_ticket", "plan_journey"):
        save_message(SESSION_ID, user_input, kb_response, intent)
        return kb_response
    elif intent == "unknown":
        fallback = "Sorry, I didn't quite understand that. You can ask me about railcards, refunds, luggage, peak times, or say 'get a ticket' to start booking."
        save_message(SESSION_ID, user_input, fallback, intent)
        return fallback

    new_entities = extract_entities(user_input)
    for key in ("origin", "destination", "date"):
        if new_entities.get(key):
            entities[key] = new_entities[key]

    next_question = ask_for_missing(entities)
    if next_question:
        save_message(SESSION_ID, user_input, next_question, intent)
        return next_question

    #all slots filled from the opening message
    safe_save_journey(entities)
    conversation_state["awaiting_preference"] = True
    response = run_expert_system(entities, preference=None)
    save_message(SESSION_ID, user_input, response, intent)
    return response

def main():
    init_db()
    print("\nTrain Assistant: Hello! How can I help you?\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            print("\nAssistant: Goodbye!\n")
            break

        response = process_user_input(user_input)
        print("\nAssistant:", response, "\n")


if __name__ == "__main__":
    main()