# app.py - Enhanced with Web Search for Chat

import asyncio
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
from ollama_interface import clarify_and_extract_criteria, call_ollama
from interactive_main import find_apartments_interactive
from user_session import add_to_favorites, get_favorites, _session_data
from web_search import get_search_snippets
from free_maps_service import get_crime_data_by_location
import re

app = Flask(__name__, template_folder='.')
CORS(app)

# Store last search results for chat context
last_search_results = []

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('apartment-finder-ui.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint that replicates the logic from interactive_main.py."""
    global last_search_results
    
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({"error": "A search query is required."}), 400

    user_query = data.get('query')
    print(f"Received query from UI: {user_query}")

    try:
        response = clarify_and_extract_criteria(user_query)
        print(f"[DEBUG] Ollama response: {json.dumps(response, indent=2)}")

        if response.get('status') == 'clarification_needed':
            return jsonify(response), 200

        if response.get('status') == 'error':
            error_msg = response.get('data', {}).get('message', 'Unknown error') if isinstance(response.get('data'), dict) else 'Unknown error'
            return jsonify({"error": error_msg}), 400

        criteria = None
        
        if response.get('status') and 'success' in response.get('status'):
            criteria = {k: v for k, v in response.items() if k != 'status'}
            print("[DEBUG] Extracted criteria from top-level response")
        
        if not criteria:
            print(f"[ERROR] Could not extract criteria from response")
            return jsonify({"error": "Could not understand the request. Please be more specific."}), 400

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

        recommendations, final_candidates = asyncio.run(find_apartments_interactive(criteria))
        
        # Store results for chat context
        if recommendations and 'recommendations' in recommendations:
            last_search_results = recommendations['recommendations']
            return jsonify(recommendations)
        else:
            last_search_results = []
            return jsonify({"recommendations": []})

    except Exception as e:
        print(f"❌ An error occurred in app.py: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500

def markdown_to_html(text):
    """Convert markdown-style formatting to HTML"""
    # Bold text
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Line breaks
    text = text.replace('\n', '<br>')
    return text

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Enhanced chat endpoint with web search and context awareness"""
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({"error": "Message is required"}), 400
    
    user_message = data.get('message')
    context = data.get('context', {})
    
    try:
        # Your updated list of keywords
        search_keywords = ['cost of living', 'crime rate', 'crime', 'safe', 'safety', 'area like', 'neighborhood', 'transport', 'schools', 'restaurants','supermarkets','vibe','vibrant','bus','tube','train']
        needs_search = any(keyword in user_message.lower() for keyword in search_keywords)
        
        system_prompt = """You are Alex, a friendly and knowledgeable UK rental assistant. 
        You help users understand property listings, compare options, and make informed decisions.
        Be conversational, helpful, and specific. Use the information provided to give detailed answers.
        When discussing properties, reference specific details like address, price, and travel time."""
        
        prompt = user_message
        
        if needs_search and context.get('property'):
            address = context['property'].get('address', '')
            
            if 'cost of living' in user_message.lower():
                search_results = get_search_snippets(f"cost of living near {address} London", max_results=3)
                prompt = f"""The user is asking: "{user_message}"
Property: {address}
Web search results about cost of living:
{search_results}
Please provide a helpful answer based on these search results."""
            
            elif any(word in user_message.lower() for word in ['crime', 'safe', 'safety']):
                crime_data = get_crime_data_by_location(address)
                prompt = f"""The user is asking: "{user_message}"
Property: {address}
Crime statistics for this area:
- Total crimes in last 6 months: {crime_data.get('total_crimes_6m', 'Unknown')}
- Crime trend: {crime_data.get('crime_trend', 'Unknown')}
Please provide a helpful answer based on these statistics."""
            
            elif any(word in user_message.lower() for word in ['area like', 'neighborhood', 'vibe', 'vibrant']):
                search_results = get_search_snippets(f"{address} London area guide neighborhood", max_results=3)
                prompt = f"""The user is asking: "{user_message}"
Property: {address}
Web search results about the area:
{search_results}
Please provide a helpful answer based on these search results."""
            
            # **NEW CATCH-ALL BLOCK**
            # If the query needs a search but isn't one of the specific cases above,
            # perform a general search.
            else:
                search_query = f"{user_message} near {address}"
                search_results = get_search_snippets(search_query, max_results=4)
                prompt = f"""The user is asking: "{user_message}"
Property: {address}
Here is what a web search found:
{search_results}
Please use these search results to give a helpful and factual answer."""

        elif context.get('property'):
            prop = context['property']
            prompt = f"""The user is asking about this property:
Address: {prop.get('address', 'N/A')}
Price: {prop.get('price', 'N/A')}
Travel Time: {prop.get('travel_time', 'N/A')}
User's question: {user_message}
Please provide a helpful, detailed response."""
        
        response_text = call_ollama(prompt, system_prompt=system_prompt, timeout=300000)
        
        if response_text:
            formatted_response = markdown_to_html(response_text)
            return jsonify({"response": formatted_response})
        else:
            return jsonify({"error": "Could not get response from AI"}), 500
            
    except Exception as e:
        print(f"❌ Chat error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
@app.route('/api/favorites', methods=['POST'])
def add_favorite():
    """Add a property to favorites"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        add_to_favorites(data)
        return jsonify({"success": True, "message": "Added to favorites"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/favorites', methods=['GET'])
def get_favorites_list():
    """Get all favorited properties"""
    try:
        favorites = get_favorites()
        return jsonify({"favorites": favorites})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/favorites/<path:url>', methods=['DELETE'])
def remove_favorite(url):
    """Remove a property from favorites"""
    try:
        if url in _session_data['favorites']:
            del _session_data['favorites'][url]
            return jsonify({"success": True, "message": "Removed from favorites"})
        return jsonify({"error": "Property not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_search_history():
    """Get search history"""
    try:
        history = _session_data.get('search_history', [])
        return jsonify({"history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, port=5001)