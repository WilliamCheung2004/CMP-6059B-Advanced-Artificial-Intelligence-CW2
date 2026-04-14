import collections
import collections.abc

# Fix for Python 3.10+ compatibility with experta
for type_name in ['Mapping', 'MutableMapping', 'Iterable', 'MutableSet']:
    if not hasattr(collections, type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))

from experta import *

# FACT
class Journey(Fact):
    """Stores information about a user's intended journey."""
    origin = Field(str)
    destination = Field(str)
    date = Field(str)
    preference = Field(str, default=None)
    price = Field(float, default=None)

class TicketPreference(Fact):
    """Stores user preference for ticket type."""
    type = Field(str)

# KNOWLEDGE ENGINE
class TrainChatbot(KnowledgeEngine):

    def set_ticket_details(self, journey, ticket_type):
        tickets = [
            {"type": "Advance", "price": 25, "speed": "slow"},
            {"type": "Off-Peak", "price": 40, "speed": "medium"},
            {"type": "Anytime", "price": 70, "speed": "fast"}
        ]

        if ticket_type == "cheapest":
            selected = min(tickets, key=lambda x: x["price"])
        elif ticket_type == "quickest":
            selected = max(tickets, key=lambda x: x["speed"])
        else:
            selected = tickets[1]  # Off-Peak default

        self.modify(journey, price=selected["price"])
        print(f"\nSelected ticket:")
        print(f"  Type: {selected['type']}")
        print(f"  Price: £{selected['price']}")
        print(f"  Route: {journey['origin']} → {journey['destination']} on {journey['date']}")
        print("You can now proceed to booking.\n")

    # RULES
    @Rule(Journey(origin=MATCH.o, destination=MATCH.d, date=MATCH.dt, preference=None))
    def ask_preference(self, o, d, dt):
        print(f"You want to travel from {o} to {d} on {dt}.")
        print("Do you want the cheapest, quickest, or any ticket?")

    @Rule(AS.journey << Journey(origin=MATCH.o, destination=MATCH.d, date=MATCH.dt),
          TicketPreference(type=MATCH.pref))
    def choose_ticket(self, journey, pref):
        self.set_ticket_details(journey, pref)
