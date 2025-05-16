# app.py
import streamlit as st
import streamlit.components.v1 as components

# import webbrowser

# webbrowser.open = lambda *args, **kwargs: None

from agent.branching_agent import BranchingAgent
from computers import (
    BrowserbaseBrowser,
    ScrapybaraBrowser,
    ScrapybaraUbuntu,
    LocalPlaywrightComputer,
    DockerComputer,
    MorphComputer,
)


def load_system_prompt(path: str = "prompts/system_prompt_v0.txt") -> str:
    """Read the system prompt from an external file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"❌ Could not find system prompt at '{path}'")
        st.stop()


SYSTEM_PROMPT = load_system_prompt()

# Map dropdown names → classes
computer_mapping = {
    "morph": MorphComputer,
    "local-playwright": LocalPlaywrightComputer,
    "docker": DockerComputer,
    "browserbase": BrowserbaseBrowser,
    "scrapybara-browser": ScrapybaraBrowser,
    "scrapybara-ubuntu": ScrapybaraUbuntu,
}

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "browser_url" not in st.session_state:
    st.session_state.browser_url = ""
if "environment" not in st.session_state:
    st.session_state.environment = "morph"
if "num_branches" not in st.session_state:
    st.session_state.num_branches = 1


def initialize_agent(task: str):
    ComputerClass = computer_mapping[st.session_state.environment]
    # 2) Spin up the computer WITHOUT launching a real browser
    with ComputerClass() as computer:
        # capture its internal browser URL for embedding
        try:
            st.session_state.browser_url = computer.get_browser_url()
        except Exception:
            st.session_state.browser_url = ""
        agent = BranchingAgent(
            computer=computer,
            agent_kwargs={
                "initial_task": task,
                "system_prompt": SYSTEM_PROMPT,
                "max_steps": 1000,
            },
        )
        st.session_state.agent = agent
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"Agent initialized with task: {task}",
            }
        )
        # run your branches…
        branches = [
            f"branch {i+1}: try a different approach"
            for i in range(st.session_state.num_branches)
        ]
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"Running {st.session_state.num_branches} branches...",  # noqa
            }
        )
        results = agent.run_branches(instructions=branches, context=task)
        st.session_state.messages.append(
            {"role": "assistant", "content": "Branching completed. Results:"}
        )
        for i, res in enumerate(results):
            st.session_state.messages.append(
                {"role": "assistant", "content": f"Branch {i+1}: {res}"}
            )


def process_user_input(user_input: str):
    st.session_state.messages.append({"role": "user", "content": user_input})
    ComputerClass = computer_mapping[st.session_state.environment]
    with ComputerClass() as computer:
        # swap in a fresh computer each turn
        st.session_state.agent.computer = computer
        outputs = st.session_state.agent.run_full_turn(
            [{"role": "user", "content": user_input}],
            print_steps=True,
            show_images=True,
            debug=False,
        )
        # again capture if the computer spun up its UI
        try:
            st.session_state.browser_url = computer.get_browser_url()
        except Exception:
            pass

    for item in outputs:
        if item.get("role") == "assistant":
            st.session_state.messages.append(
                {"role": "assistant", "content": item["content"]}
            )
        if item.get("images"):
            for img in item["images"]:
                if "url" in img:
                    # this covers any screengrabs or image-based nav
                    st.session_state.browser_url = img["url"]
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"Browser navigated to: {img['url']}",
                        }
                    )


# --- Streamlit setup ---
st.set_page_config(page_title="AI Agent", layout="wide")
st.title("AI Agent")

# Sidebar: settings + embedded browser
with st.sidebar:
    st.header("Settings")
    st.session_state.environment = st.selectbox(
        "Environment",
        options=list(computer_mapping.keys()),
        index=list(computer_mapping.keys()).index(st.session_state.environment),  # noqa
    )
    st.session_state.num_branches = st.slider(
        "Number of branches", 1, 5, st.session_state.num_branches
    )
    st.markdown("---")
    st.header("Browser View")
    if st.session_state.browser_url:
        components.iframe(st.session_state.browser_url, height=500)
        st.write(f"URL: {st.session_state.browser_url}")
    else:
        st.write("No browser view yet")

# Main form
with st.form("input_form", clear_on_submit=True):
    user_input = st.text_input(
        "Enter your task or message:", key="latest_input"
    )  # noqa
    submitted = st.form_submit_button("Submit")

if submitted and user_input:
    if st.session_state.agent is None:
        initialize_agent(user_input)
    else:
        process_user_input(user_input)

# Chat log
for msg in st.session_state.messages:
    role = "You" if msg["role"] == "user" else "Agent"
    st.markdown(f"**{role}:** {msg['content']}")

# Virtual desktop (if supported)
st.markdown("---")
st.header("Virtual Computer View")
if st.session_state.agent and hasattr(
    st.session_state.agent.computer, "get_desktop_url"
):
    desktop_url = st.session_state.agent.computer.get_desktop_url()
    components.iframe(desktop_url, height=600)
    st.write(f"Desktop URL: {desktop_url}")
else:
    st.write("Virtual computer view will appear here after initialization")
