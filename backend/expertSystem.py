import collections
import collections.abc

for type_name in ['Mapping','MutableMapping','Iterable','MutableSet']:
    if not hasattr(collections,type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))

from experta import *

#Stores information about a user's intended journey.
class Journey(Fact):
    pass

#Stores user preference for ticket type.
class TicketPreference(Fact):
    pass

class TrainChatbot(KnowledgeEngine):
    @Rule(Journey(origin=MATCH.o, destination=MATCH.d, date=MATCH.dt))
    def ask_ticket(self, o, d, dt):
        print(f"You want to travel from {o} to {d} on {dt}.")
        print("Do you want the cheapest, fastest, or any ticket?")

    @Rule(Journey(origin=MATCH.origin, destination=MATCH.destination, date=MATCH.dt),
          TicketPreference(type="cheapest"))
    
    def cheapest_ticket(self, origin, destination, dt):
        tickets = [
            {"type": "Advance", "price": 25, "time": "09:00"},
            {"type": "Off-Peak", "price": 40, "time": "11:00"},
            {"type": "Anytime", "price": 70, "time": "08:00"}
        ]
        cheapest = min(tickets, key=lambda x: x["price"])
        print(f"Cheapest ticket: £{cheapest['price']} ({cheapest['type']}) at {cheapest['time']}")
        print(f"Book here:")

engine = TrainChatbot()
engine.reset()

# Use journey info
# engine.declare(Journey(origin="London", destination="Manchester", date="2026-04-01"))

# User provides ticket preference
engine.declare(TicketPreference(type="cheapest"))

engine.run()

