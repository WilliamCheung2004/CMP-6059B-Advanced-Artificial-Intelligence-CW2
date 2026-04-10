import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import os 
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, 'user.env')
loaded = load_dotenv(dotenv_path=env_path, override=True, verbose=True)

username = os.environ.get("CURRENT_USERNAME")
password = os.environ.get("CURRENT_PASSWORD")
    
# User inputs
stopping_pattern = "DEPART"    
origin = "NRW"           
destination = "LST"     

# Build SOAP envelope
from_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
print(from_time)

#Method to get station info from station code
soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:jps="http://www.thalesgroup.com/ojp/jpservices"
                  xmlns:com="http://www.thalesgroup.com/ojp/common">
   <soapenv:Header/>
   <soapenv:Body>
      <jps:DepartureBoardRequest>
         <jps:specifiedStation>
            <jps:primaryStationCrs>{origin}</jps:primaryStationCrs>
         </jps:specifiedStation>
         <jps:stoppingPattern>{stopping_pattern}</jps:stoppingPattern>
         <jps:fromTime>{from_time}</jps:fromTime>
      </jps:DepartureBoardRequest>
   </soapenv:Body>
</soapenv:Envelope>"""

# Send SOAP request
url = "https://ojp.nationalrail.co.uk/webservices/jpservices"
headers = {'Content-Type': 'text/xml; charset=utf-8'}

response = requests.post(url, data=soap_envelope, headers=headers, auth=(username, password))

if response.status_code != 200:
    print(f"Error {response.status_code}: {response.text}")
    exit()

# Parse XML response
ns = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'ns1': 'http://www.thalesgroup.com/ojp/jpservices',
    'ns2': 'http://www.thalesgroup.com/ojp/common'
}

root = ET.fromstring(response.text)
body = root.find('soap:Body', ns)

if body is None:
    print("No SOAP Body found.")
    exit()

departure_board = body.find('.//ns1:DepartureBoardResponse', ns)
if departure_board is None:
    print("No DepartureBoardResponse found in SOAP response.")
    exit()

# print the SOAP info
pretty_xml = minidom.parseString(ET.tostring(body)).toprettyxml()
print("SOAP Body:\n", pretty_xml)

# Extract journey details
journeys = departure_board.findall('.//ns1:stationJourneyDetail', ns)

rows = []

for j in journeys:
    origin = j.findtext('ns2:originStation', default='', namespaces=ns)
    destinationData = j.findtext('ns2:destinationStation', default='', namespaces=ns)

    # Skip trains that are not going to the desired destination
    if destination != destinationData:
        continue

    departure_time = j.findtext(
        'ns2:timetable/ns2:scheduled/ns2:departure',
        default='',
        namespaces=ns
    )

    platform = j.findtext('ns2:platform', default='', namespaces=ns)

    rows.append([origin, destination, departure_time, platform])


# Print extracted data
print("\nExtracted departures:")
for r in rows:
    print(r)

