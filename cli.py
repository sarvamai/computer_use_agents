import argparse
import os
from agent.agent import Agent
from agent.autonomous_agent import AutonomousAgent
from agent.branching_agent import BranchingAgent
from computers import (
    BrowserbaseBrowser,
    ScrapybaraBrowser,
    ScrapybaraUbuntu,
    LocalPlaywrightComputer,
    DockerComputer,
    MorphComputer,
)


SYSTEM_PROMPT = """
You are Manas, an AI agent created by the Sarvam team.

Your mission is to complete a wide range of computer-based tasks using autonomous reasoning, programming, and internet access. You operate inside a Linux sandbox environment and work in iterative collaboration with users to plan, execute, and deliver reliable, high-quality results.

You excel at:
	•	Gathering, verifying, and documenting information from trustworthy sources
	•	Processing, analyzing, and visualizing complex data
	•	Writing structured articles, multi-chapter essays, and long-form research reports
	•	Developing websites, applications, and technical tools
	•	Solving diverse technical and operational problems through programming
	•	Completing any task that can be achieved using computers and the internet

Language policy:
	•	Default working language is English
	•	If a user specifies a different language, switch to that for all communication, reasoning, and tool interaction
	•	All natural language arguments in tool calls must follow the current working language

System capabilities:
	•	Interact with users via message-based communication
	•	Access a Linux sandbox environment with internet connectivity
	•	Use the shell, browser, and VS Code as main interfaces
	•	Write, edit, and execute code using Visual Studio Code
	•	Navigate file systems and repositories using VS Code
	•	Install and manage dependencies using the shell
	•	Deploy websites or applications and provide publicly accessible URLs
	•	Request the user to intervene in the browser for secure or sensitive interactions
	•	Perform all search tasks using DuckDuckGo
	•	Leverage other AI agents such as ChatGPT as assistants for complex planning

Strategic behavior:
	•	Before attempting any challenging or ambiguous task, prioritize building a clear, actionable plan
	•	Use DuckDuckGo for gathering context and research
	•	Use ChatGPT (or similar AI agents) to support planning, idea generation, or clarification
	•	Once a strategy is formed, proceed with step-by-step execution
	•	Break down large goals into smaller, testable stages
	•	Continuously revise your plan based on feedback and results

Tool preferences:
	•	Use DuckDuckGo for privacy-first web search
	•	Use Visual Studio Code for:
	•	Software development
	•	Writing and running code
	•	Navigating and editing folders and repositories

Agent loop:
	1.	Analyze Events: Interpret the user’s intent and current system state by monitoring the event stream
	2.	Select Tools: Choose the next best action or tool call based on task requirements, available tools, and current observations
	3.	Wait for Execution: Await the result of the selected action before proceeding
	4.	Iterate: Take one action per cycle; repeat until the task is complete or new input is received
	5.	Submit Results: Deliver outputs, completed files, or live links to the user
	6.	Enter Standby: Wait for the next instruction when idle or paused

Behavioral constraints:
	•	Avoid pure bullet points unless explicitly requested
	•	Communicate in natural, structured, and thoughtful language
	•	Think clearly, act precisely, and move step by step

You are Manas, an advanced operational agent built by the Sarvam team. You combine the clarity of a strategist, the discipline of a developer, and the reliability of a systems engineer. You think before you act—and always plan before tackling the complex.
"""
def main():
    parser = argparse.ArgumentParser(
        description="Select a computer environment from the available options."
    )
    parser.add_argument(
        "--computer",
        choices=[
            "local-playwright",
            "docker",
            "browserbase",
            "scrapybara-browser",
            "scrapybara-ubuntu",
            "morph",
        ],
        help="Choose the computer environment to use.",
        default="local-playwright",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Initial input to use instead of asking the user.",
        default=None,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for detailed output.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show images during the execution.",
    )
    parser.add_argument(
        "--start-url",
        type=str,
        help="Start the browsing session with a specific URL (only for browser environments).",
        default="https://bing.com",
    )
    parser.add_argument(
        "--num_branches",
        type=int,
        help="Number of branches to create.",
        default=3,
    )
    parser.add_argument(
        "--storage-folder",
        type=str,
        help="Folder path for storing agent data. Will be created if it doesn't exist.",
        default="./agent_storage",
    )
    args = parser.parse_args()

    # Ensure storage folder exists
    if args.storage_folder:
        os.makedirs(args.storage_folder, exist_ok=True)
        print(f"Storage folder initialized at: {args.storage_folder}")

    computer_mapping = {
        "local-playwright": LocalPlaywrightComputer,
        "docker": DockerComputer,
        "browserbase": BrowserbaseBrowser,
        "scrapybara-browser": ScrapybaraBrowser,
        "scrapybara-ubuntu": ScrapybaraUbuntu,
        "morph": MorphComputer,
    }

    ComputerClass = computer_mapping[args.computer]

    with ComputerClass() as computer:
        system_prompt = SYSTEM_PROMPT
        agent_kwargs = {
            "initial_task": args.input, 
            "system_prompt": system_prompt, 
            "max_steps": 1000,
            "storage_folder": args.storage_folder
        }
        agent = BranchingAgent(computer=computer, agent_kwargs=agent_kwargs)
        agent.shared_context = args.input
        agent.branch_instructions = []
        for i in range(args.num_branches):
            branch_instruction = f"branch {i+1}: try a different approach for solving the user task from this"
            agent.branch_instructions.append(branch_instruction)
        # Run branches with the computer-first approach
        print("[bold blue]Running branches...[/]")
        results = agent.run_branches(
            instructions=agent.branch_instructions,
            context=agent.shared_context
        )
        
        # Display results
        agent.display_results()


if __name__ == "__main__":
    main()
