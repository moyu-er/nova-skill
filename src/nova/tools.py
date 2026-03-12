"""
工具模块 - 使用 LangChain @tool 装饰器
"""
import re
import httpx
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool, InjectedToolArg

from nova.skill import SkillRegistry

logger = logging.getLogger(__name__)


@tool
def search_web(query: Annotated[str, "搜索关键词"]) -> str:
    """搜索网络信息（使用 DuckDuckGo）"""
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            
            html = response.text
            results = []
            
            # 提取搜索结果
            links = re.findall(r'class="result__a" href="([^"]+)"[^>]*>([^<]+)', html)
            for i, (link, title) in enumerate(links[:5], 1):
                results.append(f"{i}. {title.strip()}\n   {link}")
            
            return "\n\n".join(results) if results else "未找到搜索结果"
            
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"搜索失败: {e}"


@tool
def fetch_url(url: Annotated[str, "网页 URL"]) -> str:
    """获取网页内容"""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            html = response.text
            
            # 清理 HTML
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text[:5000]
            
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return f"获取失败: {e}"


@tool
def read_file(path: Annotated[str, "文件路径"]) -> str:
    """读取本地文件内容（跨平台）"""
    try:
        file_path = Path(path).expanduser().resolve()
        
        if not file_path.exists():
            return f"文件不存在: {file_path}"
        
        if not file_path.is_file():
            return f"不是文件: {file_path}"
        
        content = file_path.read_text(encoding='utf-8')
        return content[:10000]
        
    except Exception as e:
        logger.error(f"Read file failed: {e}")
        return f"读取失败: {e}"


@tool  
def write_file(path: Annotated[str, "文件路径"], content: Annotated[str, "文件内容"]) -> str:
    """写入内容到本地文件（跨平台）"""
    try:
        file_path = Path(path).expanduser().resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        logger.info(f"Wrote file: {file_path}")
        return f"成功写入: {file_path} ({len(content)} 字符)"
        
    except Exception as e:
        logger.error(f"Write file failed: {e}")
        return f"写入失败: {e}"


@tool
def list_directory(path: Annotated[str, "目录路径，默认为当前目录"] = ".") -> str:
    """列出目录内容（跨平台）"""
    try:
        dir_path = Path(path).expanduser().resolve()
        
        if not dir_path.exists():
            return f"目录不存在: {dir_path}"
        
        if not dir_path.is_dir():
            return f"不是目录: {dir_path}"
        
        items = []
        for item in dir_path.iterdir():
            item_type = "D" if item.is_dir() else "F"
            items.append(f"[{item_type}] {item.name}")
        
        return "\n".join(items) if items else "空目录"
        
    except Exception as e:
        logger.error(f"List directory failed: {e}")
        return f"列出失败: {e}"


@tool
def get_available_skills(registry: Annotated[SkillRegistry, InjectedToolArg]) -> str:
    """获取所有可用的 skill 列表"""
    skills = registry.list_all()
    if not skills:
        return "没有可用的 skills"
    
    result = []
    for skill in skills:
        result.append(f"- {skill.name}: {skill.description[:50]}...")
    
    return "可用 Skills:\n" + "\n".join(result)


@tool
def read_skill_detail(skill_name: Annotated[str, "Skill 名称"], 
                       registry: Annotated[SkillRegistry, InjectedToolArg]) -> str:
    """读取指定 skill 的完整内容"""
    return registry.read_skill_content(skill_name)


def get_all_tools(registry: SkillRegistry = None):
    """获取所有工具"""
    base_tools = [search_web, fetch_url, read_file, write_file, list_directory]
    
    if registry:
        from functools import partial
        skill_tools = [
            partial(get_available_skills, registry=registry),
            partial(read_skill_detail, registry=registry),
        ]
        return base_tools + skill_tools
    
    return base_tools
