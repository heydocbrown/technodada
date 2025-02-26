try:
    import cursor
except ImportError:
    cursor = None

try:
    from model_config import ModelProvider, ModelConfig, CONCEPTUAL_AXES
except ImportError:
    from matty_invertor_v2.model_config import ModelProvider, ModelConfig, CONCEPTUAL_AXES

class MattyInvertor:
    def __init__(self, provider=ModelProvider.CURSOR, model=None, api_key=None):
        self.provider = provider
        self.model = model or ModelConfig.get_default_model()
        self.api_key = api_key
        
        if provider == ModelProvider.OPENAI and not api_key:
            raise ValueError("OpenAI API key required when using OpenAI provider")
        
        if provider == ModelProvider.OPENAI:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
        elif provider == ModelProvider.CURSOR:
            if not cursor:
                raise ImportError("Cursor package not found. Please run inside Cursor editor.")
            self.client = cursor
        elif provider == ModelProvider.GROK:
            raise NotImplementedError("Grok support coming soon")

    def _generate_completion(self, prompt, system_message="You are an expert in conceptual divergence."):
        if self.provider == ModelProvider.CURSOR:
            response = self.client.chat(messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ])
            return response
        elif self.provider == ModelProvider.OPENAI:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content

    def format_as_sentence(self, concept):
        """Format a concept as a clean string."""
        concept = concept.replace('Concept name:', '').replace('Concept Name:', '')
        concept = concept.replace('Concept:', '').replace('The concept of', '')
        return concept.strip().rstrip('.')

    def invert_concept(self, corpus, depth=1, selected_axes=None, format_sentence=True, revector=False):
        """Generate orthogonal concepts using specified parameters.
        
        Args:
            corpus: Initial concept to invert
            depth: Number of iterations (default=1 for basic inversion)
            selected_axes: List of conceptual axes to consider
            format_sentence: Whether to format the output as clean sentences
            revector: If True, each iteration considers all previous outputs (MCI_v3 behavior)
        
        Returns:
            List of generated concepts (or single concept if depth=1)
        """
        if selected_axes is None:
            selected_axes = ["semantic", "functional", "causal", "spatial_temporal", "conceptual_abstract"]
        
        history = []
        current_input = corpus

        for _ in range(depth):
            if revector and history:
                # MCI_v3 behavior: combine input with previous outputs
                current_input = corpus + " + " + " + ".join([h.rstrip('.') for h in history])
            
            axes_text = "\n".join([f"- {axis.replace('_', ' ').title()} ({CONCEPTUAL_AXES[axis]})" 
                                 for axis in selected_axes if axis in CONCEPTUAL_AXES])
            
            prompt = f"""
            Given the concept: "{current_input}", generate a concept that is maximally orthogonal across these axes:
            {axes_text}
            
            Provide only the concept name.
            """
            
            result = self._generate_completion(prompt)
            formatted_result = self.format_as_sentence(result) if format_sentence else result
            history.append(formatted_result)
            
            if not revector:
                # MCI_v2 behavior: use last output as next input
                current_input = result

        # Return single concept for depth=1, list otherwise
        return history[0] if depth == 1 else history

    def generate_contrast_image(self, concept1, concept2, is_revector=False):
        """Generate an image showing the contrast between two concepts."""
        if isinstance(concept2, list):
            if is_revector:  # Previously is_mci_v3
                concept2 = " merged with ".join(self.format_as_sentence(c) for c in concept2)
            else:
                concept2 = self.format_as_sentence(concept2[-1])
                
        if isinstance(concept1, list):
            concept1 = self.format_as_sentence(concept1[-1])
        
        concept1 = concept1.replace('Concept name:', '').replace('Concept Name:', '').strip()
        concept2 = concept2.replace('Concept name:', '').replace('Concept Name:', '').strip()
        
        prompt = f"A split image showing the contrast between: {concept1} VS {concept2}"
        
        if self.provider == ModelProvider.CURSOR:
            response = self.client.generate_image(prompt)
            return response
        elif self.provider == ModelProvider.OPENAI:
            try:
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                return response.data[0].url
            except Exception as e:
                return f"Error generating image: {str(e)}"

    # For backward compatibility
    def mci_v1(self, corpus, selected_axes=None, format_sentence=True):
        return self.invert_concept(corpus, depth=1, selected_axes=selected_axes, format_sentence=format_sentence)

    def mci_v2(self, corpus, depth, selected_axes=None, format_sentence=True):
        return self.invert_concept(corpus, depth=depth, selected_axes=selected_axes, format_sentence=format_sentence)

    def mci_v3(self, corpus, depth, selected_axes=None, format_sentence=True):
        return self.invert_concept(corpus, depth=depth, selected_axes=selected_axes, format_sentence=format_sentence, revector=True) 