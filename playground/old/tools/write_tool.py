#!/usr/bin/env python3
"""
Write file tool for LangChain/LangGraph.
Based on the TypeScript write-file.ts from gemini-cli-tools.
"""

import os
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool


def validate_file_path(file_path: str, root_dir: Optional[str] = None) -> Optional[str]:
    """
    验证文件路径的有效性
    
    Args:
        file_path: 要验证的文件路径
        root_dir: 根目录，默认为当前工作目录
        
    Returns:
        错误消息，如果路径有效则返回 None
    """
    if not root_dir:
        root_dir = os.getcwd()
    
    # 检查是否为绝对路径
    if not os.path.isabs(file_path):
        return f"文件路径必须是绝对路径: {file_path}"
    
    # 检查路径是否在根目录内
    try:
        abs_file_path = os.path.abspath(file_path)
        abs_root_dir = os.path.abspath(root_dir)
        
        # 使用 commonpath 检查路径关系
        if not abs_file_path.startswith(abs_root_dir):
            return f"文件路径必须在根目录内 ({abs_root_dir}): {file_path}"
    except (ValueError, OSError) as e:
        return f"路径验证错误: {str(e)}"
    
    # 检查如果路径存在，确保不是目录
    if os.path.exists(file_path):
        if os.path.isdir(file_path):
            return f"路径是目录而非文件: {file_path}"
    
    return None


@tool
def write_file(file_path: str, content: str, root_dir: Optional[str] = None) -> str:
    """
    将内容写入指定文件。如果目录不存在会自动创建。
    
    Args:
        file_path: 要写入的文件的绝对路径
        content: 要写入的内容
        root_dir: 根目录，默认为当前工作目录
        
    Returns:
        操作结果消息
    """
    try:
        # 验证参数
        validation_error = validate_file_path(file_path, root_dir)
        if validation_error:
            return f"错误: 参数无效。原因: {validation_error}"
        
        # 检查文件是否已存在
        file_exists = os.path.exists(file_path)
        
        # 创建目录（如果不存在）
        dir_name = os.path.dirname(file_path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 返回成功消息
        if file_exists:
            return f"成功覆写文件: {file_path}"
        else:
            return f"成功创建并写入新文件: {file_path}"
            
    except PermissionError:
        return f"错误: 权限被拒绝，无法写入文件: {file_path}"
    except OSError as e:
        return f"错误: 文件系统错误: {str(e)}"
    except Exception as e:
        return f"错误: 写入文件时发生未知错误: {str(e)}"


def test_langchain_tool_interface():
    """测试 LangChain 工具接口"""
    print("=== LangChain Tool Interface 测试 ===")
    print(f"工具名称: {write_file.name}")
    print(f"工具描述: {write_file.description}")
    print(f"工具参数: {write_file.args}")
    print(f"工具类型: {type(write_file)}")
    
    # 测试工具 schema
    schema = write_file.args_schema
    if schema:
        print(f"参数 schema: {schema.model_json_schema()}")
    
    print("\n")


if __name__ == "__main__":
    import tempfile
    import shutil
    
    # 首先测试 LangChain 工具接口
    test_langchain_tool_interface()
    
    print("=== Write Tool 测试 ===\n")
    
    # 创建临时测试目录
    test_root = tempfile.mkdtemp(prefix="write_tool_test_")
    print(f"测试根目录: {test_root}")
    
    try:
        # 测试1: 创建新文件
        print("\n1. 测试创建新文件:")
        test_file1 = os.path.join(test_root, "test1.txt")
        result1 = write_file.invoke({"file_path": test_file1, "content": "Hello, World!", "root_dir": test_root})
        print(f"结果: {result1}")
        print(f"文件存在: {os.path.exists(test_file1)}")
        if os.path.exists(test_file1):
            with open(test_file1, 'r', encoding='utf-8') as f:
                print(f"文件内容: {repr(f.read())}")
        
        # 测试2: 覆写现有文件
        print("\n2. 测试覆写现有文件:")
        result2 = write_file.invoke({"file_path": test_file1, "content": "Updated content!", "root_dir": test_root})
        print(f"结果: {result2}")
        if os.path.exists(test_file1):
            with open(test_file1, 'r', encoding='utf-8') as f:
                print(f"更新后内容: {repr(f.read())}")
        
        # 测试3: 自动创建目录
        print("\n3. 测试自动创建目录:")
        test_file3 = os.path.join(test_root, "subdir", "nested", "test3.txt")
        result3 = write_file.invoke({"file_path": test_file3, "content": "Nested file content", "root_dir": test_root})
        print(f"结果: {result3}")
        print(f"目录存在: {os.path.exists(os.path.dirname(test_file3))}")
        print(f"文件存在: {os.path.exists(test_file3)}")
        
        # 测试4: 相对路径错误
        print("\n4. 测试相对路径错误:")
        result4 = write_file.invoke({"file_path": "relative_path.txt", "content": "content", "root_dir": test_root})
        print(f"结果: {result4}")
        
        # 测试5: 路径在根目录外错误
        print("\n5. 测试路径在根目录外错误:")
        outside_path = "/tmp/outside_test.txt"
        result5 = write_file.invoke({"file_path": outside_path, "content": "content", "root_dir": test_root})
        print(f"结果: {result5}")
        
        # 测试6: 目标是目录而非文件
        print("\n6. 测试目标是目录而非文件:")
        test_dir = os.path.join(test_root, "test_directory")
        os.makedirs(test_dir, exist_ok=True)
        result6 = write_file.invoke({"file_path": test_dir, "content": "content", "root_dir": test_root})
        print(f"结果: {result6}")
        
        # 测试7: 空内容
        print("\n7. 测试空内容:")
        test_file7 = os.path.join(test_root, "empty.txt")
        result7 = write_file.invoke({"file_path": test_file7, "content": "", "root_dir": test_root})
        print(f"结果: {result7}")
        if os.path.exists(test_file7):
            with open(test_file7, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"文件内容长度: {len(content)}")
        
        # 测试8: 包含特殊字符的内容
        print("\n8. 测试特殊字符内容:")
        test_file8 = os.path.join(test_root, "special_chars.txt")
        special_content = "特殊字符: 中文, émojis: 🚀, newlines:\nline2\nline3"
        result8 = write_file.invoke({"file_path": test_file8, "content": special_content, "root_dir": test_root})
        print(f"结果: {result8}")
        if os.path.exists(test_file8):
            with open(test_file8, 'r', encoding='utf-8') as f:
                read_content = f.read()
                print(f"内容匹配: {special_content == read_content}")
        
        # 测试9: 大文件内容
        print("\n9. 测试大文件内容:")
        test_file9 = os.path.join(test_root, "large_file.txt")
        large_content = "Large content line\n" * 1000  # 1000 行
        result9 = write_file.invoke({"file_path": test_file9, "content": large_content, "root_dir": test_root})
        print(f"结果: {result9}")
        if os.path.exists(test_file9):
            print(f"文件大小: {os.path.getsize(test_file9)} bytes")
        
        print(f"\n=== 测试完成 ===")
        print(f"测试目录中的文件:")
        for root, dirs, files in os.walk(test_root):
            level = root.replace(test_root, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                print(f"{subindent}{file} ({size} bytes)")
    
    finally:
        # 清理测试目录
        shutil.rmtree(test_root)
        print(f"\n已清理测试目录: {test_root}")