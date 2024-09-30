import requests
from datetime import datetime

API_KEY = 'VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'

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
        print(f"Response from {response.url}:\n")
        print(data)
    except Exception as e:
        print(f"Error making GET request to {url}: {e}")

def main():
    # First GET request
    url1 = 'https://api.resy.com/4/venue/calendar'
    params1 = {
        'venue_id': 69593,
        'num_seats': 4,
        'start_date': '2024-09-30',
        'end_date': '2025-09-30'
    }
    print("Making first GET request...")
    make_get_request(url1, params1)
    print("\n" + "="*80 + "\n")

    # Second GET request
    url2 = 'https://api.resy.com/4/find'
    params2 = {
        'lat': 0,
        'long': 0,
        'day': '2024-09-30',
        'party_size': 4,
        'venue_id': 69593
    }
    print("Making second GET request...")
    make_get_request(url2, params2)

if __name__ == '__main__':
    main()
