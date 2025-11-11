# Kling数据接入OneRec-Think快速指南

## 🎯 核心问题与解决方案

### 问题1: SID维度不匹配 ❌

**原始代码**:
```python
# process_kling_data.py (原版)
sid = f'<|sid_begin|><s_a_{a}><s_b_{b}><s_c_{c}><|sid_end|>'  # 3维
```

**OneRec-Think要求**:
```python
# 模型词表需要4维
sid = f'<|sid_begin|><s_a_{a}><s_b_{b}><s_c_{c}><s_d_{d}><|sid_end|>'  # 4维
```

**✅ 修正方案**:
```python
# process_kling_data_fixed.py
# 使用content_type作为第4维
def format_semantic_id_to_sid(semantic_id_array, content_type=0):
    a, b, c = semantic_id_array[0:3]
    d = int(content_type) if pd.notna(content_type) else 0
    sid = f'<|sid_begin|><s_a_{a}><s_b_{b}><s_c_{c}><s_d_{d}><|sid_end|>'
    return sid
```

---

## 📦 已创建的文件

### 1. 数据处理脚本

| 文件 | 状态 | 说明 |
|------|------|------|
| `kling_data/process_kling_data_fixed.py` | ✅ 新建 | 修正版处理脚本（4维SID） |
| `kling_data/load_kling_data.py` | ✅ 已有 | Hive数据导出脚本 |
| `kling_data/README.md` | ✅ 新建 | Kling数据处理指南 |

### 2. 训练数据生成脚本

| 文件 | 状态 | 用途 |
|------|------|------|
| `data/generate_training_data_kling.py` | ✅ 新建 | Stage 1: Alignment训练数据 |
| `data/generate_sid_prediction_data_kling.py` | ✅ 新建 | Stage 2: SID预测训练数据 |
| `data/generate_RA_data_kling.py` | ✅ 新建 | RA训练数据（可选） |

### 3. 分析文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `kling_data_analysis.md` | ✅ 新建 | 详细的错误分析和解决方案 |
| `KLING_DATA_QUICKSTART.md` | ✅ 新建 | 本快速指南 |

---

## 🚀 完整流程

### 第一步: 准备Kling原始数据

**选项A: 从Hive导出（内部环境）**

```bash
cd /workspace/kling_data
python load_kling_data.py
# 输出: kling_data.csv 或 kling_data.tsv
```

**选项B: 使用已有CSV文件**

将CSV文件复制到 `/workspace/kling_data/` 目录，命名为：
- `kling_data.tsv` (推荐，制表符分隔)
- 或 `kling_data.csv` (逗号分隔)

⚠️ **重要**: CSV应包含以下字段：
```
user_id, kling_photo_id, kling_photo_type, event_type, behavior_type,
behavior_subtype, time_stamp, content_type, prompt, title, introduction,
element_query_content, query_cnt, semantic_id
```

### 第二步: 处理Kling数据

```bash
cd /workspace/kling_data
python process_kling_data_fixed.py
```

**输出文件**:
- ✅ `kling_items.json` - 物品元数据（4维SID）
- ✅ `kling_sequential.txt` - 用户序列
- ✅ `kling_user_behaviors.json` - 行为详情

**验证输出**:
```bash
# 检查SID格式（应该看到4个维度：s_a, s_b, s_c, s_d）
head -20 kling_items.json | grep "sid"
```

### 第三步: 生成训练数据

```bash
cd /workspace/data

# 3.1 生成Alignment数据（Stage 1 - 必需）
python generate_training_data_kling.py
# 输出:
#   - training_align_data_kling_train.parquet
#   - training_align_data_kling_val.parquet
#   - training_align_data_kling_test.parquet

# 3.2 生成SID预测数据（Stage 2 - 必需）
python generate_sid_prediction_data_kling.py
# 输出:
#   - training_prediction_sid_data_kling_train.parquet
#   - training_prediction_sid_data_kling_val.parquet
#   - training_prediction_sid_data_kling_test.parquet

# 3.3 生成RA数据（可选）
python generate_RA_data_kling.py
# 输出:
#   - training_RA_kling_train.parquet
#   - training_RA_kling_val.parquet
#   - training_RA_kling_test.parquet
```

### 第四步: 开始训练

**Stage 1: Itemix Alignment训练**

```bash
cd /workspace/train

# 方式1: 使用shell脚本
bash run_training_stage1.sh

# 方式2: 直接运行Python脚本（需要配置参数）
cd scripts
python train_beauty_align.py \
    --model_dir ../../basemodel/Qwen3-1-7B-expand \
    --train_data_path ../../data/training_align_data_kling_train.parquet \
    --val_data_path ../../data/training_align_data_kling_val.parquet \
    --output_dir ../output/stage1_kling \
    --num_train_epochs 3 \
    --per_device_train_batch_size 4 \
    --learning_rate 1e-4
```

**Stage 2: Sequential Recommendation训练**

```bash
cd /workspace/train

# 方式1: 使用shell脚本
bash run_training_stage2.sh

# 方式2: 直接运行Python脚本
cd scripts
python train_beauty_sid_rec.py \
    --model_name_or_path ../../basemodel/Qwen3-1-7B-expand \
    --train_data_path ../../data/training_prediction_sid_data_kling_train.parquet \
    --val_data_path ../../data/training_prediction_sid_data_kling_val.parquet \
    --output_dir ../output/stage2_kling \
    --num_train_epochs 3 \
    --per_device_train_batch_size 2 \
    --learning_rate 1e-5
```

---

## ✅ 验证检查清单

在训练前，请确认：

### 数据格式验证

- [ ] **SID格式**: 所有SID都是4维格式
  ```bash
  # 检查命令
  python -c "
  import json
  with open('/workspace/kling_data/kling_items.json') as f:
      items = json.load(f)
      sample = list(items.values())[0]['sid']
      print('SID示例:', sample)
      has_4_dims = all(f'<s_{d}_' in sample for d in ['a','b','c','d'])
      print('4维验证:', '✅' if has_4_dims else '❌')
  "
  ```

- [ ] **SID值范围**: 所有维度的值在 [0, 255] 范围内
- [ ] **必需字段**: 每个物品都有 title, description, categories, sid
- [ ] **序列文件**: sequential文件格式正确（空格分隔）
- [ ] **Parquet文件**: 训练数据parquet文件可以读取

### 数据规模检查

```bash
# 检查物品数量
python -c "import json; print('物品数:', len(json.load(open('/workspace/kling_data/kling_items.json'))))"

# 检查用户数量
wc -l /workspace/kling_data/kling_sequential.txt

# 检查训练数据规模
python -c "
import pandas as pd
df = pd.read_parquet('/workspace/data/training_align_data_kling_train.parquet')
print('Train集样本数:', len(df))
print('列名:', list(df.columns))
print('示例:', df.iloc[0]['description'][:100], '...')
"
```

---

## 🔍 故障排查

### 问题1: SID格式错误

**症状**: 训练时提示token不存在或无法识别

**检查**:
```bash
grep -o '<s_[a-z]_' /workspace/kling_data/kling_items.json | sort | uniq -c
# 应该看到: s_a, s_b, s_c, s_d 四个维度
```

**解决**: 确保使用 `process_kling_data_fixed.py`（不是原版）

---

### 问题2: CSV读取失败

**症状**: `ParserError` 或读取的数据行数不对

**解决方案**:
1. 使用制表符导出：在SQL导出时使用 `\t` 分隔
2. 检查编码：确保是 UTF-8
3. 检查引号：字段中的引号需要正确转义

---

### 问题3: 物品缺失

**症状**: `missing_items_count` 很大

**原因**: 
- semantic_id字段为空或无效
- item_id在元数据中不存在

**解决**: 
```bash
# 检查semantic_id的有效性
python -c "
import pandas as pd
df = pd.read_csv('/workspace/kling_data/kling_data.tsv', sep='\t')
print('总记录数:', len(df))
print('semantic_id非空:', df['semantic_id'].notna().sum())
print('semantic_id示例:', df['semantic_id'].iloc[0])
"
```

---

### 问题4: 训练脚本找不到数据

**症状**: `FileNotFoundError`

**检查路径**:
```bash
# 训练脚本中的路径配置
cd /workspace/train/scripts
grep -n "data_path" train_beauty_*.py

# 确保路径正确指向kling数据文件
```

**解决**: 修改训练脚本中的 `train_data_path` 和 `val_data_path` 参数

---

## 📊 数据对比

### Kling vs Beauty数据集

| 维度 | Beauty数据集 | Kling数据集 | 适配方案 |
|------|-------------|------------|---------|
| SID维度 | 4维 | 3维 | ✅ 添加content_type作为第4维 |
| 物品类别 | 商品类别 | content_type + photo_type | ✅ 映射为类别格式 |
| 描述 | 商品描述 | prompt | ✅ 直接使用 |
| 标题 | 商品标题 | title/introduction | ✅ 优先使用title |
| 行为类型 | 购买 | RECOMMEND/SEARCH/PRODUCE | ✅ 支持多种行为 |

---

## 🎓 技术细节

### OneRec-Think的SID格式要求

模型词表通过 `basemodel/expand_vocab.py` 扩展，添加了：

```python
# 特殊token定义
special_tokens = ['<|sid_begin|>', '<|sid_end|>']

# 4维SID token (每维0-255，共256个值)
for prefix in ['s_a', 's_b', 's_c', 's_d']:  # 必须4维
    for idx in range(256):
        special_tokens.append(f'<{prefix}_{idx}>')

# 总计: 2 + 4*256 = 1026 个特殊token
```

因此，**所有SID必须是4维格式**，否则模型无法识别。

### 训练数据格式

**Stage 1 (Alignment)**:
```
The user has purchased the following items: 
<|sid_begin|><s_a_69><s_b_142><s_c_246><s_d_0><|sid_end|>, 
  its title is "Image Title", 
  its categories are "Image Creation > Material"; 
...
```

**Stage 2 (SID Prediction)**:
```
<|im_start|>system
You are a professional recommendation expert...<|im_end|>
<|im_start|>user
The user has purchased the following items: <|sid_begin|>...<|sid_end|>; ...<|im_end|>
<|im_start|>assistant
<think>

</think>
<|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|><|im_end|>
```

---

## 📚 相关资源

- **详细分析**: `/workspace/kling_data_analysis.md`
- **Kling数据指南**: `/workspace/kling_data/README.md`
- **OneRec-Think论文**: `/workspace/OneRec-Think.pdf`
- **原始Beauty数据生成**: `/workspace/data/generate_training_data.py`

---

## 🎉 总结

通过以下修正，Kling数据现在可以正确接入OneRec-Think：

1. ✅ **SID维度**: 从3维扩展为4维（使用content_type）
2. ✅ **数据格式**: 兼容OneRec-Think的JSON和TXT格式
3. ✅ **训练脚本**: 创建了3个数据生成脚本
4. ✅ **文档完善**: 提供了详细的使用指南

**下一步行动**:
1. 准备Kling原始数据（CSV/TSV格式）
2. 运行 `process_kling_data_fixed.py` 处理数据
3. 运行数据生成脚本
4. 开始训练！

---

**最后更新**: 2025-11-11  
**状态**: ✅ 已完成所有修正和文档
