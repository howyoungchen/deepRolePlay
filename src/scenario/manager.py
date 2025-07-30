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
        try:
            # 检查文件是否存在
            if not os.path.exists(self.scenario_file_path):
                # 如果文件不存在，创建默认情景
                default_scenario = "这是一个全新的对话开始。"
                await self._save_scenario_to_file(default_scenario)
                return default_scenario
            
            # 直接读取文件
            async with aiofiles.open(self.scenario_file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            return content.strip()
            
        except Exception as e:
            await request_logger.log_error(f"获取情景文件失败: {str(e)}")
            # 返回默认情景
            return "这是一个全新的对话开始。"
    
    async def update_scenario(self, messages: List[Dict[str, Any]]) -> None:
        """
        同步更新情景，等待完成
        
        Args:
            messages: 原始消息列表
        """
        try:
            # 直接调用工作流更新逻辑，使用 await 同步等待
            await self._update_scenario_workflow(messages)
        except Exception as e:
            await request_logger.log_error(f"同步情景更新失败: {str(e)}")
    
    async def _update_scenario_workflow(self, messages: List[Dict[str, Any]]) -> None:
        """
        运行情景更新工作流
        
        Args:
            messages: 原始消息列表
        """
        try:
            # 动态导入以避免循环依赖
            from src.workflow.graph.scenario_updater import ScenarioUpdaterAgent
            
            # 创建工作流实例
            updater = ScenarioUpdaterAgent()
            
            # 运行工作流生成新情景
            new_scenario = await updater.generate_scenario(messages)
            
            if new_scenario and new_scenario.strip():
                # 保存新情景到文件
                await self._save_scenario_to_file(new_scenario)
                
                await request_logger.log_info(f"情景更新成功，新情景长度: {len(new_scenario)}")
            else:
                await request_logger.log_warning("工作流未生成有效的情景内容")
                
        except Exception as e:
            await request_logger.log_error(f"情景更新工作流执行失败: {str(e)}")
    
    async def _save_scenario_to_file(self, scenario_content: str) -> None:
        """
        保存情景内容到文件
        
        Args:
            scenario_content: 情景内容
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.scenario_file_path), exist_ok=True)
            
            # 异步写入文件
            async with aiofiles.open(self.scenario_file_path, 'w', encoding='utf-8') as f:
                await f.write(scenario_content)
            
            # 同时保存带时间戳的备份
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(
                os.path.dirname(self.scenario_file_path),
                f"scenario_backup_{timestamp}.txt"
            )
            
            async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                await f.write(scenario_content)
                
        except Exception as e:
            await request_logger.log_error(f"保存情景文件失败: {str(e)}")
            raise
    
    
    async def get_scenario_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取情景历史记录
        
        Args:
            limit: 返回的历史记录数量限制
            
        Returns:
            情景历史记录列表
        """
        try:
            scenarios_dir = os.path.dirname(self.scenario_file_path)
            history_files = []
            
            # 查找所有备份文件
            for filename in os.listdir(scenarios_dir):
                if filename.startswith("scenario_backup_") and filename.endswith(".txt"):
                    file_path = os.path.join(scenarios_dir, filename)
                    # 提取时间戳
                    timestamp_str = filename.replace("scenario_backup_", "").replace(".txt", "")
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        history_files.append({
                            "path": file_path,
                            "timestamp": timestamp,
                            "filename": filename
                        })
                    except ValueError:
                        continue
            
            # 按时间戳倒序排序
            history_files.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # 限制数量
            history_files = history_files[:limit]
            
            # 读取文件内容
            history_records = []
            for file_info in history_files:
                try:
                    async with aiofiles.open(file_info["path"], 'r', encoding='utf-8') as f:
                        content = await f.read()
                    
                    history_records.append({
                        "timestamp": file_info["timestamp"].isoformat(),
                        "filename": file_info["filename"],
                        "content": content.strip(),
                        "length": len(content.strip())
                    })
                except Exception as e:
                    await request_logger.log_warning(f"读取历史文件失败 {file_info['filename']}: {str(e)}")
                    continue
            
            return history_records
            
        except Exception as e:
            await request_logger.log_error(f"获取情景历史失败: {str(e)}")
            return []
    
    async def manually_update_scenario(self, new_scenario: str) -> bool:
        """
        手动更新情景
        
        Args:
            new_scenario: 新的情景内容
            
        Returns:
            更新是否成功
        """
        try:
            if not new_scenario or not new_scenario.strip():
                raise ValueError("情景内容不能为空")
            
            await self._save_scenario_to_file(new_scenario.strip())
            
            await request_logger.log_info(f"手动更新情景成功，新情景长度: {len(new_scenario)}")
            return True
            
        except Exception as e:
            await request_logger.log_error(f"手动更新情景失败: {str(e)}")
            return False


# 全局实例
scenario_manager = ScenarioManager()