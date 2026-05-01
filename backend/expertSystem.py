import collections
import collections.abc
import re

for type_name in ['Mapping', 'MutableMapping', 'Iterable', 'MutableSet']:
    if not hasattr(collections, type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))

from experta import *

class Journey(Fact):
    origin = Field(str)
    destination = Field(str)
    date = Field(str)
    preference = Field(str, default=None)
    price = Field(float, default=None)

class TicketPreference(Fact):
    type = Field(str)

class Railcard(Fact):
    type = Field(str)
    num_children = Field(int, default=0)
    num_companions = Field(int, default=0)

RAILCARD_DISCOUNTS = {
    "16-17": {"adult": 0.50},
    "16-25": {"adult": 0.6667},
    "26-30": {"adult": 0.6667},
    "Disabled": {"adult": 0.6667},
    "Senior": {"adult": 0.6667},
}

class TicketBot(KnowledgeEngine):
    """Expert system for intelligent ticket selection based on user preferences and railcard."""
    
    def __init__(self, tickets_data=None):
        """Initialize TicketBot with optional ticket data."""
        super().__init__()
        self.tickets_data = tickets_data or []
        self.selected_ticket = None
    
    def select_ticket(self, preference=None, railcard=None):
        """
        Select the best ticket based on preference and railcard.
        
        Args:
            preference: "cheapest", "quickest", or None
            railcard: Railcard type or None
        
        Returns:
            Selected ticket dict or None
        """
        if not self.tickets_data:
            return None
        
        # Select based on preference
        if preference == "cheapest":
            selected = min(self.tickets_data, key=lambda x: int(x.get("totalPrice", float('inf'))))
        else:
            # Default to first available
            selected = self.tickets_data[0]
        
        self.selected_ticket = selected
        return selected
    
    def apply_railcard_discount(self, base_price, railcard_type):
        """Apply railcard discount to base price."""
        if not railcard_type:
            return base_price
        
        rules = RAILCARD_DISCOUNTS.get(railcard_type, {})
        multiplier = rules.get("adult", 1.0)
        return base_price * multiplier

    def set_ticket_details(self, journey, ticket_type, railcard=None):
        """Legacy method: Set ticket details and update journey fact."""
        if not self.tickets_data:
            print("Error: No ticket data available")
            return
        
        # Select ticket based on preference
        selected = self.select_ticket(ticket_type, railcard)
        if not selected:
            print("Error: Could not select a ticket")
            return
        
        # Extract base price
        try:
            base_price = int(selected.get("totalPrice", 0)) / 100
        except:
            base_price = 0.0
        
        # Apply railcard discount
        if railcard:
            if isinstance(railcard, dict):
                railcard_type = railcard.get("type")
            else:
                railcard_type = railcard
            final_price = self.apply_railcard_discount(base_price, railcard_type)
        else:
            final_price = base_price
        
        # Update journey fact if available
        if journey:
            self.modify(journey, price=float(final_price))
        
        # Output
        print("\nSelected ticket:")
        print(f"  Description: {selected.get('description', 'Fare')}")
        print(f"  Base Price: £{base_price:.2f}")
        if railcard:
            print(f"  Railcard Applied: {railcard}")
        print(f"  Final Price: £{final_price:.2f}")
        print(f"  Route: {journey.origin} → {journey.destination} on {journey.date}")
        print("You can now proceed to booking.\n")

    @Rule(Journey(preference=MATCH.p),
          Railcard(type=MATCH.rc))
    def apply_ticket_with_railcard(self, p, rc):
        """Apply ticket selection with railcard discount."""
        # Note: This rule is not executed in current flow; selection done in reasoningEngine.py
        if self.tickets_data:
            journey = [f for f in self.facts.values() if isinstance(f, Journey)]
            if journey:
                self.set_ticket_details(journey[0], p, rc)

    @Rule(Journey(preference=MATCH.p),
          NOT(Railcard(type=MATCH.anything)))
    def apply_ticket_no_railcard(self, p):
        """Apply ticket selection without railcard."""
        if self.tickets_data:
            journey = [f for f in self.facts.values() if isinstance(f, Journey)]
            if journey:
                self.set_ticket_details(journey[0], p, railcard=None)

def parse_traveller_info(text):
    text = text.lower()

    result = {
        "num_adults": 0,
        "num_children": 0,
        "railcard": None,
        "fare_class": None,
        "ticket_category": None
    }

    # Adults
    adult_match = re.search(r"(\d+)\s*adult", text)
    if adult_match:
        result["num_adults"] = int(adult_match.group(1))
    elif "adult" in text:
        result["num_adults"] = 1

    # Children
    child_match = re.search(r"(\d+)\s*child", text)
    if child_match:
        result["num_children"] = int(child_match.group(1))
    elif "child" in text:
        result["num_children"] = 1

    # Railcards
    for rc in RAILCARD_DISCOUNTS.keys():
        if rc.lower() in text:
            result["railcard"] = rc

    # Fare class
    if "first" in text:
        result["fare_class"] = "FIRST"
    elif "standard" in text:
        result["fare_class"] = "STANDARD"

    # Ticket category
    if "advance" in text:
        result["ticket_category"] = "Advance"
    elif "off-peak" in text:
        result["ticket_category"] = "Off-Peak"
    elif "anytime" in text:
        result["ticket_category"] = "Anytime"

    return result


