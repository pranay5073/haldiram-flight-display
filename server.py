import os
import requests
import json
from datetime import datetime, timedelta
import logging
import time
import random
import pytz
from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO
from bs4 import BeautifulSoup
import concurrent.futures
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the current directory is in the Python path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_url_path='')

class FlightRadarScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.flightradar24.com',
            'Referer': 'https://www.flightradar24.com/',
        })
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.sort_by = 'time'
        self.base_url = "https://www.nagpurairport.com"
        self.arrival_url = f"{self.base_url}/flight-information/arrivals"
        self.departure_url = f"{self.base_url}/flight-information/departures"

    def _format_time(self, time_str):
        """Convert time string to proper format"""
        try:
            # Handle various time formats
            if isinstance(time_str, (int, float)):
                return datetime.fromtimestamp(time_str, self.timezone).strftime("%H:%M")
            
            # Clean the time string
            time_str = time_str.strip().upper()
            if not time_str or time_str == 'NIL':
                return 'N/A'

            # Try parsing common formats
            formats = ["%H:%M", "%I:%M %p", "%H%M"]
            for fmt in formats:
                try:
                    return datetime.strptime(time_str, fmt).strftime("%H:%M")
                except ValueError:
                    continue

            return time_str
        except Exception as e:
            logger.error(f"Error formatting time {time_str}: {str(e)}")
            return 'N/A'

    def _format_flight_number(self, flight_num):
        """Format flight number properly"""
        if not flight_num:
            return 'N/A'
        
        # Remove spaces and special characters
        flight_num = re.sub(r'[^\w\s]', '', flight_num).strip()
        
        # Common airline codes mapping
        airline_codes = {
            'AI': 'Air India',
            '6E': 'IndiGo',
            'UK': 'Vistara',
            'SG': 'SpiceJet',
            'G8': 'GoAir'
        }
        
        # Try to identify airline code
        for code in airline_codes:
            if flight_num.startswith(code):
                return flight_num
        
        return flight_num

    def _get_flight_status(self, scheduled_time):
        """Determine flight status based on scheduled time"""
        try:
            if not scheduled_time or scheduled_time == 'N/A':
                return 'Unknown'

            scheduled_dt = datetime.strptime(scheduled_time, "%H:%M")
            current_time = datetime.now(self.timezone).replace(tzinfo=None)
            
            # Set scheduled time to today
            scheduled_dt = scheduled_dt.replace(
                year=current_time.year,
                month=current_time.month,
                day=current_time.day
            )

            time_diff = (scheduled_dt - current_time).total_seconds() / 60

            if abs(time_diff) <= 15:
                return 'On Time'
            elif time_diff < -15:
                return 'Delayed'
            else:
                return 'Scheduled'

        except Exception as e:
            logger.error(f"Error determining status: {str(e)}")
            return 'Unknown'

    def _scrape_flights(self, url):
        """Scrape flight information from the given URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            flights = []
            flight_tables = soup.find_all('table', class_='flight-table')
            
            for table in flight_tables:
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        flight_info = {
                            'flight': self._format_flight_number(cols[0].text.strip()),
                            'destination': cols[1].text.strip(),
                            'time': self._format_time(cols[2].text.strip()),
                            'status': 'Scheduled'  # Default status
                        }
                        
                        # Add status based on scheduled time
                        flight_info['status'] = self._get_flight_status(flight_info['time'])
                        
                        flights.append(flight_info)
            
            return flights
        
        except Exception as e:
            logger.error(f"Error scraping flights from {url}: {str(e)}")
            return []

    def sort_flights(self, flights, sort_by=None):
        """Sort flights based on specified criteria"""
        if sort_by:
            self.sort_by = sort_by

        def get_sort_key(flight):
            if self.sort_by == 'time':
                time_str = flight.get('time', '00:00')
                try:
                    if time_str == 'N/A':
                        return datetime.max
                    return datetime.strptime(time_str, "%H:%M")
                except:
                    return datetime.max
            elif self.sort_by == 'flight':
                return flight.get('flight', '')
            elif self.sort_by == 'destination':
                return flight.get('destination', '')
            return 0

        return sorted(flights, key=get_sort_key)

    def get_flights(self, sort_by=None):
        """Get and sort flight data from both arrivals and departures"""
        try:
            # Scrape both arrivals and departures
            arrivals = self._scrape_flights(self.arrival_url)
            departures = self._scrape_flights(self.departure_url)
            
            # Combine and sort flights
            all_flights = arrivals + departures
            
            # If no flights found, use sample data
            if not all_flights:
                all_flights = [
                    {"flight": "6E 6233", "destination": "New Delhi", "time": "09:30", "status": "On Time"},
                    {"flight": "AI 628", "destination": "Mumbai", "time": "10:15", "status": "Delayed"},
                    {"flight": "SG 2451", "destination": "Bangalore", "time": "11:00", "status": "On Time"},
                    {"flight": "6E 7124", "destination": "Hyderabad", "time": "12:30", "status": "On Time"},
                    {"flight": "AI 469", "destination": "Chennai", "time": "14:45", "status": "On Time"}
                ]
            
            # Sort flights if requested
            if sort_by:
                all_flights = self.sort_flights(all_flights, sort_by)
            
            return all_flights

        except Exception as e:
            logger.error(f"Error getting flight data: {str(e)}")
            return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_flights')
def get_flights():
    try:
        sort_by = request.args.get('sort_by', 'time')
        scraper = FlightRadarScraper()
        flights = scraper.get_flights(sort_by)
        return jsonify({"success": True, "flights": flights})
    except Exception as e:
        logger.error(f"Error in get_flights route: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch flight data",
            "details": str(e)
        }), 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
