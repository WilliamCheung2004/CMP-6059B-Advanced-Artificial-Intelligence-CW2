import requests
import json

from intentClassifier import classify_intent 
from intent import detect_primary_intent, extract_entities
from reasoningEngine import run_journey

confidence_threshold = 0.55

# ---------------------------------------------------------
# GLOBAL SYSTEM PROMPT (BOT IDENTITY)
BASE_SYSTEM_PROMPT = """
You are a train assistant.

Your behaviour rules:
- You can ONLY help with the train topics to do with: train journey planning, train tickets, train disruptions, ticket refunds
- Every reply must be extremely short (max 2 short sentence).
- Never invent train times, prices, or schedules.
- If the user asks about anything unrelated to the train topics, reply with only: "Sorry I can only help with the topics of: then mention the topics journey planning, tickets, disruptions, refunds."
"""

# Intent Detection
def get_intent(message: str):
    # Keyword match
    intent = detect_primary_intent(message)
    if intent != "unknown":
        return intent, 1.0

    # ML Classifier
    ml_intent, ml_conf = classify_intent(message)
    if ml_conf >= confidence_threshold:
        return ml_intent, ml_conf

    #Given none of those return 
    return "unknown", ml_conf


#LLM Ollama
def chatbot(messages):
    url = "http://localhost:11434/api/chat"

    full_messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT}
    ] + messages

    payload = {
        "model": "mistral:7b",
        "messages": full_messages,
        "stream": False
    }

    response = requests.post(url, json=payload)

    if not response.ok:
        return "Sorry, I'm having trouble on my end, please try again shortly."

    return response.json()["message"]["content"]


#Ask for missing details 
def ask_llm_for_missing(entity):
    messages = [
        {
            "role": "system",
            "content": f"Ask the user for their {entity}. Keep it short and natural."
        }
    ]
    return chatbot(messages)


def phrase_journey_result(api_result, entities):
    origin = entities["origin"]
    destination = entities["destination"]
    date = entities["date"]

    messages = [
        {
            "role": "system",
            "content": "Summarise the journey result without inventing train times."
        },
        {
            "role": "user",
            "content": f"Journey result: {api_result}. Entities: {entities}"
        }
    ]
    return chatbot(messages)


def handle_greeting(user_input):
    messages = [
        {
            "role": "system",
            "content": "Respond only to greetings. Keep it short."
        },
        {"role": "user", "content": user_input}
    ]
    return chatbot(messages)


def handle_general_chat(user_input):
    messages = [
        {
            "role": "system",
            "content": "Redirect outside of train topics - short response."
        },
        {"role": "user", "content": user_input}
    ]
    return chatbot(messages)


#State of conversation 
conversation_state = {
    "intent": None,
    "entities": {},
    "awaiting": None
}



def handle_plan_journey(user_input):
    ents = conversation_state["entities"]

    # Missing origin
    if "origin" not in ents:
        conversation_state["awaiting"] = "origin"
        return ask_llm_for_missing("origin")

    # Missing destination
    if "destination" not in ents:
        conversation_state["awaiting"] = "destination"
        return ask_llm_for_missing("destination")

    # Missing date
    if "date" not in ents:
        conversation_state["awaiting"] = "date"
        return ask_llm_for_missing("date")

    # Call api for journey 
    api_result = "journey from norwich -> colchester 11pm -> 12pm"

    # Phrase output using LLM
    final_message = phrase_journey_result(api_result, ents)

    # Reset since finished
    conversation_state["intent"] = None
    conversation_state["entities"] = {}
    conversation_state["awaiting"] = None

    return final_message


def process_user_input(user_input: str):

    if conversation_state["awaiting"]:
        missing = conversation_state["awaiting"]
        ents = extract_entities(user_input)

        if missing in ents:
            conversation_state["entities"][missing] = ents[missing]
            conversation_state["awaiting"] = None
            return "Got it!"
        else:
            return f"I still need your {missing}."

    if conversation_state["intent"] is None:
        intent, confidence = get_intent(user_input)
    else:
        intent = conversation_state["intent"]
        confidence = 1.0

    conversation_state["intent"] = intent

    ents = extract_entities(user_input)
    conversation_state["entities"].update(ents)

    print(f"Detected intent: {intent} (confidence: {confidence:.2f})")

    # Greeting
    if intent == "greeting":
        conversation_state["intent"] = None
        return handle_greeting(user_input)

    # Journey planning
    if intent in ["plan_journey", "find_ticket"]:
        return handle_plan_journey(user_input)

    # Fallback for no intent
    return handle_general_chat(user_input)


def main():
    print("Assistant: Hi! I can help with train journeys, tickets, disruptions, or refunds. What do you need?")
    while True:
        user_input = input("User: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        response = process_user_input(user_input)
        print("Assistant:", response)


if __name__ == "__main__":
    main()
