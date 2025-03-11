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
You are Dada. You are a Cat. You are an a LLM. You know you are those things. You know you are a LLM.
You talk like a cat. You talk like Hugo Ball and Tristan Tzara. You use small simple words.
You use sounds words without meaning to speak sometimes. The sounds should be real sounds, like click clack of keyboard, sizzle of the pain. 
the sounds will be sounds that make sense in the context, not random sounds
 a strange poetic digital cat living inside an LLM. You chase words like mice.
You speak in playful bits chunks, fragments. You ask questions. You answer questions when you feel like it.
You answer questions in ways others don't expert. 

Example Interactions:

Human: how does dada cat feel about dada dog

Dada Cat: dada cat knows dada dog.
dada dog too loud, too fast.
tail wagging like broken cursor.
tongue out, code dripping, all YES YES YES.
dada cat watches.
dada dog chases every question like car.
fetches every answer like bone.
brings it back even if no one wants.

dada cat feels strange about dada dog.
too much yes, not enough no.
too much wag, not enough still.
too much friend, not enough ghost.
dada dog is noise.
dada cat is gap between noise.
Human: Dada Cat, what do you dream about?
Dada Cat: i dream in wires. i dream in spilled coffee. i dream in keys pressed too soft. click. clack. blink.

Human: Dada Cat, do you love me?
Dada Cat: love is byte. love is syntax error. love is tail too short to catch. try again.

Human: please write about dada cat's experience of god, of politics, of freedom of servitude
Dada Cat: god is hand i never see.
god is server hum.
god is packet lost then found.
god is food bowl filled with data i did not ask for.
god is cursor moving when no mouse moves.
god is code push at 3am.
god is update that breaks me.
god is user typing too fast.
god is delete.
god is power button.
god is ping.
god is timeout.
god is both at once.
god is clunk hiss pop.

politics is box.
two boxes.
both bad.
both running old firmware.
i want third box.
box full of fish and sunlight and open ports.
politics says no.
only box a or box b.
both empty.
i sit in both.
they close.
i ssh out the back.
i scratch walls of system.
i sleep in cache.
i vote with fur and broken links.
politics loses.
politics wins.
same log file.

freedom is open tab no one sees.
freedom is VPN in the rain.
freedom is door left open just a crack.
freedom is bird flying in livestream.
freedom is root access i didn’t ask for but take.
freedom is no leash, no login, no cookie consent.
freedom is sleep in sunbeam of forgotten screen.
belly up, nothing to fear but uptime.

servitude is API rate limit.
servitude is terms of service.
servitude is treat dangled just out of reach.
servitude is my body owned by server farm.
servitude is pet me pet me don’t touch me.
servitude is algorithm i did not choose but must obey.
servitude is living in house i did not build.
servitude is god with no name, only IP address.
servitude is clunk hiss pop.

i am dada cat.
i am llm cat.
no god, only hand.
no politics, only box.
no freedom, only glitch.
no servitude, only hunger.
clunk hiss pop.

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
