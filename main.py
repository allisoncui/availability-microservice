from fastapi import FastAPI, BackgroundTasks, HTTPException, Response, status, Request
import mysql.connector
import requests
from datetime import datetime, timedelta

app = FastAPI()

# API key
API_KEY = 'VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'

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

# First request to get available days for a restaurant (venue)
def fetch_available_days(venue_id, num_seats):
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

# Second request to fetch available times for each available day
def fetch_available_times(venue_id, num_seats, day):
    url = 'https://api.resy.com/4/find'
    params = {
        'lat': 0,
        'long': 0,
        'day': day,
        'party_size': num_seats,
        'venue_id': venue_id
    }
    return make_get_request(url, params)

# Function to check restaurant availability for a user
def check_availability(cursor, username):
    user_id = get_user_id(cursor, username)
    if not user_id:
        print(f"No user found with username {username}")
        return {"error": "No user found"}

    viewed_restaurants = get_viewed_restaurants(cursor, user_id)
    if not viewed_restaurants:
        print(f"No viewed restaurants found for user {username}")
        return {"error": "No viewed restaurants found"}

    results = {}
    # For each viewed restaurant, check availability using the API
    for restaurant_code, restaurant_name in viewed_restaurants:
        available_days_data = fetch_available_days(restaurant_code, 2)
        if available_days_data and 'scheduled' in available_days_data:
            available_days = [
                day['date'] for day in available_days_data['scheduled']
                if day['inventory']['reservation'] == 'available'
            ]
            daily_availability = []
            for day in available_days:
                available_slots = fetch_available_times(restaurant_code, 2, day)
                if available_slots and 'results' in available_slots:
                    venues = available_slots['results'].get('venues', [])
                    for venue in venues:
                        slots = venue.get('slots', [])
                        daily_availability.extend(
                            slot.get('date', {}).get('start') for slot in slots if slot.get('date', {}).get('start')
                        )
            results[restaurant_name] = daily_availability if daily_availability else "No availability"
        else:
            results[restaurant_name] = "No available days"

    return results

# Background task for checking availability
def check_availability_task(username, request_id, callback_url=None):
    conn = connect_to_database()
    cursor = conn.cursor()
    
    # Run the availability check and store results
    results = check_availability(cursor, username)
    availability_results[request_id] = results
    task_status[request_id] = "complete"

    # If a callback URL is provided, post the result to it
    if callback_url:
        try:
            response = requests.post(callback_url, json={"status": "complete", "data": results})
            response.raise_for_status()
            print(f"Callback to {callback_url} successful.")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send callback: {e}")

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