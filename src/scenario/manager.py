"""
Scenario Management Module
Responsible for scenario file management and workflow scheduling
"""
import os
import aiofiles
from typing import List, Dict, Any
from datetime import datetime

from config.manager import settings


class ScenarioManager:
    """Scenario Manager"""
    
    def __init__(self):
        """Initializes the Scenario Manager."""
        # Get the scenario file path from the configuration, or use the default value if it does not exist.
        if hasattr(settings, 'scenario') and hasattr(settings.scenario, 'file_path'):
            self.scenario_file_path = settings.scenario.file_path
        else:
            self.scenario_file_path = "./scenarios/current_scenario.txt"
        
        # Ensure that the scenarios directory exists.
        os.makedirs(os.path.dirname(self.scenario_file_path), exist_ok=True)
    
    
    async def update_scenario(self, messages: List[Dict[str, Any]]):
        """
        Synchronously updates the scenario, waits for completion, and returns the updated scenario content.
        
        Args:
            messages: The original list of messages.
            
        Returns:
            The updated scenario content.
        """
        try:
            # Get the current scenario content.
            from utils.scenario_utils import read_scenario
            current_scenario = await read_scenario()
            
            # Dynamically import the new workflow to avoid circular dependencies.
            from src.workflow.graph.scenario_workflow import create_scenario_workflow
            
            # Create and invoke the workflow.
            workflow = create_scenario_workflow()
            await workflow.ainvoke({
                "current_scenario": current_scenario,
                "messages": messages
            })
    
        except Exception as e:
            raise RuntimeError(f"Failed to update scenario: {str(e)}")
    
    async def update_scenario_streaming(self, messages: List[Dict[str, Any]]):
        """
        Updates the scenario in a streaming fashion, returning streaming events from the workflow execution.
        
        Args:
            messages: The original list of messages.
            
        Yields:
            Streaming events from the workflow execution.
        """
        try:
            # Get the current scenario content.
            from utils.scenario_utils import read_scenario
            current_scenario = await read_scenario()
            
            # Dynamically import the new workflow to avoid circular dependencies.
            from src.workflow.graph.scenario_workflow import create_scenario_workflow
            
            # Create the workflow.
            workflow = create_scenario_workflow()
            
            # Use astream_events to get streaming events.
            async for event in workflow.astream_events({
                "current_scenario": current_scenario,
                "messages": messages
            }, version="v2"):
                yield event
    
        except Exception as e:
            print(f"Error: Failed to update scenario in streaming mode: {str(e)}")
            raise RuntimeError(f"Failed to update scenario in streaming mode: {str(e)}")



# Global instance
scenario_manager = ScenarioManager()