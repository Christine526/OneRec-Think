# coding=utf8

import os, time
import logging
import numpy as np
import pandas as pd
from pandas import DataFrame as PDataFrame
from pyspark.sql import DataFrame as SDataFrame
import dask.dataframe as DDataFrame
from pyspark.sql import functions as F

from kmlutils.kml_hive import Hive
from dask.distributed import Client, LocalCluster
from kmlutils import get_envs, date_parse
from kmlutils import invert_onehot_names
from datetime import datetime, timedelta
import time

# 抑制过多的日志输出
logging.basicConfig(level=logging.WARNING)
logging.getLogger('distributed').setLevel(logging.WARNING)
logging.getLogger('dask').setLevel(logging.WARNING)
logging.getLogger('kmlutils').setLevel(logging.WARNING)

# 设置NumPy和Pandas的显示选项（防止打印大量数据）
np.set_printoptions(threshold=50, edgeitems=3)  # 只显示前后3个元素
pd.set_option('display.max_rows', 20)  # 最多显示20行
pd.set_option('display.max_columns', 10)  # 最多显示10列
pd.set_option('max_colwidth', 20)  # 列宽限制为20个字符

# 禁用pandas警告
import warnings
warnings.filterwarnings('ignore')


def read_sql(hive,params):
    if params['wait_table_ready']:
        print("begin wait table1...")
        begin_time = datetime.now()
        hive.wait_table_ready(params['wait_table_name1'], params['wait_table_part1'], timeout=int(params['wait_table_timeout']))
        time_cost = (datetime.now()-begin_time).seconds
        print("wait table1 cost %ds" % time_cost)
        print("end wait table")
    df = hive.query(params['sql']['originSql'], smart=False, cached=params['cached'], persist=params['persist'])
    auto_cols = hive.auto_cols(params['sql']['originSql'])
    if isinstance(df, list):
        npartitions = 1*len(hive.client.scheduler_info()['workers'])
        df = pd.DataFrame(df, columns=auto_cols)
        df = df.from_pandas(df, npartitions=npartitions)
    if params['repartition']:
        npartitions = 1*len(hive.client.scheduler_info()['workers']) if params['default_repartition'] else int(params['repartition_value'])
        df = df.repartition(npartitions=npartitions, force=True)
    return df


def get_kling_data(hive, p_date):
    """
    从Hive获取Kling数据
    包含正向行为过滤和所有必要字段
    
    Args:
        hive: Hive客户端
        p_date: 数据日期，格式YYYYMMDD（例如：20251105）
    
    Returns:
        DataFrame: 包含用户行为数据
    """
    origin_sql = f"""
        -- 正向行为过滤：保留推荐、搜索之后的强互动行为的item，生产行为均是正向行为
        -- 强互动包括：点赞、取消点赞、评论、转发、点击、举报、一键同款、完播、长播放
        -- 搜索行为中的搜索次数query_cnt作为上下文信息也需要加进来
        with filtered_behavior AS (
        SELECT *
        FROM (
            SELECT
                *,
                get_json_object(extra_info, '$.played_dur') AS played_dur, --Web端的播放时间
                get_json_object(extra_info, '$.element_action') AS element_action,
                get_json_object(extra_info, '$.query_cnt') AS query_cnt
            FROM kling_web_app.prd_kling_community_gr_basic_data
            WHERE p_date = '{p_date}'
                AND nvl(kling_photo_id,'') <> ''
                AND nvl(user_id,'') <> ''
                AND prompt is not null
                AND semantic_id is not null
        ) raw_t
        WHERE 
            event_type = 'PRODUCE'
            OR (behavior_type = 'OPERATE' AND behavior_subtype IN ('LIKE', 'UNLIKE', 'COMMENT', 'SHARE', 'SAME_STYLE', 'REPORT'))
            OR behavior_type = 'VIDEO_PLAY_FINISH'
            OR (behavior_type in ('LONG_PLAY', 'SHORT_PLAY') AND platform_type = 'Web' AND CAST(played_dur AS DOUBLE) >= 5)
            OR (behavior_type in ('LONG_PLAY', 'SHORT_PLAY') AND platform_type = 'App') -- App不限制播放时长
            OR --点击
            ( (
                platform_type = 'Web'
                and element_action in ('FANC_CARD')
                and behavior_type = 'OPERATE'
                and behavior_subtype = 'LARGE'
                ) or (
                platform_type = 'App'
                and behavior_type = 'OPERATE'
                and behavior_subtype = 'LARGE'
            ) ) 
        )

        select 
            user_id,
            kling_photo_id,
            kling_photo_type,
            event_type,
            behavior_type,
            behavior_subtype,
            time_stamp,
            content_type,
            prompt,
            title,
            introduction,
            element_query_content,
            query_cnt,
            semantic_id 
        from filtered_behavior
    """

    params = {
        "process": 1,
        "sql": {
            'originSql': origin_sql,
            'columns': ['user_id', 'kling_photo_id', 'kling_photo_type', 'event_type',
                       'behavior_type', 'behavior_subtype', 'time_stamp', 'content_type',
                       'prompt', 'title', 'introduction', 'element_query_content',
                       'query_cnt', 'semantic_id'] 
        },
        "cached": True,
        "persist": True,
        "repartition": False,
        "default_repartition": True,
        "repartition_value": "",
        "wait_table_ready": True,
        "wait_table_name1": "kling_web_app.prd_kling_community_gr_basic_data",
        "wait_table_part1": [f"p_date='{p_date}'"],
        "wait_table_timeout": 64800 # 18h
    }

    df = read_sql(hive, params)
    return df

def get_kling_csv(kling_dir, p_date):
    """
    获取kling数据并保存为CSV格式
    
    Args:
        kling_dir: 输出目录
        p_date: 数据日期，格式YYYYMMDD
    
    Returns:
        tuple: (csv_file_path, row_count)
    """
    os.makedirs(kling_dir, exist_ok=True)
    os.environ['HADOOP_USER_NAME'] = 'kling_web_app'
    os.environ['HIVE_GROUP_ID'] = '2820'

    # 初始化Dask客户端
    client = Client(LocalCluster(memory_limit="60GB"))

    # 初始化Hive客户端
    hive = Hive(username=os.getenv('HADOOP_USER_NAME'), group_id=os.getenv('HIVE_GROUP_ID'), priority=1, client=client)

    # 检查环境变量是否正确
    if os.getenv('HADOOP_USER_NAME') != "kling_web_app" or os.getenv('HIVE_GROUP_ID') != '2820':
        print("Error!!! must be ytech account")

    # 获取环境变量
    envs = get_envs()

    # 设置日志记录
    logger = logging.getLogger(__name__)
    start_time = time.time()

    kling_df = get_kling_data(hive, p_date)
    kling_df = kling_df.compute()

    # 清洗文本字段中的特殊行终止符
    text_columns = ['prompt', 'title', 'introduction', 'element_query_content']
    for col in text_columns:
        if col in kling_df.columns:
            kling_df[col] = kling_df[col].str.replace('\u2028', ' ', regex=False)
            kling_df[col] = kling_df[col].str.replace('\u2029', ' ', regex=False)
            kling_df[col] = kling_df[col].str.replace('\r', ' ', regex=False)
    
    # 保存为TSV格式（制表符分隔），避免CSV中逗号和引号的干扰
    csv_file_path = os.path.join(kling_dir, f"{p_date}.tsv")
    kling_df.to_csv(csv_file_path, sep='\t', index=False, encoding='utf-8-sig')
    
    end_time = time.time() 
    elapsed_time = end_time - start_time 
    print(f"[读取HIVE并保存TSV] 用时{elapsed_time:.2f}秒")
    
    row_count = len(kling_df)
    print(f"p_date={p_date}共{row_count}条数据已保存到{csv_file_path}中")

    return csv_file_path, row_count

if __name__ == "__main__":
    today = datetime.now()
    # p_date = (today - timedelta(days=1)).strftime('%Y%m%d')
    p_date = '20251109'
    base_dir = '/renweishuai/zhouzhiyan/dataset_GR'
    csv_file_path, row_count = get_kling_csv(base_dir, p_date)
