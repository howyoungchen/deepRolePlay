"""
情景文件读写工具函数
"""
import os
import aiofiles
from config.manager import settings
from utils.logger import request_logger


def get_scenario_file_path() -> str:
    """获取情景文件的绝对路径"""
    return os.path.abspath(settings.scenario.file_path)


async def read_scenario() -> str:
    """
    读取当前情景内容
    
    Returns:
        当前情景内容字符串
    """
    scenario_file_path = get_scenario_file_path()
    
    try:
        # 检查文件是否存在
        if not os.path.exists(scenario_file_path):
            # 如果文件不存在，创建默认情景
            default_scenario = "这是一个全新的对话开始。"
            await write_scenario(default_scenario)
            return default_scenario
        
        # 直接读取文件
        async with aiofiles.open(scenario_file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        return content.strip()
        
    except Exception as e:
        await request_logger.log_error(f"读取情景文件失败: {str(e)}")
        # 返回默认情景
        return "这是一个全新的对话开始。"


async def write_scenario(content: str) -> None:
    """
    写入情景内容到文件
    
    Args:
        content: 情景内容
    """
    scenario_file_path = get_scenario_file_path()
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(scenario_file_path), exist_ok=True)
        
        # 写入文件
        async with aiofiles.open(scenario_file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
            
        await request_logger.log_info(f"情景文件保存成功: {scenario_file_path}")
        
    except Exception as e:
        await request_logger.log_error(f"保存情景文件失败: {str(e)}")
        raise


