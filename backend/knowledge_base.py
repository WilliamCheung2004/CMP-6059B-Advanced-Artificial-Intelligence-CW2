import json
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_stations():
    """Loads station names and codes from a CSV file into the knowledge base"""
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

def get_station_code(station_name: str) -> str:
    """Returns the station code e.g. Norwich → NRW"""
    station_name = station_name.strip().upper()  # Normalise input
    if station_name in KB['stations']:
        return KB['stations'][station_name]
    
    for name, code in KB['stations'].items():
        if station_name in name:
            return code
        
    return None

def get_faq(topic: str) -> str:
    """Returns FAQ answer for a topic e.g. 'railcard'"""
    #check for keyword match in faqs
    topic_lower = topic.lower()
    for key, answer in KB['faqs'].items():
        if key in topic_lower:
            return answer
    return None

def get_rule(topic: str) -> str:
    """Returns a rule e.g. 'advance_booking'"""
    return KB['rules'].get(topic, None)

def get_all_stations() -> list:
    """Returns list of all known station names"""
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