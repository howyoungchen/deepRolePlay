import json
import copy
from pathlib import Path
from typing import Dict, List, Any, Optional
from prettytable import PrettyTable
from config.manager import settings

# 全局空模板定义 - 所有表格的基础结构
EMPTY_TEMPLATE = {
    "情景表": {
        "description": "情景表 - 记录故事发生的主要事件时间线",
        "columns": ["行号", "时间", "地点", "事件", "参与人", "备注"],
        "rows": {},
        "operation_guide": "情景表至少需要包含3条情境。【行号意义】搜索结果里，<loc: n行以前>,n代表了事件在时间上的先后顺序，n越大，事件越早，【时间顺序】从上到下严格按时间发展（远→近）。绝对禁止前面条目的时间晚于或等于后面条目。绝对禁止不同条目使用相同时间。【时间表述】禁止猜测绝对时间，不明确时用相对时间：T+1天上午、T+2天傍晚、T+3天深夜等。【事件记录】每条包含：时间、地点、事件描述、参与人。【粒度原则】越早的情境可包含更广的时间跨度和更多概括的事件，越近的情境要求越详细具体。【新增原则】重要时间点的关键事件或状态转折时新增条目。"
    },
    "角色属性表": {
        "description": "角色属性表 - 定义角色的基本属性信息",
        "columns": ["行号", "角色名", "身份", "年龄", "性别", "社会关系", "备注"],
        "rows": {},
        "operation_guide": "增加：建立角色档案供理解其行为模式，修改：当发现角色属性理解有误或变化，删除：当角色对理解故事不再重要。备注：记录驱动角色行为的深层特质。"
    },
    "角色状态表": {
        "description": "角色状态表 - 追踪角色的当前状态和动态信息",
        "columns": ["行号", "角色名", "穿着", "精确动作", "情绪", "精确位置"],
        "rows": {},
        "operation_guide": "作为LLM的五官，增加：任何有助于'感觉到'和理解当前场景的状态信息，修改：当之前的观察不够准确或完整，删除：当这些细节对理解当前情境不再有帮助。"
    },
    "关键实体表": {
        "description": "关键实体表 - 记录重要的物品、地点或概念",
        "columns": ["行号", "实体名", "类别", "关键信息", "备注"],
        "rows": {},
        "operation_guide": "增加：追踪影响故事走向的关键要素，修改：当对实体的理解需要更新或深化，删除：当实体不再影响情节发展。备注：揭示实体的隐藏属性和潜在作用。"
    },
    "世界观表": {
        "description": "世界观表 - 定义故事世界的规则和背景",
        "columns": ["行号", "世界知识"],
        "rows": {},
        "operation_guide": "增加：建立理解故事的基础规则框架，修改：当发现规则理解有偏差或需要细化，删除：当规则被新设定取代或不再适用。"
    },
    "metadata": {
        "next_row_id": "A1",
        "row_id_sequence": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"],
        "current_letter_index": 0,
        "current_number": 1
    }
}


def get_all_table_names() -> List[str]:
    """获取所有表格名称（不包含metadata）"""
    return [name for name in EMPTY_TEMPLATE.keys() if name != "metadata"]


def get_table_names_string() -> str:
    """获取所有表格名称的字符串，用于提示词"""
    return "、".join(get_all_table_names())


def get_empty_template() -> Dict[str, Any]:
    """获取空模板的深拷贝"""
    return copy.deepcopy(EMPTY_TEMPLATE)


class ScenarioManager:
    """情景管理类 - 管理多个JSON表格的CRUD操作"""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.json_file_path: Optional[str] = None
        
    def init(self, json_file_path: str) -> bool:
        """初始化情景管理类，加载指定路径的JSON文件。
        如果文件不存在或初始化失败，则自动执行reset()创建空模板"""
        try:
            file_path = Path(json_file_path)
            
            # 设置文件路径（无论文件是否存在）
            self.json_file_path = json_file_path
            
            # 如果文件不存在，直接执行reset()
            if not file_path.exists():
                print(f"JSON文件不存在: {json_file_path}，自动执行reset()创建空模板")
                return self.reset()
            
            # 尝试加载现有文件
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                
                # 验证必要的元数据
                if "metadata" not in self.data:
                    self.data["metadata"] = {
                        "next_row_id": "A1",
                        "row_id_sequence": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"],
                        "current_letter_index": 0,
                        "current_number": 1
                    }
                
                return True
                
            except Exception as load_error:
                # 文件加载失败，执行reset()
                print(f"文件加载失败: {load_error}，自动执行reset()创建空模板")
                return self.reset()
                
        except Exception as e:
            print(f"初始化过程出错: {e}")
            # 如果已经设置了文件路径，尝试reset()
            if self.json_file_path:
                print("尝试执行reset()创建空模板")
                return self.reset()
            return False
    
    def persist(self) -> bool:
        """将当前的情景数据保存到JSON文件中"""
        try:
            if not self.json_file_path:
                raise ValueError("未初始化JSON文件路径")
            
            Path(self.json_file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False
    
    def reload_from_file(self) -> bool:
        """从JSON文件重新加载数据到内存中，如果文件不存在则自动触发reset()"""
        try:
            if not self.json_file_path:
                raise ValueError("未初始化JSON文件路径")
            
            file_path = Path(self.json_file_path)
            if not file_path.exists():
                print(f"JSON文件不存在: {self.json_file_path}，自动触发reset()")
                return self.reset()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            # 验证必要的元数据
            if "metadata" not in self.data:
                self.data["metadata"] = {
                    "next_row_id": "A1",
                    "row_id_sequence": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"],
                    "current_letter_index": 0,
                    "current_number": 1
                }
            
            return True
            
        except Exception as e:
            print(f"从文件重新加载失败: {e}，尝试触发reset()")
            return self.reset()
    
    def _get_next_row_id(self) -> str:
        """获取下一个行ID"""
        metadata = self.data["metadata"]
        letter_index = metadata["current_letter_index"]
        number = metadata["current_number"]
        letters = metadata["row_id_sequence"]
        
        current_letter = letters[letter_index]
        row_id = f"{current_letter}{number}"
        
        # 更新到下一个ID
        number += 1
        if number > 999:
            number = 1
            letter_index = (letter_index + 1) % len(letters)
        
        metadata["current_letter_index"] = letter_index
        metadata["current_number"] = number
        metadata["next_row_id"] = f"{letters[letter_index]}{number}"
        
        return row_id
    
    def _validate_table(self, table_name: str) -> bool:
        """验证表格是否存在"""
        return table_name in self.data and table_name != "metadata"
    
    def _validate_row_id(self, table_name: str, row_id: str) -> bool:
        """验证行ID是否存在"""
        if not self._validate_table(table_name):
            return False
        return row_id in self.data[table_name].get("rows", {})
    
    def _validate_column(self, table_name: str, column_name: str) -> bool:
        """验证列名是否存在"""
        if not self._validate_table(table_name):
            return False
        columns = self.data[table_name].get("columns", [])
        return column_name in columns
    
    def _validate_tool_operation(self, operation: str, table_name: str, *args, **kwargs) -> tuple[bool, str]:
        """验证工具操作是否正确使用"""
        if operation == "create_row":
            row_data = args[0] if args else kwargs.get('row_data', {})
            if not isinstance(row_data, dict):
                return False, "create_row操作需要提供字典类型的row_data参数"
            
            # 验证字段schema
            if not self._validate_table(table_name):
                return False, f"表格 '{table_name}' 不存在"
            
            columns = set(self.data[table_name].get("columns", []))
            provided_fields = set(row_data.keys())
            
            # 检查未定义字段  
            invalid_fields = provided_fields - columns
            if invalid_fields:
                return False, f"包含未定义字段: {list(invalid_fields)}，允许字段: {list(columns)}"
                
        elif operation == "delete_row":
            row_id = args[0] if args else kwargs.get('row_id', '')
            if not isinstance(row_id, str) or not row_id:
                return False, "delete_row操作需要提供非空字符串类型的row_id参数"
            
        elif operation == "update_cell":
            if len(args) < 3:
                return False, "update_cell操作需要提供row_id, column_name, new_value三个参数"
            row_id, column_name, new_value = args[:3]
            if not isinstance(row_id, str) or not isinstance(column_name, str):
                return False, "update_cell操作的row_id和column_name参数必须是字符串类型"
        
        return True, ""
    
    def create_row(self, table_name: str, row_data: dict) -> str:
        """在指定表格中创建一行数据"""
        try:
            if not self._validate_table(table_name):
                return f"错误: 表格 '{table_name}' 不存在"
            
            # 校验工具操作
            is_valid, error_msg = self._validate_tool_operation("create_row", table_name, row_data)
            if not is_valid:
                return f"错误: {error_msg}"
            
            # 获取新的行ID
            new_row_id = self._get_next_row_id()
            
            # 确保行数据包含行号
            row_data["行号"] = new_row_id
            
            # 添加行数据
            if "rows" not in self.data[table_name]:
                self.data[table_name]["rows"] = {}
            
            self.data[table_name]["rows"][new_row_id] = row_data
            
            # 自动保存
            self.persist()
            
            return f"成功: 在表格 '{table_name}' 中创建了行 '{new_row_id}'"
            
        except Exception as e:
            return f"错误: 创建行失败 - {e}"
    
    def delete_row(self, table_name: str, row_id: str) -> str:
        """删除指定表格中指定行ID的数据"""
        try:
            # 校验工具操作
            is_valid, error_msg = self._validate_tool_operation("delete_row", table_name, row_id)
            if not is_valid:
                return f"错误: {error_msg}"
                
            if not self._validate_table(table_name):
                return f"错误: 表格 '{table_name}' 不存在"
            
            if not self._validate_row_id(table_name, row_id):
                return f"错误: 行ID '{row_id}' 在表格 '{table_name}' 中不存在"
            
            # 删除行
            del self.data[table_name]["rows"][row_id]
            
            # 自动保存
            self.persist()
            
            return f"成功: 从表格 '{table_name}' 中删除了行 '{row_id}'"
            
        except Exception as e:
            return f"错误: 删除行失败 - {e}"
    
    def update_cell(self, table_name: str, row_id: str, column_name: str, new_value) -> str:
        """更新指定表格中指定行ID的指定列的数据"""
        try:
            # 校验工具操作
            is_valid, error_msg = self._validate_tool_operation("update_cell", table_name, row_id, column_name, new_value)
            if not is_valid:
                return f"错误: {error_msg}"
                
            if not self._validate_table(table_name):
                return f"错误: 表格 '{table_name}' 不存在"
            
            if not self._validate_row_id(table_name, row_id):
                return f"错误: 行ID '{row_id}' 在表格 '{table_name}' 中不存在"
            
            if not self._validate_column(table_name, column_name):
                return f"错误: 列名 '{column_name}' 在表格 '{table_name}' 中不存在"
            
            # 更新单元格
            self.data[table_name]["rows"][row_id][column_name] = new_value
            
            # 自动保存
            self.persist()
            
            return f"成功: 更新了表格 '{table_name}' 行 '{row_id}' 列 '{column_name}' 的值"
            
        except Exception as e:
            return f"错误: 更新单元格失败 - {e}"
    
    def get_pretty_table(self, table_name: str, description: bool = True, operation_guide: bool = True) -> str:
        """返回指定表格的紧凑分隔符格式表示或JSON字符串"""
        try:
            # 强制从文件重新加载数据
            self.reload_from_file()
            
            if not self._validate_table(table_name):
                return f"错误: 表格 '{table_name}' 不存在"
            
            table_data = self.data[table_name]
            
            # 检查输出格式配置
            output_format = settings.scenario.output_format
            
            if output_format == "json":
                # 返回JSON格式
                result = {
                    "table_name": table_name
                }
                
                # 根据参数控制添加描述和操作指南
                if description and "description" in table_data:
                    result["description"] = table_data["description"]
                
                if operation_guide and "operation_guide" in table_data:
                    result["operation_guide"] = table_data["operation_guide"]
                
                # 添加行数据（不包含columns字段，因为每个row已经包含所有字段）
                rows = table_data.get("rows", {})
                if rows:
                    # 按行ID排序并转换为列表
                    result["rows"] = [rows[row_id] for row_id in sorted(rows.keys())]
                else:
                    result["rows"] = []
                
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                # 原有的表格格式
                result = []
                
                # 构建表头信息
                header_parts = []
                
                # 添加表名/描述
                if description and "description" in table_data:
                    header_parts.append(table_data['description'])
                else:
                    header_parts.append(table_name)
                
                # 添加操作指南到表头
                if operation_guide and "operation_guide" in table_data:
                    header_parts.append(f"操作指南: {table_data['operation_guide']}")
                
                # 组合表头
                result.append(" - ".join(header_parts))
                
                # 创建表格
                columns = table_data.get("columns", [])
                rows = table_data.get("rows", {})
                
                if not rows:
                    result.append("表格为空")
                    return "\n".join(result)
                
                # 添加表格说明和列名行
                result.append("以下为对应表格：")
                result.append("|".join(columns))
                
                # 添加行数据
                for row_id in sorted(rows.keys()):
                    row_data = rows[row_id]
                    row_values = []
                    for col in columns:
                        value = row_data.get(col, "")
                        # 处理列表类型的数据
                        if isinstance(value, list):
                            value = ", ".join(str(item) for item in value)
                        # 清理分隔符，避免格式错乱
                        value_str = str(value).replace("|", "丨").replace("\n", " ")
                        row_values.append(value_str)
                    result.append("|".join(row_values))
                
                return "\n".join(result)
            
        except Exception as e:
            return f"错误: 获取表格失败 - {e}"
    
    def get_all_pretty_tables(self, description: bool = True, operation_guide: bool = True) -> str:
        """返回所有表格的紧凑分隔符格式表示或JSON字符串"""
        try:
            # 强制从文件重新加载数据
            self.reload_from_file()
            
            # 检查输出格式配置
            output_format = settings.scenario.output_format
            
            if output_format == "json":
                # 返回JSON格式 - 包含所有表格的数组
                all_tables = []
                
                for table_name in self.data:
                    if table_name == "metadata":
                        continue
                    
                    table_data = self.data[table_name]
                    result = {
                        "table_name": table_name
                    }
                    
                    # 根据参数控制添加描述和操作指南
                    if description and "description" in table_data:
                        result["description"] = table_data["description"]
                    
                    if operation_guide and "operation_guide" in table_data:
                        result["operation_guide"] = table_data["operation_guide"]
                    
                    # 添加行数据（不包含columns字段）
                    rows = table_data.get("rows", {})
                    if rows:
                        # 按行ID排序并转换为列表
                        result["rows"] = [rows[row_id] for row_id in sorted(rows.keys())]
                    else:
                        result["rows"] = []
                    
                    all_tables.append(result)
                
                return json.dumps(all_tables, ensure_ascii=False, indent=2)
            
            else:
                # 原有的表格格式
                result = []
                
                for table_name in self.data:
                    if table_name == "metadata":
                        continue
                    
                    table_str = self.get_pretty_table(table_name, description, operation_guide)
                    result.append(table_str)
                    result.append("")  # 空行分隔，替代长分隔符
                
                return "\n".join(result)
            
        except Exception as e:
            return f"错误: 获取所有表格失败 - {e}"
    
    def get_table_schema_text(self) -> str:
        """生成所有表格的字段定义文本，用于提示词"""
        schema_lines = ["\n**严格字段要求 - 必须遵守**：\n"]
        
        for table_name in self.data:
            if table_name == "metadata":
                continue
                
            columns = self.data[table_name].get("columns", [])
            schema_lines.append(f"{table_name}字段：{columns}")
        
        return "\n".join(schema_lines)
    
    def reset(self) -> bool:
        """重置情景管理类，使用空模板数据重新初始化，然后保存覆盖当前json文件"""
        try:
            if not self.json_file_path:
                raise ValueError("未初始化JSON文件路径")
            
            # 使用全局空模板数据
            self.data = get_empty_template()
            
            # 保存到文件
            result = self.persist()
            if not result:
                return False
            
            return True
            
        except Exception as e:
            print(f"重置失败: {e}")
            return False


# 全局实例 - 直接在创建时初始化
scenario_manager = ScenarioManager()
scenario_manager.init(settings.scenario.file_path)


# OpenAI 函数调用工具定义

async def create_row(table_name: str, row_data: dict) -> str:
    """在指定表格中创建一行数据"""
    return scenario_manager.create_row(table_name, row_data)


async def delete_row(table_name: str, row_id: str) -> str:
    """删除指定表格中指定行ID的数据"""
    return scenario_manager.delete_row(table_name, row_id)


async def update_cell(table_name: str, row_id: str, column_name: str, new_value: str) -> str:
    """更新指定表格中指定行和列的单元格数据"""
    return scenario_manager.update_cell(table_name, row_id, column_name, new_value)


async def read_table(table_name: Optional[str] = None) -> str:
    """读取表格数据
    
    Args:
        table_name: 可选参数，指定要读取的表格名称
                   如果为None，则读取所有表格数据
                   如果指定表格名称，则只读取该表格的数据
    """
    if table_name is None:
        return scenario_manager.get_all_pretty_tables(description=True, operation_guide=True)
    else:
        return scenario_manager.get_pretty_table(table_name, description=True, operation_guide=True)


async def reset_table() -> str:
    """重置所有表格数据"""
    result = scenario_manager.reset()
    if result:
        return "成功: 所有表格已重置为空模板状态"
    else:
        return "错误: 表格重置失败"


# OpenAI 函数调用 schema 定义

create_row_schema = {
    "type": "function",
    "function": {
        "name": "create_row",
        "description": """在指定表格中创建一行数据。用于记录新发现的信息。

使用场景：
- 需要记录新发现的重要信息元素
- 当前对话中出现了需要持久化的数据
- 补充背景设定或状态信息

不要使用的情况：
- 信息不够完整或不确定时
- 重复已存在的信息""",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": """目标表格的名称。

系统管理多个表格来组织不同类型的信息，常见表格类型包括但不限于：事件记录、角色信息、物品道具、世界设定等。"""
                },
                "row_data": {
                    "type": "object",
                    "description": """要插入的数据，格式为键值对字典。

每个表格有其预定义的字段结构，提供的字段名必须与表格定义完全匹配。
格式示例：{\"字段1\": \"值1\", \"字段2\": \"值2\"}
注意：系统会自动生成行标识符，无需手动提供行号字段。"""
                }
            },
            "required": ["table_name", "row_data"],
            "additionalProperties": False
        },
        "strict": True
    }
}

delete_row_schema = {
    "type": "function",
    "function": {
        "name": "delete_row",
        "description": """删除指定表格中的特定行数据。用于清理过时、错误或不再相关的信息。

使用场景：
- 信息过时或不再相关
- 发现记录的信息有误且无法修复
- 需要清理冗余或重复的数据

不要使用的情况：
- 信息仍然有参考价值
- 可以通过 update_cell 修正的错误
- 不确定是否应该删除时

操作提醒：删除操作不可撤销，请谨慎使用""",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": """目标表格的名称。

确保表格名称与系统中实际存在的表格完全匹配。"""
                },
                "row_id": {
                    "type": "string",
                    "description": """要删除的行的标识符。

格式：通常为字母+数字组合，如 \"A1\"、\"B5\" 等
注意：行ID必须与表格中实际存在的行完全匹配"""
                }
            },
            "required": ["table_name", "row_id"],
            "additionalProperties": False
        },
        "strict": True
    }
}

update_cell_schema = {
    "type": "function",
    "function": {
        "name": "update_cell",
        "description": """更新指定表格中特定单元格的数据。用于修正或完善已有信息。

使用场景：
- 需要修正或完善已有信息
- 数据发生变化需要更新
- 补充遗漏的详细信息
- 纠正理解偏差

不要使用的情况：
- 信息变化足够大需要创建新行时
- 字段不存在时（应先确认字段名）

更新策略：针对性修改特定字段，保持其他信息不变""",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": """目标表格的名称。

确保表格名称与系统中实际存在的表格完全匹配。"""
                },
                "row_id": {
                    "type": "string",
                    "description": """要更新的行的标识符。

格式：通常为字母+数字组合，如 \"A1\"、\"B5\" 等
要求：必须是表格中实际存在的行标识符"""
                },
                "column_name": {
                    "type": "string",
                    "description": """要更新的列（字段）名称。

重要：字段名必须与表格定义完全匹配，区分大小写"""
                },
                "new_value": {
                    "type": "string",
                    "description": """新的单元格内容，用于替换原有内容。

要求：
- 提供完整、准确的新值
- 内容应该与字段的含义和数据类型相符
- 以字符串形式提供，系统会适当处理数据类型"""
                }
            },
            "required": ["table_name", "row_id", "column_name", "new_value"],
            "additionalProperties": False
        },
        "strict": True
    }
}

def _create_read_table_schema():
    """动态创建read_table的schema，使用动态表格名"""
    table_names = get_table_names_string()
    return {
        "type": "function",
        "function": {
            "name": "read_table",
            "description": """读取表格数据，支持读取所有表格或指定单个表格。

使用场景：
- 需要了解当前所有记录的信息（不提供参数）
- 只查看特定表格内容（提供table_name参数）
- 查看表格结构和字段定义
- 确认行ID和数据内容
- 规划后续的表格操作

不要使用的情况：
- 只需要特定信息时（应使用搜索工具）
- 频繁调用造成信息冗余

返回信息包含：
- 表格的名称和描述
- 表格的操作指南
- 完整的列名定义
- 所有行数据内容
- 空表格状态提示

输出格式：根据系统配置返回表格格式或JSON格式""",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": f"""可选参数，指定要读取的表格名称。

如果不提供此参数，将读取所有表格数据。
如果提供表格名称，将只返回指定表格的数据。

可用表格名称：{table_names}"""
                    }
                },
                "additionalProperties": False
            },
            "strict": True
        }
    }

# 动态生成read_table_schema
read_table_schema = _create_read_table_schema()

reset_table_schema = {
    "type": "function",
    "function": {
        "name": "reset_table",
        "description": """重置所有表格数据，清空所有内容并恢复为空模板状态。这是一个危险操作，会永久删除所有数据。

使用场景：
- 开始全新的角色扮演场景
- 当前数据完全不适用于新情境
- 需要彻底清理所有历史记录

不要使用的情况：
- 只需要删除部分数据时（应使用delete_row）
- 数据仍有部分参考价值时
- 不确定是否需要完全重置时

重要警告：
- 此操作不可撤销
- 将永久删除所有表格中的数据
- 请确保真正需要完全重置后再使用

操作结果：
- 成功：所有表格恢复为空模板状态
- 失败：返回具体错误信息""",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        "strict": True
    }
}

# 导出工具配置
table_tools = [
    {
        "function": create_row,
        "schema": create_row_schema
    },
    {
        "function": delete_row,
        "schema": delete_row_schema
    },
    {
        "function": update_cell,
        "schema": update_cell_schema
    },
    # {
    #     "function": read_table,
    #     "schema": read_table_schema
    # },
    # {
    #     "function": reset_table,
    #     "schema": reset_table_schema
    # }
]

# 为了方便直接使用，也可以单独导出
__all__ = [
    # 空模板和工具函数
    "EMPTY_TEMPLATE", "get_all_table_names", "get_table_names_string", "get_empty_template",
    # 操作函数和schema
    "create_row", "create_row_schema",
    "delete_row", "delete_row_schema", 
    "update_cell", "update_cell_schema",
    "read_table", "read_table_schema",
    "reset_table", "reset_table_schema",
    # 工具集合和管理器实例
    "table_tools", "scenario_manager"
]