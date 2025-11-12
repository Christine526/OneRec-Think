#!/bin/bash
# Kling训练数据生成 - 一键运行脚本
# 依次运行3个数据生成脚本，生成所有训练数据

set -e  # 遇到错误立即退出

echo "=================================="
echo "Kling训练数据生成 - 开始"
echo "=================================="

# 检查输入文件
echo ""
echo "检查输入文件..."
required_files=("kling_items.json" "kling_sequential.txt" "kling_user_behaviors.json")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ 错误: 文件不存在: $file"
        echo "请先运行 process_kling_data.py 生成元数据文件"
        exit 1
    fi
    echo "  ✓ $file"
done

# 1. 生成富文本用户画像数据 (RA)
echo ""
echo "=================================="
echo "1/3 生成富文本用户画像数据 (RA)"
echo "=================================="
python generate_kling_RA_data.py
if [ $? -ne 0 ]; then
    echo "❌ 生成RA数据失败"
    exit 1
fi

# 2. 生成SID序列预测数据
echo ""
echo "=================================="
echo "2/3 生成SID序列预测数据"
echo "=================================="
python generate_kling_sid_prediction_data.py
if [ $? -ne 0 ]; then
    echo "❌ 生成SID预测数据失败"
    exit 1
fi

# 3. 生成物品描述数据
echo ""
echo "=================================="
echo "3/3 生成物品描述数据"
echo "=================================="
python generate_kling_training_data.py
if [ $? -ne 0 ]; then
    echo "❌ 生成物品描述数据失败"
    exit 1
fi

# 汇总输出文件
echo ""
echo "=================================="
echo "✨ 所有训练数据生成完成！"
echo "=================================="
echo ""
echo "📁 输出文件列表："
echo ""
echo "1️⃣ 富文本用户画像数据 (RA):"
ls -lh training_RA_*.parquet 2>/dev/null || echo "  未找到输出文件"
echo ""
echo "2️⃣ SID序列预测数据:"
ls -lh training_prediction_sid_data_*.parquet 2>/dev/null || echo "  未找到输出文件"
echo ""
echo "3️⃣ 物品描述数据:"
ls -lh training_align_data_*.parquet 2>/dev/null || echo "  未找到输出文件"
echo ""
echo "=================================="
