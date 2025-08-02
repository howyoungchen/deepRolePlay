"""
情景管理模块
负责情景文件管理和工作流调度
"""
import os
import aiofiles
from typing import List, Dict, Any
from datetime import datetime

from config.manager import settings
from utils.logger import request_logger


class ScenarioManager:
    """情景管理器"""
    
    def __init__(self):
        """初始化情景管理器"""
        # 从配置中获取情景文件路径，如果不存在则使用默认值
        if hasattr(settings, 'scenario') and hasattr(settings.scenario, 'file_path'):
            self.scenario_file_path = settings.scenario.file_path
        else:
            self.scenario_file_path = "./scenarios/current_scenario.txt"
        
        # 确保scenarios目录存在
        os.makedirs(os.path.dirname(self.scenario_file_path), exist_ok=True)
    
    
    async def update_scenario(self, messages: List[Dict[str, Any]]):
        """
        同步更新情景，等待完成并返回更新后的情景内容
        
        Args:
            messages: 原始消息列表
            
        Returns:
            更新后的情景内容
        """
        try:
            # 获取当前情景内容
            from utils.scenario_utils import read_scenario
            current_scenario = read_scenario()
            
            # 动态导入新的工作流以避免循环依赖
            from src.workflow.graph.scenario_workflow import create_scenario_workflow
            
            # 创建并调用工作流
            workflow = create_scenario_workflow()
            await workflow.ainvoke({
                "current_scenario": current_scenario,
                "messages": messages
            })
    
        except Exception as e:
            raise RuntimeError(f"更新情景失败: {str(e)}")
    


# 全局实例
scenario_manager = ScenarioManager()