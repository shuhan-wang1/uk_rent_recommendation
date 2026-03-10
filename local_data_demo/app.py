# app.py - Enhanced with RAG and ReAct Agent Framework

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

# 统一 UI 模式标志
USE_UNIFIED_UI = True  # 设置为 True 使用新的统一 Alex 界面

# ReAct Agent 实例
react_agent = None

# 对话历史存储 - 用于保持上下文记忆
conversation_history = []
MAX_HISTORY_LENGTH = 10  # 保留最近10轮对话

# --- Tool System Setup (从 fengyuan-agent 迁移) ---
print("[STARTUP] Initializing Tool System...")
try:
    tool_registry = create_tool_registry()
    print(f"✓ [STARTUP] Tool System initialized with {len(tool_registry.tools)} tools")
    
    # 🆕 设置 tool_registry 到 web_search，让它可以调用其他工具
    from core.tools.web_search import set_tool_registry
    set_tool_registry(tool_registry)
    
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
    if USE_UNIFIED_UI:
        return render_template('unified-ui.html')
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


# ============================================================================
# 统一的 Alex API 端点 - 纯 ReAct Agent 架构
# 
# 核心原则：
# 1. 没有关键词匹配 - 完全由 LLM 决定使用哪个工具
# 2. 所有请求都通过 ReAct Agent
# 3. search_properties 工具内部整合了 Fine-tuned Model
# ============================================================================

@app.route('/api/alex', methods=['POST'])
async def api_alex():
    """
    统一的 Alex 端点 - 纯 ReAct Agent 架构
    
    所有用户请求都交给 ReAct Agent 处理，由 LLM 自主决定：
    - 是否需要搜索房源（调用 search_properties 工具）
    - 是否需要检查安全（调用 check_safety 工具）
    - 是否需要计算通勤（调用 calculate_commute 工具）
    - 是否需要查询天气（调用 get_weather 工具）
    - 是否需要搜索附近设施（调用 search_nearby_pois 工具）
    - 或者直接回答用户问题
    """
    global last_search_results, react_agent
    
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({"error": "Message is required"}), 400
    
    user_message = data.get('message')
    context = data.get('context', {})
    is_continuation = data.get('is_continuation', False)
    
    print(f"\n{'='*60}")
    print(f"🤖 [ALEX - ReAct Agent] 收到消息: {user_message}")
    print(f"📋 [ALEX] is_continuation: {is_continuation}")
    print(f"📋 [ALEX] context: {context}")
    print(f"{'='*60}")
    
    try:
        # 所有请求都通过 ReAct Agent 处理
        return await handle_with_react_agent(user_message, context, is_continuation)
    
    except Exception as e:
        print(f"❌ [ALEX] 错误: {e}")
        traceback.print_exc()
        return jsonify({
            "response_type": "error",
            "message": "抱歉，处理您的请求时出错了。请稍后再试。"
        }), 500


async def handle_with_react_agent(user_message: str, context: dict, is_continuation: bool):
    """
    使用 ReAct Agent 处理所有用户请求 - 纯 LLM 驱动
    
    ReAct Agent 会自主决定：
    1. 是否需要调用 search_properties 工具搜索房源
    2. 是否需要调用其他工具（安全检查、通勤计算等）
    3. 或者直接回答用户问题
    
    没有任何关键词匹配 - 完全由 LLM 决策
    """
    global react_agent, tool_registry, last_search_results, conversation_history
    
    # 确保 tool_registry 已初始化
    if tool_registry is None:
        print("[ReAct] tool_registry 为空，重新初始化...")
        tool_registry = create_tool_registry()
    
    # 初始化或获取 ReAct Agent
    if react_agent is None:
        from core.react_agent import ReActAgent
        react_agent = ReActAgent(
            tool_registry=tool_registry,
            max_turns=5,
            verbose=True
        )
    
    # 如果有 property context，设置到 agent 的 extracted_context 中
    # 并从数据库获取详细信息
    if context and context.get('property'):
        property_info = context['property']
        property_address = property_info.get('address', '')
        
        react_agent.extracted_context['property_address'] = property_address
        react_agent.extracted_context['property_price'] = property_info.get('price')
        react_agent.extracted_context['property_travel_time'] = property_info.get('travel_time')
        
        # 🆕 从数据库中获取该房产的详细信息
        print(f"[ReAct] 📍 已设置 property context: {property_address}")
        print(f"[ReAct] 🔍 正在从数据库获取房产详细信息...")
        
        # 在 all_properties 中查找匹配的房产
        matched_property = None
        for prop in all_properties:
            if prop.get('Address', '').lower().strip() == property_address.lower().strip():
                matched_property = prop
                break
            # 也尝试部分匹配（地址可能被截断）
            if property_address.lower() in prop.get('Address', '').lower() or prop.get('Address', '').lower() in property_address.lower():
                matched_property = prop
                break
        
        if matched_property:
            print(f"[ReAct] ✅ 找到匹配房产，加载详细信息")
            react_agent.extracted_context['room_type'] = matched_property.get('Room_Type_Category', '')
            react_agent.extracted_context['amenities'] = matched_property.get('Detailed_Amenities', '')
            react_agent.extracted_context['guest_policy'] = matched_property.get('Guest_Policy', '')
            react_agent.extracted_context['payment_rules'] = matched_property.get('Payment_Rules', '')
            react_agent.extracted_context['excluded_features'] = matched_property.get('Excluded_Features', '')
            react_agent.extracted_context['description'] = matched_property.get('Description', '')
            react_agent.extracted_context['enhanced_description'] = matched_property.get('Enhanced_Description', '')
            # 🆕 添加 URL
            react_agent.extracted_context['property_url'] = matched_property.get('URL', '')
            print(f"[ReAct] 🔗 房产 URL: {matched_property.get('URL', 'N/A')}")
        else:
            print(f"[ReAct] ⚠️ 未在数据库中找到匹配房产: {property_address}")
    
    # 构建包含历史的查询
    query_with_history = user_message
    
    # 检查是否有房产上下文（用户在询问特定房产的问题）
    has_property_context = bool(react_agent.extracted_context.get('property_address'))
    
    # 🆕 检测对比查询 - 如果用户在比较两个房产
    comparison_keywords = ['compare', 'vs', 'versus', 'between', 'or', 'better', 'which one', 'deciding between']
    is_comparison_query = any(kw in user_message.lower() for kw in comparison_keywords)
    
    if is_comparison_query:
        # 尝试从用户查询中提取房产名称并加载它们的数据
        print(f"[ReAct] 🔄 检测到对比查询，正在加载房产数据...")
        
        # 查找提到的房产
        mentioned_properties = []
        for prop in all_properties:
            prop_name = prop.get('Address', '').split(',')[0].strip().lower()
            # 检查房产名称的关键词是否在用户查询中
            name_words = prop_name.split()
            for word in name_words:
                if len(word) > 3 and word.lower() in user_message.lower():
                    mentioned_properties.append(prop)
                    print(f"[ReAct] ✅ 找到提及的房产: {prop.get('Address', '')[:50]}")
                    break
        
        # 将对比房产的信息添加到上下文中
        if mentioned_properties:
            comparison_context = "\n=== Properties to Compare ===\n"
            for i, prop in enumerate(mentioned_properties[:3], 1):  # 最多3个
                comparison_context += f"\n**Property {i}: {prop.get('Address', '').split(',')[0]}**\n"
                comparison_context += f"- Price: {prop.get('Price', 'N/A')}\n"
                comparison_context += f"- Room Type: {prop.get('Room_Type_Category', 'N/A')}\n"
                comparison_context += f"- Amenities: {prop.get('Detailed_Amenities', 'N/A')}\n"
                comparison_context += f"- Guest Policy: {prop.get('Guest_Policy', 'N/A')}\n"
                comparison_context += f"- Payment Rules: {prop.get('Payment_Rules', 'N/A')}\n"
                comparison_context += f"- NOT Included: {prop.get('Excluded_Features', 'N/A')}\n"
                comparison_context += f"- Commute Info: {prop.get('Description', 'N/A')}\n"
            
            react_agent.extracted_context['comparison_properties'] = comparison_context
            print(f"[ReAct] 📊 已加载 {len(mentioned_properties)} 个房产的对比数据")
    
    # Agent 自己决定是否需要设施搜索 - 不再使用关键词检测
    # 设施搜索逻辑已移至 search_properties 工具内部
    
    if has_property_context:
        # 用户在询问关于特定房产的问题，不需要添加搜索提示
        print(f"[ReAct] 📍 用户正在询问关于特定房产的问题，将使用房产上下文回答")
        # 保持原始查询，不添加历史提示
    elif conversation_history:
        # 🆕 检查是否是对澄清问题的回复
        last_response = conversation_history[-1].get('assistant', '') if conversation_history else ''
        is_clarification_answer = any(q in last_response.lower() for q in [
            'what is your', 'could you tell me', 'what\'s the maximum', 
            'please provide', 'how many', 'which area', '?'
        ])
        
        if is_clarification_answer and len(user_message.split()) <= 5:
            # 这看起来是对澄清问题的回复（如 "30 minutes", "10", "no preference"）
            # 需要保持完整的对话上下文
            print(f"[ReAct] 🔄 检测到澄清回复，保持完整上下文")
            history_text = "\n".join([
                f"User: {h['user']}\nAlex: {h['assistant']}" 
                for h in conversation_history[-5:]  # 更多历史以保持上下文
            ])
            query_with_history = f"""Previous conversation (IMPORTANT - user is answering a clarification question):
{history_text}

User's answer to the clarification question: {user_message}

INSTRUCTIONS: The user just answered your clarification question. Use their answer to complete the ORIGINAL request. Do NOT ask more questions about the same thing. Do NOT treat their answer as a confusing new command."""
        else:
            # 普通的对话延续
            history_text = "\n".join([
                f"User: {h['user']}\nAlex: {h['assistant']}" 
                for h in conversation_history[-3:]
            ])
            query_with_history = f"""Previous conversation:
{history_text}

Current user message: {user_message}"""
    
    # 运行 ReAct 循环
    result = await react_agent.run(query_with_history, context, is_continuation=is_continuation)
    
    print(f"\n[ReAct] 完成! Turns: {result.get('turns')}, Success: {result.get('success')}")
    print(f"[ReAct] Response Type: {result.get('response_type')}")
    
    # 保存对话历史
    response_text = result.get('response', '')
    conversation_history.append({
        'user': user_message,
        'assistant': response_text[:500]  # 限制长度
    })
    # 保持历史长度限制
    if len(conversation_history) > MAX_HISTORY_LENGTH:
        conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]
    
    # 检查是否有房源搜索结果（从工具调用中获取）
    tool_data = result.get('tool_data', {})
    if tool_data.get('recommendations'):
        # 存储搜索结果供 UI 展示
        last_search_results = tool_data['recommendations']
        
        # 🆕 保存搜索结果到 extracted_context，供后续安全/设施问题使用
        prev_results_context = "\n"
        for i, rec in enumerate(tool_data['recommendations'][:6], 1):
            addr = rec.get('address', 'Unknown')
            price = rec.get('price', 'N/A')
            travel = rec.get('travel_time', 'N/A')
            # 从 all_properties 获取完整信息
            full_prop = None
            for prop in all_properties:
                if prop.get('Address', '').startswith(addr.split(',')[0]):
                    full_prop = prop
                    break
            
            # 提取房产名称（用于用户引用）
            property_name = addr.split(',')[0].strip()
            
            # 🆕 保存完整地址（用于 check_safety 等工具）
            full_address = full_prop.get('Address', addr) if full_prop else addr
            
            prev_results_context += f"{i}. **{property_name}**\n"
            prev_results_context += f"   - Full Address: {full_address}\n"  # 🆕 添加完整地址
            prev_results_context += f"   - Price: {price}\n"
            prev_results_context += f"   - Commute: {travel}\n"
            if full_prop:
                prev_results_context += f"   - Amenities: {full_prop.get('Detailed_Amenities', 'N/A')}\n"
                prev_results_context += f"   - URL: {full_prop.get('URL', 'N/A')}\n"
            prev_results_context += "\n"
        
        react_agent.extracted_context['previous_search_results'] = prev_results_context
        print(f"[ReAct] 💾 已保存 {len(tool_data['recommendations'])} 个搜索结果到上下文")
        
        # 🆕 检查是否有安全警告需要记住
        if react_agent.extracted_context.get('safety_warnings'):
            print(f"[ReAct] ⚠️ 注意：有安全警告待处理")
        
        return jsonify({
            "response_type": "search",
            "message": result.get('response'),
            "recommendations": tool_data['recommendations']
        })
    
    # 根据结果类型返回响应
    if result.get('response_type') == 'question':
        return jsonify({
            "response_type": "clarification",
            "message": result.get('response'),
            "agent_state": "waiting_for_input",
            "extracted_context": result.get('extracted_context', {})
        })
    
    elif result.get('response_type') == 'answer':
        return jsonify({
            "response_type": "chat",
            "message": result.get('response'),
            "turns_used": result.get('turns')
        })
    
    else:
        return jsonify({
            "response_type": "chat",
            "message": result.get('response', "I'm here to help! What would you like to know?")
        })


@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """清除对话历史，开始新对话"""
    global conversation_history, react_agent
    conversation_history = []
    if react_agent:
        react_agent.reset()
    print("[ALEX] 对话历史已清除")
    return jsonify({"success": True, "message": "Conversation history cleared"})


@app.route('/api/search', methods=['POST'])
async def api_search():
    """
    ✅ FIXED: Properly preserve original query context
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
        # ✅ Step 0: Check if this is a clarification response
        if has_pending_clarification() and is_clarification_response(user_query):
            print("[API] ✓ This is a clarification response")
            pending = get_pending_criteria()
            print(f"[API] Original criteria: {json.dumps(pending, indent=2)}")
            
            # ✅ CRITICAL FIX: Pass BOTH the pending criteria AND the new answer
            # Don't let the model re-parse everything - just merge the new info
            criteria_response = refine_criteria_with_answer(pending, user_query)
            
            print(f"[API] Merged criteria: {json.dumps(criteria_response, indent=2)}")
            
            # If still needs clarification, save and return
            if criteria_response.get('status') != 'success':
                set_pending_criteria(criteria_response)
                return jsonify(criteria_response), 200
            
            # Otherwise clear and continue to search
            clear_pending_criteria()
            criteria = criteria_response
            
        else:
            # New search query
            print("[API] → This is a new search query")
            criteria_response = clarify_and_extract_criteria(user_query)
            
            # ✅ CRITICAL: Save the original query for context
            if criteria_response.get('status') != 'success':
                criteria_response['_original_query'] = user_query  # Save for later!
                
            print(f"[DEBUG] Initial criteria: {json.dumps(criteria_response, indent=2)}")

            # If needs clarification, save and return
            if criteria_response.get('status') != 'success':
                print("[API] → Needs clarification")
                set_pending_criteria(criteria_response)
                return jsonify(criteria_response), 200

            criteria = criteria_response

        # ✅ At this point we have complete criteria with status='success'
        print("[API] ✓ Complete criteria obtained, starting search...")

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
        
        # 🆕 3.5. 去重 - 移除重复的房源地址
        print(f"\n[STEP 3.5] 检查并去重...")
        seen_addresses = set()
        unique_candidates = []
        
        for prop in candidates_with_travel:
            # 标准化地址用于比较（小写，去空格，取前50字符）
            addr = prop.get('Address', '').lower().strip()[:50]
            
            if addr and addr not in seen_addresses:
                seen_addresses.add(addr)
                unique_candidates.append(prop)
            else:
                print(f"  ⚠️  跳过重复房源: {prop.get('Address', '')[:40]}")
        
        print(f"  ✓ 去重后剩余 {len(unique_candidates)} 个唯一房源")
        candidates_with_travel = unique_candidates
        
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

def validate_and_fix_poi_response(llm_response: str, poi_data: list, poi_type: str) -> str:
    """
    强力验证LLM响应，检测并修正编造的内容
    超级激进模式：如果检测到任何编造迹象，立即替换为安全响应
    
    Args:
        llm_response: LLM生成的原始响应
        poi_data: 真实的POI数据列表
        poi_type: POI类型（restaurant, supermarket等）
    
    Returns:
        验证/修正后的响应
    """
    if not poi_data:
        return llm_response
    
    # 常见的编造名称（按类型）
    FAKE_MARKERS = {
        'restaurant': [
            'delaunay', 'wolseley', 'padella', 'dishoom', 'simpson', 
            'hawksmoor', 'the ivy', 'nobu', 'sketch', 'barbary',
            'roka', 'coya', 'zuma', 'hakkasan', 'gymkhana'
        ],
        'supermarket': []
    }
    
    # 获取真实的POI名称（小写）
    real_names_lower = [p['name'].lower() for p in poi_data[:10]]
    top_5_names = [p['name'] for p in poi_data[:5]]
    
    # 🔥 激进检测1：检查是否包含足够的真实餐厅名
    found_real_count = sum(1 for name in top_5_names if name in llm_response)
    
    if found_real_count < 3:
        print(f"\n🔥 [AGGRESSIVE VALIDATION] LLM只提到了{found_real_count}/5个真实{poi_type}，强制替换")
        return generate_safe_poi_response(poi_data, poi_type)
    
    # 🔥 激进检测2：检测编造的著名餐厅名
    fake_names_detected = []
    markers = FAKE_MARKERS.get(poi_type, [])
    
    for fake in markers:
        if fake in llm_response.lower():
            # 检查是否真的在数据中
            if not any(fake in name for name in real_names_lower):
                fake_names_detected.append(fake)
    
    if fake_names_detected:
        print(f"\n🔥 [AGGRESSIVE VALIDATION] 检测到编造的{poi_type}名: {', '.join(fake_names_detected)}")
        return generate_safe_poi_response(poi_data, poi_type)
    
    # 🔥 激进检测3：检测错误的距离数字
    real_distances = [str(p['distance_m']) for p in poi_data[:10]]
    import re
    
    distance_pattern = r'(\d+)\s*(?:米|m|meter|metre|miles?)'
    distances_in_response = re.findall(distance_pattern, llm_response, re.IGNORECASE)
    
    # 检查是否有太多不匹配的距离
    mismatched = 0
    for dist in distances_in_response:
        if dist not in real_distances:
            dist_int = int(dist)
            # 允许±10米的误差
            if not any(abs(dist_int - int(rd)) < 10 for rd in real_distances):
                mismatched += 1
    
    if mismatched >= 2:
        print(f"\n🔥 [AGGRESSIVE VALIDATION] 检测到{mismatched}个错误距离，强制替换")
        return generate_safe_poi_response(poi_data, poi_type)
    
    # 所有检查通过，返回原响应
    print(f"✅ [VALIDATION] 响应通过验证（包含{found_real_count}个真实{poi_type}）")
    return llm_response


def generate_safe_poi_response(poi_data: list, poi_type: str) -> str:
    """
    生成100%准确的安全响应，完全不依赖LLM
    🆕 支持餐厅菜系分类
    
    Args:
        poi_data: POI数据列表
        poi_type: POI类型
    
    Returns:
        格式化的安全响应
    """
    # 中文类型映射
    type_cn = {
        'restaurant': '餐厅',
        'cafe': '咖啡厅',
        'gym': '健身房',
        'park': '公园',
        'supermarket': '超市',
        'hospital': '医院',
        'library': '图书馆',
        'school': '学校'
    }
    
    poi_cn = type_cn.get(poi_type, poi_type)
    
    # 🆕 如果是餐厅，按菜系分类展示
    if poi_type == 'restaurant':
        from core.cuisine_classifier import group_restaurants_by_cuisine, format_cuisine_summary
        
        grouped = group_restaurants_by_cuisine(poi_data)
        cuisine_summary = format_cuisine_summary(grouped)
        
        response = f"根据OpenStreetMap的实时数据，这个房源附近的餐厅按菜系分类如下：\n\n"
        
        # 按餐厅数量排序菜系
        sorted_cuisines = sorted(
            grouped.items(),
            key=lambda x: len(x[1]['restaurants']),
            reverse=True
        )
        
        # 展示每个菜系（最多前5个菜系）
        for cuisine_type, data in sorted_cuisines[:5]:
            restaurants = data['restaurants'][:3]  # 每个菜系展示前3家
            cuisine_name = data['name_cn']
            total_count = len(data['restaurants'])
            
            response += f"**{cuisine_name} ({total_count}家)**\n"
            for i, r in enumerate(restaurants, 1):
                distance_m = r['distance_m']
                distance_km = round(distance_m / 1000, 2)
                response += f"{i}. {r['name']} - {distance_m}米（{distance_km}公里）\n"
            response += "\n"
        
        # 添加总结
        closest = poi_data[0]['distance_m']
        response += f"**总结**：\n"
        response += f"• 1.5公里范围内共找到 {len(poi_data)} 家餐厅\n"
        response += f"• 最近的餐厅距离只有 {closest} 米\n"
        response += f"• 菜系分布：\n{cuisine_summary}\n"
        
        if closest < 100:
            response += f"\n💡 餐饮选择非常丰富，楼下就有多家餐厅！"
        elif closest < 300:
            response += f"\n💡 周边餐饮选择丰富，步行几分钟即可到达。"
        else:
            response += f"\n💡 附近有多种菜系可选，满足不同口味需求。"
        
        return response
    
    # 非餐厅类型，使用原有逻辑
    top_5 = poi_data[:5]
    
    response = f"根据OpenStreetMap的实时数据，这个房源附近最近的{poi_cn}有：\n\n"
    
    for i, place in enumerate(top_5, 1):
        distance_m = place['distance_m']
        distance_km = round(distance_m / 1000, 2)
        walk_time_min = max(1, round(distance_m / 80))  # 按80米/分钟计算步行时间
        
        # 格式化名称
        name = place['name']
        if name.startswith('Unknown'):
            name = f"未命名的{poi_cn}"
        
        response += f"{i}. **{name}** - {distance_m}米（{distance_km}公里），步行约{walk_time_min}分钟\n"
    
    # 添加实用总结
    closest = top_5[0]['distance_m']
    closest_time = max(1, round(closest / 80))
    farthest_in_top3 = max(p['distance_m'] for p in top_5[:3])
    
    response += f"\n**距离总结**：\n"
    response += f"• 最近的是 **{top_5[0]['name']}**，只有{closest}米（步行约{closest_time}分钟）\n"
    response += f"• 前3家都在{farthest_in_top3}米以内\n"
    response += f"• 1.5公里范围内共找到{len(poi_data)}个{poi_cn}\n"
    
    # 根据距离给出建议
    if closest < 100:
        response += f"\n💡 这些{poi_cn}非常近，楼下就有，非常方便！"
    elif closest < 300:
        response += f"\n💡 最近的{poi_cn}步行3-5分钟即可到达，位置很好。"
    elif closest < 500:
        response += f"\n💡 最近的{poi_cn}在步行范围内，大约5-8分钟。"
    else:
        response += f"\n💡 最近的{poi_cn}距离稍远，但仍在步行范围（10分钟左右）。"
    
    return response


@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with Tool System integration for multi-source POI search"""
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({"error": "Message is required"}), 400
    
    user_message = data.get('message')
    context = data.get('context', {})
    
    # 🔍 DEBUG: 打印接收到的数据
    print(f"\n{'='*60}")
    print(f"[CHAT] 收到消息 (长度 {len(user_message)}): {user_message}")  # 显示完整消息
    print(f"[CHAT] Context: {context}")
    if context.get('property'):
        print(f"[CHAT] Property address: {context['property'].get('address', 'N/A')}")
    print(f"{'='*60}\n")
    
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
                          'school', 'primary', 'secondary', 'education',
                          '餐厅', '餐馆', '饭店', '吃饭', '美食']  # 添加中文关键词
        needs_search = any(keyword in user_message.lower() for keyword in search_keywords)
        
        print(f"[CHAT] needs_search: {needs_search}")
        print(f"[CHAT] 消息全文: '{user_message}'")
        
        # 初始化POI相关变量（用于后续验证）
        detected_poi = None
        poi_data = None
        
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
                'gym': ['gym', 'fitness', 'health club', 'sports center', 'leisure', '健身', '健身房'],
                'park': ['park', 'green space', 'outdoor', '公园', '绿地'],
                'restaurant': ['restaurant', 'cafe', 'coffee', 'diner', 'eating', '餐厅', '餐馆', '饭店', '吃饭', '美食'],
                'hospital': ['hospital', 'medical', 'doctor', 'clinic', 'health', '医院', '诊所', '医疗'],
                'library': ['library', 'books', '图书馆', '书店'],
                'school': ['school', 'primary', 'secondary', 'education', '学校', '教育'],
            }
            
            # detected_poi 已在函数开始时初始化
            for poi_type, keywords in poi_keywords.items():
                if any(keyword in user_message.lower() for keyword in keywords):
                    detected_poi = poi_type
                    break
            
            # GENERIC POI QUERY (GYM, PARK, RESTAURANT, HOSPITAL, ETC)
            if detected_poi:
                print(f"\n[POI SEARCH] 检测到POI类型: {detected_poi.upper()}")
                print(f"[POI SEARCH] 搜索地址: {address}")
                from core.maps_service import get_nearby_places_osm
                
                poi_data = get_nearby_places_osm(address, detected_poi, radius_m=1500)
                print(f"[POI SEARCH] 找到 {len(poi_data) if poi_data else 0} 个 {detected_poi}")
                
                if poi_data and len(poi_data) > 0:
                    # 🆕 如果是餐厅查询，添加菜系分类
                    if detected_poi == 'restaurant':
                        from core.cuisine_classifier import group_restaurants_by_cuisine, format_cuisine_summary
                        
                        # 按菜系分组
                        grouped = group_restaurants_by_cuisine(poi_data)
                        cuisine_summary = format_cuisine_summary(grouped)
                        
                        print(f"[CUISINE] 菜系统计:\n{cuisine_summary}")
                        
                        # 准备详细数据（前10个，按菜系分组）
                        import json
                        
                        # 构建按菜系组织的数据结构
                        cuisine_data = {}
                        for cuisine_type, data in grouped.items():
                            restaurants = data['restaurants'][:5]  # 每个菜系最多5家
                            cuisine_data[data['name_cn']] = [
                                {
                                    "name": r['name'],
                                    "distance_m": r['distance_m'],
                                    "distance_km": round(r['distance_m']/1000, 2),
                                    "cuisine_original": r.get('cuisine', '未标注')
                                }
                                for r in restaurants
                            ]
                        
                        data_json = json.dumps(cuisine_data, indent=2, ensure_ascii=False)
                        
                        prompt = f"""用户问题："{user_message}"
房源地址：{address}

===== 真实数据（来自OpenStreetMap，按菜系分类）=====
{data_json}
===== 真实数据结束 =====

菜系统计：
{cuisine_summary}

总共找到 {len(poi_data)} 家餐厅。

严格要求：
1. 必须按菜系分类介绍餐厅（中餐、意大利菜、日本料理等）
2. 只能使用上面JSON中的餐厅名称和数据
3. 必须逐字复制餐厅名称（保持原文）
4. 必须使用精确的距离数字
5. 禁止提到任何不在JSON中的餐厅（如"The Delaunay"、"Padella"等）
6. 每个菜系介绍最近的2-3家餐厅

回答格式示例：
"根据OpenStreetMap的真实数据，这个房源附近的餐厅按菜系分类如下：

**中餐 (X家)**
1. [餐厅名] - [距离]米
2. [餐厅名] - [距离]米

**意大利菜 (X家)**
1. [餐厅名] - [距离]米
2. [餐厅名] - [距离]米

**日本料理 (X家)**
...

总体来说，这个区域的餐饮选择[丰富/一般]，最近的餐厅距离只有[X]米。"

用中文回答，但餐厅名称保持原文（英文）。"""
                    else:
                        # 非餐厅类型，使用原有逻辑
                        top_5 = poi_data[:5]
                        
                        import json
                        structured_data = []
                        for i, place in enumerate(top_5, 1):
                            structured_data.append({
                                "rank": i,
                                "name": place['name'],
                                "distance_m": place['distance_m'],
                                "distance_km": round(place['distance_m']/1000, 2),
                                "coordinates": f"({place['lat']:.4f}, {place['lon']:.4f})"
                            })
                        
                        data_json = json.dumps(structured_data, indent=2, ensure_ascii=False)
                        
                        prompt = f"""用户问题："{user_message}"
房源地址：{address}

===== 真实数据（来自OpenStreetMap，禁止修改）=====
{data_json}
===== 真实数据结束 =====

总共找到 {len(poi_data)} 个{detected_poi}，以上是最近的5个。

严格要求：
1. 只能使用上面JSON中的5个{detected_poi}
2. 必须逐字复制名称（不要翻译、不要修改、保持原文）
3. 必须使用上面显示的精确距离数字
4. 禁止提到任何其他{detected_poi}名称
5. 如果用户问"附近"，理解为500米以内
6. 必须按距离从近到远排序
7. 距离数据必须完全匹配JSON中的数字

回答格式示例：
"根据OpenStreetMap的真实数据，这个房源最近的{detected_poi}是：

1. [从JSON逐字复制名称] - [从JSON复制距离]米（[从JSON复制公里数]公里）
2. [从JSON逐字复制名称] - [从JSON复制距离]米（[从JSON复制公里数]公里）
...

其中最近的3个都在[X]米以内，步行只需几分钟。"

用中文回答，但{detected_poi}名称必须保持原文（英文）。"""
                else:
                    prompt = f"""用户问题："{user_message}"
房源地址：{address}

OpenStreetMap搜索结果：在1.5公里范围内未找到{detected_poi}。

严格要求：
1. 诚实告诉用户在附近未找到{detected_poi}
2. 建议扩大搜索范围或使用其他方式查找
3. 绝对禁止编造任何{detected_poi}名称
4. 不要猜测或推荐不在数据中的地点

用中文诚实、友好地回答。"""

            # SUPERMARKET/CHAIN QUERY - Now uses Tool System with multi-source search
            elif any(word in user_message.lower() for word in ['supermarket', 'shop', 'store', 'grocery', 'lidl', 'aldi', 'tesco', 'sainsbury', 'waitrose']):
                print(f"  [Overpass API] Supermarket search for: {address}")
                
                # 检测用户询问的特定连锁超市
                target_chains = ['tesco', 'sainsbury', 'lidl', 'waitrose', 'aldi', 'co-op', 'marks & spencer', 'm&s']
                
                # 获取OpenStreetMap数据
                from core.maps_service import get_nearby_places_osm
                supermarket_data = get_nearby_places_osm(address, 'supermarket', radius_m=1500)
                
                # 检查用户询问的连锁店是否存在
                found_chains = {}
                asked_chains = []
                
                for chain in target_chains:
                    if chain.lower() in user_message.lower():
                        asked_chains.append(chain)
                
                # 🔍 DEBUG: 打印找到的超市
                print(f"[SUPERMARKET] 找到 {len(supermarket_data) if supermarket_data else 0} 家超市")
                if supermarket_data:
                    print(f"[SUPERMARKET] 前10家超市名称:")
                    for i, s in enumerate(supermarket_data[:10], 1):
                        print(f"  {i}. {s['name']} - {s['distance_m']}米")
                
                # 在数据中查找这些连锁店（使用更宽松的匹配）
                if supermarket_data:
                    for chain in asked_chains if asked_chains else target_chains:
                        # 🆕 更智能的匹配逻辑
                        matching = []
                        chain_lower = chain.lower().replace("'", "").replace(" ", "")  # sainsbury's -> sainsburys
                        
                        for s in supermarket_data:
                            name_lower = s['name'].lower().replace("'", "").replace(" ", "")
                            # 检查链名是否在超市名中
                            if chain_lower in name_lower or name_lower in chain_lower:
                                matching.append(s)
                        
                        if matching:
                            found_chains[chain] = matching[0]  # 只取最近的一个
                            print(f"[SUPERMARKET] ✅ 找到 {chain}: {matching[0]['name']}")
                        else:
                            print(f"[SUPERMARKET] ❌ 未找到 {chain}")
                
                if found_chains or (not asked_chains and supermarket_data):
                    import json
                    
                    # 如果用户询问了特定连锁，只显示找到的连锁店
                    if asked_chains:
                        chains_json = []
                        not_found = []
                        
                        for chain in asked_chains:
                            if chain in found_chains:
                                data = found_chains[chain]
                                chains_json.append({
                                    "chain": chain.upper(),
                                    "name": data['name'],
                                    "distance_m": data['distance_m'],
                                    "distance_km": round(data['distance_m']/1000, 2),
                                    "coordinates": f"({data['lat']:.4f}, {data['lon']:.4f})",
                                    "note": "OpenStreetMap未提供街道地址" if data['address'].startswith('(') else data['address']
                                })
                            else:
                                not_found.append(chain.upper())
                        
                        data_json = json.dumps(chains_json, indent=2, ensure_ascii=False)
                        
                        prompt = f"""房源地址：{address}

===== 真实数据（来自OpenStreetMap）=====
{data_json}
===== 真实数据结束 =====

未找到的连锁店：{', '.join(not_found) if not_found else '无'}

严格要求：
1. 不要重复用户的问题
2. 只能使用上面JSON中的超市数据
3. 必须显示每个超市的距离（米数和公里数）
4. 计算并显示步行时间（按80米/分钟计算）
5. 如果JSON中没有某个连锁店，明确说"未找到"
6. 绝对禁止编造地址信息
7. 不要编造任何不在JSON中的超市

回答格式示例：
"根据OpenStreetMap数据，这个房源附近找到以下超市：

**找到的超市：**
1. **[超市名]** - [距离]米（[公里]公里），步行约[时间]分钟
2. **[超市名]** - [距离]米（[公里]公里），步行约[时间]分钟

[如果有未找到的]
**未找到：** [列出]

💡 最近的超市距离只有[X]米，步行[Y]分钟即可到达，购物非常方便。"

用中文回答，直接给出结果，不要重复问题。"""
                    else:
                        # 用户没有指定连锁，显示所有超市
                        top_supermarkets = []
                        for s in supermarket_data[:8]:  # 显示前8家
                            top_supermarkets.append({
                                "name": s['name'],
                                "distance_m": s['distance_m'],
                                "distance_km": round(s['distance_m']/1000, 2),
                                "walk_time_min": max(1, round(s['distance_m'] / 80))  # 按80米/分钟计算
                            })
                        
                        data_json = json.dumps(top_supermarkets, indent=2, ensure_ascii=False)
                        
                        prompt = f"""房源地址：{address}

===== 真实数据（来自OpenStreetMap）=====
{data_json}
===== 真实数据结束 =====

总共找到 {len(supermarket_data)} 家超市，以上是最近的{len(top_supermarkets)}家。

严格要求：
1. 不要重复用户的问题
2. 只能使用JSON中的超市名称、距离和步行时间
3. 必须逐字复制名称（保持原文）
4. 必须显示距离和步行时间（使用JSON中的数据）
5. 不要编造任何信息

回答格式示例：
"根据OpenStreetMap数据，这个房源附近最近的超市有：

1. **[超市名]** - [距离]米（[公里]公里），步行约[时间]分钟
2. **[超市名]** - [距离]米（[公里]公里），步行约[时间]分钟
3. **[超市名]** - [距离]米（[公里]公里），步行约[时间]分钟
...

💡 最近的超市距离只有[X]米，步行[Y]分钟即可到达。1.5公里范围内共有{len(supermarket_data)}家超市可选。"

用中文回答，超市名称保持原文（英文），直接给出结果，不要重复问题。"""

                else:
                    prompt = f"""房源地址：{address}

OpenStreetMap搜索结果：在1.5公里范围内未找到超市。

严格要求：
1. 不要重复用户的问题
2. 诚实告诉用户在1.5公里范围内未找到超市
3. 建议扩大搜索范围或使用其他购物方式
4. 不要编造任何超市名称

用中文友好地回答，直接给出结果。"""
            
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
        else:
            # 用户没有提供房源上下文，但问了位置相关的问题
            if needs_search:
                response_text = "抱歉，我需要知道具体的房源地址才能为您查询附近的设施。\n\n请您：\n1. 先搜索房源\n2. 点击房源卡片上的'Chat'按钮\n3. 然后在对话框中询问我\n\n或者您可以直接告诉我具体的地址，比如：'伦敦WC1H 0AQ附近有什么餐厅？'"
                formatted_response = markdown_to_html(response_text)
                return jsonify({"response": formatted_response})
            else:
                # 一般性对话，不涉及位置
                prompt = f"""User: "{user_message}"
You are Alex, a friendly UK rental assistant.
Provide helpful, friendly information."""
        
        response_text = call_ollama(prompt, system_prompt=system_prompt, timeout=360)
        
        # 检查响应是否为空（超时或失败）
        if not response_text:
            # 如果是POI查询且有数据，使用安全响应
            if detected_poi and poi_data:
                print(f"⚠️ [TIMEOUT] Ollama超时，使用安全响应生成{detected_poi}信息")
                response_text = generate_safe_poi_response(poi_data, detected_poi)
            else:
                return jsonify({"error": "AI模型响应超时。模型可能正在处理其他请求，请稍后再试。"}), 500
        
        # 如果是POI查询，验证并修正响应
        elif detected_poi and poi_data:
            print(f"\n[VALIDATION] 验证{detected_poi}响应...")
            try:
                response_text = validate_and_fix_poi_response(response_text, poi_data, detected_poi)
                print(f"[VALIDATION] 验证完成")
            except Exception as validation_error:
                print(f"⚠️ [VALIDATION] 验证出错: {validation_error}")
                # 如果验证失败，使用安全响应
                response_text = generate_safe_poi_response(poi_data, detected_poi)
        
        if response_text:
            formatted_response = markdown_to_html(response_text)
            return jsonify({"response": formatted_response})
        else:
            return jsonify({"error": "Could not get response from AI. The model may be busy or unavailable."}), 500
            
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

@app.route('/api/generate_map', methods=['POST'])
def generate_property_map():
    """
    Generate an interactive amenity map for a property
    
    Expected JSON body:
    {
        "address": "property address",
        "geo_location": "lat, lon" or {"lat": X, "lng": Y},
        "price": "£X pcm",
        "travel_time": "X min" or X (minutes)
    }
    
    Returns:
    HTML content of the interactive map or error
    """
    data = request.get_json()
    if not data or not data.get('address'):
        return jsonify({"error": "Property address is required"}), 400
    
    try:
        from core.amenity_map_generator import PropertyAmenityMapGenerator
        from core.maps_service import get_nearby_places_osm
        
        print(f"\n{'='*60}")
        print(f"[MAP GEN] Generating amenity map for: {data['address']}")
        print(f"{'='*60}\n")
        
        # Initialize map generator
        generator = PropertyAmenityMapGenerator(radius_km=1.5)
        
        # Prepare property data
        property_data = {
            'Address': data['address'],
            'address': data['address'],
            'Price': data.get('price', 'N/A'),
            'price': data.get('price', 'N/A'),
            'travel_time_minutes': data.get('travel_time', 'N/A'),
            'travel_time': data.get('travel_time', 'N/A'),
            'geo_location': data.get('geo_location'),
            'coordinates': data.get('coordinates') or data.get('geo_location')
        }
        
        # Query amenities from OpenStreetMap
        print(f"  [MAP GEN] Querying nearby amenities...")
        amenities_data = {}
        
        # Parse coordinates once
        coords = generator.parse_geo_location(data.get('geo_location'))
        if not coords:
            return jsonify({"error": "Invalid coordinates"}), 400
        
        lat, lon = coords
        
        # Use the new query method that supports cuisine filtering
        for amenity_key in generator.amenity_config.keys():
            try:
                config = generator.amenity_config[amenity_key]
                cuisine_filter = config.get('cuisine_filter', None)
                
                # Use the specialized query method that handles cuisine filtering
                places = generator.query_osm_amenities_with_filter(
                    lat, lon,
                    amenity_key,
                    cuisine_filter
                )
                amenities_data[amenity_key] = places
                print(f"    ✓ Found {len(places)} {config['name']}")
            except Exception as e:
                print(f"    ✗ Error querying {amenity_key}: {e}")
                import traceback as tb
                tb.print_exc()
                amenities_data[amenity_key] = []
        
        # Generate map HTML
        print(f"\n  [MAP GEN] Generating interactive map...")
        map_html = generator.generate_map_html(property_data, amenities_data)
        
        if map_html:
            print(f"  ✓ [MAP GEN] Map generated successfully\n")
            return map_html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        else:
            return jsonify({"error": "Failed to generate map"}), 500
            
    except Exception as e:
        print(f"❌ Error generating map: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Map generation failed: {str(e)}"}), 500


@app.route('/api/cached_pois', methods=['GET'])
def get_cached_pois():
    """
    获取缓存的 POI 数据
    
    Query params:
    - address: 要查询的地址
    
    Returns:
    缓存的 POI 数据或错误
    """
    address = request.args.get('address')
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    try:
        import os
        cache_file = "data/osm_poi_cache.json"
        
        if not os.path.exists(cache_file):
            return jsonify({"error": "No cache file found", "cached": False}), 404
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        cache_key = address.lower().strip()
        
        if cache_key in cache:
            return jsonify({
                "cached": True,
                "data": cache[cache_key]
            })
        else:
            return jsonify({
                "cached": False,
                "message": "Address not in cache"
            }), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
if __name__ == '__main__':
    # 允许所有来源访问(用于公网访问)
    app.run(debug=True, host='0.0.0.0', port=5001)