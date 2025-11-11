# Kling数据接入OneRec-Think分析报告

## 一、发现的主要问题

### 1. SID维度错误 ⚠️ **严重**

**位置**: `process_kling_data.py` 第35-50行

**问题描述**:
- 当前实现: 使用3维semantic_id `<s_a_X><s_b_X><s_c_X>` (3个维度)
- OneRec-Think要求: 使用4维semantic_id `<s_a_X><s_b_X><s_c_X><s_d_X>` (4个维度)

**证据**:
```python
# 来自 basemodel/expand_vocab.py (17-19行)
for prefix in ["s_a", "s_b", "s_c", "s_d"]:  # 4个维度
    for idx in range(max_range):
        special_tokens.append(f"<{prefix}_{idx}>")

# 来自 test/precompute_global_trie.py (12行)
sid_pattern = r'<\|sid_begin\|><s_a_\d+><s_b_\d+><s_c_\d+><s_d_\d+><\|sid_end\|>'  # 4维
```

**影响**:
- 生成的SID格式与模型词表不匹配
- 训练时会导致token无法识别
- 测试推理时trie树构建失败

---

### 2. 目录结构问题

**问题**: `kling_data/` 目录不存在，但两个脚本都假定该目录存在

---

### 3. load_kling_data.py中的环境依赖

**位置**: `load_kling_data.py`

**问题**:
- 依赖内部的 `kmlutils` 库（不在标准环境中）
- 需要Hive环境和特定的账户权限
- 代码中SQL硬编码日期 `p_date = '20251105'`（第68行）

**建议**: 这个脚本仅在有Hive访问权限的内部环境使用，导出CSV后使用process_kling_data.py处理

---

### 4. Semantic ID解析问题

**位置**: `process_kling_data.py` 第20-32行

**当前实现**:
```python
def parse_semantic_id(semantic_id_str):
    # 解析: ' [69,142,246] ' -> [69, 142, 246]  # 3个值
```

**问题**: Kling数据的semantic_id只有3个维度，但OneRec-Think需要4个维度

**可能的解决方案**:
1. **方案A**: 添加一个固定的第4维（如0或特殊值）
2. **方案B**: 使用数据中的其他字段补充第4维（如content_type）
3. **方案C**: 修改模型配置支持变长SID（需要大量改动，不推荐）

---

## 二、OneRec-Think数据接口规范

### 1. 物品元数据JSON格式

**文件**: `Beauty.pretrain.json`

**格式**:
```json
{
  "item_id": {
    "title": "商品标题",
    "description": "商品描述",
    "categories": "分类1 > 分类2 > 分类3",
    "sid": "<|sid_begin|><s_a_99><s_b_19><s_c_220><s_d_204><|sid_end|>"
  }
}
```

**关键要求**:
- `sid` 必须是4维格式
- `title`, `description`, `categories` 都是文本字段
- 所有字段必须存在

---

### 2. 用户序列文件格式

**文件**: `sequential_data_processed.txt`

**格式**:
```
user_id item_id1 item_id2 item_id3 ...
```

**示例**:
```
1 1 2 3 4 5 6 7 8
2 9 10 11 12 13 14 15 16 17 18 19 20
```

**要求**:
- 每行一个用户
- 空格分隔
- 按时间顺序排列item_id

---

### 3. 训练数据生成流程

OneRec-Think需要生成3种训练数据：

#### 3.1 Alignment训练数据 (Stage 1)

**脚本**: `data/generate_training_data.py`

**输入**:
- `Beauty.pretrain.json` (物品元数据)
- `sequential_data_processed.txt` (用户序列)

**输出**:
- `training_align_data_train.parquet`
- `training_align_data_val.parquet`
- `training_align_data_test.parquet`

**数据格式**:
```python
{
    'user_id': '1',
    'description': 'The user has purchased the following items: <|sid_begin|><s_a_99><s_b_19><s_c_220><s_d_204><|sid_end|>, its title is "...", its categories are "..."; ...'
}
```

**用途**: 训练模型理解物品的SID、标题和类别之间的映射关系（Itemix Alignment）

---

#### 3.2 SID预测数据 (Stage 2)

**脚本**: `data/generate_sid_prediction_data.py`

**输入**: 同上

**输出**:
- `training_prediction_sid_data_train.parquet`
- `training_prediction_sid_data_val.parquet`
- `training_prediction_sid_data_test.parquet`

**数据格式**:
```python
{
    'user_id': '1',
    'description': 'The user has purchased the following items: <|sid_begin|>...<|sid_end|>; ...',
    'groundtruth': '<|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|>'
}
```

**训练格式**:
```
<|im_start|>system
You are a professional recommendation expert...<|im_end|>
<|im_start|>user
{description}<|im_end|>
<|im_start|>assistant
<think>

</think>
{groundtruth}<|im_end|>
```

**用途**: 训练模型进行序列推荐，预测下一个物品的SID

---

#### 3.3 RA (Retrieve & Align) 数据 (可选)

**脚本**: `data/generate_RA_data.py`

**用途**: 同时包含SID、title和categories，用于更丰富的上下文训练

---

## 三、Kling数据特点分析

### 数据字段

从`load_kling_data.py`可以看出Kling数据包含：

```python
columns = [
    'user_id',              # 用户ID
    'kling_photo_id',       # 物品ID
    'kling_photo_type',     # 物品类型: 1=素材, 2=短片
    'event_type',           # 行为类型: RECOMMEND/SEARCH/PRODUCE
    'behavior_type',        # 行为类型
    'behavior_subtype',     # 行为子类型
    'time_stamp',           # 时间戳
    'content_type',         # 内容类型: 0=图片+视频, 1=图片, 2=视频
    'prompt',               # 生成提示词（可作为description）
    'title',                # 标题
    'introduction',         # 介绍
    'element_query_content', # 搜索查询词
    'query_cnt',            # 搜索次数
    'semantic_id'           # 语义ID: [a, b, c] 格式 (3维)
]
```

### 行为类型统计

- **RECOMMEND**: 推荐场景
- **SEARCH**: 搜索场景（可能包含element_query_content）
- **PRODUCE**: 生产场景（用户创作内容）

### 与Beauty数据集的差异

| 维度 | Beauty数据集 | Kling数据集 | 解决方案 |
|-----|-------------|------------|---------|
| semantic_id维度 | 4维 | 3维 | 需要补充第4维 |
| 类别信息 | 商品类别 | content_type + photo_type | 映射到类别格式 |
| 描述信息 | 商品描述 | prompt字段 | 直接使用 |
| 标题 | 商品标题 | title/introduction | 优先title |
| 行为类型 | 单一购买行为 | 多种行为类型 | 需要过滤或区分 |

---

## 四、修正方案

### 方案：补充第4维semantic_id

**理由**:
- 最小化改动
- 保留原有的3维信息
- 使用content_type作为第4维有业务意义

**实现**:
```python
def format_semantic_id_to_sid(semantic_id_array, content_type=0):
    """
    将3维semantic_id扩展为4维SID格式
    例如: [69, 142, 246] + content_type=0 -> 
         <|sid_begin|><s_a_69><s_b_142><s_c_246><s_d_0><|sid_end|>
    """
    if not semantic_id_array or len(semantic_id_array) < 3:
        return None
    
    # 取前3个值
    a, b, c = semantic_id_array[0:3]
    
    # 第4维使用content_type (0/1/2)
    d = int(content_type) if pd.notna(content_type) else 0
    
    sid = f'<|sid_begin|><s_a_{a}><s_b_{b}><s_c_{c}><s_d_{d}><|sid_end|>'
    return sid
```

**优点**:
- content_type有明确业务含义（图片/视频/混合）
- 可以区分不同内容类型的物品
- 符合OneRec-Think的4维格式要求

---

## 五、修正后的完整流程

### 步骤1: 从Hive导出数据 (可选)

```bash
# 在有Hive权限的环境执行
cd kling_data
python load_kling_data.py  # 生成 kling_data.csv 或 kling_data.tsv
```

### 步骤2: 处理Kling数据

```bash
cd kling_data
python process_kling_data.py  # 生成3个文件
```

**输出**:
- `kling_items.json` (物品元数据，4维SID)
- `kling_sequential.txt` (用户序列)
- `kling_user_behaviors.json` (行为详情，可选)

### 步骤3: 生成训练数据

```bash
cd /workspace/data

# 3.1 生成Alignment数据（Stage 1）
python generate_training_data_kling.py

# 3.2 生成SID预测数据（Stage 2）
python generate_sid_prediction_data_kling.py

# 3.3 生成RA数据（可选）
python generate_RA_data_kling.py
```

### 步骤4: 训练模型

```bash
cd /workspace/train

# Stage 1: Alignment训练
bash run_training_stage1.sh

# Stage 2: SID预测训练
bash run_training_stage2.sh
```

---

## 六、需要创建/修改的文件

### 需要修改的文件

1. ✅ `kling_data/process_kling_data.py` - 修正SID维度问题
2. ✅ `kling_data/load_kling_data.py` - 添加注释和使用说明

### 需要创建的文件

1. ✅ `data/generate_training_data_kling.py` - Kling版本的Alignment数据生成
2. ✅ `data/generate_sid_prediction_data_kling.py` - Kling版本的SID预测数据生成
3. ✅ `data/generate_RA_data_kling.py` - Kling版本的RA数据生成
4. ✅ `kling_data/README.md` - Kling数据处理说明

---

## 七、验证检查清单

训练前必须验证：

- [ ] SID格式正确: `<|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|>`
- [ ] 所有SID的a,b,c,d值都在[0, 255]范围内
- [ ] JSON文件中所有item都有title、description、categories、sid字段
- [ ] sequential文件格式正确，user_id和item_id用空格分隔
- [ ] 生成的parquet文件可以正常读取
- [ ] parquet文件的列名与训练脚本期望的一致

---

**总结**: 主要问题是SID维度不匹配（3维 vs 4维）。建议使用content_type作为第4维来补充，这样既能满足模型要求，又能保留业务语义。
