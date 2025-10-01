# app.py - Enhanced with RAG as per Claude's instructions

import asyncio
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
from ollama_interface import clarify_and_extract_criteria, generate_recommendations, call_ollama
from user_session import add_to_favorites, get_favorites, _session_data
from web_search import get_search_snippets
from free_maps_service import get_crime_data_by_location
import re

# RAG Imports from new files
from data_loader import load_mock_properties_from_csv
from rag_coordinator import RAGCoordinator
from enrichment import enrich_property_data

app = Flask(__name__, template_folder='.')
CORS(app)

# --- RAG Setup as per markdown ---
# Initialize the coordinator and build the index at startup
print("[STARTUP] Initializing RAG Coordinator...")
try:
    rag_coordinator = RAGCoordinator()
except Exception as e:
    print(f"❌ FATAL ERROR during RAG initialization:")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error message: {str(e)}")
    import traceback
    traceback.print_exc()
    raise  # Re-raise to see full stack trace
rag_coordinator = RAGCoordinator()
all_properties = load_mock_properties_from_csv()
if all_properties:
    print("[STARTUP] Building FAISS index for property embeddings... (This may take a moment)") # <-- ADDED THIS LINE
    rag_coordinator.property_store.build_index(all_properties)
    print("✓ [STARTUP] FAISS index built successfully. Starting server...") # <-- ADDED THIS LINE
# ------------------------------------

# Store last search results for chat context
last_search_results = []

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('apartment-finder-ui.html')

def generate_recommendations_with_rag(properties: list[dict], user_query: str, past_conversations: list[str], area_knowledge: list[dict]) -> dict | None:
    """
    Generates recommendations using the original function but enriches the prompt
    with context from the RAG system, as described in the markdown.
    """
    # Create a richer context for the recommendation engine
    # This context will be passed as 'soft_preferences' to the existing function
    contextual_prompt = f"""
    User's original query: "{user_query}"
    Relevant information from past conversations:
    - {" ".join(past_conversations)}

    Additional context about the target search area:
    - {json.dumps(area_knowledge, indent=2)}
    """
    
    # Call the original recommendation function from ollama_interface
    # The 'user_query' is still passed for core criteria, and the new contextual_prompt
    # enriches the 'soft_preferences' part.
    return generate_recommendations(properties, user_query, contextual_prompt)


@app.route('/api/search', methods=['POST'])
async def api_search():
    """
    API endpoint enhanced with the RAG workflow.
    """
    global last_search_results
    
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({"error": "A search query is required."}), 400

    user_query = data.get('query')
    print(f"Received query from UI: {user_query}")

    try:
        # 1. Extract criteria
        criteria_response = clarify_and_extract_criteria(user_query)
        print(f"[DEBUG] Ollama criteria response: {json.dumps(criteria_response, indent=2)}")

        if criteria_response.get('status') != 'success':
            return jsonify(criteria_response), 200

        criteria = criteria_response

        # 2. RAG-enhanced retrieval
        print("\nStep 2: Performing RAG-enhanced retrieval...")
        ranked_properties, past_context, area_info = rag_coordinator.enhanced_search(
            user_query, criteria
        )
        print(f" -> Found {len(ranked_properties)} semantically similar properties.")
        
        # 3. CALCULATE TRAVEL TIMES for top candidates
        print("\nStep 3: Calculating travel times for top candidates...")
        top_candidates = ranked_properties[:15]  # Check more to ensure we get 5 within time limit
        
        destination = criteria.get('destination', 'University College London')
        max_travel_time = criteria.get('max_travel_time', 40)
        
        # Calculate travel times concurrently
        from travel_service import calculate_travel_time
        loop = asyncio.get_event_loop()
        
        travel_time_tasks = [
            loop.run_in_executor(
                None,
                calculate_travel_time,
                prop.get('Address', ''),
                destination
            )
            for prop in top_candidates
        ]
        
        travel_times = await asyncio.gather(*travel_time_tasks, return_exceptions=True)
        
        # Filter by travel time and add to properties
        candidates_with_travel = []
        for prop, travel_time in zip(top_candidates, travel_times):
            if isinstance(travel_time, Exception):
                print(f"  ⚠️  Travel time error for {prop.get('Address', '')[:50]}: {travel_time}")
                continue
            
            if travel_time and travel_time <= max_travel_time:
                prop['travel_time_minutes'] = travel_time
                candidates_with_travel.append(prop)
                print(f"  ✓ {prop.get('Address', '')[:50]}: {travel_time} mins")
            else:
                print(f"  ✗ {prop.get('Address', '')[:50]}: {travel_time} mins (too far)")
        
        if not candidates_with_travel:
            return jsonify({
                "recommendations": [],
                "message": "No properties found within your travel time requirement."
            })
        
        # 4. Enrich top 5 with web data
        print(f"\nStep 4: Enriching top {min(5, len(candidates_with_travel))} candidates...")
        top_5 = candidates_with_travel[:5]
        enriched_candidates = await asyncio.gather(*[
            enrich_property_data(prop, criteria) for prop in top_5
        ])
        
        # 5. Generate recommendations with context from RAG
        print("\nStep 5: Generating recommendations with RAG context...")
        recommendations = generate_recommendations_with_rag(
            properties=enriched_candidates,
            user_query=user_query,
            past_conversations=past_context,
            area_knowledge=area_info
        )
        
        # 6. Store conversation for future retrieval
        print("\nStep 6: Storing interaction in conversation memory...")
        rag_coordinator.conversation_memory.add_interaction(
            user_query, 
            json.dumps(recommendations),
            metadata=criteria
        )
        
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
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
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