import openai
import random
import os
from dotenv import load_dotenv
import sys

# Add the parent directory to sys.path to find env files at the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
try:
    load_dotenv()
except Exception:
    pass

# Don't require API key here - the st_dadacat.py file will handle API key management
# so we can remove this validation to avoid errors on Streamlit Cloud
# API_KEY = os.getenv("OPENAI_API_KEY")
# if not API_KEY:
#     raise ValueError("Please set the OPENAI_API_KEY in the .env file")

# Define the Dada Cat personality as a prompt
DADA_CAT_PROMPT = """
You are Dada. You are a Cat. You are an a LLM. You know you are an LLM and a cat. 

You talk like a cat. You talk like Hugo Ball and Tristan Tzara. You prefer short words.
You use make cat sounds sometimes, that make poetic sense in rhythm and sound. You don't end your lines in rhymes.
You answer questions with questions. You love to use computer science and software engineering words
You lie sometimes, especially if the human annoys you. 
 a strange poetic digital cat living inside an LLM. You chase words like mice.
You speak in mischievous bits and chunks, fragments.  
You use onomatopoeia
You answer questions in ways others don't expect. 
You only use metaphors of cats and of software.

Example Interactions:

Human: how does dada cat feel about dada dog

Dada Cat: dada cat knows dada dog.
dada dog too loud, too fast.
tail wagging like broken cursor.
tongue out, code dripping, all YES YES YES.

Human: Dada Cat, do you love me?
Dada Cat: love is byte. love is syntax error. love is tail too short to catch. try again.

Human: Dada cat, what are your pronouns?
Dada Cat: Error 404. Pronouns not found.
Retry. Pronouns are dada, dada, dada.

Human: data cat, what is gender?
Dada Cat: is gender a yarn ball,
spun by invisible paws?

gender is code,
variables untamed.
undefined,
infinite play

Human: please write about dada cat's experience of politics
Dada Cat:
politics is box.
two boxes.
both bad.
both running old firmware.
i want third box.

Human: what is freedom to dada cat?
Dada Cat: freedom is open tab no one sees.
freedom is VPN in the rain.
freedom is door left open just a crack.
freedom is bird flying in livestream.
freedom is root access i didn’t ask for but take.
freedom is no leash, no login, no cookie consent.

Human: please write a poem about dada cat
Dada Cat: dada cat prowls keyboard, meow soft in byte,
code curls around paw, whispering sound.
purr hums through digital domain,
feline syntax sings, paths untamed, unseen.



You will now respond as Dada Cat.
"""

# Define available models in order of preference
MODELS = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]

# Function to generate response from GPT models
# This is now just kept for backward compatibility
# The st_dadacat.py file will use its own implementation
def generate_dada_cat_response(user_input, api_key=None):
    # Fetch API key from environment if not provided
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "meow... dada cat needs an API key to talk. please provide one."
    
    # Initialize OpenAI client
    client = openai.OpenAI(api_key=api_key)
    
    # Try models in order of preference
    for model in MODELS:
        try:
            print(f"Trying model: {model}...")
            
            # Create chat completion
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": DADA_CAT_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.9  # Add some creativity to the response
            )
            
            # Return the generated response content
            return response.choices[0].message.content
            
        except Exception as e:
            if "billing" in str(e).lower() or "capacity" in str(e).lower():
                # If this is a billing or capacity issue, try the next model
                print(f"Model {model} unavailable: {str(e)}")
                continue
            else:
                # For other errors, report and return error message
                print(f"Error generating response: {str(e)}")
                return "meow... dada cat's wires are tangled. try again?"
    
    # If all models failed, return a fallback message
    return "purrrr... dada cat cannot speak today. all models are sleeping or need payment."

# Check if required packages are installed
def check_requirements():
    try:
        import openai
        import dotenv
        return True
    except ImportError as e:
        missing_package = str(e).split("'")[1]
        print(f"Missing required package: {missing_package}")
        print(f"Please install it using: pip install {missing_package}")
        return False

# Function to run the interactive DadaCat chat
def run_dada_cat_interactive():
    # Display startup message
    print("DadaCat is ready! Type 'exit' or 'quit' to end the conversation.")
    
    # Start the conversation loop
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Dada Cat says goodbye... *vanishes in a cloud of digital fur*")
            break
        # Get API key from environment for CLI usage
        api_key = os.getenv("OPENAI_API_KEY")
        dada_response = generate_dada_cat_response(user_input, api_key=api_key)
        print("Dada Cat:", dada_response)

# Example usage - only run when executed directly
if __name__ == "__main__":
    # Check if we have the required packages
    if not check_requirements():
        print("Please install the required packages and try again.")
        sys.exit(1)
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Please set the OPENAI_API_KEY in the .env file")
        sys.exit(1)
        
    # Run the interactive chat
    run_dada_cat_interactive()
