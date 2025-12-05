# web_search.py
"""
Web Search Module - 使用 SearXNG 本地实例进行网络搜索
替代 DuckDuckGo，提供更稳定和可控的搜索能力
"""

import requests
from typing import List, Dict, Optional, Union
from .cache_service import get_from_cache, set_to_cache, create_cache_key


class SearXNGSearch:
    """
    SearXNG 搜索客户端类
    用于与本地或远程 SearXNG 实例进行交互
    """
    
    def __init__(
        self, 
        instance_url: str = "http://localhost:8080",
        timeout: int = 10,
        default_max_results: int = 10
    ):
        """
        初始化 SearXNG 搜索客户端
        
        Args:
            instance_url: SearXNG 实例的 URL
            timeout: 请求超时时间（秒）
            default_max_results: 默认返回的最大结果数
        """
        self.instance_url = instance_url.rstrip('/')
        self.search_endpoint = f"{self.instance_url}/search"
        self.timeout = timeout
        self.default_max_results = default_max_results
        # 🆕 指定可用的搜索引擎（brave, duckduckgo, startpage 经常被 CAPTCHA 封锁）
        self.engines = "google,bing,yahoo,wikipedia"
    
    def search(
        self, 
        query: str, 
        max_results: Optional[int] = None,
        categories: str = "general",
        language: str = "en-GB"
    ) -> List[Dict[str, str]]:
        """
        执行搜索并返回结构化结果
        
        Args:
            query: 搜索查询字符串
            max_results: 返回的最大结果数
            categories: 搜索类别 (general, images, news, etc.)
            language: 搜索语言
            
        Returns:
            List[Dict]: 包含 title, url, content 的字典列表
        """
        if max_results is None:
            max_results = self.default_max_results
            
        params = {
            "q": query,
            "format": "json",
            "categories": categories,
            "language": language,
            "engines": self.engines  # 🆕 明确指定引擎，避免使用被封锁的默认引擎
        }
        
        try:
            print(f"  -> [SearXNG] Searching: '{query}' (engines: {self.engines})")
            response = requests.get(
                self.search_endpoint,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            # 🆕 检查是否有不响应的引擎，记录日志
            unresponsive = data.get("unresponsive_engines", [])
            if unresponsive:
                print(f"  ⚠️ [SearXNG] Unresponsive engines: {unresponsive}")
            
            # 提取并格式化结果
            formatted_results = []
            for result in results[:max_results]:
                formatted_results.append({
                    "title": result.get("title", "No title"),
                    "url": result.get("url", ""),
                    "content": result.get("content", "No content available")
                })
            
            print(f"  ✅ Found {len(formatted_results)} results")
            return formatted_results
            
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Connection Error: Cannot connect to SearXNG at {self.instance_url}")
            print("     Make sure the SearXNG Docker container is running.")
            return []
        except requests.exceptions.Timeout:
            print(f"  ❌ Timeout: SearXNG request timed out after {self.timeout}s")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTP Error: {e}")
            return []
        except Exception as e:
            print(f"  ❌ SearXNG search failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def format_for_llm(self, results: List[Dict[str, str]]) -> str:
        """
        将搜索结果格式化为 LLM 友好的字符串
        
        Args:
            results: 搜索结果列表
            
        Returns:
            str: 格式化的字符串，适合 LLM 阅读
        """
        if not results:
            return "No search results found for this query."
        
        formatted_parts = []
        for i, result in enumerate(results, 1):
            formatted_part = (
                f"[{i}] Title: {result['title']}\n"
                f"    Link: {result['url']}\n"
                f"    Summary: {result['content']}"
            )
            formatted_parts.append(formatted_part)
        
        return "\n\n".join(formatted_parts)


# 全局搜索实例（使用本地 SearXNG）
_searxng_client = SearXNGSearch(
    instance_url="http://localhost:8080",
    timeout=10,
    default_max_results=10
)


def get_search_snippets(query: str, max_results: int = 5) -> str:
    """
    执行 SearXNG 搜索并返回格式化的摘要字符串。
    使用缓存。返回详细的结果，包括标题、链接和摘要。
    
    Args:
        query: 搜索查询字符串
        max_results: 返回的最大结果数
        
    Returns:
        str: 格式化的搜索结果字符串
    """
    cache_key = create_cache_key('get_search_snippets', query, max_results)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Web search for: '{query}'")
        return cached_result
    
    print(f"  -> [API Call] Web search for: '{query}'")
    
    # 使用 SearXNG 执行搜索
    results = _searxng_client.search(query, max_results=max_results)
    
    if not results:
        print(f"  ⚠️ SearXNG returned no results for: {query}")
        return "No search results found for this query."
    
    # 格式化为 LLM 友好的输出
    full_result = _searxng_client.format_for_llm(results)
    set_to_cache(cache_key, full_result)
    
    return full_result


def search_web(query: str, max_results: int = 10) -> Union[str, List[Dict[str, str]]]:
    """
    主要的网络搜索函数 - 作为 LLM 工具使用
    
    Args:
        query: 搜索查询字符串
        max_results: 返回的最大结果数 (5-10)
        
    Returns:
        str: 格式化的搜索结果，适合 LLM 阅读
        
    Example:
        >>> result = search_web("python docker tutorial")
        >>> print(result)
        [1] Title: Docker Python Tutorial
            Link: https://example.com/...
            Summary: Learn how to use Docker with Python...
    """
    return get_search_snippets(query, max_results=max_results)


def search_rent_prices(property_type: str, area: str = "London") -> str:
    """专门搜索租金价格信息，使用更精准的查询"""
    queries = [
        f"{property_type} rent price {area} UK 2024",
        f"average {property_type} rental cost {area}",
    ]
    all_results = []
    for q in queries:
        result = get_search_snippets(q, max_results=3)
        if result and "No search results" not in result:
            all_results.append(result)
    return "\n\n---\n\n".join(all_results) if all_results else "No rent price information found."


def search_crime_data(area: str) -> str:
    """使用更精确的查询搜索特定英国地区的犯罪数据。"""
    if not area:
        return "No area provided for crime search."
    return get_search_snippets(f'"{area} crime rate" official statistics')


def search_cost_of_living(area: str) -> str:
    """使用更精确的查询搜索生活成本信息。"""
    if not area:
        return "No area provided for cost of living search."
    return get_search_snippets(f'"cost of living in {area} London"')


# 便捷函数：检查 SearXNG 是否可用
def check_searxng_health() -> bool:
    """
    检查 SearXNG 实例是否正常运行
    
    Returns:
        bool: True 如果实例可用，否则 False
    """
    try:
        response = requests.get(
            f"{_searxng_client.instance_url}/healthz",
            timeout=5
        )
        return response.status_code == 200
    except:
        # 尝试基本连接
        try:
            response = requests.get(
                _searxng_client.instance_url,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False


if __name__ == "__main__":
    # 测试代码
    print("=== SearXNG Web Search Test ===\n")
    
    # 检查健康状态
    print("Checking SearXNG health...")
    if check_searxng_health():
        print("✅ SearXNG is running!\n")
    else:
        print("❌ SearXNG is not available. Make sure Docker container is running.\n")
        exit(1)
    
    # 测试搜索
    test_query = "London rent prices 2024"
    print(f"Testing search: '{test_query}'\n")
    result = search_web(test_query, max_results=5)
    print(result)