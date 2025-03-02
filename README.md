# TechnoDada

A concept inversion system that explores the transformation of ideas across multiple conceptual axes using various LLM models.

## Features

- Multiple LLM model support (GPT-3.5-Turbo, GPT-4-Turbo, GPT-4)
- Interactive web dashboard using Streamlit
- Concept inversion across multiple axes:
  - Semantic (meaning and definition)
  - Causal (causes and effects)
  - Emotional (emotional associations)
  - Functional (purpose and use)
  - Conceptual Abstract (abstract properties)
  - Spatial Temporal (space and time relationships)
- Three inversion modes:
  - Basic inversion (single step)
  - Chain inversion (multiple steps)
  - Revector inversion (considering all previous steps)
- DALL-E 3 image generation for concept visualization
- Custom image style support

## Setup

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/heydocbrown/technodada.git
   cd technodada
   ```

2. Create and activate a conda environment:
   ```bash
   conda create -n technodada python=3.12
   conda activate technodada
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   GROK_API_KEY=your_grok_api_key_here
   
   # Backblaze credentials (optional)
   BACKBLAZE_APPLICATION_KEY_ID=your_backblaze_key_id
   BACKBLAZE_APPLICATION_KEY=your_backblaze_application_key
   BACKBLAZE_BUCKET_NAME=your_backblaze_bucket_name
   ```

### Streamlit Cloud Deployment

When deploying to Streamlit Cloud, you need to set up your API keys as secrets:

1. Create a file named `.streamlit/secrets.toml` locally (do not commit to git):
   ```toml
   OPENAI_API_KEY = "your_openai_api_key_here"
   ANTHROPIC_API_KEY = "your_anthropic_api_key_here"
   GROK_API_KEY = "your_grok_api_key_here"
   
   # Backblaze credentials (optional)
   BACKBLAZE_APPLICATION_KEY_ID = "your_backblaze_key_id"
   BACKBLAZE_APPLICATION_KEY = "your_backblaze_application_key"
   BACKBLAZE_BUCKET_NAME = "your_backblaze_bucket_name"
   ```

2. In the Streamlit Cloud dashboard:
   - Go to your app settings
   - Navigate to the "Secrets" section
   - Paste the contents of your `secrets.toml` file
   - Click "Save"

The app will now be able to access these secrets in the cloud environment.

## Usage

1. Run the Streamlit dashboard:
   ```bash
   streamlit run st_concept_invertor.py
   ```

2. Access the dashboard in your browser at `http://localhost:8501`

3. Configure your inversion:
   - Select an LLM model
   - Choose inversion axes
   - Set recursion depth
   - Toggle Revector mode if desired

4. Enter your concept and explore the inversions

5. Generate images to visualize the contrast between concepts

## Project Structure

- `st_concept_invertor.py` - Main Streamlit dashboard application
- `matty_invertor_v2/` - Core inversion system
  - `__init__.py` - Package initialization
  - `invertor.py` - Main invertor implementation
  - `model_config.py` - Model and axis configurations

## License

MIT License

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 