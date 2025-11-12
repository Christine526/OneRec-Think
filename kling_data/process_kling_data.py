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
    例如: [69, 142, 246] -> <|sid_begin|><s_a_69><s_b_142><s_c_246><|sid_end|>
    """
    if not semantic_id_array or len(semantic_id_array) == 0:
        return None
    
    prefixes = ['s_a', 's_b', 's_c']
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
    
    # 统计行为类型分布（event_type: RECOMMEND/SEARCH/PRODUCE）
    print("\n事件类型分布:")
    if 'event_type' in df_raw.columns:
        event_counts = df_raw['event_type'].value_counts()
        
        # 按类型排序显示
        event_order = ['RECOMMEND', 'SEARCH', 'PRODUCE']
        for event_type in event_order:
            if event_type in event_counts:
                count = event_counts[event_type]
                pct = count/len(df_raw)*100
                print(f"  {event_type:12s}: {count:6,d} 条 ({pct:5.1f}%)")
    
    # 按kling_photo_id去重，保留最新的记录。因为多个用户可能交互同一个item,但是kling_items.json中仅需要记录一次该item的元信息即可。
    df_items = df_raw.sort_values('time_stamp').drop_duplicates(
        subset=['kling_photo_id'], keep='last'
    )
    
    print(f"\n物品去重: {len(df_raw):,} 条行为记录 -> {len(df_items):,} 个唯一物品")
    
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
    
    print(f"{len(df_items):,} 个唯一item，{len(items_dict):,} 个有效item (缺失SID: {missing_sid_count:,})")
    
    # 保存为JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items_dict, f, ensure_ascii=False, indent=2)
    
    print(f"物品元数据已保存到: {output_path}")
    
    return items_dict


def create_sequential_file(df_raw, output_path, min_sequence_length=3):
    """
    创建用户序列文件 (类似sequential_data_processed.txt)
    
    格式：每行一个用户的行为序列
    user_id item_id1 item_id2 item_id3 ...
    
    Args:
        df_raw: 正向行为数据DataFrame
        output_path: 输出文件路径
        min_sequence_length: 最小序列长度（默认3，用于后续训练分割）
    """
    print(f"创建用户行为序列文件,总记录数: {len(df_raw):,} 条")
    
    # 检查是否有有效的semantic_id
    df_raw['semantic_id_parsed'] = df_raw['semantic_id'].apply(parse_semantic_id)
    df_positive = df_raw[df_raw['semantic_id_parsed'].notna()].copy()
    
    # 按用户和时间排序
    df_sorted = df_positive.sort_values(['user_id', 'time_stamp'])
    
    # 统计信息
    user_counts = df_sorted.groupby('user_id').size()
    total_users = len(user_counts)
    valid_users = (user_counts >= min_sequence_length).sum()
    
    print(f"\n总用户数: {total_users:,},有效用户数 (行为≥{min_sequence_length}): {valid_users:,}")
    
    # 统计序列长度分布
    print("序列长度分布:")
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
    
    print(f"用户序列文件已保存到: {output_path}")
    
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
    
    print(f"用户行为详情已保存到: {output_path}")
    
    return user_behaviors


def main():
    input_file = '/renweishuai/zhouzhiyan/dataset_GR/20251109.tsv'
    
    items_output = Path("./kling_items.json")
    sequential_output = Path("./kling_sequential.txt")
    behaviors_output = Path("./kling_user_behaviors.json")
    
    # 检查输入文件
    if input_file is None:
        print(f"输入文件{input_file}不存在")
        return
    
    # 读取TSV文件
    try:
        df = pd.read_csv(input_file, sep='\t', encoding='utf-8-sig', engine='python')
        print(f"成功读取 {len(df):,} 条记录，{len(df.columns)} 列")
        
        # 移除BOM
        if df.columns[0].startswith('\ufeff'):
            df.columns = [col.replace('\ufeff', '') for col in df.columns]
    except Exception as e:
        print(f"读取文件失败: {str(e)}")
        return
    
    # 清理列名（移除可能的表前缀，如 table.column -> column）
    df = clean_column_names(df)
    
    # 步骤1: 创建物品元数据
    items_dict = create_item_metadata(df, items_output)
    
    # 步骤2: 创建用户序列
    valid_users = create_sequential_file(df, sequential_output)
    
    # 步骤3: 创建用户行为详情（用于生成富文本Alignment数据）
    user_behaviors = create_user_behaviors_file(df, behaviors_output)
    

    print(f"{items_output} ({len(items_dict):,} 个物品)")
    print(f"{sequential_output} ({valid_users:,} 个用户)")
    print(f"{behaviors_output} ({len(user_behaviors):,} 个用户)")


if __name__ == "__main__":
    main()
