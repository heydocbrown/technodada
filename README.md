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

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/technodada.git
   cd technodada
   ```

2. Create and activate a conda environment:
   ```bash
   conda create -n technodada python=3.12
   conda activate technodada
   ```

3. Install dependencies:
   ```bash
   pip install streamlit openai python-dotenv
   ```

4. Create a `.env` file in the project root and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

1. Run the Streamlit dashboard:
   ```bash
   streamlit run app.py
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

- `app.py` - Main Streamlit dashboard application
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