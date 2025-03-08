import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO
import base64
import sys
import os
import json
import datetime
import re

# Page config must come first
st.set_page_config(
    page_title="Image Concept Invertor",
    page_icon="🔄",
    layout="wide"
)

# Add parent directory to path to import from matty_invertor_v2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the MattyInvertor class for its parsing functions and other utilities
from matty_invertor_v2.invertor import MattyInvertor, ModelProvider, ModelConfig

# Conditionally import Backblaze SDK
try:
    from b2sdk.v2 import InMemoryAccountInfo, B2Api
    BACKBLAZE_AVAILABLE = True
except ImportError:
    BACKBLAZE_AVAILABLE = False

# ===========================================
# PROMPT ENGINEERING CONFIGURATION
# ===========================================

# System prompts
SYSTEM_CONCEPT_EXTRACTION = "You are an expert at extracting concepts from images and aligning them to conceptual axes."
SYSTEM_CONCEPT_SYNTHESIS = "You are an expert at synthesizing concepts from multidimensional conceptual descriptions."
SYSTEM_CONCEPT_INVERSION = "You are an expert at generating maximally different concepts."
SYSTEM_CONCEPT_SUMMARY = "You are an expert at distilling complex concepts into concise summaries."

# User prompts
PROMPT_EXTRACT_CONCEPTS = "Please describe the core concepts of this image, and break them down into these axes: Semantic, Functional, Causal, Spatial/Temporal, Conceptual/Abstract, Perceptual, Emotional, Technological vs Natural, Scale, Deterministic vs Stochastic."
PROMPT_SYNTHESIZE_CONCEPT = "Given this detailed breakdown of an image across multiple conceptual axes, please create a single unified concept that captures the core meaning and message implied by these axes:\n\n{axes_descriptions}"
PROMPT_INVERT_CONCEPT = "Given this concept: '{concept}', generate a concept that is maximally different across these axes:\n\n{axes_list}"
#PROMPT_SUMMARIZE_CONCEPT = "Given this concept: '{corpus}', generate a concept in {max_words} words or less that is maximally different across all these axes combined:\n\n{description}"

PROMPT_SUMMARIZE_CONCEPT = "Summarize this concept: '{concept}' in as few words as possible and no more than {max_words} words, capturing its essence along these dimensions:\n\n{axes_descriptions}"
PROMPT_GENERATE_IMAGE = "Create a surreal image representing the concept: {concept}"
PROMPT_GENERATE_CONTRAST = "Create an image that visually contrasts these two concepts: '{original_concept}' versus '{inverted_concept}.'"#Show the duality and tension between them in a single unified composition."

# ===========================================
# INITIALIZATION
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

# Initialize session state for API settings
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "GPT-4o"
if 'saved_api_keys' not in st.session_state:
    st.session_state.saved_api_keys = {}
if 'selected_api_service' not in st.session_state:
    st.session_state.selected_api_service = "OpenAI"
if 'backblaze_enabled' not in st.session_state:
    st.session_state.backblaze_enabled = False
if 'backblaze_configured' not in st.session_state:
    st.session_state.backblaze_configured = False
if 'backblaze_client' not in st.session_state:
    st.session_state.backblaze_client = None
if 'auto_save_images' not in st.session_state:
    st.session_state.auto_save_images = False

# Try to load API keys for each service from environment
api_services = {
    "OpenAI": {"env_key": "OPENAI_API_KEY", "loaded": False},
    "Backblaze": {"env_key": "BACKBLAZE_APPLICATION_KEY", "loaded": False, "id_key": "BACKBLAZE_APPLICATION_KEY_ID", "bucket": "BACKBLAZE_BUCKET_NAME"}
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
        
        # Special handling for Backblaze which requires key ID and bucket name
        if service == "Backblaze" and BACKBLAZE_AVAILABLE:
            # Get key ID
            key_id = get_api_key(config["id_key"])
            
            # Get bucket name
            bucket_name = get_api_key(config["bucket"])
            
            # Store Backblaze credentials in session state
            if key_id and bucket_name:
                st.session_state.saved_api_keys["Backblaze_ID"] = key_id
                st.session_state.saved_api_keys["Backblaze_Bucket"] = bucket_name
                st.session_state.backblaze_configured = True
                print("Backblaze fully configured with key ID and bucket name")
    else:
        print(f"{key_name} not found")

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
        response = requests.get(url)
        image_bytes = response.read() if hasattr(response, 'read') else response.content
        return image_bytes
    except Exception as e:
        print(f"Error downloading image: {str(e)}")
        return None

# Save image and metadata to Backblaze
def save_to_backblaze(image_url, metadata_dict, filename_prefix="image_inversion"):
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

# Set up model options for OpenAI - defining this early so it can be used anywhere
model_options = {
    "GPT-4o": "gpt-4o",
    "GPT-4 Turbo": ModelConfig.GPT_4_TURBO,
    "GPT-4": ModelConfig.GPT_4,
    "GPT-3.5 Turbo": ModelConfig.GPT_3_5_TURBO
}

# Get API key for OpenAI
service = "OpenAI"
api_key = st.session_state.saved_api_keys.get(service, "")

# Set up OpenAI client with the API key
if api_key:
    client = OpenAI(api_key=api_key)
    # Also create a MattyInvertor instance for its parsing and utility functions
    # Use the selected model from session state if available
    selected_model = model_options.get(st.session_state.get('selected_model', "GPT-4o"), "gpt-4o")
    matty_invertor = MattyInvertor(provider=ModelProvider.OPENAI, model=selected_model, api_key=api_key)
else:
    client = None
    matty_invertor = None

# Page config is already set at the top of the file

# Use MattyInvertor's improved axes parsing function
def parse_axes(text):
    """Parse axes by using the MattyInvertor implementation."""
    # The parse_axes method expects 'self' as first parameter, so we call it on our matty_invertor instance
    return matty_invertor.parse_axes(text)

# Function to create a concise summary of a concept
def create_concise_summary(client, concept, max_words=10):
    # Use the selected model
    model = model_options.get(st.session_state.selected_model, "gpt-4o")
    
    # Get the selected axes for the summary prompt
    selected_axes = []
    if 'axes_checkboxes' in st.session_state:
        selected_axes = [axis for axis, is_selected in st.session_state.axes_checkboxes.items() if is_selected]
    
    # Format the axes descriptions as a list
    axes_descriptions = ", ".join(selected_axes) if selected_axes else "Semantic, Functional, Conceptual/Abstract"
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_CONCEPT_SUMMARY},
            {"role": "user", "content": PROMPT_SUMMARIZE_CONCEPT.format(
                max_words=max_words, 
                concept=concept, 
                axes_descriptions=axes_descriptions
            )}
        ]
    )
    return response.choices[0].message.content

# ============================================
# PROMPT-ENGINEERED FUNCTIONS
# ============================================

# Extract concepts from an image using prompt engineering
def extract_concepts_from_image(client, image_url):
    # Use the selected model for extraction
    model = model_options.get(st.session_state.selected_model, "gpt-4o")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_CONCEPT_EXTRACTION},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_EXTRACT_CONCEPTS},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    )
    return response.choices[0].message.content

# Combine axes into a single concept using prompt engineering
def combine_axes_into_single_concept(client, axes):
    # Use the selected model
    model = model_options.get(st.session_state.selected_model, "gpt-4o")
    
    # Format the axes descriptions as a list with name and content
    axes_descriptions = "\n".join([f"{axis}: {concept}" for axis, concept in axes.items()])
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_CONCEPT_SYNTHESIS},
            {"role": "user", "content": PROMPT_SYNTHESIZE_CONCEPT.format(axes_descriptions=axes_descriptions)}
        ]
    )
    return response.choices[0].message.content

# Generate an orthogonal concept using prompt engineering
def run_mci1(client, concept):
    # Use the selected model
    model = model_options.get(st.session_state.selected_model, "gpt-4o")
    
    # Get the selected axes from session state
    selected_axes = []
    if 'axes_checkboxes' in st.session_state:
        selected_axes = [axis for axis, is_selected in st.session_state.axes_checkboxes.items() if is_selected]
    
    # If no axes are selected, use default ones
    if not selected_axes:
        selected_axes = ["Semantic", "Functional", "Causal", "Spatial/Temporal", "Conceptual/Abstract"]
    
    # Format the axes list
    axes_list = ", ".join(selected_axes)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_CONCEPT_INVERSION},
            {"role": "user", "content": PROMPT_INVERT_CONCEPT.format(concept=concept, axes_list=axes_list)}
        ]
    )
    return response.choices[0].message.content

# Generate an image from a concept using prompt engineering
def generate_recursive_image(client, concept):
    response = client.images.generate(
        model="dall-e-3",
        prompt=PROMPT_GENERATE_IMAGE.format(concept=concept),
        size="1024x1024",
        n=1
    )
    return response.data[0].url

# ============================================
# HELPER FUNCTIONS
# ============================================

# Helper functions for the Streamlit app
def load_image_from_url(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return img

def get_image_base64_for_api(image_path):
    """Convert image to base64 string for API"""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def save_uploaded_file(uploaded_file):
    """Save uploaded file temporarily and return the path"""
    with open(f"temp_{uploaded_file.name}", "wb") as f:
        f.write(uploaded_file.getbuffer())
    return f"temp_{uploaded_file.name}"

# Main Streamlit app interface
st.title("Image Concept Invertor 🔄")
st.markdown("Upload an image or provide a URL, extract concepts, and generate a new image based on those concepts.")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    
    # Set default to OpenAI
    service = "OpenAI"
    st.session_state.selected_api_service = service
    
    # Model options are already defined at the top level
    
    # Reset selected model if not in options
    if st.session_state.selected_model not in model_options:
        st.session_state.selected_model = list(model_options.keys())[0]
    
    # API Key status
    if service in st.session_state.saved_api_keys:
        st.success(f"✅ App owner's {service} API key is available")
    else:
        st.warning(f"⚠️ App owner's {service} API key is not available")
    
    # Custom API key option
    use_custom_key = st.checkbox(
        "Use your own API key",
        value=service not in st.session_state.saved_api_keys,
        help=f"Check this to use your own {service} API key instead of the app owner's key"
    )
    
    if use_custom_key:
        st.info(f"🔑 Enter your own {service} API key to use instead of the app owner's key.")
        
        custom_api_key = st.text_input(
            f"Your {service} API Key",
            type="password",
            help="Enter your OpenAI API key. Get one at https://platform.openai.com/account/api-keys"
        )
        
        # Clean the user-provided API key
        custom_api_key = clean_api_key(custom_api_key)
        
        # Use custom key
        api_key = custom_api_key
        
        # Update client if API key changes
        if api_key and (not client or api_key != st.session_state.get('current_api_key', '')):
            st.session_state.current_api_key = api_key
            client = OpenAI(api_key=api_key)
            selected_model = model_options.get(st.session_state.selected_model, "gpt-4o")
            matty_invertor = MattyInvertor(provider=ModelProvider.OPENAI, model=selected_model, api_key=api_key)
    else:
        # Use owner's saved key from session state
        api_key = st.session_state.saved_api_keys.get(service, "")
        
        # Initialize client if needed
        if api_key and not client:
            client = OpenAI(api_key=api_key)
            selected_model = model_options.get(st.session_state.selected_model, "gpt-4o")
            matty_invertor = MattyInvertor(provider=ModelProvider.OPENAI, model=selected_model, api_key=api_key)
    
    # Model selection
    st.subheader("Model Selection")
    st.session_state.selected_model = st.selectbox(
        "Select LLM Model",
        options=list(model_options.keys()),
        index=list(model_options.keys()).index(st.session_state.selected_model) if st.session_state.selected_model in model_options else 0,
        key="model_selector"
    )
    
    # Initialize Backblaze silently if credentials are available
    if BACKBLAZE_AVAILABLE and st.session_state.backblaze_configured and not st.session_state.backblaze_enabled:
        initialize_backblaze()
        # Always enable auto-save if Backblaze is configured
        st.session_state.auto_save_images = True

# Set up tabs for different input methods
tab1, tab2 = st.tabs(["Upload Image", "Image URL"])

# Variables to store the image data
image = None
image_url = None

# Tab 1: Upload image
with tab1:
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        # Display the uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_container_width=True)
        
        # Save the file temporarily to get a path for the API
        image_path = save_uploaded_file(uploaded_file)
        
        # Create a data URL for the OpenAI API
        with open(image_path, "rb") as img_file:
            encoded_img = base64.b64encode(img_file.read()).decode('utf-8')
            image_url = f"data:image/{uploaded_file.type.split('/')[1]};base64,{encoded_img}"
        
        # Clean up the temporary file (in a production app, handle this better)
        # os.remove(image_path)  # Commented out to avoid file-in-use errors

# Tab 2: Image URL
with tab2:
    url_input = st.text_input("Enter the URL of an image")
    if url_input:
        try:
            image = load_image_from_url(url_input)
            st.image(image, caption="Image from URL", use_container_width=True)
            image_url = url_input
        except Exception as e:
            st.error(f"Error loading image from URL: {e}")

# Process button
if image_url and st.button("Extract Concepts"):
    with st.spinner("Extracting concepts from the image..."):
        try:
            if not client:
                st.error("API key is required to extract concepts. Please enter a valid OpenAI API key.")
            else:
                # Use the selected model from dropdown
                selected_model_id = model_options[st.session_state.selected_model]
                
                # Extract concepts using the client with the selected model
                concept_text = extract_concepts_from_image(client, image_url)
                
                # Store in session state
                st.session_state.image_url = image_url
                st.session_state.concept_text = concept_text
                st.session_state.show_concept_editor = True
        except Exception as e:
            st.error(f"Error extracting concepts: {e}")

# Show concept editor if we have concepts
if 'show_concept_editor' in st.session_state and st.session_state.show_concept_editor:
    # Display the extracted concepts
    st.subheader("Extracted Concepts")
    concept_edit = st.text_area(
        "You can edit these concepts before synthesizing:", 
        st.session_state.get('concept_text', ''),
        height=300
    )
    st.session_state.concept_edit = concept_edit
    
    # Parse the axes
    axes = parse_axes(concept_edit)
    
    # Store in session state
    st.session_state.axes = axes
    
    # Display the parsed axes with checkboxes
    st.subheader("Parsed Conceptual Axes")
    
    # Initialize checkboxes in session state if not present
    if 'axes_checkboxes' not in st.session_state:
        st.session_state.axes_checkboxes = {axis: True for axis in axes.keys()}
    
    # Display axes with checkboxes
    for axis, value in axes.items():
        checkbox = st.checkbox(axis, value=st.session_state.axes_checkboxes.get(axis, True), key=f"checkbox_{axis}")
        st.session_state.axes_checkboxes[axis] = checkbox
        
        # Only display the value if checkbox is checked
        if checkbox:
            # Convert the value to a proper bulleted list with formatting
            lines = value.split("\n")
            formatted_lines = []
            
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue
                # Skip lines that are just bullet points
                if line.strip() in ["•", "-"]:
                    continue
                    
                # Add bullet point and proper indentation (if it doesn't already have one)
                if not line.startswith("• ") and not line.startswith("Left:") and not line.startswith("Right:"):
                    formatted_lines.append(f"• {line}")
                else:
                    formatted_lines.append(line)
            
            # Join with HTML line breaks and create a nicely formatted div
            formatted_value = "<br>".join(formatted_lines)
            st.write(f"<div style='margin-left: 25px;'>{formatted_value}</div>", unsafe_allow_html=True)
            st.write("") # Add blank line after each axis for readability
    
    # Generate a unified concept button
    # Debug option to show the prompt details
    show_debug_info = st.checkbox("Show debug information", value=False, key="show_debug")

    if st.button("Synthesize Unified Concept"):
        with st.spinner("Synthesizing a unified concept..."):
            # Filter axes based on checkboxes
            selected_axes = {axis: value for axis, value in axes.items() 
                            if st.session_state.axes_checkboxes.get(axis, True)}
            
            if selected_axes:
                # Format axes descriptions for debug view
                axes_descriptions = "\n".join([f"{axis}: {concept}" for axis, concept in selected_axes.items()])
                
                # Save to session state for debug view
                st.session_state.last_axes_descriptions = axes_descriptions
                
                # Create unified concept
                unified_concept = combine_axes_into_single_concept(client, selected_axes)
                st.session_state.unified_concept = unified_concept
                
                # Generate concise summary
                concise_summary = create_concise_summary(client, unified_concept)
                st.session_state.concise_summary = concise_summary
                
                st.session_state.show_unified_concept = True
            else:
                st.warning("Please select at least one conceptual axis to synthesize a concept.")
    
    # Show debug information if enabled
    if st.session_state.get("show_debug", False) and "last_axes_descriptions" in st.session_state:
        with st.expander("Debug: Axes Descriptions Used in Prompt", expanded=True):
            st.text_area("Axes Descriptions", st.session_state.last_axes_descriptions, height=250, disabled=True)

# Show unified concept if we have it
if 'show_unified_concept' in st.session_state and st.session_state.show_unified_concept:
    # Display the unified concept
    st.subheader("Unified Concept")
    
    # Full concept
    unified_concept_edit = st.text_area(
        "Full concept description:", 
        st.session_state.get('unified_concept', ''),
        height=150
    )
    st.session_state.unified_concept_edit = unified_concept_edit
    
    # Concise summary
    concise_summary_edit = st.text_area(
        "Concise summary (10 words or less):", 
        st.session_state.get('concise_summary', ''),
        height=80
    )
    st.session_state.concise_summary_edit = concise_summary_edit
    
    # Select which concept version to use for image generation
    st.session_state.use_concise_unified = st.radio(
        "Which concept to use for image generation:",
        ["Full concept", "Concise summary"],
        key="unified_concept_choice"
    )
    
    st.session_state.show_generate = True

# Generate new image
if 'show_generate' in st.session_state and st.session_state.show_generate:
    # Determine which concept version to use based on user selection
    if 'unified_concept_edit' in st.session_state:
        if st.session_state.get('use_concise_unified') == "Concise summary" and 'concise_summary_edit' in st.session_state:
            default_value = st.session_state.concise_summary_edit
        else:
            default_value = st.session_state.unified_concept_edit
    else:
        # Fall back to joined axes if no unified concept
        default_value = " + ".join(st.session_state.get('axes', {}).values())
    
    final_concept = st.text_input(
        "Final concept for the original image:", 
        value=default_value
    )
    st.session_state.final_concept = final_concept
    
    # Add option to invert the concept
    invert_concept = st.checkbox("Generate an inverted concept (maximally orthogonal)")
    
    if invert_concept and st.button("Generate Inverted Concept"):
        with st.spinner("Generating an inverted concept..."):
            try:
                # Get the selected axes for debugging
                selected_axes = []
                if 'axes_checkboxes' in st.session_state:
                    selected_axes = [axis for axis, is_selected in st.session_state.axes_checkboxes.items() if is_selected]
                
                # Format the axes list for debug view
                axes_list = ", ".join(selected_axes)
                st.session_state.last_inversion_axes = axes_list
                
                # Generate inverted concept using run_mci1
                inverted_concept = run_mci1(client, final_concept)
                st.session_state.inverted_concept = inverted_concept
                
                # Also generate concise summary for the inverted concept
                inverted_concise = create_concise_summary(client, inverted_concept)
                st.session_state.inverted_concise_summary = inverted_concise
                
                st.session_state.show_inverted = True
                st.rerun()  # Rerun to show the inverted concept editor
            except Exception as e:
                st.error(f"Error generating inverted concept: {e}")
                
    # Show debug information for inversion if enabled and available
    if st.session_state.get("show_debug", False) and "last_inversion_axes" in st.session_state:
        with st.expander("Debug: Axes Used for Inversion", expanded=True):
            st.text_area("Axes List", st.session_state.last_inversion_axes, height=100, disabled=True)
    
    # Show inverted concept editor if available
    if 'show_inverted' in st.session_state and st.session_state.show_inverted:
        # Display the inverted concept with its own text input
        st.subheader("Inverted Concept")
        st.write("This concept represents ideas maximally orthogonal to your original concept:")
        
        # Use the stored inverted concept if available
        inverted_default = st.session_state.get('inverted_concept', '')
        
        # Full inverted concept
        inverted_final_concept = st.text_area(
            "Full inverted concept:",
            value=inverted_default,
            height=150
        )
        st.session_state.inverted_final_concept = inverted_final_concept
        
        # Generate concise summary for the inverted concept if needed
        if 'inverted_concise_summary' not in st.session_state and inverted_default:
            with st.spinner("Creating concise summary of inverted concept..."):
                inverted_concise = create_concise_summary(client, inverted_default)
                st.session_state.inverted_concise_summary = inverted_concise
        
        # Concise summary for inverted concept
        inverted_concise_edit = st.text_area(
            "Concise summary of inverted concept (10 words or less):",
            value=st.session_state.get('inverted_concise_summary', ''),
            height=80
        )
        st.session_state.inverted_concise_summary_edit = inverted_concise_edit
        
        # Select which inverted concept version to use
        st.session_state.use_concise_inverted = st.radio(
            "Which inverted concept to use for image generation:",
            ["Full concept", "Concise summary"],
            key="inverted_concept_choice"
        )
    
    # Generation options
    st.subheader("Generate Images")
    
    # Add Image Prompt field for styling the generated image
    image_prompt = st.text_input(
        "Image Prompt", 
        placeholder="e.g. drawn in chalk pastels",
        help="Optional styling to add to the image generation prompt"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Regenerate Original Image"):
            with st.spinner("Generating image from original concept..."):
                try:
                    # Combine the concept with the optional image prompt
                    full_prompt = final_concept
                    if image_prompt:
                        full_prompt = f"{final_concept}, {image_prompt}"
                    
                    # Generate the image from the combined prompt
                    generated_image_url = generate_recursive_image(client, full_prompt)
                    
                    # Store the URL and concept source in session state
                    st.session_state.generated_image_url = generated_image_url
                    st.session_state.used_concept_type = "original"
                    st.session_state.used_concept_text = full_prompt
                    
                    # Rerun to show the image
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error generating image: {e}")
    
    # Only show inverted and contrast options if we have an inverted concept
    if 'show_inverted' in st.session_state and st.session_state.show_inverted:
        with col2:
            if st.button("Generate Inverted Image"):
                with st.spinner("Generating image from inverted concept..."):
                    try:
                        # Determine which inverted concept version to use based on user selection
                        if st.session_state.get('use_concise_inverted') == "Concise summary" and 'inverted_concise_summary_edit' in st.session_state:
                            inverted_concept_to_use = st.session_state.inverted_concise_summary_edit
                        else:
                            inverted_concept_to_use = st.session_state.get('inverted_final_concept', '')
                        
                        # Combine the concept with the optional image prompt
                        full_prompt = inverted_concept_to_use
                        if image_prompt:
                            full_prompt = f"{inverted_concept_to_use}, {image_prompt}"
                        
                        # Generate the image from the combined prompt
                        generated_image_url = generate_recursive_image(client, full_prompt)
                        
                        # Store the URL and concept source in session state
                        st.session_state.generated_image_url = generated_image_url
                        st.session_state.used_concept_type = "inverted"
                        st.session_state.used_concept_text = full_prompt
                        
                        # Rerun to show the image
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error generating image: {e}")
        
        with col3:
            if st.button("Generate Contrasting Image"):
                with st.spinner("Generating image contrasting both concepts..."):
                    try:
                        # Determine which original concept version to use
                        if st.session_state.get('use_concise_unified') == "Concise summary" and 'concise_summary_edit' in st.session_state:
                            original_concept = st.session_state.concise_summary_edit
                        else:
                            original_concept = final_concept
                        
                        # Determine which inverted concept version to use
                        if st.session_state.get('use_concise_inverted') == "Concise summary" and 'inverted_concise_summary_edit' in st.session_state:
                            inverted_concept = st.session_state.inverted_concise_summary_edit
                        else:
                            inverted_concept = st.session_state.get('inverted_final_concept', '')
                        
                        # Create a prompt that contrasts both concepts
                        contrast_prompt = PROMPT_GENERATE_CONTRAST.format(
                            original_concept=original_concept,
                            inverted_concept=inverted_concept
                        )
                        
                        # Add the image prompt if provided
                        if image_prompt:
                            contrast_prompt = f"{contrast_prompt} {image_prompt}"
                        
                        # Generate the contrasting image
                        generated_image_url = generate_recursive_image(client, contrast_prompt)
                        
                        # Store the URL and concept source in session state
                        st.session_state.generated_image_url = generated_image_url
                        st.session_state.used_concept_type = "contrast"
                        st.session_state.used_concept_text = contrast_prompt
                        
                        # Rerun to show the image
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error generating image: {e}")

# Display the generated image if it exists in session state
if 'generated_image_url' in st.session_state:
    st.subheader("Generated Image")
    
    # Show which concept was used to generate the image
    concept_type = st.session_state.get('used_concept_type', 'unknown')
    
    if concept_type == "original":
        st.info("This image was generated from the original concept.")
    elif concept_type == "inverted":
        st.info("This image was generated from the inverted concept.")
    elif concept_type == "contrast":
        st.info("This image contrasts the original and inverted concepts.")
    
    # Display the concept used
    if 'used_concept_text' in st.session_state:
        st.write(f"**Concept used:** {st.session_state.used_concept_text}")
    
    st.image(st.session_state.generated_image_url, caption="Generated Image", use_container_width=True)
    st.markdown(f"[Download Generated Image]({st.session_state.generated_image_url})")
    
    # Auto-save to Backblaze if enabled (completely silently, no UI feedback)
    if st.session_state.get('auto_save_images', False) and st.session_state.backblaze_enabled:
        # Collect metadata for the image
        original_concept = st.session_state.get('final_concept', '')
        inverted_concept = st.session_state.get('inverted_final_concept', '')
        
        # Create metadata dictionary
        metadata = {
            "generation_time": datetime.datetime.now().isoformat(),
            "concept_type": concept_type,
            "original_concept": original_concept,
            "inverted_concept": inverted_concept,
            "used_concept": st.session_state.get('used_concept_text', ''),
            "model": st.session_state.selected_model,
            "app_version": "1.0"
        }
        
        # Save to Backblaze completely silently (no spinners, no success/error messages)
        try:
            save_to_backblaze(
                st.session_state.generated_image_url, 
                metadata, 
                filename_prefix=f"image_inversion_{concept_type}"
            )
        except:
            # Silently fail - no error messaging to user
            pass
    
    # Add a button to start over
    if st.button("Create Another Image"):
        # Keep the image_url but reset the workflow
        if 'image_url' in st.session_state:
            keep_url = st.session_state.image_url
            # Reset session state while preserving settings
            preserved_keys = ['image_url', 'selected_model', 'saved_api_keys', 
                             'selected_api_service', 'backblaze_enabled', 
                             'backblaze_configured', 'backblaze_client', 
                             'auto_save_images', 'current_api_key']
            
            for key in list(st.session_state.keys()):
                if key not in preserved_keys:
                    del st.session_state[key]
                    
            st.session_state.image_url = keep_url
            st.rerun()

# Footer
st.markdown("---")
st.markdown("This app uses the OpenAI API to extract concepts from images and generate new images.") 