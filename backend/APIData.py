import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import os 
from dotenv import load_dotenv

load_dotenv(dotenv_path='user.env')  

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD") 

# User inputs
station_code = "NRW"           
stopping_pattern = "DEPART"    
forced_destination = "LST"     

# Build SOAP envelope
from_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
print(from_time)

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

#Journeys contain origin, destingation and time departure
for j in journeys:
    origin = j.findtext('ns2:originStation', default='', namespaces=ns)
    destination = j.findtext('ns2:destinationStation', default='', namespaces=ns)

    # Fallback if destination somehow missing - probably dosen't happen
    if not destination:
        destination = "NONE"

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

