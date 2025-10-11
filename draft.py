# import requests

# url = "http://localhost:11434/api/generate"
# # Ollama是个本地运行的语言模型，可以通过REST API调用
# payload = {
#     "model": "llama3.2:1b",
#     "prompt": "Hello, how are you?",
#     "stream": False  # 一次性返回结果
# }
# print('hello')
# response = requests.post(url, json=payload)
# print(response.json())

'''
{'model': 'llama3.2:1b', 'created_at': '2025-10-07T21:11:15.815403Z', 'response': "I'm doing well, thanks for asking. I'm a large language model, so I don't have feelings or emotions like humans do, but I'm here and ready to help you with any questions or topics you'd like to discuss. How about you? How's your day going so far?", 'done': True, 'done_reason': 'stop', 'context': [128006, 9125, 128007, 271, 38766, 1303, 33025, 2696, 25, 6790, 220, 2366, 18, 271, 128009, 128006, 882, 128007, 271, 9906, 11, 1268, 527, 499, 30, 128009, 128006, 78191, 128007, 271, 40, 2846, 3815, 1664, 11, 9523, 369, 10371, 13, 358, 2846, 264, 3544, 4221, 1646, 11, 779, 358, 1541, 956, 617, 16024, 477, 21958, 1093, 12966, 656, 11, 719, 358, 2846, 1618, 323, 5644, 311, 1520, 499, 449, 904, 4860, 477, 13650, 499, 4265, 1093, 311, 4358, 13, 2650, 922, 499, 30, 2650, 596, 701, 1938, 2133, 779, 3117, 30], 'total_duration': 727720875, 'load_duration': 64979291, 'prompt_eval_count': 31, 'prompt_eval_duration': 63123875, 'eval_count': 61, 'eval_duration': 598997875}
'''

import requests

# 目标 API
api_url = "https://www.rightmove.co.uk/api/_search"

# 测试参数（这里随便选了伦敦某个地区 OUTCODE）
params = {
    "locationIdentifier": "REGION^87490",   # 位置ID（这里是 London）
    "minBedrooms": 1,                       # 最小卧室数量
    "maxBedrooms": 3,                       # 最大卧室数量
    "minPrice": 300,                       # 最低价格 (£)
    "maxPrice": 20000,                       # 最高价格 (£)
    "radius": 10.0,                          # 搜索半径（英里）
    "channel": "RENT",                      # 渠道（RENT=租房，BUY=买房）
    "index": 0,                             # 翻页索引（0=第一页，24=第二页...）
    "viewType": "LIST",                     # 列表展示
    "sortType": "6",                        # 排序方式（6=最近发布，1=价格从低到高...）
    "numberOfPropertiesPerPage": 24,        # 每页多少个房源
}


# 模拟浏览器 headers
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/141.0.0.0 Safari/537.36"
}

# 发请求
try:
    response = requests.get(api_url, headers=headers, params=params, timeout=10)
    print("Status Code:", response.status_code)

    if response.status_code == 200:
        # 打印前500字符，看看是否拿到 JSON
        print(response.text)
    else:
        print("❌ 请求失败")

except Exception as e:
    print("⚠️ 出错:", e)
