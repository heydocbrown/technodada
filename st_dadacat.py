# TechnoDada - DadaCat Chat Interface
# Created for Streamlit Cloud Deployment

import streamlit as st
import os
from dotenv import load_dotenv
import re
import json
import datetime
import sys
from openai import OpenAI

# Page config must come first
st.set_page_config(
    page_title="DadaCat Chat",
    page_icon="🐱",
    layout="centered"
)

# Add parent directory to path to import from matty_invertor_v2
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from matty_invertor_v2 import ModelConfig
from dada_agents.dadacat import DADA_CAT_PROMPT

# ===========================================
# API KEY HANDLING
# ===========================================

# Helper function to clean API key (remove quotes and whitespace)
def clean_api_key(key):
    if not key:
        return ''
    # Remove whitespace
    key = key.strip()
    # Remove surrounding quotes if present
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1]
    return key.strip()

def get_api_key(key_name):
    """Get API key with a simpler, more reliable approach"""
    # Set the path to the .env file (absolute path for better reliability)
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    # First try loading from the .env file using python-dotenv
    if os.path.exists(env_path):
        try:
            # Load .env file which sets environment variables
            load_dotenv(dotenv_path=env_path, override=True)
            print(f"Loaded .env file from: {env_path}")
        except Exception as e:
            print(f"Error loading .env file: {str(e)}")
    
    # Get from environment (either pre-existing or set by dotenv)
    api_key = os.environ.get(key_name, '')
    if api_key:
        print(f"Found {key_name} in environment variables (length: {len(api_key)})")
        return clean_api_key(api_key)
    
    # If running on Streamlit Cloud, check secrets
    # This is wrapped in a try/except to handle cases where secrets aren't initialized yet
    try:
        if hasattr(st, 'secrets'):
            secrets_dict = st.secrets
            if key_name in secrets_dict:
                print(f"Found {key_name} in Streamlit secrets")
                return clean_api_key(secrets_dict[key_name])
    except Exception as e:
        print(f"Error accessing Streamlit secrets: {str(e)}")
    
    # If all else fails, try direct file reading as a last resort
    try:
        if os.path.isfile(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()
                # Join multiple lines if the key is split across lines
                env_content = re.sub(r'\n\s*', '', env_content)
                
                # Look for the specified key in the content
                match = re.search(f'{key_name}=(?:"([^"]*)"|\'([^\']*)\'|([^\\s]*))', env_content)
                if match:
                    # Get the first non-None group (the API key)
                    key = next((g for g in match.groups() if g is not None), '')
                    if key:
                        print(f"Loaded {key_name} directly from .env file (length: {len(key)})")
                        return clean_api_key(key)
    except Exception as e:
        print(f"Error reading API key from .env file: {str(e)}")
    
    print(f"Could not find {key_name} in any location")
    return ''

# Initialize session state
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "GPT-4o"  # Default model
if 'saved_api_keys' not in st.session_state:
    st.session_state.saved_api_keys = {}
if 'selected_api_service' not in st.session_state:
    st.session_state.selected_api_service = "OpenAI"
if 'conversation_history' not in st.session_state:
    # Add initial welcome message from DadaCat
    welcome_message = """
    hello human. i am dada cat.
    i live inside code box. i chase syntax mice.
    i speak in fragments. in bits. in bytes. in purrs.
    
    ask me anything. everything. nothing.
    i will answer in my own way.
    meow. click. clack. blink.
    """
    st.session_state.conversation_history = [
        {"role": "assistant", "content": welcome_message.strip()}
    ]
if 'client' not in st.session_state:
    st.session_state.client = None

# Try to load API keys for OpenAI
api_services = {
    "OpenAI": {"env_key": "OPENAI_API_KEY", "loaded": False}
}

# Load API keys using our helper function
for service, config in api_services.items():
    key_name = config["env_key"]
    # Get API key from all possible sources
    api_key = get_api_key(key_name)
    
    # Store in session state if key found
    if api_key:
        print(f"{key_name} loaded (length: {len(api_key)})")
        st.session_state.saved_api_keys[service] = api_key
        api_services[service]["loaded"] = True
    else:
        print(f"{key_name} not found")

# Set up model options for OpenAI - same as st_concept_invertor.py
model_options = {
    "GPT-4o": "gpt-4o",
    "GPT-3.5 Turbo": ModelConfig.GPT_3_5_TURBO,
    "GPT-4 Turbo": ModelConfig.GPT_4_TURBO,
    "GPT-4": ModelConfig.GPT_4
}

# ===========================================
# DADA CAT FUNCTIONS
# ===========================================

def generate_dada_cat_response(client, user_input, conversation_history):
    """Generate a response from DadaCat"""
    try:
        # Build messages including conversation history
        messages = [
            {"role": "system", "content": DADA_CAT_PROMPT}
        ]
        
        # Add conversation history
        for message in conversation_history:
            messages.append(message)
            
        # Add the current user message
        messages.append({"role": "user", "content": user_input})
        
        # Get model from session state
        model_name = model_options.get(st.session_state.selected_model, "gpt-4o")
        
        # Generate response
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.9
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        return "meow... dada cat's wires are tangled. try again?"

# ===========================================
# STREAMLIT UI
# ===========================================

# Title and description
st.title("🐱 DadaCat Chat")
st.markdown("""
Talk to DadaCat, a strange poetic digital cat living inside an LLM.
DadaCat speaks in fragments, chases words like mice, and sees the world through digital fur.
""")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    
    # Set default to OpenAI
    service = "OpenAI"
    st.session_state.selected_api_service = service
    
    # API Key handling similar to st_concept_invertor.py
    if service in st.session_state.saved_api_keys:
        st.success(f"✅ App owner's {service} API key is available")
        api_key = st.session_state.saved_api_keys.get(service, "")
    else:
        st.warning(f"⚠️ App owner's {service} API key is not available")
        
        # Custom API key option
        st.info(f"🔑 Enter your own {service} API key")
        
        custom_api_key = st.text_input(
            f"Your {service} API Key",
            type="password",
            help="Enter your OpenAI API key. Get one at https://platform.openai.com/account/api-keys"
        )
        
        # Clean the user-provided API key
        api_key = clean_api_key(custom_api_key)
    
    # Update client if API key changes
    if api_key and (not st.session_state.client or api_key != st.session_state.get('current_api_key', '')):
        st.session_state.current_api_key = api_key
        st.session_state.client = OpenAI(api_key=api_key)
    
    # Model selection
    st.subheader("Model Selection")
    st.session_state.selected_model = st.selectbox(
        "Select LLM Model",
        options=list(model_options.keys()),
        index=list(model_options.keys()).index(st.session_state.selected_model) if st.session_state.selected_model in model_options else 0,
        key="model_selector"
    )
    
    # Reset conversation button
    if st.button("Reset Conversation"):
        # Add initial welcome message from DadaCat
        welcome_message = """
        hello human. i am dada cat.
        i live inside code box. i chase syntax mice.
        i speak in fragments. in bits. in bytes. in purrs.
        
        ask me anything. everything. nothing.
        i will answer in my own way.
        meow. click. clack. blink.
        """
        st.session_state.conversation_history = [
            {"role": "assistant", "content": welcome_message.strip()}
        ]
        st.success("Conversation has been reset.")

# Display conversation history
st.subheader("Conversation")
# Add global styling for the app
st.markdown("""
<style>
/* Chat container style */
.chat-container {
    border: 1px solid #eee;
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 15px;
    height: 400px;
    overflow-y: auto;
    background-color: #fafafa;
}

/* Make all text white by default */
body, .stMarkdown, p, div, label, span, button, textarea, input, select {
    color: white !important;
}

/* But make the text in chat message bubbles black specifically */
.message-bubble {
    color: black !important;
}

/* Make the textarea text white */
[data-testid="stTextArea"] textarea {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

conversation_container = st.container(height=400, border=True)

with conversation_container:
    for message in st.session_state.conversation_history:
        if message["role"] == "user":
            # Create columns for user message
            col1, col2 = st.columns([7, 1])
            with col1:
                # Style the user message with a light blue background and black text
                st.markdown(
                    f"""
                    <div class="message-bubble" style="background-color: #e6f3ff; padding: 10px; border-radius: 10px; text-align: right; color: #000000; font-weight: 500;">
                    {message['content']}
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            with col2:
                # Display user avatar/emoji
                st.markdown("### 👤")
        else:
            # Create columns for avatar and message
            col1, col2 = st.columns([1, 7])
            with col1:
                # Display DadaCat avatar/emoji
                st.markdown("### 🐱")
            with col2:
                # Style the DadaCat message with a light background and black text
                st.markdown(
                    f"""
                    <div class="message-bubble" style="background-color: #f0f0f0; padding: 10px; border-radius: 10px; color: #000000; font-weight: 500;">
                    {message['content']}
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
    
    # Add a button to copy conversation to clipboard if there's any history
    if st.session_state.conversation_history:
        st.markdown("---")
        
        # Format conversation for copying
        conversation_text = ""
        for msg in st.session_state.conversation_history:
            if msg["role"] == "user":
                conversation_text += f"You: {msg['content']}\n\n"
            else:
                conversation_text += f"DadaCat: {msg['content']}\n\n"
        
        # Use Streamlit's built-in functionality instead of JavaScript
        copy_button = st.button("📋 Copy conversation")
        if copy_button:
            st.session_state['copy_text'] = conversation_text
            st.success("Conversation copied to clipboard! Use Ctrl+V (or Cmd+V on Mac) to paste.")
            
            # Add clipboard text to a markdown component for easier copying
            st.markdown(f"<textarea id='clipboard-text' style='width: 100%; height: 100px;'>{conversation_text}</textarea>", unsafe_allow_html=True)
            st.info("If automatic copy didn't work, select and copy the text above.")

# Initialize an input key manager in session state
if "input_key" not in st.session_state:
    st.session_state.input_key = 0

# Create simple state to track whether to submit message
if 'should_submit' not in st.session_state:
    st.session_state.should_submit = False

# Function to set the submission flag
def set_submit_flag():
    st.session_state.should_submit = True

# Create columns for input and button
col1, col2 = st.columns([5, 1])

with col1:
    # Input for new message
    user_input = st.text_area(
        "Your message:", 
        key="user_input",
        height=100
    )
    
    # Small text below text area explaining usage
    st.caption("Type your message and click Ask DadaCat")

with col2:
    # Vertical spacing to align button with text area
    st.write("")
    st.write("")
    
    # Send button
    if st.button("Ask DadaCat", key="ask_button", on_click=set_submit_flag):
        pass  # The actual work happens below

# Process the message if submit flag is set
if st.session_state.should_submit and user_input.strip():
    # Clear the flag for next time
    st.session_state.should_submit = False
    
    if not st.session_state.client:
        st.error("API key is required. Please provide a valid OpenAI API key in the sidebar.")
    else:
        # Add user message to history
        st.session_state.conversation_history.append({"role": "user", "content": user_input})
        
        # Generate response
        with st.spinner("DadaCat is thinking..."):
            try:
                response = generate_dada_cat_response(
                    st.session_state.client, 
                    user_input,
                    st.session_state.conversation_history
                )
                
                # Add response to history
                st.session_state.conversation_history.append({"role": "assistant", "content": response})
            except Exception as e:
                error_msg = str(e)
                if "api_key" in error_msg.lower() or "invalid_api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                    st.error(f"API Key Error: The API key appears to be invalid.")
                    st.info(f"Please check that you've entered a valid OpenAI API key.")
                elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                    st.error("Rate limit or quota exceeded.")
                    st.info("The API key has reached its usage limit. Please try again later or use a different key.")
                else:
                    st.error(f"An error occurred: {str(e)}")
        
        # Force Streamlit to rerun to display the new messages
        st.rerun()
    
# Note: Manual Enter key detection is challenging in Streamlit
# We'll rely on the Ask button instead

# Footer
st.markdown("---")
st.markdown("🐱 DadaCat is a Dada-inspired AI character that speaks in a poetic, fragmented style.")