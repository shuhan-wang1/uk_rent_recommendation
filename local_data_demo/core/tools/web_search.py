"""
Web Search Tool - 使用 DuckDuckGo 搜索获取信息
用于回答一般性问题（区域信息、生活成本、学校等）
"""

from core.tool_system import Tool, ToolResult
from core.web_search import get_search_snippets

async def web_search_func(query: str) -> ToolResult:
    """
    使用 DuckDuckGo 搜索引擎获取信息
    
    Args:
        query: 搜索查询语句
    
    Returns:
        ToolResult: 搜索结果摘要
    """
    try:
        print(f"[WEB_SEARCH] 搜索: {query}")
        
        # 执行搜索
        result = get_search_snippets(query, max_results=5)
        
        if not result or result == "Could not retrieve search information.":
            return ToolResult(
                success=False,
                error="No search results found",
                tool_name="web_search"
            )
        
        print(f"[WEB_SEARCH] 找到结果: {len(result)} 字符")
        
        return ToolResult(
            success=True,
            data={
                "query": query,
                "results": result
            },
            tool_name="web_search"
        )
        
    except Exception as e:
        print(f"[WEB_SEARCH] 错误: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            tool_name="web_search"
        )


# 工具定义
web_search_tool = Tool(
    name="web_search",
    description="Search the web for information using DuckDuckGo. Use this for general knowledge questions about UK areas, neighborhoods, universities, safety statistics, living costs, local amenities, etc. This is your go-to tool when you need factual information that isn't available from other specific tools.",
    func=web_search_func,
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific and include 'UK' or 'London' when relevant. Example: 'safe areas for students in London UK'"
            }
        },
        "required": ["query"]
    }
)
