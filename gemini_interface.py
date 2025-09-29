import google.generativeai as genai
from config import GEMINI_API_KEY
import json

# Configure the Gemini API client
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-lite')

def extract_criteria(user_query: str) -> dict | None:
    """Extracts search criteria from a user query using Gemini."""
    prompt = f"""
    Extract apartment search criteria from this query as a valid JSON object.
    The user query is: "{user_query}"

    The JSON object must have the following keys:
    - "destination": A string representing the full destination address if mentioned.
    - "max_budget": A number representing the maximum monthly rent in GBP.
    - "max_travel_time": A number representing the maximum travel time in minutes.
    - "preferences": An object containing importance ratings. For example: {{"crime_rate": "somewhat_important"}}

    If a field is not mentioned, use these defaults:
    - max_budget: 3000
    - max_travel_time: 60
    - preferences: {{"crime_rate": "somewhat_important", "cost_of_living": "somewhat_important"}}

    Return ONLY the JSON object and nothing else.
    """
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's a valid JSON string
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing JSON from Gemini response: {e}")
        return None

def generate_recommendations(properties_data: list[dict], user_query: str) -> dict | None:
    """Generates ranked recommendations with explanations using Gemini."""
    prompt = f"""
    You are a helpful London apartment recommendation assistant.
    The user's original request was: "{user_query}"

    Here is a list of available apartments that fit the user's budget and travel time requirements:
    {json.dumps(properties_data, indent=2)}

    Your task is to:
    1. Analyze the provided list of apartments.
    2. Rank the top 3 to 5 apartments that are most suitable for the user.
    3. For each recommended apartment, provide a detailed explanation of why it's a good fit, considering the user's preferences (rent, travel time, crime, cost of living). Mention specific trade-offs if any.

    Return your answer as a single, valid JSON object with a key "recommendations". 
    Each item in the "recommendations" list should be an object with the keys: "rank", "address", "price", "travel_time", and "explanation".

    Return ONLY the JSON object and nothing else.
    """
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's a valid JSON string
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing JSON from Gemini recommendation response: {e}")
        return None