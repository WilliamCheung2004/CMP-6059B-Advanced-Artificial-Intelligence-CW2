#knowledge_base.py

import json
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#load station names and codes from a CSV file into the knowledge base
def load_stations():
    stations = {}
    with open(os.path.join(BASE_DIR, 'stations.csv'), 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stations[row['NAME']] = row['CRS']
            
    return stations


#load the knowledge base from the JSON file
with open(os.path.join(BASE_DIR, 'knowledge_base.json'), 'r') as f:
    KB = json.load(f)
    
KB['stations'] = load_stations()

#returns the station code for a given station name, or None if not found
def get_station_code(station_name: str) -> str:
    station_name = station_name.strip().upper()  # Normalise input
    if station_name in KB['stations']:
        return KB['stations'][station_name]
    
    for name, code in KB['stations'].items():
        if station_name in name:
            return code
        
    return None

#returns the FAQ answer for a given topic, or None if not found
def get_faq(topic: str) -> str:
    #check for keyword match in faqs
    topic_lower = topic.lower()
    for key, answer in KB['faqs'].items():
        if key in topic_lower:
            return answer
    return None

#returns the rule for a given topic, or None if not found
def get_booking_rule(topic: str) -> str:
    return KB['booking_rules'].get(topic, None)

#returns a list of all known station names
def get_all_stations() -> list:
    return list(KB['stations'].keys())


if __name__ == '__main__':
    print("\nTesting knowledge base functions...\n")
    print(get_station_code('Norwich'))     # NRW
    print(get_station_code('Cambridge'))    # CBG
    print(get_station_code('Liverpool street')) # LSX
    print(get_station_code('Liverpool street London')) # LST
    print(get_faq('railcard'))             # A railcard gives you...
    print(get_rule('advance_booking'))     # Cheapest advance tickets...
    print("\n")