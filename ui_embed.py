import streamlit as st
import streamlit.components.v1 as components
from computers import MorphComputer  # assuming MorphComputer is in computers.py


def load_system_prompt(path: str = "prompts/system_prompt_v0.txt") -> str:
    """Read the system prompt from an external file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"❌ Could not find system prompt at '{path}'")
        st.stop()


SYSTEM_PROMPT = load_system_prompt()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "desktop_url" not in st.session_state:
    st.session_state.desktop_url = ""
if "morph_instance" not in st.session_state:
    st.session_state.morph_instance = None
if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "num_branches" not in st.session_state:
    st.session_state.num_branches = 1


def initialize_morph_desktop(task: str):
    try:
        with MorphComputer(auto_open_browser=False) as computer:
            # Grab the URL of the full remote desktop
            desktop_url = computer.get_desktop_url()
            st.session_state.desktop_url = desktop_url
            st.session_state.morph_instance = computer
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"✅ Initialized Morph virtual desktop for task: **{task}**",
                }
            )
            st.session_state.initialized = True
    except Exception as e:
        st.error(f"❌ Failed to initialize Morph desktop: {e}")
        st.stop()


def process_user_input(user_input: str):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": f"💡 (Pretend agent is working on this...)\n\n**Command received**: `{user_input}`",
        }
    )
    # In reality, you'd trigger agent + MorphComputer commands here.


# Page layout
st.set_page_config(page_title="Morph Desktop Viewer", layout="wide")
st.title("🖥️ Morph Virtual Desktop Agent")

# Task input form
with st.form("task_input_form", clear_on_submit=True):
    user_input = st.text_input("Enter your task:")
    submitted = st.form_submit_button("Submit")

if submitted and user_input:
    if not st.session_state.initialized:
        initialize_morph_desktop(user_input)
    else:
        process_user_input(user_input)

# Show chat log
for msg in st.session_state.messages:
    role = "You" if msg["role"] == "user" else "Agent"
    st.markdown(f"**{role}:** {msg['content']}")

# --- Virtual desktop UI embed ---
st.markdown("---")
st.header("🧩 Live Virtual Desktop")

if st.session_state.desktop_url:
    components.iframe(st.session_state.desktop_url, height=600)
    st.write(f"[Open in new tab]({st.session_state.desktop_url})")
else:
    st.info("Morph desktop not initialized yet.")
