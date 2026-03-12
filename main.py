#!/usr/bin/env python3
"""
Nova Skill - 启动脚本

跨平台启动（Windows / Linux / macOS）
"""
import os
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from langchain_openai import ChatOpenAI

from nova.skill import SkillRegistry
from nova.agent import Agent, AgentConfig


def create_sandbox_tool():
    """创建沙箱执行工具（跨平台）"""
    import platform
    import subprocess
    import tempfile
    
    system = platform.system()
    
    def execute_python(code: str) -> str:
        """执行 Python 代码"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 执行代码
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[Error] {result.stderr}"
            
            return output
        except subprocess.TimeoutExpired:
            return "Execution timeout (30s)"
        except Exception as e:
            return f"Execution error: {e}"
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
    
    return execute_python


def main():
    """主函数"""
    print("=" * 60)
    print("Nova Skill - 轻量级 AI 助手")
    print("=" * 60)
    
    # 检查 API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ Error: OPENAI_API_KEY not set")
        print("Please set your OpenAI API key in .env file")
        return 1
    
    # 初始化 LLM
    print("\n[1/3] Initializing LLM...")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        api_key=api_key
    )
    
    # 加载 Skills（从 Markdown 文件）
    print("\n[2/3] Loading skills from Markdown...")
    registry = SkillRegistry()
    skills_dir = Path(__file__).parent / "skills"
    registry.load_from_directory(skills_dir)
    
    # 绑定工具到 skill
    coder_skill = registry.get("coder")
    if coder_skill:
        from nova.skill import Tool
        sandbox_tool = Tool(
            name="execute_python",
            description="在沙箱中执行 Python 代码",
            func=create_sandbox_tool()
        )
        coder_skill.tools.append(sandbox_tool)
        print(f"   Bound sandbox tool to coder skill")
    
    # 创建 Agent
    print("\n[3/3] Creating agent with skills...")
    config = AgentConfig(
        name="nova",
        model="gpt-4o-mini",
        skills=None  # 加载所有 skills
    )
    
    agent = Agent(config, llm, registry)
    
    # 打印 system prompt 预览
    print(f"\n{'='*60}")
    print("System Prompt Preview:")
    print(f"{'='*60}")
    preview = agent.get_system_prompt()[:500]
    print(preview + "..." if len(agent.get_system_prompt()) > 500 else preview)
    print(f"\n{'='*60}")
    
    print("\nReady! Type 'exit' to quit")
    print("=" * 60 + "\n")
    
    # 交互式对话
    import asyncio
    
    async def chat_loop():
        thread_id = "main"
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() == 'exit':
                    break
                
                print("\nNova: ", end="", flush=True)
                response = await agent.arun(user_input, thread_id)
                print(response)
                print()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
    
    asyncio.run(chat_loop())
    
    print("\nGoodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
