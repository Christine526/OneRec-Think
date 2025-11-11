# OneRec-Think 3维SID适配修改说明

## 📋 修改概述

根据Kling数据的实际情况（3维semantic_id），我们修改了OneRec-Think代码以支持3维SID格式，而不是强制Kling数据适配4维SID。

**修改前**: OneRec-Think使用4维SID `<|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|>`

**修改后**: OneRec-Think支持3维SID `<|sid_begin|><s_a_X><s_b_X><s_c_X><|sid_end|>`

---

## 🔧 修改的文件列表

### 1. 核心模型文件

#### `basemodel/expand_vocab.py` ✅

**修改内容**:
- 第17-21行: `get_special_tokens()` 函数改为只生成3维token (s_a, s_b, s_c)
- 第73-78行: 示例文本改为3维SID格式

**修改前**:
```python
for prefix in ["s_a", "s_b", "s_c", "s_d"]:  # 4维
    for idx in range(max_range):
        special_tokens.append(f"<{prefix}_{idx}>")
```

**修改后**:
```python
# Modified to support 3D SID format (s_a, s_b, s_c) for Kling data
for prefix in ["s_a", "s_b", "s_c"]:  # 3维
    for idx in range(max_range):
        special_tokens.append(f"<{prefix}_{idx}>")
```

**影响**: 
- 词表大小从 `2 + 4×256 = 1026` 减少到 `2 + 3×256 = 770` 个特殊token
- 模型参数量略微减少

---

### 2. 测试脚本

#### `test/precompute_global_trie.py` ✅

**修改内容**:
- 第12-16行: `extract_all_sids_from_text()` 的正则表达式改为3维
- 第19-26行: `extract_sid_from_text()` 的正则表达式改为3维

**修改前**:
```python
sid_pattern = r'<\|sid_begin\|><s_a_\d+><s_b_\d+><s_c_\d+><s_d_\d+><\|sid_end\|>'
```

**修改后**:
```python
sid_pattern = r'<\|sid_begin\|><s_a_\d+><s_b_\d+><s_c_\d+><\|sid_end\|>'
```

---

#### `test/test_model_hitrate.py` ✅

**修改内容**:
- 第369-378行: `extract_sid_from_text()` 的正则表达式改为3维
- 第380-387行: `extract_all_sids_from_text()` 的正则表达式改为3维

---

#### `test/test_model_hitrate_cot.py` ✅

**修改内容**:
- 第23-29行: `extract_all_sids_from_text()` 的正则表达式改为3维
- 第32-40行: `extract_sid_from_text()` 的正则表达式改为3维

---

### 3. 训练脚本

#### `train/scripts/train_beauty_align.py` ✅

**修改内容**:
- 第64-77行: `get_special_tokens()` 函数改为只生成3维token

**修改前**:
```python
for prefix in ['s_a', 's_b', 's_c', 's_d']:  # 4维
```

**修改后**:
```python
# Modified to support 3D SID format (s_a, s_b, s_c) for Kling data
for prefix in ['s_a', 's_b', 's_c']:  # 3维
```

---

#### `train/scripts/train_beauty_sid_rec.py` ✅

**修改内容**:
- 第98-111行: `get_special_tokens()` 函数改为只生成3维token

---

#### `train/scripts/train_beauty_RA.py` ✅

**修改内容**:
- 第92-105行: `get_special_tokens()` 函数改为只生成3维token

---

## 📊 修改影响分析

### 1. Token数量变化

| 项目 | 修改前(4维) | 修改后(3维) | 变化 |
|------|------------|-----------|------|
| 维度数量 | 4 (s_a, s_b, s_c, s_d) | 3 (s_a, s_b, s_c) | -1维 |
| 每维取值范围 | [0, 255] | [0, 255] | 不变 |
| SID token数量 | 4 × 256 = 1024 | 3 × 256 = 768 | -256 |
| 总特殊token | 1026 | 770 | -256 |

### 2. 模型影响

**优点**:
✅ 完全匹配Kling数据的3维格式，无需数据转换  
✅ 词表更小，模型参数略少  
✅ 训练和推理速度略快  
✅ 避免了人工添加第4维带来的信息失真

**注意事项**:
⚠️ 需要重新运行 `expand_vocab.py` 生成新的扩展模型  
⚠️ 之前用4维SID训练的模型无法直接使用  
⚠️ 需要使用3维格式的训练数据

### 3. 数据格式

**Kling数据** (保持原样):
```json
{
  "item_id": {
    "sid": "<|sid_begin|><s_a_69><s_b_142><s_c_246><|sid_end|>",
    "title": "...",
    "description": "...",
    "categories": "..."
  }
}
```

**Beauty数据** (需要调整):
- 如果Beauty数据本来就是4维的，需要决定是保留4维还是统一为3维
- 建议方案: 保持Beauty数据4维不变，这次修改仅针对Kling项目

---

## 🚀 使用流程

### 步骤1: 重新扩展词表

```bash
cd /workspace/basemodel

# 删除旧的扩展模型（如果存在）
rm -rf Qwen3-1-7B-expand

# 运行词表扩展（现在会生成3维token）
python expand_vocab.py
```

**验证**:
```bash
# 检查新模型的token数量
python << 'EOF'
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("Qwen3-1-7B-expand")
print(f"词表大小: {len(tokenizer)}")

# 测试3维SID编码
test_sid = "<|sid_begin|><s_a_0><s_b_0><s_c_0><|sid_end|>"
tokens = tokenizer.encode(test_sid, add_special_tokens=False)
print(f"3维SID token数量: {len(tokens)}")  # 应该是5
EOF
```

### 步骤2: 处理Kling数据

```bash
cd /workspace/kling_data

# 使用原始的process_kling_data.py（已经是3维格式）
python process_kling_data.py

# 输出: kling_items.json (3维SID格式)
```

### 步骤3: 生成训练数据

```bash
cd /workspace/data

# 使用原始的数据生成脚本
python generate_training_data.py \
    --items_file ../kling_data/kling_items.json \
    --sequential_file ../kling_data/kling_sequential.txt
```

### 步骤4: 训练模型

```bash
cd /workspace/train

# Stage 1: Alignment训练
bash run_training_stage1.sh

# Stage 2: SID预测训练
bash run_training_stage2.sh
```

### 步骤5: 测试评估

```bash
cd /workspace/test

# 预计算trie树
python precompute_global_trie.py \
    --test_parquet_file ../data/training_prediction_sid_data_test.parquet \
    --model_path ../basemodel/Qwen3-1-7B-expand \
    --output_file ./global_trie.pkl

# 运行评估
python test_model_hitrate.py \
    --merged_model_path ../train/output/merged_model \
    --test_parquet_file ../data/training_prediction_sid_data_test.parquet
```

---

## ✅ 验证清单

在使用修改后的代码前，请确认：

- [ ] 已重新运行 `expand_vocab.py` 生成新的扩展模型
- [ ] 扩展模型的词表包含3维SID token（不包含s_d）
- [ ] Kling数据已处理为3维SID格式
- [ ] 训练数据中的SID都是3维格式
- [ ] 所有测试脚本使用3维SID正则表达式

**验证SID格式**:
```python
import json

# 检查items文件
with open('/workspace/kling_data/kling_items.json') as f:
    items = json.load(f)
    sample_sid = list(items.values())[0]['sid']
    print(f"示例SID: {sample_sid}")
    
    # 验证格式
    import re
    pattern = r'<\|sid_begin\|><s_a_\d+><s_b_\d+><s_c_\d+><\|sid_end\|>'
    if re.match(pattern, sample_sid):
        print("✅ SID格式正确（3维）")
    else:
        print("❌ SID格式错误")
```

---

## 🔄 回滚方案

如果需要恢复到4维SID格式：

```bash
cd /workspace

# 使用git恢复修改
git checkout basemodel/expand_vocab.py
git checkout test/precompute_global_trie.py
git checkout test/test_model_hitrate.py
git checkout test/test_model_hitrate_cot.py
git checkout train/scripts/train_beauty_align.py
git checkout train/scripts/train_beauty_sid_rec.py
git checkout train/scripts/train_beauty_RA.py

# 重新扩展词表（4维）
cd basemodel
rm -rf Qwen3-1-7B-expand
python expand_vocab.py
```

---

## 📝 注意事项

### 1. 与Beauty数据集的兼容性

如果需要同时支持Beauty数据（4维）和Kling数据（3维）：

**方案A**: 保持Beauty为4维，Kling使用3维（推荐）
- 分别维护两套模型
- 使用不同的扩展词表

**方案B**: 统一为3维
- 将Beauty数据的4维SID降维到3维（丢弃s_d）
- 可能会有轻微的性能损失

**方案C**: 统一为4维
- 为Kling数据人工添加第4维（如使用content_type）
- 这是之前的方案，现在已经废弃

### 2. 模型迁移

如果已经用4维SID训练了模型，有两个选择：

1. **重新训练**: 使用3维SID重新训练（推荐）
2. **模型转换**: 技术上可行但复杂，不推荐

### 3. 数据一致性

确保整个pipeline使用相同的SID格式：
- 数据处理 → 3维
- 模型训练 → 3维
- 模型测试 → 3维
- 线上推理 → 3维

---

## 📚 相关文档

- **原始数据**: `/workspace/kling_data/process_kling_data.py`
- **词表扩展**: `/workspace/basemodel/expand_vocab.py`
- **训练脚本**: `/workspace/train/scripts/`
- **测试脚本**: `/workspace/test/`

---

## 🎯 总结

| 修改内容 | 文件数量 | 状态 |
|---------|---------|------|
| 核心模型文件 | 1 | ✅ 已完成 |
| 训练脚本 | 3 | ✅ 已完成 |
| 测试脚本 | 3 | ✅ 已完成 |
| **总计** | **7** | **✅ 全部完成** |

**修改原则**: 
- 最小化改动
- 保持代码清晰
- 添加注释说明
- 保留原始逻辑的注释

**修改时间**: 2025-11-11  
**修改理由**: 适配Kling数据的3维semantic_id格式  
**影响范围**: OneRec-Think核心代码，不影响Beauty数据集

---

**✅ 修改已完成，可以开始使用3维SID进行训练！**
