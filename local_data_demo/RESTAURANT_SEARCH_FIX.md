# 餐厅搜索问题分析与修复方案

## 问题总结

用户询问"Scape Bloomsbury附近有没有餐厅"，Alex（AI助手）提供了以下餐厅：
1. The Delaunay ✅ (在真实数据中，但距离约1.3km)
2. The Wolseley ❌ (编造的，实际不在1.5km范围内)
3. Padella ❌ (编造的，实际不在1.5km范围内)
4. Dishoom ✅ (在真实数据中，但距离约800m)

**问题**：Alex提到的餐厅大多距离较远（而非"附近"），且部分是编造的。

---

## 测试结果

### ✅ 数据获取层工作正常

运行 `test_restaurant_search.py` 验证：

```
✅ 找到 878 家餐厅在 1.5km 范围内

前10家最近的餐厅：
 1. Crazy Salad                   -   36m (0.04km)
 2. Nonna Selena Pizzeria         -   41m (0.04km)
 3. WingWing Krispy Chicken       -   46m (0.05km)
 4. Poppadom Express              -   89m (0.09km)
 5. Bloomsbury Pizza Cafe         -  107m (0.11km)
 6. China City                    -  146m (0.15km)
 7. Miné Mané                     -  151m (0.15km)
 8. fig & walnut                  -  170m (0.17km)
 9. Leo Sushi                     -  185m (0.18km)
10. Poppie's Fish & Chips         -  193m (0.19km)
```

**结论**：
- OpenStreetMap Overpass API **正常工作**
- 返回了878家真实餐厅数据
- 最近的餐厅距离仅36米

### ❌ LLM响应层存在问题

Alex提到的餐厅：
- **The Delaunay**: 在数据中，但距离约1.3km（不是"附近"）
- **The Wolseley**: 不在1.5km范围内（可能编造）
- **Padella**: 不在1.5km范围内（可能编造）
- **Dishoom**: 在数据中，但距离约800m

**真实的最近餐厅（应该推荐的）**：
- Crazy Salad - 36米
- Nonna Selena Pizzeria - 41米
- WingWing Krispy Chicken - 46米

---

## 根本原因分析

### 1. LLM没有严格使用提供的数据

检查 `app.py` 第293-343行的餐厅查询逻辑：

```python
if detected_poi:
    print(f"  [Overpass API] {detected_poi.upper()} search for: {address}")
    from core.maps_service import get_nearby_places_osm
    
    poi_data = get_nearby_places_osm(address, detected_poi, radius_m=1500)
    
    if poi_data and len(poi_data) > 0:
        # Format the detailed location data
        poi_text = "\n".join([
            f"- {place['name']} - {place['distance_m']}m away ({round(place['distance_m']/1000, 1)}km)"
            for place in poi_data[:10]  # Top 10
        ])
        
        prompt = f"""The user asked: "{user_message}"
Property address: {address}

VERIFIED DATA (OpenStreetMap via Overpass API):
Found {len(poi_data)} {detected_poi} locations within 1.5km:

{poi_text}

INSTRUCTIONS:
1. List the {detected_poi} locations exactly as shown above with names and distances
2. Include distances in both meters and kilometers
3. Do NOT invent names or locations not in this list
4. Provide helpful context about which ones are closest
5. If user asks about travel time, explain that it depends on method (walking, cycling, public transport)

Provide a helpful, friendly response using ONLY this verified data."""
```

**问题**：
- Prompt已经明确要求"ONLY use this verified data"
- 但LLM仍然忽略了这些指令，使用了自己的知识库
- LLM倾向于提供"著名"的餐厅而非真实的最近餐厅

### 2. LLM的"幻觉"(Hallucination)

小型LLM（如Llama 3.2 1B）在这类任务中容易：
- 忽略提供的具体数据
- 使用预训练时学到的"常识"
- 编造听起来合理的答案

### 3. System Prompt不够强制性

当前的system prompt：
```python
system_prompt = """You are Alex, a friendly and knowledgeable UK rental assistant. 
CRITICAL RULES:
1. ONLY use data from the provided search results
2. NEVER invent store names, distances, or locations
3. If data is incomplete, say "Based on available data..." and be honest
4. Always verify before claiming something is "nearby" """
```

这个prompt虽然有要求，但对小型LLM来说不够强制。

---

## 修复方案

### 方案 1：强化Prompt + 结构化输出（推荐）

**修改 `app.py` 第293-343行**：

```python
if detected_poi:
    print(f"  [Overpass API] {detected_poi.upper()} search for: {address}")
    from core.maps_service import get_nearby_places_osm
    
    poi_data = get_nearby_places_osm(address, detected_poi, radius_m=1500)
    
    if poi_data and len(poi_data) > 0:
        # 只取前5个最近的
        top_5 = poi_data[:5]
        
        # 构建结构化数据
        structured_data = []
        for i, place in enumerate(top_5, 1):
            structured_data.append({
                "rank": i,
                "name": place['name'],
                "distance_m": place['distance_m'],
                "distance_km": round(place['distance_m']/1000, 2)
            })
        
        import json
        data_json = json.dumps(structured_data, indent=2, ensure_ascii=False)
        
        prompt = f"""User asked: "{user_message}"
Property: {address}

===== REAL DATA FROM OPENSTREETMAP (DO NOT MODIFY) =====
{data_json}
===== END OF REAL DATA =====

YOU MUST:
1. Copy the restaurant names EXACTLY as shown above
2. Copy the distances EXACTLY as shown above  
3. DO NOT add any restaurant not in the list above
4. DO NOT mention any famous restaurant like "The Delaunay", "Wolseley", "Padella" unless they appear in the data above
5. Start with: "Based on OpenStreetMap data, the nearest restaurants are:"

Format example:
"Based on OpenStreetMap data, the nearest restaurants are:
1. [Name from data] - [distance from data]m away
2. [Name from data] - [distance from data]m away
..."

Answer in Chinese using ONLY the data provided above."""
```

### 方案 2：后处理验证（额外保护）

在LLM响应后，添加验证步骤：

```python
def validate_poi_response(llm_response: str, real_poi_data: List[Dict]) -> str:
    """
    验证LLM响应是否只使用了真实数据
    
    如果发现编造的餐厅名，替换为真实数据
    """
    real_names = {place['name'] for place in real_poi_data[:10]}
    
    # 检查常见的编造餐厅
    fake_restaurants = [
        "The Delaunay", "Wolseley", "Padella", "Dishoom", 
        "Hawksmoor", "The Ivy", "Nobu", "Sketch"
    ]
    
    # 如果发现编造的餐厅名，直接返回基于真实数据的回答
    for fake in fake_restaurants:
        if fake in llm_response and fake not in real_names:
            print(f"⚠️ 检测到编造的餐厅名: {fake}")
            print(f"   替换为真实数据...")
            
            # 生成安全的、基于真实数据的回答
            response = "根据OpenStreetMap数据，这个房源附近有以下餐厅：\n\n"
            for i, place in enumerate(real_poi_data[:5], 1):
                distance_m = place['distance_m']
                distance_km = round(distance_m / 1000, 2)
                response += f"{i}. **{place['name']}** - {distance_m}米（{distance_km}公里）\n"
            
            response += f"\n共找到{len(real_poi_data)}家餐厅在1.5公里范围内。"
            return response
    
    return llm_response
```

### 方案 3：切换到Function Calling模式

使用更现代的Function Calling API，让LLM只负责决策，不负责生成最终答案：

```python
# 让LLM选择要展示的餐厅（通过索引）
function_call_prompt = f"""User: "{user_message}"

Available restaurants (from OpenStreetMap):
{json.dumps(structured_data, indent=2)}

Select the top 3-5 restaurants to recommend (by rank number).
Return JSON: {{"selected_ranks": [1, 2, 3, 4, 5]}}
"""

# LLM只返回索引，我们自己格式化最终答案
selected = call_llm_function(function_call_prompt)
recommended = [structured_data[i-1] for i in selected['selected_ranks']]

# 我们自己生成最终答案（100%准确）
response = "根据OpenStreetMap数据，这个房源附近有以下餐厅：\n\n"
for place in recommended:
    response += f"{place['rank']}. **{place['name']}** - {place['distance_m']}米\n"
```

---

## 关于出行时间计算

测试显示出行时间计算**功能正常**：

```
从: Scape Bloomsbury, London
到: Dishoom King's Cross, London
步行时间: 25 分钟
✅ 出行时间计算功能正常
```

**问题**：虽然功能正常，但**没有被调用**。

原因：
- 当前实现只在property推荐时计算到目的地（如大学）的出行时间
- 没有在POI查询时计算到每个餐厅的出行时间

**建议改进**：
```python
# 为前5个最近的餐厅计算步行时间
for place in poi_data[:5]:
    restaurant_address = f"{place['lat']},{place['lon']}"  # 使用坐标
    walk_time = calculate_travel_time(address, restaurant_address, mode='walking')
    place['walk_time_minutes'] = walk_time
```

---

## 推荐实施步骤

### 立即修复（方案1）
1. 修改 `app.py` 中的POI查询prompt（使用结构化输出）
2. 限制只返回前5个最近的餐厅
3. 要求LLM逐字复制餐厅名和距离

### 短期改进（方案2）
1. 添加后处理验证函数
2. 检测并阻止常见的编造餐厅名
3. 在检测到问题时自动替换为真实数据

### 长期优化（方案3）
1. 实现Function Calling模式
2. 分离"决策"和"生成"职责
3. 让系统代码负责最终格式化，确保100%准确性

### 额外功能
1. 为每个餐厅添加步行时间计算
2. 在响应中包含出行方式建议
3. 考虑添加餐厅类型/评分信息（如果OSM数据中有）

---

## 测试验证

运行以下测试确保修复有效：

```bash
# 1. 测试OpenStreetMap数据获取
python test_restaurant_search.py

# 2. 测试完整的聊天流程
python app.py
# 然后询问："这个房源附近有没有餐厅？"

# 3. 验证响应中的餐厅名
# 应该看到：Crazy Salad, Nonna Selena Pizzeria, WingWing Krispy Chicken
# 不应该看到：The Delaunay, The Wolseley, Padella（除非它们真的在数据中）
```

---

## 总结

**当前状态**：
- ✅ OpenStreetMap API工作正常
- ✅ 返回了878家真实餐厅数据
- ✅ 出行时间计算功能正常
- ❌ LLM没有使用提供的数据
- ❌ LLM编造了部分餐厅名

**根本原因**：
- 小型LLM容易产生幻觉
- Prompt不够强制性
- 缺少后处理验证

**解决方案**：
- 使用结构化输出 + 强化Prompt
- 添加后处理验证
- 考虑Function Calling模式
- 添加步行时间计算

通过以上修复，可以确保Alex只提供**真实的、经过OpenStreetMap验证的**餐厅信息。
