import requests
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

# Load env
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, 'user.env')
load_dotenv(env_path)

USERNAME = os.environ.get("CURRENT_USERNAME")
PASSWORD = os.environ.get("CURRENT_PASSWORD")

NS = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'jps': 'http://www.thalesgroup.com/ojp/jpservices',
    'com': 'http://www.thalesgroup.com/ojp/common'
}

URL = "https://ojp.nationalrail.co.uk/webservices/jpservices"
HEADERS = {'Content-Type': 'text/xml; charset=utf-8'}


def get_departures(station_code, destination=None):
    from_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:jps="http://www.thalesgroup.com/ojp/jpservices"
                      xmlns:com="http://www.thalesgroup.com/ojp/common">
       <soapenv:Header/>
       <soapenv:Body>
          <jps:DepartureBoardRequest>
             <jps:specifiedStation>
                <jps:primaryStationCrs>{station_code}</jps:primaryStationCrs>
             </jps:specifiedStation>
             <jps:stoppingPattern>DEPART</jps:stoppingPattern>
             <jps:fromTime>{from_time}</jps:fromTime>
          </jps:DepartureBoardRequest>
       </soapenv:Body>
    </soapenv:Envelope>"""

    response = requests.post(URL, data=soap_envelope, headers=HEADERS, auth=(USERNAME, PASSWORD))

    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text}")

    root = ET.fromstring(response.text)
    body = root.find('soap:Body', NS)
    board = body.find('.//jps:DepartureBoardResponse', NS)

    journeys = board.findall('.//jps:stationJourneyDetail', NS)

    results = []

    for j in journeys:
        origin = j.findtext('com:originStation', default='', namespaces=NS)
        dest = j.findtext('com:destinationStation', default='', namespaces=NS)
        dep_time = j.findtext('com:timetable/com:scheduled/com:departure', default='', namespaces=NS)
        platform = j.findtext('com:platform', default='', namespaces=NS)

        if destination and dest != destination:
            continue

        results.append({
            "origin": origin,
            "destination": dest,
            "departure_time": dep_time,
            "platform": platform
        })

    return results

#Get the stations inbetween origin and destination 
def get_calling_points(origin, destination, dep_time, arr_time):
    soap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:jps="http://www.thalesgroup.com/ojp/jpservices">
       <soapenv:Header/>
       <soapenv:Body>
          <jps:RealtimeCallingPointsRequest>
             <jps:origin>{origin}</jps:origin>
             <jps:destination>{destination}</jps:destination>
             <jps:departure>{dep_time}</jps:departure>
             <jps:arrival>{arr_time}</jps:arrival>
          </jps:RealtimeCallingPointsRequest>
       </soapenv:Body>
    </soapenv:Envelope>"""

    response = requests.post(URL, data=soap, headers=HEADERS, auth=(USERNAME, PASSWORD))

    if response.status_code != 200:
        print("Calling points error:", response.text)
        return None

    root = ET.fromstring(response.text)
    body = root.find('soap:Body', NS)
    resp = body.find('.//jps:RealtimeCallingPointsResponse', NS)

    if resp is None:
        print("No calling points returned — likely wrong times.")
        print(response.text)
        return None

    legs = resp.findall('.//jps:leg', NS)
    calling_points = []

    #For each station within the journey 
    for leg in legs:
        cps = leg.findall('.//jps:realtimeCallingPoint', NS)
        for cp in cps:
            calling_points.append({
                "station": cp.findtext('jps:station', default='', namespaces=NS),
                "platform": cp.findtext('jps:platform', default='', namespaces=NS),
                "scheduled_arrival": cp.findtext('jps:timetable/jps:scheduledTimes/jps:arrival', default='', namespaces=NS),
                "scheduled_departure": cp.findtext('jps:timetable/jps:scheduledTimes/jps:departure', default='', namespaces=NS),
                "xml": cp
            })

    return calling_points

#Distruptions for a station
def extract_origin_disruption(journey_xml):
    scheduled_dep = journey_xml.findtext('jps:timetable/jps:scheduled/jps:departure', namespaces=NS)
    realtime_dep = journey_xml.findtext('jps:timetable/jps:realtime/jps:departure', namespaces=NS)

    cancelled = journey_xml.findtext('jps:cancelled', default='false', namespaces=NS)
    cancel_reason = journey_xml.findtext('jps:cancellationReason', default='', namespaces=NS)
    late_reason = journey_xml.findtext('jps:lateRunningReason', default='', namespaces=NS)

    bulletins = journey_xml.findall('.//com:serviceBulletin', NS)

    return {
        "scheduled_departure": scheduled_dep,
        "realtime_departure": realtime_dep,
        "cancelled": cancelled,
        "cancellation_reason": cancel_reason,
        "late_running_reason": late_reason,
        "service_bulletins": [b.text for b in bulletins]
    }

#Get departures from Origin to Destination
def get_departures(station_code, destination=None):
    from_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:jps="http://www.thalesgroup.com/ojp/jpservices"
                      xmlns:com="http://www.thalesgroup.com/ojp/common">
       <soapenv:Header/>
       <soapenv:Body>
          <jps:DepartureBoardRequest>
             <jps:specifiedStation>
                <jps:primaryStationCrs>{station_code}</jps:primaryStationCrs>
             </jps:specifiedStation>
             <jps:stoppingPattern>DEPART</jps:stoppingPattern>
             <jps:fromTime>{from_time}</jps:fromTime>
          </jps:DepartureBoardRequest>
       </soapenv:Body>
    </soapenv:Envelope>"""

    response = requests.post(URL, data=soap_envelope, headers=HEADERS, auth=(USERNAME, PASSWORD))

    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text}")

    root = ET.fromstring(response.text)
    body = root.find('soap:Body', NS)
    board = body.find('.//jps:DepartureBoardResponse', NS)

    journeys = board.findall('.//jps:stationJourneyDetail', NS)

    results = []

    for j in journeys:
        origin = j.findtext('com:originStation', default='', namespaces=NS)
        dest = j.findtext('com:destinationStation', default='', namespaces=NS)

        if destination and dest != destination:
            continue

        scheduled_dep = j.findtext('com:timetable/com:scheduled/com:departure', default='', namespaces=NS)
        realtime_dep = j.findtext('com:timetable/com:realtime/com:departure', default='', namespaces=NS)

        cancelled = j.findtext('com:cancelled', default='false', namespaces=NS)
        cancel_reason = j.findtext('com:cancellationReason', default='', namespaces=NS)
        late_reason = j.findtext('com:lateRunningReason', default='', namespaces=NS)

        platform = j.findtext('com:platform', default='', namespaces=NS)

        results.append({
            "origin": origin,
            "destination": dest,
            "scheduled_departure": scheduled_dep,
            "realtime_departure": realtime_dep,
            "cancelled": cancelled == "true",
            "cancellation_reason": cancel_reason,
            "late_running_reason": late_reason,
            "platform": platform
        })

    return results

def get_ticket_prices_clean(origin_crs, destination_crs, depart_datetime, num_adults=0, num_children=0, fare_class="STANDARD"):
    soap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:jps="http://www.thalesgroup.com/ojp/jpservices"
                      xmlns:com="http://www.thalesgroup.com/ojp/common">
       <soapenv:Header/>
       <soapenv:Body>
          <jps:RealtimeJourneyPlanRequest>

             <jps:origin>
                <com:stationCRS>{origin_crs}</com:stationCRS>
             </jps:origin>

             <jps:destination>
                <com:stationCRS>{destination_crs}</com:stationCRS>
             </jps:destination>

             <jps:realtimeEnquiry>STANDARD</jps:realtimeEnquiry>

             <jps:outwardTime>
                <jps:departBy>{depart_datetime}</jps:departBy>
             </jps:outwardTime>

             <jps:directTrains>false</jps:directTrains>

             <jps:fareRequestDetails>
                <jps:passengers>
                    <com:adult>{num_adults}</com:adult>
                    <com:child>{num_children}</com:child>
                </jps:passengers>
                <jps:fareClass>{fare_class}</jps:fareClass>
             </jps:fareRequestDetails>

          </jps:RealtimeJourneyPlanRequest>
       </soapenv:Body>
    </soapenv:Envelope>"""

    response = requests.post(URL, data=soap, headers=HEADERS, auth=(USERNAME, PASSWORD))

    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text}")

    root = ET.fromstring(response.text)

    # -----------------------------
    # FIND FARES WITHOUT XPATH
    # -----------------------------
    fares = []
    for elem in root.iter():
        if elem.tag.endswith("fare"):
            fares.append(elem)

    print("\n===== Ticket Prices =====")

    if not fares:
        print("No fares returned.")
        return []

    results = []

    for f in fares:
        fare_info = {}

        # Loop through all children and extract by local-name
        for child in f.iter():
            tag = child.tag.split('}')[-1]  # remove namespace
            text = child.text.strip() if child.text else None
            fare_info[tag] = text

        results.append(fare_info)

        # Pretty print
        price = None
        if "totalPrice" in fare_info and fare_info["totalPrice"]:
            price = int(fare_info["totalPrice"]) / 100

        print(f"\n{fare_info.get('description', 'Unknown fare')}")
        print(f"  Class: {fare_info.get('fareClass')}")
        print(f"  Category: {fare_info.get('fareCategory')}")
        print(f"  Route code: {fare_info.get('routeCode')}")
        print(f"  Price: £{price:.2f}" if price else "  Price: N/A")

    print("=========================\n")

    return results




now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
get_ticket_prices_clean("NRW", "LST", now, num_adults=1, num_children=0, fare_class="STANDARD")





#Test Usage:

#Departures
# departures = get_departures("RDG", destination="PAD")
# for d in departures:
#     print(d)

#Calling points inbetween origin and destination
# calling_points = get_calling_points("NRW", "COL", "2026-06-01T15:30:00", "2026-06-01T16:28:00")
# print(calling_points)  
