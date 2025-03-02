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
        
        if provider == ModelProvider.ANTHROPIC and not api_key:
            raise ValueError("Anthropic API key required when using Claude models")
        
        if provider == ModelProvider.GROK and not api_key:
            raise ValueError("Grok API key required when using Grok models")
        
        if provider == ModelProvider.OPENAI:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
        elif provider == ModelProvider.ANTHROPIC:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("Anthropic package not found. Please install with: pip install anthropic")
        elif provider == ModelProvider.CURSOR:
            if not cursor:
                raise ImportError("Cursor package not found. Please run inside Cursor editor.")
            self.client = cursor
        elif provider == ModelProvider.GROK:
            try:
                # Import the Grok client library - this will need to be adjusted based on xAI's actual API
                from xai import grok
                self.client = grok.Grok(api_key=api_key)
            except ImportError:
                raise ImportError("Grok package not found. Please install with: pip install xai-grok")

    def _generate_completion(self, prompt, system_message="You are an expert in conceptual divergence. Always return plain text without quotes or formatting."):
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
        elif self.provider == ModelProvider.ANTHROPIC:
            response = self.client.messages.create(
                model=self.model,
                system=system_message,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            return response.content[0].text
        elif self.provider == ModelProvider.GROK:
            # This is a placeholder - the actual implementation will depend on Grok's API
            response = self.client.chat(
                model=self.model,
                system_prompt=system_message,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            # Assuming the response format is similar to OpenAI
            return response.choices[0].message.content

    def format_as_sentence(self, concept):
        """Format a concept as a clean string."""
        # Remove common prefixes
        concept = concept.replace('Concept name:', '').replace('Concept Name:', '')
        concept = concept.replace('Concept:', '').replace('The concept of', '')
        
        # Remove any trailing periods and extra whitespace
        concept = concept.strip().rstrip('.')
        
        # Handle quotes - simple but effective for most cases
        if concept.startswith('"') and concept.endswith('"'):
            concept = concept[1:-1].strip()
        elif concept.startswith("'") and concept.endswith("'"):
            concept = concept[1:-1].strip()
        
        # Also add explicit instruction in the prompt to avoid quotes
        return concept.strip()

    def invert_concept(self, corpus, depth=1, selected_axes=None, format_sentence=True, revector=False, 
                       instruction_text=None, requirements=None):
        """Generate orthogonal concepts using specified parameters.
        
        Args:
            corpus: Initial concept to invert
            depth: Number of iterations (default=1 for basic inversion)
            selected_axes: List of conceptual axes to consider
            format_sentence: Whether to format the output as clean sentences
            revector: If True, each iteration considers all previous outputs (MCI_v3 behavior)
            instruction_text: Custom instruction text for the prompt
            requirements: List of requirements to include in the prompt
        
        Returns:
            List of generated concepts (or single concept if depth=1)
        """
        if selected_axes is None:
            selected_axes = ["semantic", "functional", "causal", "spatial_temporal", "conceptual_abstract"]
        
        # Use default instruction if none provided
        if instruction_text is None:
            instruction_text = "generate a concept that is maximally different across these axes"
        
        # Use default requirements if none provided
        if requirements is None:
            requirements = [
                "The concept should be recognizable to many people",
                "Avoid technical jargon."
            ]
        
        # If requirements is an empty list, respect that choice
        if requirements == []:
            requirements_text = ""
        else:
            # Create requirements text with numbering
            requirements_text = "\n".join([f"{i+1}. {req}" for i, req in enumerate(requirements)])
            requirements_text = f"\nRequirements:\n{requirements_text}\n"
        
        history = []
        current_input = corpus

        for _ in range(depth):
            if revector and history:
                # MCI_v3 behavior: combine input with previous outputs
                current_input = corpus + " + " + " + ".join([h.rstrip('.') for h in history])
            
            axes_text = "\n".join([f"- {axis.replace('_', ' ').title()} ({CONCEPTUAL_AXES[axis]})" 
                                 for axis in selected_axes if axis in CONCEPTUAL_AXES])
            
            # Add custom axes if any are in selected_axes but not in CONCEPTUAL_AXES
            custom_axes_text = "\n".join([f"- {axis.replace('_', ' ').title()} (custom)" 
                                       for axis in selected_axes if axis not in CONCEPTUAL_AXES])
            if custom_axes_text:
                axes_text = axes_text + "\n" + custom_axes_text if axes_text else custom_axes_text
            
            prompt = f"""
            Given the concept: "{current_input}", {instruction_text}:
            {axes_text}
            {requirements_text}
            Return only the plain concept name without any quotes, prefixes or explanations.
            Example format: Abstract Harmony
            """
            
            result = self._generate_completion(prompt)
            formatted_result = self.format_as_sentence(result) if format_sentence else result
            history.append(formatted_result)
            
            if not revector:
                # MCI_v2 behavior: use last output as next input
                current_input = result

        # Return single concept for depth=1, list otherwise
        return history[0] if depth == 1 else history

    def generate_contrast_image(self, concept1, concept2, is_revector=False, custom_prompt=None):
        """Generate an image showing the contrast between two concepts."""
        if isinstance(concept2, list):
            if is_revector:  # Previously is_mci_v3
                concept2 = " merged with ".join(self.format_as_sentence(c) for c in concept2)
            else:
                concept2 = self.format_as_sentence(concept2[-1])
                
        if isinstance(concept1, list):
            concept1 = self.format_as_sentence(concept1[-1])
        else:
            # Also apply format_as_sentence to string input
            concept1 = self.format_as_sentence(concept1)
        
        # Ensure concept2 is also formatted if it's a string
        if not isinstance(concept2, list):
            concept2 = self.format_as_sentence(concept2)
        
        # Remove any remaining prefixes (this is already handled by format_as_sentence, but adding as a safety)
        concept1 = concept1.replace('Concept name:', '').replace('Concept Name:', '').strip()
        concept2 = concept2.replace('Concept name:', '').replace('Concept Name:', '').strip()
        
        # Use custom prompt if provided, otherwise use the default
        if custom_prompt:
            prompt = custom_prompt
        else:
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
        elif self.provider == ModelProvider.ANTHROPIC:
            # Claude doesn't currently have image generation capabilities
            # Return a message indicating this
            return "Error generating image: Claude doesn't support image generation. Please use OpenAI for image generation."
        elif self.provider == ModelProvider.GROK:
            try:
                # This is a placeholder - actual implementation will depend on Grok's API
                response = self.client.generate_image(
                    prompt=prompt,
                    # Add any other required parameters for Grok's image generation
                )
                # Adjust this based on Grok's actual response format
                return response.image_url
            except Exception as e:
                return f"Error generating image: {str(e)}"

    # For backward compatibility
    def mci_v1(self, corpus, selected_axes=None, format_sentence=True, instruction_text=None, requirements=None):
        return self.invert_concept(corpus, depth=1, selected_axes=selected_axes, format_sentence=format_sentence, 
                                   instruction_text=instruction_text, requirements=requirements)

    def mci_v2(self, corpus, depth, selected_axes=None, format_sentence=True, instruction_text=None, requirements=None):
        return self.invert_concept(corpus, depth=depth, selected_axes=selected_axes, format_sentence=format_sentence,
                                   instruction_text=instruction_text, requirements=requirements)

    def mci_v3(self, corpus, depth, selected_axes=None, format_sentence=True, instruction_text=None, requirements=None):
        return self.invert_concept(corpus, depth=depth, selected_axes=selected_axes, format_sentence=format_sentence, 
                                   revector=True, instruction_text=instruction_text, requirements=requirements) 