#!/usr/bin/env python3
"""
使用原生OpenAI SDK获取DeepSeek Reasoner推理内容
这是目前最可靠的方法
"""

from openai import OpenAI

# 填入你的API Key
API_KEY = "sk-5b155b212651493b942e7dca7dfb4751"
BASE_URL = "https://api.deepseek.com"

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

def test_streaming():
    messages = [{"role": "user", "content": "模拟猫咪，100字以内"}]
    
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=messages,
        stream=True
    )
    
    reasoning_content = ""
    content = ""
    thinking_output = False
    
    for chunk in response:
        # 检查推理内容
        if chunk.choices[0].delta.reasoning_content:
            if not thinking_output:
                print("<think>\n", end="", flush=True)
                thinking_output = True
            reasoning_content += chunk.choices[0].delta.reasoning_content
            print(chunk.choices[0].delta.reasoning_content, end="", flush=True)
        
        # 检查最终内容
        if chunk.choices[0].delta.content:
            if thinking_output:
                print("</think>")
                thinking_output = False
            content += chunk.choices[0].delta.content
            print(chunk.choices[0].delta.content, end="", flush=True)
    
    if thinking_output:
        print("\n</think>")
    
    print("\n")  # 最后换行


if __name__ == "__main__":
    test_streaming()