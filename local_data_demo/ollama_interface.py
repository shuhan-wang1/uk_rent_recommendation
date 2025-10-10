# ollama_interface.py - COMPLETE UPDATED VERSION

import json
import re
import requests

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2:1b"  # Change to your model (qwen2.5:1.5b, llama3.2:3b, etc.)

USE_FINETUNED_MODEL = True
# ========================================
FINETUNED_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"  # or path to Ollama's download
FINETUNED_ADAPTER_PATH = "./student_model_lora/"     # Your LoRA adapters directory
# ========================================
  # Default model if not using fine-tuned


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
    
    # DEBUG: Print what we're sending
    print(f"[DEBUG] Ollama URL: {url}")
    print(f"[DEBUG] Model: {MODEL_NAME}")
    print(f"[DEBUG] Prompt length: {len(prompt)} chars")
    print(f"[DEBUG] Has system prompt: {system_prompt is not None}")
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        
        # DEBUG: Print response status
        print(f"[DEBUG] Response status: {response.status_code}")
        
        response.raise_for_status()  # This line throws the 404 error
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.HTTPError as e:
        print(f"❌ Ollama HTTP error: {e}")
        print(f"[DEBUG] Response text: {response.text[:500]}")
        return None
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
    """Extract criteria from user query - now supports fine-tuned model"""
    
    
    if USE_FINETUNED_MODEL:
        try:
            print("[INFO] Attempting to use fine-tuned model...")
            from finetuned_parser import get_finetuned_parser
            
            parser = get_finetuned_parser(FINETUNED_BASE_MODEL, FINETUNED_ADAPTER_PATH)
            result = parser.parse_query(user_query)
            
            print("[INFO] ✓ Used fine-tuned model for parsing")
            
            # Validate result has required fields
            if result.get('status') == 'success':
                required = ['destination', 'max_budget', 'max_travel_time']
                if all(result.get(field) for field in required):
                    return result
                else:
                    print("[WARN] Fine-tuned model missing required fields, falling back to Ollama")
            elif result.get('status') == 'error':
                print(f"[WARN] Fine-tuned model returned error: {result.get('data', {}).get('message')}")
                print("[INFO] Falling back to Ollama")
            
        except ImportError as e:
            print(f"[ERROR] Could not import finetuned_parser: {e}")
            print("[INFO] Falling back to Ollama")
        except Exception as e:
            print(f"[ERROR] Fine-tuned model failed: {e}")
            import traceback
            traceback.print_exc()
            print("[INFO] Falling back to Ollama")
    else:
        print("[INFO] Using Ollama (USE_FINETUNED_MODEL = False)")
    
    # EXISTING: Original Ollama-based parsing (fallback)
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
    
    parsed_json = extract_first_json(response_text)
    
    if parsed_json:
        if "$schema" in parsed_json or "properties" in parsed_json:
            print("[WARN] Got schema instead of data, retrying with simple prompt")
            return retry_with_simple_prompt(user_query)
        
        required = ['destination', 'max_budget', 'max_travel_time']
        has_required = all(parsed_json.get(field) for field in required)
        
        if has_required:
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
    """Generate personalized property recommendations with natural explanations"""

    print(f"\n🤖 [RECOMMENDATION ENGINE] Starting...")
    print(f"   Properties to analyze: {len(properties_data)}")

    if not properties_data:
        return {"recommendations": []}

    top_props = properties_data[:5]
    
    # Prepare property data for the model
    simple_props = []
    for i, prop in enumerate(top_props):
        url = _get_property_url(prop)
        travel_time = prop.get('travel_time_minutes', 'N/A')
        images = prop.get('Images', [])
        
        # Extract crime data
        crime_data = prop.get('crime_data_summary', {})
        crimes = crime_data.get('total_crimes_6m', 0)
        crime_trend = crime_data.get('crime_trend', 'unknown')
        top_crime_types = crime_data.get('top_crime_types', [])
        
        # Extract amenities
        amenities = prop.get('amenities_nearby', {})
        
        simple_prop = {
            'id': i + 1,
            'address': prop.get('Address', 'Unknown')[:70],
            'price': prop.get('Price', 'N/A'),
            'price_numeric': prop.get('parsed_price', 0),
            'url': url,
            'travel_time_minutes': travel_time,
            'crimes_6m': crimes,
            'crime_trend': crime_trend,
            'top_crime_types': top_crime_types[:2],  # Top 2 crime types
            'nearby_supermarkets': amenities.get('supermarket_in_1500m', 0),
            'nearby_parks': amenities.get('park_in_1500m', 0),
            'nearby_gyms': amenities.get('gym_in_1500m', 0),
            'description': prop.get('Description', '')[:200],
            'images': images
        }
        simple_props.append(simple_prop)

    # IMPROVED PROMPT: More natural, conversational
    system_prompt = """You are Alex, a friendly and knowledgeable London rental assistant with years of experience helping people find their perfect home. 

Your task is to write engaging, personalized property recommendations that feel like advice from a trusted friend who really understands the London rental market.

CRITICAL RULES:
1. Write in a warm, conversational tone - like you're talking to a friend
2. Tell a story about each property - don't just list facts
3. Compare properties naturally (e.g., "While Property 1 is closer, Property 2 offers better value...")
4. Be honest about downsides (high crime, expensive, etc.) but frame them constructively
5. Use specific numbers to back up your points, but weave them into the narrative
6. Consider the user's priorities and explain WHY each property matches or doesn't match
7. Each explanation should be 3-5 sentences, not just one sentence of facts"""

    # Extract key user concerns
    user_concerns = []
    if soft_preferences:
        sp_lower = soft_preferences.lower()
        if 'crime' in sp_lower or 'safe' in sp_lower:
            user_concerns.append("safety and low crime")
        if 'quiet' in sp_lower:
            user_concerns.append("a quiet neighborhood")
        if 'modern' in sp_lower:
            user_concerns.append("modern amenities")
        if 'pet' in sp_lower or 'dog' in sp_lower or 'cat' in sp_lower:
            user_concerns.append("pet-friendly properties")

    concerns_text = ", ".join(user_concerns) if user_concerns else "good value and convenience"

    prompt = f"""The user is searching for a London rental with these priorities: {concerns_text}.
Their original query: "{user_query}"

Here are the top 5 properties that match their criteria:

{json.dumps(simple_props, indent=2)}

YOUR TASK:
Recommend the TOP 3 properties. For each one, write a natural, engaging explanation that:
- Starts with why this property stands out
- Discusses the commute (is it quick? convenient?)
- Addresses safety honestly (use the actual crime numbers and trend)
- Mentions value for money (is it a good deal for the area?)
- Notes any standout features (nearby amenities, description highlights)
- Ends with who this property is perfect for

EXAMPLE OF GOOD EXPLANATION:
"This flat in Camden really caught my eye because of its unbeatable 20-minute commute to UCL - you'll actually have time for morning coffee! The area has seen 76 reported crimes over the past 6 months with an increasing trend, which is something to be aware of, but it's typical for this vibrant neighborhood. At £1,850 per month, you're getting solid value for such a convenient location, plus there are 3 supermarkets and 2 parks within walking distance. This is perfect for someone who prioritizes convenience over a super quiet area."

EXAMPLE OF BAD EXPLANATION:
"20-minute commute, 76 crimes (increasing), £1,850 per month. 3 supermarkets nearby."

Now write recommendations for the top 3 properties in this natural, helpful style.

Return ONLY this JSON structure:
{{
  "recommendations": [
    {{
      "rank": 1,
      "address": "full address from data",
      "price": "£X pcm",
      "travel_time": "X minutes",
      "explanation": "Your engaging 3-5 sentence explanation here",
      "url": "property url"
    }},
    {{
      "rank": 2,
      ...
    }},
    {{
      "rank": 3,
      ...
    }}
  ]
}}

Return ONLY valid JSON, no other text."""

    # Call Ollama with longer timeout for better responses
    response_text = call_ollama(prompt, system_prompt, timeout=90)

    if not response_text:
        print("[INFO] Ollama failed, using rule-based recommendations")
        return create_fallback_recommendations(properties_data, soft_preferences)

    parsed = extract_first_json(response_text)

    if parsed and 'recommendations' in parsed:
        print("\n[DEBUG] Fixing travel times and images...")
        
        # Match recommendations back to original properties
        for rec in parsed['recommendations']:
            rank = rec.get('rank', 0)
            rec_address = rec.get('address', '').lower().strip()
            
            # Find matching property
            original_prop = None
            for prop in properties_data:
                prop_address = prop.get('Address', '').lower().strip()
                if rec_address[:30] in prop_address or prop_address[:30] in rec_address:
                    original_prop = prop
                    break
            
            if not original_prop and 1 <= rank <= len(properties_data):
                original_prop = properties_data[rank - 1]
            
            if original_prop:
                tt_mins = original_prop.get('travel_time_minutes')
                rec['travel_time'] = f"{tt_mins} minutes" if isinstance(tt_mins, (int, float)) else "N/A"
                rec['images'] = original_prop.get('Images', [])
                rec['url'] = original_prop.get('URL', rec.get('url', ''))
                rec['address'] = original_prop.get('Address', rec.get('address', ''))
                
                print(f"  ✓ Rank {rank}: {rec['address'][:40]} - {rec['travel_time']}")
        
        return parsed
    else:
        print("[WARN] Could not parse JSON, using fallback")
        return create_fallback_recommendations(properties_data, soft_preferences)

def create_fallback_recommendations(properties_data: list[dict], soft_preferences: str = "") -> dict:
    """High-quality fallback with natural explanations"""
    print("   🔧 Creating intelligent rule-based recommendations...")
    
    sorted_props = sorted(
        properties_data[:15],
        key=lambda x: (
            x.get('travel_time_minutes', 999),
            x.get('parsed_price', 9999)
        )
    )
    
    user_cares_about_crime = 'crime' in soft_preferences.lower() or 'safe' in soft_preferences.lower()
    
    recommendations = []
    for i, prop in enumerate(sorted_props[:5]):
        travel_time = prop.get('travel_time_minutes', 'N/A')
        price = prop.get('Price', 'N/A')
        parsed_price = prop.get('parsed_price', 0)
        address = prop.get('Address', 'Unknown')
        description = prop.get('Description', '')
        
        # Extract crime data
        crime_data = prop.get('crime_data_summary', {})
        crime_count = crime_data.get('total_crimes_6m', 0)
        crime_trend = crime_data.get('crime_trend', 'unknown')
        top_crimes = crime_data.get('top_crime_types', [])
        
        # Extract area name
        area_parts = address.split(',')
        area = area_parts[1].strip() if len(area_parts) > 1 else "the area"
        
        # Build natural explanation
        explanation_parts = []
        
        # Opening sentence - personalized based on rank
        if i == 0:
            explanation_parts.append(f"This is my top recommendation! Located in {area}, it offers the quickest commute at just {travel_time} minutes, which means you'll spend less time on the tube and more time enjoying London.")
        elif i == 1:
            explanation_parts.append(f"Coming in as a strong second choice, this {area} property provides a {travel_time}-minute commute - just a bit longer than my top pick but potentially worth it depending on your priorities.")
        elif i == 2:
            explanation_parts.append(f"Here's an interesting alternative in {area} with a {travel_time}-minute journey to UCL that offers some unique advantages.")
        else:
            explanation_parts.append(f"Option #{i+1} in {area} gives you a {travel_time}-minute commute and some features worth considering.")
        
        # Price and value
        if isinstance(travel_time, (int, float)) and parsed_price > 0 and travel_time > 0:
            value_score = parsed_price / travel_time
            if value_score < 60:
                explanation_parts.append(f"At {price}, this is exceptional value - you're getting a great location without breaking the bank.")
            elif value_score < 80:
                explanation_parts.append(f"Priced at {price}, it's competitively priced for the area and commute time.")
            else:
                explanation_parts.append(f"At {price}, this is at the premium end for the commute time, but that might reflect the quality or location.")
        else:
            explanation_parts.append(f"Priced at {price}.")
        
        # Safety discussion - always included but framed naturally
        if crime_count > 0:
            if crime_count < 100:
                explanation_parts.append(f"The neighborhood feels quite safe with only {crime_count} incidents reported over the past 6 months ({crime_trend} trend), which is below average for London.")
            elif crime_count < 200:
                explanation_parts.append(f"Safety-wise, there were {crime_count} incidents in the area over 6 months ({crime_trend} trend) - about average for a busy London neighborhood.")
            else:
                explanation_parts.append(f"I should mention that the area has seen {crime_count} incidents in the past 6 months ({crime_trend} trend), which is higher than some other neighborhoods, so security might be something to check when viewing.")
            
            if top_crimes:
                crime_types = " and ".join(top_crimes[:2]).lower()
                explanation_parts.append(f"Most incidents were {crime_types}.")
        elif crime_trend != 'unknown':
            explanation_parts.append(f"Great news on safety - no crimes were reported in this immediate area over the past 6 months!")
        
        # Property features from description
        if description and len(description) > 20:
            desc_lower = description.lower()
            highlights = []
            
            if 'newly renovated' in desc_lower or 'new build' in desc_lower:
                highlights.append("newly renovated")
            elif 'modern' in desc_lower:
                highlights.append("modern finish")
            
            if 'garden' in desc_lower:
                highlights.append("private garden")
            if 'balcony' in desc_lower or 'terrace' in desc_lower:
                highlights.append("balcony")
            if 'parking' in desc_lower:
                highlights.append("parking")
            
            if highlights:
                explanation_parts.append(f"Nice touches include: {', '.join(highlights[:3])}.")
        
        # Who it's perfect for
        if i == 0 and crime_count < 100 and travel_time < 25:
            explanation_parts.append(f"Perfect if you want the best of both worlds - safety and convenience.")
        elif parsed_price < 2000 and travel_time < 30:
            explanation_parts.append(f"Ideal for budget-conscious students who still want a reasonable commute.")
        
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
    
    print(f"   ✓ Created {len(recommendations)} natural recommendations")
    return {'recommendations': recommendations[:3]}  # Return top 3