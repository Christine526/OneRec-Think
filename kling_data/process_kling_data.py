#!/usr/bin/env python3
"""
Kling数据预处理脚本
将kling_data.tsv转换为OneRec-Think需要的格式

生成三个核心文件：
1. kling_items.json - 物品元数据（title, description, categories, sid）
2. kling_sequential.txt - 用户行为序列（user_id + item_ids）
3. kling_user_behaviors.json - 用户行为详情（包含行为类型、搜索词等富文本信息）
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
        return ast.literal_eval(semantic_id_str)
    except:
        return None


def format_semantic_id_to_sid(semantic_id_array):
    """
    将semantic_id数组转换为SID格式
    Kling数据是3维，Beauty数据是4维
    例如: [69, 142, 246] -> <|sid_begin|><s_a_69><s_b_142><s_c_246><|sid_end|>
    """
    if not semantic_id_array or len(semantic_id_array) == 0:
        return None
    
    prefixes = ['s_a', 's_b', 's_c']  # 3维，适配kling数据
    sid_tokens = []
    
    for i, val in enumerate(semantic_id_array[:3]):  # 最多取3个
        if i < len(prefixes):
            sid_tokens.append(f'<{prefixes[i]}_{val}>')
    
    return '<|sid_begin|>' + ''.join(sid_tokens) + '<|sid_end|>'


def extract_category(row):
    """
    从数据中提取类别信息
    content_type: 0=图片+视频, 1=图片, 2=视频
    kling_photo_type: 1=素材, 2=短片
    """
    # 基于content_type
    if pd.notna(row.get('content_type')):
        content_type_map = {
            '0': 'Image and Video Creation',
            '1': 'Image Creation',
            '2': 'Video Creation'
        }
        content_type = str(int(row['content_type']))  # 转为整数再转字符串
        category = content_type_map.get(content_type, f'Content Type {content_type}')
    else:
        category = 'General Creation'
    
    # 添加photo_type信息
    if pd.notna(row.get('kling_photo_type')):
        photo_type = int(row['kling_photo_type'])
        if photo_type == 1:
            category += ' > Material'  # 素材
        elif photo_type == 2:
            category += ' > Short Film'  # 短片
        else:
            category += f' > Type {photo_type}'
    
    return category


def create_item_metadata(df_raw, output_path):
    """
    创建物品元数据JSON (类似Beauty.pretrain.json)
    
    格式：
    {
        "item_id": {
            "title": "物品标题",
            "description": "物品描述(prompt)",
            "categories": "类别层级",
            "sid": "<|sid_begin|><s_a_X><s_b_Y><s_c_Z><|sid_end|>"
        },
        ...
    }
    """
    print("\n" + "="*60)
    print("📊 统计原始数据信息")
    print("="*60)
    
    # 统计行为类型分布（event_type: RECOMMEND/SEARCH/PRODUCE）
    if 'event_type' in df_raw.columns:
        print("\n📈 行为类型分布 (event_type):")
        event_counts = df_raw['event_type'].value_counts()
        
        # 按类型排序显示
        event_order = ['RECOMMEND', 'SEARCH', 'PRODUCE']
        for event_type in event_order:
            if event_type in event_counts:
                count = event_counts[event_type]
                pct = count/len(df_raw)*100
                print(f"  {event_type:12s}: {count:6,d} 条 ({pct:5.1f}%)")
    
    # 统计搜索查询内容（仅统计展示，暂未用于训练）
    if 'element_query_content' in df_raw.columns:
        search_with_query = df_raw['element_query_content'].notna().sum()
        total_search = (df_raw['event_type'] == 'SEARCH').sum() if 'event_type' in df_raw.columns else 0
        
        print("\n🔍 搜索场景统计 (element_query_content):")
        if total_search > 0:
            print(f"  SEARCH类型总数: {total_search:,} 条")
            print(f"  包含查询词: {search_with_query:,} 条 ({search_with_query/total_search*100:.1f}%)")
        else:
            print(f"  包含查询词的记录: {search_with_query:,} 条")
    
    print("\n" + "="*60)
    print("🔧 处理物品元数据")
    print("="*60)
    
    # 按kling_photo_id去重，保留最新的记录
    df_items = df_raw.sort_values('time_stamp').drop_duplicates(
        subset=['kling_photo_id'], keep='last'
    )
    
    print(f"去重前: {len(df_raw):,} 条记录")
    print(f"去重后: {len(df_items):,} 个唯一物品")
    
    items_dict = {}
    missing_sid_count = 0
    
    for idx, row in df_items.iterrows():
        item_id = str(row['kling_photo_id'])
        
        # 解析semantic_id
        semantic_id_array = parse_semantic_id(row['semantic_id'])
        if not semantic_id_array:
            missing_sid_count += 1
            continue
        
        # 转换为SID格式
        sid = format_semantic_id_to_sid(semantic_id_array)
        if not sid:
            missing_sid_count += 1
            continue
        
        # 提取类别
        categories = extract_category(row)
        
        # 使用prompt作为description，限制长度避免超长文本
        description = row['prompt'] if pd.notna(row['prompt']) else ''
        if len(description) > 1000:  # 限制字符数，QWen的token限制为max_length=4096
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
    
    print(f"成功处理: {len(items_dict):,} 个物品")
    print(f"缺失SID: {missing_sid_count:,} 个物品")
    
    # 保存为JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items_dict, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 物品元数据已保存到: {output_path}")
    
    return items_dict


def create_sequential_file(df_raw, output_path, min_sequence_length=3):
    """
    创建用户序列文件 (类似sequential_data_processed.txt)
    
    格式：每行一个用户的行为序列
    user_id item_id1 item_id2 item_id3 ...
    
    注意: 假设CSV中已经包含正向行为（在SQL中已筛选）
    
    Args:
        df_raw: 正向行为数据DataFrame
        output_path: 输出文件路径
        min_sequence_length: 最小序列长度（默认3，用于后续训练分割）
    """
    print("\n" + "="*60)
    print("📝 创建用户行为序列文件")
    print("="*60)
    print(f"总记录数: {len(df_raw):,} 条")
    
    # 检查是否有有效的semantic_id
    df_raw['semantic_id_parsed'] = df_raw['semantic_id'].apply(parse_semantic_id)
    df_positive = df_raw[df_raw['semantic_id_parsed'].notna()].copy()
    
    # 按用户和时间排序
    df_sorted = df_positive.sort_values(['user_id', 'time_stamp'])
    
    # 统计信息
    user_counts = df_sorted.groupby('user_id').size()
    total_users = len(user_counts)
    valid_users = (user_counts >= min_sequence_length).sum()
    
    print(f"总用户数: {total_users:,}")
    print(f"有效用户数 (行为≥{min_sequence_length}): {valid_users:,}")
    
    # 统计序列长度分布
    print("\n📊 序列长度分布:")
    length_bins = [0, 3, 5, 10, 20, 50, float('inf')]
    length_labels = ['1-2', '3-4', '5-9', '10-19', '20-49', '50+']
    user_counts_series = user_counts.reset_index(name='count')['count']
    length_dist = pd.cut(user_counts_series, bins=length_bins, labels=length_labels, right=False)
    for label, count in length_dist.value_counts().sort_index().items():
        pct = count / total_users * 100
        print(f"  {label:6s}: {count:6,d} 用户 ({pct:5.1f}%)")
    
    # 写入序列文件
    with open(output_path, 'w', encoding='utf-8') as f:
        for user_id, group in df_sorted.groupby('user_id'):
            item_ids = group['kling_photo_id'].astype(str).tolist()
            if len(item_ids) >= min_sequence_length:
                line = f"{user_id} {' '.join(item_ids)}\n"
                f.write(line)
    
    print(f"✅ 用户序列文件已保存到: {output_path}")
    
    return valid_users


def create_user_behaviors_file(df_raw, output_path):
    """
    创建用户行为详细信息文件
    包含每个交互的行为类型、搜索词等富文本信息
    
    这个文件用于生成富文本的Alignment训练数据(Interleaved User Persona Grounding)
    
    格式：
    {
        "user_id": [
            {
                "item_id": "xxx",
                "event_type": "RECOMMEND/SEARCH/PRODUCE",
                "behavior_type": "OPERATE/VIDEO_PLAY_FINISH/...",
                "behavior_subtype": "LIKE/COMMENT/...",
                "timestamp": "...",
                "element_query_content": "搜索词",
                "query_cnt": 搜索次数
            },
            ...
        ],
        ...
    }
    
    Args:
        df_raw: 原始行为数据DataFrame
        output_path: 输出JSON文件路径
    """
    print("\n" + "="*60)
    print("📋 创建用户行为详情文件")
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
    
    print(f"✅ 用户行为详情已保存到: {output_path}")
    print(f"总用户数: {len(user_behaviors):,}")
    
    return user_behaviors


def main():
    print("="*60)
    print("🚀 Kling数据预处理 - 生成OneRec-Think训练元数据")
    print("="*60)
    
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
            print(f"✓ 检测到数据文件: {input_file}\n")
            break
    
    items_output = Path("./kling_items.json")
    sequential_output = Path("./kling_sequential.txt")
    behaviors_output = Path("./kling_user_behaviors.json")
    
    # 检查输入文件
    if input_file is None:
        print(f"❌ 错误: 找不到输入文件，请确保以下文件之一存在:")
        for f in possible_files:
            print(f"  - {f}")
        print("\n提示: 请先运行 load_kling_data.py 从Hive获取数据")
        return
    
    # 读取CSV (尝试多种分隔符和编码)
    print(f"📥 读取数据文件: {input_file}")
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
            print(f"  ✓ 成功! 读取 {len(df):,} 条记录，{len(df.columns)} 列")
            break
        except (pd.errors.ParserError, TypeError) as e:
            print(f"    失败: {str(e)[:50]}...")
            continue
        except Exception as e:
            print(f"    失败: {str(e)[:50]}...")
            continue
    
    # 如果所有方式都失败
    if df is None or len(df) == 0:
        print(f"\n❌ 错误: 无法读取数据文件")
        print(f"建议: 请使用制表符(\\t)重新导出数据")
        return
    
    # 移除BOM（如果有）
    if df.columns[0].startswith('\ufeff'):
        df.columns = [col.replace('\ufeff', '') for col in df.columns]
        print(f"  ✓ 移除了UTF-8 BOM标记")
    
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
            print(f"  ✓ 已设置标准列名")
        else:
            print(f"  ⚠️  列数不匹配: 期望 {len(expected_columns)}，实际 {len(df.columns)}")
    
    # 清理列名
    df = clean_column_names(df)
    
    # 步骤1: 创建物品元数据
    items_dict = create_item_metadata(df, items_output)
    
    # 步骤2: 创建用户序列
    valid_users = create_sequential_file(df, sequential_output)
    
    # 步骤3: 创建用户行为详情（用于生成富文本Alignment数据）
    user_behaviors = create_user_behaviors_file(df, behaviors_output)
    
    print(f"\n" + "="*60)
    print(f"✅ 数据处理完成!")
    print(f"="*60)
    print(f"📦 输出文件:")
    print(f"  1. {items_output} ({len(items_dict):,} 个物品)")
    print(f"  2. {sequential_output} ({valid_users:,} 个用户)")
    print(f"  3. {behaviors_output} ({len(user_behaviors):,} 个用户)")
    print(f"\n📚 下一步: 运行以下脚本生成训练数据")
    print(f"  - generate_kling_RA_data.py (Alignment数据)")
    print(f"  - generate_kling_sid_prediction_data.py (SID预测数据)")
    print(f"  - generate_kling_training_data.py (Dense Captioning数据)")


if __name__ == "__main__":
    main()
