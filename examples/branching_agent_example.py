#!/usr/bin/env python3
"""
Branching Agent Example

This script demonstrates how to use the BranchingAgent class to create
multiple branches and run autonomous agents.

Run the example:
  python examples/branching_agent_example.py [--snapshot_id <your_snapshot_id>]
"""

import sys
import os
import argparse

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.branching_agent import BranchingAgent
from computers.morph import MorphComputer
from rich.console import Console
from rich.panel import Panel

console = Console()

def agent_callback(branch_id, step, action, response):
    """Callback function for the autonomous agent to report progress"""
    branch_id_num = int(branch_id.split('-')[1]) if '-' in branch_id else 0
    colors = ["blue", "green", "magenta", "yellow", "cyan", "red"]
    color = colors[branch_id_num % len(colors)]

    action_display = action
    if action == "initial_task":
        action_display = "STARTED"
    elif action == "continuation":
        action_display = "THINKING"
    elif action == "error":
        action_display = "ERROR"
    elif "done" in action.lower():
        action_display = "COMPLETED"

    title = f"BRANCH {branch_id} | Step {step}: {action_display}"

    if response:
        if isinstance(response, list):
            formatted_response = str(response)[:150] + ('...' if len(str(response)) > 150 else '')
        else:
            formatted_response = response[:150] + ('...' if len(response) > 150 else '')

        panel = Panel(
            f"[white]{formatted_response}[/]",
            title=title,
            border_style=color,
            title_align="left",
            padding=(1, 2)
        )
        console.print(panel)

def main():
    parser = argparse.ArgumentParser(description="Run branching experiments with autonomous agents")
    parser.add_argument("--instance_id", help="Existing instance ID to use")
    parser.add_argument("--snapshot_id", help="Existing snapshot ID to use for branching")
    parser.add_argument("--skip_verification", action="store_true", help="Skip verification")
    parser.add_argument("--max_steps", type=int, default=100, help="Maximum steps per agent")
    parser.add_argument("--step_delay", type=float, default=1.0, help="Delay between agent steps")
    parser.add_argument("--completion_mode", default="all", choices=["all", "first"], help="Completion mode: all or first (default: all)")
    parser.add_argument("--auto_open_browser", action="store_true", default=True, help="Automatically open browser")
    args = parser.parse_args()

    agent_kwargs = {
        "max_steps": args.max_steps,
        "step_delay": args.step_delay
    }

    # Initialize the source computer first
    console.print("[bold blue]Initializing source computer...[/]")
    computer = MorphComputer(
        instance_id=args.instance_id,
        snapshot_id=args.snapshot_id,
        skip_verification=args.skip_verification,
        auto_open_browser=args.auto_open_browser
    )
    
    # Initialize the computer using context manager
    with computer as initialized_computer:
        console.print("[bold green]Computer initialized successfully[/]")
        
        # Create the branching agent with the initialized computer
        branching_agent = BranchingAgent(
            computer=initialized_computer,
            skip_verification=args.skip_verification,
            agent_callback=agent_callback,
            agent_kwargs=agent_kwargs,
            completion_mode=args.completion_mode
        )
            # Let user explore before branching
        input("\nExplore the initial state in the browser window.\nPress Enter when you're ready to create branches...\n")

        # Always get instructions interactively
        branching_agent.shared_context = input("\nEnter shared context for all branches: ")

        while True:
            try:
                num_branches = int(input("How many branches would you like to create? "))
                if num_branches <= 0:
                    print("Please enter a positive number.")
                    continue
                break
            except ValueError:
                print("Please enter a valid number.")

        branching_agent.branch_instructions = []
        for i in range(num_branches):
            branch_instruction = input(f"Instruction for branch {i+1}: ")
            branching_agent.branch_instructions.append(branch_instruction)
        
            
        # Run branches with the computer-first approach
        console.print("[bold blue]Running branches...[/]")
        results = branching_agent.run_branches(
            instructions=branching_agent.branch_instructions,
            context=branching_agent.shared_context
        )
        
        # Display results
        branching_agent.display_results()
        

if __name__ == "__main__":
    main()
