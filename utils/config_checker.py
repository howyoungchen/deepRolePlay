"""
配置检查器
在程序启动前检查proxy和agent配置是否正确
"""
import asyncio
import httpx
import sys
import time
from typing import Dict, Optional, Tuple
from config.manager import settings


class ConfigChecker:
    """配置检查器类，用于验证proxy和agent配置"""
    
    def __init__(self):
        self.timeout = 30
    
    async def check_proxy_config(self) -> Tuple[bool, Optional[str]]:
        """
        检查proxy配置是否正确
        
        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        try:
            models_url = settings.proxy.get_models_url()
            api_key = settings.proxy.api_key
            
            if not models_url:
                return False, "Proxy target URL not configured"
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "DeepRolePlay-ConfigChecker/1.0"
            }
            
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(models_url, headers=headers)
                
                if response.status_code == 200:
                    # 尝试解析JSON响应
                    try:
                        json_data = response.json()
                        # 检查是否包含models字段或data字段（不同服务商格式可能不同）
                        if "data" in json_data or "models" in json_data:
                            return True, None
                        else:
                            return False, f"Invalid response format: {json_data}"
                    except Exception as e:
                        return False, f"Failed to parse JSON response: {str(e)}"
                elif response.status_code == 401:
                    return False, "Authentication failed - invalid API key"
                elif response.status_code == 403:
                    return False, "Access forbidden - check API key permissions"
                else:
                    return False, f"HTTP {response.status_code}: {response.text}"
                    
        except httpx.ConnectError:
            return False, f"Connection failed - cannot reach {models_url}"
        except httpx.TimeoutException:
            return False, f"Request timeout after {self.timeout} seconds"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    async def check_agent_config(self) -> Tuple[bool, Optional[str]]:
        """
        检查agent配置是否正确
        
        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        try:
            base_url = settings.agent.base_url.rstrip('/')
            models_url = f"{base_url}/models"
            api_key = settings.agent.api_key
            
            if not base_url or base_url == "https://api.deepseek.com/v1":
                # 检查是否使用了默认配置
                if api_key == "sk-your-api-key-here":
                    return False, "Agent API key not configured (using default placeholder)"
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "DeepRolePlay-ConfigChecker/1.0"
            }
            
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(models_url, headers=headers)
                
                if response.status_code == 200:
                    # 尝试解析JSON响应
                    try:
                        json_data = response.json()
                        # 检查是否包含models字段或data字段（不同服务商格式可能不同）
                        if "data" in json_data or "models" in json_data:
                            return True, None
                        else:
                            return False, f"Invalid response format: {json_data}"
                    except Exception as e:
                        return False, f"Failed to parse JSON response: {str(e)}"
                elif response.status_code == 401:
                    return False, "Authentication failed - invalid API key"
                elif response.status_code == 403:
                    return False, "Access forbidden - check API key permissions"
                else:
                    return False, f"HTTP {response.status_code}: {response.text}"
                    
        except httpx.ConnectError:
            return False, f"Connection failed - cannot reach {models_url}"
        except httpx.TimeoutException:
            return False, f"Request timeout after {self.timeout} seconds"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    async def run_all_checks(self) -> bool:
        """
        运行所有配置检查
        
        Returns:
            bool: 所有检查是否都通过
        """
        print("🔍 正在检查配置...")
        print("🔍 Checking configurations...")
        
        # 检查proxy配置
        print("  - 检查proxy配置... / Checking proxy config...", end="", flush=True)
        proxy_success, proxy_error = await self.check_proxy_config()
        if proxy_success:
            print(" ✅")
        else:
            print(" ❌")
            self._print_error("proxy", proxy_error)
            return False
        
        # 检查agent配置
        print("  - 检查agent配置... / Checking agent config...", end="", flush=True)
        agent_success, agent_error = await self.check_agent_config()
        if agent_success:
            print(" ✅")
        else:
            print(" ❌")
            self._print_error("agent", agent_error)
            return False
        
        print("✅ 所有配置检查通过！")
        print("✅ All configuration checks passed!")
        return True
    
    def _print_error(self, config_type: str, error_msg: str):
        """打印错误信息"""
        print("\n🚫 ==========================================")
        print(f"   小笨蛋，你的{config_type}配置填错了！请检查配置文件")
        print(f"   Hey, your {config_type} configuration is wrong! Please check the config file")
        if error_msg:
            print(f"   错误详情 / Error details: {error_msg}")
        print("   ==========================================")
        print("   等待30秒后退出... / Exiting in 30 seconds...")
        
        # 等待30秒
        for i in range(30, 0, -1):
            print(f"   {i:2d} 秒后退出... / {i:2d} seconds until exit...", end="\r", flush=True)
            time.sleep(1)
        print("\n   程序退出 / Program exit")


# 创建全局检查器实例
config_checker = ConfigChecker()