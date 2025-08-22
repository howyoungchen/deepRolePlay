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
            bool: True表示检查通过或用户选择继续，False表示需要退出
        """
        print("🔍 正在检查配置...")
        print("🔍 Checking configurations...")
        
        has_error = False
        
        # 检查proxy配置
        print("  - 检查proxy配置... / Checking proxy config...", end="", flush=True)
        proxy_success, proxy_error = await self.check_proxy_config()
        if proxy_success:
            print(" ✅")
        else:
            print(" ❌")
            has_error = True
            # 询问用户是否继续
            if not self._print_error("proxy", proxy_error):
                return False  # 用户选择退出
        
        # 检查agent配置
        print("  - 检查agent配置... / Checking agent config...", end="", flush=True)
        agent_success, agent_error = await self.check_agent_config()
        if agent_success:
            print(" ✅")
        else:
            print(" ❌")
            has_error = True
            # 询问用户是否继续
            if not self._print_error("agent", agent_error):
                return False  # 用户选择退出
        
        if not has_error:
            print("✅ 所有配置检查通过！")
            print("✅ All configuration checks passed!")
        else:
            print("⚠️  配置有错误，但用户选择继续运行")
            print("⚠️  Configuration has errors, but user chose to continue")
        
        return True
    
    def _print_error(self, config_type: str, error_msg: str) -> bool:
        """
        打印错误信息并询问是否继续
        
        Returns:
            bool: True表示用户选择继续运行，False表示退出
        """
        print("\n🚫 ==========================================")
        print(f"   小笨蛋，你的{config_type}配置填错了！请检查配置文件")
        print(f"   Hey, your {config_type} configuration is wrong! Please check the config file")
        if error_msg:
            print(f"   错误详情 / Error details: {error_msg}")
        print("   ==========================================")
        print("   是否仍要继续运行？/ Do you still want to continue?")
        print("   输入 y 继续，其他任意键退出 / Enter 'y' to continue, any other key to exit")
        print("   等待输入 (30秒超时)... / Waiting for input (30s timeout)...")
        
        # 设置超时等待用户输入
        import select
        import termios
        import tty
        
        # 保存终端原始设置
        old_settings = None
        user_choice = False
        
        try:
            # 对于Windows系统，使用不同的方法
            if sys.platform == 'win32':
                import msvcrt
                import threading
                
                result = None
                
                def get_input():
                    nonlocal result
                    result = input().strip().lower()
                
                thread = threading.Thread(target=get_input)
                thread.daemon = True
                thread.start()
                thread.join(timeout=30)
                
                if thread.is_alive():
                    print("\n   超时，自动退出... / Timeout, auto exit...")
                    user_choice = False
                else:
                    user_choice = (result == 'y')
            else:
                # Unix/Linux系统使用select
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError()
                
                # 设置超时信号
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                try:
                    user_input = input().strip().lower()
                    signal.alarm(0)  # 取消超时
                    user_choice = (user_input == 'y')
                except TimeoutError:
                    print("\n   超时，自动退出... / Timeout, auto exit...")
                    user_choice = False
                except Exception:
                    user_choice = False
                    
        except Exception as e:
            # 如果出现任何错误，默认为不继续
            print(f"\n   输入处理错误，自动退出... / Input error, auto exit: {e}")
            user_choice = False
        
        if user_choice:
            print("   ⚠️  警告：继续运行可能会导致功能异常！")
            print("   ⚠️  Warning: Continuing may cause functional issues!")
        else:
            print("\n   程序退出 / Program exit")
            
        return user_choice


# 创建全局检查器实例
config_checker = ConfigChecker()