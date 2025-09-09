"""
Wikipedia搜索工具
提供日文Wikipedia词条搜索功能，用于角色扮演中的外部知识查询
"""

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper


def create_wikipedia_search_tool() -> dict:
    """
    创建Wikipedia搜索工具
    
    Returns:
        dict: 包含function和schema的工具配置字典
    """
    # 创建Wikipedia工具实例
    api_wrapper = WikipediaAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=2000,
        lang="ja"  # 固定为日文
    )
    
    wikipedia_tool = WikipediaQueryRun(
        name="wikipedia_search",
        description="查询日文Wikipedia词条。必须输入单个词条标题（如'東京'、'富士山'、'源氏物語'），不能输入完整句子或多个词汇。",
        api_wrapper=api_wrapper
    )
    
    def search_wikipedia(query: str) -> str:
        """查询日文Wikipedia词条
        
        Args:
            query: Wikipedia词条的标题（必须是单个词条名，不能是句子）
            正确：'東京'、'富士山'、'アニメ'、'源氏物語'
            错误：'东京的历史'、'富士山在哪里'、'什么是动漫'
            
        Returns:
            Wikipedia词条内容
        """
        try:
            result = wikipedia_tool.invoke(query)
            return f"[外部知识] {result}"
        except Exception as e:
            return f"Wikipedia搜索失败: {str(e)}"
    
    # 设置函数名称（用于OpenAI函数调用）
    search_wikipedia.__name__ = "search_wikipedia"
    
    # OpenAI 函数调用 schema 定义
    schema = {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "查询日文Wikipedia词条。必须输入单个词条标题（如'東京'、'富士山'、'源氏物語'），不能输入完整句子或多个词汇。返回词条的基础知识和背景信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Wikipedia词条的标题，必须是单个词条名，不能是句子。正确示例：'東京'、'富士山'、'アニメ'、'源氏物語'。错误示例：'东京的历史'、'富士山在哪里'、'什么是动漫'。"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
    
    return {
        "function": search_wikipedia,
        "schema": schema
    }


# 为了方便直接使用
__all__ = ["create_wikipedia_search_tool"]