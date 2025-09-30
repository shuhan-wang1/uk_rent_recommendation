# app.py - Fixed to handle Ollama's response structure

import asyncio
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
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
        # Step 1: Use Ollama to extract criteria
        response = clarify_and_extract_criteria(user_query)
        print(f"[DEBUG] Ollama response: {json.dumps(response, indent=2)}")

        # Handle clarification needed
        if response.get('status') == 'clarification_needed':
            return jsonify(response), 200

        # Handle error status
        if response.get('status') == 'error':
            error_msg = response.get('data', {}).get('message', 'Unknown error') if isinstance(response.get('data'), dict) else 'Unknown error'
            return jsonify({"error": error_msg}), 400

        # Extract criteria - Ollama puts data at top level when status is success
        criteria = None
        
        if response.get('status') == 'success':
            # Check if data is nested under 'data' key
            if 'data' in response and isinstance(response['data'], dict):
                criteria = response['data']
            else:
                # Data is at top level - extract everything except 'status'
                criteria = {k: v for k, v in response.items() if k != 'status'}
                print("[DEBUG] Extracted criteria from top-level response")
        
        # Validate we got criteria
        if not criteria:
            print(f"[ERROR] Could not extract criteria from response")
            return jsonify({"error": "Could not understand the request. Please be more specific."}), 400

        # Validate criteria has required fields
        required_fields = ['destination', 'max_budget', 'max_travel_time']
        missing_fields = [f for f in required_fields if f not in criteria]
        
        if missing_fields:
            print(f"[ERROR] Missing required fields: {missing_fields}")
            return jsonify({
                "status": "clarification_needed",
                "data": {
                    "question": f"To find the best apartments, please provide: {', '.join(missing_fields)}"
                }
            }), 200

        print(f"✓ Extracted criteria: {json.dumps(criteria, indent=2)}")

        # Step 2: Run the apartment finding logic
        recommendations, final_candidates = asyncio.run(find_apartments_interactive(criteria))
        
        if recommendations and 'recommendations' in recommendations:
            return jsonify(recommendations)
        else:
            return jsonify({"recommendations": []})

    except Exception as e:
        print(f"❌ An error occurred in app.py: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)