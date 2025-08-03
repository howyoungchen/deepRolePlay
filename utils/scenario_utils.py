"""
Utility functions for reading and writing scenario files.
"""
import os
import aiofiles
from config.manager import settings
from utils.logger import request_logger


def get_scenario_file_path() -> str:
    """Get the absolute path of the scenario file."""
    return os.path.abspath(settings.scenario.file_path)


async def read_scenario() -> str:
    """
    Read the current scenario content.
    
    Returns:
        The current scenario content as a string.
    """
    scenario_file_path = get_scenario_file_path()
    
    try:
        # Check if the file exists
        if not os.path.exists(scenario_file_path):
            # If the file does not exist, create a default scenario
            default_scenario = "This is the beginning of a new conversation."
            await write_scenario(default_scenario)
            return default_scenario
        
        # Read the file directly
        async with aiofiles.open(scenario_file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        return content.strip()
        
    except Exception as e:
        await request_logger.log_error(f"Failed to read scenario file: {str(e)}")
        # Return default scenario
        return "This is the beginning of a new conversation."


async def write_scenario(content: str) -> None:
    """
    Write scenario content to the file.
    
    Args:
        content: The scenario content.
    """
    scenario_file_path = get_scenario_file_path()
    
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(scenario_file_path), exist_ok=True)
        
        # Write to the file
        async with aiofiles.open(scenario_file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
            
        await request_logger.log_info(f"Scenario file saved successfully: {scenario_file_path}")
        
    except Exception as e:
        await request_logger.log_error(f"Failed to save scenario file: {str(e)}")
        raise


