"""
图片优化工具：解决SillyTavern前端卡死问题
通过压缩和格式化图片base64数据，优化SSE传输
"""
import base64
import io
import textwrap
from pathlib import Path
from typing import Optional
from PIL import Image


class ImageOptimizer:
    """图片优化器：压缩图片并格式化base64输出"""
    
    def __init__(self, max_size: Optional[int] = None, quality: int = 70, max_base64_size: int = 350 * 1024):
        """
        初始化图片优化器
        
        Args:
            max_size: 最大边长（像素），如果为None则从配置文件读取
            quality: WebP质量（1-100）
            max_base64_size: base64最大大小（字节），超过则进一步压缩
        """
        if max_size is None:
            # 从配置文件读取最大显示尺寸
            from config.manager import settings
            max_size = settings.comfyui.max_display_size
        
        self.max_size = max_size
        self.quality = quality
        self.max_base64_size = max_base64_size
    
    def optimize_image(self, image_path: str) -> Optional[str]:
        """
        优化图片并返回格式化的base64字符串
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            格式化的base64字符串，失败返回None
        """
        try:
            if not Path(image_path).exists():
                print(f"⚠️ Image file not found: {image_path}")
                return None
            
            # 打开图片
            with Image.open(image_path) as img:
                # 转换为RGB（确保兼容性）
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 缩放图片
                img = self._resize_image(img, self.max_size)
                
                # 压缩为WebP并获取base64
                base64_str = self._compress_to_base64(img, self.quality)
                
                # 检查大小，如果超限则进一步压缩
                if len(base64_str) > self.max_base64_size:
                    print(f"🔄 Base64 size {len(base64_str)} exceeds limit {self.max_base64_size}, reducing quality...")
                    base64_str = self._auto_reduce_quality(img, target_size=self.max_base64_size)
                
                # 格式化base64字符串（每76字符换行）
                formatted_base64 = self._format_base64(base64_str)
                
                print(f"✅ Image optimized: {Path(image_path).name}")
                print(f"   Original size: {Path(image_path).stat().st_size / 1024:.1f}KB")
                print(f"   Base64 size: {len(base64_str)} bytes ({len(base64_str) / 1024:.1f}KB)")
                print(f"   Image size: {img.size}")
                
                return formatted_base64
                
        except Exception as e:
            print(f"❌ Image optimization failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _resize_image(self, img: Image.Image, max_size: int) -> Image.Image:
        """调整图片尺寸，保持宽高比"""
        # 计算缩放比例
        width, height = img.size
        if max(width, height) <= max_size:
            return img
        
        # 使用ImageOps.fit保持宽高比并裁剪至目标尺寸
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _compress_to_base64(self, img: Image.Image, quality: int) -> str:
        """将图片压缩为WebP格式并转换为base64"""
        buffer = io.BytesIO()
        img.save(buffer, format='WebP', quality=quality, optimize=True)
        buffer.seek(0)
        
        img_bytes = buffer.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _auto_reduce_quality(self, img: Image.Image, target_size: int, min_quality: int = 30) -> str:
        """自动降低质量直到满足大小要求"""
        current_quality = self.quality
        
        while current_quality >= min_quality:
            base64_str = self._compress_to_base64(img, current_quality)
            if len(base64_str) <= target_size:
                print(f"✅ Quality reduced to {current_quality}, size: {len(base64_str)} bytes")
                return base64_str
            
            current_quality -= 10
        
        # 如果质量已降到最低仍然过大，尝试进一步缩小尺寸
        print(f"⚠️ Min quality {min_quality} still too large, reducing size...")
        smaller_img = self._resize_image(img, int(self.max_size * 0.8))
        return self._compress_to_base64(smaller_img, min_quality)
    
    def _format_base64(self, base64_str: str) -> str:
        """将base64字符串格式化为每76字符换行"""
        return textwrap.fill(base64_str, width=76)
    
    def create_optimized_img_tag(self, image_path: str, alt_text: str = "Generated Image", 
                                collapsible: bool = False) -> str:
        """
        创建优化的Markdown格式图片
        
        Args:
            image_path: 图片文件路径
            alt_text: alt属性文本
            collapsible: 是否使用可折叠的details标签
            
        Returns:
            Markdown图片语法字符串
        """
        formatted_base64 = self.optimize_image(image_path)
        if not formatted_base64:
            return f'[图片加载失败: {Path(image_path).name}]'
        
        # 将多行base64重新组合为单行（Markdown data URI需要单行）
        clean_base64 = formatted_base64.replace('\n', '').replace(' ', '')
        
        # 使用Markdown格式
        markdown_img = f'![{alt_text}](data:image/webp;base64,{clean_base64})'
        
        if collapsible:
            # Markdown不直接支持details，使用HTML包装
            return f'<details><summary>📷 查看生成图片</summary>\n\n{markdown_img}\n\n</details>'
        else:
            return markdown_img


# 全局实例
image_optimizer = ImageOptimizer()


def optimize_and_format_image(image_path: str, alt_text: str = "Generated Image", 
                             collapsible: bool = False) -> str:
    """
    快捷函数：优化图片并生成Markdown格式图片
    
    Args:
        image_path: 图片文件路径
        alt_text: alt属性文本
        collapsible: 是否可折叠显示
        
    Returns:
        优化的Markdown图片语法
    """
    return image_optimizer.create_optimized_img_tag(
        image_path, alt_text, collapsible
    )


if __name__ == "__main__":
    # 测试代码
    import glob
    
    # 查找测试图片
    test_images = glob.glob("logs/imgs/*.png")
    if test_images:
        test_image = test_images[0]
        print(f"Testing with: {test_image}")
        
        # 测试优化
        result = optimize_and_format_image(test_image, collapsible=True)
        print(f"Generated HTML length: {len(result)}")
        print(f"HTML preview: {result[:200]}...")
    else:
        print("No test images found in logs/imgs/")