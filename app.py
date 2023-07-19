import streamlit as st
import requests
from datetime import datetime as dt

arrival_url = "http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode="
stop_url = "http://datamall2.mytransport.sg/ltaodataservice/BusStops"
headers = {
    "AccountKey": st.secrets["lta_token"]
}
TIMEOUT = (5, 15)

response_dict = {
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
        try:
            response = requests.get(stop_url+"?$skip="+str(skip_operator), headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if data["value"]:
                for stop in data["value"]:
                    bus_stops[stop["BusStopCode"]] = f"{stop['Description'].title()} along {stop['RoadName']}"
            else:
                break
        except requests.exceptions.HTTPError as e:
            print(e)
            st.error("Sorry, an error occurred. Please try again.")
            break
        except requests.exceptions.JSONDecodeError as e:
            print(e)
            st.error("Sorry, an error occurred. Please try again.")    
            break
        
        skip_operator += 500

    print(f"{len(bus_stops.keys())} stops retrieved.")
    return bus_stops

def read_response(data):
    results = {}
    for service in data["Services"]:
        service_no = service["ServiceNo"]
        results[service_no] = {
            "ETA": [],
            "Buses": []
        }
        for bus in ["NextBus", "NextBus2", "NextBus3"]:
            if service[bus]["EstimatedArrival"]:
                # get eta
                bus_eta = dt.strptime(service[bus]['EstimatedArrival'], "%Y-%m-%dT%H:%M:%S%z") - dt.now().astimezone()
                bus_eta_mins = round(bus_eta.total_seconds() / 60)
                # check bus type and load
                bus_info = f"{response_dict['Type'][service[bus]['Type']]} {response_dict['Load'][service[bus]['Load']]}"
                if bus_eta_mins >= 0:
                    results[service_no]["ETA"].append(bus_eta_mins)
                results[service_no]["Buses"].append([bus_eta_mins, bus_info])
            else:
                results[service_no]["Buses"].append([None, None, None])

    # sort by ETA
    sorted_results = sorted(results.items(), key=lambda x:x[1]["ETA"][0])
    return dict(sorted_results)

@st.cache_data(ttl=15, show_spinner=False)
def get_arrivals(bus_stop):
    try:
        response = requests.get(arrival_url+bus_stop, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        results2 = read_response(data)
        last_update = dt.now()
    
        for service_no, details in results2.items():
            with st.expander(f"**{service_no}** in {details['ETA'][0]} mins"):
                for bus in details["Buses"]:
                    if bus[0] is None:
                        pass # add check if last service
                    elif bus[0] == 0:
                        st.markdown(f"Bus is here! {bus[1]}")
                    elif bus[0] < 0:
                        st.markdown("Oops, you just missed this bus.")
                    elif bus[0] > 0:
                        st.markdown(f"**{bus[0]}** mins. {bus[1]}")
        
        return last_update
    except requests.exceptions.HTTPError as e:
        print(e)
        st.error("Sorry, an error occurred. Please try again.")
    except requests.exceptions.JSONDecodeError as e:
        print(e)
        st.error("Sorry, an error occurred. Please try again.")

bus_stops = get_stops()

st.title("Where's My Bus? :bus:")
st.markdown("Stalk your bus, made possible by the [Land Transport Authority](https://datamall.lta.gov.sg/content/datamall/en.html) of Singapore.")
my_stop = st.text_input("Which bus stop?", max_chars=5, key="my_stop")
col1, col2 = st.columns([1, 5])
bus_stop_placeholder = st.empty()
results_placeholder = st.empty()

if my_stop:
    if my_stop.isdigit() and len(my_stop) == 5:
        if my_stop in bus_stops:
            bus_stop_placeholder.header(f"{bus_stops[my_stop]} ({my_stop})")
            with results_placeholder.container():
                last_update = get_arrivals(my_stop)
        else:
            st.error("Bus stop not found. Please try again.")
    else:
        st.error("Please provide a 5 digit bus stop code.")

with col1:
    refresh = st.button("Refresh", type="primary")
with col2:
    try:
        st.markdown(f"Last updated: {last_update.strftime('%d %b %Y, %H:%M:%S')}")
    except:
        st.markdown(f"Last updated: None")

if refresh and my_stop:
    with results_placeholder.container():
        get_arrivals(my_stop)