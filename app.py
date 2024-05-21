import streamlit as st
import requests
from datetime import datetime, time
import pytz

## To do list
# Add search for bus stop by name

st.set_page_config(page_title="Where's My Bus", page_icon=":bus:")

arrival_url = "http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode="
stops_url = "http://datamall2.mytransport.sg/ltaodataservice/BusStops"
routes_url = "http://datamall2.mytransport.sg/ltaodataservice/BusRoutes"
train_alerts_url = "http://datamall2.mytransport.sg/ltaodataservice/TrainServiceAlerts"
headers = {
    "AccountKey": st.secrets["lta_token"]
}
TIMEOUT = (5, 15)
sg_timezone = pytz.timezone("Asia/Singapore")

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
            response = requests.get(stops_url+"?$skip="+str(skip_operator), headers=headers, timeout=TIMEOUT)
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

@st.cache_data(ttl=2_630_000, show_spinner="Hang in there...")
def get_routes():
    skip_operator = 0
    bus_routes = {}
    
    while True:
        try:
            response = requests.get(routes_url+"?$skip="+str(skip_operator), headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if data["value"]:
                for stop in data["value"]:
                    if bus_routes.get(stop["ServiceNo"]) is None:
                        bus_routes[stop["ServiceNo"]] = {}
                    if bus_routes[stop["ServiceNo"]].get(stop["BusStopCode"]) is None:
                        bus_routes[stop["ServiceNo"]][stop["BusStopCode"]] = {}
                    bus_routes[stop["ServiceNo"]][stop["BusStopCode"]] = {
                                                                    "Weekday": {"first": stop["WD_FirstBus"], "last": stop["WD_LastBus"]},
                                                                    "Sat": {"first": stop["SAT_FirstBus"], "last": stop["SAT_LastBus"]},
                                                                    "Sun": {"first": stop["SUN_FirstBus"], "last": stop["SUN_LastBus"]},                                                            
                                                                        }
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

    print(f"{len(bus_routes.keys())} routes retrieved.")
    return bus_routes

def check_trains():
    try:
        response = requests.get(train_alerts_url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        affected_lines = []

        print(data["value"])

        if data["value"]["Status"] == 2:
            for segment in data["value"]["AffectedSegments"]:
                affected_lines.append(segment["Line"])

        if affected_lines:
            print(f"Train services disrupted along {','.join(affected_lines)}.")
            train_alerts_placeholder.warning(f"Train services disrupted along {','.join(affected_lines)}.")
        else:
            print("Train services operating normally.")
    except requests.exceptions.HTTPError as e:
        print(e)
        st.error("Sorry, an error occurred. Please try again.")
    except requests.exceptions.JSONDecodeError as e:
        print(e)
        st.error("Sorry, an error occurred. Please try again.")

# retrieve and store data from LTA DataMall
bus_stops = get_stops()
bus_routes = get_routes()

def check_operation(stop, service):

    def convert_time(time):
        return datetime.strptime(time, "%H%M").time()

    current_time = datetime.now()
    day_of_week = current_time.weekday()
    
    schedule = bus_routes[service][stop]["Weekday"]
    if day_of_week == 5:
        schedule = bus_routes[service][stop]["Sat"]
    elif day_of_week == 6:
        schedule = bus_routes[service][stop]["Sun"]
    
    if current_time.time() < convert_time(schedule["first"]): # after midnight
        if schedule["last"][0] == "0":
            return current_time.time() < convert_time(schedule["last"])
        else:
            return False
    else: # normal timings
        return convert_time(schedule["first"]) <= current_time.time() <= convert_time(schedule["last"])
    

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
                bus_eta = datetime.strptime(service[bus]['EstimatedArrival'], "%Y-%m-%dT%H:%M:%S%z") - datetime.now().astimezone()
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

        results = read_response(data)
        last_update = datetime.now(sg_timezone)
    
        for service_no, details in results.items():
            if details['ETA'][0] is not None:
                next_arrival = f"in {details['ETA'][0]} mins" if details['ETA'][0] > 0 else "is arriving"
                with st.expander(f"**{service_no}** {next_arrival}"):
                    for bus in details["Buses"]:
                        if bus[0] is None:
                            pass
                        elif bus[0] == 0:
                            st.markdown(f"Bus is arriving! {bus[1]}")
                        elif bus[0] < 0:
                            st.markdown("Oops, you just missed this bus.")
                        elif bus[0] > 0:
                            st.markdown(f"**{bus[0]}** mins. {bus[1]}")
            else: # check if bus is in service
                if check_operation(bus_stop, service_no):
                    st.expander(f"**{service_no}** No estimate available")
                else:
                    st.expander(f"**{service_no}** Not in operation")
        
        return last_update
    
    except requests.exceptions.HTTPError as e:
        print(e)
        st.error("Sorry, an error occurred. Please try again.")
    except requests.exceptions.JSONDecodeError as e:
        print(e)
        st.error("Sorry, an error occurred. Please try again.")

st.title("Where's My Bus? :bus:")
st.markdown("Stalk your bus, made possible by the [Land Transport Authority](https://datamall.lta.gov.sg/content/datamall/en.html) of Singapore.")
my_stop = st.text_input("Enter Bus Stop number:", max_chars=5, key="my_stop")
col1, col2 = st.columns([1, 6])
train_alerts_placeholder = st.empty()
bus_stop_placeholder = st.empty()
results_placeholder = st.empty()

check_trains()

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
        st.markdown(f"Last updated: {last_update.strftime('%H:%M, %d %b')}")
    except:
        st.markdown(f"Last updated: None")

if refresh and my_stop:
    with results_placeholder.container():
        get_arrivals(my_stop)
