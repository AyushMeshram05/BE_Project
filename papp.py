import os
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
import random  # For generating random coordinates if needed

load_dotenv()  # Load environment variables from .env

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Flask session secret key

df = pd.read_excel("merged_data_reviews_about.xlsx")

# Add coordinates to the dataframe if they don't exist
if 'latitude' not in df.columns or 'longitude' not in df.columns:
    # Generate random coordinates for India (for demonstration)
    # In a real app, you would geocode the addresses
    df['latitude'] = np.random.uniform(8.0, 37.0, len(df))  # Latitude range for India
    df['longitude'] = np.random.uniform(68.0, 97.0, len(df))  # Longitude range for India

# ✅ MongoDB Connection
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

# ✅ Google OAuth Setup
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Development Only

@app.route('/')
def index():
    return render_template('pindex.html')

# ✅ Sign Up (Register)
@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    name, email, password = data.get("name"), data.get("email"), data.get("password")

    if users_collection.find_one({"email": email}):
        return jsonify({"success": False, "error": "Email already exists!"}), 400

    users_collection.insert_one({"name": name, "email": email, "password": generate_password_hash(password)})
    return jsonify({"success": True, "message": "User registered successfully!"})

# ✅ Sign In
@app.route('/signin', methods=['POST'])
def signin():
    data = request.form
    email, password = data.get("email"), data.get("password")
    user = users_collection.find_one({"email": email})

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"success": False, "error": "Invalid email or password!"}), 400

    session['user'] = {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}
    return jsonify({"success": True, "message": "Login successful!"})

# ✅ Logout
@app.route('/signout')
def signout():
    session.clear()
    return redirect(url_for('index'))

# ✅ Google Login
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
    "Religious Sites": ["Krishna", "Lakshmi", "Vishnu"],
    "Delivery & Pickup": [
        "Kerbside pickup", "No-contact delivery"
    ],
    "Check-in & Check-out": [
        "Check-in time", "Check-out time"
    ]
}

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
                    results.append({
                        "name": place_name,
                        "latitude": coords["latitude"],
                        "longitude": coords["longitude"]
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
                        # Generate coordinates in India (based on region information if available)
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
                    
                    results.append({
                        "name": place['name'],
                        "latitude": lat,
                        "longitude": lon,
                        "type": place['type'] if 'type' in place and not pd.isna(place['type']) else "Unknown",
                        "rank_score": float(place['rank_score']) if 'rank_score' in place and not pd.isna(place['rank_score']) else 0
                    })
                else:
                    # If place not found, use Pune's coordinates as default or generate within India
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
                        "rank_score": 0
                    })
        
        return jsonify(results)
    except Exception as e:
        print(f"Error in get_locations: {str(e)}")
        return jsonify({"error": str(e)}), 500

def recommend_places(user_id, place_type=None, borough=None, facets=None):
    """
    Recommend places based on user_id, type, and/or borough.
    """
    recommendations = df.copy()
    
    if place_type:
        recommendations = recommendations[recommendations["type"].str.contains(place_type, case=False, na=False)]
    
    if borough:
        recommendations = recommendations[recommendations["borough"].str.contains(borough, case=False, na=False)]

    if facets and len(facets) > 0:
        recommendations[facets] = recommendations[facets].apply(lambda x: 1 if str(x).strip().upper() == "TRUE" else 0)

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
    required_columns = ["name", "type", "borough", "rank_score", "location_link"]
    if "latitude" in df.columns and "longitude" in df.columns:
        required_columns.extend(["latitude", "longitude"])

    return exact_matches[required_columns], \
           partial_matches[required_columns] if not partial_matches.empty else pd.DataFrame()

@app.route("/recommendation", methods=['GET', 'POST'])
def recommend():
    unique_types = df["type"].dropna().unique().tolist()  # Get unique place types
    unique_boroughs = df["borough"].dropna().unique().tolist()  # Get unique boroughs

    exact_matches, partial_matches = None, None
    selected_facets = []
    
    if request.method == "POST":
        user_id = request.form.get('user_id')
        place_type = request.form.get('type')
        borough = request.form.get('borough')
        selected_facets = request.form.getlist('facets')

        if user_id:
            user_id = int(user_id)  # Convert user_id to int
            exact_matches, partial_matches = recommend_places(user_id, place_type, borough, selected_facets)

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

if __name__ == '__main__':
    app.run(debug=True)