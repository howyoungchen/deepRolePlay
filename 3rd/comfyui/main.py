#!/usr/bin/env python3
"""
使用ComfyUIClient的示例业务代码
"""
from comfyui_client import ComfyUIClient


def main():
    """主函数"""
    print("=== ComfyUI 图像生成示例 ===\n")
    
    # 创建客户端实例
    client = ComfyUIClient(
        ip="111.198.68.218",
        port=8188,
        api_key="8b97a21432e6ac9d18d03fc760e905f37c6bd9f322ca844e22db72e1a20f84a1",
        workflow_path="anythingXL_v1.json",
        positive_prompt_node_id="6",  # 正向提示词节点ID
        latent_image_node_id="5"      # 潜在图像节点ID
    )
    
    # 测试连接
    print("测试连接...")
    if not client.test_connection():
        print("无法连接到ComfyUI服务器")
        return
    print("连接成功！\n")
    
    # 单张图片生成示例
    print("--- 单张图片生成 ---")
    prompt = "recent, 1girl, original, masterpiece, best quality, lying on bed, looking at viewer, silk nightgown, messy hair, soft lighting"
    
    saved_files = client.generate_image(
        positive_prompt=prompt,
        width=960,
        height=1536,
        output_dir="."
    )
    
    if saved_files:
        print(f"\n成功生成 {len(saved_files)} 张图片")
        for file in saved_files:
            print(f"  - {file}")
    else:
        print("图片生成失败")
    
    print("\n--- 批量生成示例 ---")
    # 批量生成示例（取消注释以使用）
    
    print("\n=== 完成 ===")



if __name__ == "__main__":
    main()