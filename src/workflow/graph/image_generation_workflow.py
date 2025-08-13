"""
图片生成工作流 - 基于情景生成图片
"""
import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from config.manager import settings
# 已移除workflow_logger，使用简单的日志保存
from src.workflow.tools.image_generation_tool import generate_one_img
from src.workflow.tools.scenario_table_tools import scenario_manager
from src.prompts.image_generation_prompts import IMAGE_SYSTEM_PROMPT, IMAGE_USER_PROMPT_TEMPLATE

# 模块级初始化scenario_manager
scenario_manager.init(settings.scenario.file_path)


class ImageGenerationState(TypedDict):
    """图片生成工作流状态定义"""
    # 输入
    current_scenario: str
    
    # 中间状态
    image_prompt: str
    tool_calls: List[Dict[str, Any]]
    
    # 输出
    generated_image_paths: List[str]


async def init_scenario_node(state: ImageGenerationState) -> Dict[str, Any]:
    """初始化节点：读取表格内容"""
    print("🚀 Scenario table initialization...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    inputs = {
        "node_type": "init_scenario_image",
        "input_state_keys": list(state.keys()) if state else []
    }
    
    try:
        # 直接从scenario_manager读取所有表格内容
        current_scenario = scenario_manager.get_all_pretty_tables(description=True, operation_guide=False)
        
        duration = time.time() - start_time
        
        outputs = {
            "scenario_length": len(current_scenario),
            "scenario_preview": current_scenario[:200] + "..." if len(current_scenario) > 200 else current_scenario
        }
        
        # init_scenario_node不调用LLM，无需记录日志
        
        print(f"  ✓ Loaded scenario tables, total length: {len(current_scenario)}", flush=True)
        return {"current_scenario": current_scenario}
        
    except Exception as e:
        duration = time.time() - start_time
        import traceback
        error_details = traceback.format_exc()
        
        # 错误不记录日志，只输出到控制台
        
        print(f"  ❌ Scenario table initialization failed: {str(e)}", flush=True)
        return {"current_scenario": "Scenario tables not initialized or empty."}


async def llm_generate_prompt_node(state: ImageGenerationState) -> Dict[str, Any]:
    """LLM节点：根据情景生成图片提示词并调用工具"""
    print("🎨 Generating image prompt from scenario...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    current_scenario = state.get("current_scenario", "")
    
    inputs = {
        "current_scenario_length": len(current_scenario),
        "num_images_requested": settings.comfyui.num_images,
        "model_temperature": 0.7,
        "current_scenario": current_scenario if current_scenario else "[Empty]"
    }
    
    try:
        # 导入结构化工具辅助函数
        from src.workflow.tools.structured_tool_helper import generate_tool_prompts, parse_tool_calls
        
        # 初始化模型
        agent_config = settings.agent
        extra_body = {"provider": {"only": [agent_config.provider]}} if agent_config.provider else {}
        model = ChatOpenAI(
            model=agent_config.model,
            api_key=agent_config.api_key,
            base_url=agent_config.base_url,
            temperature=0.7,
            extra_body=extra_body
        )
        
        # 生成工具提示词
        tools_description_system, tools_description_user = generate_tool_prompts([generate_one_img])
        
        # 使用新的提示词模板
        system_prompt = IMAGE_SYSTEM_PROMPT.format(tools_description_system=tools_description_system)
        user_input = IMAGE_USER_PROMPT_TEMPLATE.format(
            current_scenario=current_scenario,
            num_images=settings.comfyui.num_images,
            tools_description_user=tools_description_user
        )
        
        print(f"  Scenario length: {len(current_scenario)}", flush=True)
        print(f"  Generating {settings.comfyui.num_images} images", flush=True)
        
        # 调用LLM
        response = await model.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ])
        
        # 解析结构化输出
        response_text = response.content if hasattr(response, 'content') else str(response)
        tool_calls = parse_tool_calls(response_text)
        
        # 提取生成的提示词（从工具调用参数中）
        image_prompt = ""
        tool_call_details = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool_name", "")
            args = tool_call.get("arguments", {})
            if tool_name == "generate_one_img":
                prompt = args.get('positive_prompt', '')
                if not image_prompt:  # 只取第一个作为主要提示词
                    image_prompt = prompt
                
                tool_call_details.append({
                    "tool_name": tool_name,
                    "positive_prompt": prompt,
                    "positive_prompt_length": len(prompt)
                })
        
        # 保存日志
        from utils.simple_logger import save_log
        from datetime import datetime
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "node_type": "llm_image_generation",
            "model_config": {
                "model": agent_config.model,
                "base_url": agent_config.base_url,
                "temperature": 0.7,
                "provider": agent_config.provider if agent_config.provider else None
            },
            "model_input": {
                "system": system_prompt,
                "user": user_input
            },
            "model_output": response_text
        }
        
        log_file = f"./logs/workflow/{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}_image.json"
        save_log(log_file, log_data)
        
        print(f"  ✓ Generated prompt: {image_prompt[:100]}..." if image_prompt else "  ❌ No prompt generated", flush=True)
        print(f"  ✓ Tool calls: {len(tool_calls)}", flush=True)
        
        return {
            "image_prompt": image_prompt,
            "tool_calls": tool_calls
        }
        
    except Exception as e:
        duration = time.time() - start_time
        import traceback
        error_details = traceback.format_exc()
        
        # 错误不记录日志，只输出到控制台
        
        print(f"❌ LLM prompt generation failed: {str(e)}", flush=True)
        return {
            "image_prompt": "",
            "tool_calls": []
        }


async def tool_execution_node(state: ImageGenerationState) -> Dict[str, Any]:
    """工具执行节点：并行执行图片生成工具"""
    print("🛠️ Executing image generation tools...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    tool_calls = state.get("tool_calls", [])
    
    inputs = {
        "tool_calls_count": len(tool_calls),
        "tool_calls_details": [
            {
                "tool_name": tc.get("name", ""),
                "args_keys": list(tc.get("args", {}).keys()),
                "positive_prompt_length": len(tc.get("args", {}).get("positive_prompt", ""))
            } for tc in tool_calls
        ]
    }
    
    try:
        if not tool_calls:
            duration = time.time() - start_time
            
            outputs = {
                "generated_paths_count": 0,
                "execution_results": [],
                "error_message": "No tool calls to execute"
            }
            
            # tool_execution_node不调用LLM，无需记录日志
            
            print("  ❌ No tool calls to execute", flush=True)
            return {"generated_image_paths": []}
        
        print(f"  Executing {len(tool_calls)} tool calls", flush=True)
        
        # 并行执行所有工具调用
        generated_paths = []
        execution_details = []
        
        from langchain_core.runnables import RunnableConfig
        config = RunnableConfig()
        
        # 使用并发执行多个工具调用
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            
            for i, tool_call in enumerate(tool_calls):
                tool_name = tool_call.get("tool_name", "")
                args = tool_call.get("arguments", {})
                
                if tool_name == "generate_one_img":
                    positive_prompt = args.get("positive_prompt", "")
                    print(f"  [{i+1}] Generating image with prompt: {positive_prompt[:50]}...", flush=True)
                    
                    future = executor.submit(generate_one_img.invoke, {"positive_prompt": positive_prompt}, config)
                    futures.append((future, i, tool_call))
                else:
                    print(f"  [{i+1}] ❌ Unknown tool: {tool_name}", flush=True)
                    execution_details.append({
                        "index": i,
                        "tool_name": tool_name,
                        "status": "error",
                        "error": f"Unknown tool: {tool_name}",
                        "args": args
                    })
            
            # 等待所有任务完成
            for future, i, tool_call in futures:
                tool_name = tool_call.get("tool_name", "")
                args = tool_call.get("arguments", {})
                
                try:
                    result = await asyncio.get_event_loop().run_in_executor(None, future.result)
                    generated_paths.append(result)
                    print(f"  [{i+1}] ✓ Image generated: {result}", flush=True)
                    
                    execution_details.append({
                        "index": i,
                        "tool_name": tool_name,
                        "status": "success",
                        "result": result,
                        "args": args,
                        "positive_prompt": args.get("positive_prompt", "")[:100] + "..." if len(args.get("positive_prompt", "")) > 100 else args.get("positive_prompt", "")
                    })
                    
                except Exception as e:
                    error_msg = f"错误：{str(e)}"
                    generated_paths.append(error_msg)
                    print(f"  [{i+1}] ❌ Generation failed: {str(e)}", flush=True)
                    
                    execution_details.append({
                        "index": i,
                        "tool_name": tool_name,
                        "status": "error",
                        "error": str(e),
                        "args": args,
                        "positive_prompt": args.get("positive_prompt", "")[:100] + "..." if len(args.get("positive_prompt", "")) > 100 else args.get("positive_prompt", "")
                    })
        
        duration = time.time() - start_time
        
        outputs = {
            "generated_paths_count": len(generated_paths),
            "generated_paths": generated_paths,
            "execution_details": execution_details,
            "successful_generations": len([d for d in execution_details if d.get("status") == "success"]),
            "failed_generations": len([d for d in execution_details if d.get("status") == "error"])
        }
        
        # tool_execution_node不调用LLM，无需记录日志
        
        print(f"  ✓ Total generated: {len(generated_paths)} images", flush=True)
        return {"generated_image_paths": generated_paths}
            
    except Exception as e:
        duration = time.time() - start_time
        import traceback
        error_details = traceback.format_exc()
        
        outputs = {
            "generated_paths_count": 0,
            "execution_results": [],
            "error_message": str(e)
        }
        
        # 错误不记录日志，只输出到控制台
        
        print(f"❌ Tool execution failed: {str(e)}", flush=True)
        return {"generated_image_paths": [f"错误：{str(e)}"]}


def create_image_generation_workflow():
    """创建图片生成工作流"""
    builder = StateGraph(ImageGenerationState)
    
    # 添加节点
    builder.add_node("init_scenario", init_scenario_node)
    builder.add_node("llm_generate_prompt", llm_generate_prompt_node)
    builder.add_node("tool_execution", tool_execution_node)
    
    # 添加边：线性流程
    builder.add_edge(START, "init_scenario")
    builder.add_edge("init_scenario", "llm_generate_prompt")
    builder.add_edge("llm_generate_prompt", "tool_execution")
    builder.add_edge("tool_execution", END)
    
    return builder.compile()


async def test_image_workflow():
    """测试图片生成工作流"""
    print("🧪 Image generation workflow test starting...", flush=True)
    
    workflow = create_image_generation_workflow()
    
    test_input = {
        "current_scenario": ""  # 空场景，让init节点从表格加载
    }
    
    try:
        result = await workflow.ainvoke(test_input)
        print(f"✅ Image workflow test completed successfully", flush=True)
        print(f"Generated paths: {result.get('generated_image_paths', [])}", flush=True)
        
    except Exception as e:
        print(f"❌ Image workflow test failed: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_image_workflow())


