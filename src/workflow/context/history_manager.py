"""
全局对话历史管理器

用于在workflow执行期间存储和管理当前对话历史，
使得re_search工具能够访问到内存中的对话数据。
"""
from typing import List, Dict, Any, Optional
import threading


class ConversationHistoryManager:
    """对话历史管理器 - 线程安全的全局状态管理"""
    
    def __init__(self):
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def set_history(self, messages: List[Dict[str, Any]]) -> None:
        """
        设置当前对话历史
        
        Args:
            messages: 对话历史列表，每个元素包含role和content字段
        """
        with self._lock:
            self._history = messages.copy() if messages else []
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取当前对话历史
        
        Returns:
            对话历史列表的副本
        """
        with self._lock:
            return self._history.copy()
    
    def clear_history(self) -> None:
        """清空对话历史"""
        with self._lock:
            self._history = []
    
    def is_empty(self) -> bool:
        """检查对话历史是否为空"""
        with self._lock:
            return len(self._history) == 0
    
    def get_message_count(self) -> int:
        """获取对话消息数量"""
        with self._lock:
            return len(self._history)


# 创建全局单例实例
conversation_history_manager = ConversationHistoryManager()


def set_conversation_history(messages: List[Dict[str, Any]]) -> None:
    """
    设置全局对话历史（便捷函数）
    
    Args:
        messages: 对话历史列表
    """
    conversation_history_manager.set_history(messages)


def get_conversation_history() -> List[Dict[str, Any]]:
    """
    获取全局对话历史（便捷函数）
    
    Returns:
        对话历史列表
    """
    return conversation_history_manager.get_history()


def clear_conversation_history() -> None:
    """清空全局对话历史（便捷函数）"""
    conversation_history_manager.clear_history()