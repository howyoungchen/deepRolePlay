"""
美化输出工具，支持打印到控制台和保存到文件
改造自playground/pretty_print_tool.py
"""
import os
from datetime import datetime
from langchain_core.messages import convert_to_messages


def pretty_print_message(message, indent=False, file_handle=None):
    """打印单个消息"""
    pretty_message = message.pretty_repr(html=True)
    
    if not indent:
        output = pretty_message
    else:
        output = "\n".join("\t" + c for c in pretty_message.split("\n"))
    
    # 打印到控制台
    print(output)
    
    # 如果提供了文件句柄，同时写入文件
    if file_handle:
        file_handle.write(output + "\n")
        file_handle.flush()


def pretty_print_messages(update, last_message=False, file_handle=None):
    """
    打印LangGraph更新消息
    
    Args:
        update: LangGraph更新数据
        last_message: 是否只显示最后一条消息
        file_handle: 可选的文件句柄，用于同时写入文件
    """
    is_subgraph = False
    if isinstance(update, tuple):
        ns, update = update
        # skip parent graph updates in the printouts
        if len(ns) == 0:
            return

        graph_id = ns[-1].split(":")[0]
        output = f"Update from subgraph {graph_id}:\n\n"
        print(output)
        if file_handle:
            file_handle.write(output)
        is_subgraph = True

    for node_name, node_update in update.items():
        update_label = f"Update from node {node_name}:\n\n"
        if is_subgraph:
            update_label = "\t" + update_label

        print(update_label)
        if file_handle:
            file_handle.write(update_label)

        messages = convert_to_messages(node_update["messages"])
        if last_message:
            messages = messages[-1:]

        for m in messages:
            pretty_print_message(m, indent=is_subgraph, file_handle=file_handle)
        
        print("\n")
        if file_handle:
            file_handle.write("\n")


def create_workflow_log_file(workflow_name: str) -> str:
    """
    为工作流创建日志文件
    
    Args:
        workflow_name: 工作流名称
        
    Returns:
        日志文件路径
    """
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    log_filename = f"{workflow_name}_{timestamp}.txt"
    log_path = os.path.join("logs", "workflow", log_filename)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    return log_path


def log_workflow_execution(workflow_name: str, update_data, last_message=False):
    """
    记录工作流执行到文件
    
    Args:
        workflow_name: 工作流名称
        update_data: 更新数据
        last_message: 是否只记录最后一条消息
    """
    log_path = create_workflow_log_file(workflow_name)
    
    with open(log_path, 'a', encoding='utf-8') as f:
        # 写入时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"=== {timestamp} ===\n")
        
        # 使用现有的pretty_print_messages函数，传入文件句柄
        pretty_print_messages(update_data, last_message=last_message, file_handle=f)
        
        f.write("\n" + "="*50 + "\n\n")
    
    return log_path