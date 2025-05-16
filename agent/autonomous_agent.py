"""
Autonomous Agent implementation that runs continuously without user input.
"""

import time
import threading
import json
import random
import os
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Union

from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from agent.agent import Agent
from utils import create_response, show_image

# Initialize Rich console
console = Console()


def retry_with_exponential_backoff(func, max_retries=5, initial_delay=0.1):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        
    Returns:
        Result of the function if successful
        
    Raises:
        Exception: If all retries fail
    """
    retries = 0
    delay = initial_delay
    
    while retries < max_retries:
        try:
            return func()
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                raise e
            
            # Add some jitter to the delay
            jitter = random.uniform(0, 0.1 * delay)
            sleep_time = delay + jitter
            
            # Log the retry
            console.print(f"[bold yellow]Retrying after error: {str(e)}. Retry {retries}/{max_retries} after {sleep_time:.2f}s delay[/]")
            
            # Sleep and increase delay for next retry
            time.sleep(sleep_time)
            delay *= 2
    
    # This should never be reached due to the exception above
    raise Exception("Max retries exceeded")


class AutonomousAgent:
    """
    An agent that continuously works on a task without requiring user input.
    
    This agent wraps a standard Agent and automatically injects continuations
    to keep the agent working on its assigned task.
    """
    
    def __init__(
        self, 
        tools: List[Dict] = [],
        initial_task: str = "",
        model: str = "computer-use-preview",
        system_prompt: str = None,
        temperature: float = None,
        max_steps: int = 10,
        step_delay: float = 1.0,
        callback: Callable = None,
        computer=None,
        branch_id=None,
        suppress_original_prints: bool = True,
        verbose_boot: bool = False,
        storage_folder: str = None
    ):
        """
        Initialize an autonomous agent.
        
        Args:
            tools: List of tool definitions (dictionaries)
            initial_task: The initial task/prompt for the agent
            model: LLM model to use (defaults to "computer-use-preview")
            system_prompt: Optional system prompt
            temperature: Optional temperature setting
            max_steps: Maximum number of autonomous steps to take
            step_delay: Delay between steps in seconds
            callback: Optional callback function(step, action, response)
            computer: Optional computer instance to pass to the agent
            branch_id: Optional identifier for the branch this agent is running in
            suppress_original_prints: Whether to suppress original agent's print statements
            verbose_boot: Whether to show verbose debugging during agent boot
            storage_folder: Optional path to a folder for storing agent data
        """
        # Store branch id
        self.branch_id = branch_id
        
        # Add new parameters
        self.suppress_original_prints = suppress_original_prints
        self.verbose_boot = verbose_boot
        
        # Handle storage folder and create subfolder if branch_id is specified
        self.storage_folder = storage_folder
        if self.storage_folder:
            # Ensure the main storage folder exists
            os.makedirs(self.storage_folder, exist_ok=True)
            
            # If branch_id is provided, create a branch-specific subfolder
            if self.branch_id:
                branch_folder = os.path.join(self.storage_folder, str(self.branch_id))
                os.makedirs(branch_folder, exist_ok=True)
                self.storage_folder = branch_folder
                if self.verbose_boot:
                    branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                    console.print(f"[bold cyan]{branch_prefix}Created branch storage folder: {self.storage_folder}[/]")
            elif self.verbose_boot:
                console.print(f"[bold cyan]Using storage folder: {self.storage_folder}[/]")
                
            # Create screenshots subfolder
            self.screenshots_folder = os.path.join(self.storage_folder, "screenshots")
            os.makedirs(self.screenshots_folder, exist_ok=True)
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold cyan]{branch_prefix}Created screenshots folder: {self.screenshots_folder}[/]")
                
            # Initialize trajectory record
            self.trajectory_file = os.path.join(self.storage_folder, "trajectory.json")
            self.trajectory = {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "branch_id": self.branch_id,
                "actions": [],
                "interactions": [],
                "completion": None
            }
            self.screenshot_counter = 0
            
            # Save initial trajectory file
            try:
                with open(self.trajectory_file, 'w') as f:
                    json.dump(self.trajectory, f, indent=2)
                if self.verbose_boot:
                    branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                    console.print(f"[bold green]{branch_prefix}Created trajectory file: {self.trajectory_file}[/]")
            except Exception as e:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold red]{branch_prefix}Error creating trajectory file: {str(e)}[/]")
        
        if self.verbose_boot:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold cyan]{branch_prefix}Initializing autonomous agent...[/]")
        
        # Add 'done' tool to the tools list if it's not already there
        has_done_tool = any(tool.get("name") == "done" for tool in tools)
        if not has_done_tool:
            done_tool = {
                "type": "function",
                "name": "done",
                "description": "Call this function when you have completed your task and want to stop.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Reason for completing the task.",
                        },
                    },
                    "additionalProperties": False,
                    "required": ["reason"],
                }
            }
            tools.append(done_tool)
            
        # Create the underlying agent
        self.agent = Agent(
            computer=computer,
            tools=tools,
            model=model
        )
        
        # Suppress original agent's print_steps if requested
        if self.suppress_original_prints:
            self.agent.print_steps = False
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold yellow]{branch_prefix}Suppressed original agent print statements[/]")
        
        # We handle "done" tool calls directly in the _run_loop method
        # rather than trying to register handlers with the base Agent
        
        self.initial_task = initial_task
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.callback = callback
        
        # Match properties from the original agent
        self.debug = False
        self.show_images = False
        
        # Execution state
        self.running = False
        self.steps_taken = 0
        self.last_response = None
        self.conversation = []
        self.thread = None
        
        if self.verbose_boot:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold green]{branch_prefix}Autonomous agent initialized successfully[/]")
    
    def start(self, computer=None, blocking=False):
        """
        Start the autonomous agent.
        
        Args:
            computer: Optional computer to pass to the agent
            blocking: If True, run synchronously; if False, run in a thread
            
        Returns:
            The thread if running asynchronously, None if running synchronously
        """
        if self.running:
            return None
        
        branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
        if self.verbose_boot:
            console.print(f"[bold cyan]{branch_prefix}Starting autonomous agent...[/]")
        
        self.running = True
        self.steps_taken = 0
        
        # Store the computer if provided
        if computer:
            self.agent.computer = computer
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold cyan]{branch_prefix}Using provided computer instance[/]")
            
        if blocking:
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold cyan]{branch_prefix}Running in blocking mode[/]")
            self._run_loop()
            return None
        else:
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold cyan]{branch_prefix}Starting agent in separate thread[/]")
            self.thread = threading.Thread(
                target=self._run_loop,
                daemon=True
            )
            self.thread.start()
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold green]{branch_prefix}Agent thread started successfully[/]")
            return self.thread
    
    def stop(self):
        """Stop the autonomous agent."""
        branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
        
        if self.verbose_boot:
            console.print(f"[bold yellow]{branch_prefix}Stopping autonomous agent...[/]")
            
        self.running = False
        
        if self.thread and self.thread.is_alive():
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold yellow]{branch_prefix}Waiting for agent thread to terminate...[/]")
            self.thread.join(timeout=1.0)
            if self.verbose_boot:
                if self.thread.is_alive():
                    branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                    console.print(f"[bold red]{branch_prefix}Thread did not terminate within timeout[/]")
                else:
                    branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                    console.print(f"[bold green]{branch_prefix}Agent thread terminated successfully[/]")
    
    def _custom_print_wrapper(self, original_print_steps):
        """Returns a modified print function that includes branch ID"""
        def wrapped_print_function(message):
            if hasattr(self, 'branch_id') and self.branch_id:
                # Format the branch ID in a more visible way
                branch_color = self._get_branch_color()
                if "(" in message and ")" in message:  # Likely an action or function call
                    # Separate action type and arguments for better visibility
                    action_parts = message.split("(", 1)
                    if len(action_parts) == 2:
                        action_type = action_parts[0]
                        args = "(" + action_parts[1]
                        print(f"\033[1m[BRANCH {self.branch_id}]\033[0m \033[{branch_color}m{action_type}\033[0m{args}")
                        return
                # Default formatting for other messages
                print(f"\033[1m[BRANCH {self.branch_id}]\033[0m {message}")
            else:
                print(message)
        
        # Always return the wrapper when we have a branch_id, even if suppress_original_prints is True
        # This ensures tagged prints are preserved
        if hasattr(self, 'branch_id') and self.branch_id:
            return wrapped_print_function
        return wrapped_print_function if original_print_steps else False
        
    def _get_branch_color(self):
        """Returns a color code based on branch ID for consistent coloring"""
        if not self.branch_id:
            return "0"
        # Extract number from branch ID if possible
        try:
            branch_num = int(self.branch_id.split('-')[1]) if '-' in self.branch_id else 0
            # ANSI color codes (31=red, 32=green, 33=yellow, 34=blue, 35=magenta, 36=cyan)
            colors = ["31", "32", "33", "34", "35", "36"]
            return colors[branch_num % len(colors)]
        except:
            return "0"  # Default color
            
    def _sanitize_for_json(self, data):
        """Sanitize data for JSON serialization, removing or truncating problematic fields."""
        if isinstance(data, list):
            return [self._sanitize_for_json(item) for item in data]
        elif isinstance(data, dict):
            result = {}
            for k, v in data.items():
                # Skip binary data or excessively large fields
                if k == "binary_data" or k == "image_data":
                    result[k] = "<binary data omitted>"
                # Recursively sanitize nested structures
                else:
                    result[k] = self._sanitize_for_json(v)
            return result
        # Handle specific types that might cause JSON serialization issues
        elif isinstance(data, (int, float, str, bool)) or data is None:
            return data
        else:
            # Convert other types to strings
            return str(data)
            
    def _save_trajectory_file(self):
        """Save the trajectory to file."""
        if not hasattr(self, 'trajectory') or not hasattr(self, 'trajectory_file'):
            return
            
        try:
            with open(self.trajectory_file, 'w') as f:
                json.dump(self.trajectory, f, indent=2)
        except Exception as e:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold red]{branch_prefix}Error saving trajectory file: {str(e)}[/]")

    def _record_in_trajectory(self, action_type: str, data: Dict[str, Any], conversation_id: Optional[str] = None):
        """Record an action in the trajectory file."""
        if not hasattr(self, 'trajectory') or not hasattr(self, 'trajectory_file'):
            return
            
        try:
            # Prepare action data with timestamp
            action = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "type": action_type,
            }
            
            # Add conversation ID if provided
            if conversation_id:
                action["conversation_id"] = conversation_id
                
            # Add all other data
            action.update(data)
            
            # Append to actions list
            self.trajectory["actions"].append(action)
            
            # Save to file every 5 actions to reduce I/O
            if len(self.trajectory["actions"]) % 5 == 0:
                self._save_trajectory_file()
        except Exception as e:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold red]{branch_prefix}Error recording trajectory: {str(e)}[/]")
    
    def _record_interaction(self, interaction_type: str, data: Dict[str, Any]):
        """Record an API interaction in the trajectory file."""
        if not hasattr(self, 'trajectory') or not hasattr(self, 'trajectory_file'):
            return
            
        try:
            # Prepare interaction data with timestamp
            interaction = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "type": interaction_type,
            }
                
            # Add all other data
            interaction.update(data)
            
            # Append to interactions list
            self.trajectory["interactions"].append(interaction)
            
            # Save to file every 2 interactions or if this is a response
            if interaction_type == "response" or len(self.trajectory["interactions"]) % 2 == 0:
                self._save_trajectory_file()
        except Exception as e:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold red]{branch_prefix}Error recording interaction: {str(e)}[/]")
            
    def _run_loop(self):
        """Main execution loop for the autonomous agent."""
        # Initialize conversation items
        items = [{"role": "user", "content": self.initial_task}]
        
        # Generate a conversation ID for tracking in the trajectory
        conversation_id = f"conversation_{int(time.time())}"
        
        # Run initial turn
        branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
        
        if not self.suppress_original_prints or self.verbose_boot:
            console.print(Panel(f"[bold blue]Starting task: [/][white]{self.initial_task}[/]", 
                            title=f"{branch_prefix}Initial Task", border_style="blue"))
        
        if self.verbose_boot:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold cyan]{branch_prefix}Initializing agent run loop[/]")
            console.print(f"[bold cyan]{branch_prefix}Initial task length: {len(self.initial_task)} characters[/]")
            
        # Inject branch ID into the agent instance for identification in logs
        if self.branch_id and self.agent:
            self.agent.branch_id = self.branch_id
            if self.verbose_boot:
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold cyan]{branch_prefix}Injected branch ID into agent[/]")
        
        try:
            # Save original print_steps value to handle branch prefixing
            original_print_steps = self.agent.print_steps
            
            # Set our custom print wrapper if we have a branch_id
            if self.branch_id:
                self.agent.print_steps = self._custom_print_wrapper(original_print_steps)
            
            try:
                # Record API request in trajectory interactions list
                if hasattr(self, 'trajectory'):
                    self._record_interaction("request", {
                        "conversation_id": conversation_id,
                        "model": self.agent.model,
                        "items": self._sanitize_for_json(items),
                        "tools": self._sanitize_for_json(self.agent.tools),
                        "truncation": "auto"
                    })
                
                # Create response with retry and exponential backoff
                response = retry_with_exponential_backoff(
                    lambda: create_response(
                        model=self.agent.model,
                        input=items,
                        tools=self.agent.tools,
                        truncation="auto"
                    )
                )
                
                if "output" not in response:
                    branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                    console.print(f"[bold red]{branch_prefix}No output from model[/]")
                    self.running = False
                    return
                
                # Record API response in trajectory interactions list
                if hasattr(self, 'trajectory'):
                    self._record_interaction("response", {
                        "conversation_id": conversation_id,
                        "output": self._sanitize_for_json(response["output"]),
                        "usage": self._sanitize_for_json(response.get("usage", {})),
                        "finish_reason": response.get("finish_reason", None)
                    })
                
                # Add the output to our conversation
                items += response["output"]
                
                # Process each item in the output
                for item in response["output"]:
                    # Check if this is a "done" function call
                    if item.get("type") == "function_call" and item.get("name") == "done":
                        # Extract the done reason
                        args = json.loads(item.get("arguments", "{}"))
                        done_reason = args.get("reason", "Task completed")
                        branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                        console.print(f"[bold blue]{branch_prefix}Agent called 'done' tool: [/][white]{done_reason}[/]")
                        # Mark agent as completed by setting running to False
                        self.running = False
                        # Add a function call output so the model knows it was processed
                        items.append({
                            "type": "function_call_output",
                            "call_id": item.get("call_id", ""),
                            "output": f"Task marked as complete: {done_reason}"
                        })
                    
                    # Process each item through our custom handler
                    new_items = self.autonomous_handle_item(item)
                    items += new_items
            finally:
                # Restore original print_steps value
                self.agent.print_steps = original_print_steps
            
            self.steps_taken += 1
            
            # Extract the last assistant response for callback
            assistant_responses = [item for item in items if item.get("role") == "assistant"]
            if assistant_responses:
                self.last_response = assistant_responses[-1].get("content", "")
            
            # Save to conversation
            self.conversation = items.copy()
            
            # Call callback if provided
            if self.callback:
                self.callback(
                    step=1, 
                    action="initial_task", 
                    response=self.last_response or ""
                )
        except Exception as e:
            import traceback
            # Get full traceback
            tb = traceback.format_exc()
            
            # Display error with traceback
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold red]{branch_prefix}Error in initial task: {str(e)}[/]")
            console.print(f"[bold red]{branch_prefix}Traceback:[/]\n{tb}")
            
            if self.callback:
                self.callback(
                    step=1,
                    action="error",
                    response=f"{str(e)}\n\nTraceback:\n{tb}" or ""
                )
            self.running = False
            return
        
        # Continue with follow-up steps
        branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
        console.print(f"[bold green]{branch_prefix}Starting follow-up steps (max: {self.max_steps})[/]")
        
        while self.running and self.steps_taken < self.max_steps:
            # Add delay between steps
            time.sleep(self.step_delay)
            
            # Check if still running
            if not self.running:
                break
            
            # Create continuation prompt
            continuation = (
                "Continue with the task. Based on what you've done so far, "
                "decide what to do next and take action. Exercise your best judgment. "
                "If you believe you have completed the task, call the 'done' tool "
                "to indicate completion."
            )
            
            # Add continuation to conversation
            items.append({"role": "user", "content": continuation})
            
            # Run the agent
            try:
                # Save original print_steps value to handle branch prefixing
                original_print_steps = self.agent.print_steps
                
                # Set our custom print wrapper if we have a branch_id
                if self.branch_id:
                    self.agent.print_steps = self._custom_print_wrapper(original_print_steps)
                
                try:
                    # Record API request in trajectory interactions list
                    if hasattr(self, 'trajectory'):
                        self._record_interaction("request", {
                            "conversation_id": conversation_id,
                            "model": self.agent.model,
                            "items": self._sanitize_for_json(items),
                            "tools": self._sanitize_for_json(self.agent.tools),
                            "truncation": "auto"
                        })
                    
                    # Create response with retry and exponential backoff
                    response = retry_with_exponential_backoff(
                        lambda: create_response(
                            model=self.agent.model,
                            input=items,
                            tools=self.agent.tools,
                            truncation="auto"
                        )
                    )
                    
                    if "output" not in response:
                        branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                        console.print(f"[bold red]{branch_prefix}No output from model[/]")
                        break
                    
                    # Record API response in trajectory interactions list
                    if hasattr(self, 'trajectory'):
                        self._record_interaction("response", {
                            "conversation_id": conversation_id,
                            "output": self._sanitize_for_json(response["output"]),
                            "usage": self._sanitize_for_json(response.get("usage", {})),
                            "finish_reason": response.get("finish_reason", None)
                        })
                    
                    # Add the output to our conversation
                    items += response["output"]
                    
                    # Process each item in the output
                    for item in response["output"]:
                        # Check if this is a "done" function call
                        if item.get("type") == "function_call" and item.get("name") == "done":
                            # Extract the done reason
                            args = json.loads(item.get("arguments", "{}"))
                            done_reason = args.get("reason", "Task completed")
                            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                            console.print(f"[bold blue]{branch_prefix}Agent called 'done' tool: [/][white]{done_reason}[/]")
                            # Mark agent as completed by setting running to False
                            self.running = False
                            # Add a function call output so the model knows it was processed
                            items.append({
                                "type": "function_call_output",
                                "call_id": item.get("call_id", ""),
                                "output": f"Task marked as complete: {done_reason}"
                            })
                        
                        # Process each item through our custom handler
                        new_items = self.autonomous_handle_item(item)
                        items += new_items
                finally:
                    # Restore original print_steps value
                    self.agent.print_steps = original_print_steps
                
                self.steps_taken += 1
                
                # Extract the last assistant response for callback
                assistant_responses = [item for item in items if item.get("role") == "assistant"]
                if assistant_responses:
                    self.last_response = assistant_responses[-1].get("content", "")
                
                # Save to conversation
                self.conversation = items.copy()
                
                # Call callback if provided
                if self.callback:
                    self.callback(
                        step=self.steps_taken,
                        action="continuation",
                        response=self.last_response or ""
                    )
                
                # Progress is now mainly shown through the callback
                # We'll leave a minimal debug output that includes the branch ID
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                if self.debug:
                    console.print(f"[dim green]{branch_prefix}Step {self.steps_taken}/{self.max_steps} completed[/]")
                
            except Exception as e:
                import traceback
                # Get full traceback
                tb = traceback.format_exc()
                
                # Display error with traceback
                branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                console.print(f"[bold red]{branch_prefix}Error in continuation: {str(e)}[/]")
                console.print(f"[bold red]{branch_prefix}Traceback:[/]\n{tb}")
                
                # Call callback with error including traceback
                if self.callback:
                    self.callback(
                        step=self.steps_taken,
                        action="error",
                        response=f"{str(e)}\n\nTraceback:\n{tb}" or ""
                    )
                break
                
        # If we've reached the max steps, show completion message
        if self.steps_taken >= self.max_steps:
            branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
            console.print(f"[bold yellow]{branch_prefix}Reached maximum {self.max_steps} steps (agent did not call 'done')[/]")
        
        self.running = False
    
    def set_debug(self, debug=True):
        """Set debug mode for both the autonomous agent and underlying agent."""
        self.debug = debug
        self.agent.debug = debug
        
    def set_show_images(self, show_images=True):
        """Set show_images mode for both the autonomous agent and underlying agent."""
        self.show_images = show_images
        self.agent.show_images = show_images
        
    def autonomous_handle_item(self, item):
        """Handle each item with additional printing capabilities for autonomous agent."""
        # Handle printing for keypresses and screenshots
        if item.get("type") == "computer_call":
            action = item["action"]
            action_type = action["type"]
            action_args = {k: v for k, v in action.items() if k != "type"}
            
            # Always print tagged messages, even if suppress_original_prints is True
            if hasattr(self, 'branch_id') and self.branch_id:
                branch_color = self._get_branch_color()
                print(f"\033[1m[BRANCH {self.branch_id}]\033[0m \033[{branch_color}m{action_type}\033[0m({action_args})")
            elif self.agent.print_steps:
                # Only print untagged messages if print_steps is True
                print(f"{action_type}({action_args})")
            
            # Get screenshot after action
            if hasattr(self.agent.computer, "screenshot"):
                screenshot_base64 = self.agent.computer.screenshot()
                if self.show_images:
                    show_image(screenshot_base64)
                
                # Save screenshot to file
                if hasattr(self, 'screenshots_folder'):
                    screenshot_name = f"screenshot_{self.screenshot_counter}.png"
                    screenshot_file = os.path.join(self.screenshots_folder, screenshot_name)
                    with open(screenshot_file, 'wb') as f:
                        f.write(base64.b64decode(screenshot_base64))
                    self.screenshot_counter += 1
            
            # Record action in trajectory
            if hasattr(self, 'trajectory'):
                action_data = {
                    "type": action_type,
                    "args": action_args,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Add screenshot name for any action that triggered a screenshot
                if hasattr(self, 'screenshots_folder') and hasattr(self.agent.computer, "screenshot"):
                    action_data["screenshot_name"] = f"screenshot_{self.screenshot_counter-1}.png"
                
                self.trajectory["actions"].append(action_data)
                try:
                    with open(self.trajectory_file, 'w') as f:
                        json.dump(self.trajectory, f, indent=2)
                except Exception as e:
                    branch_prefix = f"[{self.branch_id}] " if self.branch_id else ""
                    console.print(f"[bold red]{branch_prefix}Error saving trajectory: {str(e)}[/]")
        
        # Delegate to the base agent's handle_item method
        return self.agent.handle_item(item)
        
    def get_result(self):
        """Get the current state and results of the agent."""
        return {
            "steps_taken": self.steps_taken,
            "last_response": self.last_response,
            "conversation": self.conversation,
            "running": self.running
        }