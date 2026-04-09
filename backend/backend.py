from intent import detect_intent, extract_entities
from expertSystem import *
from experta import *
from datetime import datetime

now = datetime.now()

def determine_greeting():
    hour = int(now.strftime("%H"))
    if 6 <= hour < 12:
        return "Good morning! "
    elif 12 <= hour < 18:
        return "Good afternoon! "
    else:
        return "Good evening! "

def run_journey(origin, destination, date, preference):
    engine = TrainChatbot()
    engine.reset()
    engine.declare(Journey(origin=origin, destination=destination, date=date))
    engine.declare(TicketPreference(type=preference))
    engine.run()

if __name__ == "__main__":
    print(determine_greeting() + "What would you like to do?")

    while True:
        response = input("> ")

        intent = detect_intent(response)
        entities = extract_entities(response)

        if intent == "goodbye":
            print("Goodbye! Have a great journey.")
            break

        elif intent == "find_ticket":
            origin = entities.get("origin", "unknown")
            destination = entities.get("destination", "unknown")
            date = entities.get("date", "today")
            # Ask for preference if not in message
            print("Do you want the cheapest, fastest, or any ticket?")
            pref = input("> ").strip().lower()
            run_journey(origin, destination, date, pref)

        elif intent == "greeting":
            print("Hi! I can help you find train tickets or check delays.")

        elif intent == "delay_prediction":
            print("Delay prediction isn't fully implemented yet — coming soon!")

        else:
            print("I'm not sure I understood that. You can ask about tickets or train delays.")