import streamlit as st
import requests
from datetime import datetime as dt

arrival_url = "http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode="
stop_url = "http://datamall2.mytransport.sg/ltaodataservice/BusStops"
headers = {
    "AccountKey": st.secrets["lta_token"]
}

bus_dict = {
    "Load": {
        "SEA": "with seats.",
        "SDA": "with standing only.",
        "LSD": "almost full.",
    },
    "Type": {
        "SD": "Single Deck",
        "DD": "Double Deck",
        "BD": "Bendy bus",
    }
}

@st.cache_data(ttl=2_630_000, show_spinner="Getting ready...")
def get_stops():
    skip_operator = 0
    bus_stops = {}
    
    while True:
        response = requests.get(stop_url+"?$skip="+str(skip_operator), headers=headers)
        results = response.json()

        if response.status_code == 200:
            if results["value"]:
                for stop in results["value"]:
                    bus_stops[stop["BusStopCode"]] = f"{stop['Description']} along {stop['RoadName']}"
            else:
                break
        else:
            print("Error")
        
        skip_operator += 500

    print(f"{len(bus_stops.keys())} stops retrieved.")
    return bus_stops

def read_response(service):
    results = []
    for bus in ["NextBus", "NextBus2", "NextBus3"]:
        if service[bus]["EstimatedArrival"]:
            # get eta
            bus_eta = dt.strptime(service[bus]['EstimatedArrival'], "%Y-%m-%dT%H:%M:%S%z") - dt.now().astimezone()
            bus_eta_mins = round(bus_eta.total_seconds() / 60)
            # check bus type and load
            bus_type = bus_dict["Type"][service[bus]['Type']]
            bus_load = bus_dict["Load"][service[bus]['Load']]
            results.append([bus_eta_mins, bus_type, bus_load])
        else:
            results.append([None, None, None])
    return results

@st.cache_data(ttl=15, show_spinner=False)
def get_arrivals(bus_stop):
    response = requests.get(arrival_url+bus_stop, headers=headers)

    if response.status_code == 200:
        results = response.json()
        for bus_service in results["Services"]:
            results = read_response(bus_service)
            eta_list = [eta for eta, *_ in results if eta is not None and eta >= 0]
            # display results
            with st.expander(f"**{bus_service['ServiceNo']}** in {eta_list[0]} mins"):
                    for result in results:
                        if result[0] is None:
                            pass
                        elif result[0] == 0:
                            st.markdown(f"Bus is here! {result[1]} {result[2]}")
                        elif result[0] < 0:
                            st.markdown(f"Oops, you just missed the bus.")
                        elif result[0] > 0:
                            st.markdown(f"**{result[0]}** mins. {result[1]} {result[2]}")
    else:
        return "Error"

bus_stops = get_stops()

st.title("Where's My Bus? :bus:")
st.markdown("Stalk your bus, made possible by the [Land Transport Authority](https://datamall.lta.gov.sg/content/datamall/en.html) of Singapore.")

my_stop = st.text_input("Which bus stop?", max_chars=5)

if my_stop:
    if my_stop.isdigit() and len(my_stop) == 5:
        if my_stop in bus_stops:
            st.header(f"{bus_stops[my_stop]}")
            get_arrivals(my_stop)
        else:
            st.error("Bus stop not found. Please try again.")
    else:
        st.error("Please provide a 5 digit bus stop code.")