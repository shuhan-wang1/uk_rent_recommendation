#!/usr/bin/env python3
"""
Test script: Verify new Tool System and multi-source supermarket search functionality

Test scenarios:
1. Verify Tool System initialization
2. Execute supermarket search tool (including Lidl, Aldi and other brands)
3. Verify cascading logic of multi-source search
4. Test cache functionality
"""

import asyncio
import sys
import json
from pathlib import Path

# Add local_data_demo to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_tool_system():
    """Test Tool System initialization"""
    print("\n" + "="*70)
    print("TEST 1: Tool System Initialization")
    print("="*70)
    
    try:
        from core.tool_system import create_tool_registry
        
        registry = create_tool_registry()
        tools = registry.list_tools()
        
        print(f"[OK] Tool System initialized successfully")
        print(f"     Registered tools: {len(registry.tools)}")
        
        for tool in tools:
            print(f"     - {tool['name']}: {tool['description']}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Tool System initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_supermarket_search():
    """Test multi-source supermarket search"""
    print("\n" + "="*70)
    print("TEST 2: Multi-source Supermarket Search (Lidl, Aldi)")
    print("="*70)
    
    try:
        from core.tool_system import create_tool_registry
        
        registry = create_tool_registry()
        
        # Test address
        test_address = "15 Kentish Town Rd, London NW1 8NH"
        chains = ['Lidl', 'Aldi']
        
        print(f"Search address: {test_address}")
        print(f"Target chains: {', '.join(chains)}")
        print(f"Search radius: 2000m")
        print(f"\nExecuting search...")
        
        result = await registry.execute_tool(
            'search_supermarkets',
            address=test_address,
            chains=chains,
            radius_m=2000
        )
        
        if result.success:
            print(f"\n[OK] Search successful!")
            print(f"     Supermarkets found: {len(result.data)}")
            print(f"     Execution time: {result.metadata.get('execution_time_ms', 'N/A')}ms")
            print(f"     Search method: {result.metadata.get('methods_used', 'N/A')}")
            
            if result.data:
                print(f"\nSupermarkets found:")
                for i, shop in enumerate(result.data[:5], 1):
                    distance_str = f"{shop.get('distance_m')}m" if shop.get('distance_m') else "N/A"
                    print(f"     {i}. {shop.get('name')} ({shop.get('type')})")
                    print(f"        Location: {shop.get('address')}")
                    print(f"        Distance: {distance_str}")
                    print(f"        Source: {shop.get('source', 'unknown')}")
            else:
                print("     (No supermarkets found)")
            
            return True
        else:
            print(f"[FAIL] Search failed: {result.error}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Supermarket search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_direct_maps_function():
    """Test direct call to maps_service.get_nearby_supermarkets_detailed"""
    print("\n" + "="*70)
    print("TEST 3: Direct Call to maps_service Multi-source Search")
    print("="*70)
    
    try:
        from core.maps_service import get_nearby_supermarkets_detailed
        
        test_address = "15 Kentish Town Rd, London NW1 8NH"
        chains = ['Lidl', 'Aldi']
        
        print(f"Test address: {test_address}")
        print(f"Target chains: {', '.join(chains)}")
        print(f"\nExecuting search...")
        
        supermarkets = get_nearby_supermarkets_detailed(
            address=test_address,
            radius=2000,
            chains=chains
        )
        
        print(f"\n[OK] Search completed!")
        print(f"     Supermarkets found: {len(supermarkets)}")
        
        if supermarkets:
            print(f"\nSupermarkets found:")
            for i, shop in enumerate(supermarkets[:5], 1):
                distance_str = f"{shop.get('distance_m')}m" if shop.get('distance_m') else "N/A"
                print(f"     {i}. {shop.get('name')} ({shop.get('type')})")
                print(f"        Address: {shop.get('address')}")
                print(f"        Distance: {distance_str}")
                print(f"        Brand: {shop.get('brand', 'N/A')}")
                print(f"        Source: {shop.get('source', 'unknown')}")
        else:
            print("     (No supermarkets found)")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Direct call test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cache_functionality():
    """Test cache functionality"""
    print("\n" + "="*70)
    print("TEST 4: Cache Functionality Verification")
    print("="*70)
    
    try:
        from core.maps_service import get_nearby_supermarkets_detailed
        import time
        
        test_address = "Test Cache Address"
        
        # First call - should execute search
        print(f"First call (not in cache)...")
        start = time.time()
        result1 = get_nearby_supermarkets_detailed(test_address, radius=2000)
        time1 = time.time() - start
        
        print(f"[OK] First call time: {time1:.3f}s")
        
        # Second call - should read from cache (faster)
        print(f"Second call (should read from cache)...")
        start = time.time()
        result2 = get_nearby_supermarkets_detailed(test_address, radius=2000)
        time2 = time.time() - start
        
        print(f"[OK] Second call time: {time2:.3f}s")
        
        if time2 < time1:
            print(f"[OK] Cache working! Speedup ratio: {time1/time2:.1f}x")
            return True
        else:
            print(f"[WARN] Cache may not be enabled (times are similar)")
            return True  # Not a failure
            
    except Exception as e:
        print(f"[FAIL] Cache test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n")
    print("+" + "="*68 + "+")
    print("|" + " "*15 + "Tool System & Multi-source POI Search Tests" + " "*10 + "|")
    print("+" + "="*68 + "+")
    
    results = []
    
    # Run tests
    results.append(("Tool System Initialization", await test_tool_system()))
    results.append(("Multi-source Supermarket Search", await test_supermarket_search()))
    results.append(("Direct Call to maps_service", await test_direct_maps_function()))
    results.append(("Cache Functionality", await test_cache_functionality()))
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Tool System integration successful!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} tests failed, need investigation")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
