#!/usr/bin/env python3
"""
Nova Skill - Terminal Interactive Mode with Rich UI

Features:
- Rich-based terminal UI with sidebar task display
- Color-coded tool behaviors and system events
- Supports streaming ReAct process (thinking, tool calls, results)
- Supports multi-turn conversations
- Cross-platform: Windows, Linux, macOS
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configure logging - only output to file, not terminal
Path("logs").mkdir(exist_ok=True)
logger.remove()  # Remove default terminal output
logger.add("logs/cli.log", rotation="10 MB", retention="7 days", level="INFO")

# Rich imports
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich import box

from src import ModelType
from src import SkillRegistry
from src import Agent, AgentConfig
from src import TaskManager
from src.display import is_rich_available, TaskSidebar, SimpleRichDisplay


# Global console
console = Console()


# Color constants - simplified
def print_banner():
    """Print welcome message using Rich"""
    banner = Panel.fit(
        "[bold cyan]Nova Skill CLI[/bold cyan]\n"
        "[dim]AI Assistant with ReAct Streaming[/dim]",
        border_style="cyan",
        box=box.DOUBLE
    )
    console.print(banner)
    console.print("[dim]Type /help for commands, /quit to exit[/dim]\n")


def print_startup_info(model: str, provider: str, skills: list):
    """Print startup information with color coding"""
    # Model info panel
    model_text = Text()
    model_text.append("Model: ", style="dim")
    model_text.append(model, style="bold cyan")
    model_text.append(" (", style="dim")
    model_text.append(provider, style="dim cyan")
    model_text.append(")", style="dim")
    
    console.print(Panel(
        model_text,
        title="[bold green]Configuration[/bold green]",
        border_style="green",
        box=box.ROUNDED,
        width=60
    ))
    
    # Skills info
    if skills:
        skills_text = Text()
        skills_text.append("Loaded ", style="dim")
        skills_text.append(str(len(skills)), style="bold yellow")
        skills_text.append(" skills: ", style="dim")
        skills_text.append(", ".join(skills[:5]), style="dim cyan")
        if len(skills) > 5:
            skills_text.append(f" ... and {len(skills) - 5} more", style="dim")
        
        console.print(Panel(
            skills_text,
            title="[bold green]Skills[/bold green]",
            border_style="green",
            box=box.ROUNDED,
            width=60
        ))
    
    # Ready indicator
    console.print(Panel(
        "[bold green]Ready for conversation![/bold green]",
        border_style="bright_green",
        box=box.DOUBLE,
        width=60
    ))
    console.print()


def print_help():
    """Print help information using Rich"""
    table = Table(title="[bold cyan]Available Commands[/bold cyan]", show_header=True, box=box.ROUNDED)
    table.add_column("Command", style="bold cyan", no_wrap=True, width=12)
    table.add_column("Description", style="white")
    
    commands = [
        ("/help", "Show this help"),
        ("/quit", "Exit the program"),
        ("/clear", "Clear screen"),
        ("/skills", "Show loaded skills"),
        ("/tools", "Show registered tools"),
        ("/model", "Show current model info"),
        ("/react", "Toggle ReAct mode (on/off)"),
        ("/plan", "Create task plan for complex requests"),
        ("/tasks", "Show current task plan status"),
    ]
    
    for cmd, desc in commands:
        table.add_row(cmd, desc)
    
    console.print(table)
    console.print("\n[dim cyan]Tips:[/dim cyan]")
    console.print("  [dim]• Type your question directly to chat with AI[/dim]")
    console.print("  [dim]• ReAct mode shows AI's thinking process and tool calls[/dim]")
    console.print("  [dim]• Use /plan for complex multi-step tasks[/dim]\n")


def get_model_config():
    """Get model configuration"""
    model = os.getenv("MODEL", "gpt-4o-mini")
    
    if "claude" in model.lower():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        provider = ModelType.ANTHROPIC.value
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        provider = ModelType.OPENAI.value
    
    return model, api_key, base_url, provider


class NovaCLI:
    """Nova Skill CLI with Rich UI"""
    
    def __init__(self):
        self.agent: Optional[Agent] = None
        self.task_manager: Optional[TaskManager] = None
        self.skill_registry: Optional[SkillRegistry] = None
        self.task_sidebar: Optional[TaskSidebar] = None
        self.rich_display: Optional[SimpleRichDisplay] = None
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        
        # State
        self.react_mode = True
        self.thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.main_content: list = []
        
    def setup(self):
        """Setup CLI components with colored output"""
        # Get configuration
        model, api_key, base_url, provider = get_model_config()
        
        # Load skills
        skills_dir = Path(__file__).parent / "skills"
        self.skill_registry = SkillRegistry(skills_dir)
        available_skills = [s.name for s in self.skill_registry.list_all()]
        
        # Create Agent
        config = AgentConfig(
            name="nova",
            model=model,
            skills=available_skills
        )
        
        self.agent = Agent(
            config=config,
            skill_registry=self.skill_registry,
            api_key=api_key,
            base_url=base_url
        )
        
        # Setup task management
        self.task_manager = TaskManager()
        self.task_sidebar = TaskSidebar()
        self.rich_display = SimpleRichDisplay()
        
        # Set global instances for tools
        from src.tools import set_global_registry, set_global_task_manager
        set_global_registry(self.skill_registry)
        set_global_task_manager(self.task_manager)
        
        # Print startup info with colors
        print_startup_info(model, provider, available_skills)
        
    def create_layout(self) -> Layout:
        """Create terminal layout with sidebar"""
        layout = Layout()
        
        # Split into main and sidebar
        layout.split_row(
            Layout(name="main", ratio=1),
            Layout(name="sidebar", size=38)
        )
        
        # Main area
        main_text = "\n".join(self.main_content[-30:]) if self.main_content else "[dim]Waiting for input...[/dim]"
        layout["main"].update(Panel(
            main_text,
            title="[bold blue]Conversation[/bold blue]",
            border_style="blue",
            box=box.ROUNDED
        ))
        
        # Sidebar with task plan
        plan = self.agent.get_current_task_plan() if self.agent else None
        layout["sidebar"].update(self.task_sidebar.render(plan))
        
        return layout
        
    def add_to_main(self, message: str, style: str = ""):
        """Add message to main content area"""
        if style:
            self.main_content.append(f"[{style}]{message}[/{style}]")
        else:
            self.main_content.append(message)
        
        # Keep last 100 lines
        if len(self.main_content) > 100:
            self.main_content = self.main_content[-100:]
        
        # Update live display if active
        if self.live:
            self.live.update(self.create_layout())
            
    def update_sidebar(self):
        """Update sidebar with current task plan"""
        if self.live and self.agent:
            plan = self.agent.get_current_task_plan()
            self.live.update(self.create_layout())
            
    def print_streaming_content(self, content: str):
        """Print streaming content (for ReAct mode)"""
        console.print(content, end="")
        
    async def handle_command(self, cmd: str) -> bool:
        """Handle CLI commands with color-coded output. Returns False if should exit."""
        cmd = cmd.lower()
        
        if cmd == '/quit':
            console.print("\n[bold yellow]Goodbye![/bold yellow]")
            return False
            
        elif cmd == '/help':
            print_help()
            
        elif cmd == '/clear':
            console.clear()
            print_banner()
            
        elif cmd == '/skills':
            table = Table(title="[bold green]Loaded Skills[/bold green]", box=box.ROUNDED)
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            
            for skill in self.skill_registry.list_all():
                desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
                table.add_row(skill.name, desc)
            
            console.print(table)
            console.print()
            
        elif cmd == '/tools':
            from src.tools import get_all_tools
            
            tools = get_all_tools()
            table = Table(title=f"[bold cyan]Registered Tools ({len(tools)})[/bold cyan]", box=box.ROUNDED)
            table.add_column("#", style="dim", width=3)
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            
            for i, tool in enumerate(tools, 1):
                desc = tool.description if tool.description else "No description"
                desc = desc[:80] + "..." if len(desc) > 80 else desc
                table.add_row(str(i), tool.name, desc)
            
            console.print(table)
            console.print()
            
        elif cmd == '/model':
            model, _, _, provider = get_model_config()
            
            table = Table(title="[bold cyan]Model Configuration[/bold cyan]", box=box.ROUNDED)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Model", f"[bold]{model}[/bold]")
            table.add_row("Provider", f"[dim]{provider}[/dim]")
            table.add_row("Temperature", str(self.agent.config.temperature))
            table.add_row("ReAct Mode", "[green]ON[/green]" if self.react_mode else "[red]OFF[/red]")
            table.add_row("Thread ID", f"[dim]{self.thread_id}[/dim]")
            
            console.print(table)
            console.print()
            
        elif cmd == '/react':
            self.react_mode = not self.react_mode
            if self.react_mode:
                console.print("[bold green]ReAct mode enabled[/bold green] - showing thinking process and tool calls\n")
            else:
                console.print("[bold yellow]ReAct mode disabled[/bold yellow] - showing only final responses\n")
            
        elif cmd == '/plan':
            console.print("[bold cyan]Enter task description for planning:[/bold cyan]")
            plan_query = console.input("[bold yellow]Plan>[/bold yellow] ").strip()
            
            if plan_query:
                console.print("\n[yellow]Creating task plan...[/yellow]")
                try:
                    plan = await self.agent.create_task_plan(plan_query)
                    
                    # Success panel
                    console.print(Panel(
                        f"[bold green]Created {len(plan.tasks)} tasks[/bold green]",
                        title="[bold green]Task Plan Created[/bold green]",
                        border_style="green",
                        box=box.ROUNDED
                    ))
                    
                    # Update sidebar
                    self.update_sidebar()
                    
                    # Show task list with colors
                    for i, task in enumerate(plan.tasks, 1):
                        deps = f" [dim](depends on: {task.blocked_by})[/dim]" if task.blocked_by else ""
                        console.print(f"  [cyan]Task {i}:[/cyan] {task.subject}{deps}")
                    
                    console.print(f"\n[dim]Use '/tasks' to check progress[/dim]\n")
                except Exception as e:
                    console.print(Panel(
                        f"[red]{e}[/red]",
                        title="[bold red]Failed to create plan[/bold red]",
                        border_style="red",
                        box=box.ROUNDED
                    ))
                    console.print()
                    
        elif cmd == '/tasks':
            plan = self.agent.get_current_task_plan()
            if plan:
                self.rich_display.print_summary(plan)
                console.print()
            else:
                console.print(Panel(
                    "[yellow]No active task plan[/yellow]\n[dim]Use /plan to create one[/dim]",
                    title="[bold yellow]No Tasks[/bold yellow]",
                    border_style="yellow",
                    box=box.ROUNDED
                ))
                console.print()
                
        else:
            console.print(f"[bold red]Unknown command:[/bold red] {cmd}")
            console.print("[dim]Type /help for available commands[/dim]\n")
            
        return True
        
    async def process_conversation(self, user_input: str):
        """Process conversation with AI and color-coded output"""
        # Print user message with color
        console.print(f"\n[bold green]You:[/bold green] {user_input}\n")
        
        if self.react_mode:
            # ReAct mode with simplified color scheme
            console.print("[bold blue]AI:[/bold blue] ", end="")
            
            async for event in self.agent.astream_react(user_input, self.thread_id):
                if event.type.value == "content":
                    # AI output content (streaming) - no color
                    console.print(event.content, end="")
                    
                elif event.type.value == "tool_call":
                    # All tool calls use yellow color with wrench icon
                    console.print(f"\n\n[yellow]\u2699\ufe0f  Tool: {event.name}[/yellow]")
                    console.print(f"[dim]   \u25b8 Args: {event.args}[/dim]")
                    
                elif event.type.value == "tool_result":
                    # All tool results use green color with checkmark icon
                    preview = event.content[:200] + " ..." if len(event.content) > 200 else event.content
                    console.print(f"\n[green]\u2713 Result: {preview}[/green]\n")
                    
                    # Update sidebar after tool execution (might have task updates)
                    self.update_sidebar()
                    
                elif event.type.value == "error":
                    console.print(f"\n[bold red]\u2717 Error: {event.content}[/bold red]\n")
                    
            console.print("\n")
            
        else:
            # Normal mode - only show final response
            console.print("[bold blue]AI:[/bold blue] ", end="")
            
            async for chunk in self.agent.astream(user_input, self.thread_id):
                console.print(chunk, end="")
                
            console.print("\n")
            
    async def run(self):
        """Main CLI loop"""
        print_banner()
        
        try:
            self.setup()
        except RuntimeError as e:
            console.print(Panel(
                f"[red]{e}[/red]",
                title="[bold red]Configuration Error[/bold red]",
                border_style="red",
                box=box.DOUBLE
            ))
            return
        except Exception as e:
            console.print(Panel(
                f"[red]{e}[/red]",
                title="[bold red]Setup Failed[/bold red]",
                border_style="red",
                box=box.DOUBLE
            ))
            return
        
        # Main interaction loop
        while True:
            try:
                # Get input with styled prompt
                user_input = console.input("[bold green]You>[/bold green] ").strip()
                
                if not user_input:
                    continue
                
                # Process commands
                if user_input.startswith('/'):
                    should_continue = await self.handle_command(user_input.lower())
                    if not should_continue:
                        break
                    continue
                
                # Process conversation
                await self.process_conversation(user_input)
                
            except KeyboardInterrupt:
                console.print("\n\n[bold yellow]Goodbye![/bold yellow]")
                break
            except Exception as e:
                console.print(Panel(
                    f"[red]{e}[/red]",
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
                console.print()


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
        cli = NovaCLI()
        if args.no_react:
            cli.react_mode = False
        asyncio.run(cli.run())
    except Exception as e:
        console.print(Panel(
            f"[red]{e}[/red]",
            title="[bold red]Startup Failed[/bold red]",
            border_style="red",
            box=box.DOUBLE
        ))
        sys.exit(1)


if __name__ == "__main__":
    main()
