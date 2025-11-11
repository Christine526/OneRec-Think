# Kling数据训练流程 - 后续步骤指南

## ✅ 已完成的工作

### 1. load_kling_data.py (已修改)

**主要改进**:
- ✓ 添加了详细的文档注释
- ✓ 在SQL中添加了ORDER BY子句，确保数据按用户和时间排序
- ✓ 使用TSV格式替代CSV，避免逗号和引号的干扰
- ✓ 添加了更清晰的输出提示信息

**使用方法**:
```bash
python load_kling_data.py
```

### 2. process_kling_data.py (已修改)

**主要改进**:
- ✓ 添加了详细的统计信息输出
- ✓ 支持行为类型分布统计（RECOMMEND/SEARCH/PRODUCE）
- ✓ 支持搜索场景统计（element_query_content）
- ✓ 添加了序列长度分布统计
- ✓ 更清晰的进度提示和格式化输出

**生成的三个元数据文件**:
1. `kling_items.json` - 物品元数据（title, description, categories, sid）
2. `kling_sequential.txt` - 用户行为序列（user_id + item_ids）
3. `kling_user_behaviors.json` - 用户行为详情（包含行为类型、搜索词等）

**使用方法**:
```bash
python process_kling_data.py
```

---

## 🎯 下一步：创建三个数据生成脚本

根据论文附录A.3.1，需要创建以下三个脚本：

### 脚本1: generate_kling_RA_data.py

**对应任务**: Interleaved User Persona Grounding (Alignment)

**核心思路**:

1. **读取数据**:
   - `kling_items.json` - 获取物品的title、categories、sid
   - `kling_sequential.txt` - 获取用户行为序列
   - `kling_user_behaviors.json` - 获取行为类型、搜索词等富文本信息

2. **生成富文本用户画像**:
   
   参考论文示例，需要生成类似这样的文本：
   
   ```
   # User Profile Narrative
   The user recently searched for "AI video generation" 3 times;
   
   # Like Behavior
   He recently liked video <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>, 
   titled "Amazing AI Art", its categories are "Image Creation > Material";
   
   # Comment Behavior
   He recently commented on video <|sid_begin|><s_a_4><s_b_5><s_c_6><|sid_end|>, 
   titled "Tutorial Video", a content about "Video Creation > Short Film";
   
   # Produce Behavior
   He recently created content with prompt "A beautiful landscape scene", 
   video <|sid_begin|><s_a_7><s_b_8><s_c_9><|sid_end|>;
   ```

3. **行为类型映射**:
   ```python
   # 根据kling_user_behaviors.json中的行为类型生成不同的描述
   behavior_templates = {
       'SEARCH': "The user recently searched for '{query}' {count} times",
       'LIKE': "liked video {sid}, titled '{title}', its categories are '{categories}'",
       'UNLIKE': "unliked video {sid}",
       'COMMENT': "commented on video {sid}, a content about '{categories}'",
       'SHARE': "shared video {sid}",
       'VIDEO_PLAY_FINISH': "finished watching video {sid}",
       'LONG_PLAY': "watched video {sid} for a long time",
       'PRODUCE': "created content with prompt '{description}', video {sid}",
   }
   ```

4. **数据分割**:
   - train: 使用前N-2个物品的行为生成描述，预测第N-1个物品
   - val: 使用前N-1个物品的行为生成描述，预测第N个物品
   - test: 使用所有N个物品的行为生成描述

5. **输出格式**:
   ```python
   {
       "user_id": "xxx",
       "description": "富文本用户画像...",
       "groundtruth": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>",
       "title": "预测物品的标题",
       "categories": "预测物品的类别"
   }
   ```

6. **参考现有脚本**: `/workspace/data/generate_RA_data.py`

---

### 脚本2: generate_kling_sid_prediction_data.py

**对应任务**: Sequential Preference Modeling (序列推荐)

**核心思路**:

1. **读取数据**:
   - `kling_items.json` - 获取物品的sid
   - `kling_sequential.txt` - 获取用户行为序列

2. **生成SID序列**:
   ```python
   # 将item_id序列转换为sid序列
   sid_sequence = []
   for item_id in item_ids:
       item_info = items_dict[item_id]
       sid_sequence.append(item_info['sid'])
   
   # 生成描述
   description = "The user has interacted with the following items: " + "; ".join(sid_sequence[:-1]) + ";"
   groundtruth = sid_sequence[-1]
   ```

3. **数据分割**:
   - train: 移除序列尾部2个物品
   - val: 移除序列尾部1个物品
   - test: 使用完整序列

4. **输出格式**:
   ```python
   {
       "user_id": "xxx",
       "description": "The user has interacted with: <|sid_begin|>...<|sid_end|>; <|sid_begin|>...<|sid_end|>;",
       "groundtruth": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>"
   }
   ```

5. **参考现有脚本**: `/workspace/data/generate_sid_prediction_data.py`

**注意**: 这个脚本相对简单，几乎可以直接复用现有Beauty数据的脚本

---

### 脚本3: generate_kling_training_data.py

**对应任务**: Itemic Dense Captioning (物品描述生成)

**核心思路**:

1. **读取数据**:
   - `kling_items.json` - 获取物品的sid、title、categories
   - `kling_sequential.txt` - 获取用户行为序列

2. **生成物品描述序列**:
   ```python
   # 将item_id序列转换为包含title和categories的描述
   item_descriptions = []
   for item_id in item_ids:
       item_info = items_dict[item_id]
       sid = item_info['sid']
       title = item_info['title']
       categories = item_info['categories']
       
       desc = f'{sid}, its title is "{title}", its categories are "{categories}"'
       item_descriptions.append(desc)
   
   # 生成最终描述
   description = "The user has interacted with the following items: " + "; ".join(item_descriptions) + ";"
   ```

3. **数据分割**:
   - train: 使用前N-2个物品
   - val: 使用前N-1个物品
   - test: 使用所有N个物品

4. **输出格式**:
   ```python
   {
       "user_id": "xxx",
       "description": "The user has interacted with: <|sid_begin|>...<|sid_end|>, its title is 'xxx', its categories are 'xxx'; ..."
   }
   ```

5. **参考现有脚本**: `/workspace/data/generate_training_data.py`

**注意**: 这个脚本也相对简单，主要是组合sid、title、categories

---

## 📝 实现要点总结

### 1. 充分利用kling_user_behaviors.json

这是Kling数据相比Beauty数据的最大优势：
- Beauty数据只有"购买"这一种行为
- Kling数据有多种行为类型（搜索、点赞、评论、生产等）

在生成Alignment数据时，要充分利用这些丰富的行为信息来构建用户画像。

### 2. 搜索场景的特殊处理

```python
# 处理搜索行为
search_behaviors = []
for behavior in user_behaviors:
    if behavior['event_type'] == 'SEARCH' and behavior['element_query_content']:
        query = behavior['element_query_content']
        count = behavior.get('query_cnt', 1)
        search_behaviors.append(f'searched for "{query}" {count} times')

# 合并到用户画像
if search_behaviors:
    description += "The user recently " + "; ".join(search_behaviors) + "; "
```

### 3. 生产行为的特殊处理

```python
# 处理PRODUCE行为
if behavior['event_type'] == 'PRODUCE':
    item_info = items_dict[behavior['item_id']]
    prompt = item_info['description']  # prompt字段
    sid = item_info['sid']
    description += f'created content with prompt "{prompt[:100]}...", video {sid}; '
```

### 4. 类别层级的使用

Kling的categories已经是层级结构：
- "Video Creation > Short Film"
- "Image Creation > Material"

可以直接使用，无需额外处理。

### 5. SID维度适配

Kling数据的SID是3维，在后续训练时需要注意：
- 词表扩展时只需要s_a、s_b、s_c三个维度
- 模型推理时也只需要预测3维

---

## 🔄 完整工作流程

```
步骤1: 数据获取
└─> python load_kling_data.py
    └─> 输出: {p_date}.tsv

步骤2: 生成元数据
└─> python process_kling_data.py
    └─> 输出: kling_items.json
    └─> 输出: kling_sequential.txt
    └─> 输出: kling_user_behaviors.json

步骤3: 生成Alignment训练数据（待实现）
└─> python generate_kling_RA_data.py
    └─> 输出: training_RA_train.parquet
    └─> 输出: training_RA_val.parquet
    └─> 输出: training_RA_test.parquet

步骤4: 生成SID预测训练数据（待实现）
└─> python generate_kling_sid_prediction_data.py
    └─> 输出: training_prediction_sid_data_train.parquet
    └─> 输出: training_prediction_sid_data_val.parquet
    └─> 输出: training_prediction_sid_data_test.parquet

步骤5: 生成Dense Captioning训练数据（待实现）
└─> python generate_kling_training_data.py
    └─> 输出: training_align_data_train.parquet
    └─> 输出: training_align_data_val.parquet
    └─> 输出: training_align_data_test.parquet
```

---

## 🎨 数据示例对比

### Beauty数据（简单）:
```
"The user has purchased the following items: 
<|sid_begin|><s_a_1><s_b_2><s_c_3><s_d_4><|sid_end|>, its title is 'Hair Care Product', its categories are 'Beauty > Hair Care';
<|sid_begin|><s_a_5><s_b_6><s_c_7><s_d_8><|sid_end|>, its title is 'Makeup Kit', its categories are 'Beauty > Makeup';"
```

### Kling数据（丰富）:
```
"# User Profile Narrative
The user recently searched for 'AI video generation' 3 times; searched for 'text to video' 2 times;

# Interaction Behaviors
He recently liked video <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>, titled 'Amazing AI Art', its categories are 'Image Creation > Material';
He commented on video <|sid_begin|><s_a_4><s_b_5><s_c_6><|sid_end|>, a tutorial about 'Video Creation > Short Film';
He created content with prompt 'A beautiful landscape with mountains and rivers', video <|sid_begin|><s_a_7><s_b_8><s_c_9><|sid_end|>;
He finished watching video <|sid_begin|><s_a_10><s_b_11><s_c_12><|sid_end|>, titled 'Tutorial: How to use AI';"
```

Kling数据的用户画像更加丰富，包含：
- 搜索意图
- 多种行为类型
- 创作行为
- 观看时长

这些信息可以帮助模型更好地理解用户偏好。

---

## 💡 建议

1. **先实现脚本2和3**：它们相对简单，可以直接参考现有Beauty数据的脚本

2. **重点设计脚本1**：Alignment数据是最复杂的，需要仔细设计用户画像的生成逻辑

3. **保持格式一致性**：确保生成的数据格式与现有Beauty数据兼容，这样可以复用训练脚本

4. **增量开发**：先生成基本版本，验证格式正确后，再逐步增强富文本的质量

5. **数据验证**：生成数据后，务必检查：
   - SID格式是否正确
   - 文本长度是否合理
   - train/val/test分割是否正确
   - 是否有缺失值

---

## 📚 相关文档

- [README.md](README.md) - 整体流程和元数据格式说明
- `/workspace/data/` - Beauty数据的生成脚本参考
- `/workspace/OneRec-Think.pdf` - 论文原文
