import requests
import json
import time
import os
import urllib.request
import urllib.parse
from typing import Optional, Dict, List, Tuple
import copy


class ComfyUIClient:
    """可复用的ComfyUI API客户端类"""
    
    def __init__(
        self,
        ip: str = "127.0.0.1",
        port: int = 8188,
        api_key: Optional[str] = None,
        workflow_path: str = None,
        positive_prompt_node_id: str = "6",
        latent_image_node_id: str = "5"
    ):
        """
        初始化ComfyUI客户端
        
        Args:
            ip: ComfyUI服务器IP地址
            port: ComfyUI服务器端口
            api_key: API密钥（如果需要认证）
            workflow_path: workflow JSON文件路径
            positive_prompt_node_id: 正向提示词编码节点的ID
            latent_image_node_id: 潜在图像生成节点的ID
        """
        self.base_url = f"http://{ip}:{port}"
        self.api_key = api_key
        self.workflow_path = workflow_path
        self.positive_prompt_node_id = positive_prompt_node_id
        self.latent_image_node_id = latent_image_node_id
        self.workflow_template = None
        
        # 如果提供了workflow路径，加载它
        if workflow_path:
            self.load_workflow(workflow_path)
    
    def load_workflow(self, workflow_path: str) -> bool:
        """加载workflow模板"""
        if not os.path.exists(workflow_path):
            print(f"错误：Workflow文件不存在：{workflow_path}")
            return False
        
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                self.workflow_template = json.load(f)
            print(f"成功加载workflow：{workflow_path}")
            return True
        except Exception as e:
            print(f"加载workflow失败：{e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def test_connection(self) -> bool:
        """测试与ComfyUI服务器的连接"""
        try:
            headers = self._get_headers()
            req = requests.get(f"{self.base_url}/system_stats", headers=headers, timeout=5)
            req.raise_for_status()
            return True
        except Exception as e:
            print(f"连接测试失败：{e}")
            return False
    
    def queue_prompt(self, workflow: Dict) -> Optional[str]:
        """提交workflow到队列"""
        try:
            headers = self._get_headers()
            req = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                headers=headers
            )
            req.raise_for_status()
            data = req.json()
            return data.get("prompt_id")
        except Exception as e:
            print(f"提交workflow失败：{e}")
            return None
    
    def get_history(self, prompt_id: str) -> Optional[Dict]:
        """获取执行历史"""
        try:
            headers = self._get_headers()
            req = requests.get(f"{self.base_url}/history/{prompt_id}", headers=headers)
            req.raise_for_status()
            return req.json()
        except Exception as e:
            print(f"获取历史失败：{e}")
            return None
    
    def get_image_data(self, filename: str, subfolder: str, folder_type: str) -> Optional[bytes]:
        """获取图片数据"""
        try:
            url_params = urllib.parse.urlencode({
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type
            })
            url = f"{self.base_url}/view?{url_params}"
            request = urllib.request.Request(url)
            
            if self.api_key:
                request.add_header("Authorization", f"Bearer {self.api_key}")
            
            with urllib.request.urlopen(request) as response:
                return response.read()
        except Exception as e:
            print(f"获取图片数据失败：{e}")
            return None
    
    def generate_image(
        self,
        positive_prompt: str,
        width: int = 960,
        height: int = 1536,
        output_dir: str = ".",
        timeout: int = 300
    ) -> List[str]:
        """
        生成图片的便捷方法
        
        Args:
            positive_prompt: 正向提示词
            width: 图片宽度
            height: 图片高度
            output_dir: 输出目录
            timeout: 超时时间（秒）
            
        Returns:
            生成的图片文件路径列表
        """
        if not self.workflow_template:
            print("错误：未加载workflow模板")
            return []
        
        # 创建workflow副本并修改参数
        workflow = copy.deepcopy(self.workflow_template)
        
        # 更新正向提示词
        if self.positive_prompt_node_id in workflow:
            workflow[self.positive_prompt_node_id]["inputs"]["text"] = positive_prompt
        
        # 更新图片尺寸
        if self.latent_image_node_id in workflow:
            workflow[self.latent_image_node_id]["inputs"]["width"] = width
            workflow[self.latent_image_node_id]["inputs"]["height"] = height
        
        # 提交workflow
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return []
        
        print(f"已提交任务，ID：{prompt_id}")
        
        # 等待结果
        start_time = time.time()
        outputs = None
        
        while time.time() - start_time < timeout:
            history = self.get_history(prompt_id)
            if history and prompt_id in history:
                if 'outputs' in history[prompt_id]:
                    outputs = history[prompt_id]['outputs']
                    print(f"\n任务完成，耗时：{time.time() - start_time:.2f}秒")
                    break
            
            elapsed = time.time() - start_time
            print(f"等待中... ({elapsed:.0f}秒)", end='\r')
            time.sleep(2)
        
        if not outputs:
            print(f"\n任务超时（{timeout}秒）")
            return []
        
        # 下载并保存图片
        saved_files = []
        for node_id in outputs:
            node_output = outputs[node_id]
            if 'images' in node_output:
                print(f"在节点 {node_id} 找到 {len(node_output['images'])} 张图片")
                for image in node_output['images']:
                    image_data = self.get_image_data(
                        image['filename'],
                        image['subfolder'],
                        image['type']
                    )
                    if image_data:
                        output_path = os.path.join(output_dir, image['filename'])
                        try:
                            with open(output_path, 'wb') as f:
                                f.write(image_data)
                            print(f"已保存：{os.path.abspath(output_path)}")
                            saved_files.append(output_path)
                        except IOError as e:
                            print(f"保存图片失败：{e}")
        
        return saved_files
    
    def generate_images_batch(
        self,
        prompts_with_params: List[Tuple[str, int, int]],
        output_dir: str = ".",
        timeout_per_image: int = 300
    ) -> Dict[str, List[str]]:
        """
        批量生成图片
        
        Args:
            prompts_with_params: 包含(提示词, 宽度, 高度)的列表
            output_dir: 输出目录
            timeout_per_image: 每张图片的超时时间
            
        Returns:
            字典，键为提示词，值为生成的图片路径列表
        """
        results = {}
        
        for i, (prompt, width, height) in enumerate(prompts_with_params):
            print(f"\n生成第 {i+1}/{len(prompts_with_params)} 张图片...")
            print(f"提示词：{prompt[:50]}...")
            
            saved_files = self.generate_image(
                prompt, width, height, output_dir, timeout_per_image
            )
            results[prompt] = saved_files
        
        return results