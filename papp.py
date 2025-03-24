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

load_dotenv()  # Load environment variables from .env

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Flask session secret key


df = pd.read_excel("merged_data_reviews_about.xlsx")

# username = "jatin_yadav"
# password = "jatin@123"

# encoded_username = quote_plus(username)
# encoded_password = quote_plus(password)
# print(encoded_password)

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
# GOOGLE_CLIENT_ID = "706372573975-5qk0q56c07p12hddpknv1cfu6a448d1hf.apps.googleusercontent.com"
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
    return redirect(url_for('pindex'))

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

    # exact_matches["rank_score"] = exact_matches["rank_score"].round(2)
    # partial_matches["rank_score"] = partial_matches["rank_score"].round(2)

    
    print("Exact Matches Found:", exact_matches.shape[0])
    print("Partial Matches Found:", partial_matches.shape[0])
    # print("First Few Exact Matches:\n", exact_matches.head())
    # print("First Few Partial Matches:\n", partial_matches.head())


    return exact_matches[["name", "type", "borough", "rank_score", "location_link"]], \
           partial_matches[["name", "type", "borough", "rank_score", "location_link"]] if not partial_matches.empty else pd.DataFrame()



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
        'precommendation.html',
        unique_types=unique_types,
        unique_boroughs=unique_boroughs,
        categories = categories,
        exact_matches=exact_matches.to_dict(orient='records') if exact_matches is not None else None,
        partial_matches=partial_matches.to_dict(orient='records') if partial_matches is not None else None
    )


if __name__ == '__main__':
    app.run(debug=True)
