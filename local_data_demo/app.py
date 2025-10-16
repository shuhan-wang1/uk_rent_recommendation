# app.py - Enhanced with RAG as per Claude's instructions

import asyncio
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
import re
from core.llm_interface import clarify_and_extract_criteria, generate_recommendations, call_ollama, refine_criteria_with_answer
from core.user_session import add_to_favorites, get_favorites, _session_data, set_pending_criteria, get_pending_criteria, clear_pending_criteria, has_pending_clarification, is_clarification_response
from core.web_search import get_search_snippets
from core.maps_service import get_crime_data_by_location
from core.data_loader import load_mock_properties_from_csv
from core.enrichment_service import enrich_property_data
from rag.rag_coordinator import RAGCoordinator
from core.tool_system import create_tool_registry

app = Flask(__name__, template_folder='.')
CORS(app)

# --- Tool System Setup (从 fengyuan-agent 迁移) ---
print("[STARTUP] Initializing Tool System...")
try:
    tool_registry = create_tool_registry()
    print(f"✓ [STARTUP] Tool System initialized with {len(tool_registry.tools)} tools")
except Exception as e:
    print(f"⚠️  [STARTUP] Warning: Tool System initialization failed: {e}")
    tool_registry = None

# --- RAG Setup as per markdown ---
# Initialize the coordinator and build the index at startup
print("[STARTUP] Initializing RAG Coordinator...")
try:
    rag_coordinator = RAGCoordinator()
    print("✓ [STARTUP] RAGCoordinator initialized successfully")
except Exception as e:
    print(f"❌ FATAL ERROR during RAG initialization:")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error message: {str(e)}")
    import traceback
    traceback.print_exc()
    raise  # Re-raise to see full stack trace

print("[STARTUP] Loading mock properties from CSV...")
all_properties = load_mock_properties_from_csv()
print(f"✓ [STARTUP] Loaded {len(all_properties)} properties from CSV")

# ✅ FIXED: 确保在建立索引前处理所有属性，添加 parsed_price
if all_properties:
    from core.data_loader import parse_price
    for prop in all_properties:
        if 'parsed_price' not in prop:
            prop['parsed_price'] = parse_price(prop.get('Price'))

if all_properties:
    print("[STARTUP] Building FAISS index for property embeddings... (This may take a moment)")
    try:
        rag_coordinator.property_store.build_index(all_properties)
        print("✓ [STARTUP] FAISS index built successfully. Starting server...")
    except Exception as e:
        print(f"❌ ERROR building FAISS index: {e}")
        import traceback
        traceback.print_exc()
        raise
else:
    print("⚠️  WARNING: No properties loaded from CSV. RAG search may not work properly.")
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
    ✅ FIXED: 现在支持澄清流程 (clarification flow)
    
    流程:
    1. 新查询 -> 调用 clarify_and_extract_criteria()
       - 如果返回 clarification_needed -> 保存到 pending_criteria，返回澄清问题
       - 如果返回 success -> 进行搜索
    
    2. 澄清回复 -> 调用 refine_criteria_with_answer()
       - 合并用户回复，返回完整条件
       - 进行搜索
    """
    global last_search_results
    
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({"error": "A search query is required."}), 400

    user_query = data.get('query')
    print(f"\n{'='*60}")
    print(f"[API] Received query from UI: {user_query}")
    print(f"[API] Has pending clarification: {has_pending_clarification()}")
    print(f"{'='*60}")

    try:
        # ✅ 步骤 0: 检查是否是对澄清问题的回复
        if has_pending_clarification() and is_clarification_response(user_query):
            print("[API] ✓ 这是对澄清问题的回复")
            pending = get_pending_criteria()
            print(f"[API] 原始条件: {json.dumps(pending, indent=2)}")
            
            # 使用 refine_criteria_with_answer() 来合并用户回复
            criteria_response = refine_criteria_with_answer(pending, user_query)
            print(f"[API] 合并后条件: {json.dumps(criteria_response, indent=2)}")
            
            # 如果合并后仍然需要澄清，返回新的澄清问题
            if criteria_response.get('status') != 'success':
                set_pending_criteria(criteria_response)
                return jsonify(criteria_response), 200
            
            # 否则清除待处理状态
            clear_pending_criteria()
            criteria = criteria_response
            
        else:
            # 新的搜索查询
            print("[API] → 这是新的搜索查询")
            criteria_response = clarify_and_extract_criteria(user_query)
            print(f"[DEBUG] 初始条件提取: {json.dumps(criteria_response, indent=2)}")

            # ✅ 如果需要澄清，保存到 pending_criteria 并返回澄清问题
            if criteria_response.get('status') != 'success':
                print("[API] → 需要澄清")
                set_pending_criteria(criteria_response)
                return jsonify(criteria_response), 200

            criteria = criteria_response

        # ✅ 到这里，我们有了成功的条件（status == 'success'）
        print("[API] ✓ 成功获得搜索条件，开始搜索...")

        # 2. RAG-enhanced retrieval
        print("\n[STEP 2] 执行 RAG 增强检索...")
        ranked_properties, past_context, area_info = rag_coordinator.enhanced_search(
            user_query, criteria
        )
        print(f" → 找到 {len(ranked_properties)} 个相似房源")
        
        # 3. CALCULATE TRAVEL TIMES for top candidates
        print("\n[STEP 3] 为前候选者计算出行时间...")
        top_candidates = ranked_properties[:15]  # Check more to ensure we get 5 within time limit
        
        destination = criteria.get('destination', 'University College London')
        max_travel_time = criteria.get('max_travel_time', 40)
        
        # Calculate travel times concurrently
        from core.maps_service import calculate_travel_time
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
                print(f"  ⚠️  出行时间错误 {prop.get('Address', '')[:50]}: {travel_time}")
                continue
            
            if travel_time and travel_time <= max_travel_time:
                prop['travel_time_minutes'] = travel_time
                candidates_with_travel.append(prop)
                print(f"  ✓ {prop.get('Address', '')[:50]}: {travel_time} 分钟")
            else:
                print(f"  ✗ {prop.get('Address', '')[:50]}: {travel_time} 分钟 (超过限制)")
        
        if not candidates_with_travel:
            return jsonify({
                "recommendations": [],
                "message": "No properties found within your travel time requirement."
            })
        
        # 4. Enrich top 5 with web data
        print(f"\n[STEP 4] 为前 {min(5, len(candidates_with_travel))} 个候选者充实数据...")
        top_5 = candidates_with_travel[:5]
        enriched_candidates = await asyncio.gather(*[
            enrich_property_data(prop, criteria) for prop in top_5
        ])
        
        # ✅ FIXED: 添加预算到每个属性，用于超预算解释
        max_budget = criteria.get('max_budget', 2000)
        for prop in enriched_candidates:
            prop['_max_budget'] = max_budget
        
        # 5. Generate recommendations with context from RAG
        print("\n[STEP 5] 基于 RAG 上下文生成建议...")
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
    """Enhanced chat endpoint with Tool System integration for multi-source POI search"""
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({"error": "Message is required"}), 400
    
    user_message = data.get('message')
    context = data.get('context', {})
    
    try:
        search_keywords = ['cost of living', 'crime rate', 'crime', 'safe', 'safety', 
                          'area like', 'neighborhood', 'transport', 'schools', 
                          'restaurants', 'supermarket', 'shop', 'store', 'grocery', 'lidl', 'aldi',
                          'vibe', 'vibrant', 'bus', 'tube', 'train',
                          'gym', 'fitness', 'health club', 'sports center', 'leisure',  # POI types
                          'park', 'green space', 'outdoor',
                          'restaurant', 'cafe', 'coffee', 'diner', 'eating',
                          'hospital', 'medical', 'doctor', 'clinic', 'health',
                          'library', 'books',
                          'school', 'primary', 'secondary', 'education']
        needs_search = any(keyword in user_message.lower() for keyword in search_keywords)
        
        system_prompt = """You are Alex, a friendly and knowledgeable UK rental assistant. 
        CRITICAL RULES:
        1. ONLY use data from the provided search results
        2. NEVER invent store names, distances, or locations
        3. If data is incomplete, say "Based on available data..." and be honest
        4. Always verify before claiming something is "nearby" """
        
        prompt = user_message
        
        if needs_search and context.get('property'):
            address = context['property'].get('address', '')
            
            # POI QUERY - Gym, Park, Restaurant, Hospital, etc.
            poi_keywords = {
                'gym': ['gym', 'fitness', 'health club', 'sports center', 'leisure'],
                'park': ['park', 'green space', 'outdoor'],
                'restaurant': ['restaurant', 'cafe', 'coffee', 'diner', 'eating'],
                'hospital': ['hospital', 'medical', 'doctor', 'clinic', 'health'],
                'library': ['library', 'books', 'library'],
                'school': ['school', 'primary', 'secondary', 'education'],
            }
            
            detected_poi = None
            for poi_type, keywords in poi_keywords.items():
                if any(keyword in user_message.lower() for keyword in keywords):
                    detected_poi = poi_type
                    break
            
            # GENERIC POI QUERY (GYM, PARK, RESTAURANT, HOSPITAL, ETC)
            if detected_poi:
                print(f"  [Overpass API] {detected_poi.upper()} search for: {address}")
                from core.maps_service import get_nearby_places_osm
                
                poi_data = get_nearby_places_osm(address, detected_poi, radius_m=1500)
                
                if poi_data and len(poi_data) > 0:
                    # Format the detailed location data
                    poi_text = "\n".join([
                        f"- {place['name']} - {place['distance_m']}m away ({round(place['distance_m']/1000, 1)}km)"
                        for place in poi_data[:10]  # Top 10
                    ])
                    
                    prompt = f"""The user asked: "{user_message}"
Property address: {address}

VERIFIED DATA (OpenStreetMap via Overpass API):
Found {len(poi_data)} {detected_poi} locations within 1.5km:

{poi_text}

INSTRUCTIONS:
1. List the {detected_poi} locations exactly as shown above with names and distances
2. Include distances in both meters and kilometers
3. Do NOT invent names or locations not in this list
4. Provide helpful context about which ones are closest
5. If user asks about travel time, explain that it depends on method (walking, cycling, public transport)

Provide a helpful, friendly response using ONLY this verified data."""
                else:
                    prompt = f"""The user asked: "{user_message}"
Property address: {address}

VERIFIED DATA (OpenStreetMap via Overpass API):
- Search result: NO {detected_poi} found within 1.5km of this address

INSTRUCTIONS:
1. Be honest that no {detected_poi} were found in the immediate area
2. Suggest expanding the search radius
3. Do NOT invent names or locations
4. Offer practical alternatives

Respond honestly and helpfully."""

            # SUPERMARKET/CHAIN QUERY - Now uses Tool System with multi-source search
            elif any(word in user_message.lower() for word in ['supermarket', 'shop', 'store', 'grocery', 'lidl', 'aldi']):
                print(f"  [Tool System] Supermarket search for: {address}")
                
                # 检测用户是否要找特定品牌
                chains_to_search = []
                if 'lidl' in user_message.lower():
                    chains_to_search.append('Lidl')
                if 'aldi' in user_message.lower():
                    chains_to_search.append('Aldi')
                if 'sainsbury' in user_message.lower():
                    chains_to_search.append('Sainsbury')
                if 'tesco' in user_message.lower():
                    chains_to_search.append('Tesco')
                
                # 如果没有指定特定品牌，使用默认列表
                if not chains_to_search:
                    chains_to_search = ['Lidl', 'Aldi', 'Sainsbury', 'Tesco']
                
                # 使用工具系统执行搜索（如果可用）
                supermarkets = []
                if tool_registry:
                    try:
                        # 通过 Tool System 执行异步搜索
                        async def run_tool_search():
                            result = await tool_registry.execute_tool(
                                'search_supermarkets',
                                address=address,
                                chains=chains_to_search,
                                radius_m=2000
                            )
                            return result.data if result.success else []
                        
                        # 在同步环境中运行异步任务
                        loop = None
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        supermarkets = loop.run_until_complete(run_tool_search())
                        print(f"  ✓ [Tool System] Found {len(supermarkets)} supermarkets")
                    except Exception as e:
                        print(f"  ⚠️  [Tool System] Tool execution failed: {e}, falling back to direct search")
                        from core.maps_service import get_nearby_supermarkets_detailed
                        supermarkets = get_nearby_supermarkets_detailed(address, radius=2000, chains=chains_to_search)
                else:
                    # Fallback if tool registry not available
                    from core.maps_service import get_nearby_supermarkets_detailed
                    supermarkets = get_nearby_supermarkets_detailed(address, radius=2000, chains=chains_to_search)
                
                if supermarkets:
                    # Format the data nicely
                    supermarket_text = "\n".join([
                        f"- {shop['name']} ({shop['type']}) - {shop['address']} - "
                        f"{('~' if shop.get('distance_m') is None else '')}{shop.get('distance_m', 'N/A')}m away"
                        for shop in supermarkets[:10]  # Top 10
                    ])
                    
                    prompt = f"""The user asked: "{user_message}"
Property address: {address}
Searching for chains: {', '.join(chains_to_search)}

VERIFIED SUPERMARKETS (multi-source: OSM + web fallback):
{supermarket_text}

Total found: {len(supermarkets)}

INSTRUCTIONS:
1. List the supermarkets exactly as shown above
2. Include their names, types, and distances
3. Do NOT add any stores not in this list
4. Highlight if this includes user-requested chains (e.g., Lidl, Aldi)
5. If no specific chains found, mention and suggest alternatives

Provide a helpful, friendly response using ONLY this verified data."""

                else:
                    prompt = f"""The user asked: "{user_message}"
Property address: {address}
Searched for: {', '.join(chains_to_search)}

Multi-source search result: NO supermarkets found within 2km (tried OSM and web search).

Respond honestly: "I searched multiple sources and couldn't find {', '.join(chains_to_search)} within 2km of this address. This could mean the area is underrepresented in public data. Would you like me to search a wider radius or look for alternatives?" """
            
            # TRANSPORT/TUBE QUERY
            elif any(word in user_message.lower() for word in ['tube', 'train', 'station', 'transport']):
                search_results = get_search_snippets(
                    f"nearest tube underground station to {address} London",
                    max_results=5
                )
                prompt = f"""The user asked: "{user_message}"
Property: {address}

Web search results about nearest stations:
{search_results}

CRITICAL RULES:
1. The STREET NAME does not determine the station name
2. "Kentish Town Road" does NOT mean "Kentish Town station" - check search results!
3. Only mention stations explicitly found in search results
4. Start with: "According to web search..."
5. If unclear, say: "The search results suggest... but I recommend verifying"

Answer based ONLY on the search results above."""
            
            # CRIME QUERY
            elif any(word in user_message.lower() for word in ['crime', 'safe', 'safety']):
                crime_data = get_crime_data_by_location(address)
                prompt = f"""The user asked: "{user_message}"
Property: {address}

Official UK Police data:
- Total crimes (last 6 months): {crime_data.get('total_crimes_6m', 'Unknown')}
- Crime trend: {crime_data.get('crime_trend', 'Unknown')}
- Top crime types: {crime_data.get('top_crime_types', [])}

Provide a balanced, factual response using this official data."""
            
            # COST OF LIVING QUERY
            elif 'cost of living' in user_message.lower():
                search_results = get_search_snippets(f"cost of living near {address} London", max_results=3)
                prompt = f"""User: "{user_message}"
Property: {address}
Web results: {search_results}
Answer based on these results."""
            
            # AREA/NEIGHBORHOOD QUERY
            elif any(word in user_message.lower() for word in ['area like', 'neighborhood', 'vibe', 'vibrant']):
                search_results = get_search_snippets(f"{address} London area guide neighborhood", max_results=3)
                prompt = f"""User: "{user_message}"
Property: {address}
Area information: {search_results}
Describe the area based on these results."""
            
            # GENERIC SEARCH
            else:
                search_query = f"{user_message} near {address}"
                search_results = get_search_snippets(search_query, max_results=4)
                prompt = f"""User: "{user_message}"
Property: {address}
Search results: {search_results}
Answer based on available information."""

        elif context.get('property'):
            prop = context['property']
            prompt = f"""User asking about:
Address: {prop.get('address', 'N/A')}
Price: {prop.get('price', 'N/A')}
Travel Time: {prop.get('travel_time', 'N/A')}
Question: {user_message}
Provide helpful information."""
        
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