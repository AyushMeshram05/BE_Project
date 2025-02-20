import React, { useEffect, useState } from 'react';
import { getPlaces, getRecommendations } from '../services/api';
import { MapPin, Star } from 'lucide-react';

function RecommendationViewer() {
  const [places, setPlaces] = useState([]);
  const [selectedPlace, setSelectedPlace] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchPlaces() {
      const placesList = await getPlaces();
      if (placesList && placesList.length > 0) {
        setPlaces(placesList);
      }
    }
    fetchPlaces();
  }, []);

  const handlePlaceChange = async (event) => {
    const placeName = event.target.value;
    setSelectedPlace(placeName);
    setLoading(true);

    if (placeName) {
      const recommendationsList = await getRecommendations(placeName);
      setRecommendations(recommendationsList);
    } else {
      setRecommendations([]);
    }
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto px-4">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Smart City Place Recommendations
        </h1>
        <p className="text-lg text-gray-600">
          Discover amazing places similar to your favorite locations
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
        <div className="mb-6">
          <label 
            htmlFor="placeSelect" 
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Select a Place
          </label>
          <div className="relative">
            <select
              id="placeSelect"
              value={selectedPlace}
              onChange={handlePlaceChange}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 py-3 pl-3 pr-10 text-gray-900"
            >
              <option value="">-- Select a Place --</option>
              {places.map((place, index) => (
                <option key={index} value={place}>{place}</option>
              ))}
            </select>
            <MapPin className="absolute right-3 top-3 h-5 w-5 text-gray-400" />
          </div>
        </div>

        <div>
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            {selectedPlace ? 'Similar Places' : 'Recommendations'}
          </h2>
          
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto"></div>
              <p className="mt-4 text-gray-600">Finding similar places...</p>
            </div>
          ) : recommendations.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2">
              {recommendations.map((rec, index) => (
                <div 
                  key={index}
                  className="bg-gray-50 rounded-lg p-4 hover:shadow-md transition"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">{rec.name}</h3>
                      <div className="flex items-center mt-2">
                        <Star className="h-4 w-4 text-yellow-400 mr-1" />
                        <span className="text-sm text-gray-600">
                          Similarity Score: {(rec.score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              {selectedPlace ? 
                'No recommendations available for this place.' :
                'Select a place to see recommendations.'
              }
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default RecommendationViewer;