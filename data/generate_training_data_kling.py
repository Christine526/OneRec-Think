#!/usr/bin/env python3
"""
Kling数据 - Alignment训练数据生成脚本

用途: Stage 1 训练 - Itemix Alignment
让模型学习物品的SID、标题和类别之间的映射关系

输入:
  - kling_items.json (物品元数据, 4维SID)
  - kling_sequential.txt (用户序列)

输出:
  - training_align_data_kling_train.parquet
  - training_align_data_kling_val.parquet
  - training_align_data_kling_test.parquet

数据格式:
  {
      'user_id': '123',
      'description': 'The user has purchased the following items: <|sid_begin|>...<|sid_end|>, its title is "...", its categories are "..."; ...'
  }
"""

import json
import pandas as pd
from pathlib import Path


def generate_training_data(sequential_file, items_file, output_train_file, output_val_file, output_test_file):
    """生成Alignment训练数据（Stage 1）"""
    
    print("="*60)
    print("🎯 生成Kling Alignment训练数据 (Stage 1)")
    print("="*60)
    
    try:
        # 加载物品元数据
        print(f"\n📖 加载物品元数据: {items_file}")
        with open(items_file, 'r', encoding='utf-8') as f:
            items = json.load(f)
        print(f"   ✅ 加载了 {len(items)} 个物品")
        
        # 验证SID格式（应该是4维）
        sample_item = list(items.values())[0]
        sample_sid = sample_item['sid']
        has_4_dims = all(f'<s_{dim}_' in sample_sid for dim in ['a', 'b', 'c', 'd'])
        if not has_4_dims:
            print(f"   ⚠️  警告: SID格式可能不正确（应该是4维）")
            print(f"   示例: {sample_sid}")
        else:
            print(f"   ✅ SID格式验证通过（4维）")

        # 加载用户序列
        print(f"\n📖 加载用户序列: {sequential_file}")
        with open(sequential_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"   ✅ 加载了 {len(lines)} 个用户序列")

        training_data_train = []
        training_data_val = []
        training_data_test = []
        missing_items_count = 0

        def build_description(item_ids, user_id):
            """构建物品描述文本"""
            item_descriptions = []
            local_missing_count = 0

            for item_id in item_ids:
                item_info = items.get(item_id)
                if not item_info:
                    local_missing_count += 1
                    continue

                sid = item_info.get('sid', '')
                title = item_info.get('title', '')
                categories = item_info.get('categories', '')

                if sid and title and categories:
                    # 格式: SID + title + categories
                    item_desc = f'{sid}, its title is "{title}", its categories are "{categories}"'
                    item_descriptions.append(item_desc)
                else:
                    local_missing_count += 1

            return item_descriptions, local_missing_count

        print(f"\n🔄 处理用户序列...")
        processed_count = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            elements = line.split()
            if len(elements) <= 1:
                continue

            user_id = elements[0]
            item_ids = elements[1:]

            # Test集: 使用完整序列
            full_item_descriptions, missing_count_full = build_description(item_ids, user_id)
            missing_items_count += missing_count_full

            if full_item_descriptions:
                test_description = "The user has purchased the following items: " + "; ".join(full_item_descriptions) + ";"
                training_data_test.append({
                    'user_id': user_id,
                    'description': test_description
                })

            # Val集: 去掉最后1个item
            if len(item_ids) > 1:
                val_item_ids = item_ids[:-1]
                val_item_descriptions, missing_count_val = build_description(val_item_ids, user_id)
                missing_items_count += missing_count_val

                if val_item_descriptions:
                    val_description = "The user has purchased the following items: " + "; ".join(val_item_descriptions) + ";"
                    training_data_val.append({
                        'user_id': user_id,
                        'description': val_description
                    })

            # Train集: 去掉最后2个item
            if len(item_ids) > 2:
                train_item_ids = item_ids[:-2]
                train_item_descriptions, missing_count_train = build_description(train_item_ids, user_id)
                missing_items_count += missing_count_train

                if train_item_descriptions:
                    train_description = "The user has purchased the following items: " + "; ".join(train_item_descriptions) + ";"
                    training_data_train.append({
                        'user_id': user_id,
                        'description': train_description
                    })
            
            processed_count += 1
            if processed_count % 1000 == 0:
                print(f"   已处理 {processed_count}/{len(lines)} 个用户...")

        print(f"   ✅ 完成处理 {processed_count} 个用户")
        print(f"   ⚠️  缺失物品数: {missing_items_count}")

        # 创建DataFrame
        print(f"\n📊 创建DataFrame...")
        df_train = pd.DataFrame(training_data_train)
        df_val = pd.DataFrame(training_data_val)
        df_test = pd.DataFrame(training_data_test)

        print(f"   Train集: {len(df_train)} 条")
        print(f"   Val集:   {len(df_val)} 条")
        print(f"   Test集:  {len(df_test)} 条")

        # 保存parquet文件
        print(f"\n💾 保存parquet文件...")
        df_train.to_parquet(output_train_file, engine='pyarrow', index=False)
        print(f"   ✅ {output_train_file}")
        
        df_val.to_parquet(output_val_file, engine='pyarrow', index=False)
        print(f"   ✅ {output_val_file}")
        
        df_test.to_parquet(output_test_file, engine='pyarrow', index=False)
        print(f"   ✅ {output_test_file}")

        # 显示示例
        print(f"\n📝 数据示例 (Train集前2条):")
        for i, row in df_train.head(2).iterrows():
            print(f"\n   [{i+1}] User: {row['user_id']}")
            desc = row['description']
            if len(desc) > 200:
                print(f"       Description: {desc[:200]}...")
            else:
                print(f"       Description: {desc}")
        
        print(f"\n{'='*60}")
        print(f"✅ Alignment训练数据生成完成!")
        print(f"{'='*60}")
        print(f"\n🎯 下一步:")
        print(f"   运行训练脚本: train/run_training_stage1.sh")
        print(f"   或使用: train/scripts/train_beauty_align.py\n")

    except Exception as e:
        print(f"\n❌ 生成训练数据失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 默认路径（可根据实际情况修改）
    sequential_file = "../kling_data/kling_sequential.txt"
    items_file = "../kling_data/kling_items.json"
    
    output_train_file = "./training_align_data_kling_train.parquet"
    output_val_file = "./training_align_data_kling_val.parquet"
    output_test_file = "./training_align_data_kling_test.parquet"
    
    # 检查输入文件是否存在
    if not Path(sequential_file).exists():
        print(f"❌ 错误: 找不到文件 {sequential_file}")
        print(f"   请先运行: kling_data/process_kling_data_fixed.py")
        exit(1)
    
    if not Path(items_file).exists():
        print(f"❌ 错误: 找不到文件 {items_file}")
        print(f"   请先运行: kling_data/process_kling_data_fixed.py")
        exit(1)

    generate_training_data(
        sequential_file,
        items_file,
        output_train_file,
        output_val_file,
        output_test_file
    )
