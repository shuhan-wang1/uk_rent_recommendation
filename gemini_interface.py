# gemini_interface.py

import google.generativeai as genai
from config import GEMINI_API_KEY
import json

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-lite')

# ... (clarify_and_extract_criteria 和 refine_criteria_with_answer 函数保持不变) ...
def clarify_and_extract_criteria(user_query: str) -> dict:
    prompt = f"""
    You are an expert rental assistant. Your job is to analyze a user's request and determine if you have enough information to perform a search, or if you need to ask a clarifying question.
    The user's request is: "{user_query}"
    You MUST return a single valid JSON object.
    1.  First, analyze the query for the following CORE CRITERIA:
        - "destination": A specific address or landmark in the UK.
        - "max_budget": The maximum monthly rent in GBP.
        - "max_travel_time": The maximum commute time in minutes.
    2.  Next, identify any SOFT PREFERENCES, like:
        - "property_style": e.g., "modern", "newly renovated", "with a balcony", "quiet".
        - "area_vibe": e.g., "lively area", "family-friendly", "good for young professionals".
        - "priorities": What is most important? e.g., "low budget is key", "fast commute is a must".
    3.  Based on your analysis, decide the "status":
        - If "destination", "max_budget", AND "max_travel_time" are clearly stated, the status is "success".
        - If any of the CORE CRITERIA are missing or ambiguous (e.g., "near the city centre", "cheap", "not too far"), the status is "clarification_needed".
    4.  Structure your response:
        - If status is "success":
          Return a JSON object with "status": "success" and a "data" object containing all extracted core criteria and soft preferences.
          Example:
          {{
            "status": "success",
            "data": {{
              "destination": "UCL, Gower Street, London",
              "max_budget": 1800,
              "max_travel_time": 30,
              "soft_preferences": "Looking for a modern, quiet apartment. Good access to supermarkets and parks is important. Crime rate is a concern."
            }}
          }}
        - If status is "clarification_needed":
          Return a JSON object with "status": "clarification_needed" and a "data" object containing a single key "question" with a friendly, specific question to ask the user.
          Example for query "Find me a flat near central London":
          {{
            "status": "clarification_needed",
            "data": {{
              "question": "I can certainly help with that! To get started, could you please provide a more specific destination, like a station or an address? Also, what is your maximum monthly budget and desired commute time?"
            }}
          }}
    Return ONLY the JSON object.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing JSON from Gemini (clarify_and_extract): {e}")
        return {"status": "error", "data": {"message": str(e)}}

def refine_criteria_with_answer(original_query: str, user_answer: str) -> dict:
    combined_query = f"Original request was: '{original_query}'. My answer to your clarification question is: '{user_answer}'."
    print(f"\n[Gemini] Refining criteria with combined query: {combined_query}")
    return clarify_and_extract_criteria(combined_query)


def generate_recommendations(properties_data: list[dict], user_query: str, soft_preferences: str) -> dict | None:
    """
    根据最终候选房源和用户的软偏好生成排名和解释。
    (PROMPT 已更新以处理新的犯罪数据)
    """
    prompt = f"""
    You are a helpful London apartment recommendation assistant.
    The user's original request was: "{user_query}"
    The user's key preferences are: "{soft_preferences}"

    Here is a list of available apartments. Crucially, each property now includes a `crime_data_summary` object from the official police API.
    `crime_data_summary` contains `total_crimes` and a `category_breakdown` for the most recent available month.
    {json.dumps(properties_data, indent=2)}

    Your task is to:
    1.  Analyze the provided list of apartments.
    2.  Rank the top 3 to 5 apartments that are MOST SUITABLE for the user.
    3.  For each recommended apartment, provide a detailed, personalized explanation.
        - **Crucially, you MUST now use the `crime_data_summary` to give a concrete, data-driven assessment of safety.**
        - If the user expressed concern about crime, directly address it using the new data. For example: "Regarding your concern for safety, the area around this property reported a total of [total_crimes] crimes last month, with the most common incidents being [category_breakdown]. You can use this official data to help your decision."
        - If the total crime number is low (e.g., under 30 for a specific spot in London), you can frame it positively. If it's high (e.g., over 100), you should mention it as a potential trade-off.
        - If the crime data has an "error" key, you should state that "Official crime data for this exact location could not be retrieved." Do NOT say it's unavailable.
        - Continue to use all other data points (travel time, nearby places, price) to support your explanation, directly referencing the user's preferences.

    Return your answer as a single, valid JSON object with a key "recommendations".
    Each item in the "recommendations" list should be an object with the keys: "rank", "address", "price", "travel_time", and "explanation".

    Return ONLY the JSON object.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing JSON from Gemini recommendation response: {e}")
        return None