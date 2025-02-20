from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})  # Allow frontend origin

# Load the sentiment-enhanced dataset
data = pd.read_csv('sentiment_data.csv')

# Combine relevant text fields for better feature extraction
data['combined_text'] = data['category'] + ' ' + data['subtypes'] + ' ' + \
                        data['about'] + ' ' + data['description']

# TF-IDF vectorization
tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(data['combined_text'])

# Compute cosine similarity between all places
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# Helper function to get recommendations
def get_recommendations(place_name):
    if place_name not in data['name'].values:
        return []

    idx = data[data['name'] == place_name].index[0]
    sim_scores = list(enumerate(cosine_sim[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    top_places = sim_scores[1:6]  # Skip the first one (itself)
    recommendations = [{"name": data.iloc[i[0]]['name'], "score": i[1]} for i in top_places]
    return recommendations

# ✅ **Fix: Add CORS to Each Route**
@app.route('/recommendations', methods=['GET'])
def recommendations():
    place_name = request.args.get('place_name')
    if not place_name:
        return jsonify({"error": "Please provide a place_name parameter."}), 400

    recommendations = get_recommendations(place_name)
    if not recommendations:
        return jsonify({"error": "Place not found or no recommendations available."}), 404

    response = jsonify(recommendations)
    response.headers.add("Access-Control-Allow-Origin", "*")  # Allow CORS
    return response

@app.route('/places', methods=['GET'])
def places():
    place_names = data['name'].tolist()
    response = jsonify(place_names)
    response.headers.add("Access-Control-Allow-Origin", "*")  # Allow CORS
    return response

if __name__ == '__main__':
    app.run(debug=True)
