"""
Unified Agent - 统一的 Alex 代理系统
让 LLM 自主决定使用哪些工具来响应用户请求
"""

import asyncio
import json
import re
from typing import Callable, List, Optional, Dict, Any
from dataclasses import dataclass
from core.tool_system import ToolRegistry, ToolResult, Tool
from core.llm_interface import call_ollama, extract_first_json


@dataclass
class AgentResponse:
    """Agent 响应结构"""
    success: bool
    response_type: str  # 'search', 'chat', 'clarification', 'error'
    message: str
    data: Optional[Dict] = None
    tools_used: Optional[List[str]] = None


class UnifiedAgent:
    """
    统一的 Alex 代理 - 自主决定使用哪些工具
    
    核心能力：
    1. 意图识别 - 判断用户想做什么
    2. 工具选择 - LLM 自主决定需要哪些工具
    3. 工具执行 - 按序执行选定的工具
    4. 结果整合 - 将工具结果整合为自然语言回复
    """
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_tool_calls: int = 5,
        verbose: bool = True
    ):
        self.tool_registry = tool_registry
        self.max_tool_calls = max_tool_calls
        self.verbose = verbose
        self.conversation_history: List[Dict] = []
        self.current_property_context: Optional[Dict] = None
    
    def _log(self, message: str):
        """日志输出"""
        if self.verbose:
            print(message)
    
    def _get_tools_description(self) -> str:
        """生成所有可用工具的描述，供 LLM 参考"""
        tools_desc = []
        for name, tool in self.tool_registry.tools.items():
            params_desc = []
            for param_name, param_info in tool.parameters.get('properties', {}).items():
                required = param_name in tool.parameters.get('required', [])
                params_desc.append(
                    f"    - {param_name} ({param_info.get('type', 'any')})"
                    f"{' [必需]' if required else ''}: {param_info.get('description', '')}"
                )
            
            tools_desc.append(f"""
工具名称: {name}
描述: {tool.description[:200]}...
参数:
{chr(10).join(params_desc)}
""")
        
        return "\n".join(tools_desc)
    
    async def analyze_intent_and_select_tools(self, user_message: str, context: Optional[Dict] = None) -> Dict:
        """
        让 LLM 分析用户意图并选择需要的工具
        
        返回格式:
        {
            "intent": "search_property" | "ask_about_property" | "general_chat" | "clarification_needed",
            "tools_to_use": [
                {"tool": "search_properties", "params": {...}},
                {"tool": "check_safety", "params": {...}}
            ],
            "direct_response": "如果不需要工具，直接回复的内容",
            "reasoning": "选择这些工具的原因"
        }
        """
        self._log(f"\n{'='*60}")
        self._log(f"🧠 [意图分析] 分析用户请求...")
        self._log(f"{'='*60}")
        
        tools_description = self._get_tools_description()
        
        # 构建上下文信息
        context_info = ""
        if context and context.get('property'):
            prop = context['property']
            context_info = f"""
当前房源上下文:
- 地址: {prop.get('address', 'N/A')}
- 价格: {prop.get('price', 'N/A')}
- 通勤时间: {prop.get('travel_time', 'N/A')}
"""
        
        prompt = f"""你是 Alex，一个智能英国租房助手。分析用户的请求，决定需要使用哪些工具来回答。

用户消息: "{user_message}"
{context_info}

可用工具:
{tools_description}

你的任务:
1. 分析用户的意图
2. 决定是否需要使用工具
3. 如果需要工具，选择最合适的工具和参数

返回以下 JSON 格式（不要包含其他内容）:

{{
    "intent": "search_property" 或 "ask_about_property" 或 "general_chat" 或 "clarification_needed",
    "reasoning": "解释你的分析过程",
    "needs_tools": true 或 false,
    "tools_to_use": [
        {{
            "tool": "工具名称",
            "params": {{参数字典}},
            "purpose": "为什么要用这个工具"
        }}
    ],
    "direct_response": "如果不需要工具，这里填写直接回复的内容",
    "clarification_question": "如果需要澄清，这里填写问题"
}}

意图判断规则:
- search_property: 用户想搜索/找房子（包含预算、位置、通勤时间等）
- ask_about_property: 用户在询问特定房源的信息（附近设施、安全性等）
- general_chat: 一般性对话、问候、租房建议等
- clarification_needed: 用户请求不清楚，需要更多信息

工具选择规则:
1. 搜索房源时，必须使用 search_properties 工具
2. 如果用户提到"安全"、"犯罪"、"crime"、"safe"，添加 check_safety 工具
3. 如果用户询问天气，使用 get_weather 工具
4. 如果用户询问通勤时间，使用 calculate_commute 工具
5. 如果是一般对话，不需要工具

参数提取规则:
- 预算: 从消息中提取数字（如 "£1500" → 1500）
- 位置: 提取地点名称（如 "near UCL" → "UCL"）
- 通勤时间: 提取分钟数（如 "30分钟" → 30，如果没提到默认50）

只返回 JSON，不要有其他文字。
"""

        response = call_ollama(prompt, timeout=120)
        
        if not response:
            self._log("❌ LLM 响应超时")
            return {
                "intent": "error",
                "needs_tools": False,
                "direct_response": "抱歉，我现在有点忙，请稍后再试。"
            }
        
        parsed = extract_first_json(response)
        
        if parsed:
            self._log(f"✅ 意图识别成功: {parsed.get('intent')}")
            self._log(f"   需要工具: {parsed.get('needs_tools')}")
            if parsed.get('tools_to_use'):
                self._log(f"   选择的工具: {[t.get('tool') for t in parsed.get('tools_to_use', [])]}")
            return parsed
        else:
            self._log("⚠️ 无法解析 LLM 响应，使用默认处理")
            return {
                "intent": "general_chat",
                "needs_tools": False,
                "direct_response": "我理解你的问题，但我需要更多信息。你能具体描述一下你在找什么样的房子吗？"
            }
    
    async def execute_tools(self, tools_to_use: List[Dict]) -> List[Dict]:
        """
        执行选定的工具
        """
        results = []
        
        for i, tool_info in enumerate(tools_to_use[:self.max_tool_calls]):
            tool_name = tool_info.get('tool')
            params = tool_info.get('params', {})
            purpose = tool_info.get('purpose', '')
            
            self._log(f"\n🔧 [{i+1}/{len(tools_to_use)}] 执行工具: {tool_name}")
            self._log(f"   目的: {purpose}")
            self._log(f"   参数: {json.dumps(params, ensure_ascii=False)}")
            
            result = await self.tool_registry.execute_tool(tool_name, **params)
            
            results.append({
                'tool': tool_name,
                'params': params,
                'result': result.to_dict(),
                'success': result.success
            })
            
            if result.success:
                self._log(f"   ✅ 执行成功")
            else:
                self._log(f"   ❌ 执行失败: {result.error}")
        
        return results
    
    async def generate_response(
        self, 
        user_message: str, 
        intent_analysis: Dict, 
        tool_results: List[Dict]
    ) -> str:
        """
        根据工具执行结果生成自然语言回复
        """
        self._log(f"\n📝 生成回复...")
        
        # 如果不需要工具，直接返回
        if not intent_analysis.get('needs_tools'):
            return intent_analysis.get('direct_response', '我能帮你什么？')
        
        # 如果需要澄清
        if intent_analysis.get('intent') == 'clarification_needed':
            return intent_analysis.get('clarification_question', '请告诉我更多细节。')
        
        # 整理工具结果
        results_summary = []
        for tr in tool_results:
            if tr['success']:
                results_summary.append(f"工具 {tr['tool']} 执行成功:\n{json.dumps(tr['result'].get('data', {}), ensure_ascii=False, indent=2)[:500]}")
            else:
                results_summary.append(f"工具 {tr['tool']} 执行失败: {tr['result'].get('error')}")
        
        prompt = f"""你是 Alex，友好的英国租房助手。根据工具执行结果，用自然、友好的方式回答用户。

用户问题: "{user_message}"

工具执行结果:
{chr(10).join(results_summary)}

要求:
1. 用友好、自然的语气回答
2. 突出关键信息（价格、位置、通勤时间等）
3. 如果有多个结果，按重要性排序展示
4. 如果工具失败，友好地解释并提供替代方案
5. 使用中英文混合（根据用户语言）

直接给出回复，不要加"AI:"或"Alex:"前缀。
"""
        
        response = call_ollama(prompt, timeout=120)
        return response if response else "抱歉，我在处理你的请求时遇到了问题。请稍后再试。"
    
    async def process_message(
        self, 
        user_message: str, 
        context: Optional[Dict] = None
    ) -> AgentResponse:
        """
        处理用户消息的主入口
        """
        self._log(f"\n{'='*60}")
        self._log(f"🤖 [Alex] 收到消息: {user_message}")
        self._log(f"{'='*60}")
        
        try:
            # 1. 分析意图并选择工具
            intent_analysis = await self.analyze_intent_and_select_tools(user_message, context)
            
            # 2. 根据意图处理
            if intent_analysis.get('intent') == 'clarification_needed':
                return AgentResponse(
                    success=True,
                    response_type='clarification',
                    message=intent_analysis.get('clarification_question', '请告诉我更多细节。'),
                    data={'intent': 'clarification_needed'}
                )
            
            if not intent_analysis.get('needs_tools'):
                return AgentResponse(
                    success=True,
                    response_type='chat',
                    message=intent_analysis.get('direct_response', '我能帮你什么？'),
                    data={'intent': intent_analysis.get('intent')}
                )
            
            # 3. 执行工具
            tools_to_use = intent_analysis.get('tools_to_use', [])
            tool_results = await self.execute_tools(tools_to_use)
            
            # 4. 生成回复
            response_message = await self.generate_response(
                user_message, intent_analysis, tool_results
            )
            
            # 5. 确定响应类型
            response_type = 'search' if intent_analysis.get('intent') == 'search_property' else 'chat'
            
            return AgentResponse(
                success=True,
                response_type=response_type,
                message=response_message,
                data={
                    'intent': intent_analysis.get('intent'),
                    'tool_results': tool_results
                },
                tools_used=[t.get('tool') for t in tools_to_use]
            )
            
        except Exception as e:
            self._log(f"❌ 处理消息出错: {e}")
            import traceback
            traceback.print_exc()
            
            return AgentResponse(
                success=False,
                response_type='error',
                message=f"抱歉，处理你的请求时出错了: {str(e)}"
            )
    
    def set_property_context(self, property_data: Dict):
        """设置当前房源上下文"""
        self.current_property_context = property_data
    
    def clear_property_context(self):
        """清除房源上下文"""
        self.current_property_context = None


# ============================================================================
# 智能搜索处理器 - 专门处理房源搜索请求
# ============================================================================

class SmartSearchHandler:
    """
    智能搜索处理器
    处理完整的房源搜索流程，包括:
    1. 解析用户需求
    2. 决定需要的数据（是否需要安全数据、天气等）
    3. 搜索并增强结果
    4. 生成推荐
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
    
    async def analyze_search_requirements(self, user_query: str) -> Dict:
        """
        分析搜索需求，决定需要哪些增强数据
        """
        prompt = f"""分析这个租房搜索请求，提取搜索条件并决定需要哪些额外信息:

用户请求: "{user_query}"

返回以下 JSON（只返回 JSON，不要其他内容）:

{{
    "search_criteria": {{
        "destination": "目的地（如 UCL, King's Cross）",
        "max_budget": 数字（预算上限），
        "max_travel_time": 数字（最大通勤时间，分钟）,
        "soft_preferences": "其他偏好描述"
    }},
    "enhancements_needed": {{
        "safety_data": true/false（用户是否关心安全/犯罪率）,
        "weather_data": true/false（用户是否提到天气）,
        "amenities_data": true/false（用户是否关心周边设施）,
        "transport_data": true/false（用户是否关心交通）
    }},
    "is_complete": true/false（信息是否足够执行搜索）,
    "missing_info": "如果不完整，缺少什么信息"
}}

规则:
- 如果用户提到 "safe", "safety", "crime", "犯罪", "安全" → safety_data: true
- 如果没有明确预算，根据上下文推断或设为 2000
- 如果没有明确通勤时间，默认 50 分钟
"""
        
        response = call_ollama(prompt, timeout=60)
        parsed = extract_first_json(response)
        
        if parsed:
            return parsed
        else:
            # 默认值
            return {
                "search_criteria": {
                    "destination": "London",
                    "max_budget": 2000,
                    "max_travel_time": 50,
                    "soft_preferences": ""
                },
                "enhancements_needed": {
                    "safety_data": False,
                    "weather_data": False,
                    "amenities_data": False,
                    "transport_data": False
                },
                "is_complete": False,
                "missing_info": "无法解析搜索条件"
            }
    
    async def execute_search_with_enhancements(
        self, 
        criteria: Dict, 
        enhancements: Dict
    ) -> Dict:
        """
        执行搜索并根据需要添加增强数据
        """
        results = {
            'properties': [],
            'enhancements': {}
        }
        
        # 1. 执行主搜索
        search_result = await self.tool_registry.execute_tool(
            'search_properties',
            location=criteria.get('destination', 'London'),
            max_budget=criteria.get('max_budget', 2000),
            max_commute_time=criteria.get('max_travel_time', 50),
            care_about_safety=enhancements.get('safety_data', False)
        )
        
        if search_result.success:
            results['properties'] = search_result.data.get('perfect_match', [])
        
        # 2. 如果需要安全数据，为每个房源添加
        if enhancements.get('safety_data') and results['properties']:
            for prop in results['properties'][:5]:  # 只为前5个添加
                address = prop.get('address', '')
                if address:
                    safety_result = await self.tool_registry.execute_tool(
                        'check_safety',
                        address=address
                    )
                    if safety_result.success:
                        prop['safety_data'] = safety_result.data
        
        # 3. 如果需要天气数据
        if enhancements.get('weather_data'):
            weather_result = await self.tool_registry.execute_tool(
                'get_weather',
                location=criteria.get('destination', 'London')
            )
            if weather_result.success:
                results['enhancements']['weather'] = weather_result.data
        
        return results


def create_unified_agent() -> UnifiedAgent:
    """创建统一的 Agent 实例"""
    from core.tool_system import create_tool_registry
    
    registry = create_tool_registry()
    return UnifiedAgent(tool_registry=registry)
