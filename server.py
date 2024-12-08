import os
import requests
import json
from datetime import datetime
import logging
import time
import random
import pytz
from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO

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
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.flightradar24.com',
            'Referer': 'https://www.flightradar24.com/',
        })
        # Set timezone to India
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.sort_by = 'time'  # Default sort method

    def _format_time(self, timestamp):
        """Convert Unix timestamp to readable format in IST"""
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp, self.timezone)
            return dt.strftime("%H:%M")
        return timestamp

    def _format_flight_number(self, flight_num):
        """Format flight number properly"""
        return flight_num.replace(' ', '') if flight_num else 'N/A'

    def sort_flights(self, flights, sort_by=None):
        """Sort flights based on specified criteria"""
        if sort_by:
            self.sort_by = sort_by

        def get_sort_key(flight):
            if self.sort_by == 'time':
                # Convert time string to datetime for proper sorting
                time_str = flight.get('time', '00:00')
                try:
                    return datetime.strptime(time_str, "%H:%M")
                except:
                    return datetime.strptime('00:00', "%H:%M")
            elif self.sort_by == 'flight':
                return flight.get('flight', '')
            elif self.sort_by == 'destination':
                return flight.get('destination', '')
            return 0

        return sorted(flights, key=get_sort_key)

    def get_flights(self, sort_by=None):
        """Get and sort flight data"""
        try:
            # Get both airport schedule and real-time flight data
            airport_data = self._get_airport_data()
            flights_data = self._get_flights_data()
            
            # Process and combine the data
            flights = self._process_flights(airport_data, flights_data)
            
            # Sort the flights if requested
            if sort_by:
                flights = self.sort_flights(flights, sort_by)
            
            return flights

        except Exception as e:
            logger.error(f"Error getting flight data: {str(e)}")
            return []

    def _get_airport_data(self):
        """Get airport schedule data"""
        try:
            url = "https://www.nagpurairport.com/flight-information/flight-schedule"
            response = self.session.get(url)
            return response.text if response.ok else ""
        except Exception as e:
            logger.error(f"Error fetching airport data: {str(e)}")
            return ""

    def _get_flights_data(self):
        """Get real-time flight data"""
        try:
            url = "https://data-cloud.flightradar24.com/zones/fcgi/feed.js"
            params = {
                'bounds': '21.09,21.22,78.96,79.09',  # Nagpur coordinates
                'faa': '1',
                'satellite': '1',
                'mlat': '1',
                'flarm': '1',
                'adsb': '1',
                'gnd': '1',
                'air': '1',
                'vehicles': '1',
                'estimated': '1',
                'gliders': '1',
                'stats': '1'
            }
            response = self.session.get(url, params=params)
            return response.json() if response.ok else {}
        except Exception as e:
            logger.error(f"Error fetching flight data: {str(e)}")
            return {}

    def _process_flights(self, airport_data, flights_data):
        """Process and combine flight data"""
        flights = []
        # Add some sample flight data
        sample_flights = [
            {"flight": "6E 6233", "destination": "New Delhi", "time": "09:30", "status": "On Time"},
            {"flight": "AI 628", "destination": "Mumbai", "time": "10:15", "status": "Delayed"},
            {"flight": "SG 2451", "destination": "Bangalore", "time": "11:00", "status": "On Time"},
            {"flight": "6E 7124", "destination": "Hyderabad", "time": "12:30", "status": "On Time"},
            {"flight": "AI 469", "destination": "Chennai", "time": "14:45", "status": "On Time"}
        ]
        flights.extend(sample_flights)
        return flights

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

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
