#!/usr/bin/env python3
"""
SID格式验证脚本

用途: 验证生成的kling_items.json中的SID格式是否正确（4维）

运行: python validate_sid_format.py [kling_items.json路径]
"""

import json
import sys
import re
from pathlib import Path


def validate_sid_format(items_file):
    """验证SID格式"""
    
    print("="*60)
    print("🔍 OneRec-Think SID格式验证工具")
    print("="*60)
    print()
    
    # 检查文件是否存在
    if not Path(items_file).exists():
        print(f"❌ 错误: 文件不存在: {items_file}")
        return False
    
    # 加载JSON
    print(f"📖 加载文件: {items_file}")
    try:
        with open(items_file, 'r', encoding='utf-8') as f:
            items = json.load(f)
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return False
    
    print(f"   ✅ 成功加载 {len(items)} 个物品\n")
    
    # SID格式正则表达式
    # 4维格式: <|sid_begin|><s_a_X><s_b_X><s_c_X><s_d_X><|sid_end|>
    sid_4d_pattern = r'^<\|sid_begin\|><s_a_\d+><s_b_\d+><s_c_\d+><s_d_\d+><\|sid_end\|>$'
    sid_3d_pattern = r'^<\|sid_begin\|><s_a_\d+><s_b_\d+><s_c_\d+><\|sid_end\|>$'
    
    # 验证所有SID
    valid_count = 0
    invalid_count = 0
    three_dim_count = 0
    out_of_range_count = 0
    
    invalid_examples = []
    
    for item_id, item_info in items.items():
        sid = item_info.get('sid', '')
        
        # 检查是否是4维格式
        if re.match(sid_4d_pattern, sid):
            # 提取4个维度的值
            matches = re.findall(r'<s_([a-z])_(\d+)>', sid)
            if len(matches) == 4:
                values = [int(m[1]) for m in matches]
                # 检查值是否在[0, 255]范围内
                if all(0 <= v <= 255 for v in values):
                    valid_count += 1
                else:
                    invalid_count += 1
                    out_of_range_count += 1
                    if len(invalid_examples) < 3:
                        invalid_examples.append((item_id, sid, "值超出范围[0,255]"))
            else:
                invalid_count += 1
                if len(invalid_examples) < 3:
                    invalid_examples.append((item_id, sid, "维度数量错误"))
        # 检查是否是3维格式（错误）
        elif re.match(sid_3d_pattern, sid):
            invalid_count += 1
            three_dim_count += 1
            if len(invalid_examples) < 3:
                invalid_examples.append((item_id, sid, "❌ 只有3维（应该是4维）"))
        else:
            invalid_count += 1
            if len(invalid_examples) < 3:
                invalid_examples.append((item_id, sid, "格式错误"))
    
    # 打印结果
    print("━"*60)
    print("📊 验证结果")
    print("━"*60)
    print()
    
    total = len(items)
    valid_rate = valid_count / total * 100 if total > 0 else 0
    
    print(f"总物品数: {total}")
    print(f"✅ 有效SID (4维): {valid_count} ({valid_rate:.1f}%)")
    print(f"❌ 无效SID: {invalid_count}")
    
    if three_dim_count > 0:
        print(f"   - 3维格式: {three_dim_count} ⚠️ 需要修正!")
    
    if out_of_range_count > 0:
        print(f"   - 值超出范围: {out_of_range_count}")
    
    # 显示示例
    print()
    if valid_count > 0:
        print("✅ 有效SID示例 (前3个):")
        count = 0
        for item_id, item_info in items.items():
            sid = item_info.get('sid', '')
            if re.match(sid_4d_pattern, sid):
                print(f"   [{count+1}] {sid}")
                count += 1
                if count >= 3:
                    break
    
    print()
    if invalid_examples:
        print("❌ 无效SID示例:")
        for i, (item_id, sid, reason) in enumerate(invalid_examples):
            print(f"   [{i+1}] Item {item_id}")
            print(f"       SID: {sid}")
            print(f"       原因: {reason}")
    
    print()
    print("━"*60)
    
    # 判断是否通过验证
    if valid_count == total:
        print("🎉 验证通过! 所有SID都是4维格式且值在有效范围内")
        print()
        print("✅ 可以继续进行训练数据生成")
        return True
    elif three_dim_count > 0:
        print("❌ 验证失败! 发现3维SID格式")
        print()
        print("⚠️  解决方案:")
        print("   1. 使用修正版脚本: kling_data/process_kling_data_fixed.py")
        print("   2. 不要使用原版的 process_kling_data.py")
        print("   3. 重新处理数据")
        return False
    else:
        print(f"⚠️  验证警告! {invalid_count} 个物品的SID格式有问题")
        print()
        print("建议检查:")
        print("   - semantic_id数据是否完整")
        print("   - 值是否在[0,255]范围内")
        return False


def main():
    if len(sys.argv) > 1:
        items_file = sys.argv[1]
    else:
        items_file = "./kling_items.json"
    
    success = validate_sid_format(items_file)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
