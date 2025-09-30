# ollama_interface.py - Fix timeout issue and missing functions

import json
import re
import requests

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2"

def call_ollama(prompt: str, system_prompt: str = None, timeout: int = 200) -> str:
    """Call Ollama with longer timeout"""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 300,  # Reduced from 512
        }
    }
    
    if system_prompt:
        payload["system"] = system_prompt
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)  # Increased timeout
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.Timeout:
        print(f"Ollama timeout after {timeout}s - model might be slow")
        return None
    except Exception as e:
        print(f"Ollama API error: {e}")
        return None

def extract_first_json(text: str) -> dict | None:
    """Extracts the first valid JSON object from a string."""
    if not text:
        return None
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    # Fallback for when markdown is not used
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

def clarify_and_extract_criteria(user_query: str) -> dict:
    """
    MODIFIED: This prompt is now more advanced.
    It not only extracts core criteria but also:
    1.  Identifies specific points of interest (POIs) like 'gym' or 'cafe'.
    2.  Attempts to map vague descriptions like 'lively area' to concrete search locations.
    3.  Structures the output to be more machine-readable for downstream tasks.
    """
    prompt = f"""
    You are an expert UK rental assistant. Your job is to analyze a user's request and structure it into a detailed, actionable JSON object.
    The user's request is: "{user_query}"

    You MUST return a single valid JSON object.

    1.  **Core Criteria Analysis**:
        - "destination" (string): A specific address, landmark, or station in the UK.
        - "max_budget" (integer): The maximum monthly rent in GBP.
        - "max_travel_time" (integer): The maximum commute time in minutes.

    2.  **Soft Preferences & Keywords**:
        - "soft_preferences" (string): A summary of the user's qualitative needs (e.g., "modern, quiet, good for young professionals").
        - "property_tags" (list of strings): Extract specific keywords about the property itself from the query, like "balcony", "newly renovated", "garden", "natural light".
        - "amenities_of_interest" (list of strings): Identify specific nearby places or amenities the user cares about. Examples: "gym", "cafe", "library", "park", "supermarket", "pub".

    3.  **Location Intelligence**:
        - "area_vibe" (string): Note any descriptions of the desired area, like "lively area", "quiet residential area", "family-friendly".
        - "suggested_search_locations" (list of strings): Based on the 'area_vibe' or a vague destination, suggest up to 3 specific UK areas, neighborhoods, or stations that would be good starting points. Consider the entire UK, not just London. For example:
        * If searching near "Manchester city center" with "lively" preference → ["Manchester City Centre", "Northern Quarter", "Spinningfields"]
        * If searching near "Edinburgh" with "student-friendly" → ["Marchmont", "Newington", "Bruntsfield"]
        * If searching in "Birmingham" with "quiet residential" → ["Harborne", "Moseley", "Kings Heath"]
        * If searching in "Bristol" with "trendy" → ["Clifton", "Stokes Croft", "Bedminster"]
        - "city_context" (string): Identify which UK city or region the search is focused on (e.g., "London", "Manchester", "Edinburgh", "Birmingham", "Bristol", "Leeds", "Glasgow", "Liverpool").

    4.  **Decision & Response Structure**:
        - **Status "success"**: If "destination", "max_budget", AND "max_travel_time" are all clearly stated.
        - **Status "clarification_needed"**: If any of the three CORE CRITERIA are missing or ambiguous.

    **Example for a successful query**: "Find me a modern 1-bed flat near Manchester University. My budget is £1200. I need to get there in under 25 mins. I like quiet neighborhoods."
    ```json
    {{
      "status": "success",
      "data": {{
        "destination": "Manchester University, Oxford Road, Manchester",
        "max_budget": 1200,
        "max_travel_time": 25,
        "soft_preferences": "Wants a modern flat in a quiet neighborhood.",
        "property_tags": ["modern"],
        "amenities_of_interest": [],
        "area_vibe": "quiet neighborhood",
        "suggested_search_locations": ["Fallowfield", "Victoria Park", "Withington"],
        "city_context": "Manchester"
      }}
    }}
    ```

    **Example for a query needing clarification**: "I want a cheap flat somewhere central."
    ```json
    {{
        "status": "clarification_needed",
        "data": {{
            "question": "I can certainly help with that! To find the best options, could you please tell me a specific destination you'll be commuting to (like an office address or station), your maximum monthly budget, and your desired maximum commute time?"
        }}
    }}
    ```

    Return ONLY the JSON object.
    """
    response_text = call_ollama(prompt)
    parsed_json = extract_first_json(response_text)
    if parsed_json:
        return parsed_json
    else:
        return {{"status": "error", "data": {{"message": "Could not parse JSON from Ollama."}}}}


def refine_criteria_with_answer(original_query: str, user_answer: str) -> dict:
    combined_query = f"My original request was: '{{original_query}}'. In response to your question, here is more information: '{{user_answer}}'."
    print(f"\n[Ollama] Refining criteria with combined query: {{combined_query}}")
    return clarify_and_extract_criteria(combined_query)


def extract_tags_from_description(description: str) -> dict:
    """
    NEW FUNCTION: Uses Ollama to extract structured tags from a property's free-text description.
    This helps in objectively comparing properties based on features not always in structured data.
    """
    prompt = f"""
    You are a property data analysis expert. Your task is to extract specific features from the following property description and return a structured JSON object.

    Property Description:
    "{{description}}"

    Analyze the text and extract the following attributes. If an attribute is not mentioned, use `null`.
    - "renovation_status": (string) e.g., "newly_renovated", "modern", "needs_refurbishment", "well_maintained".
    - "features": (list of strings) e.g., "balcony", "garden", "parking", "concierge", "bills_included", "furnished", "unfurnished".
    - "natural_light": (string) e.g., "excellent", "good", "average", "not_mentioned". Infer this from phrases like "bright and airy", "large windows", "sun-drenched".
    - "noise_level": (string) e.g., "quiet_street", "ex-local_authority", "purpose_built", "standard". Infer this from context.
    - "summary": (string) A very brief, one-sentence summary of the property's key selling points.

    Return ONLY the JSON object. Example output:
    ```json
    {{
      "renovation_status": "modern",
      "features": ["balcony", "furnished"],
      "natural_light": "excellent",
      "noise_level": "quiet_street",
      "summary": "A modern, furnished apartment with a balcony and excellent natural light on a quiet street."
    }}
    ```
    """
    response_text = call_ollama(prompt)
    parsed_json = extract_first_json(response_text)
    if parsed_json:
        return parsed_json
    else:
        return {{}}

def generate_recommendations(properties_data: list[dict], user_query: str, soft_preferences: str) -> dict | None:
    """
    SIMPLIFIED for faster generation
    """
    if not properties_data:
        return {"recommendations": []}
    
    # Only use top 5 properties
    top_props = properties_data[:5]
    
    system_prompt = """You are a helpful UK rental assistant. Be concise."""
    
    # Extremely simplified property data
    simple_props = []
    for i, prop in enumerate(top_props):
        simple_props.append({
            'id': i + 1,
            'address': prop.get('Address', 'Unknown')[:50],  # Truncate
            'price': prop.get('Price', 'N/A'),
            'url': prop.get('URL', ''),
            'travel': f"{prop.get('travel_time_minutes', 'N/A')} min",
            'crimes': prop.get('crime_data_summary', {}).get('total_crimes_6m', 0),
        })
    
    prompt = f"""
User needs: {user_query[:100]}

Properties (rank by travel time and crime):
{json.dumps(simple_props, indent=1)}

Return top 3 as JSON:
{{
  "recommendations": [
    {{"rank": 1, "address": "...", "price": "...", "travel_time": "...", "explanation": "Good location, low crime.", "url": "..."}}
  ]
}}

JSON only:
"""
    
    response_text = call_ollama(prompt, system_prompt, timeout=90)  # 90s timeout
    
    if not response_text:
        return create_fallback_recommendations(properties_data)
    
    parsed = extract_first_json(response_text)
    
    if parsed and 'recommendations' in parsed:
        return parsed
    
    return create_fallback_recommendations(properties_data)


def create_fallback_recommendations(properties_data: list[dict]) -> dict:
    """Fast rule-based recommendations"""
    sorted_props = sorted(
        properties_data[:10],
        key=lambda x: (
            x.get('travel_time_minutes', 999),
            x.get('crime_data_summary', {}).get('total_crimes_6m', 999)
        )
    )
    
    recommendations = []
    for i, prop in enumerate(sorted_props[:5]):
        crime_count = prop.get('crime_data_summary', {}).get('total_crimes_6m', 0)
        crime_desc = "low crime area" if crime_count < 50 else "moderate crime" if crime_count < 100 else "higher crime area"
        
        recommendations.append({
            'rank': i + 1,
            'address': prop.get('Address', 'Unknown'),
            'price': prop.get('Price', 'N/A'),
            'travel_time': f"{prop.get('travel_time_minutes', 'N/A')} minutes",
            'explanation': f"Commute time of {prop.get('travel_time_minutes', 'N/A')} minutes with {crime_count} crimes reported in 6 months ({crime_desc}). Good option for your needs.",
            'url': prop.get('URL', '')
        })
    
    return {'recommendations': recommendations}