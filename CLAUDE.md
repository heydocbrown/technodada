# TechnoDada Development Guide

## Setup & Run
```bash
conda activate technodada     # Use existing environment
pip install -r requirements.txt
streamlit run st_dadacat.py   # Run DadaCat interface
streamlit run st_concept_invertor.py  # Run Concept Invertor
```

## Testing
```bash
pytest tests/                 # Run all tests
pytest tests/unit/test_file.py::test_function  # Run specific test
python dadacat-twilio/FlightCheck/run_all_checks.py  # Verify environment
```

## Code Style Guidelines
- Follow PEP 8 conventions with Google-style docstrings
- Use type hints for all function parameters and returns
- Group imports: standard library → third-party → local
- Use descriptive variable names (snake_case for variables/functions)
- Handle exceptions with meaningful error messages
- Always validate user input and API responses
- Log errors and important events consistently
- Use environment variables for configuration and secrets
- Create modular components with single responsibilities
- Document complex algorithms and design decisions