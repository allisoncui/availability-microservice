from fastapi import FastAPI, BackgroundTasks, HTTPException, Response, status, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import mysql.connector
import requests
from datetime import datetime, timedelta
import time
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Constants for external microservices
USER_MICROSERVICE_URL = "http://52.23.233.221:8000"
RESTAURANT_MICROSERVICE_URL = "http://34.207.95.163:8000"


# API key
API_KEY = 'VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = int(os.getenv('DB_PORT', 3306))

# In-memory store for results and status tracking
availability_results = {}
task_status = {}

# Connect to the MySQL database
def connect_to_database():
    return mysql.connector.connect(
        host='availability-database.cb821k94flru.us-east-1.rds.amazonaws.com',
        user='root',
        password='dbuserdbuser',
        database='availability',
    )

# Function to search for the username in the Profile table and retrieve the user_id
def get_user_id(cursor, username):
    cursor.execute("SELECT user_id FROM Profile WHERE username = %s", (username,))
    result = cursor.fetchone()
    return result[0] if result else None

# Function to get the viewed restaurants of a user based on user_id
def get_viewed_restaurants(cursor, user_id):
    cursor.execute("""
        SELECT r.restaurant_code, r.name
        FROM Viewed_Restaurants vr
        JOIN Restaurant r ON vr.restaurant_code = r.restaurant_code
        WHERE vr.user_id = %s
    """, (user_id,))
    return cursor.fetchall()

# Function to make API requests
def make_get_request(url, params):
    headers = {
        'Authorization': f'ResyAPI api_key="{API_KEY}"',
        'Origin': 'https://resy.com',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/94.0.4606.81 Safari/537.36'
        ),
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()  # Return the JSON data
    except Exception as e:
        print(f"Error making GET request to {url}: {e}")
        return None


# Adjust `fetch_available_days` to look for availability for 2 people
def fetch_available_days(venue_id, num_seats=2):
    today = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    url = 'https://api.resy.com/4/venue/calendar'
    params = {
        'venue_id': venue_id,
        'num_seats': num_seats,
        'start_date': today,
        'end_date': end_date
    }
    return make_get_request(url, params)


# Adjust `fetch_available_times` to search for availability for 2 people
def fetch_available_times(venue_id, num_seats=2, day=None):
    url = 'https://api.resy.com/4/find'
    params = {
        'lat': 0,
        'long': 0,
        'day': day,
        'party_size': num_seats,
        'venue_id': venue_id
    }
    return make_get_request(url, params)


# Update `check_availability` to stop as soon as the first available reservation is found
def check_availability(cursor, username):
    user_id = get_user_id(cursor, username)
    if not user_id:
        print(f"No user found with username {username}")
        return {"error": "No user found"}

    viewed_restaurants = get_viewed_restaurants(cursor, user_id)
    if not viewed_restaurants:
        print(f"No viewed restaurants found for user {username}")
        return {"error": "No viewed restaurants found"}

    for restaurant_code, restaurant_name in viewed_restaurants:
        available_days_data = fetch_available_days(restaurant_code, 2)
        if available_days_data and 'scheduled' in available_days_data:
            for day in available_days_data['scheduled']:
                if day['inventory']['reservation'] == 'available':
                    available_slots = fetch_available_times(restaurant_code, 2, day['date'])
                    if available_slots and 'results' in available_slots:
                        venues = available_slots['results'].get('venues', [])
                        for venue in venues:
                            for slot in venue.get('slots', []):
                                start_time = slot.get('date', {}).get('start')
                                if start_time:
                                    print(
                                        f"First available reservation for {restaurant_name} on {day['date']} at {start_time}")
                                    return {restaurant_name: start_time}  # Return the first available reservation
                                time.sleep(10)
    return {"error": "No available reservations found"}  # If no reservation is found


# Background task for checking availability for the first available reservation
def check_availability_task(username, request_id, callback_url=None):
    conn = connect_to_database()
    cursor = conn.cursor()

    # Run the availability check and store the first available result
    results = check_availability(cursor, username)

    # Log storing availability results
    logger.info(f"Storing availability for request_id: {request_id}, results: {results}")

    if results:
        for restaurant_code, availability_data in results.items():
            # Store the first available reservation with restaurant_code as the key
            availability_results[restaurant_code] = {
                "restaurant": restaurant_code,
                "date": availability_data.split(" ")[0],  # Extract date
                "time": availability_data.split(" ")[1]   # Extract time
            }

            # Log that availability has been stored
            logger.info(f"Stored first available reservation for {restaurant_code}: {availability_results[restaurant_code]}")

    task_status[request_id] = "complete"

    # Log callback attempt
    if callback_url:
        try:
            response = requests.post(callback_url, json={"status": "complete", "data": results})
            response.raise_for_status()
            logger.info(f"Callback to {callback_url} successful.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send callback: {e}")

    cursor.close()
    conn.close()

# Endpoint to initiate availability check with optional callback
@app.post("/availability/{username}", status_code=status.HTTP_202_ACCEPTED)
async def initiate_availability_check(username: str, request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    callback_url = payload.get("callback_url")

    # Generate a unique request ID
    request_id = f"{username}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Start the background task
    background_tasks.add_task(check_availability_task, username, request_id, callback_url)
    task_status[request_id] = "processing"

    # Return 202 Accepted with a link to check the status
    return Response(
        content=f"Request accepted. Check status at /availability/status/{request_id}",
        headers={"Location": f"/availability/status/{request_id}"},
        status_code=status.HTTP_202_ACCEPTED
    )

# Endpoint to check status (polling)
@app.get("/availability/status/{request_id}")
async def check_status(request_id: str):
    if request_id in task_status:
        status = task_status[request_id]
        if status == "complete":
            return {"status": "complete", "data": availability_results[request_id]}
        else:
            return {"status": "processing", "data": None}
    else:
        raise HTTPException(status_code=404, detail="Request ID not found")
    
@app.get("/availability/{restaurant_code}")
async def get_availability(restaurant_code: str):
    """
    Endpoint to get the first available reservation for a given restaurant by its code.
    """
    # Check if the reservation for the restaurant code exists in availability_results
    availability_data = availability_results.get(restaurant_code)

    if availability_data:
        logger.info(f"Returning availability for {restaurant_code}: {availability_data}")
        return availability_data
    else:
        logger.warning(f"No availability found for restaurant_code: {restaurant_code}")
        raise HTTPException(status_code=404, detail="No availability found for this restaurant")