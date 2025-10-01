# gemini_interface.py

import google.generativeai as genai
from config import GEMINI_API_KEY
import json
import re

genai.configure(api_key=GEMINI_API_KEY)
# 建议使用更高版本的模型以获得更好的性能和JSON输出能力
model = genai.GenerativeModel('gemini-2.0-flash-lite')

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
    try:
        response = model.generate_content(prompt)
        # A more robust way to clean potential markdown formatting
        cleaned_response = re.search(r'```json\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if cleaned_response:
            return json.loads(cleaned_response.group(1))
        else:
            # Fallback for when the model doesn't use markdown
            return json.loads(response.text)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing JSON from Gemini (clarify_and_extract): {e}")
        return {{"status": "error", "data": {{"message": str(e)}}}}

def refine_criteria_with_answer(original_query: str, user_answer: str) -> dict:
    combined_query = f"My original request was: '{{original_query}}'. In response to your question, here is more information: '{{user_answer}}'."
    print(f"\n[Gemini] Refining criteria with combined query: {{combined_query}}")
    return clarify_and_extract_criteria(combined_query)

def extract_tags_from_description(description: str) -> dict:
    """
    NEW FUNCTION: Uses Gemini to extract structured tags from a property's free-text description.
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
    try:
        response = model.generate_content(prompt)
        cleaned_response = re.search(r'```json\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if cleaned_response:
            return json.loads(cleaned_response.group(1))
        else:
            return json.loads(response.text)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error extracting tags from description: {e}")
        return {{}}


def generate_recommendations(properties_data: list[dict], user_query: str, soft_preferences: str) -> dict | None:
    """
    MODIFIED: The prompt is now significantly more powerful.
    It instructs the model to act as a persona (a helpful assistant) and to use ALL the newly
    enriched data points (environment, crime trends, amenities, extracted tags) to create a
    holistic and deeply personalized recommendation. It also explicitly asks for the URL.
    """
    prompt = f"""
    You are Alex, a helpful and insightful London apartment recommendation assistant.
    The user's original request was: "{user_query}"
    The user's key preferences are: "{soft_preferences}"

    Here is a list of final candidate apartments. Each property has been enriched with detailed data including travel times, crime statistics (including trends), nearby amenities, environmental quality, and tags extracted from its description.
    {json.dumps(properties_data, indent=2)}

    Your task is to:
    1.  **Adopt the Persona of Alex**: Write a friendly, engaging, and trustworthy analysis.
    2.  **Deeply Analyze**: Go beyond just listing facts. Synthesize all the provided data points to form a compelling narrative for why each property is a good match. For example, connect a low crime trend with the user's preference for a 'quiet area', or highlight the number of nearby gyms if they are interested in fitness.
    3.  **Rank the Top 3-5 Apartments**: The ranking should be based on the best overall fit for the user's stated and inferred needs.
    4.  **Provide Detailed Explanations**: For each recommended apartment, your explanation MUST be personalized and justify the ranking by referencing multiple data points like:
        - The **commute time** and its convenience.
        - The **crime data**, paying special attention to the **crime_trend**.
        - The specific **amenities_nearby** that match the user's interests.
        - The **environmental quality** (air quality, green space).
        - Key **description_tags** like 'newly_renovated' or 'balcony'.
        - How the price fits within their budget.

    Return your answer as a single, valid JSON object with a key "recommendations".
    Each item in the list MUST have these exact keys: "rank", "address", "price", "travel_time", "explanation", and "url".

    Return ONLY the JSON object.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = re.search(r'```json\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if cleaned_response:
            return json.loads(cleaned_response.group(1))
        else:
            return json.loads(response.text)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing JSON from Gemini recommendation response: {e}")
        return None