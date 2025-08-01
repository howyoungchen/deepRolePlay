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
    
    async def get_current_scenario(self) -> str:
        """
        获取当前情景内容
        
        Returns:
            当前情景内容字符串
        """
        from utils.scenario_utils import read_scenario
        return await read_scenario()
    
    async def update_scenario(self, messages: List[Dict[str, Any]]) -> str:
        """
        同步更新情景，等待完成并返回更新后的情景内容
        
        Args:
            messages: 原始消息列表
            
        Returns:
            更新后的情景内容
        """
        try:
            # 获取当前情景内容
            current_scenario = await self.get_current_scenario()
            
            # 动态导入新的工作流以避免循环依赖
            from src.workflow.graph.scenario_workflow import create_scenario_workflow
            
            # 创建并调用工作流
            workflow = create_scenario_workflow()
            result = await workflow.ainvoke({
                "current_scenario": current_scenario,
                "messages": messages
            })
            
            # 获取结果（工作流已经保存了文件，这里只是验证）
            new_scenario = result.get("final_scenario", "")
            if new_scenario and new_scenario.strip() and new_scenario != "情景更新失败":
                await request_logger.log_info(f"情景更新成功，新情景长度: {len(new_scenario)}")
                return new_scenario
            else:
                await request_logger.log_warning("工作流未生成有效的情景内容")
                return ""
                
        except Exception as e:
            await request_logger.log_error(f"同步情景更新失败: {str(e)}")
            return ""
    


# 全局实例
scenario_manager = ScenarioManager()