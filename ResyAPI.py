import requests
import time
from datetime import datetime

# List of restaurants to monitor
RESTAURANTS = [
    {'id': 1543, 'name': 'Jeju Noodle Bar', 'city': 'ny', 'urlName': 'jeju-noodle-bar'},
    {'id': 65452, 'name': 'Tatiana', 'city': 'new-york-ny', 'urlName': 'tatiana'}
]

# Reservation details
PARTY_SIZE = 6
START_DATE = '2024-09-01'
END_DATE = '2025-09-01'

# API key and Discord webhook URL
API_KEY = 'VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'
auth = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9'
def make_get_request(url, params):
    """
    Makes a GET request to the specified URL with the given parameters and headers.
    """
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
        data = response.json()
        return data  # Return the JSON data
    except Exception as e:
        print(f"Error making GET request to {url}: {e}")
        return None

def fetch_calendar_data(venue_id, num_seats, start_date, end_date):
    """
    Fetches the calendar data for the specified venue and date range.
    """
    url = 'https://api.resy.com/4/venue/calendar'
    params = {
        'venue_id': venue_id,
        'num_seats': num_seats,
        'start_date': start_date,
        'end_date': end_date
    }
    return make_get_request(url, params)

def fetch_available_times(venue_id, num_seats, day):
    """
    Fetches available reservation times for a specific day.
    """
    url = 'https://api.resy.com/4/find'
    params = {
        'lat': 0,
        'long': 0,
        'day': day,
        'party_size': num_seats,
        'venue_id': venue_id
    }
    return make_get_request(url, params)

def parse_and_display_availabilities(venue_id, calendar_data, party_sizes):
    """
    Parses the calendar data and fetches available times for each day and party size.
    """
    scheduled = calendar_data.get('scheduled', [])
    available_days = [day['date'] for day in scheduled if day['inventory']['reservation'] == 'available']

    if not available_days:
        print("No days with available reservations found.")
        return

    for day in available_days:
        print(f"\nDate: {day}")
        for num_seats in party_sizes:
            # Fetch available times for the day and party size
            find_data = fetch_available_times(venue_id, num_seats, day)
            if find_data:
                # Extract restaurant name and available slots
                venues = find_data.get('results', {}).get('venues', [])
                if not venues:
                    continue  # No venue information for this party size

                venue = venues[0].get('venue', {})
                venue_name = venue.get('name', 'Unknown Restaurant')

                slots = venues[0].get('slots', [])
                if not slots:
                    continue  # No available reservations for this party size

                print(f"\nParty Size: {num_seats}")
                print("Available Reservation Times:")
                for slot in slots:
                    start_time = slot.get('date', {}).get('start')
                    if start_time:
                        # Convert the time to a readable format
                        reservation_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                        formatted_time = reservation_time.strftime('%I:%M %p')
                        print(formatted_time)
            else:
                print(f"Failed to retrieve available times for {day} and party size {num_seats}.")

def main():
    # Venue and reservation details
    venue_id = 65452  # Replace with your venue ID
    party_sizes = [2, 3, 4]  # Party sizes to check
    start_date = '2024-09-30'
    end_date = '2024-10-31'  # Shortened date range for example

    for num_seats in party_sizes:
        # Fetch calendar data for each party size
        calendar_data = fetch_calendar_data(venue_id, num_seats, start_date, end_date)

        # Parse and display availabilities
        if calendar_data:
            parse_and_display_availabilities(venue_id, calendar_data, [num_seats])
        else:
            print(f"Failed to retrieve calendar data for party size {num_seats}.")

if __name__ == '__main__':
    main()