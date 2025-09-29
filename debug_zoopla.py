# debug_zoopla_detail.py

import requests
import json
import time

def get_detail_page_html():
    """
    一个专门用于获取单个Zoopla详情页HTML的调试脚本。
    """
    session = requests.Session()
    flaresolverr_url = "http://localhost:8191/v1"
    headers = {'Content-Type': 'application/json'}
    session_id = 'zoopla_debug_session'
    
    # 您提供的有问题的URL
    target_url = "https://www.zoopla.co.uk/to-rent/details/59905851/"

    print("--- 启动Zoopla详情页HTML获取程序 ---")
    
    try:
        # 1. 创建 FlareSolverr 会话
        print(f"1. 正在创建 FlareSolverr 会话 (ID: {session_id})...")
        init_payload = {'cmd': 'sessions.create', 'session': session_id}
        response = session.post(flaresolverr_url, headers=headers, json=init_payload, timeout=20)
        response.raise_for_status()
        if response.json().get('status') != 'ok':
            raise Exception("无法创建FlareSolverr会话。")
        print("   会话创建成功。")

        # 2. 通过 FlareSolverr 获取详情页
        print(f"2. 正在请求URL: {target_url} ...")
        payload = {
            'cmd': 'request.get',
            'url': target_url,
            'session': session_id,
            'maxTimeout': 60000 
        }
        response = session.post(flaresolverr_url, headers=headers, json=payload, timeout=70)
        response.raise_for_status()
        
        flare_data = response.json()
        if flare_data.get('status') != 'ok':
            raise Exception(f"FlareSolverr返回错误: {flare_data.get('message', 'Unknown error')}")
            
        html = flare_data['solution']['response']
        print("   页面HTML获取成功。")

        # 3. 将获取到的HTML保存到文件
        output_filename = 'zoopla_detail_debug_page.html'
        print(f"3. 正在将HTML内容保存到文件: {output_filename} ...")
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"   文件 '{output_filename}' 已成功保存！")

    except Exception as e:
        print(f"\n--- 程序出错 ---")
        print(f"错误信息: {e}")
        print("请确保您的Docker FlareSolverr容器正在另一个终端中运行。")
    finally:
        # 4. 销毁会话
        print("4. 正在销毁 FlareSolverr 会话...")
        destroy_payload = {'cmd': 'sessions.destroy', 'session': session_id}
        session.post(flaresolverr_url, headers=headers, json=destroy_payload, timeout=20)
        print("   会话已销毁。")
        print("\n--- 调试程序执行完毕 ---")


if __name__ == '__main__':
    get_detail_page_html()