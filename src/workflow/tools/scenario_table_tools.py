import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from prettytable import PrettyTable
from langchain_core.tools import tool
from config.manager import settings


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
            
            # 创建空模板数据
            empty_template = {
                "情景表": {
                    "description": "情景表 - 记录故事发生的主要事件时间线",
                    "columns": ["行号", "时间", "地点", "事件", "参与人", "备注"],
                    "rows": {},
                    "operation_guide": "增加：构建时间线和因果链，修改：纠正或完善事件理解，删除：当事件对理解当前情境失去价值时。事件字段需要描述清楚发生了什么，包括起因、过程、结果，避免过于简略如'谈话'、'争吵'等。备注：标记隐含信息和情境关联。"
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
            
            # 重置内存中的数据
            self.data = empty_template
            
            # 保存到文件
            result = self.persist()
            if not result:
                return False
            
            return True
            
        except Exception as e:
            print(f"重置失败: {e}")
            return False


# 全局实例
scenario_manager = ScenarioManager()


# LangGraph 工具接口
@tool("create_row", parse_docstring=True)
def create_row(table_name: str, row_data: dict) -> str:
    """在指定表格中创建一行数据。
    
    Args:
        table_name: 表格名称，使用read_table()查看可用表格
        row_data: 字典格式数据，键必须是表格中已存在的列名
    """
    return scenario_manager.create_row(table_name, row_data)


@tool("delete_row", parse_docstring=True)
def delete_row(table_name: str, row_id: str) -> str:
    """删除指定表格中指定行ID的数据。
    
    Args:
        table_name: 表格名称
        row_id: 行标识符，格式如"A1"、"B5"，使用read_table()查看现有行号
    """
    return scenario_manager.delete_row(table_name, row_id)


@tool("update_cell", parse_docstring=True)
def update_cell(table_name: str, row_id: str, column_name: str, new_value: str) -> str:
    """更新指定表格中指定行和列的单元格数据。
    
    Args:
        table_name: 表格名称
        row_id: 行标识符，如"A1"
        column_name: 列名，必须是表格中存在的列名
        new_value: 新的单元格内容
    """
    return scenario_manager.update_cell(table_name, row_id, column_name, new_value)


@tool("read_table", parse_docstring=True)
def read_table() -> str:
    """读取所有表格数据，显示完整的表格内容和操作指南。
    
    Args:
        无参数，返回所有表格的结构和数据，用于查看表格名、列名、行号等信息
    """
    return scenario_manager.get_all_pretty_tables(description=True, operation_guide=True)


@tool("reset_table", parse_docstring=True)  
def reset_table() -> str:
    """重置所有表格数据，清空所有内容并恢复为空模板状态。
    
    Args:
        无参数，执行后将永久删除所有表格中的数据，不可撤销
    """
    result = scenario_manager.reset()
    if result:
        return "成功: 所有表格已重置为空模板状态"
    else:
        return "错误: 表格重置失败"