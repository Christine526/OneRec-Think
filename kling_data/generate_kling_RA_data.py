#!/usr/bin/env python3
"""
Kling数据 - Interleaved User Persona Grounding (RA) 训练数据生成脚本

对应论文附录A.3.1中的任务1：Interleaved User Persona Grounding
将用户画像与物品交织，生成富文本描述，包含行为类型、搜索词等信息

输入文件:
- kling_items.json: 物品元数据
- kling_sequential.txt: 用户行为序列  
- kling_user_behaviors.json: 用户行为详情

输出文件:
- training_RA_train.parquet
- training_RA_val.parquet
- training_RA_test.parquet
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

import pandas as pd


def get_behavior_description(behavior: dict, item_info: dict) -> str:
    """
    根据Kling数据的行为类型生成富文本描述
    
    Kling数据结构：
    - event_type: RECOMMEND/SEARCH/PRODUCE
    - behavior_type: OPERATE/VIDEO_PLAY_FINISH/LONG_PLAY/SHORT_PLAY (PRODUCE场景下为null)
    - behavior_subtype: 只有behavior_type='OPERATE'时才有值
      - LIKE, UNLIKE, COMMENT, SHARE, SAME_STYLE, REPORT, LARGE(点击)
    
    Args:
        behavior: 行为信息字典
        item_info: 物品元数据
    
    Returns:
        格式化的行为描述
    """
    event_type = behavior.get('event_type', 'UNKNOWN')
    behavior_type = behavior.get('behavior_type', '')
    behavior_subtype = behavior.get('behavior_subtype', '')
    query_content = behavior.get('element_query_content', '')
    query_cnt = behavior.get('query_cnt', 0)
    
    sid = item_info.get('sid', '')
    title = item_info.get('title', '')
    categories = item_info.get('categories', '')
    
    # 1. 确定行为动词
    action = 'interacted with'  # 默认
    
    if event_type == 'PRODUCE':
        # 生产场景：behavior_type和behavior_subtype都是null
        action = 'created'
    elif behavior_type == 'OPERATE':
        # 操作行为，根据behavior_subtype细分
        subtype_action_map = {
            'LIKE': 'liked',
            'UNLIKE': 'unliked',
            'COMMENT': 'commented on',
            'SHARE': 'shared',
            'SAME_STYLE': 'used same style for',
            'REPORT': 'reported',
            'LARGE': 'clicked'  # LARGE才是点击
        }
        action = subtype_action_map.get(behavior_subtype, 'interacted with')
    elif behavior_type == 'VIDEO_PLAY_FINISH':
        action = 'finished watching'
    elif behavior_type == 'LONG_PLAY':
        action = 'watched for a long time'
    elif behavior_type == 'SHORT_PLAY':
        action = 'browsed'
    
    # 2. 构建基本描述
    desc_parts = [action, 'item', sid]
    
    # 3. 添加标题和类别
    if title:
        desc_parts.extend([', its title is', f'"{title}"'])
    if categories:
        desc_parts.extend([', its categories are', f'"{categories}"'])
    
    # 4. 添加上下文信息
    context_parts = []
    
    # 搜索场景：添加搜索词和搜索次数
    if event_type == 'SEARCH' and query_content:
        if query_cnt and int(query_cnt) > 1:
            context_parts.append(f'searched for "{query_content}" {query_cnt} times')
        else:
            context_parts.append(f'searched for "{query_content}"')
    
    # 推荐场景
    elif event_type == 'RECOMMEND':
        context_parts.append('from recommendations')
    
    # 生产场景
    elif event_type == 'PRODUCE':
        context_parts.append('created by user')
    
    # 5. 组合完整描述
    full_desc = ' '.join(desc_parts)
    if context_parts:
        full_desc += ' (' + ', '.join(context_parts) + ')'
    
    return full_desc


def load_kling_items(items_file: Path) -> dict:
    """加载Kling物品元数据"""
    print(f"加载物品元数据: {items_file}")
    with items_file.open("r", encoding="utf-8") as f:
        items = json.load(f)
    print(f"物品数量: {len(items):,}")
    return items


def load_user_behaviors(behaviors_file: Path) -> dict:
    """加载用户行为详情"""
    print(f"加载用户行为详情: {behaviors_file}")
    with behaviors_file.open("r", encoding="utf-8") as f:
        behaviors = json.load(f)
    print(f"用户数量: {len(behaviors):,}")
    return behaviors


def build_rich_description(
    item_ids: list[str],
    user_id: str,
    kling_items: dict,
    user_behaviors: dict,
) -> list[str]:
    """
    构建富文本用户画像描述
    
    Args:
        item_ids: 物品ID列表
        user_id: 用户ID
        kling_items: 物品元数据字典
        user_behaviors: 用户行为详情字典
    
    Returns:
        物品描述列表
    """
    item_descriptions = []
    
    # 获取该用户的行为序列
    behaviors = user_behaviors.get(str(user_id), [])
    
    # 创建item_id到行为的映射（取最后一次交互）
    item_to_behavior = {}
    for behavior in behaviors:
        item_id = behavior['item_id']
        item_to_behavior[item_id] = behavior  # 后面的会覆盖前面的
    
    # 为每个item生成描述
    for item_id in item_ids:
        item_info = kling_items.get(item_id)
        if not item_info:
            continue
        
        sid = item_info.get('sid')
        if not sid:
            continue
        
        # 获取该item的行为信息
        behavior = item_to_behavior.get(item_id)
        
        if behavior:
            # 有行为详情，生成富文本描述
            desc = get_behavior_description(behavior, item_info)
        else:
            # 没有行为详情，使用基本格式
            title = item_info.get('title', '')
            categories = item_info.get('categories', '')
            desc_parts = ['interacted with item', sid]
            if title:
                desc_parts.extend([', its title is', f'"{title}"'])
            if categories:
                desc_parts.extend([', its categories are', f'"{categories}"'])
            desc = ' '.join(desc_parts)
        
        item_descriptions.append(desc)
    
    return item_descriptions


def build_dataset_entry(
    user_id: str,
    item_ids: list[str],
    tail_remove_count: int,
    kling_items: dict,
    user_behaviors: dict,
) -> dict | None:
    """
    构建单个训练样本
    
    Args:
        user_id: 用户ID
        item_ids: 物品ID列表
        tail_remove_count: 尾部移除数量（train=2, val=1, test=0）
        kling_items: 物品元数据
        user_behaviors: 用户行为详情
    
    Returns:
        训练样本字典
    """
    # 序列长度检查
    if len(item_ids) <= tail_remove_count + 1:
        return None
    
    # 分割序列
    candidate_ids = (
        item_ids[: len(item_ids) - tail_remove_count]
        if tail_remove_count > 0
        else item_ids
    )
    
    if len(candidate_ids) < 2:
        return None
    
    # groundtruth是最后一个物品
    groundtruth_id = candidate_ids[-1]
    description_ids = candidate_ids[:-1]
    
    if not description_ids:
        return None
    
    # 获取groundtruth物品信息
    groundtruth_item = kling_items.get(groundtruth_id)
    if not groundtruth_item or not groundtruth_item.get('sid'):
        return None
    
    # 构建富文本描述
    item_descriptions = build_rich_description(
        description_ids, user_id, kling_items, user_behaviors
    )
    
    if not item_descriptions:
        return None
    
    # 组装完整描述
    description = "The user has " + "; ".join(item_descriptions) + ";"
    
    return {
        "user_id": user_id,
        "description": description,
        "groundtruth": groundtruth_item["sid"],
        "title": groundtruth_item.get("title", ""),
        "categories": groundtruth_item.get("categories", ""),
    }


def generate_kling_ra_data(
    sequential_file: Path,
    items_file: Path,
    behaviors_file: Path,
    output_train: Path,
    output_val: Path,
    output_test: Path,
) -> None:
    """生成Kling RA训练数据"""
    
    # 加载数据
    kling_items = load_kling_items(items_file)
    user_behaviors = load_user_behaviors(behaviors_file)
    
    print(f"\n加载用户序列文件: {sequential_file}")
    with sequential_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"序列数量: {len(lines):,}")
    
    # 统计信息
    stats = {
        'total_users': 0,
        'event_types': defaultdict(int),
        'behavior_types': defaultdict(int),
        'behavior_subtypes': defaultdict(int),
        'with_search_query': 0,
        'produce_events': 0,
    }
    
    # 统计行为类型分布
    print("\n统计行为类型分布...")
    for user_id, behaviors in user_behaviors.items():
        for behavior in behaviors:
            event_type = behavior.get('event_type', 'UNKNOWN')
            behavior_type = behavior.get('behavior_type', '') or 'NULL'
            behavior_subtype = behavior.get('behavior_subtype', '') or 'NULL'
            
            stats['event_types'][event_type] += 1
            stats['behavior_types'][behavior_type] += 1
            stats['behavior_subtypes'][behavior_subtype] += 1
            
            if event_type == 'SEARCH' and behavior.get('element_query_content'):
                stats['with_search_query'] += 1
            if event_type == 'PRODUCE':
                stats['produce_events'] += 1
    
    print("\n📈 事件类型分布:")
    for event_type in ['RECOMMEND', 'SEARCH', 'PRODUCE', 'UNKNOWN']:
        count = stats['event_types'].get(event_type, 0)
        if count > 0:
            print(f"  {event_type:12s}: {count:8,d} 次")
    
    print("\n📊 行为类型分布:")
    sorted_behaviors = sorted(
        stats['behavior_types'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    for behavior_type, count in sorted_behaviors:
        print(f"  {behavior_type:20s}: {count:8,d} 次")
    
    print("\n📝 操作子类型分布 (behavior_subtype):")
    sorted_subtypes = sorted(
        stats['behavior_subtypes'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    for subtype, count in sorted_subtypes:
        print(f"  {subtype:20s}: {count:8,d} 次")
    
    print(f"\n🔍 搜索场景统计:")
    search_total = stats['event_types'].get('SEARCH', 0)
    if search_total > 0:
        print(f"  总搜索事件: {search_total:,} 次")
        print(f"  包含查询词: {stats['with_search_query']:,} 次 ({stats['with_search_query']/search_total*100:.1f}%)")
    print(f"  生产事件: {stats['produce_events']:,} 次")
    
    # 生成训练数据
    print("\n生成训练数据...")
    train_rows: list[dict] = []
    val_rows: list[dict] = []
    test_rows: list[dict] = []
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        elements = line.split()
        if len(elements) <= 1:
            continue
        
        user_id = elements[0]
        item_ids = elements[1:]
        stats['total_users'] += 1
        
        # 生成train/val/test样本
        entry_train = build_dataset_entry(
            user_id, item_ids, 2, kling_items, user_behaviors
        )
        if entry_train:
            train_rows.append(entry_train)
        
        entry_val = build_dataset_entry(
            user_id, item_ids, 1, kling_items, user_behaviors
        )
        if entry_val:
            val_rows.append(entry_val)
        
        entry_test = build_dataset_entry(
            user_id, item_ids, 0, kling_items, user_behaviors
        )
        if entry_test:
            test_rows.append(entry_test)
        
        if (idx + 1) % 1000 == 0:
            print(f"  已处理 {idx + 1:,} 个用户...")
    
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
            print(f"    标题: {row['title'][:50]}...")
            print(f"    类别: {row['categories']}")
    
    preview(df_train, "训练集")
    preview(df_val, "验证集")
    
    print("\n✨ 数据生成完成!")


if __name__ == "__main__":
    # 文件路径
    sequential_file = Path("./kling_sequential.txt")
    items_file = Path("./kling_items.json")
    behaviors_file = Path("./kling_user_behaviors.json")
    
    output_train = Path("./training_RA_train.parquet")
    output_val = Path("./training_RA_val.parquet")
    output_test = Path("./training_RA_test.parquet")
    
    # 检查输入文件
    for file in [sequential_file, items_file, behaviors_file]:
        if not file.exists():
            print(f"❌ 错误: 文件不存在: {file}")
            exit(1)
    
    # 生成数据
    generate_kling_ra_data(
        sequential_file=sequential_file,
        items_file=items_file,
        behaviors_file=behaviors_file,
        output_train=output_train,
        output_val=output_val,
        output_test=output_test,
    )
