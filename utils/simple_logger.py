"""
简单的JSON日志保存工具
"""
import json
from pathlib import Path


def save_log(file_path: str, data: dict):
    """
    简单保存JSON日志
    
    Args:
        file_path: 保存文件路径
        data: 要保存的字典数据
    """
    try:
        # 确保目录存在
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存JSON文件
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"日志保存失败 {file_path}: {e}")  # 不影响主流程