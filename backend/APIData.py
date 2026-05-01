import string

import requests
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
from datetime import datetime

# Load env
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, 'user.env')
load_dotenv(env_path)

def format_date(dt_str):
    if not dt_str:
        return ""
    return dt_str.replace("T", " ").split(".")[0]


def get_timestamp(date_str, time_str):
    if not date_str or not time_str:
        return None
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except:
        return None

USERNAME = os.environ.get("CURRENT_USERNAME")
PASSWORD = os.environ.get("CURRENT_PASSWORD")

NS = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'jps': 'http://www.thalesgroup.com/ojp/jpservices',
    'com': 'http://www.thalesgroup.com/ojp/common',
    'ns3': 'http://www.thalesgroup.com/ojp/common'
}


URL = "https://ojp.nationalrail.co.uk/webservices/jpservices"
HEADERS = {'Content-Type': 'text/xml; charset=utf-8'}


#Get the stations inbetween origin and destination 
def journey_plan(origin, destination, time):
    soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:jps="http://www.thalesgroup.com/ojp/jpservices"
                      xmlns:com="http://www.thalesgroup.com/ojp/common">
       <soapenv:Header/>
       <soapenv:Body>
          <jps:RealtimeJourneyPlanRequest>

             <jps:origin>
                <com:stationCRS>{origin}</com:stationCRS>
             </jps:origin>

             <jps:destination>
                <com:stationCRS>{destination}</com:stationCRS>
             </jps:destination>

             <jps:realtimeEnquiry>STANDARD</jps:realtimeEnquiry>

             <jps:outwardTime>
                <jps:departBy>{time}</jps:departBy>
             </jps:outwardTime>

             <jps:directTrains>false</jps:directTrains>

          </jps:RealtimeJourneyPlanRequest>
       </soapenv:Body>
    </soapenv:Envelope>"""

    response = requests.post(
        URL,
        data=soap_envelope,
        headers=HEADERS,
        auth=(USERNAME, PASSWORD)
    )

    root = ET.fromstring(response.text)
    body = root.find("soap:Body", NS)

    if body is None:
        return []

    jp = body.find(".//jps:RealtimeJourneyPlanResponse", NS)

    if jp is None:
        print("DEBUG SOAP RESPONSE:\n", response.text)
        return []

    journeys_xml = jp.findall(".//jps:outwardJourney", NS)

    results = []

    for j in journeys_xml:
        journey_origin = j.findtext("jps:origin", default="", namespaces=NS)
        journey_dest = j.findtext("jps:destination", default="", namespaces=NS)

        if journey_dest.upper() != destination.upper():
            continue

        bulletins = set()

        raw_bulletins = j.findall(".//jps:serviceBulletins/com:description", NS)
        for b in raw_bulletins:
            if b is not None and b.text:
                bulletins.add(b.text.strip())

        services = []
        seen_services = set()

        for leg in j.findall(".//jps:leg", NS):

            service_key = (
                leg.findtext("jps:board", default="", namespaces=NS),
                leg.findtext("jps:alight", default="", namespaces=NS),
                leg.findtext(".//jps:scheduled/jps:departure", default="", namespaces=NS),
                leg.findtext(".//jps:scheduled/jps:arrival", default="", namespaces=NS),
                leg.findtext(".//com:name", default="", namespaces=NS),
            )

            if service_key in seen_services:
                continue
            seen_services.add(service_key)

            services.append({
                "mode": leg.findtext("jps:mode", default="", namespaces=NS),
                "from": service_key[0],
                "to": service_key[1],
                "departure": format_date(service_key[2]),
                "arrival": format_date(service_key[3]),
                "realtime_departure": leg.findtext(".//jps:realtime/jps:departure", default="", namespaces=NS),
                "realtime_arrival": leg.findtext(".//jps:realtime/jps:arrival", default="", namespaces=NS),
                "operator": service_key[4],
            })

        results.append({
            "origin": journey_origin,
            "destination": journey_dest,
            "service_bulletins": list(bulletins),
            "services": services
        })

    return results


def get_ticket_prices(origin_crs, destination_crs, depart_datetime, num_adults=0, num_children=0, fare_class="STANDARD"):
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

    # Find all fare elements 
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

    #     print(f"\n{fare_info.get('description', 'Unknown fare')}")
    #     print(f"  Class: {fare_info.get('fareClass')}")
    #     print(f"  Category: {fare_info.get('fareCategory')}")
    #     print(f"  Route code: {fare_info.get('routeCode')}")
    #     print(f"  Price: £{price:.2f}" if price else "  Price: N/A")

    # print("=========================\n")

    return results

def print_journey_details(origin_crs, destination_crs, depart_datetime):


    journeys = journey_plan(origin_crs, destination_crs, depart_datetime)

    if not journeys:
        print("No journeys found.")
        return []

    # for j in journeys:
    #     print(f"\nJourney {j['journey_origin']} → {j['journey_destination']}")

    #     if j["service_bulletin"]:
    #         print("  ⚠ " + j["service_bulletin"])

    #     for leg in j["legs"]:
    #         dep = leg["realtime_departure"] or leg["scheduled_departure"]
    #         arr = leg["realtime_arrival"] or leg["scheduled_arrival"]

    #         print(
    #             f"  {leg['mode']:<16} "
    #             f"{leg['origin']} → {leg['destination']}  "
    #             f"{dep} → {arr}  "
    #             f"({leg['operator']})"
    #         )

    # print("\n")  # spacing
    return journeys





#Test Usage:

#Ticket prices 
# now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
# get_ticket_prices("NRW", "COL", now, num_adults=1, num_children=0, fare_class="STANDARD")


# now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
# print_journey_details("NRW", "LST", now)

#Journey info with legs 

# time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
# journeys = journey_plan("WSB", "PAD", time)

# for j in journeys:
#     print(f"\nJourney {j['journey_origin']} → {j['journey_destination']}")

#     if j["service_bulletin"]:
#         print("  ⚠ " + j["service_bulletin"])

#     for leg in j["legs"]:
#         dep = leg["realtime_departure"] or leg["scheduled_departure"]
#         arr = leg["realtime_arrival"] or leg["scheduled_arrival"]

#         print(
#             f"  {leg['mode']:<16} "
#             f"{leg['origin']} → {leg['destination']}  "
#             f"{dep} → {arr}  "
#             f"({leg['operator']})"
#         )
