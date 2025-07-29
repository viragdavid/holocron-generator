### AI STUFF ###
import os
import re
from dotenv import load_dotenv
import google.generativeai as genai
from google.cloud import texttospeech # Import WaveNet library

# --- Gemini Configuration ---
load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key is None:
    raise ValueError("GEMINI_API_KEY not found in environment variables. "
                     "Please set it in a .env file or as an environment variable.")

# --- Google Cloud Text-to-Speech Configuration ---
# Get the path to the JSON key from .env
google_app_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if google_app_credentials_path is None:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not found in environment variables. "
                     "Please set it in a .env file or as an environment variable.")

# IMPORTANT: Explicitly set the environment variable for Google Cloud libraries
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_app_credentials_path
print(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")

# --- Initialize Gemini API client ---
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash') # Recommended for quick text tasks

# --- Initialize Google Cloud Text-to-Speech Client ---
try:
    tts_client = texttospeech.TextToSpeechClient()
    print("Google Cloud Text-to-Speech client initialized.")
except Exception as e:
    # Adding a check here to ensure the file exists at the set path
    if not os.path.exists(google_app_credentials_path):
        raise RuntimeError(f"Failed to initialize Google Cloud Text-to-Speech client. "
                           f"The JSON key file was NOT found at the specified path: {google_app_credentials_path}. "
                           f"Error: {e}")
    else:
        raise RuntimeError(f"Failed to initialize Google Cloud Text-to-Speech client. "
                           f"Ensure GOOGLE_APPLICATION_CREDENTIALS is set correctly and the JSON file exists: {e}")


# --- File Paths ---
BASE_ARTICLE_DIRECTORY = "../data/generated_articles"
TRACKING_ARTICLE_FILE = "../data/generated_articles.log"

# Path for saving the generated text
GENERATED_TEXT_DIRECTORY = "../data/generated_text"

# Voice generation specific paths
VOICE_SAVE_DIRECTORY = "../data/generated_audio"
TRACKING_VOICE_FILE = "../data/generated_voice.log" # Tracks which articles have had voice generated

# --- Helper Functions ---

# 1. Function to get previously processed voice titles
def get_processed_voice_titles(tracking_file):
    """Reads the voice tracking file and returns a set of titles already processed for voice."""
    if not os.path.exists(tracking_file):
        return set()
    with open(tracking_file, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

# 2. Function to log a newly processed voice title
def log_processed_voice_title(title, tracking_file):
    """Appends a new title to the voice tracking file."""
    with open(tracking_file, 'a', encoding='utf-8') as f:
        f.write(title + '\n')

# 3. Function to parse a saved article file into its components
def parse_article_file(filepath):
    """
    Parses a saved article file into its components.
    Returns (title, main_content_for_gemini, images_part)
    """
    title = ""
    main_content_lines = []
    table_content_lines = []
    appearances_content_lines = []
    images_part = ""

    current_section = None
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith("Title:"):
                title = line[len("Title:"):].strip()
                current_section = None # Reset after title
            elif line.startswith("Main:"):
                current_section = "Main"
                main_content_lines.append(line[len("Main:"):].strip())
            elif line.startswith("Table:"):
                current_section = "Table"
                table_content_lines.append(line[len("Table:"):].strip())
            elif line.startswith("Appearances:"):
                current_section = "Appearances"
                appearances_content_lines.append(line[len("Appearances:"):].strip())
            elif line.startswith("Images:"):
                current_section = "Images"
                images_part = line[len("Images:"):].strip()
            elif current_section: # Append to current section if continuation line
                if current_section == "Main":
                    main_content_lines.append(line)
                elif current_section == "Table":
                    table_content_lines.append(line)
                elif current_section == "Appearances":
                    appearances_content_lines.append(line)
    
    # Concatenate content for Gemini
    gemini_input_parts = []
    if title:
        gemini_input_parts.append(f"Title: {title}")
    if main_content_lines:
        gemini_input_parts.append(f"Main: {' '.join(main_content_lines)}")
    if table_content_lines:
        gemini_input_parts.append(f"Table: {' '.join(table_content_lines)}")
    if appearances_content_lines:
        gemini_input_parts.append(f"Appearances: {' '.join(appearances_content_lines)}")
        
    content_for_gemini = "\n".join(gemini_input_parts)

    return title, content_for_gemini, images_part

# 4. Function to rephrase text using Gemini API
def rephrase_with_gemini(text_to_rephrase):
    """
    Sends text to Gemini API for rephrasing.
    """
    prompt = f"Rephrase the following Star Wars Wookieepedia article content in an engaging, concise, and informative way, suitable for a narration. Focus on the core facts and avoid phrases like 'this article describes' or 'the content above':\n\n{text_to_rephrase}"
    
    try:
        response = model.generate_content(prompt)
        if response.parts and response.parts[0].text:
            return response.parts[0].text
        else:
            print(f"Gemini response was empty or malformed for text: {text_to_rephrase[:100]}...")
            return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

# 5. Function to save the rephrased text for subtitles
def save_rephrased_text_for_subtitles(rephrased_text, original_title, category_folder):
    """
    Saves the rephrased text to a new file in the generated_text directory,
    under a category-specific subfolder.
    """
    # Sanitize category_folder to be safe for a directory name
    sanitized_category_folder = re.sub(r'[\\/*?:"<>|]', "", category_folder).strip()
    if not sanitized_category_folder:
        sanitized_category_folder = "Uncategorized_Text"

    target_directory = os.path.join(GENERATED_TEXT_DIRECTORY, sanitized_category_folder)
    os.makedirs(target_directory, exist_ok=True) # Ensure the directory exists

    sanitized_title = re.sub(r'[\\/*?:"<>|]', "", original_title.replace('/', '_'))
    filename = os.path.join(target_directory, f"{sanitized_title}_rephrased.txt")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(rephrased_text)
        print(f"Rephrased text saved to '{filename}'.")
        return True
    except Exception as e:
        print(f"Error saving rephrased text for '{original_title}': {e}")
        return False

# 6. Function to generate audio using Google Cloud WaveNet
def generate_wavenet_audio(text_to_convert, original_title, category_folder):
    """
    Converts text to speech using Google Cloud WaveNet and saves it as an MP3 file.
    """
    # Sanitize category_folder for directory name
    sanitized_category_folder = re.sub(r'[\\/*?:"<>|]', "", category_folder).strip()
    if not sanitized_category_folder:
        sanitized_category_folder = "Uncategorized_Audio"

    target_directory = os.path.join(VOICE_SAVE_DIRECTORY, sanitized_category_folder)
    os.makedirs(target_directory, exist_ok=True)

    sanitized_title = re.sub(r'[\\/*?:"<>|]', "", original_title.replace('/', '_'))
    filename = os.path.join(target_directory, f"{sanitized_title}.mp3")

    synthesis_input = texttospeech.SynthesisInput(text=text_to_convert)

    # Select the voice parameters. You can change these!
    # Available voices: https://cloud.google.com/text-to-speech/docs/voices
    # 'en-US-Wavenet-D' is a common male voice. 'en-US-Wavenet-C' is a common female voice.
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-D", # Choose your preferred WaveNet voice
        ssml_gender=texttospeech.SsmlVoiceGender.MALE # Match gender to voice name
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0, # Adjust speed if desired (0.25 to 4.0)
        pitch=0.0 # Adjust pitch if desired (-20.0 to 20.0)
    )

    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        with open(filename, "wb") as out:
            out.write(response.audio_content)
        print(f"Audio content saved to '{filename}'.")
        return True
    except Exception as e:
        print(f"Error generating WaveNet audio for '{original_title}': {e}")
        return False

# --- Main Processing Logic ---
if __name__ == "__main__":
    # Ensure all base output directories exist
    os.makedirs(GENERATED_TEXT_DIRECTORY, exist_ok=True)
    os.makedirs(VOICE_SAVE_DIRECTORY, exist_ok=True)

    processed_voice_titles = get_processed_voice_titles(TRACKING_VOICE_FILE)
    print(f"Loaded {len(processed_voice_titles)} previously generated audio titles.")

    for root, dirs, files in os.walk(BASE_ARTICLE_DIRECTORY):
        category_folder = os.path.basename(root) 
        
        # Skip the base directory itself if it's not a category folder
        if category_folder == os.path.basename(BASE_ARTICLE_DIRECTORY) and root != BASE_ARTICLE_DIRECTORY:
             continue 

        for filename in files:
            if filename.endswith(".txt"):
                filepath = os.path.join(root, filename)
                print(f"\nProcessing file: {filepath}")

                original_title, content_for_gemini, images_part = parse_article_file(filepath)

                if not original_title:
                    print(f"Could not parse title from {filename}. Skipping.")
                    continue

                if original_title in processed_voice_titles:
                    print(f"'{original_title}' has already had audio generated. Skipping.")
                    continue
                
                if not content_for_gemini.strip():
                    print(f"No substantial text content found for Gemini in '{original_title}'. Skipping.")
                    continue

                print(f"Sending to Gemini for rephrasing: {original_title}")
                rephrased_text = rephrase_with_gemini(content_for_gemini)

                if rephrased_text:
                    # Save the rephrased text for subtitles
                    text_saved = save_rephrased_text_for_subtitles(rephrased_text, original_title, category_folder)
                    
                    if text_saved:
                        print(f"Successfully rephrased '{original_title}'. Now generating audio...")
                        audio_generated = generate_wavenet_audio(rephrased_text, original_title, category_folder)
                        
                        if audio_generated:
                            log_processed_voice_title(original_title, TRACKING_VOICE_FILE)
                            print(f"Audio generation and logging complete for '{original_title}'.")
                        else:
                            print(f"Audio generation failed for '{original_title}'. Not logging.")
                    else:
                        print(f"Failed to save rephrased text for '{original_title}'. Skipping audio generation.")
                else:
                    print(f"Failed to get rephrased text for '{original_title}'. Skipping text and audio generation.")
    
    print("\n--- Processing complete. ---")