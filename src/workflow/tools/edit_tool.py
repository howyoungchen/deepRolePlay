"""
Edit Tool for LangChain
Ported from TypeScript gemini-cli-tools/ts-tools/edit.ts
Provides file editing functionality with string replacement capabilities.
"""

import os
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class EditToolParams(BaseModel):
    """Parameters for the Edit tool"""
    file_path: str = Field(description="The absolute path to the file to modify")
    old_string: str = Field(description="The text to replace")
    new_string: str = Field(description="The text to replace it with")
    expected_replacements: int = Field(default=1, description="Number of replacements expected. Defaults to 1 if not specified.")


def validate_file_path(file_path: str, root_dir: Optional[str] = None) -> str:
    """
    Validates the file path parameters
    Returns error message string or empty string if valid
    """
    if not os.path.isabs(file_path):
        return f"File path must be absolute: {file_path}"
    
    if root_dir:
        abs_root = os.path.abspath(root_dir)
        abs_file = os.path.abspath(file_path)
        if not abs_file.startswith(abs_root):
            return f"File path must be within the root directory ({abs_root}): {file_path}"
    
    return ""


def apply_replacement(current_content: Optional[str], old_string: str, new_string: str, is_new_file: bool) -> str:
    """Apply string replacement logic"""
    if is_new_file:
        return new_string
    
    if current_content is None:
        return new_string if old_string == "" else ""
    
    if old_string == "" and not is_new_file:
        return current_content
    
    return current_content.replace(old_string, new_string)


def calculate_edit(file_path: str, old_string: str, new_string: str, expected_replacements: int = 1) -> dict:
    """
    Calculates the potential outcome of an edit operation.
    Returns a dict with: current_content, new_content, occurrences, error, is_new_file
    """
    current_content: Optional[str] = None
    file_exists = False
    is_new_file = False
    occurrences = 0
    error: Optional[str] = None
    
    # Try to read the file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        # Normalize line endings to LF for consistent processing
        current_content = current_content.replace('\r\n', '\n')
        file_exists = True
    except FileNotFoundError:
        file_exists = False
    except Exception as e:
        error = f"Error reading file: {str(e)}"
        return {
            "current_content": None,
            "new_content": "",
            "occurrences": 0,
            "error": error,
            "is_new_file": False
        }
    
    # Handle file creation vs editing logic
    if old_string == "" and not file_exists:
        # Creating a new file
        is_new_file = True
    elif not file_exists:
        # Trying to edit a nonexistent file (and old_string is not empty)
        error = "File not found. Cannot apply edit. Use an empty old_string to create a new file."
    elif current_content is not None:
        # Editing an existing file
        if old_string == "":
            # Error: Trying to create a file that already exists
            error = "Failed to edit. Attempted to create a file that already exists."
        else:
            # Count occurrences
            occurrences = current_content.count(old_string)
            
            if occurrences == 0:
                error = f"Failed to edit, could not find the string to replace. The exact text in old_string was not found."
            elif occurrences != expected_replacements:
                occurrence_term = "occurrence" if expected_replacements == 1 else "occurrences"
                error = f"Failed to edit, expected {expected_replacements} {occurrence_term} but found {occurrences}."
            elif old_string == new_string:
                error = "No changes to apply. The old_string and new_string are identical."
    else:
        error = "Failed to read content of file."
    
    # Calculate new content
    new_content = apply_replacement(current_content, old_string, new_string, is_new_file)
    
    return {
        "current_content": current_content,
        "new_content": new_content,
        "occurrences": occurrences,
        "error": error,
        "is_new_file": is_new_file
    }


def ensure_parent_directories_exist(file_path: str) -> None:
    """Creates parent directories if they don't exist"""
    parent_dir = os.path.dirname(file_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)


@tool
def edit_file(
    file_path: str,
    old_string: str, 
    new_string: str,
    expected_replacements: int = 1
) -> str:
    """
    Replaces text within a file. By default, replaces a single occurrence, but can replace multiple 
    occurrences when `expected_replacements` is specified. This tool requires providing significant 
    context around the change to ensure precise targeting.

    Expectation for required parameters:
    1. `file_path` MUST be an absolute path; otherwise an error will be thrown.
    2. `old_string` MUST be the exact literal text to replace (including all whitespace, indentation, newlines, and surrounding code etc.).
    3. `new_string` MUST be the exact literal text to replace `old_string` with (also including all whitespace, indentation, newlines, and surrounding code etc.). Ensure the resulting code is correct and idiomatic.
    4. NEVER escape `old_string` or `new_string`, that would break the exact literal text requirement.
    
    **Important:** If ANY of the above are not satisfied, the tool will fail. CRITICAL for `old_string`: Must uniquely identify the single instance to change. Include at least 3 lines of context BEFORE and AFTER the target text, matching whitespace and indentation precisely. If this string matches multiple locations, or does not match exactly, the tool will fail.
    **Multiple replacements:** Set `expected_replacements` to the number of occurrences you want to replace. The tool will replace ALL occurrences that match `old_string` exactly. Ensure the number of replacements matches your expectation.

    Args:
        file_path: The absolute path to the file to modify. Must start with '/'.
        old_string: The exact literal text to replace, preferably unescaped. For single replacements (default), include at least 3 lines of context BEFORE and AFTER the target text, matching whitespace and indentation precisely. For multiple replacements, specify expected_replacements parameter. If this string is not the exact literal text (i.e. you escaped it) or does not match exactly, the tool will fail.
        new_string: The exact literal text to replace `old_string` with, preferably unescaped. Provide the EXACT text. Ensure the resulting code is correct and idiomatic.
        expected_replacements: Number of replacements expected. Defaults to 1 if not specified. Use when you want to replace multiple occurrences.

    Returns:
        String describing the result of the edit operation.
    """
    # Validate parameters
    validation_error = validate_file_path(file_path)
    if validation_error:
        return f"Error: Invalid parameters provided. Reason: {validation_error}"
    
    # Calculate the edit
    try:
        edit_data = calculate_edit(file_path, old_string, new_string, expected_replacements)
    except Exception as e:
        return f"Error preparing edit: {str(e)}"
    
    if edit_data["error"]:
        return f"Error: {edit_data['error']}"
    
    # Execute the edit
    try:
        ensure_parent_directories_exist(file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(edit_data["new_content"])
        
        if edit_data["is_new_file"]:
            return f"Created new file: {file_path} with provided content."
        else:
            return f"Successfully modified file: {file_path} ({edit_data['occurrences']} replacements)."
    
    except Exception as e:
        return f"Error executing edit: {str(e)}"


if __name__ == "__main__":
    # Test cases based on TypeScript edit.test.ts
    import tempfile
    import shutil
    
    def run_tests():
        print("Running Edit Tool Tests...")
        test_dir = tempfile.mkdtemp()
        
        try:
            # Test 1: Basic file editing
            print("\n1. Testing basic file editing...")
            test_file = os.path.join(test_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("This is some old text.")
            
            result = edit_file.invoke({
                "file_path": test_file,
                "old_string": "old",
                "new_string": "new",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            
            with open(test_file, 'r') as f:
                content = f.read()
            print(f"File content: {content}")
            assert content == "This is some new text.", f"Expected 'This is some new text.', got '{content}'"
            print("✓ Basic editing test passed")
            
            # Test 2: Creating a new file
            print("\n2. Testing new file creation...")
            new_file = os.path.join(test_dir, "new_file.txt")
            result = edit_file.invoke({
                "file_path": new_file,
                "old_string": "",
                "new_string": "Content for the new file.",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            
            assert os.path.exists(new_file), "New file should exist"
            with open(new_file, 'r') as f:
                content = f.read()
            assert content == "Content for the new file.", f"Expected 'Content for the new file.', got '{content}'"
            print("✓ New file creation test passed")
            
            # Test 3: Multiple replacements
            print("\n3. Testing multiple replacements...")
            multi_file = os.path.join(test_dir, "multi.txt")
            with open(multi_file, 'w') as f:
                f.write("old text old text old text")
            
            result = edit_file.invoke({
                "file_path": multi_file,
                "old_string": "old",
                "new_string": "new",
                "expected_replacements": 3
            })
            print(f"Result: {result}")
            
            with open(multi_file, 'r') as f:
                content = f.read()
            assert content == "new text new text new text", f"Expected 'new text new text new text', got '{content}'"
            print("✓ Multiple replacements test passed")
            
            # Test 4: String not found error
            print("\n4. Testing string not found...")
            result = edit_file.invoke({
                "file_path": test_file,
                "old_string": "nonexistent",
                "new_string": "replacement",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            assert "could not find the string to replace" in result
            print("✓ String not found test passed")
            
            # Test 5: Multiple occurrences found when expecting one
            print("\n5. Testing multiple occurrences error...")
            with open(test_file, 'w') as f:
                f.write("multiple old old strings")
            
            result = edit_file.invoke({
                "file_path": test_file,
                "old_string": "old",
                "new_string": "new",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            assert "expected 1 occurrence but found 2" in result
            print("✓ Multiple occurrences error test passed")
            
            # Test 6: Trying to create file that already exists
            print("\n6. Testing create existing file error...")
            result = edit_file.invoke({
                "file_path": test_file,
                "old_string": "",
                "new_string": "new content",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            assert "Attempted to create a file that already exists" in result
            print("✓ Create existing file error test passed")
            
            # Test 7: Invalid file path
            print("\n7. Testing invalid file path...")
            result = edit_file.invoke({
                "file_path": "relative_path.txt",
                "old_string": "old",
                "new_string": "new",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            assert "File path must be absolute" in result
            print("✓ Invalid file path test passed")
            
            # Test 8: Identical old and new strings
            print("\n8. Testing identical strings...")
            with open(test_file, 'w') as f:
                f.write("This is some identical text.")
            
            result = edit_file.invoke({
                "file_path": test_file,
                "old_string": "identical",
                "new_string": "identical",
                "expected_replacements": 1
            })
            print(f"Result: {result}")
            assert "No changes to apply" in result
            print("✓ Identical strings test passed")
            
            print("\n✓ All tests passed!")
            
        finally:
            # Clean up
            shutil.rmtree(test_dir)
    
    run_tests()