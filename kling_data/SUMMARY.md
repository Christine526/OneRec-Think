# Kling训练数据生成 - 完成总结

## ✅ 已创建的脚本

### 数据生成脚本（3个）

| 脚本名称 | 大小 | 对应论文任务 | 描述 |
|---------|------|-------------|------|
| `generate_kling_RA_data.py` | 13KB | 任务1: Interleaved User Persona Grounding | 生成富文本用户画像数据，包含行为类型、搜索词等 |
| `generate_kling_sid_prediction_data.py` | 6.6KB | 任务2: Sequential Preference Modeling | 生成SID序列预测数据，用于序列建模 |
| `generate_kling_training_data.py` | 6.9KB | 任务3: Itemic Dense Captioning | 生成物品描述数据，包含标题和类别 |

### 辅助文件

| 文件名称 | 用途 |
|---------|------|
| `run_all_generation.sh` | 一键运行所有数据生成脚本 |
| `QUICKSTART.md` | 快速开始指南 |
| `SUMMARY.md` | 本文档，总结说明 |
| `README.md` | 更新后的完整文档 |

## 📦 输出数据文件（待生成）

运行脚本后将生成以下9个训练数据文件：

### 1. 富文本用户画像数据（RA）
- `training_RA_train.parquet`
- `training_RA_val.parquet`
- `training_RA_test.parquet`

### 2. SID序列预测数据
- `training_prediction_sid_data_train.parquet`
- `training_prediction_sid_data_val.parquet`
- `training_prediction_sid_data_test.parquet`

### 3. 物品描述数据
- `training_align_data_train.parquet`
- `training_align_data_val.parquet`
- `training_align_data_test.parquet`

## 🎯 关键特性

### 1. generate_kling_RA_data.py 特色功能

✨ **富文本行为描述**
- 支持12种行为类型映射 (LIKE → "liked", COMMENT → "commented on", etc.)
- 搜索场景：包含搜索词和搜索次数
- 生产场景：标注为"created this content"
- 推荐场景：标注为"from recommendations"

🔍 **统计功能**
- 事件类型分布统计 (RECOMMEND/SEARCH/PRODUCE)
- 行为类型分布统计 (Top 10)
- 搜索场景统计（含查询词比例）

📋 **输出格式**
```python
{
  "user_id": str,
  "description": str,  # 富文本行为序列
  "groundtruth": str,  # 预测目标SID
  "title": str,        # 预测目标标题
  "categories": str    # 预测目标类别
}
```

### 2. generate_kling_sid_prediction_data.py 特色功能

🎯 **纯SID序列建模**
- 提取物品的SID序列
- 不包含其他元数据
- 简洁高效的序列格式

📋 **输出格式**
```python
{
  "user_id": str,
  "description": str,  # SID序列
  "groundtruth": str   # 预测目标SID
}
```

### 3. generate_kling_training_data.py 特色功能

📝 **物品描述对齐**
- SID + 标题 + 类别的组合
- 用于预训练阶段
- 统一的"interacted with"动词

📋 **输出格式**
```python
{
  "user_id": str,
  "description": str  # 物品描述序列
}
```

## 🔄 数据分割策略

所有3个脚本使用统一的数据分割策略：

| 数据集 | 尾部移除 | 说明 |
|--------|---------|------|
| **Train** | 2个物品 | 移除序列最后2个物品 |
| **Val** | 1个物品 | 移除序列最后1个物品 |
| **Test** | 0个物品 | 使用完整序列 |

**最小序列长度**: 3（至少需要3个物品才能生成train数据）

## 🆚 Kling vs Beauty 数据对比

| 特性 | Kling数据 | Beauty数据 |
|------|----------|-----------|
| **SID格式** | `<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>` | `<|sid_begin|><s_a_X><s_b_Y><s_c_Z><s_d_W><|sid_end|>` |
| **SID维度** | 3维 (s_a, s_b, s_c) | 4维 (s_a, s_b, s_c, s_d) |
| **行为动词** | liked, commented on, watched, searched, created | purchased |
| **事件类型** | RECOMMEND, SEARCH, PRODUCE | 购买行为 |
| **搜索支持** | ✅ 支持query_content | ❌ 不支持 |
| **创作支持** | ✅ 支持PRODUCE事件 | ❌ 不支持 |
| **类别层级** | 2层 (Video Creation > Material) | 多层 (Beauty > Makeup > Lipstick > Red) |

## 📊 使用场景

### Stage 1 - Alignment训练

使用以下数据：
- `training_align_data_*.parquet` (物品描述对齐)
- `training_RA_*.parquet` (富文本用户画像)

**目标**: 学习物品表示和用户画像建模

### Stage 2 - Recommendation训练

使用以下数据：
- `training_prediction_sid_data_*.parquet` (SID序列预测)

**目标**: 学习序列推荐

## 🚀 快速开始

```bash
# 1. 进入目录
cd /workspace/kling_data

# 2. 一键运行
bash run_all_generation.sh

# 3. 查看输出
ls -lh training_*.parquet
```

## 📖 参考文档

- **快速指南**: `QUICKSTART.md`
- **完整文档**: `README.md`
- **论文附录**: `A.3.1 Implementation Details`
- **Beauty参考**: `/workspace/data/generate_*_data.py`

## ⚙️ 技术细节

### 依赖包
- `pandas` - DataFrame处理
- `pyarrow` - Parquet文件读写
- `json` - JSON数据处理

### 性能优化
- 每1000个用户打印进度
- 批量处理避免内存溢出
- Parquet格式高效存储

### 错误处理
- 缺失item_id自动跳过
- 缺失SID自动跳过
- 序列长度不足自动过滤

## 🎉 总结

本次创建了完整的Kling训练数据生成流程：

✅ 3个核心数据生成脚本  
✅ 1个一键运行脚本  
✅ 完整的文档和指南  
✅ 与论文任务完全对应  
✅ 针对Kling数据特点优化  

所有脚本已准备就绪，可直接运行生成训练数据！

---

**创建日期**: 2025-11-12  
**对应论文**: OneRec-Think 附录 A.3.1  
**数据来源**: Kling视频创作平台
