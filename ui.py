import streamlit as st
import os
import asyncio
from typing import List, Dict, Any, Optional

# Import the agent components from cli.py
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

# Use the system prompt from cli.py
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
	1.	Analyze Events: Interpret the user's intent and current system state by monitoring the event stream
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

# Streamlit styling
STREAMLIT_STYLE = """
<style>
    /* Custom styles for the chat interface */
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #f0f2f6;
    }
    .chat-message.assistant {
        background-color: #e3f2fd;
    }
    .chat-message .avatar {
        width: 20px;
        height: 20px;
        margin-right: 8px;
    }
    .chat-message .content {
        display: flex;
        flex-direction: column;
        margin-top: 0.5rem;
    }
    /* Make the desktop view fill its container */
    .desktop-view {
        width: 100%;
        height: 600px;
        border: 1px solid #ddd;
        border-radius: 5px;
    }
    /* Hide the streamlit deploy button */
    .stAppDeployButton {
        visibility: hidden;
    }
</style>
"""

# Message container for the chat interface
def message_container(is_user, content, key=None):
    container = st.container()
    with container:
        if is_user:
            st.markdown(f'<div class="chat-message user"><div class="content">{content}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-message assistant"><div class="content">{content}</div></div>', unsafe_allow_html=True)
    return container

# Capture and display screenshots/browser views
def display_browser_view(url, container):
    container.markdown(f'<div class="desktop-view"><iframe src="{url}" width="100%" height="600px"></iframe></div>', unsafe_allow_html=True)
    container.write(f"Current URL: {url}")

# Initialize session state
def initialize_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "browser_url" not in st.session_state:
        st.session_state.browser_url = ""
    if "computer" not in st.session_state:
        st.session_state.computer = None
    if "initial_task" not in st.session_state:
        st.session_state.initial_task = ""
    if "num_branches" not in st.session_state:
        st.session_state.num_branches = 3
    if "branch_results" not in st.session_state:
        st.session_state.branch_results = []

# Initialize the agent
def initialize_agent():
    computer_type = st.session_state.computer_type
    start_url = st.session_state.start_url
    initial_task = st.session_state.initial_task
    num_branches = st.session_state.num_branches
    
    if not initial_task.strip():
        st.error("Please provide an initial task before initializing the agent.")
        return
    
    computer_mapping = {
        "local-playwright": LocalPlaywrightComputer,
        "docker": DockerComputer,
        "browserbase": BrowserbaseBrowser,
        "scrapybara-browser": ScrapybaraBrowser,
        "scrapybara-ubuntu": ScrapybaraUbuntu,
        "morph": MorphComputer,
    }
    
    ComputerClass = computer_mapping[computer_type]
    
    # Initialize the computer and branching agent using a context manager
    with ComputerClass() as computer:
        st.session_state.computer = computer
        
        # Use BranchingAgent like in cli.py
        agent = BranchingAgent(
            computer=computer, 
            agent_kwargs={
                "initial_task": initial_task, 
                "system_prompt": SYSTEM_PROMPT, 
                "max_steps": 1000
            }
        )
        
        # Set up branching like in cli.py
        agent.shared_context = initial_task
        agent.branch_instructions = []
        for i in range(num_branches):
            branch_instruction = f"branch {i+1}: try a different approach for solving the user task from this"
            agent.branch_instructions.append(branch_instruction)
        
        st.session_state.agent = agent
        
        # Add a system message to the chat
        st.session_state.messages.append({"role": "assistant", "content": f"Agent initialized with task: {initial_task}\nRunning {num_branches} branches to explore different approaches..."})
        
        # Start branching in the background
        try:
            # Clear previous results
            st.session_state.branch_results = []
            
            # Run branches with the computer-first approach
            results = agent.run_branches(
                instructions=agent.branch_instructions,
                context=agent.shared_context
            )
            
            # Store results
            st.session_state.branch_results = results
            
            # Add results to chat
            st.session_state.messages.append({"role": "assistant", "content": "Branching completed. Here are the results:"})
            for i, result in enumerate(results):
                st.session_state.messages.append({"role": "assistant", "content": f"Branch {i+1}: {result}"})
            
            # If a start URL is provided, navigate to it
            if start_url:
                st.session_state.browser_url = start_url
                st.session_state.messages.append({"role": "assistant", "content": f"Navigated to {start_url}"})
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Error running branches: {str(e)}"})

# Process user input and run agent
def process_user_input(user_input):
    if not st.session_state.agent:
        st.session_state.messages.append({"role": "assistant", "content": "Agent not initialized. Please provide an initial task and click 'Initialize Agent' in the sidebar."})
        return
    
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Get the stored agent configuration
    computer_type = st.session_state.computer_type
    
    computer_mapping = {
        "local-playwright": LocalPlaywrightComputer,
        "docker": DockerComputer,
        "browserbase": BrowserbaseBrowser,
        "scrapybara-browser": ScrapybaraBrowser,
        "scrapybara-ubuntu": ScrapybaraUbuntu,
        "morph": MorphComputer,
    }
    
    ComputerClass = computer_mapping[computer_type]
    
    # Create message items for the agent
    items = [{"role": "user", "content": user_input}]
    
    # Run the agent with a fresh computer instance using context manager
    try:
        with ComputerClass() as computer:
            # Get the agent from session state
            agent = st.session_state.agent
            
            # Update the agent with the new computer
            agent.computer = computer
            
            # Run the agent and get output
            output_items = agent.run_full_turn(
                items,
                print_steps=True,
                show_images=True,
                debug=st.session_state.debug_mode
            )
            
            # Process agent responses
            for item in output_items:
                if item["role"] == "assistant":
                    st.session_state.messages.append({"role": "assistant", "content": item["content"]})
                
                # Check if there's a screenshot/browser update
                if "images" in item and item["images"]:
                    for image in item["images"]:
                        # In a real implementation, we would handle the image display here
                        # For now, we'll just capture the URL
                        if "url" in image:
                            st.session_state.browser_url = image["url"]
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Error running agent: {str(e)}"})

# Main Streamlit app
def main():
    st.set_page_config(page_title="AI Agent UI", layout="wide")
    st.markdown(STREAMLIT_STYLE, unsafe_allow_html=True)
    
    initialize_session()
    
    # Store a counter in session state to create unique keys
    if "input_key_counter" not in st.session_state:
        st.session_state.input_key_counter = 0
    
    # Sidebar for configuration
    with st.sidebar:
        st.title("Agent Configuration")
        
        # Initial task input
        st.text_area("Initial Task", key="initial_task", height=100, 
                     help="Enter the task you want the agent to complete")
        
        # Number of branches slider
        st.session_state.num_branches = st.slider("Number of Branches", min_value=1, max_value=5, value=3,
                                              help="Number of different approaches to try for solving the task")
        
        # Computer type selection
        computer_options = [
            "morph",  # Set as first option to be default
            "local-playwright", 
            "docker", 
            "browserbase", 
            "scrapybara-browser", 
            "scrapybara-ubuntu"
        ]
        st.session_state.computer_type = st.selectbox(
            "Computer Environment", 
            options=computer_options, 
            index=0  # Default to morph
        )
        
        # Start URL input
        st.session_state.start_url = st.text_input("Start URL", value="https://duckduckgo.com")
        
        # Debug mode
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        # Initialize agent button
        if st.button("Initialize Agent"):
            initialize_agent()
        
        # Add spacing
        st.markdown("---")
        
        # Desktop URL view in sidebar
        st.header("Desktop View")
        
        # Create tabs for each branch plus a "Current" tab
        tab_titles = ["Current"]
        for i in range(st.session_state.num_branches):
            tab_titles.append(f"Branch {i+1}")
        
        desktop_tabs = st.tabs(tab_titles)
        
        # Display browser view in tabs
        with desktop_tabs[0]:  # Current tab
            if st.session_state.browser_url:
                display_browser_view(st.session_state.browser_url, desktop_tabs[0])
            else:
                st.write("Browser will be displayed here after initialization.")
        
        # Display branch results in their respective tabs
        for i in range(min(len(st.session_state.branch_results), st.session_state.num_branches)):
            with desktop_tabs[i+1]:  # Branch tabs (index offset by 1 because of "Current" tab)
                st.write(f"Branch {i+1} approach:")
                st.write(st.session_state.branch_results[i])
                # If we had specific URLs for each branch, we would display them here
                st.write("No branch-specific view available")
    
    # Main content area for chat only now
    st.header("Chat")
    
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            message_container(
                is_user=(message["role"] == "user"),
                content=message["content"]
            )
    
    # Input for new messages - using a form with a dynamic key
    current_key = f"user_message_{st.session_state.input_key_counter}"
    with st.form(key=f"chat_form_{st.session_state.input_key_counter}", clear_on_submit=True):
        user_input = st.text_input("Type your message here...", key=current_key)
        submit = st.form_submit_button("Send")
        if submit and user_input.strip():
            process_user_input(user_input)
            # Increment counter for next render to get a fresh input field
            st.session_state.input_key_counter += 1
            st.experimental_rerun()

if __name__ == "__main__":
    main()