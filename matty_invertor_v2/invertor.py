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
    
    # Image to concept functions (from image2concept.py)
    def extract_concepts_from_image(self, image_url):
        """Extract concepts from an image and align them to conceptual axes."""
        if self.provider != ModelProvider.OPENAI:
            raise ValueError("Image concept extraction is currently only supported with OpenAI's GPT-4o")
            
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at extracting concepts from images and aligning them to conceptual axes."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please describe the core concepts of this image, and break them down into these axes: Semantic, Functional, Causal, Spatial/Temporal, Conceptual/Abstract, Perceptual, Emotional, Technological vs Natural, Scale, Deterministic vs Stochastic."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )
        return response.choices[0].message.content
        
    def parse_axes(self, text):
        """Parse axes from a text describing conceptual dimensions.
        This parser uses a more context-aware approach that doesn't rely on hardcoded axis names."""
        
        import re
        
        # First, try to detect which format the text is in
        format_type = None
        
        # Check for numbered list (e.g., "1. **Semantic**")
        if re.search(r'^\d+\.\s+\*\*[A-Za-z]+\*\*', text, re.MULTILINE):
            format_type = "numbered_list"
        # Check for markdown headers (e.g., "### Semantic:")
        elif re.search(r'^###\s+[A-Za-z]+\s*:', text, re.MULTILINE):
            format_type = "markdown_headers"
        # Check for bullet points with axis names (e.g., "• Semantic:")
        elif re.search(r'^[•\-]\s+[A-Za-z]+\s*:', text, re.MULTILINE):
            format_type = "bullet_axes"
        # Check for axis names as lines (e.g., "**Semantic:**")
        elif re.search(r'^\*\*[A-Za-z]+\*\*\s*:', text, re.MULTILINE):
            format_type = "bold_axes"
            
        # Function to clean up text (remove markdown formatting, etc.)
        def clean_text(text):
            # Remove markdown formatting
            text = text.replace("**", "")
            # Clean up any extra whitespace
            text = text.strip()
            return text
            
        # Handle numbered list format (e.g., "1. **Semantic**")
        if format_type == "numbered_list":
            axes = {}
            current_axis = None
            current_content = []
            
            # Regular expression to match numbered list items
            numbered_regex = re.compile(r'^\d+\.\s+\*\*([A-Za-z /]+)\*\*')
            
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Check if this is a new numbered axis
                match = numbered_regex.match(line)
                if match:
                    # Save previous axis content if any
                    if current_axis and current_content:
                        axes[current_axis] = '\n'.join(current_content)
                        current_content = []
                    
                    # Extract the axis name and set as current
                    current_axis = match.group(1)
                    
                    # Check if there's content on the same line after the axis name
                    rest_of_line = line[match.end():].strip()
                    if rest_of_line:
                        current_content.append(clean_text(rest_of_line))
                    
                # If it's an indented line under current axis
                elif line.startswith(' ') and current_axis:
                    # Handle bullet points or other content
                    cleaned_line = clean_text(line)
                    if cleaned_line.startswith('-') or cleaned_line.startswith('•'):
                        cleaned_line = cleaned_line[1:].strip()
                    
                    if cleaned_line:
                        current_content.append(cleaned_line)
                
                # Handle continuation lines
                elif current_axis:
                    # This might be a continuation of the previous content
                    current_content.append(clean_text(line))
            
            # Don't forget the last axis
            if current_axis and current_content:
                axes[current_axis] = '\n'.join(current_content)
                
            # Return results if we found any axes
            if axes:
                return axes
                
        # Handle markdown headers format (e.g., "### Semantic:")
        if format_type == "markdown_headers" or not format_type:
            axes = {}
            current_axis = None
            current_content = []
            
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Skip introductory text
                if any(intro in line.lower() for intro in ["certainly", "breakdown", "here is", "using the specified"]):
                    continue
                    
                # Check for markdown header
                if line.startswith('###') and ':' in line:
                    # Save previous axis if any
                    if current_axis and current_content:
                        axes[current_axis] = '\n'.join(current_content)
                        current_content = []
                    
                    # Extract axis name
                    axis_name = line.replace('###', '').split(':', 1)[0].strip()
                    current_axis = clean_text(axis_name)
                    
                    # Check if there's content after the colon
                    if ':' in line:
                        rest_content = line.split(':', 1)[1].strip()
                        if rest_content:
                            current_content.append(clean_text(rest_content))
                
                # Handle bullet points or other content lines
                elif current_axis and (line.startswith('-') or line.startswith('•') or not line.startswith('#')):
                    cleaned_line = clean_text(line)
                    if cleaned_line.startswith('-') or cleaned_line.startswith('•'):
                        cleaned_line = cleaned_line[1:].strip()
                    
                    # If it mentions "Left Image" or "Right Image", it's content not a new axis
                    if cleaned_line and not cleaned_line.startswith('###'):
                        current_content.append(cleaned_line)
            
            # Add the last axis
            if current_axis and current_content:
                axes[current_axis] = '\n'.join(current_content)
                
            # Return results if we found any axes
            if axes:
                return axes
        
        # Generic fallback parser that handles most formats
        axes = {}
        current_axis = None
        current_content = []
        
        # If we're still here, try a more generic approach
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            # Skip intro text that may confuse the parser
            if any(intro in line.lower() for intro in ["certainly", "breakdown", "here is", "using the specified"]):
                continue
            # Skip standalone bullet points
            if line in ["•", "-"]:
                continue
            lines.append(line)
        
        # Process each line with a more flexible approach
        for i, line in enumerate(lines):
            if not line:
                continue
            
            # Skip numbered list markers at the beginning of a line
            if re.match(r'^\d+\.', line):
                line = re.sub(r'^\d+\.', '', line).strip()
            
            # Look for axis names in various formats
            # Case 1: Line starts with a bold axis name
            if re.match(r'^\*\*[A-Za-z /]+\*\*\s*:?', line):
                axis_match = re.match(r'^\*\*([A-Za-z /]+)\*\*\s*:?', line)
                if axis_match:
                    # Save previous axis content if any
                    if current_axis and current_content:
                        axes[current_axis] = '\n'.join(current_content)
                        current_content = []
                    
                    current_axis = axis_match.group(1)
                    # Get content after the axis name if any
                    content_part = line[axis_match.end():].strip()
                    if content_part.startswith(':'):
                        content_part = content_part[1:].strip()
                    if content_part:
                        current_content.append(clean_text(content_part))
                    continue
            
            # Case 2: Line starts with a plain axis name followed by colon
            elif ':' in line and not line.startswith('-') and not line.startswith('•'):
                # But make sure this isn't a "Left Image:" or "Right Image:" line
                parts = line.split(':', 1)
                potential_axis = clean_text(parts[0])
                
                # Only treat as an axis if it's not a Left/Right Image line
                if potential_axis not in ["Left Image", "Right Image", "Left", "Right"]:
                    # Save previous axis content
                    if current_axis and current_content:
                        axes[current_axis] = '\n'.join(current_content)
                        current_content = []
                    
                    current_axis = potential_axis
                    # Get content after colon
                    if len(parts) > 1 and parts[1].strip():
                        current_content.append(clean_text(parts[1]))
                    continue
            
            # Case 3: Line is a bullet point under current axis
            if current_axis and (line.startswith('-') or line.startswith('•')):
                line_content = line[1:].strip()  # Remove bullet marker
                # Check if this actually contains a "Left/Right Image:" pattern
                if ":" in line_content:
                    parts = line_content.split(':', 1)
                    # If left/right image, treat as content not axis
                    if clean_text(parts[0]) in ["Left Image", "Right Image", "Left", "Right"]:
                        current_content.append(clean_text(line_content))
                    else:
                        # This might be a secondary axis in bullet format, add as content
                        current_content.append(clean_text(line_content))
                else:
                    # Regular bullet point content
                    current_content.append(clean_text(line_content))
                continue
            
            # Case 4: Any other line under current axis
            if current_axis:
                current_content.append(clean_text(line))
        
        # Don't forget the last axis
        if current_axis and current_content:
            axes[current_axis] = '\n'.join(current_content)
            
        # FINAL SANITY CHECKS
        
        # Check 1: Remove entries that look like introduction text
        cleaned_axes = {}
        for axis, content in axes.items():
            if any(intro in axis.lower() for intro in ["breakdown", "here", "certainly", "provided"]):
                continue
            cleaned_axes[axis] = content
        
        # Check 2: If all we have are "Left Image" and "Right Image" keys, it's not parsed correctly
        if all(key in ["Left Image", "Right Image", "Left", "Right"] for key in cleaned_axes.keys()):
            cleaned_axes = {}
            
        # Check 3: If we still don't have useful axes, try the section-based approach
        if not cleaned_axes:
            # This approach doesn't rely on known axis names, but rather on the structure
            # First, identify possible section headers
            section_headers = []
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Check if this line might be a section header (with various formats)
                is_header = False
                
                # Check for markdown headers: ### Something
                if line.startswith('###'):
                    header_name = line.replace('###', '').split(':', 1)[0].strip()
                    is_header = True
                
                # Check for numbered headers: 1. Something or 1. **Something**
                elif re.match(r'^\d+\.\s+', line):
                    # Remove the number and any markdown
                    header_name = re.sub(r'^\d+\.\s+', '', line)
                    header_name = header_name.replace('**', '').split(':', 1)[0].strip()
                    is_header = True
                
                # Check for bold headers: **Something**
                elif line.startswith('**') and '**' in line[2:]:
                    header_name = line.replace('**', '').split(':', 1)[0].strip()
                    is_header = True
                
                # If this line seems to be a header and not a subitem like "Left Image"
                if is_header and header_name and header_name not in ["Left Image", "Right Image", "Left", "Right"]:
                    section_headers.append(header_name)
            
            # Now extract content between these headers
            if section_headers:
                current_section = None
                section_content = []
                
                for line in text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this line contains one of our identified section headers
                    found_header = None
                    for header in section_headers:
                        # Look for the header in various formats
                        patterns = [
                            r'###\s*' + re.escape(header),
                            r'\d+\.\s+' + re.escape(header),
                            r'\d+\.\s+\*\*' + re.escape(header) + r'\*\*',
                            r'\*\*' + re.escape(header) + r'\*\*'
                        ]
                        
                        for pattern in patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                found_header = header
                                break
                        
                        if found_header:
                            break
                    
                    if found_header:
                        # Save previous section content if it exists
                        if current_section and section_content:
                            cleaned_axes[current_section] = '\n'.join([clean_text(s) for s in section_content])
                            section_content = []
                        
                        current_section = found_header
                        
                        # Check if there's content on the same line after the header
                        if ':' in line:
                            content_part = line.split(':', 1)[1].strip()
                            if content_part:
                                section_content.append(content_part)
                    
                    # If not a header and we have a current section, add to content
                    elif current_section:
                        # Skip empty bullet points
                        if line in ["•", "-"]:
                            continue
                        
                        # Clean up bullet points and formatting
                        if line.startswith('-') or line.startswith('•'):
                            line = line[1:].strip()
                        
                        # Only add non-empty lines
                        if line.strip():
                            section_content.append(line)
                
                # Don't forget to add the last section
                if current_section and section_content:
                    # Clean content and handle Left/Right formatting
                    cleaned_content = [clean_text(s) for s in section_content if clean_text(s)]
                    
                    # Process content to handle "Left" and "Right" subheaders
                    final_content = []
                    i = 0
                    while i < len(cleaned_content):
                        line = cleaned_content[i]
                        
                        # Skip empty lines or standalone bullet points
                        if not line or line == "•" or line == "-":
                            i += 1
                            continue
                            
                        # Look for Left/Right markers
                        left_match = re.match(r'^(?:Left|Left Image)(?::|-)?\s*(.*)', line, re.IGNORECASE)
                        right_match = re.match(r'^(?:Right|Right Image)(?::|-)?\s*(.*)', line, re.IGNORECASE)
                        
                        if left_match and i+1 < len(cleaned_content):
                            # Check if the next line is a Right match
                            next_line = cleaned_content[i+1]
                            next_right_match = re.match(r'^(?:Right|Right Image)(?::|-)?\s*(.*)', next_line, re.IGNORECASE)
                            
                            if next_right_match:
                                # Combine the Left and Right entries
                                left_content = left_match.group(1)
                                right_content = next_right_match.group(1)
                                final_content.append(f"Left: {left_content}")
                                final_content.append(f"Right: {right_content}")
                                i += 2  # Skip both lines
                                continue
                        
                        # If it's not a combined Left/Right, just add the line
                        final_content.append(line)
                        i += 1
                    
                    cleaned_axes[current_section] = '\n'.join(final_content)
        
        # If all else fails, try a pattern-based approach that doesn't rely on specific axis names
        if not cleaned_axes:
            # Look for sections based on formatting patterns like headers, numbers, etc.
            patterns = [
                r'(?:^|\n)###\s*([A-Za-z /]+)(?:\s*:|\s*$)(.*?)(?=\n###|\n\d+\.|\n\*\*|\Z)',  # Markdown headers
                r'(?:^|\n)\d+\.\s+\*\*([A-Za-z /]+)\*\*(?:\s*:|\s*$)(.*?)(?=\n###|\n\d+\.|\n\*\*|\Z)',  # Numbered bold items
                r'(?:^|\n)\d+\.\s+([A-Za-z /]+)(?:\s*:|\s*$)(.*?)(?=\n###|\n\d+\.|\n\*\*|\Z)',  # Numbered items
                r'(?:^|\n)\*\*([A-Za-z /]+)\*\*(?:\s*:|\s*$)(.*?)(?=\n###|\n\d+\.|\n\*\*|\Z)'  # Bold items
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.DOTALL)
                for header, content in matches:
                    header = clean_text(header)
                    # Skip headers that are clearly not axis names
                    if any(intro in header.lower() for intro in ["breakdown", "here", "certainly", "provided"]):
                        continue
                    if header in ["Left Image", "Right Image", "Left", "Right"]:
                        continue
                    
                    # Clean up content
                    content_lines = []
                    for line in content.split('\n'):
                        line = line.strip()
                        if line:
                            # Handle bullet points
                            if line.startswith('-') or line.startswith('•'):
                                line = line[1:].strip()
                            # Strip markdown and extra formatting
                            line = clean_text(line)
                            # Skip empty lines after cleaning
                            if line:
                                content_lines.append(line)
                    
                    if content_lines:
                        # Process content to handle "Left" and "Right" subheaders
                        # This will combine them properly instead of treating them as separate entries
                        final_content = []
                        i = 0
                        while i < len(content_lines):
                            line = content_lines[i]
                            
                            # Skip empty lines or standalone bullet points
                            if not line or line == "•" or line == "-":
                                i += 1
                                continue
                                
                            # Look for Left/Right markers
                            left_match = re.match(r'^(?:Left|Left Image)(?::|-)?\s*(.*)', line, re.IGNORECASE)
                            right_match = re.match(r'^(?:Right|Right Image)(?::|-)?\s*(.*)', line, re.IGNORECASE)
                            
                            if left_match and i+1 < len(content_lines):
                                # Check if the next line is a Right match
                                next_line = content_lines[i+1]
                                next_right_match = re.match(r'^(?:Right|Right Image)(?::|-)?\s*(.*)', next_line, re.IGNORECASE)
                                
                                if next_right_match:
                                    # Combine the Left and Right entries
                                    left_content = left_match.group(1)
                                    right_content = next_right_match.group(1)
                                    final_content.append(f"Left: {left_content}")
                                    final_content.append(f"Right: {right_content}")
                                    i += 2  # Skip both lines
                                    continue
                            
                            # If it's not a combined Left/Right, just add the line
                            final_content.append(line)
                            i += 1
                        
                        cleaned_axes[header] = '\n'.join(final_content)
                
                # If we found sections with this pattern, no need to try others
                if cleaned_axes:
                    break
                
        return cleaned_axes
        
    def combine_axes_into_single_concept(self, axes):
        """Synthesize a unified concept from multiple conceptual axes."""
        description = "\n".join([f"{axis}: {concept}" for axis, concept in axes.items()])
        
        system_message = "You are an expert at synthesizing abstract concepts from multidimensional conceptual descriptions."
        prompt = f"Given this detailed breakdown of an image across multiple conceptual axes, please create a single unified concept that captures the core meaning and message implied by all these axes combined:\n\n{description}"
        
        return self._generate_completion(prompt, system_message)
    
    def run_mci3(self, corpus, depth):
        """Run multiple iterations of orthogonal concept generation with revector approach."""
        history = [corpus]
        for _ in range(depth):
            combined_corpus = " + ".join(history)
            orthogonal_concept = self.mci_v1(combined_corpus)
            history.append(orthogonal_concept)
        return history
    
    def generate_recursive_image(self, concept):
        """Generate an image representing a concept using DALL-E."""
        if self.provider == ModelProvider.OPENAI:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=f"Create an image representing the concept: {concept}",
                size="1024x1024",
                n=1
            )
            return response.data[0].url
        else:
            raise ValueError("Image generation currently only supported with OpenAI")
    
    def process_image_to_recursive_inversion(self, image_url, depth=5):
        """Process an image through concept extraction, unification, inversion, and image generation."""
        concepts_text = self.extract_concepts_from_image(image_url)
        axes = self.parse_axes(concepts_text)
        
        unified_concept = self.combine_axes_into_single_concept(axes)
        
        final_concepts = self.run_mci3(unified_concept, depth)
        
        final_concept = final_concepts[-1]
        image_url = self.generate_recursive_image(final_concept)
        
        return {
            "initial_axes": axes,
            "unified_concept": unified_concept,
            "mci3_concepts": final_concepts,
            "final_image_url": image_url
        }