# Kling数据处理流程

本目录包含将Kling数据转换为OneRec-Think训练格式的完整流程。

## 📋 目录结构

```
kling_data/
├── load_kling_data.py                      # 步骤1: 从Hive读取数据
├── process_kling_data.py                   # 步骤2: 生成元数据
├── generate_kling_RA_data.py               # 步骤3.1: 生成富文本用户画像数据
├── generate_kling_sid_prediction_data.py   # 步骤3.2: 生成SID序列预测数据
├── generate_kling_training_data.py         # 步骤3.3: 生成物品描述数据
├── run_all_generation.sh                   # 一键运行所有数据生成脚本
└── README.md                               # 本文档
```

## 🚀 使用流程

### 步骤1: 从Hive获取原始数据

运行 `load_kling_data.py` 从Hive读取Kling数据并保存为TSV文件：

```bash
python load_kling_data.py
```

**输出文件**: `{p_date}.tsv` (例如：20251105.tsv)

**说明**:
- 自动读取前一天的数据
- 包含正向行为过滤（点赞、评论、转发、完播等强互动）
- 保存为TSV格式（制表符分隔），避免CSV中逗号和引号的干扰

### 步骤2: 生成训练元数据

运行 `process_kling_data.py` 处理TSV文件，生成三个核心元数据文件：

```bash
python process_kling_data.py
```

**输出文件**:
1. `kling_items.json` - 物品元数据
2. `kling_sequential.txt` - 用户行为序列
3. `kling_user_behaviors.json` - 用户行为详情

### 步骤3: 生成训练数据

#### 方法1: 一键运行所有脚本（推荐）

```bash
cd kling_data
bash run_all_generation.sh
```

这将自动运行以下3个数据生成脚本，并在最后显示所有输出文件。

#### 方法2: 分别运行各个脚本

如果需要单独运行某个脚本：

**3.1 生成富文本用户画像数据 (Interleaved User Persona Grounding)**

```bash
cd kling_data
python generate_kling_RA_data.py
```

**输出文件**:
- `training_RA_train.parquet`
- `training_RA_val.parquet`
- `training_RA_test.parquet`

**3.2 生成SID序列预测数据 (Sequential Preference Modeling)**

```bash
python generate_kling_sid_prediction_data.py
```

**输出文件**:
- `training_prediction_sid_data_train.parquet`
- `training_prediction_sid_data_val.parquet`
- `training_prediction_sid_data_test.parquet`

**3.3 生成物品描述数据 (Itemic Dense Captioning)**

```bash
python generate_kling_training_data.py
```

**输出文件**:
- `training_align_data_train.parquet`
- `training_align_data_val.parquet`
- `training_align_data_test.parquet`

## 📦 元数据格式说明

### 1. kling_items.json - 物品元数据

类似Beauty.pretrain.json，包含物品的基本信息：

```json
{
  "item_id": {
    "title": "物品标题",
    "description": "物品描述(来自prompt)",
    "categories": "Image Creation > Material",
    "sid": "<|sid_begin|><s_a_69><s_b_142><s_c_246><|sid_end|>"
  }
}
```

**注意**: 
- Kling的semantic_id是3维 (s_a, s_b, s_c)
- Beauty数据的semantic_id是4维 (s_a, s_b, s_c, s_d)

### 2. kling_sequential.txt - 用户序列

类似sequential_data_processed.txt，每行一个用户的行为序列：

```
user_id item_id1 item_id2 item_id3 ...
```

### 3. kling_user_behaviors.json - 用户行为详情

包含每个交互的详细信息（用于生成富文本Alignment数据）：

```json
{
  "user_id": [
    {
      "item_id": "xxx",
      "event_type": "RECOMMEND/SEARCH/PRODUCE",
      "behavior_type": "OPERATE/VIDEO_PLAY_FINISH/LONG_PLAY/SHORT_PLAY",
      "behavior_subtype": "LIKE/COMMENT/SHARE/LARGE...",
      "timestamp": "...",
      "element_query_content": "搜索词",
      "query_cnt": 5
    }
  ]
}
```

## 📚 Kling数据行为类型结构

### event_type（事件类型）

- **RECOMMEND**: 推荐场景
- **SEARCH**: 搜索场景
- **PRODUCE**: 生产/创作场景

### behavior_type（行为类型）

仅在RECOMMEND和SEARCH场景下有值，PRODUCE场景下为null：

- **OPERATE**: 操作行为（需看behavior_subtype细分）
- **VIDEO_PLAY_FINISH**: 完播
- **LONG_PLAY**: 长播放
- **SHORT_PLAY**: 短播放

### behavior_subtype（行为子类型）

仅当behavior_type='OPERATE'时才有值：

- **LIKE**: 点赞
- **UNLIKE**: 取消点赞
- **COMMENT**: 评论
- **SHARE**: 转发/分享
- **SAME_STYLE**: 一键同款
- **REPORT**: 举报
- **LARGE**: 放大/点击 ✅ **这才是点击行为**

### 行为类型映射表

在生成富文本描述时，使用以下映射：

| 行为组合 | 英文描述 | 中文含义 |
|---------|---------|---------|
| PRODUCE (event_type) | created | 创作 |
| OPERATE + LIKE | liked | 点赞 |
| OPERATE + UNLIKE | unliked | 取消点赞 |
| OPERATE + COMMENT | commented on | 评论 |
| OPERATE + SHARE | shared | 分享 |
| OPERATE + SAME_STYLE | used same style for | 一键同款 |
| OPERATE + REPORT | reported | 举报 |
| OPERATE + LARGE | clicked | 点击 ✅ |
| VIDEO_PLAY_FINISH | finished watching | 完播 |
| LONG_PLAY | watched for a long time | 长播放 |
| SHORT_PLAY | browsed | 浏览 |

**重要**：
- ✅ `OPERATE + LARGE` 才是点击行为
- ❌ 不要把 `OPERATE` 本身当作点击
- ℹ️ PRODUCE场景下，behavior_type和behavior_subtype都是null

## 📚 训练数据格式说明

根据论文附录A.3.1，生成了三类训练数据：

### 1️⃣ Interleaved User Persona Grounding (Alignment)

**目标**: 将用户画像与物品交织，生成富文本描述

**脚本**: `generate_kling_RA_data.py` ✅

**输入文件**:
- `kling_items.json` (物品元数据)
- `kling_sequential.txt` (用户序列)
- `kling_user_behaviors.json` (用户行为详情)

**输出文件**:
- `training_RA_train.parquet`
- `training_RA_val.parquet`
- `training_RA_test.parquet`

**数据格式示例**:
```json
{
  "user_id": "xxx",
  "description": "The user has liked item <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>, its title is 'xxx', its categories are 'Video Creation' (from recommendations); clicked item <|sid_begin|><s_a_4><s_b_5><s_c_6><|sid_end|>, its title is 'yyy', its categories are 'Image Creation' (searched for 'AI video' 3 times);",
  "groundtruth": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>",
  "title": "预测物品的标题",
  "categories": "预测物品的类别"
}
```

**特点**:
- 包含丰富的行为类型信息 (liked, commented on, watched, clicked, etc.)
- 搜索场景包含 `element_query_content` 和 `query_cnt`
- 生产行为(PRODUCE)标注为 "created"
- 推荐场景标注为 "from recommendations"

---

### 2️⃣ Sequential Preference Modeling (SID预测)

**目标**: 预测用户下一个交互的物品SID

**脚本**: `generate_kling_sid_prediction_data.py` ✅

**输入文件**:
- `kling_items.json` (物品元数据)
- `kling_sequential.txt` (用户序列)

**输出文件**:
- `training_prediction_sid_data_train.parquet`
- `training_prediction_sid_data_val.parquet`
- `training_prediction_sid_data_test.parquet`

**数据格式示例**:
```json
{
  "user_id": "xxx",
  "description": "The user has interacted with the following items: <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>; <|sid_begin|><s_a_4><s_b_5><s_c_6><|sid_end|>; ...",
  "groundtruth": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>"
}
```

**特点**:
- 只包含SID序列，不包含行为类型
- 简洁的序列建模格式
- train/val/test通过移除尾部不同数量的物品生成

---

### 3️⃣ Itemic Dense Captioning (物品描述生成)

**目标**: 生成物品的文本描述

**脚本**: `generate_kling_training_data.py` ✅

**输入文件**:
- `kling_items.json` (物品元数据)
- `kling_sequential.txt` (用户序列)

**输出文件**:
- `training_align_data_train.parquet`
- `training_align_data_val.parquet`
- `training_align_data_test.parquet`

**数据格式示例**:
```json
{
  "user_id": "xxx",
  "description": "The user has interacted with the following items: <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>, its title is 'xxx', its categories are 'Video Creation > Material'; <|sid_begin|><s_a_4><s_b_5><s_c_6><|sid_end|>, its title is 'yyy', its categories are 'Image Creation';"
}
```

**特点**:
- 包含SID、title和categories信息
- 用于预训练阶段的物品描述对齐
- 不包含行为类型，统一使用 "interacted with"

## 🎯 实现建议

### 针对Kling数据的特殊处理

1. **搜索场景的富文本生成**:
   - 利用 `element_query_content` 生成搜索行为描述
   - 例如: "searched for 'AI video generation' 5 times"

2. **生产行为(PRODUCE)的标注**:
   - 例如: "created item ..."
   - PRODUCE场景下behavior_type和behavior_subtype都是null

3. **点击行为的正确识别**:
   - ✅ 只有 `behavior_type='OPERATE' AND behavior_subtype='LARGE'` 才是点击
   - 需要额外检查platform_type和element_action（详见load_kling_data.py第92-102行）

4. **类别层级**:
   - Kling的categories已经是层级结构
   - 例如: "Video Creation > Short Film"

## ⚠️ 注意事项

1. **SID维度差异**:
   - Kling数据: 3维 (s_a, s_b, s_c)
   - Beauty数据: 4维 (s_a, s_b, s_c, s_d)
   - 需要在词表扩展时注意这个差异

2. **文本长度限制**:
   - prompt字段可能很长，已限制为1000字符
   - QWen模型的max_length=4096 tokens

3. **数据分割**:
   - train: 移除序列尾部2个物品
   - val: 移除序列尾部1个物品
   - test: 使用完整序列

4. **最小序列长度**:
   - 默认要求用户至少有3次交互
   - 否则无法进行train/val/test分割

5. **行为类型null值处理**:
   - PRODUCE场景下behavior_type和behavior_subtype为null是正常的
   - 不要当作缺失数据过滤掉

## 📊 数据统计示例

运行完成后会输出类似统计信息：

```
📈 事件类型分布:
  RECOMMEND   : 50,000 次 (50.0%)
  SEARCH      : 30,000 次 (30.0%)
  PRODUCE     : 20,000 次 (20.0%)

📊 行为类型分布:
  OPERATE             : 40,000 次
  VIDEO_PLAY_FINISH   : 20,000 次
  LONG_PLAY           : 15,000 次
  SHORT_PLAY          : 20,000 次
  NULL                : 20,000 次 (PRODUCE场景)

📝 操作子类型分布:
  LIKE          : 15,000 次
  LARGE         :  8,000 次 ✅ 点击
  COMMENT       :  7,000 次
  SHARE         :  5,000 次
  UNLIKE        :  3,000 次
  SAME_STYLE    :  1,500 次
  REPORT        :    500 次
  NULL          : 60,000 次 (非OPERATE场景)

🔍 搜索场景统计:
  总搜索事件: 30,000 次
  包含查询词: 25,000 次 (83.3%)
  生产事件: 20,000 次

📊 序列长度分布:
  1-2   :    500 用户 ( 5.0%)
  3-4   :  2,000 用户 (20.0%)
  5-9   :  3,500 用户 (35.0%)
  10-19 :  2,500 用户 (25.0%)
  20-49 :  1,000 用户 (10.0%)
  50+   :    500 用户 ( 5.0%)
```

## 🔗 相关文件

参考现有Beauty数据的生成脚本：
- `/workspace/data/generate_RA_data.py`
- `/workspace/data/generate_sid_prediction_data.py`
- `/workspace/data/generate_training_data.py`

这些脚本可以作为实现Kling数据生成的模板。
