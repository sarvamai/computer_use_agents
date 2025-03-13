import time
import json
import argparse
from typing import List, Dict, Any, Optional, Callable, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from computers.morph import MorphComputer
from agent.autonomous_agent import AutonomousAgent

console = Console()

class BranchingAgent:
    """
    A class to manage branching of MorphComputer environments and running
    autonomous agents in each branch.
    
    The BranchingAgent allows developers to:
    1. Create multiple parallel branches from a single starting environment
    2. Run different strategies or behaviors in each branch
    3. Compare the outcomes to determine which approach is most successful
    """

    def __init__(self,
                 computer: Optional[MorphComputer] = None,
                 skip_verification: bool = False,
                 agent_callback: Optional[Callable] = None,
                 agent_kwargs: Optional[Dict] = None,
                 completion_mode: str = "all"):
        """
        Initialize the BranchingAgent.

        Args:
            computer: An initialized MorphComputer to use for branching.
            config_path: Path to a JSON config file.
            skip_verification: Skip verification of instance or snapshot.
            agent_callback: Callback function for agents (step, action, response).
            agent_kwargs: Keyword arguments to pass to AutonomousAgent constructor.
            completion_mode: "all" to wait for all agents, "first" to stop on first completion.
        """
        self.main_computer = computer
        self.skip_verification = skip_verification
        self.agent_callback = agent_callback
        self.agent_kwargs = agent_kwargs or {}  # Default to empty dict if None
        self.completion_mode = completion_mode.lower() # Store and normalize completion_mode

        self.shared_context = None
        self.branch_instructions = []
        self.branches = {}
        self.agents = {}
        self.base_snapshot = None


        if self.completion_mode not in ["all", "first"]: # Validate completion_mode
            raise ValueError(f"Invalid completion_mode: '{completion_mode}'. Must be 'all' or 'first'.")


    def _load_config(self):
        """Load configuration from JSON file if provided."""
        if self.config_path:
            try:
                with open(self.config_path, 'r') as f:
                    self.config_data = json.load(f)
                if 'context' in self.config_data:
                    self.shared_context = self.config_data['context']
                if 'branch_instructions' in self.config_data:
                    self.branch_instructions = self.config_data['branch_instructions']
                if 'completion_mode' in self.config_data: # Load completion_mode from config
                    self.completion_mode = self.config_data['completion_mode'].lower()
                console.print(f"[bold green]Loaded configuration from {self.config_path}[/]")
            except Exception as e:
                console.print(f"[bold red]Error loading config file: {str(e)}[/]")
                raise

    def create_snapshot(self, computer=None):
        """
        Create a snapshot from a computer for branching.
        
        Args:
            computer: The computer to snapshot. If None, uses main_computer.
            
        Returns:
            The snapshot object created.
        """
        if computer is None:
            computer = self.main_computer
            
        if not computer:
            raise ValueError("No computer provided to create a snapshot from. Initialize BranchingAgent with a computer or provide one explicitly.")
            
        print(f"Creating snapshot for branching...")
        snapshot = computer.create_snapshot(
            description="Branch base state",
            metadata={"purpose": "branching", "created_by": "BranchingAgent"}
        )
        
        # Store for later use if needed
        self.base_snapshot = snapshot
        
        return snapshot
        
    def create_branches(self, instructions, snapshot=None, context=None, 
                        branch_names=None, auto_open_browser=True, skip_verification=None):
        """
        Create branch computers based on snapshot and instructions.
        
        Args:
            instructions: List of branch-specific instructions.
            snapshot: Snapshot object to branch from. If None, uses base_snapshot.
            context: Shared context for all branches. If None, uses self.shared_context.
            branch_names: Custom names for branches. If None, uses "branch-0", "branch-1", etc.
            auto_open_browser: Whether to open browser for branch computers.
            skip_verification: Whether to skip snapshot verification. If None, uses self.skip_verification.
            
        Returns:
            Dictionary of branch_id -> branch_computer.
        """
        if snapshot is None:
            snapshot = self.base_snapshot
            
        if not snapshot:
            raise ValueError("No snapshot provided and no base_snapshot available")
            
        if context is None:
            context = self.shared_context
            
        if skip_verification is None:
            skip_verification = self.skip_verification
            
        # Store instructions for later use
        self.branch_instructions = instructions
        
        if branch_names is None:
            branch_names = [f"branch-{i}" for i in range(len(instructions))]
            
        branches = {}
        console.print("\n[bold green]Creating branches...[/]")
        
        for i, (branch_name, instruction) in enumerate(zip(branch_names, instructions)):
            console.print(f"[bold green]Creating branch [cyan]{branch_name}[/]...[/]")
            
            console.print(f"[bold yellow]Branch {branch_name} - Creating computer from snapshot...[/]")
            branch_computer = MorphComputer.from_snapshot(
                snapshot=snapshot,
                auto_open_browser=auto_open_browser,
                skip_verification=skip_verification
            )
            branch_computer = branch_computer.__enter__()
            console.print(f"[bold green]Branch [cyan]{branch_name}[/] created[/]")
            branches[branch_name] = branch_computer
            
        # Store for later use
        self.branches = branches
        return branches
        
    def create_agents(self, branches=None, instructions=None, context=None, agent_kwargs=None):
        """
        Create autonomous agents for each branch.
        
        Args:
            branches: Dictionary of branch_id -> branch_computer. If None, uses self.branches.
            instructions: List of branch-specific instructions. If None, uses self.branch_instructions.
            context: Shared context for all branches. If None, uses self.shared_context.
            agent_kwargs: Additional kwargs for AutonomousAgent. If None, uses self.agent_kwargs.
            
        Returns:
            Dictionary of branch_id -> agent.
        """
        if branches is None:
            branches = self.branches
            
        if not branches:
            raise ValueError("No branches provided and no branches available")
            
        if instructions is None:
            instructions = self.branch_instructions
            
        if len(instructions) != len(branches):
            raise ValueError(f"Number of instructions ({len(instructions)}) does not match number of branches ({len(branches)})")
            
        if context is None:
            context = self.shared_context
            
        if agent_kwargs is None:
            agent_kwargs = self.agent_kwargs.copy() if self.agent_kwargs else {}
            
        agents = {}
        branch_ids = list(branches.keys())
        
        console.print("\n[bold green]Creating agents for branches...[/]")
        
        for i, branch_id in enumerate(branch_ids):
            branch_computer = branches[branch_id]
            instruction = instructions[i]
            
            # Format full instruction with context
            full_instruction = f"SHARED CONTEXT: {context}\n\nBRANCH-SPECIFIC INSTRUCTION: {instruction}\n\nWhen you believe you have completed your task, use the 'done' tool to indicate completion and provide a reason."
            
            branch_tools = [
                {
                    "type": "computer-preview",
                    "display_width": branch_computer.dimensions[0],
                    "display_height": branch_computer.dimensions[1],
                    "environment": branch_computer.environment,
                }
            ]
            
            # Create agent kwargs for this specific branch
            branch_agent_kwargs = agent_kwargs.copy()
            branch_agent_kwargs.update({
                "tools": branch_tools,
                "initial_task": full_instruction,
                "computer": branch_computer,
                "branch_id": branch_id,
                "callback": lambda step, action, response, bid=branch_id: self.agent_callback(bid, step, action, response) if self.agent_callback else None,
                "suppress_original_prints": True,
                "verbose_boot": False
            })
            
            console.print(f"[bold yellow]Branch {branch_id} - Creating autonomous agent...[/]")
            branch_agent = AutonomousAgent(**branch_agent_kwargs)
            agents[branch_id] = branch_agent
            
        # Store for later use
        self.agents = agents
        return agents
        
    def start_agents(self, agents=None, blocking=False):
        """
        Start autonomous agents.
        
        Args:
            agents: Dictionary of branch_id -> agent. If None, uses self.agents.
            blocking: Whether to block until all agents complete.
            
        Returns:
            Dictionary of branch_id -> agent.
        """
        if agents is None:
            agents = self.agents
            
        if not agents:
            raise ValueError("No agents provided and no agents available")
            
        console.print("\n[bold green]Starting agents...[/]")
        
        for branch_id, agent in agents.items():
            console.print(f"[bold yellow]Branch {branch_id} - Starting autonomous agent...[/]")
            agent.start(blocking=False)  # Always non-blocking initially
            console.print(f"[bold green]Started autonomous agent on branch [cyan]{branch_id}[/][/]")
            
        # If blocking is requested, wait for all agents to complete
        if blocking:
            self.wait_for_agents_completion()
            
        return agents
    
    def run_branches(self, instructions, context=None, 
                    branch_names=None, wait_mode=None, timeout=None,
                    auto_open_browser=True, skip_verification=None):
        """
        High-level method to run branches with instructions.
        This is the primary method that most developers will use.
        
        Args:
            instructions: List of branch-specific instructions.
            context: Shared context for all branches. If None, uses self.shared_context.
            branch_names: Custom names for branches. If None, generates names.
            wait_mode: How to wait for completion ("all" or "first"). If None, uses self.completion_mode.
            timeout: Maximum time (in seconds) to wait for agents. If None, waits indefinitely.
            auto_open_browser: Whether to open browser for branch computers.
            skip_verification: Whether to skip snapshot verification. If None, uses self.skip_verification.
            
        Returns:
            Dictionary of results from each branch.
        """
        # Save original completion mode and restore it later
        original_mode = self.completion_mode
        
        if skip_verification is None:
            skip_verification = self.skip_verification
        
        try:
            # Setup wait mode if provided
            if wait_mode:
                if wait_mode not in ["all", "first"]:
                    raise ValueError(f"Invalid wait_mode: {wait_mode}. Must be 'all' or 'first'.")
                self.completion_mode = wait_mode
            
            # Verify we have a source computer
            if not self.main_computer:
                raise ValueError("No computer provided. Initialize BranchingAgent with a computer.")
            
            # Take a snapshot of the source computer
            snapshot = self.create_snapshot(self.main_computer)
            
            # Verify we have instructions
            if not instructions:
                raise ValueError("No branch instructions provided")
            
            self.branch_instructions = instructions
            
            # Verify we have context
            if context is not None:
                self.shared_context = context
                
            if not self.shared_context:
                self.shared_context = "Execute the branch-specific instruction."
            
            # Create branches
            branches = self.create_branches(
                self.branch_instructions,
                snapshot=snapshot,
                context=self.shared_context,
                branch_names=branch_names,
                auto_open_browser=auto_open_browser,
                skip_verification=skip_verification
            )
            
            # Create agents
            agents = self.create_agents(
                branches=branches,
                instructions=self.branch_instructions,
                context=self.shared_context
            )
            
            # Start agents
            self.start_agents(agents)
            
            # Wait for completion with optional timeout
            if timeout:
                import threading
                completion_event = threading.Event()
                
                def wait_thread():
                    self.wait_for_agents_completion()
                    completion_event.set()
                
                thread = threading.Thread(target=wait_thread)
                thread.start()
                
                if not completion_event.wait(timeout):
                    console.print(f"[bold yellow]Timeout after {timeout} seconds[/]")
                    self.stop_all_agents()
            else:
                self.wait_for_agents_completion()
            
            # Get results
            results = self.get_results()
            
            return results
            
        finally:
            # Restore original completion mode
            self.completion_mode = original_mode
    
    def get_results(self):
        """
        Get results from all agents.
        
        Returns:
            Dictionary of branch_id -> result, where result contains metrics and output.
        """
        results = {}
        
        for branch_id, agent in self.agents.items():
            result = {
                "status": "completed" if not agent.running else "running",
                "steps": agent.steps_taken,
                "output": agent.last_response,
                "agent": agent,
                "branch_id": branch_id
            }
            results[branch_id] = result
            
        return results
        

    def wait_for_agents_completion(self):
        """Wait for agents to complete based on completion_mode."""
        console.print(f"\n[bold yellow]Waiting for agents to finish ({self.completion_mode} mode)...[/]")
        if self.completion_mode == "all":
            running = True
            while running:
                running = False
                for agent in self.agents.values():
                    if agent.running:
                        running = True
                        break
                if running:
                    time.sleep(2)
            console.print("[bold green]All agents completed![/]")
        elif self.completion_mode == "first":
            while True:
                for agent in self.agents.values():
                    if not agent.running: # Check if *any* agent is not running
                        console.print("[bold green]First agent completed, stopping wait.[/]")
                        return # Exit as soon as one agent is done
                time.sleep(2) # Wait and check again
        else: # Should not reach here due to validation in __init__
            raise ValueError("Invalid completion_mode (internal error)")

    def display_results(self):
        """Display the final results from each agent in a table and panels."""
        console.print("\n[bold]===== FINAL RESULTS =====", style="white on blue")
        table = Table(title="Branch Results Summary", show_header=True, header_style="bold")
        table.add_column("Branch", style="cyan")
        table.add_column("Instruction", style="green", no_wrap=False)
        table.add_column("Steps", style="magenta")
        table.add_column("Status", style="yellow") # Added Status column

        branch_specific_instructions = self.branch_instructions # Assuming these are set

        for branch_id, agent in self.agents.items():
            branch_index = int(branch_id.split('-')[1])
            instruction = branch_specific_instructions[branch_index]
            steps = str(agent.steps_taken)
            status = "[green]Completed[/]" if not agent.running else "[yellow]Running[/]" # Determine status
            table.add_row(branch_id, instruction, steps, status)
        console.print(table)

    def stop_all_agents(self):
        """Stop all running autonomous agents."""
        console.print("[bold yellow]Stopping agents...[/]")
        for agent in self.agents.values():
            agent.stop()
        console.print("[bold green]All agents stopped[/]")

    def cleanup_branches(self):
        """Clean up all branch MorphComputer instances."""
        console.print("[bold yellow]Cleaning up branch computers...[/]")
        for branch_id, branch in self.branches.items():
            try:
                branch.__exit__(None, None, None)  # Will be replaced by branch.cleanup() when implemented in MorphComputer
                console.print(f"[green]Cleaned up branch {branch_id}[/]")
            except Exception as e:
                console.print(f"[bold red]Error cleaning up branch {branch_id}: {e}[/]")
    
    def cleanup_main_computer(self):
        """Clean up the main MorphComputer instance."""
        if self.main_computer:
            try:
                self.main_computer.__exit__(None, None, None)  # Will be replaced by main_computer.cleanup() when implemented
                console.print("[green]Cleaned up main computer[/]")
            except Exception as e:
                console.print(f"[bold red]Error cleaning up main computer: {e}[/]")


