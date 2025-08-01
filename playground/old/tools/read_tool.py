import os
from langchain_core.tools import tool


@tool
def read_target_file(file_path: str) -> str:
    """读取指定文件的内容，返回带行号的格式化内容。如果文件不存在会创建空文件。
    
    返回格式为 '行号→实际内容'，这只是为了显示方便。
    例如返回：
      1→Hello World
      2→Second line
    
    实际文件内容是：
      Hello World
      Second line
    
    Args:
        file_path: 要读取的文件路径
    
    Returns:
        str: 带行号的文件内容
    """
    try:
        file_path = file_path.strip()
        if not file_path:
            raise ValueError("文件路径不能为空")
        
        # 如果文件不存在，创建空文件
        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('')
            print(f"文件不存在，已创建空文件: {file_path}")
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 格式化内容，添加行号
        formatted_lines = []
        for i, line in enumerate(lines, 1):
            line = line.rstrip('\n\r')
            formatted_lines.append(f"{i:6d}→{line}")
        
        content = '\n'.join(formatted_lines)
        print(f"成功读取文件: {file_path}, 行数: {len(lines)}")
        return content
        
    except Exception as e:
        return f"错误：{str(e)}"