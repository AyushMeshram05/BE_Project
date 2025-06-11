import os
import markdown
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import pickle
import numpy as np
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from werkzeug.security import generate_password_hash, check_password_hash
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2 import id_token
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv
import random
from bson import ObjectId
import google.generativeai as genai

load_dotenv()  # Load environment variables from .env

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Add your Gemini API key to .env

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Flask session secret key

# Load the main dataframe
df = pd.read_excel("merged_data_reviews_about.xlsx")

# Debug: Print columns of df
print("Columns in df before merge:", df.columns)

# Check if 'rating' column exists in df
if 'rating' in df.columns:
    df['rating'] = df['rating'].fillna('No rating available')
else:
    print("Warning: 'rating' column not found in the DataFrame.")
    df['rating'] = 'No rating available'

# Load the additional dataframe with photos
additional_df = pd.read_excel("outscraper_first.xlsx")

# Merge only the 'photo' column from additional_df
df = pd.merge(df, additional_df[['name', 'photo']], on='name', how='left')

# Debug: Print columns of df after merge
print("Columns in df after merge:", df.columns)

# Add coordinates to the dataframe if they don't exist
if 'latitude' not in df.columns or 'longitude' not in df.columns:
    # Generate random coordinates for India (for demonstration)
    # In a real app, you would geocode the addresses
    df['latitude'] = np.random.uniform(8.0, 37.0, len(df))  # Latitude range for India
    df['longitude'] = np.random.uniform(68.0, 97.0, len(df))  # Longitude range for India

# MongoDB Connection
MONGO_URI = "mongodb+srv://jatin_bihari:jatin123@cluster0.duslu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
try:
    client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    client.admin.command('ping')
    print("✅ MongoDB connected successfully!")
    db = client["sample_mflix"]
    users_collection = db["users"]
except Exception as e:
    print("❌ MongoDB Connection Failed:", e)
    db = None

# Google OAuth Setup
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Development Only

@app.route('/')
def index():
    return render_template('pindex.html')

# Sign Up (Register)
@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    name, email, password = data.get("name"), data.get("email"), data.get("password")
    latitude, longitude = data.get("latitude"), data.get("longitude")

    if users_collection.find_one({"email": email}):
        return jsonify({"success": False, "error": "Email already exists!"}), 400

    users_collection.insert_one({
        "name": name,
        "email": email,
        "password": generate_password_hash(password),
        "latitude": latitude,
        "longitude": longitude
    })
    return jsonify({"success": True, "message": "User registered successfully!"})

# Sign In
@app.route('/signin', methods=['POST'])
def signin():
    data = request.form
    email, password = data.get("email"), data.get("password")
    user = users_collection.find_one({"email": email})

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"success": False, "error": "Invalid email or password!"}), 400

    session['user'] = {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}
    return jsonify({"success": True, "message": "Login successful!"})

# Logout
@app.route('/signout')
def signout():
    session.clear()
    return redirect(url_for('index'))

# Google Login
@app.route('/google-login', methods=['POST'])
def google_login_verify():
    try:
        token = request.json['token']
        id_info = id_token.verify_oauth2_token(token, Request(), GOOGLE_CLIENT_ID)

        user_info = {'id': id_info['sub'], 'name': id_info.get('name'), 'email': id_info.get('email'), 'picture': id_info.get('picture')}
        user = users_collection.find_one({"email": user_info['email']})
        if not user:
            # Insert new Google user
            user_info["google_id"] = user_info["id"]
            users_collection.insert_one(user_info)
        else:
            # Optionally update the document with Google ID if not already set
            if "google_id" not in user:
                users_collection.update_one({"_id": user["_id"]}, {"$set": {"google_id": user_info["id"]}})

        session['google_credentials'] = user_info
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/get_user_location')
def get_user_location():
    if 'user' in session:
        user_id = session['user']['id']
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            return jsonify({
                "latitude": user.get("latitude"),
                "longitude": user.get("longitude")
            })
    return jsonify({"error": "User not found"}), 404

categories = {
    "Accessibility": [
        "Wheelchair-accessible car park", "Wheelchair-accessible entrance",
        "Wheelchair-accessible seating", "Wheelchair-accessible toilet",
        "Assistive hearing loop", "Braille menu", "Identifies as women-owned",
        "Gender-neutral toilets"
    ],
    "Facilities": [
        "Toilets", "Public restroom", "Parking", "Free parking", "Free parking lot", "Paid parking lot",
        "Paid street parking", "Free street parking", "Valet parking", "Family friendly", "LGBTQ+ friendly",
        "Dog park", "Pool", "Spa", "On-site services"
    ],
    "Dining Options": [
        "Restaurant", "Outdoor seating", "Fireplace", "All you can eat",
        "Lunch", "Dinner", "Dessert", "Dine-in", "Takeaway",
        "Drive-through", "Delivery", "In-store pick-up", "Same-day delivery",
        "Small plates", "Catering", "Seating", "In-store shopping", "Wi-Fi"
    ],
    "Payments": [
        "Google Pay", "Cheques", "Debit cards", "Mobile Wallets",
        "Credit cards", "Cash only", "Meal coupons", "Pluxee"
    ],
    "Recreation": [
        "Live performances", "Live music", "Sport", "Birdwatching",
        "Hiking", "Jogging", "Trail difficulty", "Walking",
        "Dogs allowed outside"
    ],
    "Food Preferences": [
        "Vegan options", "Vegetarian options", "Vegetarian options only",
        "Halal food", "Organic dishes", "Salad bar", "Cuisine", "Late-night food",
        "Dishes"
    ],
    "Beverages": [
        "Beer", "Cocktails", "Spirits", "Wine", "Coffee",
        "Happy-hour drinks", "Happy-hour food", "Alcohol", "Bar on site"
    ],
    "Reservations": [
        "Accepts reservations", "Reservations required", "Private dining room"
    ],
    "Child Friendly": [
        "Good for kids", "Good for kids birthday", "Kid-friendly hikes",
        "Slides", "Swings", "Playground", "Kids' menu", "High chairs"
    ],
    "Extras": [
        "Casual", "Romantic", "Groups", "Cozy", "Brunch", "Breakfast",
        "Picnic tables", "Camping fee", "Counter service", "Star rating"
    ],
    "Delivery & Pickup": [
        "Kerbside pickup", "No-contact delivery"
    ],
    "Check-in & Check-out": [
        "Check-in time", "Check-out time"
    ]
}

from datetime import datetime
import json

def is_place_open(working_hours_json):
    try:
        if not working_hours_json or not isinstance(working_hours_json, str):
            return False, "Hours not available"

        working_hours = json.loads(working_hours_json)

        now = datetime.now()
        current_day = now.strftime("%A")
        current_time = now.time()

        if current_day not in working_hours:
            return False, "Hours not available"

        today_hours = working_hours[current_day]

        if today_hours == "Closed":
            return False, f"Closed today ({current_day})"
        if today_hours == "Open 24 hours":
            return True, "Open 24 hours"

        if "-" in today_hours:
            opening_time_str, closing_time_str = today_hours.split("-")
            opening_time = parse_time_to_24h(opening_time_str)
            closing_time = parse_time_to_24h(closing_time_str)

            if opening_time < closing_time:
                is_open = opening_time <= current_time <= closing_time
            else:
                # Over-midnight case
                is_open = current_time >= opening_time or current_time <= closing_time

            if is_open:
                return True, f"Open now: {today_hours}"
            else:
                return False, f"Closed now - Today's hours: {today_hours}"
        else:
            return False, f"Hours today: {today_hours}"

    except Exception as e:
        return False, "Hours not available"

def parse_time_to_24h(time_str):
    time_str = time_str.strip().lower()
    try:
        if "am" in time_str or "pm" in time_str:
            if ":" in time_str:
                return datetime.strptime(time_str, "%I:%M%p").time()
            return datetime.strptime(time_str, "%I%p").time()
        else:
            return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None

def recommend_places(place_type=None, borough=None, facets=None):
    """
    Recommend places based on type, borough, and facets.
    Now includes whether the place is currently open.
    """
    recommendations = df.copy()

    if place_type:
        recommendations = recommendations[recommendations["type"].str.contains(place_type, case=False, na=False)]

    if borough:
        recommendations = recommendations[recommendations["borough"].str.contains(borough, case=False, na=False)]

    if facets and len(facets) > 0:
        recommendations[facets] = recommendations[facets].map(lambda x: 1 if str(x).strip().upper() == "TRUE" else 0)

        # Compute match score
        recommendations["MatchScore"] = recommendations[facets].sum(axis=1)

        # Exact matches (all facets matched)
        exact_matches = recommendations[recommendations["MatchScore"] == len(facets)]

        # Partial matches (some facets matched)
        partial_matches = recommendations[recommendations["MatchScore"] > 0]
        partial_matches = partial_matches[partial_matches["MatchScore"] < len(facets)]

        # Sort results by rank_score
        exact_matches = exact_matches.sort_values(by="rank_score", ascending=False).drop(columns=["MatchScore"])
        partial_matches = partial_matches.sort_values(by="rank_score", ascending=False).drop(columns=["MatchScore"])
    else:
        # If no facets are selected, return all places sorted by rank_score
        exact_matches = recommendations.sort_values(by="rank_score", ascending=False)
        partial_matches = pd.DataFrame()  # No partial matches in this case

    print("Exact Matches Found:", exact_matches.shape[0])
    print("Partial Matches Found:", partial_matches.shape[0])

    # Include latitude and longitude in the results
    required_columns = ["name", "type", "borough", "rank_score", "location_link", "photo", "rating"]
    if "latitude" in df.columns and "longitude" in df.columns:
        required_columns.extend(["latitude", "longitude"])

    # Add working_hours column if it's not already in required_columns
    if "working_hours" in df.columns and "working_hours" not in required_columns:
        required_columns.append("working_hours")

    exact_results = exact_matches[required_columns] if not exact_matches.empty else pd.DataFrame()
    partial_results = partial_matches[required_columns] if not partial_matches.empty else pd.DataFrame()

    # Add open status to results
    if not exact_results.empty:
        # Apply the is_place_open function to add open status
        if "working_hours" in exact_results.columns:
            open_status = exact_results["working_hours"].apply(is_place_open)
            exact_results["is_open"] = [status[0] for status in open_status]
            exact_results["open_status_text"] = [status[1] for status in open_status]
        else:
            exact_results["is_open"] = False
            exact_results["open_status_text"] = "Hours not available"

    if not partial_results.empty:
        # Apply the is_place_open function to add open status
        if "working_hours" in partial_results.columns:
            open_status = partial_results["working_hours"].apply(is_place_open)
            partial_results["is_open"] = [status[0] for status in open_status]
            partial_results["open_status_text"] = [status[1] for status in open_status]
        else:
            partial_results["is_open"] = False
            partial_results["open_status_text"] = "Hours not available"

    return exact_results, partial_results

@app.route('/get_locations', methods=['POST'])
def get_locations():
    try:
        data = request.json
        place_names = data.get("recommended_places", [])

        # Dictionary of known locations (you can expand this)
        known_locations = {
            "Mayur Artifacts": {"latitude": 18.5204, "longitude": 73.8567},  # Pune coordinates
            "Raj Art Gallery Pune": {"latitude": 18.5204, "longitude": 73.8567},  # Pune
            "Top Art Gallery": {"latitude": 19.0760, "longitude": 72.8777},  # Mumbai
            # Add more known locations here as needed
        }

        results = []
        for place_name in place_names:
            # First check if it's in our known locations dictionary
            matched = False

            # Check for exact or partial matches in known locations
            for known_name, coords in known_locations.items():
                if (place_name.lower() in known_name.lower() or
                    known_name.lower() in place_name.lower()):
                    # Get working hours for this place from the dataframe
                    place_data = df[df['name'].str.contains(place_name, case=False, na=False)]
                    working_hours = None
                    is_open = False
                    open_status_text = "Hours not available"

                    if not place_data.empty and 'working_hours' in place_data.columns:
                        working_hours = place_data.iloc[0]['working_hours']
                        is_open, open_status_text = is_place_open(working_hours)

                    results.append({
                        "name": place_name,
                        "latitude": coords["latitude"],
                        "longitude": coords["longitude"],
                        "working_hours": working_hours,
                        "is_open": is_open,
                        "open_status_text": open_status_text
                    })
                    matched = True
                    break

            if not matched:
                # Try to find in dataframe
                place_data = df[df['name'].str.contains(place_name, case=False, na=False)]

                if not place_data.empty:
                    # Use the first match if multiple matches found
                    place = place_data.iloc[0]

                    # Check if place has latitude and longitude
                    if 'latitude' in place and 'longitude' in place and not pd.isna(place['latitude']) and not pd.isna(place['longitude']):
                        lat = float(place['latitude'])
                        lon = float(place['longitude'])
                    else:
                        # Generate coordinates as before...
                        if 'borough' in place and not pd.isna(place['borough']):
                            borough = place['borough'].lower()
                            if 'pune' in borough:
                                lat, lon = 18.5204, 73.8567  # Pune
                            elif 'mumbai' in borough:
                                lat, lon = 19.0760, 72.8777  # Mumbai
                            elif 'delhi' in borough:
                                lat, lon = 28.6139, 77.2090  # Delhi
                            elif 'bangalore' in borough or 'bengaluru' in borough:
                                lat, lon = 12.9716, 77.5946  # Bangalore
                            elif 'chennai' in borough:
                                lat, lon = 13.0827, 80.2707  # Chennai
                            else:
                                # Default to a random location in central India
                                lat = 20.5937 + (random.random() * 2 - 1)  # +/- 1 degree from center of India
                                lon = 78.9629 + (random.random() * 2 - 1)
                        else:
                            # Default to a random location in central India
                            lat = 20.5937 + (random.random() * 2 - 1)
                            lon = 78.9629 + (random.random() * 2 - 1)

                    # Process working hours
                    working_hours = place['working_hours'] if 'working_hours' in place and not pd.isna(place['working_hours']) else None
                    is_open = False
                    open_status_text = "Hours not available"

                    if working_hours:
                        is_open, open_status_text = is_place_open(working_hours)

                    results.append({
                        "name": place['name'],
                        "latitude": lat,
                        "longitude": lon,
                        "type": place['type'] if 'type' in place and not pd.isna(place['type']) else "Unknown",
                        "rank_score": float(place['rank_score']) if 'rank_score' in place and not pd.isna(place['rank_score']) else 0,
                        "photo": place['photo'] if 'photo' in place and not pd.isna(place['photo']) else None,
                        "rating": place['rating'] if 'rating' in place and not pd.isna(place['rating']) else 'No rating available',
                        "working_hours": working_hours,
                        "is_open": is_open,
                        "open_status_text": open_status_text
                    })
                else:
                    # If place not found, use default coordinates as before
                    if 'pune' in place_name.lower():
                        lat, lon = 18.5204, 73.8567  # Pune
                    elif 'mumbai' in place_name.lower():
                        lat, lon = 19.0760, 72.8777  # Mumbai
                    elif 'delhi' in place_name.lower():
                        lat, lon = 28.6139, 77.2090  # Delhi
                    else:
                        # Generate random coordinates within India
                        lat = 20.5937 + (random.random() * 8 - 4)  # +/- 4 degrees from center of India
                        lon = 78.9629 + (random.random() * 10 - 5)  # +/- 5 degrees from center of India

                    results.append({
                        "name": place_name,
                        "latitude": lat,
                        "longitude": lon,
                        "type": "Unknown",
                        "rank_score": 0,
                        "photo": None,
                        "rating": 'No rating available',
                        "working_hours": None,
                        "is_open": False,
                        "open_status_text": "Hours not available"
                    })

        return jsonify(results)
    except Exception as e:
        print(f"Error in get_locations: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/recommendation", methods=['GET', 'POST'])
def recommend():
    unique_types = df["type"].dropna().unique().tolist()  # Get unique place types
    unique_boroughs = df["borough"].dropna().unique().tolist()  # Get unique boroughs

    exact_matches, partial_matches = None, None
    selected_facets = []

    if request.method == "POST":
        place_type = request.form.get('type')
        borough = request.form.get('borough')
        selected_facets = request.form.getlist('facets')

        exact_matches, partial_matches = recommend_places(place_type, borough, selected_facets)

    return render_template(
        'recommendation.html',
        unique_types=unique_types,
        unique_boroughs=unique_boroughs,
        categories=categories,
        exact_matches=exact_matches.to_dict(orient='records') if exact_matches is not None else None,
        partial_matches=partial_matches.to_dict(orient='records') if partial_matches is not None else None
    )

@app.route('/map')
def map_page():
    return render_template('map.html')

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    try:
        query = request.args.get('query', '').lower()
        if not query or len(query) < 2:
            return jsonify([])

        # Filter place names based on the query
        matches = df[df['name'].str.lower().str.contains(query, na=False)]

        # Get unique names and limit to top 10
        results = matches['name'].unique().tolist()[:10]

        return jsonify(results)
    except Exception as e:
        print(f"Error in autocomplete: {str(e)}")
        return jsonify([])

@app.route('/get_place_by_name', methods=['GET'])
def get_place_by_name():
    try:
        place_name = request.args.get('name', '')
        if not place_name:
            return jsonify({"error": "No place name provided"}), 400

        # Find the place in the dataframe
        place_data = df[df['name'].str.contains(place_name, case=False, na=False)]

        if place_data.empty:
            return jsonify({"error": "Place not found"}), 404

        # Get the first matching place
        place = place_data.iloc[0]

        # Get coordinates
        lat, lon = None, None
        if 'latitude' in place and 'longitude' in place and not pd.isna(place['latitude']) and not pd.isna(place['longitude']):
            lat = float(place['latitude'])
            lon = float(place['longitude'])
        else:
            # Try to get coordinates based on borough
            if 'borough' in place and not pd.isna(place['borough']):
                borough = place['borough'].lower()
                if 'pune' in borough:
                    lat, lon = 18.5204, 73.8567
                elif 'mumbai' in borough:
                    lat, lon = 19.0760, 72.8777
                elif 'delhi' in borough:
                    lat, lon = 28.6139, 77.2090
                elif 'bangalore' in borough or 'bengaluru' in borough:
                    lat, lon = 12.9716, 77.5946
                elif 'chennai' in borough:
                    lat, lon = 13.0827, 80.2707
                else:
                    lat = 20.5937 + (random.random() * 2 - 1)
                    lon = 78.9629 + (random.random() * 2 - 1)
            else:
                lat = 20.5937 + (random.random() * 2 - 1)
                lon = 78.9629 + (random.random() * 2 - 1)

        # Prepare the place data
        result = {
            "name": place['name'],
            "type": place['type'] if 'type' in place and not pd.isna(place['type']) else "Unknown",
            "borough": place['borough'] if 'borough' in place and not pd.isna(place['borough']) else "Unknown",
            "rank_score": float(place['rank_score']) if 'rank_score' in place and not pd.isna(place['rank_score']) else 0,
            "rating": place['rating'] if 'rating' in place and not pd.isna(place['rating']) else 'No rating available',
            "photo": place['photo'] if 'photo' in place and not pd.isna(place['photo']) else None,
            "latitude": lat,
            "longitude": lon
        }

        return jsonify(result)
    except Exception as e:
        print(f"Error in get_place_by_name: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        places = data.get("places", [])
        days = data.get("days", 3)  # Default to 3 days if not specified

        if not places:
            return jsonify({"error": "No places provided"}), 400

        # Prepare the prompt for the Gemini API
        places_str = "\n".join([f"- {place['name']} ({place['type']})" for place in places])
        prompt = f"""
        Create a {days}-day itinerary for a trip to visit the following places in India:

        {places_str}

        The itinerary should include:
        1. A balanced schedule with morning, afternoon, and evening activities for each day.
        2. Consider travel time between locations.
        3. Include suggestions for meals and breaks.
        4. Group nearby locations together to minimize travel time.
        5. Provide a brief description of each place or activity.
        6. Format the itinerary in a clear and organized way.
        """

        # Generate the itinerary using the Gemini API
        model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
        response = model.generate_content(prompt)

        html_itinerary = markdown.markdown(response.text)

        # Store in session and redirect
        session["itinerary"] = html_itinerary

        return jsonify({"redirect": "/itinerary"})
    except Exception as e:
        print(f"Error in generate_itinerary: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/itinerary')
def show_itinerary():
    itinerary = session.get("itinerary", "No itinerary found. Please try generating again.")
    return render_template('itinerary.html', itinerary=itinerary)

if __name__ == '__main__':
    app.run(debug=True)
