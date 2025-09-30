# ollama_interface.py - Fixed version with better logging and URL handling

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
            "num_predict": 300,
        }
    }
    
    if system_prompt:
        payload["system"] = system_prompt
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.Timeout:
        print(f"⚠️  Ollama timeout after {timeout}s - model might be slow")
        return None
    except Exception as e:
        print(f"❌ Ollama API error: {e}")
        return None

def extract_first_json(text: str) -> dict | None:
    """Extracts the first valid JSON object from a string - improved version"""
    if not text:
        return None
    
    # Strategy 1: Try parsing the entire text as-is (most common for Ollama)
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Strategy 2: Look for markdown JSON blocks
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Find JSON object with proper brace matching
    # This handles nested objects correctly
    brace_count = 0
    start_idx = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                # Found a complete JSON object
                try:
                    json_str = text[start_idx:i+1]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Keep looking for another object
                    start_idx = -1
                    continue
    
    return None

def clarify_and_extract_criteria(user_query: str) -> dict:
    """Extract criteria from user query"""
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
    - "suggested_search_locations" (list of strings): Based on the 'area_vibe' or a vague destination, suggest up to 3 specific UK areas, neighborhoods, or stations.
    - "city_context" (string): Identify which UK city or region the search is focused on (e.g., "London", "Manchester", "Edinburgh").

4.  **Decision & Response Structure**:
    - **Status "success"**: If "destination", "max_budget", AND "max_travel_time" are all clearly stated.
    - **Status "clarification_needed"**: If any of the three CORE CRITERIA are missing or ambiguous.

Return ONLY the JSON object.
"""
    response_text = call_ollama(prompt)
    parsed_json = extract_first_json(response_text)
    if parsed_json:
        return parsed_json
    else:
        return {"status": "error", "data": {"message": "Could not parse JSON from Ollama."}}


def refine_criteria_with_answer(original_query: str, user_answer: str) -> dict:
    combined_query = f"My original request was: '{original_query}'. In response to your question, here is more information: '{user_answer}'."
    print(f"\n[Ollama] Refining criteria with combined query: {combined_query}")
    return clarify_and_extract_criteria(combined_query)


def extract_tags_from_description(description: str) -> dict:
    """Extract structured tags from property description"""
    # Handle non-string descriptions
    if not isinstance(description, str):
        description = str(description) if description else ""
    
    if not description.strip():
        return {
            "renovation_status": None,
            "features": [],
            "natural_light": None,
            "noise_level": None,
            "summary": "No description available"
        }
    
    prompt = f"""
You are a property data analysis expert. Extract features from this property description as JSON.

Property Description:
"{description}"

Extract these attributes (use null if not mentioned):
- "renovation_status": e.g., "newly_renovated", "modern", "needs_refurbishment"
- "features": list like ["balcony", "garden", "parking", "furnished"]
- "natural_light": "excellent", "good", "average", or "not_mentioned"
- "noise_level": "quiet_street", "purpose_built", or "standard"
- "summary": Brief one-sentence summary

Return ONLY the JSON object.
"""
    
    try:
        response_text = call_ollama(prompt, timeout=3000)
        if not response_text:
            return {}
        
        parsed_json = extract_first_json(response_text)
        if parsed_json:
            return parsed_json
        else:
            return {}
    except Exception as e:
        print(f"Error extracting tags from description: {e}")
        return {}


def _get_property_url(prop: dict) -> str:
    """Helper to get URL from property dict with multiple fallbacks"""
    # Try different possible keys
    for key in ['URL', 'url', 'Url', 'link', 'Link']:
        if key in prop and prop[key]:
            return prop[key]
    return ''


def generate_recommendations(properties_data: list[dict], user_query: str, soft_preferences: str) -> dict | None:
    """Generate personalized property recommendations using Ollama"""
    
    print(f"\n🤖 [RECOMMENDATION ENGINE] Starting...")
    print(f"   Properties to analyze: {len(properties_data)}")
    print(f"   User preferences: {soft_preferences[:100]}...")
    
    if not properties_data:
        print("   ⚠️  No properties to recommend")
        return {"recommendations": []}
    
    # Use top 5 properties only for faster processing
    top_props = properties_data[:5]
    print(f"   Analyzing top {len(top_props)} properties")
    
    # Debug: Print what keys are available
    if top_props:
        print(f"   Available keys in property dict: {list(top_props[0].keys())}")
    
    # Build simplified property data for LLM
    simple_props = []
    for i, prop in enumerate(top_props):
        url = _get_property_url(prop)
        simple_prop = {
            'id': i + 1,
            'address': prop.get('Address', 'Unknown')[:60],
            'price': prop.get('Price', 'N/A'),
            'url': url,
            'travel': f"{prop.get('travel_time_minutes', 'N/A')} min",
            'crimes': prop.get('crime_data_summary', {}).get('total_crimes_6m', 0),
            'crime_trend': prop.get('crime_data_summary', {}).get('crime_trend', 'unknown'),
        }
        simple_props.append(simple_prop)
        print(f"   Property {i+1}: {simple_prop['address'][:40]}... | £{simple_prop['price']} | {simple_prop['travel']} | {simple_prop['crimes']} crimes")
    
    system_prompt = "You are an expert London rental assistant. Provide detailed, personalized recommendations."
    
    prompt = f"""
User is looking for: {user_query}
User preferences: {soft_preferences}

Available properties ranked by travel time:
{json.dumps(simple_props, indent=2)}

Create recommendations for the top 3 properties. For EACH property write:
1. Why it matches their needs (mention travel time, safety, price)
2. Specific benefits (e.g., "Only 6 mins to UCL with low crime rate")
3. Trade-offs if any

Return as JSON with this EXACT format:
{{
  "recommendations": [
    {{
      "rank": 1,
      "address": "Full address here",
      "price": "£1500 pcm",
      "travel_time": "6 minutes",
      "explanation": "This property is excellent for your needs because [detailed reason]. The area has only 45 crimes in 6 months (low crime) and the commute is very short. [More specific details]",
      "url": "https://..."
    }}
  ]
}}

Be specific and detailed in explanations. Return ONLY the JSON.
"""
    
    print(f"\n   Calling Ollama LLM (timeout: 120s)...")
    response_text = call_ollama(prompt, system_prompt, timeout=5000)
    
    if not response_text:
        print("   ❌ Ollama timeout or error - using fallback recommendations")
        return create_fallback_recommendations(properties_data)
    
    print(f"   ✓ Got response from Ollama ({len(response_text)} chars)")
    
    # Try to parse JSON
    parsed = extract_first_json(response_text)
    
    if parsed and 'recommendations' in parsed:
        print(f"   ✓ Successfully parsed {len(parsed['recommendations'])} recommendations")
        
        # Ensure URLs are set correctly
        for rec in parsed['recommendations']:
            if not rec.get('url') or rec.get('url') == '':
                # Find matching property and get its URL
                rec_address = rec.get('address', '')
                for prop in properties_data:
                    if rec_address in prop.get('Address', ''):
                        rec['url'] = _get_property_url(prop)
                        break
        
        return parsed
    else:
        print(f"   ⚠️  Could not parse JSON from Ollama response")
        print(f"   Raw response: {response_text[:200]}...")
        print("   Using fallback recommendations")
        return create_fallback_recommendations(properties_data)


def create_fallback_recommendations(properties_data: list[dict]) -> dict:
    """Fast rule-based recommendations when LLM fails"""
    print("   🔧 Creating fallback recommendations...")
    
    sorted_props = sorted(
        properties_data[:10],
        key=lambda x: (
            x.get('travel_time_minutes', 999),
            x.get('crime_data_summary', {}).get('total_crimes_6m', 999)
        )
    )
    
    recommendations = []
    for i, prop in enumerate(sorted_props[:5]):
        crime_data = prop.get('crime_data_summary', {})
        crime_count = crime_data.get('total_crimes_6m', 0)
        crime_trend = crime_data.get('crime_trend', 'unknown')
        travel_time = prop.get('travel_time_minutes', 'N/A')
        
        # More detailed crime description
        if crime_count < 50:
            crime_desc = f"very safe area ({crime_count} crimes in 6 months, {crime_trend} trend)"
        elif crime_count < 100:
            crime_desc = f"moderately safe area ({crime_count} crimes in 6 months, {crime_trend} trend)"
        else:
            crime_desc = f"area with higher crime rate ({crime_count} crimes in 6 months, {crime_trend} trend)"
        
        # Build detailed explanation
        explanation = f"This property offers an excellent {travel_time}-minute commute to your destination. "
        explanation += f"The location is a {crime_desc}. "
        explanation += f"Priced at {prop.get('Price', 'N/A')}, it represents good value within your budget. "
        
        # Add cost of living info if available
        if prop.get('cost_of_living'):
            explanation += f"Local amenities are readily available. "
        
        recommendations.append({
            'rank': i + 1,
            'address': prop.get('Address', 'Unknown'),
            'price': prop.get('Price', 'N/A'),
            'travel_time': f"{travel_time} minutes",
            'explanation': explanation,
            'url': _get_property_url(prop)
        })
    
    print(f"   ✓ Created {len(recommendations)} fallback recommendations")
    return {'recommendations': recommendations}