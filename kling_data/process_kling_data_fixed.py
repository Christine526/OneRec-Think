#!/usr/bin/env python3
"""
Kling数据预处理脚本 (修正版)
将kling_data.csv转换为OneRec-Think需要的格式

主要修正：
1. ✅ 修正SID格式：从3维扩展为4维 (s_a, s_b, s_c, s_d)
2. ✅ 使用content_type作为第4维，保留业务语义
3. ✅ 完善错误处理和数据验证
"""

import pandas as pd
import json
from pathlib import Path
import ast
import warnings
warnings.filterwarnings('ignore')


def clean_column_names(df):
    """清理列名，移除前缀"""
    df.columns = [col.split('.')[-1] for col in df.columns]
    return df


def parse_semantic_id(semantic_id_str):
    """
    解析semantic_id字符串为数组
    例如: ' [69,142,246] ' -> [69, 142, 246]
    """
    if pd.isna(semantic_id_str) or semantic_id_str == '':
        return None
    try:
        # 去除空格并解析
        semantic_id_str = str(semantic_id_str).strip()
        result = ast.literal_eval(semantic_id_str)
        # 确保是列表且至少有3个元素
        if isinstance(result, list) and len(result) >= 3:
            return result
        return None
    except:
        return None


def format_semantic_id_to_sid(semantic_id_array, content_type=0):
    """
    将3维semantic_id扩展为4维SID格式（OneRec-Think要求）
    
    修正要点：
    - 原版使用3维：<s_a><s_b><s_c>
    - 修正后使用4维：<s_a><s_b><s_c><s_d>
    - 第4维使用content_type，有业务含义（0=图片+视频, 1=图片, 2=视频）
    
    Args:
        semantic_id_array: [a, b, c] 3维语义ID
        content_type: 内容类型 (0/1/2)
    
    Returns:
        例如: [69, 142, 246] + content_type=0 -> 
             <|sid_begin|><s_a_69><s_b_142><s_c_246><s_d_0><|sid_end|>
    """
    if not semantic_id_array or len(semantic_id_array) < 3:
        return None
    
    # 取前3个值
    a, b, c = semantic_id_array[0:3]
    
    # 验证范围（OneRec-Think使用0-255）
    if not all(0 <= x <= 255 for x in [a, b, c]):
        print(f"⚠️  警告: semantic_id值超出范围[0,255]: [{a}, {b}, {c}]")
        return None
    
    # 第4维使用content_type (0/1/2)
    if pd.notna(content_type):
        try:
            d = int(content_type)
            # 确保d也在合理范围
            if d < 0 or d > 255:
                d = 0
        except:
            d = 0
    else:
        d = 0
    
    # 构造4维SID（符合OneRec-Think格式）
    sid = f'<|sid_begin|><s_a_{a}><s_b_{b}><s_c_{c}><s_d_{d}><|sid_end|>'
    return sid


def extract_category(row):
    """
    从数据中提取类别信息
    content_type: 0=图片+视频, 1=图片, 2=视频
    kling_photo_type: 1=素材, 2=短片
    """
    # 基于content_type
    if pd.notna(row.get('content_type')):
        try:
            content_type = int(float(row['content_type']))
            content_type_map = {
                0: 'Image and Video Creation',
                1: 'Image Creation',
                2: 'Video Creation'
            }
            category = content_type_map.get(content_type, f'Content Type {content_type}')
        except:
            category = 'General Creation'
    else:
        category = 'General Creation'
    
    # 添加photo_type信息
    if pd.notna(row.get('kling_photo_type')):
        try:
            photo_type = int(float(row['kling_photo_type']))
            if photo_type == 1:
                category += ' > Material'  # 素材
            elif photo_type == 2:
                category += ' > Short Film'  # 短片
            else:
                category += f' > Type {photo_type}'
        except:
            pass
    
    return category


def create_item_metadata(df_raw, output_path):
    """
    创建物品元数据JSON (类似Beauty.pretrain.json)
    
    格式要求：
    {
        "item_id": {
            "title": "...",
            "description": "...",
            "categories": "...",
            "sid": "<|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|>"  # 4维！
        }
    }
    """
    print("="*60)
    print("📊 创建物品元数据...")
    print("="*60)
    
    # 统计行为类型分布（event_type: RECOMMEND/SEARCH/PRODUCE）
    if 'event_type' in df_raw.columns:
        event_counts = df_raw['event_type'].value_counts()
        print("\n📌 行为类型分布:")
        
        # 按类型排序显示
        event_order = ['RECOMMEND', 'SEARCH', 'PRODUCE']
        for event_type in event_order:
            if event_type in event_counts:
                count = event_counts[event_type]
                pct = count/len(df_raw)*100
                print(f"  {event_type:12s}: {count:5d} 条 ({pct:5.1f}%)")
    
    # 统计搜索查询内容（仅统计展示，暂未用于训练）
    if 'element_query_content' in df_raw.columns:
        search_with_query = df_raw['element_query_content'].notna().sum()
        total_search = (df_raw['event_type'] == 'SEARCH').sum() if 'event_type' in df_raw.columns else 0
        
        print("\n🔍 搜索场景统计 (element_query_content):")
        if total_search > 0:
            print(f"  SEARCH类型总数: {total_search} 条")
            print(f"  包含查询词: {search_with_query} 条 ({search_with_query/total_search*100:.1f}%)")
        else:
            print(f"  包含查询词的记录: {search_with_query} 条")
    
    # 按kling_photo_id去重，保留最新的记录
    df_items = df_raw.sort_values('time_stamp').drop_duplicates(
        subset=['kling_photo_id'], keep='last'
    )
    
    print(f"\n📦 物品去重:")
    print(f"  去重前: {len(df_raw)} 条记录")
    print(f"  去重后: {len(df_items)} 个唯一物品")
    
    items_dict = {}
    missing_sid_count = 0
    invalid_sid_count = 0
    
    for idx, row in df_items.iterrows():
        item_id = str(row['kling_photo_id'])
        
        # 解析semantic_id
        semantic_id_array = parse_semantic_id(row['semantic_id'])
        if not semantic_id_array:
            missing_sid_count += 1
            continue
        
        # 转换为4维SID格式（关键修正）
        content_type = row.get('content_type', 0)
        sid = format_semantic_id_to_sid(semantic_id_array, content_type)
        if not sid:
            invalid_sid_count += 1
            continue
        
        # 提取类别
        categories = extract_category(row)
        
        description = row['prompt'] if pd.notna(row['prompt']) else ''
        # 添加长度限制，避免超长文本, QWen的token限制为max_length=4096
        if len(description) > 1000:  # 限制字符数
            description = description[:1000] + '...'
        
        # 使用title或introduction作为标题
        title = row['title'] if pd.notna(row['title']) else ''
        if not title and pd.notna(row['introduction']):
            title = row['introduction'][:100]  # 截取前100字符
        if not title:
            title = description[:100] if description else f'Item {item_id}'
        
        items_dict[item_id] = {
            'title': title,
            'description': description,
            'categories': categories,
            'sid': sid
        }
    
    print(f"\n✅ 处理结果:")
    print(f"  成功处理: {len(items_dict)} 个物品")
    print(f"  缺失SID: {missing_sid_count} 个物品")
    print(f"  无效SID: {invalid_sid_count} 个物品")
    
    # 验证SID格式
    sample_sids = list(items_dict.values())[:3]
    print(f"\n🔍 SID格式验证（前3个样例）:")
    for i, item in enumerate(sample_sids):
        sid = item['sid']
        # 检查是否包含4个维度
        has_4_dims = all(f'<s_{dim}_' in sid for dim in ['a', 'b', 'c', 'd'])
        status = "✅" if has_4_dims else "❌"
        print(f"  {status} [{i+1}] {sid}")
    
    # 保存为JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items_dict, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 物品元数据已保存到: {output_path}")
    
    return items_dict


def create_sequential_file(df_raw, output_path, min_sequence_length=3):
    """
    创建用户序列文件 (类似sequential_data_processed.txt)
    
    格式: user_id item_id1 item_id2 item_id3 ...
    
    注意: 假设CSV中已经包含正向行为（在SQL中已筛选）
    
    Args:
        df_raw: 正向行为数据DataFrame
        output_path: 输出文件路径
        min_sequence_length: 最小序列长度
    """
    print("\n" + "="*60)
    print("📝 创建用户序列文件...")
    print("="*60)
    
    print(f"总记录数: {len(df_raw)} 条")
    
    # 检查是否有有效的semantic_id
    df_raw['semantic_id_parsed'] = df_raw['semantic_id'].apply(parse_semantic_id)
    df_positive = df_raw[df_raw['semantic_id_parsed'].notna()].copy()
    
    print(f"有效semantic_id记录: {len(df_positive)} 条")
    
    # 按用户和时间排序
    df_sorted = df_positive.sort_values(['user_id', 'time_stamp'])
    
    # 统计信息
    user_counts = df_sorted.groupby('user_id').size()
    total_users = len(user_counts)
    valid_users = (user_counts >= min_sequence_length).sum()
    
    print(f"\n📊 用户统计:")
    print(f"  总用户数: {total_users}")
    print(f"  序列长度 >= {min_sequence_length} 的用户: {valid_users}")
    print(f"  平均序列长度: {user_counts.mean():.2f}")
    print(f"  中位序列长度: {user_counts.median():.0f}")
    print(f"  最长序列: {user_counts.max()}")
    
    # 写入序列文件
    written_count = 0
    with open(output_path, 'w', encoding='utf-8') as f:
        for user_id, group in df_sorted.groupby('user_id'):
            item_ids = group['kling_photo_id'].astype(str).tolist()
            if len(item_ids) >= min_sequence_length:
                line = f"{user_id} {' '.join(item_ids)}\n"
                f.write(line)
                written_count += 1
    
    print(f"\n✅ 成功写入 {written_count} 个用户序列")
    print(f"💾 文件已保存到: {output_path}")
    
    return valid_users


def create_user_behaviors_file(df_raw, output_path):
    """
    创建用户行为详细信息文件，包含每个交互的行为类型
    这个文件用于生成富文本的Alignment训练数据
    
    Args:
        df_raw: 原始行为数据DataFrame
        output_path: 输出JSON文件路径
    """
    print("\n" + "="*60)
    print("📋 创建用户行为详情文件...")
    print("="*60)
    
    # 检查是否有有效的semantic_id
    df_raw['semantic_id_parsed'] = df_raw['semantic_id'].apply(parse_semantic_id)
    df_positive = df_raw[df_raw['semantic_id_parsed'].notna()].copy()
    
    # 按用户和时间排序
    df_sorted = df_positive.sort_values(['user_id', 'time_stamp'])
    
    user_behaviors = {}
    
    for user_id, group in df_sorted.groupby('user_id'):
        behaviors = []
        
        for _, row in group.iterrows():
            behavior_info = {
                'item_id': str(row['kling_photo_id']),
                'event_type': row['event_type'] if pd.notna(row.get('event_type')) else 'UNKNOWN',
                'behavior_type': row['behavior_type'] if pd.notna(row.get('behavior_type')) else '',
                'behavior_subtype': row['behavior_subtype'] if pd.notna(row.get('behavior_subtype')) else '',
                'timestamp': str(row['time_stamp']) if pd.notna(row.get('time_stamp')) else '',
                'element_query_content': row['element_query_content'] if pd.notna(row.get('element_query_content')) else '',
                'query_cnt': int(row['query_cnt']) if pd.notna(row.get('query_cnt')) else 0
            }
            behaviors.append(behavior_info)
        
        user_behaviors[str(user_id)] = behaviors
    
    # 保存为JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(user_behaviors, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 总用户数: {len(user_behaviors)}")
    print(f"💾 文件已保存到: {output_path}")
    
    return user_behaviors


def main():
    print("\n" + "🚀"*30)
    print("Kling数据处理脚本 (OneRec-Think格式)")
    print("修正版本：支持4维SID格式")
    print("🚀"*30 + "\n")
    
    # 文件路径（按优先级检查）
    possible_files = [
        Path("./kling_data_fixed.tsv"),  # 修复后的TSV（优先）
        Path("./kling_data.tsv"),        # TSV格式（制表符分隔）
        Path("./kling_data_fixed.csv"),  # 修复后的CSV（备选）
        Path("./kling_data.csv"),        # CSV格式（逗号分隔，备选）
    ]
    
    input_file = None
    for f in possible_files:
        if f.exists():
            input_file = f
            print(f"✅ 检测到数据文件: {input_file}\n")
            break
    
    items_output = Path("./kling_items.json")
    sequential_output = Path("./kling_sequential.txt")
    behaviors_output = Path("./kling_user_behaviors.json")
    
    # 检查输入文件
    if input_file is None:
        print(f"❌ 错误: 找不到输入文件")
        print(f"\n请确保以下文件之一存在:")
        for f in possible_files:
            print(f"  - {f}")
        print(f"\n提示：如果从Hive导出数据，请使用制表符(\\t)作为分隔符")
        return
    
    # 读取CSV (尝试多种分隔符和编码)
    print(f"📖 读取数据文件: {input_file}")
    df = None
    
    # 尝试多种读取方式
    attempts = [
        # 1. 制表符分隔（最常见的解决方案）
        {'sep': '\t', 'encoding': 'utf-8-sig', 'engine': 'python', 'desc': '制表符分隔'},
        # 2. 标准CSV
        {'sep': ',', 'encoding': 'utf-8-sig', 'desc': '标准CSV'},
        # 3. Python引擎 + 制表符
        {'sep': '\t', 'encoding': 'utf-8-sig', 'engine': 'python', 'on_bad_lines': 'skip', 'desc': '制表符(跳过坏行)'},
        # 4. Python引擎 + 逗号（宽松模式）
        {'sep': ',', 'encoding': 'utf-8-sig', 'engine': 'python', 'on_bad_lines': 'skip', 'quoting': 3, 'desc': '逗号分隔(跳过坏行)'},
    ]
    
    for i, params in enumerate(attempts, 1):
        desc = params.pop('desc')
        try:
            print(f"  尝试方式 {i}: {desc}")
            df = pd.read_csv(input_file, **params)
            print(f"  ✅ 成功! 读取 {len(df)} 条记录，{len(df.columns)} 列")
            break
        except (pd.errors.ParserError, TypeError) as e:
            print(f"    ❌ 失败: {str(e)[:50]}...")
            continue
        except Exception as e:
            print(f"    ❌ 失败: {str(e)[:50]}...")
            continue
    
    # 如果所有方式都失败
    if df is None or len(df) == 0:
        print(f"\n❌ 错误: 无法读取数据文件")
        print(f"请使用制表符(\\t)重新导出数据")
        return
    
    # 移除BOM（如果有）
    if df.columns[0].startswith('\ufeff'):
        df.columns = [col.replace('\ufeff', '') for col in df.columns]
        print(f"  ✅ 移除了UTF-8 BOM标记")
    
    # 检查是否有表头（如果第一行全是数字，说明没有表头）
    first_row = df.iloc[0]
    if all(str(val).replace('.', '').replace('-', '').replace(':', '').replace(' ', '').isdigit() or pd.isna(val) for val in first_row[:3]):
        print(f"  ⚠️  检测到文件可能没有表头，设置标准列名...")
        expected_columns = [
            'user_id', 'kling_photo_id', 'kling_photo_type', 'event_type',
            'behavior_type', 'behavior_subtype', 'time_stamp', 'content_type',
            'prompt', 'title', 'introduction', 'element_query_content',
            'query_cnt', 'semantic_id'
        ]
        if len(df.columns) == len(expected_columns):
            df.columns = expected_columns
            print(f"  ✅ 已设置标准列名")
        else:
            print(f"  ⚠️  列数不匹配: 期望 {len(expected_columns)}，实际 {len(df.columns)}")
    
    # 清理列名
    df = clean_column_names(df)
    
    print(f"\n📋 数据列: {list(df.columns)}")
    
    # 步骤1: 创建物品元数据
    items_dict = create_item_metadata(df, items_output)
    
    # 步骤2: 创建用户序列
    valid_users = create_sequential_file(df, sequential_output)
    
    # 步骤3: 创建用户行为详情（用于生成富文本Alignment数据）
    user_behaviors = create_user_behaviors_file(df, behaviors_output)
    
    print(f"\n" + "="*60)
    print(f"✅ 数据处理完成!")
    print(f"="*60)
    print(f"\n📦 输出文件:")
    print(f"  1. 物品元数据: {items_output}")
    print(f"     - 共 {len(items_dict)} 个物品")
    print(f"     - 格式: OneRec-Think兼容 (4维SID)")
    print(f"\n  2. 用户序列: {sequential_output}")
    print(f"     - 共 {valid_users} 个用户")
    print(f"     - 格式: user_id item_id1 item_id2 ...")
    print(f"\n  3. 用户行为详情: {behaviors_output}")
    print(f"     - 共 {len(user_behaviors)} 个用户")
    print(f"     - 包含行为类型、时间戳等详细信息")
    
    print(f"\n🎯 下一步:")
    print(f"  1. 验证SID格式: 检查 {items_output} 中的SID是否为4维")
    print(f"  2. 生成训练数据: 运行 data/generate_*_data_kling.py")
    print(f"  3. 开始训练: 运行 train/run_training_stage*.sh")
    print(f"\n详细说明请查看: kling_data_analysis.md\n")


if __name__ == "__main__":
    main()
