# ollama_interface.py - COMPLETE UPDATED VERSION

import json
import re
import requests

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "gemma3:12b"  # Change to your model (qwen2.5:1.5b, llama3.2:3b, etc.)

def call_ollama(prompt: str, system_prompt: str = None, timeout: int = 6000) -> str:
    """Call Ollama with better defaults"""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 4000,
            "num_ctx": 8192,
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
        print(f"⚠️  Ollama timeout after {timeout}s")
        return None
    except Exception as e:
        print(f"❌ Ollama API error: {e}")
        return None

def extract_first_json(text: str) -> dict | None:
    """Extracts the first valid JSON object from a string"""
    if not text:
        return None
    
    try:
        cleaned_text = text.strip()
        return json.loads(cleaned_text)
    except (json.JSONDecodeError, TypeError):
        pass
    
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    match = re.search(r'`\s*(\{.*?\})\s*`', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
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
                try:
                    json_str = text[start_idx:i+1]
                    json_str = json_str.replace('\n', ' ').replace('\r', '')
                    parsed = json.loads(json_str)
                    
                    if isinstance(parsed, dict) and len(parsed) > 0:
                        if "$schema" not in parsed and "properties" not in parsed:
                            return parsed
                except json.JSONDecodeError:
                    pass
                finally:
                    start_idx = -1
    
    return None

def retry_with_simple_prompt(user_query: str) -> dict:
    """Ultra-simple prompt for stubborn models"""
    
    prompt = f"""Extract these values from the user's request and return ONLY a JSON object (no explanation):

User request: "{user_query}"

{{
  "status": "success",
  "destination": "",
  "max_budget": 0,
  "max_travel_time": 0,
  "soft_preferences": "",
  "city_context": "London",
  "suggested_search_locations": [],
  "amenities_of_interest": [],
  "area_vibe": ""
}}

Fill in the values. Return ONLY the JSON object, nothing else."""

    response_text = call_ollama(prompt, timeout=60000)
    
    if response_text:
        parsed = extract_first_json(response_text)
        if parsed and "$schema" not in parsed:
            return parsed
    
    return {
        "status": "clarification_needed",
        "data": {
            "question": "Could you specify your destination, budget, and maximum commute time?"
        }
    }

def clarify_and_extract_criteria(user_query: str) -> dict:
    """Extract criteria from user query - V5 with better soft_preferences extraction"""

    system_prompt = """You are a JSON extraction tool. You MUST return ONLY valid JSON, no explanations.
Extract UK rental search criteria from user requests.
If a specific place is mentioned (e.g., 'UCL', 'King's Cross'), use it as the destination.
If travel time is 'unlimited' or 'any', set max_travel_time to 999.
IMPORTANT: Extract any specific concerns or preferences the user mentions (safety, crime, noise, quiet, modern, etc.) into soft_preferences."""

    prompt = f"""USER REQUEST: "{user_query}"

YOUR TASK: Extract rental criteria and return ONLY the JSON below (NO explanations, NO markdown, NO backticks):

{{
  "status": "success",
  "destination": "",
  "max_budget": 0,
  "max_travel_time": 0,
  "soft_preferences": "",
  "property_tags": [],
  "amenities_of_interest": [],
  "area_vibe": "",
  "suggested_search_locations": [],
  "city_context": "London"
}}

RULES:
1. destination: Be specific (e.g., "University College London" not just "London")
2. max_budget: Extract numeric value (e.g., 5000 for "£5000/month")
3. max_travel_time: Extract minutes ONLY. "40 min" = 40, "1 hour" = 60, "90 minutes" = 90
4. If unlimited travel time, set to 999
5. suggested_search_locations: List nearby areas for the destination
6. soft_preferences: Extract SPECIFIC user concerns like "concerned about crime", "want safe area", "need quiet location", "prefer modern", etc. This is IMPORTANT!
7. CRITICAL: Return ONLY the completed JSON object, nothing else

JSON OUTPUT:"""

    response_text = call_ollama(prompt, system_prompt, timeout=6000)
    
    if not response_text:
        print("[ERROR] Ollama timeout")
        return {"status": "error", "data": {"message": "Ollama timeout"}}
    
    print(f"[DEBUG] Raw Ollama response length: {len(response_text)} chars")
    print(f"[DEBUG] First 300 chars: {response_text[:300]}")
    print(f"[DEBUG] Last 200 chars: {response_text[-200:]}")
    
    parsed_json = extract_first_json(response_text)
    
    if parsed_json:
        if "$schema" in parsed_json or "properties" in parsed_json:
            print("[WARN] Got schema instead of data, retrying with simple prompt")
            return retry_with_simple_prompt(user_query)
        
        required = ['destination', 'max_budget', 'max_travel_time']
        has_required = all(parsed_json.get(field) for field in required)
        
        if has_required:
            # ENHANCEMENT: If soft_preferences is empty, try to extract key concerns from query
            if not parsed_json.get('soft_preferences'):
                query_lower = user_query.lower()
                concerns = []
                if 'crime' in query_lower or 'safe' in query_lower:
                    concerns.append('safety and crime rates')
                if 'quiet' in query_lower:
                    concerns.append('quiet area')
                if 'modern' in query_lower or 'new' in query_lower:
                    concerns.append('modern property')
                if 'park' in query_lower or 'green' in query_lower:
                    concerns.append('access to parks')
                
                if concerns:
                    parsed_json['soft_preferences'] = ', '.join(concerns)
            
            print("[SUCCESS] Extracted valid criteria")
            return parsed_json
        else:
            print(f"[WARN] Missing required fields, retrying")
            return retry_with_simple_prompt(user_query)
    else:
        print("[ERROR] Could not parse JSON from Ollama response")
        print(f"[DEBUG] Full response:\n{response_text}")
        return retry_with_simple_prompt(user_query)

def refine_criteria_with_answer(original_query: str, user_answer: str) -> dict:
    """Refine criteria with additional user input"""
    combined_query = f"Original: '{original_query}'. Additional info: '{user_answer}'."
    print(f"\n[Ollama] Refining with: {combined_query}")
    return clarify_and_extract_criteria(combined_query)

def extract_tags_from_description(description: str) -> dict:
    """Extract structured tags from property description"""
    if not isinstance(description, str) or not description.strip():
        return {
            "renovation_status": None,
            "features": [],
            "natural_light": None,
            "noise_level": None,
            "summary": "No description available"
        }
    
    prompt = f"""Property: "{description}"

Extract features as JSON (no explanation):

{{
  "renovation_status": "newly_renovated/modern/needs_refurbishment/null",
  "features": ["feature1", "feature2"],
  "natural_light": "excellent/good/average/null",
  "noise_level": "quiet_street/standard/null",
  "summary": "one sentence"
}}

JSON OUTPUT:"""
    
    try:
        response_text = call_ollama(prompt, timeout=6000)
        if response_text:
            return extract_first_json(response_text) or {}
        return {}
    except Exception as e:
        print(f"Error extracting tags: {e}")
        return {}

def _get_property_url(prop: dict) -> str:
    """Helper to get URL from property dict"""
    for key in ['URL', 'url', 'Url', 'link', 'Link']:
        if key in prop and prop[key]:
            return prop[key]
    return ''

def generate_recommendations(properties_data: list[dict], user_query: str, soft_preferences: str) -> dict | None:
    """Generate personalized property recommendations - V3 with distinctive details"""

    print(f"\n🤖 [RECOMMENDATION ENGINE] Starting...")
    print(f"   Properties to analyze: {len(properties_data)}")

    if not properties_data:
        return {"recommendations": []}

    top_props = properties_data[:5]
    
    simple_props = []
    for i, prop in enumerate(top_props):
        url = _get_property_url(prop)
        travel_time = prop.get('travel_time_minutes', 'N/A')
        images = prop.get('Images', [])

        simple_prop = {
            'id': i + 1,  # This is the key for matching
            'address': prop.get('Address', 'Unknown')[:70],
            'price': prop.get('Price', 'N/A'),
            'url': url,
            'travel_time_minutes': travel_time,
            'crimes': prop.get('crime_data_summary', {}).get('total_crimes_6m', 0),
            'crime_trend': prop.get('crime_data_summary', {}).get('crime_trend', 'unknown'),
            'images': images,
            'description': prop.get('Description', '')[:200]
        }
        simple_props.append(simple_prop)

    system_prompt = """You are an expert London rental assistant. Provide HIGHLY DISTINCTIVE recommendations. 
    Each property should have unique selling points. Avoid generic phrases.
    Focus on SPECIFIC differences: exact commute times, safety statistics, price advantages, unique features.
    
    CRITICAL: You MUST keep properties in the EXACT order provided. Use the 'id' field as the rank."""

    prompt = f"""User is looking for: {user_query}
Preferences: {soft_preferences}

Properties (ALREADY RANKED - DO NOT REORDER):
{json.dumps(simple_props, indent=2)}

Create recommendations for top 3 properties IN THE EXACT ORDER PROVIDED.

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. Use the EXACT travel_time_minutes from the data (e.g., if it says 20, write "20 minutes")
2. Use the EXACT crimes number from the data (e.g., if crimes=170, write "170 reported crimes")
3. NEVER say "0 crimes" unless the crimes field is actually 0
4. NEVER make up numbers - only use the data provided
5. Start each explanation with the KEY ADVANTAGE
6. Include EXACT statistics from the data

Example of CORRECT explanation:
"This property offers a 20-minute commute to UCL. The area has 170 reported crimes in the last 6 months, with most incidents being theft-related. At £2,500 pcm, it's premium-priced but offers immediate access to Carnaby Street."

Example of WRONG explanation:
"This property has a short commute. The area is very safe with 0 crimes reported." ❌

Return ONLY this JSON format:
{{
  "recommendations": [
    {{
      "rank": 1,
      "address": "Full address from id:1",
      "price": "£X pcm",
      "travel_time": "X minutes",
      "explanation": "Start with key advantage. Include EXACT numbers: X minute commute, Y crimes reported. Mention specific features.",
      "url": "url from id:1"
    }}
  ]
}}"""

    response_text = call_ollama(prompt, system_prompt, timeout=6000)

    if not response_text:
        return create_fallback_recommendations(properties_data, soft_preferences)

    parsed = extract_first_json(response_text)

    if parsed and 'recommendations' in parsed:
        print("\n[DEBUG] Fixing travel times and images...")
        
        # Match by address (more reliable than URL)
        for rec in parsed['recommendations']:
            rank = rec.get('rank', 0)
            rec_address = rec.get('address', '').lower().strip()
            
            # Find matching property by address substring
            original_prop = None
            for prop in properties_data:
                prop_address = prop.get('Address', '').lower().strip()
                if rec_address[:30] in prop_address or prop_address[:30] in rec_address:
                    original_prop = prop
                    break
            
            # Fallback to rank-based matching
            if not original_prop and 1 <= rank <= len(properties_data):
                original_prop = properties_data[rank - 1]
            
            if original_prop:
                tt_mins = original_prop.get('travel_time_minutes')
                rec['travel_time'] = f"{tt_mins} minutes" if isinstance(tt_mins, (int, float)) else "N/A"
                rec['images'] = original_prop.get('Images', [])
                rec['url'] = original_prop.get('URL', rec.get('url', ''))
                rec['address'] = original_prop.get('Address', rec.get('address', ''))
                
                print(f"  ✓ Rank {rank}: {rec['address'][:40]} - {rec['travel_time']}")
            else:
                print(f"  ⚠️  Could not match rank {rank}")
                rec['travel_time'] = "N/A"
                rec['images'] = []
        
        return parsed
    else:
        print("[WARN] Could not parse JSON, using fallback")
        return create_fallback_recommendations(properties_data, soft_preferences)

def create_fallback_recommendations(properties_data: list[dict], soft_preferences: str = "") -> dict:
    """High-quality, context-aware recommendations that address user concerns"""
    print("   🔧 Creating intelligent rule-based recommendations...")
    
    sorted_props = sorted(
        properties_data[:15],
        key=lambda x: (
            x.get('travel_time_minutes', 999),
            x.get('parsed_price', 9999)
        )
    )
    
    user_cares_about_crime = 'crime' in soft_preferences.lower() or 'safe' in soft_preferences.lower()
    user_cares_about_modern = 'modern' in soft_preferences.lower() or 'new' in soft_preferences.lower()
    user_cares_about_quiet = 'quiet' in soft_preferences.lower()
    
    recommendations = []
    for i, prop in enumerate(sorted_props[:5]):
        travel_time = prop.get('travel_time_minutes', 'N/A')
        price = prop.get('Price', 'N/A')
        parsed_price = prop.get('parsed_price', 0)
        address = prop.get('Address', 'Unknown')
        description = prop.get('Description', '')
        
        crime_data = prop.get('crime_data_summary', {})
        crime_count = crime_data.get('total_crimes_6m', 0)
        crime_trend = crime_data.get('crime_trend', 'unknown')
        top_crimes = crime_data.get('top_crime_types', [])
        
        area_parts = address.split(',')
        area = area_parts[1].strip() if len(area_parts) > 1 else "the area"
        
        if isinstance(travel_time, (int, float)) and parsed_price > 0 and travel_time > 0:
            value_score = parsed_price / travel_time
            if value_score < 60:
                value_assessment = "exceptional value"
            elif value_score < 80:
                value_assessment = "good value"
            else:
                value_assessment = "premium pricing"
        else:
            value_assessment = "competitive pricing"
        
        explanation_parts = []
        
        if i == 0:
            explanation_parts.append(f"🥇 **Top choice**: Located in {area}, this property offers the shortest commute at just {travel_time} minutes to UCL.")
        elif i == 1:
            explanation_parts.append(f"🥈 **Runner-up**: In {area}, with a {travel_time}-minute commute to UCL.")
        elif i == 2:
            explanation_parts.append(f"🥉 **Alternative**: Situated in {area}, {travel_time} minutes from UCL.")
        else:
            explanation_parts.append(f"**Option #{i+1}**: In {area}, {travel_time}-minute journey to UCL.")
        
        explanation_parts.append(f"Priced at {price}, offering {value_assessment}.")
        
        # ADDRESS USER CONCERNS EXPLICITLY
        if user_cares_about_crime and crime_count > 0:
            if crime_count < 100:
                safety_desc = f"very safe area with only {crime_count} reported incidents in the past 6 months"
            elif crime_count < 200:
                safety_desc = f"moderate urban safety level with {crime_count} incidents over 6 months"
            else:
                safety_desc = f"higher crime area with {crime_count} incidents in 6 months"
            
            trend_desc = f"({crime_trend} trend)"
            
            if top_crimes:
                crime_types = " and ".join(top_crimes[:2])
                explanation_parts.append(f"**Safety**: This is a {safety_desc} {trend_desc}. Most common issues: {crime_types}.")
            else:
                explanation_parts.append(f"**Safety**: This is a {safety_desc} {trend_desc}.")
        
        if description and len(description) > 20:
            desc_lower = description.lower()
            highlights = []
            
            if user_cares_about_modern:
                if 'newly renovated' in desc_lower or 'new build' in desc_lower:
                    highlights.append("newly renovated")
                elif 'modern' in desc_lower:
                    highlights.append("modern")
            
            if 'garden' in desc_lower:
                highlights.append("garden")
            if 'balcony' in desc_lower or 'terrace' in desc_lower:
                highlights.append("balcony/terrace")
            if 'parking' in desc_lower:
                highlights.append("parking")
            if 'furnished' in desc_lower:
                highlights.append("furnished")
            if user_cares_about_quiet and 'quiet' in desc_lower:
                highlights.append("quiet street")
            if 'period' in desc_lower or 'victorian' in desc_lower:
                highlights.append("period features")
            
            if highlights:
                explanation_parts.append(f"Features: {', '.join(highlights[:4])}.")
        
        explanation = " ".join(explanation_parts)
        
        recommendations.append({
            'rank': i + 1,
            'address': address,
            'price': price,
            'travel_time': f"{travel_time} minutes" if isinstance(travel_time, (int, float)) else str(travel_time),
            'explanation': explanation,
            'url': _get_property_url(prop),
            'images': prop.get('Images', [])
        })
    
    print(f"   ✓ Created {len(recommendations)} context-aware recommendations")
    return {'recommendations': recommendations}