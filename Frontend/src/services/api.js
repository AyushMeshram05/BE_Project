import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:5000';

export const getPlaces = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/places`);
      console.log("Places data:", response.data);  // Debugging
      return response.data;
    } catch (error) {
      console.error("Error fetching places:", error);
      return [];
    }
  };
  

export const getRecommendations = async (placeName) => {
  const response = await axios.get(`${API_BASE_URL}/recommendations`, {
    params: { place_name: placeName }
  });
  return response.data;
};
