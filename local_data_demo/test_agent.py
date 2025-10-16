#!/usr/bin/env python3
"""
测试 Agent 系统 - ReAct 循环演示
"""

import asyncio
import sys
from pathlib import Path

# 添加本地路径
sys.path.insert(0, str(Path(__file__).parent))

from core.tool_system import create_tool_registry
from core.agent import Agent
from core.llm_interface import call_ollama


async def test_agent():
    """测试 Agent 系统"""
    
    print("\n" + "="*70)
    print("🧪 Agent 系统测试")
    print("="*70)
    
    # 初始化工具注册表
    print("\n[1/3] 初始化工具系统...")
    try:
        tool_registry = create_tool_registry()
        print(f"✅ 工具系统初始化完成")
        print(f"   可用工具: {', '.join(tool_registry.list_tool_names())}")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 创建 Agent
    print("\n[2/3] 创建 Agent...")
    try:
        agent = Agent(
            tool_registry=tool_registry,
            llm_func=call_ollama,
            max_turns=5,
            verbose=True
        )
        print(f"✅ Agent 创建成功")
    except Exception as e:
        print(f"❌ Agent 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试查询
    print("\n[3/3] 运行 Agent...")
    test_queries = [
        "Find me a flat near UCL, budget £1500, with less than 30 min commute to King's College London",
        "我想在 Bloomsbury 找一个房子，预算 £1200，要求靠近地铁"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─'*70}")
        print(f"测试查询 {i}: {query}")
        print(f"{'─'*70}")
        
        try:
            result = await agent.run(query)
            
            print(f"\n{'='*70}")
            print(f"📊 执行结果")
            print(f"{'='*70}")
            
            if result['success']:
                print(f"✅ 成功")
                print(f"   最终答案: {result['final_answer'][:100]}...")
            else:
                print(f"❌ 失败: {result.get('error', 'Unknown error')}")
            
            print(f"\n📈 统计信息:")
            stats = agent.get_stats()
            print(f"   - 执行轮次: {stats['turns']}")
            print(f"   - 工具调用: {stats['observations_count']}")
            print(f"   - 成功: {stats['successful_tools']}")
            print(f"   - 失败: {stats['failed_tools']}")
            print(f"   - 总耗时: {stats['total_execution_time_ms']:.0f}ms")
            
        except KeyboardInterrupt:
            print("\n\n⏹️  用户中断")
            break
        except Exception as e:
            print(f"\n❌ 执行出错: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"✅ 测试完成")
    print(f"{'='*70}\n")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_agent())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  程序中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 致命错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
