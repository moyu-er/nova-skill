#!/usr/bin/env python3
"""
Nova Skill - Terminal Interactive Mode

Features:
- Supports streaming ReAct process (thinking, tool calls, results)
- Supports multi-turn conversations
- Colored output
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configure logging - only output to file, not terminal
Path("logs").mkdir(exist_ok=True)
logger.remove()  # Remove default terminal output
logger.add("logs/cli.log", rotation="10 MB", retention="7 days", level="INFO")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nova.skill import SkillRegistry
from nova.agent import Agent, AgentConfig


# Color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_banner():
    """Print welcome message"""
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════╗
║           Nova Skill CLI                 ║
║   AI Assistant with ReAct Streaming      ║
╚══════════════════════════════════════════╝
{Colors.ENDC}
Type /help for commands, /quit to exit
""")


def print_help():
    """Print help information"""
    print(f"""
{Colors.BOLD}Available Commands:{Colors.ENDC}
  /help      - Show this help
  /quit      - Exit the program
  /clear     - Clear screen
  /skills    - Show loaded skills
  /tools     - Show registered tools
  /model     - Show current model info
  /react     - Toggle ReAct mode (on/off)

{Colors.BOLD}Tips:{Colors.ENDC}
  - Type your question directly to chat with AI
  - ReAct mode shows AI's thinking process and tool calls
""")


def get_model_config():
    """Get model configuration"""
    model = os.getenv("MODEL", "gpt-4o-mini")
    
    if "claude" in model.lower():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        provider = "anthropic"
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        provider = "openai"
    
    return model, api_key, base_url, provider


async def run_cli():
    """Run CLI interaction"""
    print_banner()
    
    # Get configuration
    try:
        model, api_key, base_url, provider = get_model_config()
        print(f"{Colors.GREEN}✓ Model: {model} ({provider}){Colors.ENDC}\n")
    except RuntimeError as e:
        print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
        return
    
    # Load skills
    skills_dir = Path(__file__).parent / "skills"
    skill_registry = SkillRegistry(skills_dir)
    
    available_skills = [s.name for s in skill_registry.list_all()]
    if available_skills:
        print(f"{Colors.GREEN}✓ Loaded skills: {', '.join(available_skills)}{Colors.ENDC}\n")
    
    # Create Agent
    config = AgentConfig(
        name="nova",
        model=model,
        skills=available_skills
    )
    
    agent = Agent(
        config=config,
        skill_registry=skill_registry,
        api_key=api_key,
        base_url=base_url
    )
    
    print(f"{Colors.GREEN}✓ Agent ready!{Colors.ENDC}\n")
    
    # State
    react_mode = True  # Default ReAct mode on
    thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Interaction loop
    while True:
        try:
            # Get input
            user_input = input(f"{Colors.BOLD}You>{Colors.ENDC} ").strip()
            
            if not user_input:
                continue
            
            # Process commands
            if user_input.startswith('/'):
                cmd = user_input.lower()
                
                if cmd == '/quit':
                    print(f"\n{Colors.YELLOW}Goodbye!{Colors.ENDC}")
                    break
                
                elif cmd == '/help':
                    print_help()
                
                elif cmd == '/clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print_banner()
                
                elif cmd == '/skills':
                    print(f"\n{Colors.BOLD}Loaded skills:{Colors.ENDC}")
                    for skill in skill_registry.list_all():
                        print(f"  • {skill.name}: {skill.description[:60]}...")
                        if skill.metadata:
                            print(f"    Metadata: {skill.metadata}")
                    print()
                
                elif cmd == '/tools':
                    from nova.tools import get_all_tools
                    print(f"\n{Colors.BOLD}Registered tools:{Colors.ENDC}")
                    tools = get_all_tools(skill_registry)
                    for tool in tools:
                        desc = tool.description[:80] if tool.description else "No description"
                        print(f"  • {tool.name}: {desc}")
                    print()
                
                elif cmd == '/model':
                    print(f"\n{Colors.BOLD}Model Info:{Colors.ENDC}")
                    print(f"  Model: {model}")
                    print(f"  Provider: {provider}")
                    print(f"  Temperature: {config.temperature}")
                    print(f"  ReAct Mode: {'ON' if react_mode else 'OFF'}")
                    print(f"  Thread ID: {thread_id}\n")
                
                elif cmd == '/react':
                    react_mode = not react_mode
                    status = "ON" if react_mode else "OFF"
                    print(f"{Colors.YELLOW}ReAct mode {status}{Colors.ENDC}\n")
                
                else:
                    print(f"{Colors.RED}Unknown command: {user_input}{Colors.ENDC}")
                    print("Type /help for available commands\n")
                
                continue
            
            # Process conversation
            print(f"\n{Colors.BOLD}{Colors.BLUE}AI>{Colors.ENDC}")
            
            if react_mode:
                # ReAct mode - show content and tool calls
                async for event in agent.astream_react(user_input, thread_id):
                    event_type = event.get("type")
                    
                    if event_type == "content":
                        # AI output content (streaming)
                        print(event.get("content", ""), end="", flush=True)
                    
                    elif event_type == "tool_call":
                        name = event.get("name", "")
                        args = event.get("args", {})
                        print(f"\n{Colors.YELLOW}[Tool: {name}] {args}{Colors.ENDC}")
                    
                    elif event_type == "tool_result":
                        content = event.get("content", "")
                        preview = content[:200] + "\n..." if len(content) > 150 else content
                        print(f"{Colors.GREEN}[Result: {preview}]{Colors.ENDC}\n")
                    
                    elif event_type == "error":
                        print(f"{Colors.RED}[Error: {event.get('content', '')}]{Colors.ENDC}")
            
            else:
                # Normal mode - only show final response
                async for chunk in agent.astream(user_input, thread_id):
                    print(chunk, end="", flush=True)
            
            print(f"\n{Colors.ENDC}\n")
        
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Goodbye!{Colors.ENDC}")
            break
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.ENDC}\n")


def main():
    """Entry function"""
    parser = argparse.ArgumentParser(description="Nova Skill CLI")
    parser.add_argument("--model", help="Override default model")
    parser.add_argument("--no-react", action="store_true", help="Disable ReAct mode")
    args = parser.parse_args()
    
    # Override environment variable if model specified
    if args.model:
        os.environ["MODEL"] = args.model
    
    # Run CLI
    try:
        asyncio.run(run_cli())
    except Exception as e:
        print(f"{Colors.RED}Startup failed: {e}{Colors.ENDC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
