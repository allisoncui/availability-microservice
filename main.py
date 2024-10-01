import mysql.connector
import requests
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta
import time

# API key
API_KEY = 'VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'
auth = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9'


# Connect to the MySQL database
def connect_to_database():
    return mysql.connector.connect(
        host="availability-database.cb821k94flru.us-east-1.rds.amazonaws.com",
        user="root",
        password="dbuserdbuser",
        database="availability"
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
    """
    Fetches available reservation days for the given venue and party size.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')  # Fetch for 30 days ahead

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


# GUI class to interact with the user
class AvailabilityApp(tk.Tk):
    def __init__(self, cursor):
        super().__init__()
        self.cursor = cursor
        self.title("Restaurant Availability Checker")
        self.geometry("400x500")

        # Username input
        self.label = tk.Label(self, text="Enter your username:")
        self.label.pack(pady=10)
        self.username_entry = tk.Entry(self)
        self.username_entry.pack(pady=10)

        # Button to fetch the viewed restaurants
        self.fetch_button = tk.Button(self, text="Check Availability", command=self.check_availability)
        self.fetch_button.pack(pady=20)

        # Display results in a listbox
        self.result_label = tk.Label(self, text="Availability Results:")
        self.result_label.pack(pady=10)
        self.result_listbox = tk.Listbox(self, height=20, width=50)
        self.result_listbox.pack(pady=10)

    # Function to check restaurant availability
    def check_availability(self):
        username = self.username_entry.get()

        if not username:
            messagebox.showerror("Error", "Please enter a username")
            return

        # Check if the username exists and get user_id
        user_id = get_user_id(self.cursor, username)
        if not user_id:
            messagebox.showerror("Error", f"No user found with username {username}")
            return

        # Get the viewed restaurants for the user
        viewed_restaurants = get_viewed_restaurants(self.cursor, user_id)
        if not viewed_restaurants:
            messagebox.showinfo("Info", "No viewed restaurants found for this user")
            return

        # Clear previous results from the listbox
        self.result_listbox.delete(0, tk.END)

        # For each viewed restaurant, check availability using the API
        for restaurant_code, restaurant_name in viewed_restaurants:
            self.result_listbox.insert(tk.END, f"Checking availability for {restaurant_name}...")

            # Fetch available days first
            available_days_data = fetch_available_days(restaurant_code, 2)

            if available_days_data and 'scheduled' in available_days_data:
                available_days = [day['date'] for day in available_days_data['scheduled'] if
                                  day['inventory']['reservation'] == 'available']

                if available_days:
                    for day in available_days:
                        # Fetch available times for each day
                        available_slots = fetch_available_times(restaurant_code, 2, day)

                        # Debugging statement to print available_slots
                        print(f"Available slots for {restaurant_name} on {day}: {available_slots}")

                        if available_slots and 'results' in available_slots:
                            venues = available_slots['results'].get('venues', [])
                            if venues:
                                for venue in venues:
                                    slots = venue.get('slots', [])
                                    if slots:
                                        self.result_listbox.insert(tk.END,
                                                                   f"Available times for {restaurant_name} on {day}:")
                                        for slot in slots:
                                            start_time = slot.get('date', {}).get('start')
                                            if start_time:
                                                # Convert the time to a readable format
                                                reservation_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                                                formatted_time = reservation_time.strftime('%I:%M %p')
                                                self.result_listbox.insert(tk.END, f"  - {formatted_time}")
                                    else:
                                        self.result_listbox.insert(tk.END,
                                                                   f"No available slots for {restaurant_name} on {day}")
                            else:
                                self.result_listbox.insert(tk.END, f"No venues found for {restaurant_name} on {day}")
                        else:
                            self.result_listbox.insert(tk.END, f"No available slots for {restaurant_name} on {day}")
                else:
                    self.result_listbox.insert(tk.END, f"No available days found for {restaurant_name}")
            else:
                self.result_listbox.insert(tk.END, f"No available days found for {restaurant_name}")


# Main function to set up the database and launch the app
def main():
    # Connect to the database
    conn = connect_to_database()
    cursor = conn.cursor()

    # Create and run the app
    app = AvailabilityApp(cursor)
    app.mainloop()

    # Close the database connection
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
