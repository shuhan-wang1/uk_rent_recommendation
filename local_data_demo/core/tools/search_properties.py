"""
Tool 1: Search Properties Tool
搜索符合条件的房源 - 完整的 ReAct Agent 工具

这个工具整合了：
1. Fine-tuned Model：从用户自然语言中提取搜索条件
2. RAG 检索：向量搜索找到相关房源  
3. 智能过滤：硬过滤 + 软过滤
4. 通勤时间计算：真实 API 计算

核心原则：
- 作为 ReAct Agent 的一个工具被调用
- LLM 决定何时调用此工具
- 工具内部处理所有房源搜索逻辑
"""

from core.tool_system import Tool
from typing import Optional, List, Dict
import pandas as pd
import asyncio
from pathlib import Path
import json


class PropertyFilter:
    """严格的过滤器 - 用户必须满足的条件"""

    @staticmethod
    def apply_hard_filters(
        properties: List[Dict],
        budget: int,
        max_commute: int,
        location_keywords: str,
        care_about_safety: bool = False
    ) -> tuple[List[Dict], List[Dict]]:
        """
        应用硬过滤器和软过滤器
        
        返回: (完全符合, 轻微超预算的)
        
        硬过滤规则（必须满足）:
        - 通勤时间 ≤ max_commute (不能违反)
        - 价格 ≤ budget (基准)
        
        软过滤规则（可以违反但需说明）:
        - 价格 ≤ budget × 1.15 (允许超预算15%)
        """
        perfect_match = []
        soft_violation = []  # 超预算但通勤符合

        for prop in properties:
            try:
                # 获取属性，处理异常情况
                price = float(prop.get('price', float('inf')))
                commute = float(prop.get('travel_time', float('inf')))
                
                # ⚠️ 硬过滤：通勤时间是绝对要求
                if commute > max_commute:
                    continue  # 过滤掉，不考虑
                
                # 价格检查
                if price <= budget:
                    # ✅ 完全符合
                    perfect_match.append({
                        **prop,
                        'match_type': 'perfect',
                        'budget_status': '✅ 在预算内',
                        'price_diff': 0,
                        'price_diff_percentage': 0.0,
                        'commute_status': '✅ 通勤符合',
                        'recommendation_score': PropertyFilter.calculate_score(price, commute, budget, max_commute)
                    })
                elif price <= budget * 1.15:  # 允许超预算最多15%
                    # ⚠️ 轻微超预算（可推荐但需说明）
                    price_diff = price - budget
                    price_diff_percentage = round((price_diff / budget) * 100, 1)
                    
                    soft_violation.append({
                        **prop,
                        'match_type': 'soft_violation',
                        'budget_status': f'⚠️ 超预算 £{int(price_diff)}',
                        'price_diff': price_diff,
                        'price_diff_percentage': price_diff_percentage,
                        'commute_status': '✅ 通勤符合',
                        'recommendation_score': PropertyFilter.calculate_score(price, commute, budget, max_commute)
                    })
                # else: 超过软过滤阈值，完全排除
                
            except (ValueError, TypeError) as e:
                print(f"   ⚠️ 跳过房源 {prop.get('address', 'Unknown')}: 数据格式错误")
                continue

        return perfect_match, soft_violation
    
    @staticmethod
    def calculate_score(price: float, commute: float, budget: int, max_commute: int) -> float:
        """
        计算推荐分数 (0-100)
        
        分数 = 价格匹配度(50%) + 通勤匹配度(50%)
        
        - 价格匹配度: 越接近预算越高
        - 通勤匹配度: 通勤时间越短越高
        """
        # 价格匹配度：0-50分
        price_match = max(0, 50 * (1 - (price - budget) / budget)) if price >= budget else 50
        
        # 通勤匹配度：0-50分
        commute_match = max(0, 50 * (1 - commute / max_commute))
        
        total_score = price_match + commute_match
        return round(total_score, 1)


async def search_properties_impl(
    user_query: str = "",
    location: str = None,
    max_budget: int = None,
    max_commute_time: int = None,
    min_budget: int = 500,
    radius_miles: float = 2.0,
    limit: int = 10,
    care_about_safety: bool = False,
    sort_by: str = "value",
    **kwargs  # 接受 LLM 可能传递的任何额外参数（如 property_type）
) -> dict:
    """
    完整的房源搜索工具 - 整合 Fine-tuned Model + RAG + 过滤器
    
    这是 ReAct Agent 调用的主要工具。
    
    流程：
    1. 如果参数不完整，使用 Fine-tuned Model 从 user_query 提取
    2. 如果仍有缺失参数，返回需要澄清的问题
    3. 参数完整后，执行 RAG 搜索 + 过滤 + 排序
    4. 返回格式化的结果供 Agent 回复
    
    Args:
        user_query: 用户的原始自然语言查询（用于 Fine-tuned Model 提取参数）
        location: 目标地点（可选，如果缺失会从 user_query 提取）
        max_budget: 最大预算（可选）
        max_commute_time: 最大通勤时间（可选）
        其他参数...
        **kwargs: 接受任何额外参数（LLM 可能会传递 property_type 等）
    
    Returns:
        包含搜索结果或澄清问题的字典
    """
    # 记录任何额外传递的参数（用于调试）
    if kwargs:
        print(f"   ℹ️ 收到额外参数（已忽略）: {kwargs}")
    
    try:
        print(f"\n{'='*60}")
        print(f"🏠 [SEARCH TOOL] 开始执行房源搜索")
        print(f"   user_query: {user_query}")
        print(f"   location: {location}")
        print(f"   max_budget: {max_budget}")
        print(f"   max_commute_time: {max_commute_time}")
        print(f"{'='*60}")
        
        # ================================================================
        # 步骤 1: 检查参数完整性，必要时用 Fine-tuned Model 提取
        # ================================================================
        
        # 如果核心参数缺失，尝试从 user_query 提取
        if not all([location, max_budget, max_commute_time]) and user_query:
            print(f"\n📝 [SEARCH] 参数不完整，使用 Fine-tuned Model 提取...")
            
            from core.llm_interface import clarify_and_extract_criteria
            
            criteria_response = clarify_and_extract_criteria(user_query)
            print(f"   Fine-tuned 返回: {json.dumps(criteria_response, ensure_ascii=False, indent=2)}")
            
            # 合并提取的参数（优先使用显式传入的参数）
            if not location:
                location = criteria_response.get('destination')
            if not max_budget:
                max_budget = criteria_response.get('max_budget')
            if not max_commute_time:
                max_commute_time = criteria_response.get('max_travel_time')
            
            # 如果 Fine-tuned Model 需要澄清
            if criteria_response.get('status') != 'success':
                missing_fields = []
                if not location:
                    missing_fields.append("destination/location (e.g., UCL, King's College, Central London)")
                if not max_budget:
                    missing_fields.append("budget (e.g., £1500/month, £2000 pcm)")
                if not max_commute_time:
                    missing_fields.append("max commute time (e.g., 30 minutes, 45 min)")
                
                question = criteria_response.get('data', {}).get('question', '')
                if not question:
                    question = f"To search for properties, I need: {', '.join(missing_fields)}. Could you please provide this information?"
                
                return {
                    'success': False,
                    'status': 'need_clarification',
                    'question': question,
                    'missing_fields': missing_fields,
                    'extracted_so_far': {
                        'destination': location,
                        'max_budget': max_budget,
                        'max_travel_time': max_commute_time
                    }
                }
        
        # 最终参数检查
        if not location:
            return {
                'success': False,
                'status': 'need_clarification',
                'question': "Where would you like to commute to? (e.g., UCL, King's College, London Bridge)",
                'missing_fields': ['location']
            }
        
        if not max_budget:
            return {
                'success': False,
                'status': 'need_clarification', 
                'question': f"What's your monthly budget for rent near {location}?",
                'missing_fields': ['max_budget']
            }
        
        # 如果没有指定通勤时间，应该询问用户而不是自动假设
        if not max_commute_time:
            return {
                'success': False,
                'status': 'need_clarification',
                'question': f"What's the maximum commute time you're willing to accept? (e.g., 30 minutes, 45 minutes, 1 hour)",
                'missing_fields': ['max_commute_time'],
                'extracted_so_far': {
                    'destination': location,
                    'max_budget': max_budget,
                    'max_travel_time': None
                }
            }
        
        # ================================================================
        # 步骤 2: 执行 RAG 增强搜索
        # ================================================================
        print(f"\n🔍 [SEARCH] 执行 RAG 搜索...")
        print(f"   📍 位置: {location}")
        print(f"   💰 预算: £{max_budget}")
        print(f"   ⏱️ 最大通勤: {max_commute_time} 分钟")
        
        from rag.rag_coordinator import RAGCoordinator
        from core.data_loader import load_mock_properties_from_csv, parse_price
        
        # 获取 RAG Coordinator
        rag_coordinator = RAGCoordinator()
        
        # 确保属性有 parsed_price
        all_properties = load_mock_properties_from_csv()
        for prop in all_properties:
            if 'parsed_price' not in prop:
                prop['parsed_price'] = parse_price(prop.get('Price'))
        
        # 重建索引（如果需要）
        if not hasattr(rag_coordinator.property_store, 'index') or rag_coordinator.property_store.index is None:
            rag_coordinator.property_store.build_index(all_properties)
        
        criteria = {
            'destination': location,
            'max_budget': max_budget,
            'max_travel_time': max_commute_time
        }
        
        ranked_properties, past_context, area_info = rag_coordinator.enhanced_search(
            user_query or f"Find flat near {location} under £{max_budget}",
            criteria
        )
        print(f"   ✅ RAG 返回 {len(ranked_properties)} 个候选房源")
        
        # ================================================================
        # 步骤 3: 计算通勤时间并过滤
        # ================================================================
        print(f"\n⏱️ [SEARCH] 计算通勤时间...")
        
        from core.maps_service import calculate_travel_time
        import asyncio
        
        top_candidates = ranked_properties[:15]
        loop = asyncio.get_event_loop()
        
        travel_time_tasks = [
            loop.run_in_executor(
                None,
                calculate_travel_time,
                prop.get('Address', ''),
                location
            )
            for prop in top_candidates
        ]
        
        travel_times = await asyncio.gather(*travel_time_tasks, return_exceptions=True)
        
        # 添加通勤时间并过滤
        candidates_with_travel = []
        for prop, travel_time in zip(top_candidates, travel_times):
            if isinstance(travel_time, Exception):
                continue
            if travel_time and travel_time <= max_commute_time:
                prop['travel_time_minutes'] = travel_time
                prop['travel_time'] = travel_time
                candidates_with_travel.append(prop)
        
        print(f"   ✅ 通勤过滤后: {len(candidates_with_travel)} 个房源")
        
        # ================================================================
        # 步骤 4: 应用价格过滤和评分
        # ================================================================
        print(f"\n💰 [SEARCH] 应用价格过滤...")
        
        # 初始化结果列表
        perfect_match = []
        soft_violation = []
        
        if candidates_with_travel:
            # 预处理价格数据
            for prop in candidates_with_travel:
                if 'price' not in prop or not prop['price']:
                    prop['price'] = prop.get('parsed_price', parse_price(prop.get('Price', '')))
            
            perfect_match, soft_violation = PropertyFilter.apply_hard_filters(
                properties=candidates_with_travel,
                budget=max_budget,
                max_commute=max_commute_time,
                location_keywords=location,
                care_about_safety=care_about_safety
            )
            
            print(f"   ✅ 完全符合: {len(perfect_match)} 个")
            print(f"   ⚠️ 超预算可考虑: {len(soft_violation)} 个")
        else:
            print(f"   ⚠️ 没有符合通勤时间的房源，跳过价格过滤")
        
        # 排序
        def sort_key(prop):
            return -prop.get('recommendation_score', 0)
        
        perfect_match.sort(key=sort_key)
        soft_violation.sort(key=sort_key)
        
        # ================================================================
        # 步骤 4.5: 如果没有完全符合的结果，使用 RAG 找最相似的
        # ================================================================
        if not perfect_match and not soft_violation:
            print(f"\n⚠️ [SEARCH] 没有找到符合预算和通勤的房源，尝试 RAG 语义搜索最相似的...")
            
            # 使用 RAG 的语义搜索找到最相似的房源
            similar_properties = rag_coordinator.property_store.search(
                f"flat apartment near {location} budget {max_budget}",
                top_k=10
            )
            
            if similar_properties:
                # 计算这些房源的通勤时间
                similar_with_commute = []
                for prop in similar_properties[:6]:  # 只处理前6个
                    try:
                        travel_time = calculate_travel_time(
                            prop.get('Address', ''),
                            location
                        )
                        if travel_time and travel_time <= max_commute_time * 1.5:  # 允许通勤时间超50%
                            prop['travel_time'] = travel_time
                            prop['price'] = prop.get('parsed_price', parse_price(prop.get('Price', '')))
                            similar_with_commute.append(prop)
                    except:
                        continue
                
                if similar_with_commute:
                    # 按价格排序，找最接近预算的
                    similar_with_commute.sort(key=lambda x: x.get('price', float('inf')))
                    
                    # 取前3个最接近的
                    closest_3 = similar_with_commute[:3]
                    
                    # 计算建议的预算
                    min_price_needed = min(p.get('price', 0) for p in closest_3)
                    suggested_budget = int(min_price_needed * 1.05)  # 加5%余量
                    budget_increase = suggested_budget - max_budget
                    
                    # 格式化这3个推荐
                    similar_formatted = []
                    for i, prop in enumerate(closest_3, 1):
                        price = int(prop.get('price', 0))
                        over_budget = price - max_budget
                        over_percentage = round((over_budget / max_budget) * 100, 1)
                        
                        similar_formatted.append({
                            'rank': i,
                            'address': prop.get('Address', prop.get('address', 'Unknown')),
                            'price': f"£{price}/month",
                            'travel_time': f"{int(prop.get('travel_time', 0))} min to {location}",
                            'budget_status': f"⚠️ Over budget by £{over_budget} ({over_percentage}%)",
                            'price_raw': price,
                            'over_budget': over_budget,
                            'similarity_score': round(prop.get('similarity_score', 0) * 100, 1),
                            'property_type': prop.get('Type', prop.get('type', 'Flat')),
                            'bedrooms': prop.get('Bedrooms', prop.get('bedrooms', 'N/A')),
                            'match_type': 'similar_suggestion',
                            'url': prop.get('URL', prop.get('url', ''))
                        })
                    
                    return {
                        'success': True,
                        'status': 'no_exact_match_but_similar',
                        'message': f"Based on our database, no properties were found within your budget of £{max_budget}/month and {max_commute_time} min commute to {location}.",
                        'suggestion': f"However, I found {len(closest_3)} similar properties. The closest match is £{int(closest_3[0].get('price', 0))}/month. Would you consider increasing your budget by approximately £{budget_increase} (to £{suggested_budget}/month)?",
                        'similar_properties': similar_formatted,
                        'suggested_budget': suggested_budget,
                        'budget_increase_needed': budget_increase,
                        'search_criteria': {
                            'destination': location,
                            'max_budget': max_budget,
                            'max_commute_time': max_commute_time
                        },
                        'recommendations': similar_formatted  # 也放在 recommendations 中让前端可以展示
                    }
            
            # 如果 RAG 也没有找到
            return {
                'success': True,
                'status': 'no_results',
                'message': f"Unfortunately, no properties were found in our database near {location} within {max_commute_time} minutes. This might be because:\n\n1. Your budget of £{max_budget}/month might be too low for the {location} area\n2. The commute time of {max_commute_time} minutes might be too restrictive\n\n**Suggestions:**\n- Try increasing your budget to £{int(max_budget * 1.3)}/month\n- Or extend your commute time to {int(max_commute_time * 1.5)} minutes\n- Or consider different nearby areas",
                'recommendations': []
            }
        
        # 限制结果数量
        perfect_limited = perfect_match[:limit]
        soft_limited = soft_violation[:3]
        
        # ================================================================
        # 步骤 5: 格式化结果
        # ================================================================
        all_results = perfect_limited + soft_limited
        
        formatted_results = []
        for i, prop in enumerate(all_results[:limit], 1):
            formatted_results.append({
                'rank': i,
                'address': prop.get('Address', prop.get('address', 'Unknown')),
                'price': f"£{int(prop.get('price', 0))}/month",
                'travel_time': f"{int(prop.get('travel_time', 0))} min to {location}",
                'budget_status': prop.get('budget_status', ''),
                'score': prop.get('recommendation_score', 0),
                'property_type': prop.get('Type', prop.get('type', 'Flat')),
                'bedrooms': prop.get('Bedrooms', prop.get('bedrooms', 'N/A')),
                'match_type': prop.get('match_type', 'perfect'),
                'url': prop.get('URL', prop.get('url', ''))
            })
        
        return {
            'success': True,
            'status': 'found',
            'total_found': len(all_results),
            'search_criteria': {
                'destination': location,
                'max_budget': max_budget,
                'max_commute_time': max_commute_time
            },
            'recommendations': formatted_results,
            'summary': f"Found {len(perfect_match)} properties within budget (£{max_budget}/month) and {len(soft_violation)} slightly over budget, all within {max_commute_time} min of {location}."
        }

    except Exception as e:
        print(f"   ❌ 搜索房源出错: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'status': 'error',
            'error': str(e)
        }


# 创建工具实例
search_properties_tool = Tool(
    name="search_properties",

    description="""Search for rental properties in the UK. This is the MAIN tool for finding apartments, flats, rooms, or any housing.

USE THIS TOOL WHEN the user:
- Wants to find/search for a place to live
- Mentions rent, accommodation, flat, apartment, room, housing
- Asks about properties near a location
- Mentions budget and commute requirements

WORKFLOW:
1. Call this tool with the user's query
2. If parameters are missing, the tool returns a clarification question
3. Once complete, returns property recommendations

IMPORTANT:
- You can pass just user_query and let the tool extract parameters
- Or pass explicit location, max_budget, max_commute_time if known
- The tool uses Fine-tuned AI to understand natural language""",

    func=search_properties_impl,

    parameters={
        'type': 'object',
        'properties': {
            'user_query': {
                'type': 'string',
                'description': 'The user\'s natural language query about finding properties. The tool will extract location, budget, and commute time from this.'
            },
            'location': {
                'type': 'string',
                'description': 'Target commute destination (e.g., UCL, King\'s College, London Bridge). Optional if user_query contains this.'
            },
            'max_budget': {
                'type': 'integer',
                'description': 'Maximum monthly budget in GBP (e.g., 1500, 2000). Optional if user_query contains this.'
            },
            'max_commute_time': {
                'type': 'integer',
                'description': 'Maximum commute time in minutes. ONLY provide if user explicitly mentions a time limit. Do NOT assume a default.'
            },
            'care_about_safety': {
                'type': 'boolean',
                'description': 'Whether user cares about area safety/crime rates.',
                'default': False
            },
            'limit': {
                'type': 'integer',
                'description': 'Maximum number of results to return.',
                'default': 10
            }
        },
        'required': []  # 没有必须参数 - 工具内部会处理
    },

    max_retries=2
)
