from openai import OpenAI

client = OpenAI()
model_name = "gpt-3.5-turbo"

# Dictionary of available conceptual axes
CONCEPTUAL_AXES = {
    "semantic": "completely different meaning",
    "functional": "completely different use",
    "causal": "has no causal relationship",
    "spatial_temporal": "exists in a different space or time",
    "conceptual_abstract": "belongs to a different intellectual framework",
    "emotional": "evokes opposite emotions",
    "physical": "has opposite physical properties",
    "cultural": "belongs to a contrasting cultural context",
    "technological": "represents opposing technological paradigms",
    "ethical": "embodies contrasting moral values"
}

def format_as_sentence(concept):
    """Format a concept as a clean string."""
    # Remove prefixes and clean up
    concept = concept.replace('Concept name:', '').replace('Concept Name:', '')
    concept = concept.replace('Concept:', '').replace('The concept of', '')
    return concept.strip().rstrip('.')

def generate_contrast_image(concept1, concept2, is_mci_v3=False):
    """Generate an image showing the contrast between two concepts.
    
    Args:
        concept1: String or list of concepts
        concept2: String or list of concepts
        is_mci_v3: Boolean indicating if the output is from MCI_v3
    """
    # Handle list inputs
    if isinstance(concept2, list):
        if is_mci_v3:
            # For MCI_v3: combine all concepts
            concept2 = " merged with ".join(format_as_sentence(c) for c in concept2)
        else:
            # For MCI_v2: take only the last concept
            concept2 = format_as_sentence(concept2[-1])
            
    if isinstance(concept1, list):
        concept1 = format_as_sentence(concept1[-1])
    
    # Clean up any remaining prefixes
    concept1 = concept1.replace('Concept name:', '').replace('Concept Name:', '').strip()
    concept2 = concept2.replace('Concept name:', '').replace('Concept Name:', '').strip()
    
    prompt = f"A split image showing the contrast between: {concept1} VS {concept2}"
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as e:
        return f"Error generating image: {str(e)}"

def mci_v1(corpus, selected_axes=None, format_sentence=True):
    """Generate orthogonal concept using selected axes."""
    if selected_axes is None:
        selected_axes = ["semantic", "functional", "causal", "spatial_temporal", "conceptual_abstract"]
    
    axes_text = "\n".join([f"- {axis.replace('_', ' ').title()} ({CONCEPTUAL_AXES[axis]})" 
                          for axis in selected_axes if axis in CONCEPTUAL_AXES])
    
    prompt = f"""
    Given the concept: "{corpus}", generate a concept that is maximally orthogonal across these axes:
    {axes_text}
    
    Provide only the concept name.
    """
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are an expert in conceptual divergence."},
            {"role": "user", "content": prompt}
        ]
    )
    result = response.choices[0].message.content
    return format_as_sentence(result) if format_sentence else result

def mci_v2(corpus, depth, selected_axes=None, format_sentence=True):
    output = corpus
    history = []

    for _ in range(depth):
        output = mci_v1(output, selected_axes, format_sentence=False)
        history.append(output if not format_sentence else format_as_sentence(output))

    return history

def mci_v3(corpus, depth, selected_axes=None, format_sentence=True):
    output = corpus
    history = []

    for _ in range(depth):
        combined_input = corpus + " + " + " + ".join([h.rstrip('.') for h in history]) if history else corpus
        output = mci_v1(combined_input, selected_axes, format_sentence=False)
        history.append(output if not format_sentence else format_as_sentence(output))

    return history

if __name__ == "__main__":
    # Example usage
    concept = "interconnected islands across the planet"
    selected_axes = ["semantic", "spatial_temporal", "technological"]
    
    # Test MCIv1 with image generation
    concept_orthogonal = mci_v1(concept, selected_axes)
    print("MCIv1 Output:", concept_orthogonal)
    
    # Generate contrast image
    image_url = generate_contrast_image(concept, concept_orthogonal.rstrip('.'))
    print("Contrast Image URL:", image_url)
    
    # Test MCIv2 (Recursive)
    recursive_outputs = mci_v2(concept, depth=3, selected_axes=selected_axes)
    print("MCIv2 Recursive Outputs:", recursive_outputs)
    
    # Test MCIv3 (Combinatorial Recursive)
    combinatorial_outputs = mci_v3(concept, depth=3, selected_axes=selected_axes)
    print("MCIv3 Combinatorial Recursive Outputs:", combinatorial_outputs)
