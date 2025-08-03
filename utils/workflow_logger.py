import os
import json
import uuid
import asyncio
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class WorkflowLogger:
    def __init__(self, log_dir: str = "./logs/workflow"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    async def log_agent_execution(
        self,
        node_type: str,  # "memory_flashback" or "scenario_updater"
        inputs: Dict[str, Any],
        agent_response: Dict[str, Any],
        outputs: Dict[str, Any],
        duration: float,
        execution_id: str = None
    ):
        """Logs the complete execution process of the agent."""
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        timestamp = datetime.now()
        
        # Parse key information from the agent response
        parsed_response = self._parse_agent_response(agent_response)
        
        log_data = {
            "execution_id": execution_id,
            "timestamp": timestamp.isoformat(),
            "node_type": node_type,
            "inputs": inputs,
            "agent_response": {
                "parsed_content": parsed_response
            },
            "outputs": outputs,
            "duration_seconds": duration,
            "status": "success" if outputs else "failed"
        }
        
        # File naming format: YYYY_MM_DD_HH_MM_SS_{node_type}.json
        log_filename = timestamp.strftime(f"%Y_%m_%d_%H_%M_%S_{node_type}.json")
        log_path = self.log_dir / log_filename
        
        try:
            # Ensure the log directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(log_data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Failed to write to workflow log file: {e}")
    
    def _parse_agent_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parses the agent response to extract key information."""
        parsed = {
            "messages_full": []
        }
        
        try:
            messages = response.get("messages", [])
            
            if messages:
                # Save the full message content
                for i, msg in enumerate(messages):
                    msg_data = {
                        "index": i,
                        "type": type(msg).__name__,
                        "content": "",
                        "role": "",
                        "name": "",
                        "tool_calls": [],
                        "tool_call_id": ""
                    }
                    
                    # Extract message content and role
                    if hasattr(msg, 'content'):
                        msg_data["content"] = str(msg.content)
                    elif isinstance(msg, dict):
                        msg_data["content"] = str(msg.get("content", ""))
                    
                    if hasattr(msg, 'type'):
                        msg_data["role"] = str(msg.type)
                    elif isinstance(msg, dict):
                        msg_data["role"] = str(msg.get("type", ""))
                    
                    if hasattr(msg, 'name'):
                        msg_data["name"] = str(msg.name)
                    elif isinstance(msg, dict):
                        msg_data["name"] = str(msg.get("name", ""))
                    
                    if hasattr(msg, 'tool_call_id'):
                        msg_data["tool_call_id"] = str(msg.tool_call_id)
                    elif isinstance(msg, dict):
                        msg_data["tool_call_id"] = str(msg.get("tool_call_id", ""))
                    
                    # Extract tool call information
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_data = {
                                "name": getattr(tool_call, 'name', str(tool_call.get("name", ""))),
                                "args": getattr(tool_call, 'args', tool_call.get("args", {})),
                                "id": getattr(tool_call, 'id', str(tool_call.get("id", "")))
                            }
                            msg_data["tool_calls"].append(tool_data)
                    elif isinstance(msg, dict) and msg.get("tool_calls"):
                        for tool_call in msg["tool_calls"]:
                            tool_data = {
                                "name": str(tool_call.get("name", "")),
                                "args": tool_call.get("args", {}),
                                "id": str(tool_call.get("id", ""))
                            }
                            msg_data["tool_calls"].append(tool_data)
                    
                    parsed["messages_full"].append(msg_data)
        
        except Exception as e:
            parsed["parse_error"] = str(e)
        
        return parsed
    
    async def log_execution_error(
        self,
        node_type: str,
        inputs: Dict[str, Any],
        error_message: str,
        error_details: str = "",
        execution_id: str = None
    ):
        """Logs an execution error."""
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        timestamp = datetime.now()
        
        log_data = {
            "execution_id": execution_id,
            "timestamp": timestamp.isoformat(),
            "node_type": node_type,
            "inputs": inputs,
            "error": {
                "message": error_message,
                "details": error_details
            },
            "status": "error",
            "duration_seconds": 0
        }
        
        log_filename = timestamp.strftime(f"%Y_%m_%d_%H_%M_%S_{node_type}_error.json")
        log_path = self.log_dir / log_filename
        
        try:
            # Ensure the log directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(log_data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Failed to write to workflow error log file: {e}")


# Create a global workflow logger instance
workflow_logger = WorkflowLogger()