# ollama_interface.py

import json
import re
import requests

# Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2"  # Change to your preferred model

def call_ollama(prompt: str, system_prompt: str = None) -> str:
    """
    Call Ollama API locally - completely free!
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
        }
    }
    
    if system_prompt:
        payload["system"] = system_prompt
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except Exception as e:
        print(f"Ollama API error: {e}")
        return None


def clarify_and_extract_criteria(user_query: str) -> dict:
    """
    Extract search criteria using Ollama (FREE!)
    """
    system_prompt = """You are a UK rental assistant. Extract search criteria and return ONLY valid JSON."""
    
    prompt = f"""
Analyze this rental request and return a JSON object with these fields:

User request: "{user_query}"

Required fields:
- "status": "success" if destination, max_budget, and max_travel_time are clear, otherwise "clarification_needed"
- "data": object containing:

If status is "success":
  - "destination": specific UK address/station
  - "max_budget": integer (monthly rent in GBP)
  - "max_travel_time": integer (minutes)
  - "soft_preferences": string summary
  - "property_tags": list of strings (e.g., ["modern", "balcony"])
  - "amenities_of_interest": list (e.g., ["gym", "cafe"])
  - "area_vibe": string or null
  - "suggested_search_locations": list of 3 nearby UK areas
  - "city_context": string (e.g., "Manchester")

If status is "clarification_needed":
  - "question": string asking for missing information

Examples:

Query: "Flat near Manchester University, £1200 budget, 25 mins max"
{{
  "status": "success",
  "data": {{
    "destination": "University of Manchester, Oxford Road",
    "max_budget": 1200,
    "max_travel_time": 25,
    "soft_preferences": null,
    "property_tags": [],
    "amenities_of_interest": [],
    "area_vibe": null,
    "suggested_search_locations": ["Fallowfield", "Withington", "Rusholme"],
    "city_context": "Manchester"
  }}
}}

Query: "Need a cheap flat in Edinburgh"
{{
  "status": "clarification_needed",
  "data": {{
    "question": "I can help you find a flat in Edinburgh! Please tell me: 1) Where will you be commuting to? 2) Your maximum monthly budget in £? 3) Maximum commute time in minutes?"
  }}
}}

Return ONLY the JSON object, no other text.
"""
    
    response_text = call_ollama(prompt, system_prompt)
    
    if not response_text:
        return {"status": "error", "data": {"message": "Model unavailable"}}
    
    try:
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw response: {response_text}")
        return {"status": "error", "data": {"message": "Could not parse response"}}


def refine_criteria_with_answer(original_query: str, user_answer: str) -> dict:
    """
    Refine search criteria based on user's clarification
    """
    combined_query = f"Original request: '{original_query}'. Additional info: '{user_answer}'."
    return clarify_and_extract_criteria(combined_query)


def extract_tags_from_description(description: str) -> dict:
    """
    Extract property features using Ollama
    """
    if not description or len(description) < 20:
        return {}
    
    prompt = f"""
Extract features from this property description and return ONLY valid JSON:

Description: "{description}"

Return this structure:
{{
  "renovation_status": "newly_renovated" | "modern" | "needs_refurbishment" | "well_maintained" | null,
  "features": ["balcony", "garden", "parking", etc.],
  "natural_light": "excellent" | "good" | "average" | null,
  "noise_level": "quiet_street" | "standard" | null,
  "summary": "Brief one-sentence summary"
}}

Return ONLY the JSON, no other text.
"""
    
    response_text = call_ollama(prompt)
    
    if not response_text:
        return {}
    
    try:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(response_text)
    except:
        return {}


def generate_recommendations(properties_data: list[dict], user_query: str, soft_preferences: str) -> dict | None:
    """
    Generate recommendations using Ollama
    """
    system_prompt = """You are Alex, a helpful UK apartment recommendation assistant. Be friendly and insightful."""
    
    # Limit data sent to model (to avoid token limits)
    simplified_props = []
    for prop in properties_data[:10]:  # Max 10 properties
        simplified_props.append({
            'Address': prop.get('Address'),
            'Price': prop.get('Price'),
            'URL': prop.get('URL'),
            'travel_time_minutes': prop.get('travel_time_minutes'),
            'crime_data_summary': prop.get('crime_data_summary', {}),
            'amenities_nearby': prop.get('amenities_nearby', {}),
            'description_tags': prop.get('description_tags', {}),
        })
    
    prompt = f"""
User's request: "{user_query}"
User's preferences: "{soft_preferences}"

Here are {len(simplified_props)} apartment candidates:
{json.dumps(simplified_props, indent=2)}

Rank the top 3-5 apartments based on best fit for the user's needs.

Return ONLY valid JSON in this format:
{{
  "recommendations": [
    {{
      "rank": 1,
      "address": "Full address",
      "price": "£X pcm",
      "travel_time": "X minutes",
      "explanation": "Detailed explanation of why this is a good match, referencing commute time, crime data, amenities, and features.",
      "url": "Full property URL"
    }}
  ]
}}

Return ONLY the JSON object.
"""
    
    response_text = call_ollama(prompt, system_prompt)
    
    if not response_text:
        return None
    
    try:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(response_text)
    except Exception as e:
        print(f"Error generating recommendations: {e}")
        return None