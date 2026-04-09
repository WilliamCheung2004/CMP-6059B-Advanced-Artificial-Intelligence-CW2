#pre-requisite libraries:
#pip install experta

import collections
import collections.abc

for type_name in ['Mapping','MutableMapping','Iterable','MutableSet']:
    if not hasattr(collections,type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))

from experta import *

#Stores information about a user's intended journey.
class Journey(Fact):
    origin = Field(str)
    destination = Field(str)
    date = Field(str)
    departure_time = Field(str, default=None)
    price = Field(float, default=None)

#Stores user preference for ticket type.
class TicketPreference(Fact):
    pass

class TrainChatbot(KnowledgeEngine):
    def set_ticket_details(self, journey, ticket_type):
        tickets = [
            {"type": "Advance", "price": 25},
            {"type": "Off-Peak", "price": 40},
            {"type": "Anytime", "price": 70}
        ]
        if ticket_type == "cheapest":
            selected = min(tickets, key=lambda x: x["price"])
        elif ticket_type == "fastest":
            selected = min(tickets, key=lambda x: x["price"])  # Assuming fastest is also cheapest for simplicity
        else:
            selected = tickets[2]  # Anytime
        self.modify(journey, price=selected['price'])
        print(f"Selected ticket: £{selected['price']} ({selected['type']}) at {journey.departure_time}")
        print(f"Book here:")

    @Rule(Journey(origin=MATCH.o, destination=MATCH.d, date=MATCH.dt, departure_time=MATCH.t))
    def ask_ticket(self, o, d, dt, t):
        print(f"You want to travel from {o} to {d} on {dt} at {t}.")
        print("Do you want the cheapest, fastest, or any ticket?")

    @Rule(AS.journey << Journey(origin=MATCH.origin, destination=MATCH.destination, date=MATCH.dt, departure_time=MATCH.departure_time),
          TicketPreference(type=MATCH.ticket_type))
    
    def select_ticket(self, journey, origin, destination, dt, departure_time, ticket_type):
        self.set_ticket_details(journey, ticket_type)


# Use journey info
# engine.declare(Journey(origin="London", destination="Manchester", date="2026-04-01"))

# User provides ticket preference
# engine.declare(TicketPreference(type="cheapest"))



