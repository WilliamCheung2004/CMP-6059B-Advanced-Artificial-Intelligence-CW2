import requests
from intentClassifier import classify_intent 
from intent import detect_primary_intent, extract_entities
from reasoningEngine import determine_greeting, ticket_manager, run_journey

confidence_threshold = 0.55

# LLM
def chatbot(messages):
    url = "http://localhost:11434/api/chat"

    payload = {
        "model": "llama3.1",
        "messages": messages,
        "stream": False
    }

    response = requests.post(url, json=payload)
    return response.json()["message"]["content"]

# -----------------------------
# GREETING HANDLER (LLM ONLY)
# -----------------------------
def handle_greeting(user_input):
    messages = [
        {
            "role": "system",
            "content": """
            You are a friendly UK train assistant.
            Respond politely to greetings.
            Do NOT offer bookings unless the user asks.
            Keep replies short and warm.
            """
        },
        {
            "role": "user",
            "content": user_input
        }
    ]
    return chatbot(messages)

# General chat handler for non-greeting intents
def handle_general_chat(user_input):
    messages = [
        {
            "role": "system",
            "content": """
            You are a UK train assistant.
            Keep answers short.
            Do NOT invent train times, prices, or schedules.
            If the user asks for something outside trains, politely redirect.
            """
        },
        {
            "role": "user",
            "content": user_input
        }
    ]
    return chatbot(messages)

# -----------------------------
# MAIN LOOP
# -----------------------------
def main():
    print("🚆 Train Assistant (Hybrid Intent + LLM) Started\n")

    while True:
        user_input = input("User: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        intent, confidence = classify_intent(user_input)
        if intent and confidence >= 0.7:
            print(f"Detected intent: {intent} (confidence: {confidence:.2f})")
        else:
            print("No clear intent detected, defaulting to general chat.")

        # --- ROUTING ---
        if intent == "greeting":
            response = handle_greeting(user_input)

        else:
            response = handle_general_chat(user_input)

        print("Assistant:", response)

if __name__ == "__main__":
    main()
