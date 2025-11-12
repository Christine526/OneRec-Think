#!/usr/bin/env python3
"""
Kling数据 - Sequential Preference Modeling (SID预测) 训练数据生成脚本

对应论文附录A.3.1中的任务2：Sequential Preference Modeling
根据用户历史交互序列，预测下一个物品的SID

输入文件:
- kling_items.json: 物品元数据
- kling_sequential.txt: 用户行为序列

输出文件:
- training_prediction_sid_data_train.parquet
- training_prediction_sid_data_val.parquet
- training_prediction_sid_data_test.parquet
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_kling_items(items_file: Path) -> dict:
    """加载Kling物品元数据"""
    print(f"加载物品元数据: {items_file}")
    with items_file.open("r", encoding="utf-8") as f:
        items = json.load(f)
    print(f"物品数量: {len(items):,}")
    return items


def extract_sid_sequence(
    item_ids: list[str], 
    user_id: str, 
    kling_items: dict
) -> list[str]:
    """
    提取物品ID序列对应的SID序列
    
    Args:
        item_ids: 物品ID列表
        user_id: 用户ID
        kling_items: 物品元数据字典
    
    Returns:
        SID字符串列表
    """
    sid_sequence: list[str] = []
    
    for item_id in item_ids:
        item_info = kling_items.get(item_id)
        if not item_info:
            continue
        
        sid = item_info.get("sid")
        if not sid:
            continue
        
        sid_sequence.append(sid)
    
    return sid_sequence


def build_dataset_entry(
    user_id: str,
    sid_sequence: list[str],
    tail_remove_count: int,
) -> dict | None:
    """
    构建单个训练样本
    
    Args:
        user_id: 用户ID
        sid_sequence: SID序列
        tail_remove_count: 尾部移除数量（train=2, val=1, test=0）
    
    Returns:
        训练样本字典
    """
    # 序列长度检查
    if len(sid_sequence) <= tail_remove_count + 1:
        return None
    
    # 分割序列
    candidate_sequence = (
        sid_sequence[: len(sid_sequence) - tail_remove_count]
        if tail_remove_count > 0
        else sid_sequence
    )
    
    if len(candidate_sequence) < 2:
        return None
    
    # groundtruth是最后一个SID
    groundtruth = candidate_sequence[-1]
    description_sids = candidate_sequence[:-1]
    
    if not description_sids:
        return None
    
    # 构建描述：简单的SID序列
    description = "The user has interacted with the following items: " + "; ".join(description_sids) + ";"
    
    return {
        "user_id": user_id,
        "description": description,
        "groundtruth": groundtruth,
    }


def generate_kling_sid_prediction_data(
    sequential_file: Path,
    items_file: Path,
    output_train: Path,
    output_val: Path,
    output_test: Path,
) -> None:
    """生成Kling SID预测训练数据"""
    
    # 加载数据
    kling_items = load_kling_items(items_file)
    
    print(f"\n加载用户序列文件: {sequential_file}")
    with sequential_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"序列数量: {len(lines):,}")
    
    # 生成训练数据
    print("\n生成训练数据...")
    train_rows: list[dict] = []
    val_rows: list[dict] = []
    test_rows: list[dict] = []
    
    skipped_users = 0
    valid_users = 0
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        elements = line.split()
        if len(elements) <= 1:
            continue
        
        user_id = elements[0]
        item_ids = elements[1:]
        
        # 提取SID序列
        sid_sequence = extract_sid_sequence(item_ids, user_id, kling_items)
        if len(sid_sequence) == 0:
            skipped_users += 1
            continue
        
        valid_users += 1
        
        # 生成train/val/test样本
        entry_train = build_dataset_entry(user_id, sid_sequence, tail_remove_count=2)
        if entry_train:
            train_rows.append(entry_train)
        
        entry_val = build_dataset_entry(user_id, sid_sequence, tail_remove_count=1)
        if entry_val:
            val_rows.append(entry_val)
        
        entry_test = build_dataset_entry(user_id, sid_sequence, tail_remove_count=0)
        if entry_test:
            test_rows.append(entry_test)
        
        if (idx + 1) % 1000 == 0:
            print(f"  已处理 {idx + 1:,} 个用户...")
    
    print(f"\n处理完成:")
    print(f"  有效用户: {valid_users:,}")
    print(f"  跳过用户: {skipped_users:,} (无有效SID)")
    
    # 创建DataFrame
    print("\n创建DataFrame...")
    df_train = pd.DataFrame(train_rows)
    df_val = pd.DataFrame(val_rows)
    df_test = pd.DataFrame(test_rows)
    
    print(f"\n✅ 数据集大小:")
    print(f"  训练集: {len(df_train):,} 条")
    print(f"  验证集: {len(df_val):,} 条")
    print(f"  测试集: {len(df_test):,} 条")
    
    # 保存文件
    print(f"\n保存训练集到: {output_train}")
    df_train.to_parquet(output_train, engine="pyarrow", index=False)
    
    print(f"保存验证集到: {output_val}")
    df_val.to_parquet(output_val, engine="pyarrow", index=False)
    
    print(f"保存测试集到: {output_test}")
    df_test.to_parquet(output_test, engine="pyarrow", index=False)
    
    # 预览数据
    def preview(df: pd.DataFrame, name: str) -> None:
        if len(df) == 0:
            return
        print(f"\n📋 {name} 前2条样本预览:")
        for i, (_, row) in enumerate(df.head(2).iterrows()):
            print(f"\n  样本 {i+1}:")
            print(f"    用户ID: {row['user_id']}")
            print(f"    描述: {row['description'][:200]}...")
            print(f"    预测目标: {row['groundtruth']}")
    
    preview(df_train, "训练集")
    preview(df_val, "验证集")
    
    print("\n✨ 数据生成完成!")


if __name__ == "__main__":
    # 文件路径
    sequential_file = Path("./kling_sequential.txt")
    items_file = Path("./kling_items.json")
    
    output_train = Path("./training_prediction_sid_data_train.parquet")
    output_val = Path("./training_prediction_sid_data_val.parquet")
    output_test = Path("./training_prediction_sid_data_test.parquet")
    
    # 检查输入文件
    for file in [sequential_file, items_file]:
        if not file.exists():
            print(f"❌ 错误: 文件不存在: {file}")
            exit(1)
    
    # 生成数据
    generate_kling_sid_prediction_data(
        sequential_file=sequential_file,
        items_file=items_file,
        output_train=output_train,
        output_val=output_val,
        output_test=output_test,
    )
