#!/usr/bin/env python3
"""
Kling数据 - SID预测训练数据生成脚本

用途: Stage 2 训练 - Sequential Recommendation
训练模型根据用户历史行为预测下一个物品的SID

输入:
  - kling_items.json (物品元数据, 4维SID)
  - kling_sequential.txt (用户序列)

输出:
  - training_prediction_sid_data_kling_train.parquet
  - training_prediction_sid_data_kling_val.parquet
  - training_prediction_sid_data_kling_test.parquet

数据格式:
  {
      'user_id': '123',
      'description': 'The user has purchased the following items: <|sid_begin|>...<|sid_end|>; ...',
      'groundtruth': '<|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|>'
  }

训练时会被转换为Chat格式:
  <|im_start|>system
  You are a professional recommendation expert...<|im_end|>
  <|im_start|>user
  {description}<|im_end|>
  <|im_start|>assistant
  <think>
  
  </think>
  {groundtruth}<|im_end|>
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_items(items_file: Path) -> dict:
    """加载物品元数据"""
    print(f"📖 加载物品元数据: {items_file}")
    with items_file.open("r", encoding="utf-8") as f:
        items = json.load(f)
    print(f"   ✅ 加载了 {len(items)} 个物品")
    
    # 验证SID格式
    sample_item = list(items.values())[0]
    sample_sid = sample_item['sid']
    has_4_dims = all(f'<s_{dim}_' in sample_sid for dim in ['a', 'b', 'c', 'd'])
    if not has_4_dims:
        print(f"   ⚠️  警告: SID格式可能不正确（应该是4维）")
        print(f"   示例: {sample_sid}")
    else:
        print(f"   ✅ SID格式验证通过（4维）")
    
    return items


def extract_sid_sequence(item_ids: list[str], user_id: str, items: dict) -> list[str]:
    """从item_ids中提取SID序列"""
    sid_sequence: list[str] = []
    for item_id in item_ids:
        item_info = items.get(item_id)
        if not item_info:
            # print(f"⚠️  警告: user {user_id} 的 item_id {item_id} 未找到，跳过")
            continue
        sid = item_info.get("sid")
        if not sid:
            # print(f"⚠️  警告: user {user_id} 的 item_id {item_id} 缺少sid字段，跳过")
            continue
        sid_sequence.append(sid)
    return sid_sequence


def build_dataset_entry(
    user_id: str,
    sid_sequence: list[str],
    tail_remove_count: int,
) -> dict | None:
    """
    构建一条训练数据
    
    Args:
        user_id: 用户ID
        sid_sequence: 用户的SID序列
        tail_remove_count: 从尾部移除的item数量（用于train/val/test划分）
    
    Returns:
        {
            'user_id': '123',
            'description': '用户历史的SID列表',
            'groundtruth': '要预测的下一个SID'
        }
    """
    # 确保序列长度足够
    if len(sid_sequence) <= tail_remove_count + 1:
        return None

    # 截取候选序列
    candidate_sequence = (
        sid_sequence[: len(sid_sequence) - tail_remove_count]
        if tail_remove_count > 0
        else sid_sequence
    )

    # 至少需要2个item（1个历史 + 1个预测）
    if len(candidate_sequence) < 2:
        return None

    # 最后一个作为groundtruth，其余作为历史
    groundtruth = candidate_sequence[-1]
    description_sids = candidate_sequence[:-1]

    if not description_sids:
        return None

    # 构造描述文本
    description = "The user has purchased the following items: " + "; ".join(description_sids) + ";"
    
    return {
        "user_id": user_id,
        "description": description,
        "groundtruth": groundtruth,
    }


def generate_sid_prediction_data(
    sequential_file: Path,
    items_file: Path,
    output_train: Path,
    output_val: Path,
    output_test: Path,
) -> None:
    """生成SID预测训练数据"""
    
    print("="*60)
    print("🎯 生成Kling SID预测训练数据 (Stage 2)")
    print("="*60)
    print()
    
    # 加载物品元数据
    items = load_items(items_file)

    # 加载用户序列
    print(f"\n📖 加载用户序列: {sequential_file}")
    with sequential_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"   ✅ 加载了 {len(lines)} 个用户序列")

    train_rows: list[dict] = []
    val_rows: list[dict] = []
    test_rows: list[dict] = []
    
    skipped_users = 0

    print(f"\n🔄 处理用户序列...")
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
        sid_sequence = extract_sid_sequence(item_ids, user_id, items)
        if len(sid_sequence) == 0:
            skipped_users += 1
            continue

        # Train集: 去掉最后2个item
        entry_train = build_dataset_entry(user_id, sid_sequence, tail_remove_count=2)
        if entry_train:
            train_rows.append(entry_train)

        # Val集: 去掉最后1个item
        entry_val = build_dataset_entry(user_id, sid_sequence, tail_remove_count=1)
        if entry_val:
            val_rows.append(entry_val)

        # Test集: 使用完整序列
        entry_test = build_dataset_entry(user_id, sid_sequence, tail_remove_count=0)
        if entry_test:
            test_rows.append(entry_test)

        if (idx + 1) % 1000 == 0:
            print(f"   已处理 {idx + 1}/{len(lines)} 个用户...")

    print(f"   ✅ 完成处理")
    print(f"   ⚠️  跳过的用户（无有效SID）: {skipped_users}")

    # 创建DataFrame
    print(f"\n📊 创建DataFrame...")
    df_train = pd.DataFrame(train_rows)
    df_val = pd.DataFrame(val_rows)
    df_test = pd.DataFrame(test_rows)

    print(f"   Train集: {len(df_train)} 条")
    print(f"   Val集:   {len(df_val)} 条")
    print(f"   Test集:  {len(df_test)} 条")

    # 保存parquet文件
    print(f"\n💾 保存parquet文件...")
    
    print(f"   保存Train集: {output_train}")
    df_train.to_parquet(output_train, engine="pyarrow", index=False)

    print(f"   保存Val集: {output_val}")
    df_val.to_parquet(output_val, engine="pyarrow", index=False)

    print(f"   保存Test集: {output_test}")
    df_test.to_parquet(output_test, engine="pyarrow", index=False)

    # 显示示例
    def preview(df: pd.DataFrame, name: str) -> None:
        print(f"\n📝 {name} 数据示例 (前2条):")
        for i, row in df.head(2).iterrows():
            print(f"\n   [{i+1}] User: {row['user_id']}")
            desc = row['description']
            if len(desc) > 150:
                print(f"       Description: {desc[:150]}...")
            else:
                print(f"       Description: {desc}")
            print(f"       Groundtruth: {row['groundtruth']}")

    preview(df_train, "Train集")
    preview(df_val, "Val集")
    preview(df_test, "Test集")
    
    print(f"\n{'='*60}")
    print(f"✅ SID预测训练数据生成完成!")
    print(f"{'='*60}")
    print(f"\n🎯 下一步:")
    print(f"   运行训练脚本: train/run_training_stage2.sh")
    print(f"   或使用: train/scripts/train_beauty_sid_rec.py\n")


if __name__ == "__main__":
    # 默认路径（可根据实际情况修改）
    sequential_file = Path("../kling_data/kling_sequential.txt")
    items_file = Path("../kling_data/kling_items.json")
    
    output_train = Path("./training_prediction_sid_data_kling_train.parquet")
    output_val = Path("./training_prediction_sid_data_kling_val.parquet")
    output_test = Path("./training_prediction_sid_data_kling_test.parquet")
    
    # 检查输入文件是否存在
    if not sequential_file.exists():
        print(f"❌ 错误: 找不到文件 {sequential_file}")
        print(f"   请先运行: kling_data/process_kling_data_fixed.py")
        exit(1)
    
    if not items_file.exists():
        print(f"❌ 错误: 找不到文件 {items_file}")
        print(f"   请先运行: kling_data/process_kling_data_fixed.py")
        exit(1)

    generate_sid_prediction_data(
        sequential_file=sequential_file,
        items_file=items_file,
        output_train=output_train,
        output_val=output_val,
        output_test=output_test,
    )
