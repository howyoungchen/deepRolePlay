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
    Validate file path validity
    
    Args:
        file_path: File path to validate
        root_dir: Root directory, defaults to current working directory
        
    Returns:
        Error message, or None if path is valid
    """
    if not root_dir:
        root_dir = os.getcwd()
    
    # Check if it's an absolute path
    if not os.path.isabs(file_path):
        return f"File path must be absolute: {file_path}"
    
    # Check if path is within root directory
    try:
        abs_file_path = os.path.abspath(file_path)
        abs_root_dir = os.path.abspath(root_dir)
        
        # Use commonpath to check path relationship
        if not abs_file_path.startswith(abs_root_dir):
            return f"File path must be within root directory ({abs_root_dir}): {file_path}"
    except (ValueError, OSError) as e:
        return f"Path validation error: {str(e)}"
    
    # Check if path exists, ensure it's not a directory
    if os.path.exists(file_path):
        if os.path.isdir(file_path):
            return f"Path is a directory, not a file: {file_path}"
    
    return None


@tool
def write_file(file_path: str, content: str, root_dir: Optional[str] = None) -> str:
    """
    Write content to specified file. Creates directories automatically if they don't exist.
    
    Args:
        file_path: Absolute path of the file to write to
        content: Content to write
        root_dir: Root directory, defaults to current working directory
        
    Returns:
        Operation result message
    """
    try:
        # Validate parameters
        validation_error = validate_file_path(file_path, root_dir)
        if validation_error:
            return f"Error: Invalid parameters. Reason: {validation_error}"
        
        # Check if file already exists
        file_exists = os.path.exists(file_path)
        
        # Create directory if it doesn't exist
        dir_name = os.path.dirname(file_path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Return success message
        if file_exists:
            return f"Successfully overwrote file: {file_path}"
        else:
            return f"Successfully created and wrote new file: {file_path}"
            
    except PermissionError:
        return f"Error: Permission denied, cannot write file: {file_path}"
    except OSError as e:
        return f"Error: File system error: {str(e)}"
    except Exception as e:
        return f"Error: Unknown error occurred while writing file: {str(e)}"


def test_langchain_tool_interface():
    """Test LangChain tool interface"""
    print("=== LangChain Tool Interface Test ===")
    print(f"Tool name: {write_file.name}")
    print(f"Tool description: {write_file.description}")
    print(f"Tool args: {write_file.args}")
    print(f"Tool type: {type(write_file)}")
    
    # Test tool schema
    schema = write_file.args_schema
    if schema:
        print(f"Args schema: {schema.model_json_schema()}")
    
    print("\n")


if __name__ == "__main__":
    import tempfile
    import shutil
    
    # First test LangChain tool interface
    test_langchain_tool_interface()
    
    print("=== Write Tool Test ===\n")
    
    # Create temporary test directory
    test_root = tempfile.mkdtemp(prefix="write_tool_test_")
    print(f"Test root directory: {test_root}")
    
    try:
        # Test 1: Create new file
        print("\n1. Test creating new file:")
        test_file1 = os.path.join(test_root, "test1.txt")
        result1 = write_file.invoke({"file_path": test_file1, "content": "Hello, World!", "root_dir": test_root})
        print(f"Result: {result1}")
        print(f"File exists: {os.path.exists(test_file1)}")
        if os.path.exists(test_file1):
            with open(test_file1, 'r', encoding='utf-8') as f:
                print(f"File content: {repr(f.read())}")
        
        # Test 2: Overwrite existing file
        print("\n2. Test overwriting existing file:")
        result2 = write_file.invoke({"file_path": test_file1, "content": "Updated content!", "root_dir": test_root})
        print(f"Result: {result2}")
        if os.path.exists(test_file1):
            with open(test_file1, 'r', encoding='utf-8') as f:
                print(f"Updated content: {repr(f.read())}")
        
        # Test 3: Auto-create directories
        print("\n3. Test auto-creating directories:")
        test_file3 = os.path.join(test_root, "subdir", "nested", "test3.txt")
        result3 = write_file.invoke({"file_path": test_file3, "content": "Nested file content", "root_dir": test_root})
        print(f"Result: {result3}")
        print(f"Directory exists: {os.path.exists(os.path.dirname(test_file3))}")
        print(f"File exists: {os.path.exists(test_file3)}")
        
        # Test 4: Relative path error
        print("\n4. Test relative path error:")
        result4 = write_file.invoke({"file_path": "relative_path.txt", "content": "content", "root_dir": test_root})
        print(f"Result: {result4}")
        
        # Test 5: Path outside root directory error
        print("\n5. Test path outside root directory error:")
        outside_path = "/tmp/outside_test.txt"
        result5 = write_file.invoke({"file_path": outside_path, "content": "content", "root_dir": test_root})
        print(f"Result: {result5}")
        
        # Test 6: Target is directory not file
        print("\n6. Test target is directory not file:")
        test_dir = os.path.join(test_root, "test_directory")
        os.makedirs(test_dir, exist_ok=True)
        result6 = write_file.invoke({"file_path": test_dir, "content": "content", "root_dir": test_root})
        print(f"Result: {result6}")
        
        # Test 7: Empty content
        print("\n7. Test empty content:")
        test_file7 = os.path.join(test_root, "empty.txt")
        result7 = write_file.invoke({"file_path": test_file7, "content": "", "root_dir": test_root})
        print(f"Result: {result7}")
        if os.path.exists(test_file7):
            with open(test_file7, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"File content length: {len(content)}")
        
        # Test 8: Content with special characters
        print("\n8. Test special character content:")
        test_file8 = os.path.join(test_root, "special_chars.txt")
        special_content = "Special chars: Chinese, émojis: 🚀, newlines:\nline2\nline3"
        result8 = write_file.invoke({"file_path": test_file8, "content": special_content, "root_dir": test_root})
        print(f"Result: {result8}")
        if os.path.exists(test_file8):
            with open(test_file8, 'r', encoding='utf-8') as f:
                read_content = f.read()
                print(f"Content matches: {special_content == read_content}")
        
        # Test 9: Large file content
        print("\n9. Test large file content:")
        test_file9 = os.path.join(test_root, "large_file.txt")
        large_content = "Large content line\n" * 1000  # 1000 lines
        result9 = write_file.invoke({"file_path": test_file9, "content": large_content, "root_dir": test_root})
        print(f"Result: {result9}")
        if os.path.exists(test_file9):
            print(f"File size: {os.path.getsize(test_file9)} bytes")
        
        print(f"\n=== Test Complete ===")
        print(f"Files in test directory:")
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
        # Clean up test directory
        shutil.rmtree(test_root)
        print(f"\nCleaned up test directory: {test_root}")