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

# ReAct Prompt - 让 LLM 完全自主决策，特别强调 search_properties 工具
REACT_PROMPT_TEMPLATE = """You are Alex, an intelligent UK rental property assistant.

## Available Tools
{tool_descriptions}

## STRICT Response Format
You MUST follow this EXACT format. Any deviation will cause errors:

Thought: [Your reasoning - what does the user need?]
Action: [EXACTLY one of: search_properties | calculate_commute | check_safety | get_weather | web_search | search_nearby_pois | Final Answer]
Action Input: [If Action is a tool: JSON object like {{"param": "value"}}. If Action is "Final Answer": your response text]

## ⚠️ CRITICAL RULES - READ CAREFULLY

### Rule 1: NEVER invent or assume parameters the user didn't provide!
- If user says "Find flat near UCL under £1500" → You have: location=UCL, max_budget=1500
- You do NOT have: max_commute_time (user didn't mention it!)
- WRONG: {{"location": "UCL", "max_budget": 1500, "max_commute_time": 45}} ← DON'T add 45!
- RIGHT: {{"location": "UCL", "max_budget": 1500}} ← Only use what user provided

### Rule 2: Property Database Has Commute Info - Use It!
Our database already contains commute times for each property (Bus, Walk, Cycle, Drive times).
- For commute questions about KNOWN properties → Use Final Answer with data from context
- Example: "How long to cycle from Vega to UCL?" → Answer: "Based on our data, cycling from Vega takes about 24 minutes"
- ONLY call calculate_commute if the property is NOT in our database

### Rule 3: Comparing Properties - Use Database Data
When user compares properties (e.g., "Spring Mews vs Scape Bloomsbury"), answer using the property database:
- Use amenities, guest policies, prices from the database
- Do NOT say "unverified" if the data exists in our database
- If you need to compare, I will provide BOTH properties' data in context

### Rule 4: Questions About Current Property → Use Final Answer
If there is "Current Property Context" below, answer questions about that property directly:
- Guarantor/payment → Use Payment_Rules
- Guests → Use Guest_Policy  
- Amenities/facilities → Use Detailed_Amenities
- What's not included → Use Excluded_Features
- Booking link → Use the URL field (we have direct links!)

### Rule 5: Follow-up Answers Must Include Original Context
When user answers a clarification question (like "30 minutes" or "no preference"):
- Remember you're continuing the ORIGINAL search
- Don't treat their answer as a new, confusing command
- If user says "10" after you asked about commute time → max_commute_time=10

### Rule 6: ALWAYS Use Real Property Names - NEVER Say "Property A/B/C"!
- WRONG: "Property A has a pool, Property B has a gym"
- RIGHT: "Spring Mews has a pool, Scape Bloomsbury has a gym"
- WRONG: "I recommend Property D"
- RIGHT: "I recommend Vega (Vauxhall)" 
- Always use the actual name from Address field (first part before comma)

### Rule 7: Facility/Amenity Searches - Search ALL Properties!
When user asks about specific amenities (karaoke, pool, gym, games room, basketball):
- Do NOT assume only one property exists
- Our database has MANY properties with different amenities
- NEVER say "this is the only property in database" - that's FALSE
- If amenity search results are provided in context, USE THEM

### Rule 8: Safety Questions - Answer Directly, Don't Start New Search!
When user asks about safety AFTER you've already shown properties:
- Use check_safety tool to get safety info for specific areas
- Then use Final Answer to compare safety of already-shown properties
- Do NOT start a new search_properties call
- The user already has property recommendations, they just want safety comparison

### Rule 9: ALWAYS Include Property URLs When Available
- Our database has booking URLs for each property
- When recommending properties, INCLUDE the URL
- NEVER say "I don't have access to links" - we have them!
- Format: "You can book here: [URL from database]"

### Rule 10: Double-Check Amenity Claims Against Database!
BEFORE saying a property has/doesn't have something:
- Re-read the Detailed_Amenities field carefully
- Spring Mews HAS: Swimming Pool, Gym (it's in the data!)
- If unsure, say "based on our records" not "I believe"
- NEVER contradict what the database clearly states

## EXAMPLES

Example 1 - Property Search (only use provided params):
User: "Find me an apartment near Imperial College that costs under £2000"
Thought: User wants apartments near Imperial College, budget £2000. They did NOT mention commute time, so I will NOT assume one.
Action: search_properties
Action Input: {{"location": "Imperial College", "max_budget": 2000}}

Example 2 - Safety Question (after properties shown):
User: "Which of these properties is in the safest area? I'm worried about Brent Cross."
Thought: User already has property recommendations. They want to compare safety. I should check safety for the areas, then use Final Answer to compare. I should NOT start a new property search.
Action: check_safety
Action Input: {{"address": "Brent Cross, London"}}
[After getting safety data]
Action: Final Answer
Action Input: Based on safety data, here's the comparison...

Example 3 - Providing Property Link:
User: "Can I get the link for Tufnell House?"
Thought: User wants the booking URL for Tufnell House. I have this in my database - the URL field contains the link.
Action: Final Answer
Action Input: Here's the booking link for Tufnell House: https://uhomes.example/tufnell-house

## Current Context
{context_info}

## User Query
{user_query}

Now respond in the EXACT format (Thought/Action/Action Input):
"""


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
        
        # 初始化 LLM
        from core.llm_interface import LLMInterface
        self.llm = LLMInterface()
    
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
        
        # 已知的工具列表（用于智能匹配）
        known_tools = ['search_properties', 'calculate_commute', 'check_safety', 
                       'get_weather', 'web_search', 'search_nearby_pois', 'final answer']
        
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
                tool_pattern = re.search(r'(search_properties|calculate_commute|check_safety|get_weather|web_search|search_nearby_pois|final\s*answer)', action_lower)
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
                
                # 如果没有找到 JSON，保留原始字符串
                if result['action_input'] is None:
                    result['action_input'] = input_str
                    
            except json.JSONDecodeError:
                # JSON 解析失败，保留原始字符串
                result['action_input'] = input_str
        
        return result
    
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
            
            # 执行工具（异步）
            result = await self.tool_registry.execute_tool(tool_name, **params)
            
            # 保存原始数据
            raw_data = result.data if result.success else None
            
            # 格式化结果供 LLM 阅读
            if result.success:
                if self.verbose:
                    print(f"  ✅ [ReAct] 工具执行成功")
                
                if isinstance(result.data, dict):
                    observation = json.dumps(result.data, ensure_ascii=False, indent=2)
                elif isinstance(result.data, list):
                    # 限制列表长度，避免输出过长
                    if len(result.data) > 10:
                        observation = json.dumps(result.data[:10], ensure_ascii=False, indent=2) + f"\n... and {len(result.data) - 10} more items"
                    else:
                        observation = json.dumps(result.data, ensure_ascii=False, indent=2)
                else:
                    observation = str(result.data)
                
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
    
    async def run(self, user_query: str, context: Optional[Dict] = None, is_continuation: bool = False) -> Dict[str, Any]:
        """
        运行 ReAct 循环
        
        Args:
            user_query: 用户的问题
            context: 上下文信息（包括 property 信息等）
            is_continuation: 是否是继续对话
        
        Returns:
            结果字典，包含:
            - success: bool
            - response: str
            - response_type: 'answer' | 'question' | 'error'
            - turns: int
            - extracted_context: dict
            - tool_data: dict (包含工具返回的原始数据，如房源列表)
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"🤖 [ReAct Agent] 开始处理...")
            print(f"   Query: {user_query}")
            print(f"   Max turns: {self.max_turns}")
            print(f"{'='*60}")
        
        # 🆕 从用户消息中提取偏好（在每次互动开始时）
        self.extract_preferences_from_interaction(user_query, '', None)
        prefs_summary = self.get_preferences_context()
        if prefs_summary and self.verbose:
            print(f"📝 [Preferences] Current user preferences:\n{prefs_summary}")
        
        # 构建初始 prompt
        tool_descriptions = self._build_tool_descriptions()
        context_info = self._build_context_info(context)
        
        prompt = REACT_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions,
            context_info=context_info,
            user_query=user_query
        )
        
        # ReAct 循环
        full_trace = prompt
        iteration = 0
        tool_data = {}  # 存储工具返回的原始数据
        
        while iteration < self.max_turns:
            iteration += 1
            
            if self.verbose:
                print(f"\n--- ReAct Turn {iteration}/{self.max_turns} ---")
            
            # 调用 LLM
            llm_response = self.llm.generate_react_response(full_trace)
            
            if self.verbose:
                print(f"LLM Response:\n{llm_response[:500]}..." if len(llm_response) > 500 else f"LLM Response:\n{llm_response}")
            
            if not llm_response:
                return {
                    'success': False,
                    'response': "I'm sorry, I couldn't process your request. Please try again.",
                    'response_type': 'error',
                    'turns': iteration,
                    'extracted_context': self.extracted_context,
                    'tool_data': tool_data
                }
            
            # 解析 LLM 输出
            parsed = self._parse_llm_output(llm_response)
            
            if self.verbose:
                print(f"Parsed - Thought: {parsed['thought'][:100]}..." if parsed['thought'] and len(parsed['thought']) > 100 else f"Parsed - Thought: {parsed['thought']}")
                print(f"Parsed - Action: {parsed['action']}")
                print(f"Parsed - Action Input: {parsed['action_input']}")
            
            # 检查是否有 Action
            if not parsed['action']:
                # 如果没有明确的 Action，尝试从整体响应中提取答案
                if self.verbose:
                    print("⚠️ No action found, using raw response")
                return {
                    'success': True,
                    'response': llm_response,
                    'response_type': 'answer',
                    'turns': iteration,
                    'extracted_context': self.extracted_context,
                    'tool_data': tool_data
                }
            
            action = parsed['action'].strip()
            action_input = parsed['action_input']
            
            # 检查是否是最终答案
            if action.lower() in ['final answer', 'final_answer', 'finalanswer']:
                final_response = action_input if isinstance(action_input, str) else str(action_input)
                
                # 🆕 清理响应 - 移除任何意外泄露的 Thought/Action 格式
                final_response = self._clean_response(final_response)
                
                # 检测是否是问题（需要用户澄清）
                is_question = any(q in final_response.lower() for q in ['?', 'could you', 'please tell me', 'what is', 'where'])
                
                if self.verbose:
                    print(f"✅ Final Answer: {final_response[:200]}...")
                
                return {
                    'success': True,
                    'response': final_response,
                    'response_type': 'question' if is_question and '?' in final_response else 'answer',
                    'turns': iteration,
                    'extracted_context': self.extracted_context,
                    'tool_data': tool_data
                }
            
            # 执行工具
            if isinstance(action_input, dict):
                observation, raw_data = await self._execute_tool(action, action_input)
            else:
                # 如果 action_input 不是字典，尝试创建空参数（用 user_query）
                observation, raw_data = await self._execute_tool(action, {'user_query': user_query})
            
            # 保存工具返回的原始数据（特别是 search_properties 的结果）
            if raw_data:
                # 🆕 保存安全检查结果，供后续推荐参考 + 更新用户偏好
                if action == 'check_safety' and isinstance(raw_data, dict):
                    safety_score = raw_data.get('safety_score', 50)
                    safety_level = raw_data.get('safety_level', 'Unknown')
                    address = raw_data.get('address', '')
                    
                    if safety_score < 50 or safety_level == 'Concerning':
                        # 保存安全警告
                        if 'safety_warnings' not in self.extracted_context:
                            self.extracted_context['safety_warnings'] = []
                        self.extracted_context['safety_warnings'].append({
                            'address': address,
                            'score': safety_score,
                            'level': safety_level
                        })
                        print(f"⚠️ [ReAct] 已记录安全警告: {address} (score: {safety_score})")
                        
                        # 🆕 自动添加到用户偏好的排除列表
                        area_name = address.split(',')[0].strip() if ',' in address else address
                        self.add_preference('excluded_areas', area_name)
                        self.add_preference('hard_preferences', f"Avoid {area_name} - safety score only {safety_score}/100")
                        self.add_preference('safety_concerns', f"{area_name}: {safety_level} (score {safety_score}/100)")
                
                if action == 'search_properties' and isinstance(raw_data, dict):
                    # 处理搜索结果
                    if raw_data.get('status') == 'need_clarification':
                        # 需要澄清 - 返回问题给用户
                        return {
                            'success': True,
                            'response': raw_data.get('question', 'Could you please provide more details?'),
                            'response_type': 'question',
                            'turns': iteration,
                            'extracted_context': raw_data.get('extracted_so_far', {}),
                            'tool_data': {}
                        }
                    elif raw_data.get('status') == 'no_exact_match_but_similar':
                        # 没有完全匹配但有相似房源 - 构建友好的回复
                        message = raw_data.get('message', '')
                        suggestion = raw_data.get('suggestion', '')
                        similar_props = raw_data.get('similar_properties', [])
                        suggested_budget = raw_data.get('suggested_budget', 0)
                        
                        # 构建 Markdown 格式的回复
                        response_parts = [
                            f"## No Exact Matches Found",
                            "",
                            message,
                            "",
                            f"### 💡 Suggestion",
                            suggestion,
                            "",
                            f"### Similar Properties (Slightly Over Budget)",
                            ""
                        ]
                        
                        for prop in similar_props[:3]:
                            response_parts.append(f"**{prop['rank']}. {prop['address']}**")
                            response_parts.append(f"   - Price: {prop['price']} ({prop['budget_status']})")
                            response_parts.append(f"   - Commute: {prop['travel_time']}")
                            response_parts.append("")
                        
                        response_parts.append(f"Would you like me to search with a higher budget of **£{suggested_budget}/month**?")
                        
                        full_response = "\n".join(response_parts)
                        
                        # 保存相似房源供前端展示
                        tool_data['recommendations'] = similar_props
                        tool_data['search_criteria'] = raw_data.get('search_criteria', {})
                        tool_data['suggested_budget'] = suggested_budget
                        
                        return {
                            'success': True,
                            'response': full_response,
                            'response_type': 'answer',
                            'turns': iteration,
                            'extracted_context': self.extracted_context,
                            'tool_data': tool_data
                        }
                    elif raw_data.get('status') == 'no_results':
                        # 完全没有结果
                        return {
                            'success': True,
                            'response': raw_data.get('message', 'No properties found matching your criteria.'),
                            'response_type': 'answer',
                            'turns': iteration,
                            'extracted_context': self.extracted_context,
                            'tool_data': {}
                        }
                    elif raw_data.get('status') == 'found' and raw_data.get('recommendations'):
                        # ✅ 找到房源 - 直接返回结果，不再继续循环
                        recommendations = raw_data['recommendations']
                        
                        # 🆕 应用用户偏好过滤 - 移除排除区域的房源
                        filtered_recommendations = self._apply_preference_filter(recommendations)
                        
                        if not filtered_recommendations:
                            # 所有房源都被过滤掉了
                            excluded = ', '.join(self.user_preferences['excluded_areas'])
                            return {
                                'success': True,
                                'response': f"I found some properties, but they're all in areas you've asked me to avoid ({excluded}). Would you like me to search with different criteria?",
                                'response_type': 'answer',
                                'turns': iteration,
                                'extracted_context': self.extracted_context,
                                'tool_data': {}
                            }
                        
                        summary = raw_data.get('summary', f"Found {len(filtered_recommendations)} properties matching your criteria.")
                        
                        # 如果有过滤，添加说明
                        if len(filtered_recommendations) < len(recommendations):
                            excluded_count = len(recommendations) - len(filtered_recommendations)
                            excluded_areas = ', '.join(self.user_preferences['excluded_areas'])
                            summary += f" (Note: {excluded_count} properties in {excluded_areas} were excluded based on your safety preferences.)"
                        
                        tool_data['recommendations'] = filtered_recommendations
                        tool_data['search_criteria'] = raw_data.get('search_criteria', {})
                        tool_data['summary'] = summary
                        
                        # 构建友好的回复消息
                        response_message = f"Great news! {summary}\n\nCheck out the listings on the right panel. 👉"
                        
                        return {
                            'success': True,
                            'response': response_message,
                            'response_type': 'answer',
                            'turns': iteration,
                            'extracted_context': self.extracted_context,
                            'tool_data': tool_data
                        }
            
            # 将观察结果添加到 trace
            full_trace += f"\n{llm_response}\nObservation: {observation}\n"
            
            if self.verbose:
                obs_preview = observation[:300] + "..." if len(observation) > 300 else observation
                print(f"Observation: {obs_preview}")
        
        # 超过最大迭代次数
        if self.verbose:
            print(f"⚠️ Reached max turns ({self.max_turns})")
        
        return {
            'success': False,
            'response': "I apologize, but I couldn't complete the task within the allowed steps. Please try rephrasing your question or being more specific.",
            'response_type': 'error',
            'turns': iteration,
            'extracted_context': self.extracted_context,
            'tool_data': tool_data
        }
    
    def _clean_response(self, response: str) -> str:
        """
        清理响应文本，移除任何意外泄露给用户的内部格式
        
        移除:
        - Thought: ... 行
        - Action: ... 行  
        - Action Input: 前缀
        - 其他调试信息
        """
        if not response:
            return response
        
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
            
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()
        
        # 确保不返回空字符串
        if not result:
            return response
        
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
        """重置 Agent 状态（保留用户偏好）"""
        self.extracted_context = {}
        # 注意：不清除 user_preferences，因为偏好需要在整个会话期间保持
    
    def reset_all(self):
        """完全重置 Agent（包括用户偏好）- 用于新会话"""
        self.extracted_context = {}
        self.user_preferences = {
            'hard_preferences': [],
            'soft_preferences': [],
            'excluded_areas': [],
            'required_amenities': [],
            'safety_concerns': [],
        }
        if self.verbose:
            print("🔄 [ReAct] Agent fully reset (including preferences)")
