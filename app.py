# app.py

import asyncio
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
# Switching to ollama_interface for local, free LLM usage
# from gemini_interface import clarify_and_extract_criteria
from ollama_interface import clarify_and_extract_criteria

from interactive_main import find_apartments_interactive


app = Flask(__name__, template_folder='.')
CORS(app)

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('apartment-finder-ui.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint that replicates the logic from interactive_main.py."""
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({"error": "A search query is required."}), 400

    user_query = data.get('query')
    print(f"Received query from UI: {user_query}")

    try:
        # Step 1: Use Gemini to extract criteria.
        response = clarify_and_extract_criteria(user_query)

        if response.get('status') != 'success':
            return jsonify({"error": "Could not understand the request. Please be more specific."}), 400

        criteria = response['data']
        print(f"Gemini extracted criteria: {json.dumps(criteria, indent=2)}")

        # Step 2: Run the apartment finding logic.
        # This function is now guaranteed to return a tuple.
        recommendations, final_candidates = asyncio.run(find_apartments_interactive(criteria))
        
        # FIX: Check if the recommendations object is valid before returning.
        if recommendations and 'recommendations' in recommendations:
            return jsonify(recommendations)
        else:
            # If no recommendations were generated, return a valid JSON structure with an empty list.
            return jsonify({"recommendations": []})

    except Exception as e:
        print(f"An error occurred in app.py: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)