#!/usr/bin/env python3
"""
Kling数据 - Itemic Dense Captioning (物品描述) 训练数据生成脚本

对应论文附录A.3.1中的任务3：Itemic Dense Captioning
为给定的物品SID生成文本描述，包含标题和类别信息

输入文件:
- kling_items.json: 物品元数据
- kling_sequential.txt: 用户行为序列

输出文件:
- training_align_data_train.parquet
- training_align_data_val.parquet
- training_align_data_test.parquet
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


def build_item_descriptions(
    item_ids: list[str],
    user_id: str,
    kling_items: dict
) -> tuple[list[str], int]:
    """
    构建物品描述列表
    
    Args:
        item_ids: 物品ID列表
        user_id: 用户ID
        kling_items: 物品元数据字典
    
    Returns:
        (物品描述列表, 跳过的物品数量)
    """
    item_descriptions = []
    skipped_count = 0
    
    for item_id in item_ids:
        item_info = kling_items.get(item_id)
        if not item_info:
            skipped_count += 1
            continue
        
        sid = item_info.get('sid', '')
        title = item_info.get('title', '')
        categories = item_info.get('categories', '')
        
        # 必须有SID、标题和类别
        if not (sid and title and categories):
            skipped_count += 1
            continue
        
        # 构建描述：SID + 标题 + 类别
        item_desc = f'{sid}, its title is "{title}", its categories are "{categories}"'
        item_descriptions.append(item_desc)
    
    return item_descriptions, skipped_count


def generate_kling_training_data(
    sequential_file: Path,
    items_file: Path,
    output_train: Path,
    output_val: Path,
    output_test: Path,
) -> None:
    """生成Kling物品描述训练数据"""
    
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
    
    total_items_skipped = 0
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        elements = line.split()
        if len(elements) <= 1:
            continue
        
        user_id = elements[0]
        item_ids = elements[1:]
        
        # 测试集：使用完整序列
        full_descriptions, skipped_full = build_item_descriptions(
            item_ids, user_id, kling_items
        )
        total_items_skipped += skipped_full
        
        if full_descriptions:
            test_description = "The user has interacted with the following items: " + "; ".join(full_descriptions) + ";"
            test_rows.append({
                'user_id': user_id,
                'description': test_description
            })
        
        # 验证集：移除最后1个物品
        if len(item_ids) > 1:
            val_item_ids = item_ids[:-1]
            val_descriptions, skipped_val = build_item_descriptions(
                val_item_ids, user_id, kling_items
            )
            total_items_skipped += skipped_val
            
            if val_descriptions:
                val_description = "The user has interacted with the following items: " + "; ".join(val_descriptions) + ";"
                val_rows.append({
                    'user_id': user_id,
                    'description': val_description
                })
        
        # 训练集：移除最后2个物品
        if len(item_ids) > 2:
            train_item_ids = item_ids[:-2]
            train_descriptions, skipped_train = build_item_descriptions(
                train_item_ids, user_id, kling_items
            )
            total_items_skipped += skipped_train
            
            if train_descriptions:
                train_description = "The user has interacted with the following items: " + "; ".join(train_descriptions) + ";"
                train_rows.append({
                    'user_id': user_id,
                    'description': train_description
                })
        
        if (idx + 1) % 1000 == 0:
            print(f"  已处理 {idx + 1:,} 个用户...")
    
    print(f"\n处理完成:")
    print(f"  总共跳过: {total_items_skipped:,} 个物品 (缺失元数据)")
    
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
            desc = row['description']
            if len(desc) > 300:
                print(f"    描述: {desc[:300]}...")
            else:
                print(f"    描述: {desc}")
    
    preview(df_train, "训练集")
    preview(df_val, "验证集")
    
    print("\n✨ 数据生成完成!")


if __name__ == "__main__":
    # 文件路径
    sequential_file = Path("./kling_sequential.txt")
    items_file = Path("./kling_items.json")
    
    output_train = Path("./training_align_data_train.parquet")
    output_val = Path("./training_align_data_val.parquet")
    output_test = Path("./training_align_data_test.parquet")
    
    # 检查输入文件
    for file in [sequential_file, items_file]:
        if not file.exists():
            print(f"❌ 错误: 文件不存在: {file}")
            exit(1)
    
    # 生成数据
    generate_kling_training_data(
        sequential_file=sequential_file,
        items_file=items_file,
        output_train=output_train,
        output_val=output_val,
        output_test=output_test,
    )
