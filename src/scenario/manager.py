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
    
    
    async def update_scenario(self, workflow_input: Dict[str, Any]):
        """
        Synchronously updates the scenario, waits for completion, and returns the LLM response.
        
        Args:
            workflow_input: Complete workflow input including messages, api_key, model, etc.
            
        Returns:
            The LLM response object.
        """
        try:
            # Dynamically import the new workflow to avoid circular dependencies.
            from src.workflow.graph.scenario_workflow import create_scenario_workflow
            
            # Create and invoke the workflow.
            workflow = create_scenario_workflow()
            result = await workflow.ainvoke(workflow_input)
            return result.get("llm_response")
    
        except Exception as e:
            raise RuntimeError(f"Failed to update scenario: {str(e)}")
    
    async def update_scenario_streaming(self, workflow_input: Dict[str, Any]):
        """
        Updates the scenario in a streaming fashion, returning streaming events from the workflow execution.
        
        Args:
            workflow_input: Complete workflow input including messages, api_key, model, etc.
            
        Yields:
            Streaming events from the workflow execution.
        """
        try:
            # Dynamically import the new workflow to avoid circular dependencies.
            from src.workflow.graph.scenario_workflow import create_scenario_workflow
            
            # Create the workflow.
            workflow = create_scenario_workflow()
            
            # Use astream_events to get streaming events.
            async for event in workflow.astream_events(workflow_input, version="v2"):
                yield event
    
        except Exception as e:
            print(f"Error: Failed to update scenario in streaming mode: {str(e)}")
            raise RuntimeError(f"Failed to update scenario in streaming mode: {str(e)}")



# Global instance
scenario_manager = ScenarioManager()