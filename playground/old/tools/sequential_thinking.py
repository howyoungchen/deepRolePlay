import os
import json
from typing import Dict, List, Optional, Any, Union
from langchain_core.tools import tool

# ANSI颜色代码
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


class SequentialThinkingManager:
    """管理思考历史和分支的核心类"""
    
    def __init__(self):
        self.thought_history: List[Dict[str, Any]] = []
        self.branches: Dict[str, List[Dict[str, Any]]] = {}
        self.disable_thought_logging = os.environ.get("DISABLE_THOUGHT_LOGGING", "").lower() == "true"
    
    def validate_thought_data(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证输入的思考数据"""
        if not input_data.get('thought') or not isinstance(input_data['thought'], str):
            raise ValueError('无效的thought: 必须是字符串')
        
        if not input_data.get('thought_number') or not isinstance(input_data['thought_number'], int):
            raise ValueError('无效的thought_number: 必须是数字')
        
        if not input_data.get('total_thoughts') or not isinstance(input_data['total_thoughts'], int):
            raise ValueError('无效的total_thoughts: 必须是数字')
        
        if 'next_thought_needed' not in input_data or not isinstance(input_data['next_thought_needed'], bool):
            raise ValueError('无效的next_thought_needed: 必须是布尔值')
        
        return {
            'thought': input_data['thought'],
            'thought_number': input_data['thought_number'],
            'total_thoughts': input_data['total_thoughts'],
            'next_thought_needed': input_data['next_thought_needed'],
            'is_revision': input_data.get('is_revision', False),
            'revises_thought': input_data.get('revises_thought'),
            'branch_from_thought': input_data.get('branch_from_thought'),
            'branch_id': input_data.get('branch_id'),
            'needs_more_thoughts': input_data.get('needs_more_thoughts', False)
        }
    
    def format_thought(self, thought_data: Dict[str, Any]) -> str:
        """格式化思考输出，带颜色和边框"""
        thought_number = thought_data['thought_number']
        total_thoughts = thought_data['total_thoughts']
        thought = thought_data['thought']
        is_revision = thought_data.get('is_revision', False)
        revises_thought = thought_data.get('revises_thought')
        branch_from_thought = thought_data.get('branch_from_thought')
        branch_id = thought_data.get('branch_id')
        
        # 设置前缀和上下文
        if is_revision:
            prefix = f"{Colors.YELLOW}🔄 修订{Colors.RESET}"
            context = f" (修订思考 {revises_thought})"
        elif branch_from_thought and branch_id:
            prefix = f"{Colors.GREEN}🌿 分支{Colors.RESET}"
            context = f" (从思考 {branch_from_thought} 分支, ID: {branch_id})"
        else:
            prefix = f"{Colors.BLUE}💭 思考{Colors.RESET}"
            context = ''
        
        header = f"{prefix} {thought_number}/{total_thoughts}{context}"
        # 计算实际显示长度（去除ANSI转义序列）
        header_display_len = len(f"💭 思考 {thought_number}/{total_thoughts}{context}")
        border_len = max(header_display_len, len(thought)) + 4
        border = '─' * border_len
        
        # 格式化输出
        output = f"\n┌{border}┐\n"
        output += f"│ {header}{' ' * (border_len - header_display_len - 2)} │\n"
        output += f"├{border}┤\n"
        output += f"│ {thought}{' ' * (border_len - len(thought) - 2)} │\n"
        output += f"└{border}┘"
        
        return output
    
    def process_thought(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理一个思考步骤"""
        try:
            # 验证输入数据
            validated_data = self.validate_thought_data(input_data)
            
            # 如果思考编号超过总数，自动调整总数
            if validated_data['thought_number'] > validated_data['total_thoughts']:
                validated_data['total_thoughts'] = validated_data['thought_number']
            
            # 添加到思考历史
            self.thought_history.append(validated_data)
            
            # 如果是分支，添加到分支记录
            if validated_data.get('branch_from_thought') and validated_data.get('branch_id'):
                branch_id = validated_data['branch_id']
                if branch_id not in self.branches:
                    self.branches[branch_id] = []
                self.branches[branch_id].append(validated_data)
            
            # 如果未禁用日志，输出格式化的思考
            if not self.disable_thought_logging:
                formatted_thought = self.format_thought(validated_data)
                print(formatted_thought)
            
            # 返回处理结果
            return {
                'success': True,
                'thought_number': validated_data['thought_number'],
                'total_thoughts': validated_data['total_thoughts'],
                'next_thought_needed': validated_data['next_thought_needed'],
                'branches': list(self.branches.keys()),
                'thought_history_length': len(self.thought_history)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status': 'failed'
            }


# 创建全局管理器实例
_manager = SequentialThinkingManager()


@tool
def sequential_thinking(
    thought: str,
    next_thought_needed: bool,
    thought_number: int,
    total_thoughts: int,
    is_revision: Optional[bool] = None,
    revises_thought: Optional[int] = None,
    branch_from_thought: Optional[int] = None,
    branch_id: Optional[str] = None,
    needs_more_thoughts: Optional[bool] = None
) -> str:
    """用于动态和反思性问题解决的详细思考工具。
    
    这个工具通过灵活的思考过程帮助分析问题，可以随着理解的深入而适应和演变。
    每个思考可以建立在、质疑或修订之前的见解之上。
    
    何时使用此工具：
    - 将复杂问题分解为步骤
    - 需要修订空间的规划和设计
    - 可能需要修正路线的分析
    - 初始时完整范围可能不清楚的问题
    - 需要多步骤解决方案的问题
    - 需要在多个步骤中保持上下文的任务
    - 需要过滤掉无关信息的情况
    
    主要特性：
    - 可以随着进展上下调整total_thoughts
    - 可以质疑或修订之前的思考
    - 即使看似到达终点后也可以添加更多思考
    - 可以表达不确定性并探索替代方法
    - 不是每个思考都需要线性构建 - 可以分支或回溯
    - 生成解决方案假设
    - 基于思考链步骤验证假设
    - 重复该过程直到满意
    - 提供正确答案
    
    参数说明：
    - thought: 当前的思考步骤，可以包括：
      * 常规分析步骤
      * 对之前思考的修订
      * 对之前决定的质疑
      * 关于需要更多分析的认识
      * 方法的改变
      * 假设生成
      * 假设验证
    - next_thought_needed: 如果需要更多思考则为True，即使看似在终点
    - thought_number: 序列中的当前编号（如果需要可以超过初始总数）
    - total_thoughts: 当前预估需要的思考数（可以上下调整）
    - is_revision: 布尔值，指示是否修订之前的思考
    - revises_thought: 如果is_revision为true，指定正在重新考虑哪个思考编号
    - branch_from_thought: 如果分支，指定分支点的思考编号
    - branch_id: 当前分支的标识符（如果有）
    - needs_more_thoughts: 如果到达终点但意识到需要更多思考
    
    你应该：
    1. 从需要的思考数的初始估计开始，但准备好调整
    2. 自由地质疑或修订之前的思考
    3. 如果需要，不要犹豫添加更多思考，即使在"终点"
    4. 在存在时表达不确定性
    5. 标记修订之前思考或分支到新路径的思考
    6. 忽略与当前步骤无关的信息
    7. 在适当时生成解决方案假设
    8. 基于思考链步骤验证假设
    9. 重复该过程直到对解决方案满意
    10. 提供单一的、理想上正确的答案作为最终输出
    11. 只有在真正完成并达到满意答案时才将next_thought_needed设置为false
    
    Args:
        thought: 当前的思考步骤
        next_thought_needed: 是否需要另一个思考步骤
        thought_number: 当前思考编号（最小值为1）
        total_thoughts: 预估总思考数（最小值为1）
        is_revision: 是否修订之前的思考
        revises_thought: 正在重新考虑哪个思考（最小值为1）
        branch_from_thought: 分支点思考编号（最小值为1）
        branch_id: 分支标识符
        needs_more_thoughts: 是否需要更多思考
        
    Returns:
        str: JSON格式的处理结果，包含思考编号、总数、是否需要继续等信息
    """
    # 构建输入数据
    input_data = {
        'thought': thought,
        'next_thought_needed': next_thought_needed,
        'thought_number': thought_number,
        'total_thoughts': total_thoughts
    }
    
    # 添加可选参数
    if is_revision is not None:
        input_data['is_revision'] = is_revision
    if revises_thought is not None:
        input_data['revises_thought'] = revises_thought
    if branch_from_thought is not None:
        input_data['branch_from_thought'] = branch_from_thought
    if branch_id is not None:
        input_data['branch_id'] = branch_id
    if needs_more_thoughts is not None:
        input_data['needs_more_thoughts'] = needs_more_thoughts
    
    # 处理思考
    result = _manager.process_thought(input_data)
    
    # 返回JSON格式的结果
    return json.dumps(result, ensure_ascii=False, indent=2)