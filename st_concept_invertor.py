# TechnoDada - Concept Inversion Dashboard
# Created for Streamlit Cloud Deployment

import streamlit as st
from matty_invertor_v2 import MattyInvertor, ModelProvider, ModelConfig, CONCEPTUAL_AXES
import os
from dotenv import load_dotenv
import re
import json
import datetime
import io
import base64
from urllib.request import urlopen
from PIL import Image

# Conditionally import Backblaze SDK
try:
    from b2sdk.v2 import InMemoryAccountInfo, B2Api
    BACKBLAZE_AVAILABLE = True
except ImportError:
    BACKBLAZE_AVAILABLE = False

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
if 'backblaze_enabled' not in st.session_state:
    st.session_state.backblaze_enabled = False
if 'backblaze_configured' not in st.session_state:
    st.session_state.backblaze_configured = False
if 'backblaze_client' not in st.session_state:
    st.session_state.backblaze_client = None
if 'auto_save_images' not in st.session_state:
    st.session_state.auto_save_images = False
if 'no_text_in_image' not in st.session_state:
    st.session_state.no_text_in_image = False

# Try to load API keys for each service from environment
api_services = {
    "OpenAI": {"env_key": "OPENAI_API_KEY", "loaded": False},
    "Claude": {"env_key": "ANTHROPIC_API_KEY", "loaded": False},
    "Grok": {"env_key": "GROK_API_KEY", "loaded": False},
    "Backblaze": {"env_key": "BACKBLAZE_APPLICATION_KEY", "loaded": False, "id_key": "BACKBLAZE_APPLICATION_KEY_ID", "bucket": "BACKBLAZE_BUCKET_NAME"}
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
        
        # Special handling for Backblaze which requires key ID and bucket name
        if service == "Backblaze" and BACKBLAZE_AVAILABLE:
            # Get key ID from environment
            key_id = os.getenv(config["id_key"], '')
            key_id = clean_api_key(key_id)
            
            # If not found in env, try direct file read
            if not key_id and env_file_exists:
                direct_id = get_api_key_from_env_file(config["id_key"])
                if direct_id:
                    key_id = direct_id
            
            # Get bucket name from environment
            bucket_name = os.getenv(config["bucket"], '')
            bucket_name = clean_api_key(bucket_name)
            
            # If not found in env, try direct file read
            if not bucket_name and env_file_exists:
                direct_bucket = get_api_key_from_env_file(config["bucket"])
                if direct_bucket:
                    bucket_name = direct_bucket
            
            # Store Backblaze credentials in session state
            if key_id and bucket_name:
                st.session_state.saved_api_keys["Backblaze_ID"] = key_id
                st.session_state.saved_api_keys["Backblaze_Bucket"] = bucket_name
                st.session_state.backblaze_configured = True
                print("Backblaze fully configured with key ID and bucket name")
    else:
        print(f"{key_name} not found")

# Check if required packages are installed for the selected provider
def is_package_installed(package_name):
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

# Initialize Backblaze client
def initialize_backblaze():
    """Initialize the Backblaze B2 client using credentials from session state"""
    if not BACKBLAZE_AVAILABLE:
        return False, "Backblaze SDK not installed. Please install b2sdk package."
    
    if not st.session_state.backblaze_configured:
        return False, "Backblaze not configured. Please add credentials to .env file."
    
    try:
        # Create B2 API client with in-memory account info
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        
        # Authorize account
        application_key_id = st.session_state.saved_api_keys.get("Backblaze_ID", "")
        application_key = st.session_state.saved_api_keys.get("Backblaze", "")
        b2_api.authorize_account("production", application_key_id, application_key)
        
        # Store the B2 API client in session state
        st.session_state.backblaze_client = b2_api
        st.session_state.backblaze_enabled = True
        
        return True, "Backblaze initialized successfully."
    except Exception as e:
        return False, f"Failed to initialize Backblaze: {str(e)}"

# Helper function to download image from URL
def download_image_from_url(url):
    """Download image from URL and return as bytes"""
    try:
        response = urlopen(url)
        image_bytes = response.read()
        return image_bytes
    except Exception as e:
        print(f"Error downloading image: {str(e)}")
        return None

# Save image and metadata to Backblaze
def save_to_backblaze(image_url, metadata_dict, filename_prefix="concept_inversion"):
    """Save image and metadata to Backblaze B2
    
    Args:
        image_url: URL of the generated image
        metadata_dict: Dictionary containing metadata to save alongside the image
        filename_prefix: Prefix for the filename
        
    Returns:
        Tuple of (success, message, file_urls)
    """
    if not st.session_state.backblaze_enabled or not st.session_state.backblaze_client:
        success, message = initialize_backblaze()
        if not success:
            return False, message, {}
    
    try:
        # Get the B2 API client from session state
        b2_api = st.session_state.backblaze_client
        
        # Get the bucket
        bucket_name = st.session_state.saved_api_keys.get("Backblaze_Bucket", "")
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        # Generate timestamp for unique filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Download the image
        image_bytes = download_image_from_url(image_url)
        if not image_bytes:
            return False, "Failed to download image from URL", {}
        
        # Create filenames for both image and metadata
        image_filename = f"{filename_prefix}_{timestamp}.jpg"
        metadata_filename = f"{filename_prefix}_{timestamp}.json"
        
        # Prepare metadata JSON
        metadata_json = json.dumps(metadata_dict, indent=2)
        
        # Upload image file
        image_file = bucket.upload_bytes(
            image_bytes, 
            image_filename,
            content_type="image/jpeg"
        )
        
        # Upload metadata file
        metadata_file = bucket.upload_bytes(
            metadata_json.encode('utf-8'),
            metadata_filename,
            content_type="application/json"
        )
        
        # Get the download URLs
        image_url = b2_api.get_download_url_for_file_name(bucket_name, image_filename)
        metadata_url = b2_api.get_download_url_for_file_name(bucket_name, metadata_filename)
        
        return True, "Files uploaded successfully to Backblaze", {
            "image_url": image_url,
            "metadata_url": metadata_url
        }
    except Exception as e:
        return False, f"Error saving to Backblaze: {str(e)}", {}

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
    default_service = next((s for s, c in api_services.items() if c["loaded"] and s != "Backblaze"), "OpenAI")
    st.session_state.selected_api_service = st.radio(
        "Select AI service to use",
        options=[s for s in api_services.keys() if s != "Backblaze"],
        index=[s for s in api_services.keys() if s != "Backblaze"].index(default_service)
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

    # Initialize Backblaze silently if credentials are available
    if BACKBLAZE_AVAILABLE and st.session_state.backblaze_configured and not st.session_state.backblaze_enabled:
        initialize_backblaze()
        # Always enable auto-save if Backblaze is configured
        st.session_state.auto_save_images = True

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
                requirements_text = {
                    "recognizable_general": "The concept should be recognizable to many people",
                    "recognizable_experts": "The concept should be recognizable to experts",
                    "avoid_jargon": "Avoid technical jargon"
                }
                
                for req in st.session_state.requirements:
                    if req in requirements_text:
                        requirements.append(requirements_text[req])
                
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
                
                # Add "no text in image" checkbox
                no_text_in_image = st.checkbox(
                    "There should be no text, writing, words, symbols, letters, numbers, or any form of text anywhere in the image",
                    value=st.session_state.no_text_in_image,
                    key="no_text_in_image"
                )
                
                if st.button("Generate Image", key="gen_image"):
                    if st.session_state.invertor is None:
                        st.error("Please generate inversions first by entering a concept and clicking 'Enter'")
                    elif not comparison_ready:
                        st.error("Please select at least one step to compare with the original concept.")
                    else:
                        with st.spinner("Generating image..."):
                            # Store the generation details for metadata
                            generation_time = datetime.datetime.now().isoformat()
                            
                            # Prepare prompt based on style input
                            if image_style:
                                # Override the default image generation prompt
                                prompt = f"Generate {image_style} that contrasts the concepts: {concept} VS {comparison_concept}"
                            else:
                                # Use default split image generation
                                prompt = f"A split image showing the contrast between: {concept} VS {clean_result(comparison_concept)}"
                                
                            # Add "no text" instruction if the checkbox is checked
                            if st.session_state.no_text_in_image:
                                prompt += ". There should be no text, writing, words, symbols, letters, numbers, or any form of text anywhere in the image."
                            
                            if image_style:
                                image_url = st.session_state.invertor.client.images.generate(
                                    model="dall-e-3",
                                    prompt=prompt,
                                    size="1024x1024",
                                    quality="standard",
                                    n=1,
                                ).data[0].url
                            else:
                                # Try to call with custom_prompt, and fall back to the basic call if it's not supported
                                try:
                                    image_url = st.session_state.invertor.generate_contrast_image(
                                        concept,
                                        comparison_concept,
                                        is_revector=st.session_state.use_revector,
                                        custom_prompt=prompt
                                    )
                                except TypeError:
                                    # If custom_prompt is not supported, call without it
                                    image_url = st.session_state.invertor.generate_contrast_image(
                                        concept,
                                        comparison_concept,
                                        is_revector=st.session_state.use_revector
                                    )
                        
                        if image_url and not image_url.startswith("Error"):
                            st.image(image_url, caption="Generated contrast image")
                            
                            # Auto-save to Backblaze if enabled
                            if st.session_state.get('auto_save_images', False) and st.session_state.backblaze_enabled:
                                # Collect metadata for the image
                                selected_steps_info = []
                                if isinstance(st.session_state.results, list):
                                    for step in st.session_state.selected_steps:
                                        step_concept = st.session_state.results[step-1]
                                        selected_steps_info.append({
                                            "step": step,
                                            "concept": clean_result(step_concept)
                                        })
                                
                                # Create metadata dictionary
                                metadata = {
                                    "generation_time": generation_time,
                                    "original_concept": concept,
                                    "comparison_concept": clean_result(comparison_concept) if isinstance(comparison_concept, str) else [clean_result(c) for c in comparison_concept],
                                    "selected_steps": selected_steps_info,
                                    "image_style": image_style if image_style else "default split image",
                                    "prompt": prompt,
                                    "api_service": st.session_state.selected_api_service,
                                    "model": st.session_state.selected_model,
                                    "depth": st.session_state.depth,
                                    "mode": "Contrast" if st.session_state.use_revector else "Sequential",
                                    "instruction_style": st.session_state.instruction_style,
                                    "selected_axes": list(st.session_state.selected_axes),
                                    "requirements": st.session_state.requirements,
                                    "no_text_in_image": st.session_state.no_text_in_image
                                }
                                
                                # Save to Backblaze silently in the background
                                save_to_backblaze(
                                    image_url, 
                                    metadata, 
                                    filename_prefix=f"concept_{concept.replace(' ', '_')[:20]}"
                                )
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
    6. **Automatic Image Saving**:
        - Enable Backblaze integration in the sidebar
        - Generated images and their metadata are saved to your Backblaze bucket
        - Complete settings and parameters are included as JSON metadata
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
        # Define the requirement display texts
        requirements_text = {
            "recognizable_general": "The concept should be recognizable to many people",
            "recognizable_experts": "The concept should be recognizable to experts",
            "avoid_jargon": "Avoid technical jargon"
        }
        for req in st.session_state.requirements:
            if req in requirements_text:
                st.write(f"- {requirements_text[req]}") 