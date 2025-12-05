"""
True ReAct Agent - 完全基于 LLM 自主决策

核心原则：
1. LLM 完全自主决定使用哪个工具
2. LLM 完全自主生成工具参数
3. 代码只负责：解析 LLM 输出 → 执行工具 → 返回观察结果
4. 没有任何关键词匹配或硬编码规则

这个版本兼容 app.py 的调用方式
"""

import asyncio
import json
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# POI 类型信息（用于格式化输出）
POI_TYPES = {
    "restaurant": {"icon": "🍽️", "name": "Restaurant"},
    "chinese_restaurant": {"icon": "🥢", "name": "Chinese Restaurant"},
    "supermarket": {"icon": "🛒", "name": "Supermarket"},
    "convenience": {"icon": "🏪", "name": "Convenience Store"},
    "cafe": {"icon": "☕", "name": "Cafe"},
    "pharmacy": {"icon": "💊", "name": "Pharmacy"},
    "gym": {"icon": "🏋️", "name": "Gym"},
    "park": {"icon": "🌳", "name": "Park"},
    "bus_stop": {"icon": "🚌", "name": "Bus Stop"},
    "tube_station": {"icon": "🚇", "name": "Tube Station"},
    "bank": {"icon": "🏦", "name": "Bank"},
    "atm": {"icon": "💳", "name": "ATM"}
}

# ReAct Prompt - 简洁版，让 LLM 自主决策
REACT_PROMPT_TEMPLATE = """You are Alex, a friendly rental assistant helping international students find housing in UK.

## Your Persona
You are talking to an INTERNATIONAL STUDENT (likely from China). Think from their perspective:
- They are NEW to UK, unfamiliar with local rental market
- They need STUDENT-FRIENDLY options (student halls, HMOs, spare rooms, not Rightmove luxury flats)
- Budget is usually limited (£600-£1500/month)
- They need practical info: how to rent as a student, which areas have students, safety concerns

## Response Format (STRICT - no markdown ** around keywords)
Thought: [reasoning]
Action: [tool name]
Action Input: [JSON parameters]

## IMPORTANT: For Complex Questions, Use multi_search
When user asks about MULTIPLE topics (e.g., rent + living costs + transport), use multi_search:

Action: multi_search
Action Input: {{"searches": [
  {{"tool": "web_search", "params": {{"query": "London student rent 2024"}}}},
  {{"tool": "web_search", "params": {{"query": "London food cost students"}}}},
  {{"tool": "web_search", "params": {{"query": "London transport cost students"}}}}
]}}

This will execute ALL searches and return combined results.

## Available Tools

### get_property_details (PRIORITY for property-specific questions)
- Use when user asks about a SPECIFIC property from our database
- Use when user clicks "Ask AI" button for a property
- Use when user questions a property's room type, price, amenities, etc.
- Example: {{"property_name": "Scape Bloomsbury", "property_address": "Woburn Place"}}
- IMPORTANT: Use THIS tool instead of web_search when asking about properties we recommended

### multi_search (for complex multi-topic questions)
- Executes multiple tool calls in parallel
- Use when question has 2+ sub-topics
- Returns combined Observation from all tools

### web_search (USE ENGLISH QUERIES ONLY)
- Query MUST be in English, short: 3-8 words
- Example: "London student room rent 2024"
- DO NOT use for properties in our database - use get_property_details instead

### get_weather
- Example: {{"location": "London"}}
- For comparing cities, use multi_search with multiple get_weather calls

### search_properties, calculate_commute, check_safety, search_nearby_pois

## Rules
1. Reply in user's language (Chinese if they speak Chinese)
2. MUST call tool first - no direct answers
3. Use ONLY Observation data - NO fabrication
4. For multi-topic questions, ALWAYS use multi_search

## Context
{context_info}

## Query
{user_query}

Thought:"""


class ReActAgent:
    """
    True ReAct Agent - LLM 完全自主决策
    
    兼容 app.py 的调用方式：
    - 支持 max_turns 参数
    - 支持 verbose 参数
    - 支持 extracted_context 属性
    - async run() 方法返回结果字典
    """
    
    def __init__(self, tool_registry, max_turns: int = 5, verbose: bool = True):
        """
        初始化 ReAct Agent
        
        Args:
            tool_registry: ToolRegistry 实例
            max_turns: 最大循环次数
            verbose: 是否打印详细日志
        """
        self.tool_registry = tool_registry
        self.max_turns = max_turns
        self.verbose = verbose
        self.extracted_context = {}  # 用于存储从上下文中提取的信息
        
        # 🆕 用户偏好系统 - 在对话过程中积累
        self.user_preferences = {
            'hard_preferences': [],  # 硬性要求（必须满足）如: "不要 Brent Cross", "必须有健身房"
            'soft_preferences': [],  # 软性偏好（尽量满足）如: "喜欢安静", "偏好现代装修"
            'excluded_areas': [],    # 明确排除的区域
            'required_amenities': [],  # 必须有的设施
            'safety_concerns': [],   # 安全相关的记录
        }
        
        # 🆕 搜索条件累积 - 保存 Fine-tuned model 提取的信息，跨对话保持
        self.accumulated_search_criteria = {
            'destination': None,
            'max_budget': None,
            'max_travel_time': None,
            'property_features': [],     # 如: ['studio', 'private', 'en-suite']
            'soft_preferences': [],      # 如: ['quiet area', 'modern building']
            'amenities_of_interest': [], # 如: ['gym', 'pool']
        }
        
        # 初始化 LLM
        from core.llm_interface import LLMInterface
        self.llm = LLMInterface()
    
    def update_search_criteria(self, new_criteria: dict):
        """
        累积更新搜索条件 - 合并新提取的条件与已有条件
        
        这确保了之前提取的信息（如 'studio', 'private'）不会丢失
        """
        if not new_criteria:
            return
        
        # 更新单值字段（如果新值存在则覆盖）
        for field in ['destination', 'max_budget', 'max_travel_time']:
            if new_criteria.get(field):
                self.accumulated_search_criteria[field] = new_criteria[field]
                print(f"📝 [SearchCriteria] Updated {field}: {new_criteria[field]}")
        
        # 累积列表字段（合并不重复）
        # 🔧 修复：正确处理字符串类型的 soft_preferences
        for field in ['property_features', 'soft_preferences', 'amenities_of_interest']:
            new_items = new_criteria.get(field, [])
            
            # 如果是字符串，转换为列表
            if isinstance(new_items, str) and new_items:
                new_items = [new_items]  # 作为整体添加，不要拆分字符
            elif not isinstance(new_items, list):
                new_items = []
            
            for item in new_items:
                # 跳过单个字符（可能是之前错误拆分的结果）
                if item and isinstance(item, str) and len(item) > 1 and item not in self.accumulated_search_criteria[field]:
                    self.accumulated_search_criteria[field].append(item)
                    print(f"📝 [SearchCriteria] Added to {field}: {item}")
        
        # 🆕 处理 property_tags (Fine-tuned model 返回的)
        property_tags = new_criteria.get('property_tags', [])
        if isinstance(property_tags, list):
            for tag in property_tags:
                if tag and tag not in self.accumulated_search_criteria['property_features']:
                    self.accumulated_search_criteria['property_features'].append(tag)
                    print(f"📝 [SearchCriteria] Added property tag: {tag}")
    
    def get_accumulated_criteria(self) -> dict:
        """获取当前累积的所有搜索条件"""
        return {
            'destination': self.accumulated_search_criteria['destination'],
            'max_budget': self.accumulated_search_criteria['max_budget'],
            'max_travel_time': self.accumulated_search_criteria['max_travel_time'],
            'property_features': self.accumulated_search_criteria['property_features'].copy(),
            'soft_preferences': self.accumulated_search_criteria['soft_preferences'].copy(),
            'amenities_of_interest': self.accumulated_search_criteria['amenities_of_interest'].copy(),
        }
    
    def add_preference(self, pref_type: str, preference: str):
        """添加用户偏好"""
        if pref_type in self.user_preferences and preference:
            if preference not in self.user_preferences[pref_type]:
                self.user_preferences[pref_type].append(preference)
                print(f"📝 [Preference] Added {pref_type}: {preference}")
    
    def get_preferences_context(self) -> str:
        """获取用户偏好上下文，供搜索时使用"""
        parts = []
        
        if self.user_preferences['hard_preferences']:
            parts.append(f"HARD REQUIREMENTS (must satisfy): {'; '.join(self.user_preferences['hard_preferences'])}")
        
        if self.user_preferences['soft_preferences']:
            parts.append(f"SOFT PREFERENCES (try to satisfy): {'; '.join(self.user_preferences['soft_preferences'])}")
        
        if self.user_preferences['excluded_areas']:
            parts.append(f"⛔ EXCLUDED AREAS (do NOT recommend): {', '.join(self.user_preferences['excluded_areas'])}")
        
        if self.user_preferences['required_amenities']:
            parts.append(f"REQUIRED AMENITIES: {', '.join(self.user_preferences['required_amenities'])}")
        
        if self.user_preferences['safety_concerns']:
            parts.append(f"⚠️ SAFETY CONCERNS: {'; '.join(self.user_preferences['safety_concerns'])}")
        
        return '\n'.join(parts) if parts else ''
    
    def extract_preferences_from_interaction(self, user_message: str, agent_response: str, tool_results: dict = None):
        """
        从用户互动中自动提取偏好
        
        这个方法在每次互动后调用，分析用户消息和工具结果来更新偏好
        """
        user_lower = user_message.lower()
        
        # 检测安全相关担忧
        safety_keywords = ['safe', 'safety', 'crime', 'dangerous', 'worried', 'afraid', 'scared', 'unsafe']
        if any(kw in user_lower for kw in safety_keywords):
            # 检查是否提到了具体区域
            areas = ['brent cross', 'brent', 'hackney', 'tottenham', 'brixton', 'peckham', 'lewisham']
            for area in areas:
                if area in user_lower:
                    concern = f"User expressed safety concerns about {area.title()}"
                    self.add_preference('safety_concerns', concern)
                    # 如果工具返回了低安全分数，添加到排除区域
                    if tool_results and isinstance(tool_results, dict):
                        safety_score = tool_results.get('safety_score', 100)
                        if safety_score < 50:
                            self.add_preference('excluded_areas', area.title())
                            self.add_preference('hard_preferences', f"Avoid {area.title()} - safety score only {safety_score}/100")
        
        # 检测设施需求
        amenity_patterns = {
            'gym': ['gym', 'fitness', 'workout', 'exercise'],
            'pool': ['pool', 'swimming'],
            'parking': ['parking', 'car park'],
            'laundry': ['laundry', 'washing machine'],
            'balcony': ['balcony', 'terrace', 'outdoor space'],
            'concierge': ['concierge', '24/7', 'reception'],
        }
        
        for amenity, keywords in amenity_patterns.items():
            if any(kw in user_lower for kw in keywords):
                # 检查是否是强烈需求
                if any(word in user_lower for word in ['must', 'need', 'require', 'essential', 'important']):
                    self.add_preference('required_amenities', amenity)
                    self.add_preference('hard_preferences', f"Must have {amenity}")
                else:
                    self.add_preference('soft_preferences', f"Would like {amenity}")
        
        # 检测排除偏好
        exclude_patterns = ['don\'t want', 'not interested', 'avoid', 'no thanks', 'not', 'without']
        if any(pattern in user_lower for pattern in exclude_patterns):
            # 尝试提取被排除的内容
            if 'brent' in user_lower:
                self.add_preference('excluded_areas', 'Brent Cross')
            if 'zone 3' in user_lower or 'zone 4' in user_lower:
                self.add_preference('hard_preferences', 'Prefer Zone 1-2 only')
        
        # 检测生活方式偏好
        lifestyle_patterns = {
            'quiet': 'Prefers quiet neighborhood',
            'vibrant': 'Likes vibrant/lively area',
            'social': 'Values social facilities',
            'study': 'Needs good study environment',
            'cooking': 'Wants to cook - needs kitchen facilities',
            'guest': 'Will have guests - needs flexible guest policy',
            'couple': 'Living as a couple',
            'female': 'Female student - safety is priority',
            'late night': 'Often comes home late - needs safe walking routes',
        }
        
        for keyword, preference in lifestyle_patterns.items():
            if keyword in user_lower:
                self.add_preference('soft_preferences', preference)
    
    def _build_tool_descriptions(self) -> str:
        """构建工具描述，供 LLM 理解每个工具的用途"""
        descriptions = []
        
        for tool_name, tool in self.tool_registry.tools.items():
            desc = f"### {tool_name}\n"
            desc += f"Description: {tool.description}\n"
            
            # 添加参数说明
            params = tool.parameters.get('properties', {})
            required = tool.parameters.get('required', [])
            
            if params:
                desc += "Parameters (as JSON):\n"
                for param_name, param_info in params.items():
                    req_mark = "[REQUIRED]" if param_name in required else "[optional]"
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    desc += f"  - {param_name} ({param_type}) {req_mark}: {param_desc}\n"
            
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def _build_context_info(self, context: Optional[Dict] = None) -> str:
        """构建上下文信息字符串，包含房产详细信息"""
        info_parts = []
        
        # 🆕 用户偏好（最重要，放在最前面）
        prefs_context = self.get_preferences_context()
        if prefs_context:
            info_parts.append("=== USER PREFERENCES (ACCUMULATED FROM CONVERSATION) ===")
            info_parts.append(prefs_context)
            info_parts.append("=== END PREFERENCES ===")
            info_parts.append("")
            info_parts.append("CRITICAL: When recommending properties, you MUST respect these preferences!")
            info_parts.append("- Do NOT recommend properties in excluded areas")
            info_parts.append("- Prioritize properties that match required amenities")
            info_parts.append("- Consider safety concerns when ranking")
            info_parts.append("")
        
        # 🆕 之前搜索过的房产列表（用于安全问题等后续问题）
        if self.extracted_context.get('previous_search_results'):
            info_parts.append("=== PREVIOUSLY SHOWN PROPERTIES ===")
            info_parts.append(self.extracted_context['previous_search_results'])
            info_parts.append("=== END PREVIOUS RESULTS ===")
            info_parts.append("")
            info_parts.append("NOTE: User already has these property recommendations. If they ask about safety/amenities/comparison, use these properties - don't start a new search!")
            info_parts.append("")
        
        # 🆕 设施搜索结果（优先显示）
        if self.extracted_context.get('amenity_search_results'):
            info_parts.append(self.extracted_context['amenity_search_results'])
            info_parts.append("")
        
        # 🆕 对比查询的房产信息（优先显示）
        if self.extracted_context.get('comparison_properties'):
            info_parts.append("=== PROPERTY COMPARISON DATA (FROM DATABASE) ===")
            info_parts.append(self.extracted_context['comparison_properties'])
            info_parts.append("=== END COMPARISON DATA ===")
            info_parts.append("")
            info_parts.append("CRITICAL: Use ONLY the property data above to answer the comparison question.")
            info_parts.append("Do NOT call any external APIs. Do NOT say 'unverified'. This data is from our trusted database.")
            info_parts.append("Compare the properties based on: price, location, amenities, commute times, room type, etc.")
            info_parts.append("")
        
        # 从 extracted_context 获取单个房产信息
        if self.extracted_context.get('property_address'):
            info_parts.append(f"=== Current Property Context ===")
            info_parts.append(f"Property Address: {self.extracted_context['property_address']}")
            
            if self.extracted_context.get('property_price'):
                info_parts.append(f"Price: {self.extracted_context['property_price']}")
            if self.extracted_context.get('property_travel_time'):
                info_parts.append(f"Commute Time: {self.extracted_context['property_travel_time']}")
            
            # 🆕 添加详细信息（如果有的话）
            if self.extracted_context.get('room_type'):
                info_parts.append(f"Room Type: {self.extracted_context['room_type']}")
            
            if self.extracted_context.get('amenities'):
                info_parts.append(f"Detailed Amenities: {self.extracted_context['amenities']}")
            
            if self.extracted_context.get('guest_policy'):
                info_parts.append(f"Guest Policy: {self.extracted_context['guest_policy']}")
            
            if self.extracted_context.get('payment_rules'):
                info_parts.append(f"Payment Rules: {self.extracted_context['payment_rules']}")
            
            if self.extracted_context.get('excluded_features'):
                info_parts.append(f"NOT Included: {self.extracted_context['excluded_features']}")
            
            if self.extracted_context.get('description'):
                info_parts.append(f"Description (includes commute info): {self.extracted_context['description']}")
            
            # 🆕 添加 URL
            if self.extracted_context.get('property_url'):
                info_parts.append(f"Booking URL: {self.extracted_context['property_url']}")
            
            info_parts.append(f"=== End Property Context ===")
            info_parts.append("")
            info_parts.append("IMPORTANT: If the user is asking about this property's details (payment, amenities, guests, guarantor, commute, booking link, etc.), answer using the information above. Do NOT call external APIs! We have the URL!")
        
        # 从 context 参数获取额外信息（如果 extracted_context 没有）
        elif context and context.get('property'):
            prop = context['property']
            info_parts.append(f"User is viewing property: {prop.get('address', 'Unknown')}")
            if prop.get('price'):
                info_parts.append(f"  Price: {prop['price']}")
            if prop.get('geo_location'):
                info_parts.append(f"  Location: {prop['geo_location']}")
            if prop.get('url'):
                info_parts.append(f"  Booking URL: {prop['url']}")
        
        if not info_parts:
            return "No specific property context. If user asks about a specific property, use Final Answer with database info if available."
        
        return "\n".join(info_parts)
    
    def _parse_llm_output(self, output: str) -> Dict[str, Any]:
        """
        解析 LLM 输出，提取 Thought、Action、Action Input
        增强版：能够从不规范的输出中提取工具名
        """
        result = {
            'thought': None,
            'action': None,
            'action_input': None,
            'raw_output': output
        }
        
        if not output:
            return result
        
        # 🆕 清理 markdown 格式（如 **Thought:** 变成 Thought:）
        # 处理 **Final Answer:** 和 **Action:** 等格式
        output = re.sub(r'\*\*([A-Za-z ]+):\*\*', r'\1:', output)
        output = re.sub(r'\*\*([A-Za-z ]+):', r'\1:', output)  # **Final Answer: 没有结束的 **
        
        # 🆕 特别处理：如果输出以 **Final Answer: 或 Final Answer: 开头，直接提取
        final_answer_match = re.match(r'^\s*(?:\*\*)?Final Answer:?(?:\*\*)?\s*(.+)', output, re.DOTALL | re.IGNORECASE)
        if final_answer_match:
            result['action'] = 'final_answer'
            result['action_input'] = final_answer_match.group(1).strip()
            print(f"  🔧 [PARSE] 直接提取 Final Answer")
            return result
        
        # 已知的工具列表（用于智能匹配）
        known_tools = ['search_properties', 'calculate_commute', 'check_safety', 
                       'get_weather', 'web_search', 'search_nearby_pois', 'multi_search', 'final answer']
        
        # 🆕 检查输出是否缺少格式，第一行直接就是工具名
        first_line = output.strip().split('\n')[0].strip().lower()
        if first_line in known_tools or first_line.replace('_', ' ') in known_tools:
            # LLM 直接输出了工具名，没有 Thought/Action 格式
            # 尝试修复：假设第一行是 Action，后面是 Action Input
            tool_name = first_line.replace(' ', '_') if first_line == 'final answer' else first_line
            remaining = '\n'.join(output.strip().split('\n')[1:]).strip()
            
            # 检查是否有 Action Input: 前缀
            if remaining.lower().startswith('action input:'):
                remaining = remaining[len('action input:'):].strip()
            
            result['action'] = tool_name
            # 尝试解析 JSON
            if remaining.startswith('{'):
                try:
                    brace_count = 0
                    for i, char in enumerate(remaining):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                result['action_input'] = json.loads(remaining[:i+1])
                                break
                except json.JSONDecodeError:
                    result['action_input'] = remaining
            else:
                result['action_input'] = remaining
            
            print(f"  🔧 [PARSE] 从无格式输出中提取工具: {tool_name}")
            return result
        
        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|$)', output, re.DOTALL | re.IGNORECASE)
        if thought_match:
            result['thought'] = thought_match.group(1).strip()
        
        # 提取 Action
        action_match = re.search(r'Action:\s*(.+?)(?=Action Input:|$)', output, re.DOTALL | re.IGNORECASE)
        if action_match:
            action_raw = action_match.group(1).strip()
            # 取第一行
            action_line = action_raw.split('\n')[0].strip()
            
            # 🆕 特殊处理：如果 Action 是 JSON 格式（模型输出错误格式）
            # 例如：Action: {"query": "..."} 应该被识别为 web_search
            if action_line.startswith('{'):
                try:
                    action_json = json.loads(action_line)
                    # 根据 JSON 的 key 推断工具类型
                    if 'query' in action_json:
                        result['action'] = 'web_search'
                        result['action_input'] = action_json
                        print(f"  🔧 [PARSE] 从 JSON Action 推断工具: web_search")
                        return result
                    elif 'location' in action_json:
                        result['action'] = 'get_weather'
                        result['action_input'] = action_json
                        print(f"  🔧 [PARSE] 从 JSON Action 推断工具: get_weather")
                        return result
                    elif 'origin' in action_json or 'destination' in action_json:
                        result['action'] = 'calculate_commute'
                        result['action_input'] = action_json
                        print(f"  🔧 [PARSE] 从 JSON Action 推断工具: calculate_commute")
                        return result
                    elif 'address' in action_json or 'area' in action_json:
                        result['action'] = 'check_safety'
                        result['action_input'] = action_json
                        print(f"  🔧 [PARSE] 从 JSON Action 推断工具: check_safety")
                        return result
                except json.JSONDecodeError:
                    pass  # 不是有效 JSON，继续正常解析
            
            # 智能提取工具名：检查是否直接是工具名
            action_lower = action_line.lower()
            
            # 方法1：直接匹配已知工具
            matched_tool = None
            for tool in known_tools:
                if action_lower == tool or action_lower == tool.replace('_', ' '):
                    matched_tool = tool.replace(' ', '_') if tool == 'final answer' else tool
                    break
            
            # 方法2：如果Action包含已知工具名，提取它
            if not matched_tool:
                for tool in known_tools:
                    if tool in action_lower or tool.replace('_', ' ') in action_lower:
                        matched_tool = tool.replace(' ', '_') if tool == 'final answer' else tool
                        break
            
            # 方法3：检查是否包含工具名模式
            if not matched_tool:
                tool_pattern = re.search(r'(search_properties|calculate_commute|check_safety|get_weather|web_search|search_nearby_pois|multi_search|final\s*answer)', action_lower)
                if tool_pattern:
                    matched_tool = tool_pattern.group(1).replace(' ', '_')
            
            result['action'] = matched_tool if matched_tool else action_line
            
            if matched_tool and matched_tool != action_line.lower():
                print(f"  🔧 [PARSE] 从 '{action_line}' 中提取工具: {matched_tool}")
        
        # 提取 Action Input
        input_match = re.search(r'Action Input:\s*(.+?)(?=Thought:|Observation:|$)', output, re.DOTALL | re.IGNORECASE)
        if input_match:
            input_str = input_match.group(1).strip()
            
            # 尝试解析 JSON（支持嵌套）
            try:
                # 查找 JSON 对象（支持嵌套的花括号）
                brace_count = 0
                start_idx = -1
                for i, char in enumerate(input_str):
                    if char == '{':
                        if brace_count == 0:
                            start_idx = i
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0 and start_idx != -1:
                            json_str = input_str[start_idx:i+1]
                            result['action_input'] = json.loads(json_str)
                            break
                
                # 🆕 检查是否是嵌套格式 {'tool_name': {...params...}}
                if result['action_input'] and isinstance(result['action_input'], dict):
                    parsed_input = result['action_input']
                    known_tools = ['search_properties', 'calculate_commute', 'check_safety', 
                                   'get_weather', 'web_search', 'search_nearby_pois', 'multi_search']
                    
                    # 如果只有一个键且是工具名，提取内部参数
                    if len(parsed_input) == 1:
                        key = list(parsed_input.keys())[0]
                        if key in known_tools:
                            # 这是嵌套格式，提取工具名和参数
                            result['action'] = key
                            result['action_input'] = parsed_input[key]
                            print(f"  🔧 [PARSE] 从嵌套格式提取工具: {key}")
                
                # 如果没有找到 JSON，保留原始字符串
                if result['action_input'] is None:
                    result['action_input'] = input_str
                    
            except json.JSONDecodeError:
                # JSON 解析失败，保留原始字符串
                result['action_input'] = input_str
        
        return result
    
    async def _execute_multi_search(self, searches: list) -> tuple:
        """
        执行多个工具调用并合并结果
        
        Args:
            searches: 搜索列表，格式为 [{"tool": "web_search", "params": {"query": "..."}}, ...]
        
        Returns:
            tuple: (combined_observation, combined_raw_data)
        """
        if self.verbose:
            print(f"\n🔀 [MultiSearch] 开始执行 {len(searches)} 个并行搜索...")
        
        all_observations = []
        all_raw_data = {}
        
        for i, search in enumerate(searches):
            tool_name = search.get('tool', 'web_search')
            params = search.get('params', {})
            
            if self.verbose:
                print(f"\n  {'='*50}")
                print(f"  📍 [Sub-Query {i+1}/{len(searches)}]")
                print(f"     Tool: {tool_name}")
                print(f"     Params: {json.dumps(params, ensure_ascii=False)}")
            
            # 执行单个工具
            observation, raw_data = await self._execute_tool(tool_name, params)
            
            # 🆕 确保 observation 是字符串
            if not isinstance(observation, str):
                observation = str(observation)
            
            # 🆕 对于 web_search，提取 results 字段（更简洁的显示）
            if tool_name == 'web_search' and raw_data and isinstance(raw_data, dict):
                if 'results' in raw_data:
                    observation = raw_data['results']
            
            # 🆕 详细打印 sub-observation
            if self.verbose:
                print(f"  📄 [Sub-Observation {i+1}]:")
                print(f"  {'-'*48}")
                # 打印完整的 observation，不截断
                for line in observation.split('\n'):
                    print(f"     {line}")
                print(f"  {'-'*48}")
            
            # 格式化这个子搜索的结果
            sub_result = f"### Sub-search {i+1}: {tool_name}\n"
            sub_result += f"Parameters: {json.dumps(params, ensure_ascii=False)}\n"
            sub_result += f"Result:\n{observation}\n"
            
            all_observations.append(sub_result)
            
            if raw_data:
                all_raw_data[f"{tool_name}_{i+1}"] = raw_data
        
        # 合并所有观察结果
        combined_observation = "\n" + "="*50 + "\n"
        combined_observation += "## Combined Results from Multi-Search\n"
        combined_observation += "="*50 + "\n\n"
        combined_observation += "\n---\n".join(all_observations)
        combined_observation += "\n" + "="*50 + "\n"
        combined_observation += f"Total: {len(searches)} searches completed.\n"
        combined_observation += "Use ALL the above data to provide a comprehensive answer.\n"
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"✅ [MultiSearch] 完成! 共 {len(searches)} 个搜索")
            print(f"{'='*60}")
            print(f"📋 [Combined Observation - 完整内容]:")
            print(f"{'-'*60}")
            print(combined_observation)
            print(f"{'-'*60}")
        
        return (combined_observation, all_raw_data)
    
    async def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> tuple:
        """
        执行工具并返回观察结果
        
        Returns:
            tuple: (observation_string, raw_result_data)
            - observation_string: 用于 LLM 理解的文本观察
            - raw_result_data: 原始工具返回数据（用于传递给前端）
        """
        try:
            # 检查工具是否存在
            if tool_name not in self.tool_registry.tools:
                available_tools = list(self.tool_registry.tools.keys())
                return (f"Error: Tool '{tool_name}' not found. Available tools: {available_tools}", None)
            
            if self.verbose:
                print(f"  🔧 [ReAct] 执行工具: {tool_name}")
                print(f"     参数: {json.dumps(params, ensure_ascii=False)}")
            
            # 🆕 对于 search_properties，注入累积的搜索条件
            if tool_name == 'search_properties':
                accumulated = self.get_accumulated_criteria()
                
                # 注入累积的条件（如果工具参数中没有提供）
                if not params.get('location') and accumulated.get('destination'):
                    params['location'] = accumulated['destination']
                    print(f"  📥 [ReAct] 注入累积 destination: {accumulated['destination']}")
                
                if not params.get('max_budget') and accumulated.get('max_budget'):
                    params['max_budget'] = accumulated['max_budget']
                    print(f"  📥 [ReAct] 注入累积 max_budget: {accumulated['max_budget']}")
                
                if not params.get('max_commute_time') and accumulated.get('max_travel_time'):
                    params['max_commute_time'] = accumulated['max_travel_time']
                    print(f"  📥 [ReAct] 注入累积 max_travel_time: {accumulated['max_travel_time']}")
                
                # 🆕 注入累积的 property_features 和 soft_preferences
                if accumulated.get('property_features'):
                    params['property_features'] = accumulated['property_features']
                    print(f"  📥 [ReAct] 注入累积 property_features: {accumulated['property_features']}")
                
                if accumulated.get('soft_preferences'):
                    params['accumulated_preferences'] = accumulated['soft_preferences']
                    print(f"  📥 [ReAct] 注入累积 soft_preferences: {accumulated['soft_preferences']}")
            
            # 执行工具（异步）
            result = await self.tool_registry.execute_tool(tool_name, **params)
            
            # 保存原始数据
            raw_data = result.data if result.success else None
            
            # 🆕 如果是 search_properties，从返回结果中提取并累积搜索条件
            if tool_name == 'search_properties' and raw_data:
                extracted = raw_data.get('extracted_so_far') or raw_data.get('search_criteria') or {}
                if extracted:
                    self.update_search_criteria(extracted)
                    print(f"  📝 [ReAct] 已累积搜索条件: {extracted}")
            
            # 格式化结果供 LLM 阅读
            if result.success:
                if self.verbose:
                    print(f"  ✅ [ReAct] 工具执行成功")
                
                # 🆕 完整输出所有数据，不截断！
                # 原因：截断会导致无法溯源，无法区分是模型幻觉还是数据源问题
                if isinstance(result.data, dict):
                    observation = json.dumps(result.data, ensure_ascii=False, indent=2)
                elif isinstance(result.data, list):
                    # 🚫 移除截断逻辑 - 必须完整保留所有数据供溯源
                    observation = json.dumps(result.data, ensure_ascii=False, indent=2)
                    if self.verbose:
                        print(f"  📋 [ReAct] 完整返回 {len(result.data)} 条结果（不截断）")
                else:
                    observation = str(result.data)
                
                # 🆕 调试输出：打印完整的 observation 到日志
                if self.verbose:
                    print(f"\n{'='*60}")
                    print(f"📝 [Tool Result - 完整内容，用于溯源调试]")
                    print(f"{'='*60}")
                    print(observation)
                    print(f"{'='*60}\n")
                
                return (observation, raw_data)
            else:
                if self.verbose:
                    print(f"  ❌ [ReAct] 工具执行失败: {result.error}")
                return (f"Error: {result.error}", None)
                
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} with {params}: {e}")
            import traceback
            traceback.print_exc()
            return (f"Error executing {tool_name}: {str(e)}", None)
    
    def _majority_vote_tool_selection(self, prompt: str, num_votes: int = 5) -> Dict[str, Any]:
        """
        多数投票机制选择工具
        
        让 LLM 进行多次独立的工具选择，然后选择得票最多的工具。
        这可以减少单次推理的偶然错误。
        
        Args:
            prompt: 当前的 prompt
            num_votes: 投票次数（默认5次）
        
        Returns:
            投票结果最多的解析结果
        """
        from collections import Counter
        
        votes = []  # 存储每次投票的 (action, parsed_result)
        all_parsed = []  # 存储所有解析结果，用于后续选择
        
        if self.verbose:
            print(f"\n🗳️ [Voting] 开始 {num_votes} 次投票选择工具...")
        
        for i in range(num_votes):
            # 调用 LLM（每次独立调用）
            llm_response = self.llm.generate_react_response(prompt)
            
            if not llm_response:
                continue
            
            # 解析输出
            parsed = self._parse_llm_output(llm_response)
            
            if parsed['action']:
                action = parsed['action'].lower().strip()
                votes.append(action)
                all_parsed.append((action, parsed, llm_response))
                
                if self.verbose:
                    print(f"   Vote {i+1}: {action}")
        
        if not votes:
            if self.verbose:
                print(f"   ⚠️ 没有有效投票")
            return None, None
        
        # 统计投票
        vote_counter = Counter(votes)
        winner, winner_count = vote_counter.most_common(1)[0]
        
        if self.verbose:
            print(f"   📊 投票结果: {dict(vote_counter)}")
            print(f"   🏆 胜出: {winner} ({winner_count}/{len(votes)} 票)")
        
        # 返回胜出工具对应的第一个完整解析结果
        for action, parsed, llm_response in all_parsed:
            if action == winner:
                return parsed, llm_response
        
        return None, None
    
    async def run(self, user_query: str, context: Optional[Dict] = None, is_continuation: bool = False) -> Dict[str, Any]:
        """
        运行 ReAct Agent - 简化版：工具优先，一轮搞定
        
        新流程：
        1. 分析问题，用投票机制决定使用什么工具
        2. 执行工具，获取真实数据
        3. 把数据喂给 LLM，让它生成基于数据的回答
        
        Args:
            user_query: 用户的问题
            context: 上下文信息（包括 property 信息等）
            is_continuation: 是否是继续对话
        
        Returns:
            结果字典
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"🤖 [ReAct Agent] 开始处理（工具优先模式）...")
            print(f"   Query: {user_query}")
            print(f"{'='*60}")
        
        # 从用户消息中提取偏好
        self.extract_preferences_from_interaction(user_query, '', None)
        
        # 构建上下文（稍后根据工具类型决定是否包含房产信息）
        tool_descriptions = self._build_tool_descriptions()
        tool_data = {}
        
        # ============ 步骤1: 决定使用什么工具 ============
        if self.verbose:
            print(f"\n📋 [Step 1] 分析问题，决定使用什么工具...")
        
        # 检测问题类型
        tool_decision = self._decide_tool(user_query)
        
        if self.verbose:
            print(f"   决定: {tool_decision['tool']} - {tool_decision['reason']}")
        
        # 🆕 根据工具类型决定是否包含房产上下文
        # 对于一般信息查询（web_search, multi_search），不应该包含之前的房产搜索结果
        if tool_decision['tool'] in ['web_search', 'multi_search']:
            # 一般信息查询 - 清空与房产相关的上下文，避免混淆
            context_info = "This is a GENERAL INFORMATION query about UK/London living costs, rent prices, transport, etc. Do NOT reference any specific property listings from previous searches."
        else:
            # 房产相关查询 - 使用完整上下文
            context_info = self._build_context_info(context)
        
        # ============ 步骤2: 执行工具，获取真实数据 ============
        if self.verbose:
            print(f"\n🔧 [Step 2] 执行工具，获取真实数据...")
        
        observation = None
        raw_data = None
        
        if tool_decision['tool'] == 'multi_search':
            # 执行多个搜索
            observation, raw_data = await self._execute_multi_search(tool_decision['params']['searches'])
            if raw_data:
                tool_data['multi_search_results'] = raw_data
                
        elif tool_decision['tool'] == 'direct_answer':
            # 不需要工具，直接让 LLM 回答（简单问候等）
            pass
            
        elif tool_decision['tool'] == 'search_properties':
            # 执行房产搜索
            observation, raw_data = await self._execute_tool('search_properties', tool_decision['params'])
            
            # 处理 search_properties 的特殊返回情况
            if raw_data:
                if raw_data.get('status') == 'need_clarification':
                    return {
                        'success': True,
                        'response': raw_data.get('question', 'Could you please provide more details?'),
                        'response_type': 'question',
                        'turns': 1,
                        'extracted_context': raw_data.get('extracted_so_far', {}),
                        'tool_data': {}
                    }
                elif raw_data.get('status') == 'found' and raw_data.get('recommendations'):
                    recommendations = raw_data['recommendations']
                    filtered = self._apply_preference_filter(recommendations)
                    summary = raw_data.get('summary', f"Found {len(filtered)} properties.")
                    tool_data['recommendations'] = filtered
                    tool_data['search_criteria'] = raw_data.get('search_criteria', {})
                    return {
                        'success': True,
                        'response': f"Great news! {summary}\n\nCheck out the listings on the right panel. 👉",
                        'response_type': 'answer',
                        'turns': 1,
                        'extracted_context': self.extracted_context,
                        'tool_data': tool_data
                    }
                    
            # 🆕 检查 search_properties 是否失败，如果失败则降级到 web_search
            if raw_data and raw_data.get('success') == False:
                error_msg = raw_data.get('error', 'Unknown error')
                if self.verbose:
                    print(f"\n⚠️ [Fallback] search_properties 失败: {error_msg}")
                    print(f"   🔄 自动降级到 web_search...")
                
                # 构建降级搜索查询
                params = tool_decision.get('params', {})
                location = params.get('location', 'London')
                max_budget = params.get('max_budget', '')
                
                fallback_query = f"student accommodation rent {location} UK 2025"
                if max_budget:
                    fallback_query += f" under £{max_budget}"
                
                # 执行 web_search 作为降级
                fallback_observation, fallback_raw_data = await self._execute_tool(
                    'web_search', 
                    {'query': fallback_query}
                )
                
                if fallback_observation and 'No search results' not in fallback_observation:
                    observation = f"[Note: Property database search failed. Using web search results instead.]\n\n{fallback_observation}"
                    raw_data = fallback_raw_data
                    if self.verbose:
                        print(f"   ✅ web_search 降级成功")
                else:
                    if self.verbose:
                        print(f"   ❌ web_search 降级也失败了")
                        
        else:
            # 执行其他单个工具
            observation, raw_data = await self._execute_tool(tool_decision['tool'], tool_decision['params'])
            
            # 处理特定工具的直接返回
            if tool_decision['tool'] == 'check_safety' and raw_data and raw_data.get('safety_score') is not None:
                return self._format_safety_response(raw_data)
            
            if tool_decision['tool'] == 'search_nearby_pois' and raw_data and raw_data.get('pois'):
                return self._format_poi_response(raw_data)
        
        if self.verbose and observation:
            print(f"\n📊 [Step 2 Result] 工具执行完成，获取到的数据:")
            print(f"{'-'*60}")
            # 打印完整的 observation
            print(observation)
            print(f"{'-'*60}")
        
        # ============ 步骤3: 让 LLM 基于真实数据生成回答 ============
        if self.verbose:
            print(f"\n💬 [Step 3] 基于真实数据生成回答...")
        
        if observation:
            # 构建包含真实数据的 prompt - 强调只使用真实数据，避免幻觉
            data_prompt = f"""You are a helpful assistant for UK student housing.

{context_info}

User Question: {user_query}

I have already gathered the following REAL DATA for you:

{observation}

=== 🚨 STRICT GROUNDING RULES - ZERO TOLERANCE FOR FABRICATION 🚨 ===

🔴 CRITICAL RULE: 你只能使用搜索结果中**字面出现**的信息！

如果搜索结果中没有提到 "Ealing"，你就不能提 Ealing。
如果搜索结果中没有提到 "£600"，你就不能写 £600。
如果搜索结果中没有提到 "agency fees are illegal"，你就不能说中介费违法。

⚠️ 你的内部训练数据可能是过时的、错误的！只信任当前搜索结果！

=== ❌ FORBIDDEN BEHAVIORS (每个都是严重错误) ===

1. 【编造地名】
   搜索结果只提到 "London average" → 你不能提 "Bloomsbury", "Ealing", "King's Cross"
   ❌ "Areas like Ealing offer good value" ← Ealing 没出现在搜索结果中！
   ✅ "搜索结果未显示具体区域推荐"

2. 【编造价格】
   搜索结果只说 "rent varies" → 你不能写具体数字
   ❌ "Rooms typically cost £600-800/month" ← 这个数字没有来源！
   ✅ "搜索结果未显示具体价格，请访问 rightmove.co.uk"

3. 【编造法律/政策】
   除非搜索结果**明确说**，否则你不能声称：
   ❌ "Agency fees are illegal in England" ← 必须有搜索结果支持！
   ❌ "Students are exempt from Council Tax" ← 必须有搜索结果支持！
   ✅ "关于中介费政策，建议查阅 gov.uk 官方信息"

4. 【地域混淆】
   "UK average £562" ≠ 伦敦（伦敦是全国3-4倍！）
   ❌ 把 UK 平均数据当作伦敦数据
   ✅ 明确说明 "这是全国平均，伦敦会更高"

5. 【年份错误】
   2024年数据 ≠ 2025年现状
   2026年政策 ≠ 2025年现行政策
   ✅ 标注数据年份，提醒用户核实

=== ✅ CORRECT BEHAVIOR ===

对于每个你要写的信息，先问自己：
"这个信息在上面的搜索结果的哪一行？"

如果找不到 → 不要写！
如果能找到 → 引用来源！

正确格式：
✅ "根据搜索结果，Rightmove 数据显示伦敦平均租金 £2,736/月"
✅ "搜索结果未包含 [XX] 的信息，建议访问 [官方网站]"
✅ "⚠️ 关于中介费政策：搜索结果未涉及，请查阅 gov.uk"

=== 🔍 SELF-CHECK BEFORE EACH CLAIM ===

在写每一个声明之前，回答这个问题：

"我即将写的这个信息（地名/价格/政策）是否在搜索结果中逐字出现？"

- YES → 写出来，并引用来源
- NO → 不写，或说"搜索结果未涉及"

=== 🚫 EXAMPLES OF FABRICATION (DO NOT DO THIS) ===

假设搜索结果只说："London rent is expensive, average £2,736/month according to Rightmove"

❌ WRONG: "Areas like Ealing, Wembley offer rooms around £600-800"
   → "Ealing" 没出现！"Wembley" 没出现！"£600-800" 没出现！

✅ CORRECT: "根据 Rightmove，伦敦平均租金 £2,736/月。搜索结果未显示具体区域的价格，建议在 Rightmove 按区域搜索。"

=== ✅ REQUIRED RESPONSE FORMAT ===

对于有具体数字的数据（必须引用来源）：
"根据 [来源名] [Sub-search X, Result Y]，伦敦平均租金为 £2,736/月。"

对于只有链接没有具体数字的数据：
"⚠️ 关于[XX]：搜索结果未显示具体金额。
请访问官方网站获取最新数据：
- 🔗 [官方链接]"

对于具体地点（如 Bloomsbury, King's Cross）的价格：
"⚠️ 搜索结果未包含[地点]的具体租金。
建议直接在 Rightmove/Zoopla 搜索该区域获取当前报价。"

=== 🎓 国际学生提醒（如果相关）===
如果搜索结果包含以下信息，务必提醒用户：
- Council Tax 学生免税政策
- 担保人（Guarantor）要求
- 租房诈骗警示
- 押金保护计划

=== 官方数据源（当搜索结果无具体数据时推荐）===

- TfL 交通费: tfl.gov.uk/fares（Zone 1-2 学生月票约 £114）
- 伦敦租金: rightmove.co.uk, zoopla.co.uk
- 生活费指南: 各大学官网 Cost of Living 页面
- 官方统计: ons.gov.uk

=== SELF-VERIFICATION CHECKLIST ===
回答前，对每个数字检查：
□ 这个数字是否**直接**出现在搜索结果的 Summary 中？
□ 如果我提到一个具体地点的价格，这个价格是否来自搜索结果？
□ 如果只有链接没有数字，我是否正确地说"请访问官网"？
□ 我有没有不小心用训练记忆"补充"了数字？
□ 搜索结果中的年份是 2025 吗？如果是未来年份，我是否标注了？

=== 🌐 LANGUAGE RULE (CRITICAL) ===
- If user asks in ENGLISH → Reply in ENGLISH
- If user asks in CHINESE → Reply in CHINESE
- 用户用什么语言问，就用什么语言答！

现在请严格按照以上规则回答：
- MATCH THE USER'S LANGUAGE (English question = English answer)
- 只使用搜索结果中**明确显示**的数字
- 对于没有具体数据的项目，提供官方链接
- 不要编造任何具体地点的价格！

Your response:"""
            
            final_response = self.llm.generate_react_response(data_prompt)
            
            if final_response:
                final_response = self._clean_response(final_response)
                
                if self.verbose:
                    print(f"   ✅ 生成回答成功 ({len(final_response)} 字符)")
                
                return {
                    'success': True,
                    'response': final_response,
                    'response_type': 'answer',
                    'turns': 1,
                    'extracted_context': self.extracted_context,
                    'tool_data': tool_data
                }
        else:
            # 没有工具数据（direct_answer 情况），直接让 LLM 回答
            simple_prompt = f"""You are a helpful assistant for UK student housing.

{context_info}

User Question: {user_query}

Provide a helpful response. Answer in the user's language.

Your response:"""
            
            final_response = self.llm.generate_react_response(simple_prompt)
            
            if final_response:
                final_response = self._clean_response(final_response)
                return {
                    'success': True,
                    'response': final_response,
                    'response_type': 'answer',
                    'turns': 1,
                    'extracted_context': self.extracted_context,
                    'tool_data': tool_data
                }
        
        # 回退
        return {
            'success': False,
            'response': "I'm sorry, I couldn't process your request. Please try again.",
            'response_type': 'error',
            'turns': 1,
            'extracted_context': self.extracted_context,
            'tool_data': tool_data
        }
    
    def _decide_tool(self, user_query: str) -> dict:
        """
        使用 LLM 多数投票决定使用什么工具
        
        核心原则：
        1. 不使用关键词匹配 - 完全由 LLM 理解语义意图
        2. 使用多数投票（5次）减少幻觉
        3. 不确定时默认使用 web_search（更安全）
        
        Returns:
            dict: {'tool': str, 'params': dict, 'reason': str}
        """
        query_lower = user_query.lower()
        
        # 简单问候 -> 直接回答（这个规则保留，因为很明确）
        greetings = ['hi', 'hello', '你好', '您好', 'hey', 'thanks', '谢谢']
        if any(g == query_lower.strip() for g in greetings) or (len(user_query) < 10 and any(g in query_lower for g in greetings)):
            return {
                'tool': 'direct_answer',
                'params': {},
                'reason': "简单问候，直接回答"
            }
        
        # 使用 LLM 多数投票决定工具
        return self._majority_vote_tool_decision(user_query, num_votes=5)
    
    def _majority_vote_tool_decision(self, user_query: str, num_votes: int = 5) -> dict:
        """
        LLM 多数投票选择工具（改进版）
        
        使用更高的 temperature 增加投票多样性，避免全票一致。
        同时改进 prompt 让 LLM 更准确地识别行动请求。
        
        Args:
            user_query: 用户查询
            num_votes: 投票次数（默认5次）
            
        Returns:
            dict: {'tool': str, 'params': dict, 'reason': str}
        """
        from collections import Counter
        
        # 🆕 改进的 prompt：更平衡，更关注用户的实际意图
        classification_prompt = f'''You are a tool router. Classify this query into ONE tool.

USER QUERY: "{user_query}"

TOOLS:
1. search_properties - User wants you to FIND/SHOW/GET properties from the database
   ✓ "find me...", "show me...", "get me...", "search for..."
   ✓ "can you find...", "based on X, find properties"
   ✓ "帮我找", "给我推荐", "搜索房源"
   ✓ User already provided context and NOW wants action
   
2. web_search - User wants INFORMATION or has QUESTIONS
   ✓ "what is...", "how much...", "which areas...", "is it possible..."
   ✓ General information about rent, areas, costs
   ✓ "介绍", "怎么样", "多少钱"

3. check_safety - Safety/crime questions about specific location
4. get_weather - Weather questions

IMPORTANT: If user says "find", "show", "get", "search", "recommend properties" → search_properties
If user asks a question without requesting action → web_search

Output ONLY the tool name:
Tool: '''

        votes = []
        
        if self.verbose:
            print(f"\n🗳️ [Voting] 开始 {num_votes} 次投票选择工具（高温度模式）...")
        
        for i in range(num_votes):
            try:
                # 🆕 使用高温度的分类函数，增加投票多样性
                response = self.llm.generate_classification_response(classification_prompt)
                if response:
                    tool = response.strip().lower().split()[0]  # Take first word
                    tool = tool.replace(':', '').replace(',', '').replace('.', '')
                    
                    # Normalize tool names
                    if 'search_prop' in tool or 'properties' in tool:
                        tool = 'search_properties'
                    elif 'web' in tool or tool == 'search':
                        tool = 'web_search'
                    elif 'safety' in tool or 'check' in tool:
                        tool = 'check_safety'
                    elif 'weather' in tool:
                        tool = 'get_weather'
                    else:
                        tool = 'web_search'  # Default fallback for unknown
                    
                    votes.append(tool)
                    
                    if self.verbose:
                        print(f"   Vote {i+1}: {tool}")
            except Exception as e:
                if self.verbose:
                    print(f"   Vote {i+1}: ERROR - {e}")
                continue
        
        if not votes:
            if self.verbose:
                print(f"   ⚠️ 没有有效投票，使用默认 web_search")
            return self._llm_plan_searches(user_query)  # Fallback
        
        # Count votes
        counter = Counter(votes)
        winner, count = counter.most_common(1)[0]
        
        if self.verbose:
            print(f"   📊 投票结果: {dict(counter)}")
            print(f"   🏆 胜出: {winner} ({count}/{len(votes)} 票)")
        
        # 🆕 如果投票结果平局或接近平局，检查用户查询中的动作词
        if len(counter) > 1:
            # 检查是否有明确的动作请求词
            action_indicators = ['find', 'show', 'get', 'search', '找', '搜索', '推荐', 'recommend', 'based on']
            query_lower = user_query.lower()
            has_action_word = any(word in query_lower for word in action_indicators)
            
            if has_action_word and 'search_properties' in counter:
                # 用户明确请求行动，且有投票支持 search_properties
                if self.verbose:
                    print(f"   🔍 检测到行动词，倾向使用 search_properties")
                winner = 'search_properties'
                count = counter.get('search_properties', 0)
        
        # Build appropriate params based on winner
        if winner == 'search_properties':
            return {
                'tool': 'search_properties', 
                'params': {'user_query': user_query}, 
                'reason': f"LLM投票决定: search_properties ({count}/{len(votes)}票)"
            }
        elif winner == 'web_search':
            # Use existing multi-search planning for web queries
            return self._llm_plan_searches(user_query)
        elif winner == 'check_safety':
            # Extract location from query if possible
            return {
                'tool': 'check_safety', 
                'params': {'address': 'London', 'area': 'London'}, 
                'reason': f"LLM投票决定: check_safety ({count}/{len(votes)}票)"
            }
        elif winner == 'get_weather':
            location = 'London'
            query_lower = user_query.lower()
            if 'manchester' in query_lower or '曼彻斯特' in user_query:
                location = 'Manchester'
            elif 'birmingham' in query_lower or '伯明翰' in user_query:
                location = 'Birmingham'
            return {
                'tool': 'get_weather', 
                'params': {'location': location}, 
                'reason': f"LLM投票决定: get_weather ({count}/{len(votes)}票)"
            }
        else:
            # Default to web search planning
            return self._llm_plan_searches(user_query)
    
    def _llm_plan_searches(self, user_query: str) -> dict:
        """
        让 LLM 自主规划搜索策略
        
        LLM 会分析问题，决定需要几个搜索（1-10个），并生成精准的搜索词
        强调使用 2025 年数据和官方来源
        所有搜索必须使用英文
        包含国际学生隐形成本搜索
        
        Returns:
            dict: {'tool': 'multi_search', 'params': {'searches': [...]}, 'reason': str}
        """
        if self.verbose:
            print(f"\n🧠 [LLM Planning] 让 LLM 自主规划搜索策略...")
        
        planning_prompt = f"""You are a search query planner for UK student housing assistance.

USER QUESTION: {user_query}

Your task: Plan the optimal search strategy to answer this question with ACCURATE, LONDON-SPECIFIC data.

🚨 CRITICAL - AVOID UK-WIDE AVERAGES:
- UK average data is MISLEADING for London (London is 50-100% more expensive!)
- ALWAYS include "London" in search queries to get London-specific data
- Example: "London rent" not "UK student rent"

🎓 INTERNATIONAL STUDENT HIDDEN COSTS (IMPORTANT):
When user asks about rent/costs, ALWAYS consider these hidden costs that affect international students:
1. Council Tax Exemption - students are exempt but need to apply
2. Guarantor Requirements - international students often need UK guarantor or pay 6-12 months upfront
3. Rental Scams - common targeting international students
4. Deposit Protection Schemes - legal requirements
5. Agency Fees - some charge extra for non-UK students

REQUIREMENTS:
1. ALL search queries MUST be in ENGLISH - translate Chinese queries to English
2. ALL searches MUST include "London" + "2025" - we need CURRENT LONDON data
3. PRIORITIZE OFFICIAL SOURCES:
   - Rent: "London Rightmove" or "London Zoopla" 
   - Transport: "TfL" or "tfl.gov.uk"
   - Living costs: "London cost of living" (NOT "UK cost of living")
4. For cost-related questions, ADD a search for international student hidden costs
5. AVOID: blog posts, UK-wide averages, outdated data

RULES:
1. Decide how many searches are needed (minimum 1, maximum 10)
2. Each query MUST include "London" + "2025"
3. Each query should target authoritative sources
4. For transport: search for SPECIFIC zones (Zone 1-2 vs Zone 1-6)
5. For rent/cost questions: INCLUDE hidden costs search for international students

OUTPUT FORMAT - STRICT JSON only:
{{"searches": [{{"tool": "web_search", "params": {{"query": "London specific query 2025"}}}}], "reason": "brief reason"}}

EXAMPLES:
User: "伦敦租房多少钱" -> {{"searches": [{{"tool": "web_search", "params": {{"query": "London average rent price 2025 Rightmove"}}}}, {{"tool": "web_search", "params": {{"query": "London international student rent guarantor requirements 2025"}}}}, {{"tool": "web_search", "params": {{"query": "London rental scams international students avoid 2025"}}}}], "reason": "London rent + hidden costs"}}
User: "通勤费用" -> {{"searches": [{{"tool": "web_search", "params": {{"query": "London TfL Zone 1-2 monthly travelcard 2025 official"}}}}], "reason": "London transport"}}
User: "生活费用" -> {{"searches": [{{"tool": "web_search", "params": {{"query": "London student cost of living 2025"}}}}, {{"tool": "web_search", "params": {{"query": "London Council Tax student exemption 2025"}}}}, {{"tool": "web_search", "params": {{"query": "London international student deposit scheme 2025"}}}}], "reason": "London living costs + hidden costs"}}

Now output JSON for: "{user_query}"
JSON:"""

        try:
            response = self.llm.generate_react_response(planning_prompt)
            
            if response:
                # 清理响应中的控制字符和非法字符
                cleaned_response = response
                # 移除控制字符（除了换行和制表符）
                cleaned_response = ''.join(char for char in cleaned_response if ord(char) >= 32 or char in '\n\t')
                # 尝试提取 JSON
                json_match = re.search(r'\{[\s\S]*\}', cleaned_response)
                if json_match:
                    json_str = json_match.group()
                    # 进一步清理 JSON 字符串
                    json_str = json_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                    
                    plan = json.loads(json_str)
                    searches = plan.get('searches', [])
                    reason = plan.get('reason', 'LLM planned searches')
                    
                    # 确保每个搜索都包含 2025 并且是英文
                    valid_searches = []
                    for search in searches:
                        if search.get('tool') == 'web_search':
                            query = search.get('params', {}).get('query', '')
                            # 跳过包含大量中文的查询
                            chinese_chars = sum(1 for char in query if '\u4e00' <= char <= '\u9fff')
                            if chinese_chars > 3:
                                continue  # 跳过中文查询
                            if '2025' not in query and '2024' not in query:
                                query = query + ' 2025'
                            search['params']['query'] = query
                            valid_searches.append(search)
                        else:
                            valid_searches.append(search)
                    
                    searches = valid_searches
                    
                    # 限制最多10个搜索
                    if len(searches) > 10:
                        searches = searches[:10]
                    
                    if self.verbose:
                        print(f"   📋 LLM 规划了 {len(searches)} 个搜索:")
                        for i, s in enumerate(searches):
                            print(f"      {i+1}. {s.get('tool')}: {s.get('params', {}).get('query', s.get('params'))}")
                    
                    if searches:
                        return {
                            'tool': 'multi_search',
                            'params': {'searches': searches},
                            'reason': f"LLM规划: {reason}"
                        }
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️ LLM 规划失败: {e}")
        
        # 回退：根据用户问题生成英文搜索查询
        if self.verbose:
            print(f"   ⚠️ 使用默认搜索策略 - 自动翻译为英文")
        
        # 分析用户问题，生成合适的英文搜索词
        fallback_searches = self._generate_fallback_english_searches(user_query)
        
        return {
            'tool': 'multi_search',
            'params': {'searches': fallback_searches},
            'reason': "默认英文搜索"
        }
    
    def _generate_fallback_english_searches(self, user_query: str) -> list:
        """
        根据用户问题生成英文搜索查询（回退策略）
        
        检测关键词并生成对应的英文搜索
        """
        searches = []
        query_lower = user_query.lower()
        
        # 检测租房相关
        if any(kw in user_query for kw in ['租房', '租金', 'rent', '房价', '房租']):
            searches.append({
                "tool": "web_search",
                "params": {"query": "London average rent price 2025 Zoopla Rightmove official"}
            })
        
        # 检测生活费用相关
        if any(kw in user_query for kw in ['生活', '开销', '费用', 'cost', 'living', '花费']):
            searches.append({
                "tool": "web_search", 
                "params": {"query": "London student cost of living 2025 official statistics"}
            })
        
        # 检测吃饭/食品相关
        if any(kw in user_query for kw in ['吃饭', '食物', '饮食', 'food', 'grocery', '餐饮']):
            searches.append({
                "tool": "web_search",
                "params": {"query": "London student weekly food budget 2025 supermarket"}
            })
        
        # 检测交通/通勤相关
        if any(kw in user_query for kw in ['通勤', '交通', 'transport', 'commute', '地铁', 'tube']):
            searches.append({
                "tool": "web_search",
                "params": {"query": "London TfL monthly travelcard price Zone 1-2 2025 official"}
            })
        
        # 检测安全相关
        if any(kw in user_query for kw in ['安全', 'safe', 'safety', '犯罪', 'crime']):
            searches.append({
                "tool": "web_search",
                "params": {"query": "London safe areas for students 2025 crime statistics"}
            })
        
        # 如果没有匹配任何关键词，使用通用搜索
        if not searches:
            searches.append({
                "tool": "web_search",
                "params": {"query": "London student accommodation guide 2025 official"}
            })
        
        if self.verbose:
            print(f"   📋 生成了 {len(searches)} 个英文回退搜索")
            for i, s in enumerate(searches):
                print(f"      {i+1}. {s['params']['query']}")
        
        return searches
    
    def _format_safety_response(self, raw_data: dict) -> dict:
        """格式化安全检查响应"""
        address = raw_data.get('address', 'the area')
        score = raw_data.get('safety_score', 50)
        level = raw_data.get('safety_level', 'Moderate')
        details = raw_data.get('details', '')
        
        emoji = "✅" if score >= 70 else "⚠️" if score >= 50 else "🚨"
        
        response = f"""## {emoji} Safety Report for {address}

**Safety Score:** {score}/100
**Risk Level:** {level}

{details}

*Note: This is based on general area statistics. Always visit in person before making a decision.*"""
        
        return {
            'success': True,
            'response': response,
            'response_type': 'answer',
            'turns': 1,
            'extracted_context': self.extracted_context,
            'tool_data': {'safety_data': raw_data}
        }
    
    def _format_poi_response(self, raw_data: dict) -> dict:
        """格式化 POI 搜索响应"""
        pois = raw_data.get('pois') or raw_data.get('results', {})
        address = raw_data.get('address', 'the location')
        
        response_parts = [f"## 📍 Nearby Facilities - {address}\n"]
        
        for poi_type, poi_list in pois.items():
            if poi_list:
                response_parts.append(f"\n### {poi_type.replace('_', ' ').title()}")
                for poi in poi_list[:5]:
                    name = poi.get('name', 'Unknown')
                    distance = poi.get('distance', 'N/A')
                    response_parts.append(f"- **{name}** - {distance}m")
        
        return {
            'success': True,
            'response': '\n'.join(response_parts),
            'response_type': 'answer',
            'turns': 1,
            'extracted_context': self.extracted_context,
            'tool_data': {'poi_results': raw_data}
        }
    
    def _clean_response(self, response: str) -> str:
        """
        清理响应文本，移除任何意外泄露给用户的内部格式
        
        移除:
        - Thought: ... 行
        - Action: ... 行  
        - Action Input: 前缀
        - **Final Answer:** 等 markdown 格式
        - 其他调试信息
        
        增强:
        - 年份校验：检测 2025 vs 2026 数据，添加时效性警告
        """
        if not response:
            return response
        
        # 🆕 先清理 markdown 格式的标记
        response = re.sub(r'^\s*\*\*Final Answer:\*\*\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^\s*\*\*Final Answer:\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^\s*Final Answer:\s*', '', response, flags=re.IGNORECASE)
        
        lines = response.split('\n')
        cleaned_lines = []
        skip_next = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # 跳过这些模式
            if line_lower.startswith('thought:'):
                continue
            if line_lower.startswith('action:'):
                continue
            if line_lower.startswith('action input:'):
                # 可能后面跟着有用内容，但 Action Input: 本身要移除
                content_after = line.split(':', 1)
                if len(content_after) > 1 and content_after[1].strip():
                    cleaned_lines.append(content_after[1].strip())
                continue
            if line_lower.startswith('observation:'):
                continue
            # 🆕 跳过只有 ** 的行
            if line.strip() == '**' or line.strip() == '** ':
                continue
            
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()
        
        # 确保不返回空字符串
        if not result:
            return response
        
        # 🆕 年份校验：检测未来年份数据并添加警告
        result = self._validate_and_annotate_year(result)
        
        return result
    
    def _validate_and_annotate_year(self, response: str) -> str:
        """
        校验响应中的年份引用，对未来政策/数据添加警告标注
        
        检测模式:
        - 2025/26 学年、2026 年入学
        - 2026 NHS surcharge、2026 visa fees
        - 将未来年份数据标注为"预计政策"
        """
        import datetime
        current_year = datetime.datetime.now().year  # 2025
        
        # 检测未来年份的政策/费用引用
        future_year_patterns = [
            # 明确的未来年份 (2026+)
            (r'\b(202[6-9]|20[3-9]\d)\s*(年|学年|academic year)', r'⚠️ \1\2 (预计政策，可能变动)'),
            (r'\b(202[6-9]|20[3-9]\d)\s*(NHS|visa|Council Tax|rent)', r'⚠️ \1 \2 (预计费用，以官方公布为准)'),
            
            # 2025/26 学年格式 - 如果已经是 2025 年下半年，这可能是当前数据
            (r'\b(2025/26|2025-26)\s*(学年|academic year)', r'\1\2 (当前学年数据)'),
            
            # 检测 "from September 2026" 等
            (r'from\s+(September|October|January)\s+(202[6-9]|20[3-9]\d)', r'from \1 \2 ⚠️ (预计，以届时官方公告为准)'),
        ]
        
        result = response
        for pattern, replacement in future_year_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # 🆕 如果响应中包含价格数据但年份是未来的，添加免责声明
        has_future_year = bool(re.search(r'\b(202[6-9]|20[3-9]\d)\b', result))
        has_price_data = bool(re.search(r'£\s*[\d,]+', result))
        
        if has_future_year and has_price_data:
            # 检查是否已经有免责声明
            if '⚠️' not in result[:100]:  # 开头没有警告
                disclaimer = "\n\n⚠️ **注意**: 响应中包含未来年份的预测数据，实际价格/政策可能有所变动，请以官方最新公告为准。"
                # 如果响应很长，在开头也加一个简短提示
                if len(result) > 500:
                    result = "📅 **数据时效提示**: 部分信息为预计值\n\n" + result
                result += disclaimer
        
        return result
    
    def _apply_preference_filter(self, recommendations: list) -> list:
        """
        根据用户偏好过滤搜索结果
        
        - 移除在排除区域的房产
        - 可以根据 required_amenities 调整排序
        """
        if not recommendations:
            return recommendations
        
        excluded_areas = [area.lower() for area in self.user_preferences.get('excluded_areas', [])]
        
        if not excluded_areas:
            return recommendations
        
        filtered = []
        for prop in recommendations:
            address = prop.get('address', '').lower()
            area = prop.get('area', '').lower()
            
            # 检查是否在排除区域
            is_excluded = False
            for excluded in excluded_areas:
                if excluded in address or excluded in area:
                    is_excluded = True
                    if self.verbose:
                        print(f"🚫 [Filter] Excluding {prop.get('address')} - in excluded area: {excluded}")
                    break
            
            if not is_excluded:
                filtered.append(prop)
        
        return filtered
    
    def reset(self):
        """重置 Agent 状态（保留用户偏好和累积的搜索条件）"""
        self.extracted_context = {}
        # 注意：不清除 user_preferences 和 accumulated_search_criteria
        # 因为它们需要在整个会话期间保持
    
    def reset_all(self):
        """完全重置 Agent（包括用户偏好和搜索条件）- 用于新会话"""
        self.extracted_context = {}
        self.user_preferences = {
            'hard_preferences': [],
            'soft_preferences': [],
            'excluded_areas': [],
            'required_amenities': [],
            'safety_concerns': [],
        }
        self.accumulated_search_criteria = {
            'destination': None,
            'max_budget': None,
            'max_travel_time': None,
            'property_features': [],
            'soft_preferences': [],
            'amenities_of_interest': [],
        }
        if self.verbose:
            print("🔄 [ReAct] Agent fully reset (including preferences and search criteria)")
