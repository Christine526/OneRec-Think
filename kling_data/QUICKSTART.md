# Kling训练数据生成 - 快速开始指南

## 📝 概述

本指南帮助你快速生成OneRec-Think论文中的三种训练数据。

## ✅ 前置条件

确保你已经通过 `process_kling_data.py` 生成了以下元数据文件：

- ✓ `kling_items.json` - 物品元数据
- ✓ `kling_sequential.txt` - 用户行为序列  
- ✓ `kling_user_behaviors.json` - 用户行为详情

## 🚀 一键运行（推荐）

```bash
cd /workspace/kling_data
bash run_all_generation.sh
```

这将自动生成以下9个训练数据文件：

### 输出文件

1. **富文本用户画像数据 (RA)** - 对应论文任务1
   - `training_RA_train.parquet`
   - `training_RA_val.parquet`
   - `training_RA_test.parquet`

2. **SID序列预测数据** - 对应论文任务2
   - `training_prediction_sid_data_train.parquet`
   - `training_prediction_sid_data_val.parquet`
   - `training_prediction_sid_data_test.parquet`

3. **物品描述数据** - 对应论文任务3
   - `training_align_data_train.parquet`
   - `training_align_data_val.parquet`
   - `training_align_data_test.parquet`

## 🔧 单独运行

如果只需要生成某一类数据：

```bash
# 生成富文本用户画像数据
python generate_kling_RA_data.py

# 生成SID序列预测数据
python generate_kling_sid_prediction_data.py

# 生成物品描述数据
python generate_kling_training_data.py
```

## 📊 数据格式

### 1. 富文本用户画像数据 (RA)

```python
{
  "user_id": "608766",
  "description": "The user has liked item <|sid_begin|><s_a_57><s_b_307><s_c_334><|sid_end|>, its title is \"宇宙陨石粒子波\", its categories are \"Video Creation > Material\" (from recommendations); ...",
  "groundtruth": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>",
  "title": "预测物品标题",
  "categories": "预测物品类别"
}
```

**特点**: 包含丰富的行为类型 (liked, commented on, searched, etc.) 和上下文信息

### 2. SID序列预测数据

```python
{
  "user_id": "608766",
  "description": "The user has interacted with the following items: <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>; <|sid_begin|><s_a_4><s_b_5><s_c_6><|sid_end|>; ...",
  "groundtruth": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>"
}
```

**特点**: 纯SID序列，用于序列建模

### 3. 物品描述数据

```python
{
  "user_id": "608766",
  "description": "The user has interacted with the following items: <|sid_begin|><s_a_1><s_b_2><s_c_3><|sid_end|>, its title is \"xxx\", its categories are \"Video Creation\"; ..."
}
```

**特点**: SID + 标题 + 类别，用于物品描述对齐

## 🎯 训练阶段使用

根据OneRec-Think论文：

- **Stage 1 (Alignment)**: 使用 `training_align_data_*.parquet` + `training_RA_*.parquet`
- **Stage 2 (Recommendation)**: 使用 `training_prediction_sid_data_*.parquet`

## ⚠️ Kling vs Beauty 数据差异

| 特性 | Kling数据 | Beauty数据 |
|------|----------|-----------|
| **SID维度** | 3维 (s_a, s_b, s_c) | 4维 (s_a, s_b, s_c, s_d) |
| **行为类型** | 多样 (RECOMMEND/SEARCH/PRODUCE) | 单一 (购买) |
| **搜索场景** | 支持，包含query_content | 不支持 |
| **创作场景** | 支持，标注为PRODUCE | 不支持 |
| **类别层级** | 2层 (Video Creation > Material) | 多层 |

## 📖 更多信息

详细说明请参考：
- `README.md` - 完整文档
- 论文附录 A.3.1 - 任务描述
- 参考脚本: `/workspace/data/generate_*_data.py`

## 🐛 常见问题

**Q: 提示"文件不存在"？**  
A: 请先运行 `process_kling_data.py` 生成元数据文件

**Q: 生成的数据量很小？**  
A: 检查 `kling_items.json` 中是否有足够的有效SID（需要3维完整）

**Q: 内存不足？**  
A: 可以分别运行3个脚本，避免同时处理

**Q: 如何查看生成的数据？**
```python
import pandas as pd
df = pd.read_parquet('training_RA_train.parquet')
print(df.head())
```

## 📞 支持

如有问题，请查看：
1. 脚本内的详细注释
2. README.md 完整文档
3. 论文附录 A.3.1
