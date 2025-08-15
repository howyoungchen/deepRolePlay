"""
场景管理模块
负责场景文件管理和工作流调度
"""
import os
import aiofiles
from typing import List, Dict, Any
from datetime import datetime

from config.manager import settings


class ScenarioManager:
    """场景管理器"""
    
    def __init__(self):
        """初始化场景管理器。"""
        # 从配置中获取场景文件路径，如果不存在则使用默认值。
        if hasattr(settings, 'scenario') and hasattr(settings.scenario, 'file_path'):
            self.scenario_file_path = settings.scenario.file_path
        else:
            self.scenario_file_path = "./scenarios/current_scenario.txt"
        
        # 确保场景目录存在。
        os.makedirs(os.path.dirname(self.scenario_file_path), exist_ok=True)
    
    
    async def update_scenario(self, workflow_input: Dict[str, Any]):
        """
        非流式更新场景，等待完成。
        
        参数:
            workflow_input: 完整的工​​作流输入，包括消息、api_key、模型等。
            
        返回:
            None (场景已更新到文件)
        """
        try:
            # 检查是否启用了 only_forward 模式
            if settings.langgraph.only_forward:
                print(f"🚀 only_forward 模式已启用，跳过情景更新工作流")
                return None
                
            # 使用快速工作流（默认且唯一模式）
            from src.workflow.graph.fast_scenario_workflow import create_fast_scenario_workflow
            workflow = create_fast_scenario_workflow()
            
            # 使用非流式 ainvoke 调用，直接等待完成
            result = await workflow.ainvoke(workflow_input)
            
            return None
    
        except Exception as e:
            raise RuntimeError(f"更新场景失败: {str(e)}")
    
    async def update_scenario_streaming(self, workflow_input: Dict[str, Any]):
        """
        以流式方式更新场景，返回工作流执行中的流式事件。
        
        参数:
            workflow_input: 完整的工​​作流输入，包括消息、api_key、模型等。
            
        产生:
            来自工作流执行的流式事件。
        """
        try:
            # 检查是否启用了 only_forward 模式
            if settings.langgraph.only_forward:
                print(f"🚀 only_forward 模式已启用，跳过情景更新工作流")
                # 返回一个空的生成器，不产生任何事件
                return
                
            # 使用快速工作流（默认且唯一模式）
            from src.workflow.graph.fast_scenario_workflow import create_fast_scenario_workflow
            workflow = create_fast_scenario_workflow()
            
            # 使用 astream_events 获取流式事件。
            async for event in workflow.astream_events(workflow_input, version="v2"):
                yield event
    
        except Exception as e:
            print(f"错误：在流模式下更新场景失败: {str(e)}")
            raise RuntimeError(f"在流模式下更新场景失败: {str(e)}")



# 全局实例
scenario_manager = ScenarioManager()