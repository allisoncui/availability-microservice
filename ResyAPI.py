import mysql.connector
import requests
import time
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

# API key
API_KEY = 'VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'

# Database connection
def connect_to_database():
    return mysql.connector.connect(
        host="availability-database.cb821k94flru.us-east-1.rds.amazonaws.com",
        user="root",
        password="dbuserdbuser",
        database="availability"
    )

# Fetch user_id from username
def get_user_id(cursor, username):
    cursor.execute("SELECT user_id FROM Profile WHERE username = %s", (username,))
    result = cursor.fetchone()
    return result[0] if result else None

# Fetch viewed restaurants for a user
def get_viewed_restaurants(cursor, user_id):
    cursor.execute("""
        SELECT r.restaurant_code, r.name
        FROM Viewed_Restaurants vr
        JOIN Restaurant r ON vr.restaurant_code = r.restaurant_code
        WHERE vr.user_id = %s
    """, (user_id,))
    return cursor.fetchall()

# Function to make GET requests
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

# Fetch available days for a restaurant (venue)
def fetch_calendar_data(venue_id, num_seats, start_date, end_date):
    url = 'https://api.resy.com/4/venue/calendar'
    params = {
        'venue_id': venue_id,
        'num_seats': num_seats,
        'start_date': start_date,
        'end_date': end_date
    }
    return make_get_request(url, params)

# Fetch available times for a restaurant (venue)
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

        # Clear previous results
        self.result_listbox.delete(0, tk.END)

        # Search for availability for each viewed restaurant
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now().replace(month=datetime.now().month + 1)).strftime('%Y-%m-%d')

        for restaurant_code, restaurant_name in viewed_restaurants:
            found_availability = False
            self.result_listbox.insert(tk.END, f"\nChecking availability for {restaurant_name}...")

            for party_size in range(2, 5):
                # Fetch calendar data for the restaurant
                calendar_data = fetch_calendar_data(restaurant_code, party_size, start_date, end_date)

                if calendar_data:
                    scheduled = calendar_data.get('scheduled', [])
                    available_days = [day['date'] for day in scheduled if day['inventory']['reservation'] == 'available']

                    if not available_days:
                        self.result_listbox.insert(tk.END, f"No available days for party size {party_size} at {restaurant_name}")
                        continue

                    for day in available_days:
                        find_data = fetch_available_times(restaurant_code, party_size, day)
                        if find_data:
                            venues = find_data.get('results', {}).get('venues', [])
                            if venues:
                                slots = venues[0].get('slots', [])
                                if slots:
                                    # Display the first available reservation and break out of the loop
                                    start_time = slots[0].get('date', {}).get('start')
                                    if start_time:
                                        reservation_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                                        formatted_time = reservation_time.strftime('%I:%M %p')
                                        self.result_listbox.insert(tk.END, f"First available reservation for {restaurant_name}: Date: {day}, Time: {formatted_time}, Party Size: {party_size}")
                                        found_availability = True
                                        break  # Exit loop after first available reservation
                        if found_availability:
                            break  # Exit if a reservation has been found for this restaurant and party size
                if found_availability:
                    break
            if not found_availability:
                self.result_listbox.insert(tk.END, f"No available reservations found for {restaurant_name}")
            time.sleep(5)

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
