import streamlit as st
from matty_invertor_v2 import MattyInvertor, ModelProvider, ModelConfig, CONCEPTUAL_AXES
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize session state
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "GPT-3.5 Turbo"
if 'use_revector' not in st.session_state:
    st.session_state.use_revector = False
if 'depth' not in st.session_state:
    st.session_state.depth = 3
if 'selected_axes' not in st.session_state:
    st.session_state.selected_axes = list(CONCEPTUAL_AXES.keys())

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
""")

# Sidebar controls
with st.sidebar:
    st.header("Configuration")
    
    # Model selection
    model_options = {
        "GPT-3.5 Turbo": ModelConfig.GPT_3_5_TURBO,
        "GPT-4 Turbo": ModelConfig.GPT_4_TURBO,
        "GPT-4": ModelConfig.GPT_4
    }
    st.session_state.selected_model = st.selectbox(
        "Select LLM Model",
        options=list(model_options.keys()),
        key="model_selector"
    )
    
    # Revector toggle
    st.session_state.use_revector = st.checkbox(
        "Use Revector",
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
    st.session_state.selected_axes = []
    for axis, description in CONCEPTUAL_AXES.items():
        if st.checkbox(
            f"{axis.replace('_', ' ').title()} ({description})",
            value=axis in st.session_state.selected_axes,
            key=f"axis_{axis}"
        ):
            st.session_state.selected_axes.append(axis)

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    # Input concept
    concept = st.text_input("Enter your concept:", value="dada", key="concept_input")
    
    if concept:
        try:
            # Initialize invertor
            invertor = MattyInvertor(
                provider=ModelProvider.OPENAI,
                model=model_options[st.session_state.selected_model],
                api_key=os.getenv('OPENAI_API_KEY')
            )
            
            # Generate inversions
            results = invertor.invert_concept(
                concept,
                depth=st.session_state.depth,
                selected_axes=st.session_state.selected_axes,
                revector=st.session_state.use_revector
            )
            
            # Display results
            st.subheader("Inversion Results")
            if isinstance(results, str):
                st.write("Level 1:", results)
            else:
                for i, result in enumerate(results, 1):
                    st.write(f"Level {i}:", result)
            
            # Image generation section
            st.subheader("Image Generation")
            col_img1, col_img2 = st.columns(2)
            
            with col_img1:
                # Select level for comparison
                if isinstance(results, list):
                    level_options = list(range(1, len(results) + 1))
                    selected_level = st.selectbox(
                        "Select level to compare with original concept",
                        options=level_options,
                        key="level_select"
                    )
                    comparison_concept = results[selected_level - 1]
                else:
                    comparison_concept = results
                
                # Image style selection
                image_style = st.text_input(
                    "Image style (optional)",
                    placeholder="e.g., a fractal image in the style of Escher",
                    help="Leave empty for default split image style",
                    key="style_input"
                )
                
                if st.button("Generate Image", key="gen_image"):
                    with st.spinner("Generating image..."):
                        # Modify the prompt based on style input
                        if image_style:
                            # Override the default image generation prompt
                            prompt = f"Generate {image_style} that contrasts the concepts: {concept} VS {comparison_concept}"
                            image_url = invertor.client.images.generate(
                                model="dall-e-3",
                                prompt=prompt,
                                size="1024x1024",
                                quality="standard",
                                n=1,
                            ).data[0].url
                        else:
                            # Use default split image generation
                            image_url = invertor.generate_contrast_image(
                                concept,
                                comparison_concept,
                                is_revector=st.session_state.use_revector
                            )
                        
                        if image_url and not image_url.startswith("Error"):
                            st.image(image_url, caption="Generated contrast image")
                        else:
                            st.error(f"Failed to generate image: {image_url}")
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            if "api_key" in str(e).lower():
                st.warning("Please make sure your OpenAI API key is set in the .env file")

with col2:
    # Help section
    st.subheader("How to Use")
    st.markdown("""
    1. **Select Model**: Choose between GPT-3.5 Turbo, GPT-4 Turbo, or GPT-4
    2. **Configure Inversion**:
        - Toggle Revector mode
        - Set recursion depth
        - Select inversion axes
    3. **Enter Concept**: Type your concept to invert
    4. **Generate Images**: 
        - Select which level to compare with original
        - Optionally specify an image style
        - Click Generate Image
    """)
    
    # Display current settings
    st.subheader("Current Settings")
    st.write(f"Model: {st.session_state.selected_model}")
    st.write(f"Depth: {st.session_state.depth}")
    st.write(f"Revector: {'On' if st.session_state.use_revector else 'Off'}")
    st.write("Selected Axes:", ", ".join(st.session_state.selected_axes)) 