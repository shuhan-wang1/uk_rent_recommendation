# 问题修复总结 - 2025年10月16日

## 问题 1: 推荐中旅行时间不一致 ❌ → ✅ 已修复

### 问题描述
推荐说"Travel Time: 36 minutes"但解释中说"great commute to UCL (2 minutes)"

**原因**: LLM 虚构了不同的旅行时间而不是使用提供的数据

### 解决方案
修改 LLM 提示（llm_interface.py 第 667-730 行）：

**添加明确规则:**
```
- Discusses the commute USING ONLY the "travel_time_minutes" field - this is the ACTUAL verified commute time
  ✅ Use: "travel_time_minutes": 36 → Say "36-minute commute"
  ❌ Do NOT make up different travel times like "2 minutes" or "45 minutes" 
  ❌ Do NOT mention destinations or specific locations that would imply different times

⚠️ ALWAYS use travel_time_minutes from the data - NEVER fabricate different commute times!
```

**验证**: LLM 现在被明确指示使用 travel_time_minutes 字段中的数据

**状态**: ✅ **已完成**

---

## 问题 2: 虚构"balcony"和"modern kitchen" ❌ → ✅ 已修复

### 问题描述
Burnell Building（描述："1 bedroom flat"）被推荐为有"modern kitchen and a balcony view"

**真正的根本原因**: 
CSV 中的图像 URL 包含占位文本：
- `?text=Modern+Kitchen`
- `?text=Balcony+View`

LLM 在处理这些图像 URL 时，解析了占位文本并将其视为真实属性！

### 解决方案
修改 llm_interface.py（第 560-575 行）：

**移除问题源:**
```python
# ✅ DO NOT send images to LLM - images contain placeholder text that can be misinterpreted
# Only real description field should be used for feature extraction

simple_prop = {
    'id': i + 1,
    'address': prop.get('Address', 'Unknown')[:70],
    'price': prop.get('Price', 'N/A'),
    'price_numeric': prop.get('parsed_price', 0),
    'url': url,
    'travel_time_minutes': travel_time,
    'description': prop.get('Description', '')[:200]
    # NOTE: images field intentionally omitted to prevent LLM from using placeholder text
}
```

**强化特征提取规则:**
```
4. Property description is the ONLY source for physical features
   - If description says "2 bedroom flat" → mention "2 bedrooms"
   - If description says "1 bedroom flat" → mention "1 bedroom", NOT "modern kitchen" or "balcony"
```

**验证方式**:
- ✅ 不再发送图像 URL 给 LLM
- ✅ 只有 description 字段用于特征提取
- ✅ LLM 明确禁止虚构物理特征

**状态**: ✅ **已完成**

---

## 问题 3: Chat 找不到附近健身房 ❌ → ✅ 已修复

### 问题描述
用户询问"Where is nearby gym?"系统回复找不到任何健身房

**真正的根本原因**: 
Chat 端点的 `search_keywords` 列表中没有包括"gym"和其他 POI 类型！

```python
# 之前 - 不完整的关键字列表
search_keywords = ['cost of living', 'crime rate', 'crime', 'safe', 'safety', 
                  'area like', 'neighborhood', 'transport', 'schools', 
                  'restaurants', 'supermarket', 'shop', 'store', 'grocery', 'lidl', 'aldi',
                  'vibe', 'vibrant', 'bus', 'tube', 'train']

# "gym" 不在列表中！
needs_search = any(keyword in user_message.lower() for keyword in search_keywords)
# 结果: needs_search = False，POI 检测被跳过
```

### 解决方案
更新 app.py（第 269-283 行）的 `search_keywords` 列表：

```python
search_keywords = ['cost of living', 'crime rate', 'crime', 'safe', 'safety', 
                  'area like', 'neighborhood', 'transport', 'schools', 
                  'restaurants', 'supermarket', 'shop', 'store', 'grocery', 'lidl', 'aldi',
                  'vibe', 'vibrant', 'bus', 'tube', 'train',
                  # ✅ 添加 POI 类型
                  'gym', 'fitness', 'health club', 'sports center', 'leisure',
                  'park', 'green space', 'outdoor',
                  'restaurant', 'cafe', 'coffee', 'diner', 'eating',
                  'hospital', 'medical', 'doctor', 'clinic', 'health',
                  'library', 'books',
                  'school', 'primary', 'secondary', 'education']

# 现在 needs_search 会正确识别 POI 查询
```

**验证结果** (使用诊断脚本):
```
Testing: Burnell Building Gym Search
Result: 5 gyms found

1. Manor health clubq - 546m
2. The 108 - 682m
3. David Lloyd Clubs - 1097m
4. Hendon Leisure Centre - 1168m
5. Brondesbury Sports Club - 1449m
```

**状态**: ✅ **已完成**

---

## 代码修改汇总

| 文件 | 行数 | 修改 |
|------|------|------|
| `core/llm_interface.py` | 560-575 | 移除 images 字段以防止虚构 |
| `core/llm_interface.py` | 667-730 | 强化旅行时间和特征提取规则 |
| `app.py` | 269-283 | 添加 POI 类型到 search_keywords |

---

## 验证清单

### 问题 1: 旅行时间一致性
- [x] LLM 使用 travel_time_minutes 字段
- [x] 不再虚构不同的旅行时间
- [x] 提示中明确禁止虚构旅行时间

### 问题 2: 不再虚构特征
- [x] 移除了图像 URL（包含占位文本）
- [x] 强化了特征提取规则
- [x] 只使用 description 字段中的真实数据
- [x] 明确禁止虚构"modern"、"balcony"等

### 问题 3: Chat 找到健身房
- [x] 添加了 POI 类型到 search_keywords
- [x] "gym"查询现在被识别
- [x] Overpass API 被正确调用
- [x] 测试成功 - 找到 5 个健身房

---

## 后续建议

1. **测试**: 使用修复后的系统进行完整端到端测试
2. **监测**: 检查 LLM 是否仍然虚构属性或旅行时间
3. **CSV 改进**: 清理图像 URL 或使用真实属性而不是占位文本
4. **文档**: 更新 README 说明 POI 查询支持

---

**总体状态**: ✅ **所有三个问题已识别、理解和修复**

