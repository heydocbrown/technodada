# TechnoDada - Concept Inversion Dashboard
# Created for Streamlit Cloud Deployment

import streamlit as st
from matty_invertor_v2 import MattyInvertor, ModelProvider, ModelConfig, CONCEPTUAL_AXES
import os
from dotenv import load_dotenv
import re

# Load environment variables with explicit parameters
load_dotenv(dotenv_path='.env', override=True)

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

# Try to load API keys directly from file if environment variable loading fails
def get_api_key_from_env_file(key_name='OPENAI_API_KEY'):
    try:
        if os.path.isfile('.env'):
            with open('.env', 'r') as f:
                env_content = f.read()
                # Join multiple lines if the key is split across lines
                env_content = re.sub(r'\n\s*', '', env_content)
                
                # Look for the specified key in the content
                match = re.search(f'{key_name}=(?:"([^"]*)"|\'([^\']*)\'|([^\s]*))', env_content)
                if match:
                    # Get the first non-None group (the API key)
                    key = next((g for g in match.groups() if g is not None), '')
                    return key.strip()
    except Exception as e:
        print(f"Error reading API key from .env file: {str(e)}")
    return None

# Check if .env file exists
env_file_exists = os.path.isfile('.env')

# Initialize session state
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "GPT-3.5 Turbo"
if 'use_revector' not in st.session_state:
    st.session_state.use_revector = False
if 'depth' not in st.session_state:
    st.session_state.depth = 3
if 'selected_axes' not in st.session_state:
    st.session_state.selected_axes = list(CONCEPTUAL_AXES.keys())
if 'custom_axes' not in st.session_state:
    st.session_state.custom_axes = {}
if 'instruction_style' not in st.session_state:
    st.session_state.instruction_style = "Default"
if 'requirements' not in st.session_state:
    st.session_state.requirements = []
if 'results' not in st.session_state:
    st.session_state.results = None
if 'invertor' not in st.session_state:
    st.session_state.invertor = None
if 'saved_api_keys' not in st.session_state:
    st.session_state.saved_api_keys = {}
if 'selected_api_service' not in st.session_state:
    st.session_state.selected_api_service = "OpenAI"
if 'selected_steps' not in st.session_state:
    st.session_state.selected_steps = []

# Try to load API keys for each service from environment
api_services = {
    "OpenAI": {"env_key": "OPENAI_API_KEY", "loaded": False},
    "Claude": {"env_key": "ANTHROPIC_API_KEY", "loaded": False},
    "Grok": {"env_key": "GROK_API_KEY", "loaded": False}
}

# Load API keys from environment or direct file read
for service, config in api_services.items():
    key_name = config["env_key"]
    # Get key from environment
    env_api_key = os.getenv(key_name, '')
    env_api_key = clean_api_key(env_api_key)
    
    # If not found in env, try direct file read
    if not env_api_key and env_file_exists:
        direct_key = get_api_key_from_env_file(key_name)
        if direct_key:
            env_api_key = direct_key
            print(f"{key_name} loaded directly from .env file")
    
    # Store in session state if key found
    if env_api_key:
        print(f"{key_name} loaded (length: {len(env_api_key)})")
        st.session_state.saved_api_keys[service] = env_api_key
        api_services[service]["loaded"] = True
    else:
        print(f"{key_name} not found")

# Check if required packages are installed for the selected provider
def is_package_installed(package_name):
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

# Page config
st.set_page_config(
    page_title="Concept Invertor Dashboard",
    page_icon="🔄",
    layout="wide"
)

# Title and description
st.title("Concept Invertor Dashboard")
st.markdown("""
This dashboard allows you to explore concept inversion using different LLM models.
Input a concept and see how it transforms through various axes of meaning.

*Note: This app uses various AI APIs. You can use your own API key by selecting the option in the sidebar.*
""")

# Sidebar controls
with st.sidebar:
    st.header("Configuration")
    
    # API Service selection
    st.subheader("Select API Service")
    
    # Display available API services - default to the first one with a valid key
    default_service = next((s for s, c in api_services.items() if c["loaded"]), "OpenAI")
    st.session_state.selected_api_service = st.radio(
        "Select AI service to use",
        options=list(api_services.keys()),
        index=list(api_services.keys()).index(default_service)
    )
    
    service = st.session_state.selected_api_service
    
    # Check if required packages are installed for selected service
    if service == "Claude" and not is_package_installed("anthropic"):
        st.warning("⚠️ The 'anthropic' package is required to use Claude models. Please run 'pip install anthropic' and restart the app.")
    elif service == "Grok" and not is_package_installed("xai"):
        st.warning("⚠️ The 'xai' package is required to use Grok models. Please run 'pip install xai-grok' and restart the app.")
    
    # API Key handling with security in mind
    # Show status of owner's API key for selected service
    if service in st.session_state.saved_api_keys:
        st.success(f"✅ App owner's {service} API key is available")
    else:
        st.warning(f"⚠️ App owner's {service} API key is not available")
    
    use_custom_key = st.checkbox(
        "Use your own API key",
        value=service not in st.session_state.saved_api_keys,  # Default to true if owner key not available
        help=f"Check this to use your own {service} API key instead of the app owner's key"
    )
    
    if use_custom_key:
        st.info(f"🔑 Enter your own {service} API key to use instead of the app owner's key.")
        
        # Add debug option in development mode
        show_debug = False
        if os.getenv('STREAMLIT_ENV') == 'development':
            show_debug = st.checkbox("Show API key debug info", value=False)
        
        api_help_texts = {
            "OpenAI": "Enter your OpenAI API key. Get one at https://platform.openai.com/account/api-keys",
            "Claude": "Enter your Anthropic API key. Get one at https://console.anthropic.com/keys. You may need to run 'pip install anthropic' to use Claude models.",
            "Grok": "Enter your Grok API key. Get one from xAI."
        }
        
        custom_api_key = st.text_input(
            f"Your {service} API Key",
            type="password",
            help=api_help_texts.get(service, "Enter your API key")
        )
        
        # Clean the user-provided API key
        custom_api_key = clean_api_key(custom_api_key)
        
        # Show debug info if enabled
        if show_debug and custom_api_key:
            st.write(f"Key length: {len(custom_api_key)}")
            st.write(f"Key starts with: {custom_api_key[:7]}...")
        
        # Use custom key
        api_key = custom_api_key
    else:
        # Use owner's saved key from session state
        api_key = st.session_state.saved_api_keys.get(service, "")
    
    # Model selection - dynamic based on selected API service
    model_options = {}
    if service == "OpenAI":
        model_options = {
            "GPT-3.5 Turbo": ModelConfig.GPT_3_5_TURBO,
            "GPT-4 Turbo": ModelConfig.GPT_4_TURBO,
            "GPT-4": ModelConfig.GPT_4
        }
    elif service == "Claude":
        model_options = {
            "Claude 3 Sonnet": ModelConfig.CLAUDE_3_SONNET,
            "Claude 3 Opus": ModelConfig.CLAUDE_3_OPUS
        }
    elif service == "Grok":
        model_options = {
            "Grok-1": ModelConfig.GROK_1
        }
    
    # Reset selected model if switching between providers
    if st.session_state.selected_model not in model_options:
        st.session_state.selected_model = list(model_options.keys())[0]
    
    st.session_state.selected_model = st.selectbox(
        "Select LLM Model",
        options=list(model_options.keys()),
        index=list(model_options.keys()).index(st.session_state.selected_model) if st.session_state.selected_model in model_options else 0,
        key="model_selector"
    )
    
    # Revector toggle
    st.session_state.use_revector = st.checkbox(
        "Contrast with all prior levels (max weird)",
        help="Each iteration considers all previous outputs",
        key="revector_toggle"
    )
    
    # Depth selection (adjusted based on revector)
    max_depth = 5 if st.session_state.use_revector else 10
    st.session_state.depth = st.slider(
        "Recursion Depth",
        min_value=1,
        max_value=max_depth,
        value=st.session_state.depth,
        key="depth_slider"
    )
    
    # Axes selection
    st.subheader("Inversion Axes")
    
    # Pre-defined axes selection
    all_axes = dict(CONCEPTUAL_AXES)
    all_axes.update(st.session_state.custom_axes)
    
    # Save current selection before rendering checkboxes
    current_axes = list(st.session_state.selected_axes)
    st.session_state.selected_axes = []
    
    for axis, description in all_axes.items():
        if st.checkbox(
            f"{axis.replace('_', ' ').title()} ({description})",
            value=axis in current_axes,
            key=f"axis_{axis}"
        ):
            st.session_state.selected_axes.append(axis)
    
    # Custom axes input
    st.subheader("Add Custom Axis")
    col_name, col_desc = st.columns(2)
    with col_name:
        new_axis_name = st.text_input("Axis Name", key="new_axis_name", placeholder="e.g., philosophical")
    with col_desc:
        new_axis_desc = st.text_input("Description", key="new_axis_desc", placeholder="e.g., different philosophical tradition")
    
    col_add, col_reset = st.columns(2)
    with col_add:
        if st.button("Add Axis"):
            if new_axis_name and new_axis_desc:
                # Convert to snake_case and add to custom axes
                axis_key = new_axis_name.lower().replace(' ', '_')
                st.session_state.custom_axes[axis_key] = new_axis_desc
                if axis_key not in st.session_state.selected_axes:
                    st.session_state.selected_axes.append(axis_key)
                st.experimental_rerun()
    
    with col_reset:
        if st.button("Reset Axes"):
            st.session_state.custom_axes = {}
            st.session_state.selected_axes = list(CONCEPTUAL_AXES.keys())
            st.experimental_rerun()
    
    # Instruction style selection
    st.subheader("Instruction Style")
    st.session_state.instruction_style = st.radio(
        "Select instruction style",
        options=["Default (max LLM hallucination)", "Concrete (keep it real)"],
        help="Changes how the model is instructed to invert concepts"
    )
    
    # Requirements selection
    st.subheader("Requirements")
    st.markdown("*No requirements selected by default*")
    requirements_options = {
        "recognizable_general": "The concept should be recognizable to many people",
        "recognizable_experts": "The concept should be recognizable to experts",
        "avoid_jargon": "Avoid technical jargon"
    }
    
    selected_requirements = []
    for req_key, req_text in requirements_options.items():
        if st.checkbox(
            req_text,
            value=req_key in st.session_state.requirements,
            key=f"req_{req_key}"
        ):
            selected_requirements.append(req_key)
    
    st.session_state.requirements = selected_requirements

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    # Input concept with Enter button
    col_input, col_button = st.columns([4, 1])
    with col_input:
        concept = st.text_input("Enter your concept:", value="dada", key="concept_input")
    with col_button:
        st.write("")  # Add some spacing
        enter_pressed = st.button("Enter", key="enter_button")
    
    if enter_pressed and concept:
        try:
            # Check if API key is provided
            if not api_key:
                if use_custom_key:
                    st.error(f"Please enter your {service} API key in the sidebar.")
                    st.info(f"You need a {service} API key to use this app.")
                else:
                    st.error(f"App owner's {service} API key is not configured.")
                    st.info(f"Please contact the app owner or use your own {service} API key by checking the box in the sidebar.")
            else:
                # Map API service to provider
                provider_map = {
                    "OpenAI": ModelProvider.OPENAI,
                    "Claude": ModelProvider.ANTHROPIC,  # Now properly set to ANTHROPIC
                    "Grok": ModelProvider.GROK
                }
                
                # Initialize invertor
                invertor = MattyInvertor(
                    provider=provider_map[service],
                    model=model_options[st.session_state.selected_model],
                    api_key=api_key
                )
                st.session_state.invertor = invertor
                
                # Generate inversions
                # Create instruction text based on selected style
                instruction_text = "generate a concept that is maximally orthogonal across these axes"
                if st.session_state.instruction_style == "Concrete (keep it real)":
                    instruction_text = "generate a concept that is maximally different across these axes"
                
                # Create requirements text based on selections
                requirements = []
                req_map = {
                    "recognizable_general": "The concept should be recognizable to many people",
                    "recognizable_experts": "The concept should be recognizable to experts",
                    "avoid_jargon": "Avoid technical jargon"
                }
                
                for req in st.session_state.requirements:
                    if req in req_map:
                        requirements.append(req_map[req])
                
                # Get all axes, including custom ones
                all_axes = dict(CONCEPTUAL_AXES)
                all_axes.update(st.session_state.custom_axes)
                
                # Filter to only selected axes
                selected_axes_dict = {k: v for k, v in all_axes.items() if k in st.session_state.selected_axes}
                
                st.session_state.results = invertor.invert_concept(
                    concept,
                    depth=st.session_state.depth,
                    selected_axes=st.session_state.selected_axes,
                    revector=st.session_state.use_revector,
                    instruction_text=instruction_text,
                    requirements=requirements
                )
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "invalid_api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                if use_custom_key:
                    st.error(f"{service} API Key Error: The key you entered appears to be invalid.")
                    st.info(f"Please check that you've entered a valid {service} API key.")
                else:
                    st.error(f"{service} API Key Error: There's an issue with the app owner's API key.")
                    st.info(f"Please use your own {service} API key by checking the box in the sidebar.")
            elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                st.error("Rate limit or quota exceeded.")
                st.info("The API key has reached its usage limit. Please try again later or use a different key.")
            else:
                # For other errors, show a generic message to avoid exposing sensitive details
                st.error(f"An error occurred during processing.")
                # Show detailed error only in development
                if os.getenv('STREAMLIT_ENV') == 'development':
                    st.error(f"Error details: {error_msg}")
            
            st.session_state.results = None
    
    # Display results if they exist
    if st.session_state.results is not None:
        st.subheader("Inversion Results")
        
        # Helper function to ensure no quotes in display
        def clean_result(result):
            if isinstance(result, str):
                # Remove quotes if they exist
                if (result.startswith('"') and result.endswith('"')) or (result.startswith("'") and result.endswith("'")):
                    return result[1:-1].strip()
            return result
            
        if isinstance(st.session_state.results, str):
            st.write("Step 1:", clean_result(st.session_state.results))
        else:
            for i, result in enumerate(st.session_state.results, 1):
                st.write(f"Step {i}:", clean_result(result))
        
        # Image generation section - only show for providers that support image generation
        image_generation_available = service in ["OpenAI", "Grok"]  # Add others as they're implemented
        
        if image_generation_available:
            st.subheader("Image Generation")
            col_img1, col_img2 = st.columns(2)
            
            with col_img1:
                # Multi-select for steps to compare
                if isinstance(st.session_state.results, list):
                    st.write("Select steps to contrast with original concept:")
                    
                    # Clear previously selected steps that are no longer valid
                    valid_steps = list(range(1, len(st.session_state.results) + 1))
                    st.session_state.selected_steps = [step for step in st.session_state.selected_steps if step in valid_steps]
                    
                    # Create a checkbox for each step
                    selected_steps = []
                    for i, result in enumerate(st.session_state.results, 1):
                        clean_concept = clean_result(result)
                        # Limit concept name length if too long
                        if len(clean_concept) > 30:
                            clean_concept = clean_concept[:27] + "..."
                        
                        if st.checkbox(f"Step {i} - {clean_concept}", 
                                       value=(i in st.session_state.selected_steps),
                                       key=f"select_step_{i}"):
                            selected_steps.append(i)
                    
                    # Update session state with current selections
                    st.session_state.selected_steps = selected_steps
                    
                    if not st.session_state.selected_steps:
                        st.warning("Please select at least one step to compare with the original concept.")
                        comparison_ready = False
                    else:
                        comparison_ready = True
                        # Create a merged concept from all selected steps
                        selected_concepts = [st.session_state.results[i-1] for i in st.session_state.selected_steps]
                        
                        if len(selected_concepts) == 1:
                            comparison_concept = selected_concepts[0]
                            st.info(f"Will contrast original with: Step {st.session_state.selected_steps[0]} - {clean_result(comparison_concept)}")
                        else:
                            # For multiple selections, merge the concepts
                            clean_concepts = [clean_result(c) for c in selected_concepts]
                            comparison_concept = " + ".join(clean_concepts)
                            step_numbers = ", ".join([str(s) for s in st.session_state.selected_steps])
                            st.info(f"Will contrast original with merged concepts from steps: {step_numbers}")
                else:
                    comparison_concept = st.session_state.results
                    comparison_ready = True
                    st.info(f"Will contrast original with: Step 1 - {clean_result(comparison_concept)}")
                
                # Image style selection
                image_style = st.text_input(
                    "Image style (optional)",
                    placeholder="e.g., a fractal image in the style of Escher",
                    help="Leave empty for default split image style",
                    key="style_input"
                )
                
                if st.button("Generate Image", key="gen_image"):
                    if st.session_state.invertor is None:
                        st.error("Please generate inversions first by entering a concept and clicking 'Enter'")
                    elif not comparison_ready:
                        st.error("Please select at least one step to compare with the original concept.")
                    else:
                        with st.spinner("Generating image..."):
                            # Modify the prompt based on style input
                            if image_style:
                                # Override the default image generation prompt
                                prompt = f"Generate {image_style} that contrasts the concepts: {concept} VS {comparison_concept}"
                                image_url = st.session_state.invertor.client.images.generate(
                                    model="dall-e-3",
                                    prompt=prompt,
                                    size="1024x1024",
                                    quality="standard",
                                    n=1,
                                ).data[0].url
                            else:
                                # Use default split image generation
                                image_url = st.session_state.invertor.generate_contrast_image(
                                    concept,
                                    comparison_concept,
                                    is_revector=st.session_state.use_revector
                                )
                        
                        if image_url and not image_url.startswith("Error"):
                            st.image(image_url, caption="Generated contrast image")
                        else:
                            st.error(f"Failed to generate image: {image_url}")
        else:
            st.info(f"Image generation is currently only available with OpenAI and Grok. You're using {service}.")

with col2:
    # Help section
    st.subheader("How to Use")
    st.markdown(f"""
    1. **Select API Service**: Choose between OpenAI, Claude, or Grok
    2. **Select Model**: Choose from available models for the selected service
    3. **Configure Inversion**:
        - Toggle contrast mode (max weird for more creative results)
        - Set recursion depth
        - Select inversion axes
    4. **Enter Concept**: Type your concept and click Enter
    5. **Generate Images** (OpenAI only): 
        - Select one or more steps to compare with the original
        - Select multiple steps to create merged concept comparisons
        - Optionally specify an image style
        - Click Generate Image
    """)
    
    # Display current settings
    st.subheader("Current Settings")
    st.write(f"API Service: {st.session_state.selected_api_service}")
    st.write(f"Model: {st.session_state.selected_model}")
    st.write(f"Depth: {st.session_state.depth}")
    st.write(f"Mode: {'Contrast with all prior levels (max weird)' if st.session_state.use_revector else 'Sequential'}")
    st.write(f"Instruction Style: {st.session_state.instruction_style}")
    st.write("Selected Axes:", ", ".join(st.session_state.selected_axes))
    st.write("Requirements:")
    if not st.session_state.requirements:
        st.write("- None (free generation)")
    else:
        # Define the req_map here to fix the NameError
        req_map = {
            "recognizable_general": "The concept should be recognizable to many people",
            "recognizable_experts": "The concept should be recognizable to experts",
            "avoid_jargon": "Avoid technical jargon"
        }
        for req in st.session_state.requirements:
            if req in req_map:
                st.write(f"- {req_map[req]}") 