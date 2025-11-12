# Kling数据行为类型详解

本文档详细说明Kling数据的行为类型结构，帮助正确理解和使用行为信息。

## 📊 三层行为类型结构

Kling数据的行为信息由三个字段组成，形成层级结构：

```
event_type (事件类型)
    └── behavior_type (行为类型)
            └── behavior_subtype (行为子类型)
```

## 1️⃣ event_type（事件类型）

最顶层分类，表示用户行为发生的场景：

| 值 | 含义 | 说明 |
|---|------|------|
| `RECOMMEND` | 推荐场景 | 用户通过推荐流发现内容 |
| `SEARCH` | 搜索场景 | 用户主动搜索发现内容 |
| `PRODUCE` | 生产场景 | 用户创作内容 |

## 2️⃣ behavior_type（行为类型）

第二层分类，表示用户的具体交互方式：

| 值 | 含义 | 适用场景 | 说明 |
|---|------|---------|------|
| `OPERATE` | 操作行为 | RECOMMEND, SEARCH | 需要查看behavior_subtype细分 |
| `VIDEO_PLAY_FINISH` | 完播 | RECOMMEND, SEARCH | 视频播放完成 |
| `LONG_PLAY` | 长播放 | RECOMMEND, SEARCH | 播放时长较长 |
| `SHORT_PLAY` | 短播放 | RECOMMEND, SEARCH | 短暂浏览 |
| `NULL` | 空值 | **PRODUCE** | ⚠️ 生产场景下为null |

**重要**: 
- ✅ 在RECOMMEND和SEARCH场景，behavior_type有具体值
- ⚠️ 在PRODUCE场景，behavior_type为`null`（这是正常的，不是数据缺失）

## 3️⃣ behavior_subtype（行为子类型）

最细粒度分类，仅当`behavior_type='OPERATE'`时才有值：

| 值 | 含义 | 触发条件 | 英文描述 | 中文含义 |
|---|------|---------|---------|---------|
| `LIKE` | 点赞 | behavior_type='OPERATE' | liked | 点赞 |
| `UNLIKE` | 取消点赞 | behavior_type='OPERATE' | unliked | 取消点赞 |
| `COMMENT` | 评论 | behavior_type='OPERATE' | commented on | 评论 |
| `SHARE` | 分享 | behavior_type='OPERATE' | shared | 分享 |
| `SAME_STYLE` | 一键同款 | behavior_type='OPERATE' | used same style for | 一键同款 |
| `REPORT` | 举报 | behavior_type='OPERATE' | reported | 举报 |
| `LARGE` | 放大/点击 | behavior_type='OPERATE' | **clicked** | **点击** ✅ |
| `NULL` | 空值 | behavior_type != 'OPERATE' | - | - |

**关键点**:
- ✅ 只有 `behavior_type='OPERATE' AND behavior_subtype='LARGE'` 才是**点击**行为
- ❌ 不要把 `OPERATE` 本身当作点击
- ℹ️ 其他behavior_type下，behavior_subtype为`null`

## 🎯 点击行为的完整判断逻辑

根据 `load_kling_data.py` 第92-102行的SQL逻辑：

```sql
-- Web端点击
(platform_type = 'Web' 
 AND element_action = 'FANC_CARD'
 AND behavior_type = 'OPERATE' 
 AND behavior_subtype = 'LARGE')

-- 或者 App端点击
OR 
(platform_type = 'App' 
 AND behavior_type = 'OPERATE' 
 AND behavior_subtype = 'LARGE')
```

**条件组合**:
- Web端: 需要4个条件同时满足
- App端: 需要3个条件同时满足

## 📝 完整行为组合示例

### RECOMMEND场景

| event_type | behavior_type | behavior_subtype | 行为描述 |
|-----------|--------------|-----------------|---------|
| RECOMMEND | OPERATE | LIKE | 推荐流中点赞 |
| RECOMMEND | OPERATE | LARGE | 推荐流中点击放大 ✅ |
| RECOMMEND | VIDEO_PLAY_FINISH | NULL | 推荐流中完播 |
| RECOMMEND | LONG_PLAY | NULL | 推荐流中长播放 |
| RECOMMEND | SHORT_PLAY | NULL | 推荐流中短浏览 |

### SEARCH场景

| event_type | behavior_type | behavior_subtype | 行为描述 | 额外信息 |
|-----------|--------------|-----------------|---------|---------|
| SEARCH | OPERATE | LIKE | 搜索后点赞 | element_query_content, query_cnt |
| SEARCH | OPERATE | LARGE | 搜索后点击 ✅ | element_query_content, query_cnt |
| SEARCH | VIDEO_PLAY_FINISH | NULL | 搜索后完播 | element_query_content, query_cnt |

### PRODUCE场景

| event_type | behavior_type | behavior_subtype | 行为描述 |
|-----------|--------------|-----------------|---------|
| PRODUCE | NULL | NULL | 用户创作内容 ⚠️ |

**重要**: PRODUCE场景的NULL值是正常的，代表创作行为本身！

## 🔄 生成富文本描述的映射

在 `generate_kling_RA_data.py` 中使用的映射逻辑：

```python
def get_behavior_description(behavior: dict, item_info: dict) -> str:
    event_type = behavior.get('event_type')
    behavior_type = behavior.get('behavior_type')
    behavior_subtype = behavior.get('behavior_subtype')
    
    # 1. PRODUCE场景（behavior_type和behavior_subtype都是null）
    if event_type == 'PRODUCE':
        action = 'created'
    
    # 2. OPERATE场景（根据behavior_subtype细分）
    elif behavior_type == 'OPERATE':
        if behavior_subtype == 'LIKE':
            action = 'liked'
        elif behavior_subtype == 'LARGE':
            action = 'clicked'  # ✅ 这才是点击
        elif behavior_subtype == 'COMMENT':
            action = 'commented on'
        # ... 其他子类型
    
    # 3. 播放场景
    elif behavior_type == 'VIDEO_PLAY_FINISH':
        action = 'finished watching'
    elif behavior_type == 'LONG_PLAY':
        action = 'watched for a long time'
    elif behavior_type == 'SHORT_PLAY':
        action = 'browsed'
    
    # 4. 默认
    else:
        action = 'interacted with'
    
    return action
```

## ⚠️ 常见错误

### ❌ 错误1: 把OPERATE当作点击

```python
# 错误写法
if behavior_type == 'OPERATE':
    action = 'clicked'  # 错误！会把LIKE、COMMENT等都当作点击
```

```python
# 正确写法
if behavior_type == 'OPERATE' and behavior_subtype == 'LARGE':
    action = 'clicked'  # 正确！只有LARGE才是点击
```

### ❌ 错误2: 过滤掉PRODUCE的null值

```python
# 错误写法
if not behavior_type or not behavior_subtype:
    continue  # 错误！会过滤掉所有PRODUCE行为
```

```python
# 正确写法
if event_type == 'PRODUCE':
    # PRODUCE场景下behavior_type和behavior_subtype为null是正常的
    action = 'created'
elif behavior_type == 'OPERATE':
    # 只在OPERATE场景才需要检查behavior_subtype
    ...
```

### ❌ 错误3: 忽略平台类型差异

```python
# 不够精确的写法
if behavior_type == 'OPERATE' and behavior_subtype == 'LARGE':
    action = 'clicked'
```

```python
# 更精确的写法（如果需要严格匹配SQL逻辑）
if behavior_type == 'OPERATE' and behavior_subtype == 'LARGE':
    platform = behavior.get('platform_type')
    element_action = behavior.get('element_action')
    
    is_click = False
    if platform == 'App':
        is_click = True
    elif platform == 'Web' and element_action == 'FANC_CARD':
        is_click = True
    
    if is_click:
        action = 'clicked'
```

## 📊 行为类型统计示例

运行数据生成脚本时会输出详细统计：

```
📈 事件类型分布:
  RECOMMEND   :   50,000 次
  SEARCH      :   30,000 次
  PRODUCE     :   20,000 次

📊 行为类型分布:
  OPERATE             :   40,000 次  (包含多种子类型)
  VIDEO_PLAY_FINISH   :   20,000 次
  LONG_PLAY           :   15,000 次
  SHORT_PLAY          :   20,000 次
  NULL                :   20,000 次  ⚠️ 全部来自PRODUCE

📝 操作子类型分布 (behavior_subtype):
  LIKE          :   15,000 次
  LARGE         :    8,000 次  ✅ 这些才是点击
  COMMENT       :    7,000 次
  SHARE         :    5,000 次
  UNLIKE        :    3,000 次
  SAME_STYLE    :    1,500 次
  REPORT        :      500 次
  NULL          :   60,000 次  (非OPERATE的场景)
```

## 🎯 最佳实践

1. **总是检查event_type**
   - PRODUCE场景特殊处理，不需要检查behavior_type和behavior_subtype

2. **OPERATE必须细分**
   - 不要直接使用OPERATE，必须查看behavior_subtype

3. **点击识别严格**
   - 只有 `OPERATE + LARGE` 是点击
   - 如需更严格，还要检查platform_type和element_action

4. **null值正常化**
   - PRODUCE场景的null值是预期的，不是数据质量问题

5. **保留上下文信息**
   - SEARCH场景保留element_query_content和query_cnt
   - 为富文本描述提供更多context

## 📚 相关文件

- `load_kling_data.py`: 数据提取SQL逻辑（第86-102行）
- `generate_kling_RA_data.py`: 行为类型映射实现（第21-80行）
- `README.md`: 完整数据处理流程说明
