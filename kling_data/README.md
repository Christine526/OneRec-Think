# Kling数据处理指南

本目录包含将Kling数据转换为OneRec-Think训练格式的脚本。

## 📋 文件说明

### 1. 数据获取脚本

- **`load_kling_data.py`**: 从Hive读取Kling数据并导出为CSV
  - ⚠️ 需要内部Hive环境和权限
  - 依赖: `kmlutils`, `pyspark`, `dask`
  - 输出: `kling_data.csv` 或 `kling_data.tsv`

### 2. 数据处理脚本

- **`process_kling_data_fixed.py`** ✅ **推荐使用（修正版）**
  - 修正了原版的SID维度问题（3维→4维）
  - 使用content_type作为第4维
  - 生成OneRec-Think兼容的数据格式

- **`process_kling_data.py`** ❌ **已弃用**
  - 原版脚本，存在SID维度错误
  - 仅供参考，请使用修正版

## 🚀 快速开始

### 步骤1: 准备数据文件

**选项A: 从Hive导出（内部环境）**

```bash
cd /workspace/kling_data
python load_kling_data.py
```

这将生成 `kling_data.csv` 或 `kling_data.tsv` 文件。

**选项B: 使用已有的CSV文件**

将你的Kling数据CSV文件放到此目录，命名为以下之一：
- `kling_data.tsv` (制表符分隔，推荐)
- `kling_data.csv` (逗号分隔)
- `kling_data_fixed.tsv`
- `kling_data_fixed.csv`

⚠️ **重要**: 建议使用制表符(`\t`)作为分隔符，避免CSV解析问题。

### 步骤2: 处理数据

```bash
cd /workspace/kling_data
python process_kling_data_fixed.py
```

**输出文件**:
- `kling_items.json` - 物品元数据（4维SID格式）
- `kling_sequential.txt` - 用户序列
- `kling_user_behaviors.json` - 用户行为详情（可选）

### 步骤3: 生成训练数据

```bash
cd /workspace/data

# 生成Alignment训练数据（Stage 1）
python generate_training_data_kling.py

# 生成SID预测训练数据（Stage 2）
python generate_sid_prediction_data_kling.py

# 生成RA训练数据（可选）
python generate_RA_data_kling.py
```

### 步骤4: 开始训练

```bash
cd /workspace/train

# Stage 1: Itemix Alignment训练
bash run_training_stage1.sh

# Stage 2: Sequential Recommendation训练
bash run_training_stage2.sh
```

## 📊 数据格式说明

### 输入数据格式（CSV/TSV）

CSV文件应包含以下列：

```
user_id, kling_photo_id, kling_photo_type, event_type, behavior_type, 
behavior_subtype, time_stamp, content_type, prompt, title, introduction, 
element_query_content, query_cnt, semantic_id
```

**关键字段**:
- `semantic_id`: 3维语义ID，格式如 `[69, 142, 246]`
- `content_type`: 内容类型 (0=图片+视频, 1=图片, 2=视频)
- `prompt`: 生成提示词（作为description）
- `title`: 标题

### 输出数据格式

#### 1. kling_items.json

```json
{
  "item_id": {
    "title": "标题",
    "description": "描述（prompt字段）",
    "categories": "Image Creation > Material",
    "sid": "<|sid_begin|><s_a_69><s_b_142><s_c_246><s_d_0><|sid_end|>"
  }
}
```

**关键点**:
- ✅ SID格式为4维 (`s_a`, `s_b`, `s_c`, `s_d`)
- 第4维 `s_d` 使用 `content_type` 值
- 所有值在 [0, 255] 范围内

#### 2. kling_sequential.txt

```
user_id item_id1 item_id2 item_id3 ...
```

每行代表一个用户的物品交互序列，按时间顺序排列。

#### 3. kling_user_behaviors.json

```json
{
  "user_id": [
    {
      "item_id": "123",
      "event_type": "RECOMMEND",
      "behavior_type": "CLICK",
      "timestamp": "2024-11-05 10:30:00",
      ...
    }
  ]
}
```

包含每个用户的详细行为信息。

## ⚠️ 常见问题

### Q1: 为什么需要4维SID？

**答**: OneRec-Think模型的词表扩展使用了4维SID格式：

```python
# 来自 basemodel/expand_vocab.py
for prefix in ["s_a", "s_b", "s_c", "s_d"]:  # 4个维度
    for idx in range(max_range):
        special_tokens.append(f"<{prefix}_{idx}>")
```

如果使用3维SID，模型将无法识别这些token。

### Q2: 第4维使用什么值？

**答**: 修正版脚本使用 `content_type` 作为第4维：
- 0: 图片+视频
- 1: 图片
- 2: 视频

这样既满足格式要求，又保留了业务语义。

### Q3: CSV读取失败怎么办？

**答**: 
1. **推荐**: 使用制表符(`\t`)导出数据，避免字段中逗号干扰
2. 检查文件编码是否为 UTF-8
3. 查看脚本尝试的多种读取方式

### Q4: 如何验证SID格式？

**答**: 运行处理脚本后，检查输出：

```
🔍 SID格式验证（前3个样例）:
  ✅ [1] <|sid_begin|><s_a_69><s_b_142><s_c_246><s_d_0><|sid_end|>
  ✅ [2] <|sid_begin|><s_a_120><s_b_88><s_c_199><s_d_1><|sid_end|>
  ✅ [3] <|sid_begin|><s_a_45><s_b_201><s_c_33><s_d_2><|sid_end|>
```

所有SID应该都有4个维度（`s_a`, `s_b`, `s_c`, `s_d`）。

### Q5: 训练数据生成失败？

**答**: 检查：
1. 是否成功生成了 `kling_items.json` 和 `kling_sequential.txt`
2. 文件路径是否正确
3. 检查脚本的输入文件路径设置

## 📝 数据统计示例

运行处理脚本后，你会看到类似的统计信息：

```
📌 行为类型分布:
  RECOMMEND   : 15000 条 (60.0%)
  SEARCH      :  5000 条 (20.0%)
  PRODUCE     :  5000 条 (20.0%)

📦 物品去重:
  去重前: 25000 条记录
  去重后: 8000 个唯一物品

📊 用户统计:
  总用户数: 1500
  序列长度 >= 3 的用户: 1200
  平均序列长度: 16.67
  中位序列长度: 12
  最长序列: 256
```

## 🔗 相关文档

- **详细分析**: `/workspace/kling_data_analysis.md`
- **OneRec-Think论文**: `/workspace/OneRec-Think.pdf`
- **训练脚本**: `/workspace/train/`
- **数据生成脚本**: `/workspace/data/generate_*_data_kling.py`

## 📧 技术支持

如有问题，请：
1. 查看 `/workspace/kling_data_analysis.md` 获取详细说明
2. 检查脚本输出的错误信息
3. 验证数据格式是否正确

---

**最后更新**: 2025-11-11
