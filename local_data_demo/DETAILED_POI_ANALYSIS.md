# Scape Bloomsbury 附近设施搜索问题详细分析报告

## 测试日期：2025年10月23日

---

## 问题1：超市地址准确性问题

### Alex的回答：
```
• Waitrose (supermarket) - 23-29 Brunswick Square - 223m away
• Tesco Express (convenience store) - 23-29 Brunswick Square - 223m away
• Sainsbury's Local (convenience store) - 23-29 Brunswick Square - 224m away
```

### 用户的质疑：
> "Tesco Express和Sainsbury's Local和Waitrose的位置是一个"

### 测试结果：

#### ✅ **距离数据准确**
- Waitrose 实际距离：**223m** ✅（与Alex说的一致）
- 距离计算是准确的

#### ❌ **Tesco和Sainsbury's根本不存在**
OpenStreetMap在1.5km范围内找到的超市：
```
✅ Waitrose         - 223m  (真实存在)
❌ Tesco Express    - 未找到（Alex编造的）
❌ Sainsbury's Local - 未找到（Alex编造的）
✅ Lidl             - 696m  (真实存在，但Alex没提到)
```

#### ❌ **"23-29 Brunswick Square"地址是编造的**
- OpenStreetMap数据中**没有**Brunswick Square的超市
- 真实数据只有**坐标**，没有街道地址
- LLM **编造了**"23-29 Brunswick Square"这个地址
- Waitrose的真实坐标：(51.5249, -0.1242)

### 结论：
**问题1的根因：LLM编造了Tesco和Sainsbury's，以及统一的Brunswick Square地址**

---

## 问题2：餐厅距离问题

### Alex的回答：
```
1. The Delaunay           - 0.2 miles (320m, 4分钟步行)
2. Simpson's-in-the-Strand - 0.3 miles (480m, 6分钟步行)
3. Padella                - 0.4 miles (640m, 8分钟步行)
4. The Barbary            - 0.5 miles (800m, 10分钟步行)
```

### 用户的质疑：
> "Alex推荐的餐厅位置都特别远，明明我要的是这个住址旁边的餐厅"

### 测试结果：

#### ❌ **Alex声称的距离完全错误**

| 餐厅名 | Alex说的距离 | 实际距离 | 差距 | 在1.5km内？ |
|--------|-------------|---------|------|-----------|
| The Delaunay | 320m | **1410m** | **+1090m** | ✅ 是 |
| Simpson's-in-the-Strand | 480m | **>1500m** | **N/A** | ❌ 否 |
| Padella | 640m | **>1500m** | **N/A** | ❌ 否 |
| The Barbary | 800m | **1114m** | **+314m** | ✅ 是 |

#### ✅ **真实的最近餐厅（Alex应该推荐的）：**

| 排名 | 餐厅名 | 实际距离 | Alex提到了吗？ |
|------|--------|---------|---------------|
| 1 | Crazy Salad | **36m** | ❌ 否 |
| 2 | Nonna Selena Pizzeria | **41m** | ❌ 否 |
| 3 | WingWing Krispy Chicken | **46m** | ❌ 否 |
| 4 | Poppadom Express | **89m** | ❌ 否 |
| 5 | Bloomsbury Pizza Cafe | **107m** | ❌ 否 |
| 6 | China City | **146m** | ❌ 否 |
| 7 | Miné Mané | **151m** | ❌ 否 |
| 8 | fig & walnut | **170m** | ❌ 否 |
| 9 | Leo Sushi | **185m** | ❌ 否 |
| 10 | Gourmet Burger Kitchen | **208m** | ❌ 否 |

### 搜索范围验证：

**问：是按Bloomsbury大区搜索还是按公寓搜索？**

**答：✅ 按公寓精确坐标搜索**

```python
搜索参数：
- 地址：Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK
- 坐标：(51.5244, -0.1273)  # 精确的公寓位置
- 搜索半径：1500m (1.5km)
- 搜索方式：以公寓为圆心画半径1.5km的圆，查找圆内所有餐厅
```

**不是**按"Bloomsbury"这个大区名搜索，而是按公寓的**精确GPS坐标**搜索。

### 结论：
**问题2的根因：LLM忽略了真实的最近餐厅（36-200m），选择了"著名"但"远得多"的餐厅（1100-1400m），且错误报告了距离**

---

## 综合问题分析

### 数据获取层 ✅ **完全正常**
```
OpenStreetMap API工作正常：
- 餐厅：找到878家真实餐厅
- 超市：找到19家真实超市
- 坐标：精确到小数点后4位
- 距离：使用Haversine公式准确计算
```

### LLM响应层 ❌ **严重问题**

#### 问题1：**编造不存在的店铺**
```
编造的店铺：
❌ Tesco Express (1.5km内不存在)
❌ Sainsbury's Local (1.5km内不存在)
❌ Simpson's-in-the-Strand (1.5km内不存在)
❌ Padella (1.5km内不存在)
```

#### 问题2：**编造地址信息**
```
编造的地址：
❌ "23-29 Brunswick Square" (OpenStreetMap数据中没有这个地址)

原因：
- OpenStreetMap只返回了坐标，没有街道地址
- LLM使用预训练知识"填补"了地址信息
- 这个地址可能是真实的，但不在OpenStreetMap数据中
```

#### 问题3：**错误的距离信息**
```
The Delaunay:
  Alex说：320m
  实际：1410m
  错误：+1090m (多报了340%)

The Barbary:
  Alex说：800m
  实际：1114m
  错误：+314m (多报了39%)
```

#### 问题4：**忽略最近的真实数据**
```
真实的最近餐厅（36m）：❌ Alex没提到
真实的最近餐厅（41m）：❌ Alex没提到
真实的最近餐厅（46m）：❌ Alex没提到

LLM选择标准：名气 > 距离
用户需要的标准：距离 > 名气
```

---

## 技术根因分析

### 1. LLM的"知识污染"问题

**什么是知识污染？**
- LLM在预训练时学到了"The Delaunay是Bloomsbury附近的著名餐厅"
- 当用户询问Bloomsbury餐厅时，LLM倾向于回忆这些"著名"餐厅
- 即使提供了真实的OpenStreetMap数据，LLM也会优先使用预训练知识

**证据：**
```python
# OpenStreetMap提供的数据（正确）：
top_restaurants = [
    "Crazy Salad - 36m",
    "Nonna Selena Pizzeria - 41m",
    "WingWing Krispy Chicken - 46m"
]

# LLM选择的餐厅（错误）：
alex_choice = [
    "The Delaunay - 1410m",     # 著名餐厅，但很远
    "Simpson's - >1500m",        # 著名餐厅，超出范围
    "Padella - >1500m"          # 著名餐厅，超出范围
]
```

### 2. Prompt约束力不足

**当前Prompt：**
```python
"""
INSTRUCTIONS:
1. List the restaurant locations exactly as shown above with names and distances
2. Include distances in both meters and kilometers
3. Do NOT invent names or locations not in this list
4. Provide helpful context about which ones are closest
"""
```

**问题：**
- 对小型LLM（Llama 3.2 1B）来说，这些指令**约束力不够**
- LLM倾向于"帮助"用户找"好"餐厅，而非"近"餐厅
- 没有明确惩罚机制防止编造

### 3. 缺少验证机制

**当前流程：**
```
OpenStreetMap数据 → LLM → 用户
                    ↑
                 (没有验证)
```

**应该的流程：**
```
OpenStreetMap数据 → LLM → 验证器 → 用户
                           ↑
                    (检查编造的名字)
                    (验证距离准确性)
```

### 4. 地址数据不完整

**OpenStreetMap数据结构：**
```json
{
  "name": "Waitrose",
  "distance_m": 223,
  "address": "(51.5249, -0.1242)",  // ⚠️ 只有坐标
  "lat": 51.5248978,
  "lon": -0.1241527
}
```

**问题：**
- OpenStreetMap没有返回街道地址
- LLM"填补"了"23-29 Brunswick Square"
- 这个地址可能是对的，但不应该由LLM编造

---

## 修复方案

### 方案A：强制性Prompt + 结构化输出（立即实施）

#### 修改1：餐厅搜索Prompt

```python
# 文件：app.py，第293-343行

# 当前问题：只提供前10个，但没有强制要求LLM使用它们
poi_text = "\n".join([
    f"- {place['name']} - {place['distance_m']}m away"
    for place in poi_data[:10]
])

# 修复方案：
# 1. 只提供前5个最近的
# 2. 使用JSON格式
# 3. 明确禁止使用其他餐厅

top_5 = poi_data[:5]
structured_data = []
for i, place in enumerate(top_5, 1):
    structured_data.append({
        "rank": i,
        "name": place['name'],
        "distance_m": place['distance_m'],
        "distance_km": round(place['distance_m']/1000, 2),
        "coordinates": f"({place['lat']:.4f}, {place['lon']:.4f})"
    })

import json
data_json = json.dumps(structured_data, indent=2, ensure_ascii=False)

prompt = f"""用户问题："{user_message}"
房源地址：{address}

===== 真实数据（来自OpenStreetMap，禁止修改）=====
{data_json}
===== 真实数据结束 =====

严格要求：
1. 只能使用上面JSON中的5家餐厅
2. 必须逐字复制餐厅名（不要翻译，不要修改）
3. 必须使用上面显示的精确距离
4. 禁止提到任何其他餐厅（如"The Delaunay"、"Simpson's"、"Padella"等）
5. 如果用户问"附近"，理解为500m以内
6. 按距离从近到远排序

回答格式：
"根据OpenStreetMap的真实数据，这个房源最近的5家餐厅是：

1. [从JSON复制餐厅名] - [从JSON复制距离]米（[从JSON复制公里数]公里）
2. ...

其中前3家都在[X]米以内，步行只需[Y]分钟。"

用中文回答，但餐厅名保持原文。"""
```

#### 修改2：超市搜索Prompt

```python
# 处理用户询问的特定连锁超市

target_chains = ['tesco', 'sainsbury', 'lidl', 'waitrose', 'aldi', 'co-op']
found_chains = {}

for chain in target_chains:
    found = [p for p in poi_data if chain.lower() in p['name'].lower()]
    if found:
        found_chains[chain] = found[0]  # 只取最近的一个

if found_chains:
    chains_json = json.dumps([
        {
            "chain": chain.upper(),
            "name": data['name'],
            "distance_m": data['distance_m'],
            "distance_km": round(data['distance_m']/1000, 2),
            "coordinates": f"({data['lat']:.4f}, {data['lon']:.4f})",
            "address": "OpenStreetMap未提供街道地址" if data['address'].startswith('(') else data['address']
        }
        for chain, data in found_chains.items()
    ], indent=2, ensure_ascii=False)
    
    prompt = f"""用户问题："{user_message}"
房源地址：{address}

===== 真实数据（来自OpenStreetMap）=====
{chains_json}
===== 真实数据结束 =====

严格要求：
1. 只能使用上面JSON中的超市
2. 如果JSON中没有某个连锁店，明确说"未找到"
3. 不要编造地址信息（如果address显示"未提供街道地址"，就说"具体地址未知，坐标为..."）
4. 必须使用精确的距离数字
5. 禁止说多个超市在"同一地址"（除非坐标完全相同）

回答格式：
"根据OpenStreetMap数据，在1.5公里范围内找到以下连锁超市：

• [连锁名] - [精确距离]米（[公里数]公里）
  地址：[如果有就显示，没有就说"坐标：(x, y)"]

未找到：[用户询问但不存在的连锁店]"

用中文回答。"""
else:
    prompt = f"""OpenStreetMap在1.5km范围内未找到用户询问的连锁超市（{', '.join(target_chains)}）。

请诚实告诉用户这些连锁超市不在附近，但可以列出实际找到的其他超市。"""
```

### 方案B：后处理验证（额外保护）

```python
def validate_poi_response(llm_response: str, real_data: List[Dict], poi_type: str) -> str:
    """
    验证LLM响应的准确性
    
    检查：
    1. 是否提到了不在真实数据中的店铺
    2. 距离数字是否准确
    3. 是否编造了地址
    """
    real_names = [p['name'].lower() for p in real_data[:10]]
    
    # 常见的"著名"餐厅/超市（经常被编造）
    fake_markers = {
        'restaurant': ['the delaunay', 'wolseley', 'padella', 'dishoom', 'simpson', 
                       'hawksmoor', 'the ivy', 'nobu', 'sketch'],
        'supermarket': ['tesco', 'sainsbury', 'waitrose', 'lidl', 'aldi']
    }
    
    # 检查是否提到了编造的店铺
    detected_fakes = []
    for fake in fake_markers.get(poi_type, []):
        if fake in llm_response.lower():
            # 检查这个名字是否在真实数据中
            if not any(fake in name for name in real_names):
                detected_fakes.append(fake)
                print(f"⚠️ 检测到可能编造的{poi_type}名: {fake}")
    
    # 如果检测到编造，生成安全的回答
    if detected_fakes:
        print(f"❌ LLM编造了{len(detected_fakes)}个{poi_type}名，使用安全回答")
        
        safe_response = f"根据OpenStreetMap的真实数据，这个房源附近的{poi_type}有：\n\n"
        for i, place in enumerate(real_data[:5], 1):
            distance_m = place['distance_m']
            distance_km = round(distance_m / 1000, 2)
            safe_response += f"{i}. **{place['name']}** - {distance_m}米（{distance_km}公里）\n"
        
        safe_response += f"\n共找到{len(real_data)}家{poi_type}在1.5公里范围内。"
        safe_response += f"\n\n（注意：系统检测到一些不在附近的{poi_type}名被错误提及，已自动更正为真实数据）"
        
        return safe_response
    
    # 检查距离数字
    import re
    distances_in_response = re.findall(r'(\d+)m', llm_response)
    real_distances = [str(p['distance_m']) for p in real_data[:10]]
    
    suspicious_distances = [d for d in distances_in_response if d not in real_distances]
    if suspicious_distances:
        print(f"⚠️ 检测到可疑的距离数字: {suspicious_distances}")
        print(f"   真实距离: {real_distances[:5]}")
    
    return llm_response
```

### 方案C：添加步行时间计算

```python
# 为每个POI添加步行时间
from core.maps_service import calculate_travel_time

def enrich_poi_with_walk_time(poi_data: List[Dict], origin_address: str) -> List[Dict]:
    """为POI数据添加步行时间"""
    
    for place in poi_data[:5]:  # 只为前5个计算
        # 使用坐标作为目的地
        dest_coords = f"{place['lat']},{place['lon']}"
        
        try:
            walk_time = calculate_travel_time(origin_address, dest_coords, mode='walking')
            place['walk_time_minutes'] = walk_time
        except Exception as e:
            print(f"   ⚠️ 无法计算到{place['name']}的步行时间: {e}")
            place['walk_time_minutes'] = None
    
    return poi_data

# 在查询后调用
poi_data = get_nearby_places_osm(address, 'restaurant', radius_m=1500)
poi_data = enrich_poi_with_walk_time(poi_data, address)

# 在prompt中包含步行时间
for place in poi_data[:5]:
    walk_time = place.get('walk_time_minutes')
    if walk_time:
        print(f"  • {place['name']} - {place['distance_m']}m - 步行{walk_time}分钟")
```

---

## 实施优先级

### 🔴 **紧急（立即实施）**

1. **修改餐厅搜索Prompt**（方案A-修改1）
   - 只提供前5个最近的
   - 使用JSON格式
   - 明确禁止提到其他餐厅
   - 预计修复时间：15分钟

2. **修改超市搜索Prompt**（方案A-修改2）
   - 只显示用户询问的连锁店
   - 不要编造地址
   - 未找到时诚实说明
   - 预计修复时间：15分钟

### 🟡 **重要（1-2天内）**

3. **添加后处理验证**（方案B）
   - 检测编造的店铺名
   - 验证距离数字
   - 自动替换为安全答案
   - 预计开发时间：1小时

### 🟢 **优化（1周内）**

4. **添加步行时间计算**（方案C）
   - 使用Google Maps API
   - 为前5个POI计算步行时间
   - 在回答中包含时间信息
   - 预计开发时间：30分钟

5. **改进地址数据**
   - 使用Google Geocoding API获取街道地址
   - 缓存地址数据
   - 只显示验证过的地址
   - 预计开发时间：1小时

---

## 测试验证计划

### 测试用例1：餐厅搜索
```
输入："Scape Bloomsbury附近有没有餐厅？"

期望输出：
✅ 应该提到：Crazy Salad (36m)
✅ 应该提到：Nonna Selena Pizzeria (41m)
❌ 不应提到：The Delaunay, Padella, Simpson's
✅ 距离应该是真实数据中的数字
```

### 测试用例2：连锁超市搜索
```
输入："附近有没有Tesco, Sainsbury's, Lidl, Waitrose？"

期望输出：
✅ 应该说：Waitrose - 223m
✅ 应该说：Lidl - 696m
✅ 应该说：未找到Tesco
✅ 应该说：未找到Sainsbury's
❌ 不应该编造地址
```

### 测试用例3：验证机制
```
如果LLM仍然提到"The Delaunay"：
✅ 验证器应该检测到
✅ 自动替换为真实数据回答
✅ 记录日志
```

---

## 附录：完整测试数据

### 真实的超市数据（OpenStreetMap）
```
1. Waitrose - 223m
2. Tian Tian Market - 228m
3. M&S Foodhall - 686m
4. Lidl - 696m
5. Amazon Fresh - 813m

❌ 未找到：Tesco
❌ 未找到：Sainsbury's
❌ 未找到：Aldi
```

### 真实的餐厅数据（OpenStreetMap，前20个）
```
1. Crazy Salad - 36m
2. Nonna Selena Pizzeria - 41m
3. WingWing Krispy Chicken - 46m
4. Poppadom Express - 89m
5. Bloomsbury Pizza Cafe - 107m
6. China City - 146m
7. Miné Mané - 151m
8. fig & walnut - 170m
9. Leo Sushi - 185m
10. Pizza Sophia - 199m
11. La Dolce - 204m
12. The Bumble Bees - 205m
13. Gourmet Burger Kitchen - 208m
14. Franco Manca - 234m
15. Galvin Bar & Grill - 243m
16. DEPA Tandoori - 245m
17. Apollo - 248m
18. North Sea Fish - 262m
19. Nando's - 263m
20. The Delaunay - 1410m  ⚠️ 很远！
```

---

## 结论

**数据获取层**：✅ 完全正常，OpenStreetMap API工作完美

**LLM响应层**：❌ 严重问题
- 编造不存在的店铺（Tesco, Sainsbury's, Simpson's, Padella）
- 编造地址信息（Brunswick Square）
- 错误的距离信息（320m vs 1410m）
- 忽略最近的真实数据，偏好"著名"但"遥远"的选项

**搜索方式**：✅ 按公寓精确坐标搜索，不是按大区

**修复策略**：
1. 强化Prompt约束（JSON格式，禁止列表）
2. 添加后处理验证（检测编造）
3. 只提供最近的5个结果（减少LLM选择空间）
4. 添加步行时间信息（更实用）

预计修复后，准确率可从**30%**提升到**95%+**。
