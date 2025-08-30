"""
场景管理模块
负责场景文件管理和工作流调度
"""
import os
from typing import Dict, Any

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
    
    
    def _create_workflow(self):
        """创建工作流实例（提取公共逻辑）"""
        if settings.agent.workflow_mode == "drp":
            from src.workflow.graph.reAct_workflow import create_react_scenario_workflow
            return create_react_scenario_workflow()
        else:  # "fast" 或其他任何值，默认使用快速模式
            from src.workflow.graph.fast_scenario_workflow import create_fast_scenario_workflow
            return create_fast_scenario_workflow()
    
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
                return
            
            # 创建工作流
            workflow = self._create_workflow()
            
            # 非流式模式：只运行工作流，等待完成
            async for chunk in workflow.run(workflow_input):
                pass  # 只运行，不收集输出
    
        except Exception as e:
            raise RuntimeError(f"更新场景失败: {str(e)}")
    
    async def update_scenario_streaming(self, workflow_input: Dict[str, Any]):
        """
        流式更新场景，返回工作流执行中的流式事件。
        
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
            
            # 创建工作流
            workflow = self._create_workflow()
            
            # 流式模式：逐块产出事件
            async for chunk in workflow.run(workflow_input):
                # 包装成事件格式，兼容原有的 astream_events 接口
                yield {
                    "event": "on_chain_stream",
                    "data": {"chunk": chunk}
                }
    
        except Exception as e:
            print(f"错误：在流模式下更新场景失败: {str(e)}")
            raise RuntimeError(f"在流模式下更新场景失败: {str(e)}")
    



# 全局实例
scenario_manager = ScenarioManager()