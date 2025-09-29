# main.py

import asyncio
from recommender import find_apartments
import json

if __name__ == "__main__":
    user_query = """
    Hi, I would like to find some apartment near UCL, Gower Street, London.
    The rent per month should not be exceeding 1800 and 
    the time of travelling should be within 40 min 
    from door to door by public transport. I am also concerned 
    about the crime rate in the area and would like a place with 
    good access to supermarkets and parks.
    """
    
    # 异步执行主函数
    results = asyncio.run(find_apartments(user_query))
    
    # 打印最终输出
    print("\n==============================================")
    print("         APARTMENT RECOMMENDATIONS")
    print("==============================================")
    
    if results and 'recommendations' in results:
        for rec in results['recommendations']:
            print(f"\n--- RANK {rec.get('rank', 'N/A')} ---")
            print(f"Address: {rec.get('address', 'N/A')}")
            print(f"Price: {rec.get('price', 'N/A')}")
            print(f"Travel Time to Destination: {rec.get('travel_time', 'N/A')} minutes")
            print("\nExplanation:")
            print(rec.get('explanation', 'No explanation provided.'))
            print("----------------------------------------------")
    else:
        print("\nSorry, I could not generate any recommendations based on your criteria.")