"""
外部知识库管理器
负责加载、缓存和管理外部知识库内容
"""
import os
from pathlib import Path
from typing import Optional, Tuple


class ExternalKnowledgeManager:
    """外部知识库管理器，使用单例模式"""
    
    _instance = None
    _knowledge_content: Optional[str] = None
    _knowledge_path: Optional[str] = None
    _loaded: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load_knowledge(self, knowledge_path: str) -> Tuple[bool, Optional[str]]:
        """
        加载外部知识库文件到内存
        
        Args:
            knowledge_path: 外部知识库文件路径
            
        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        if not knowledge_path or not knowledge_path.strip():
            self._loaded = False
            self._knowledge_content = None
            self._knowledge_path = None
            return False, "外部知识库路径为空"
        
        # 如果已经加载过相同的文件，直接返回成功
        if self._loaded and self._knowledge_path == knowledge_path:
            return True, None
        
        try:
            # 检查文件是否存在
            knowledge_file = Path(knowledge_path)
            if not knowledge_file.exists():
                return False, f"文件不存在: {knowledge_path}"
            
            if not knowledge_file.is_file():
                return False, f"路径不是文件: {knowledge_path}"
            
            # 读取文件内容
            with open(knowledge_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查内容是否为空
            if not content.strip():
                return False, f"文件内容为空: {knowledge_path}"
            
            # 缓存内容
            self._knowledge_content = content
            self._knowledge_path = knowledge_path
            self._loaded = True
            
            # 获取文件大小信息
            file_size = knowledge_file.stat().st_size
            content_length = len(content)
            
            return True, f"成功加载 {file_size} 字节，{content_length} 字符"
            
        except UnicodeDecodeError as e:
            return False, f"文件编码错误，请确保文件为UTF-8编码: {e}"
        except PermissionError:
            return False, f"没有权限读取文件: {knowledge_path}"
        except Exception as e:
            return False, f"加载文件时发生错误: {str(e)}"
    
    def get_knowledge_content(self) -> Optional[str]:
        """
        获取已缓存的外部知识库内容
        
        Returns:
            Optional[str]: 知识库内容，如果未加载则返回None
        """
        return self._knowledge_content if self._loaded else None
    
    def is_loaded(self) -> bool:
        """
        检查外部知识库是否已加载
        
        Returns:
            bool: 是否已加载
        """
        return self._loaded
    
    def get_knowledge_path(self) -> Optional[str]:
        """
        获取当前加载的知识库文件路径
        
        Returns:
            Optional[str]: 文件路径，如果未加载则返回None
        """
        return self._knowledge_path if self._loaded else None
    
    def clear(self):
        """清空已缓存的知识库内容"""
        self._knowledge_content = None
        self._knowledge_path = None
        self._loaded = False
    
    def get_status_info(self) -> str:
        """
        获取知识库状态信息
        
        Returns:
            str: 状态信息字符串
        """
        if not self._loaded:
            return "未加载外部知识库"
        
        if self._knowledge_content:
            char_count = len(self._knowledge_content)
            line_count = self._knowledge_content.count('\n') + 1
            return f"已加载: {self._knowledge_path} ({char_count} 字符, {line_count} 行)"
        else:
            return "知识库已加载但内容为空"


# 创建全局实例
external_knowledge_manager = ExternalKnowledgeManager()