import os
from dotenv import load_dotenv
import mysql.connector
import requests
from datetime import datetime, timedelta

load_dotenv()

API_KEY = os.getenv('API_KEY')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = int(os.getenv('DB_PORT', 3306))

# Connect to the MySQL database
def connect_to_database():
    return mysql.connector.connect(
         host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
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
        return

    viewed_restaurants = get_viewed_restaurants(cursor, user_id)
    if not viewed_restaurants:
        print(f"No viewed restaurants found for user {username}")
        return

    # For each viewed restaurant, check availability using the API
    for restaurant_code, restaurant_name in viewed_restaurants:
        print(f"\nChecking availability for {restaurant_name}...")

        # Fetch available days first
        available_days_data = fetch_available_days(restaurant_code, 2)
        if available_days_data and 'scheduled' in available_days_data:
            available_days = [day['date'] for day in available_days_data['scheduled'] if day['inventory']['reservation'] == 'available']
            if available_days:
                for day in available_days:
                    available_slots = fetch_available_times(restaurant_code, 2, day)
                    if available_slots and 'results' in available_slots:
                        venues = available_slots['results'].get('venues', [])
                        if venues:
                            for venue in venues:
                                slots = venue.get('slots', [])
                                if slots:
                                    print(f"Available times for {restaurant_name} on {day}:")
                                    for slot in slots:
                                        start_time = slot.get('date', {}).get('start')
                                        if start_time:
                                            reservation_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                                            formatted_time = reservation_time.strftime('%I:%M %p')
                                            print(f"  - {formatted_time}")
                                else:
                                    print(f"No available slots for {restaurant_name} on {day}")
                        else:
                            print(f"No venues found for {restaurant_name} on {day}")
                    else:
                        print(f"No available slots for {restaurant_name} on {day}")
            else:
                print(f"No available days for {restaurant_name}")
        else:
            print(f"No available days for {restaurant_name}")

# Main function to set up the database and launch the availability checker
def main():
    conn = connect_to_database()
    cursor = conn.cursor()

    # Prompt user for username
    username = input("Enter your username: ")
    check_availability(cursor, username)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
