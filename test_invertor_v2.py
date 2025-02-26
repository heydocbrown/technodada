from matty_invertor_v2 import MattyInvertor, ModelProvider, ModelConfig
import webbrowser
import os
from dotenv import load_dotenv  # You might need to pip install python-dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def test_model(model_config, concept, selected_axes):
    print(f"\nTesting with model: {model_config}")
    invertor = MattyInvertor(
        provider=ModelProvider.OPENAI,
        model=model_config,
        api_key=os.getenv('OPENAI_API_KEY')
    )
    
    print(f"Starting concept inversion for: {concept}")
    
    # Basic inversion (equivalent to MCI_v1)
    result1 = invertor.invert_concept(concept, depth=1, selected_axes=selected_axes)
    print(f"Basic inversion result: {result1}")
    
    # Chain inversion (equivalent to MCI_v2)
    result2 = invertor.invert_concept(concept, depth=3, selected_axes=selected_axes)
    print(f"Chain inversion results: {result2}")
    
    # Revector inversion (equivalent to MCI_v3)
    result3 = invertor.invert_concept(concept, depth=3, selected_axes=selected_axes, revector=True)
    print(f"Revector inversion results: {result3}")

    print("Generating contrast image...")
    image_url = invertor.generate_contrast_image(concept, result3, is_revector=True)
    print(f"Image URL generated: {image_url}")
    
    if image_url:
        print("Opening image in browser...")
        webbrowser.open(image_url)
    else:
        print("No image URL was generated.")
    
    return result3

def main():
    print("Initializing MattyInvertor tests...")
    
    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError("OpenAI API key not found in environment variables. Please set OPENAI_API_KEY in your .env file.")

    concept = "dada"
    selected_axes = ["semantic", "causal", "emotional", "functional", "conceptual_abstract"]

    # Test with different models
    models = [
        ModelConfig.GPT_3_5_TURBO,  # GPT-3.5-Turbo
        ModelConfig.GPT_4_TURBO,    # GPT-4-Turbo
        ModelConfig.GPT_4           # GPT-4
    ]
    
    results = {}
    for model in models:
        try:
            results[model] = test_model(model, concept, selected_axes)
        except Exception as e:
            print(f"Error with model {model}: {str(e)}")
            results[model] = None
    
    # Compare results
    print("\nComparison of results across models:")
    for model, result in results.items():
        print(f"\n{model}:")
        print(f"Final inversion result: {result}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {str(e)}") 