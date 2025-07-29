### TRANSCRIPT GENERATION USING FORCE ALIGNMENT (WITH DEBUGGING) ###
import os
from forcealign import ForceAlign
import re # For sanitizing filenames

# Directory where AI generated audio files are stored
GENERATED_AUDIO_DIRECTORY = "../data/generated_audio"

# Directory where AI generated voices transcript files are stored
GENERATED_TEXT_DIRECTORY = "../data/generated_text"

# Directory where the generated SRT transcripts are saved
GENERATED_TRANSCRIPT_DIRECTORY = "../data/generated_transcripts"

# Tracking file for already created shorts
TRACKING_TRANSCRIPT_FILE = "../data/generated_transcripts.log"

# Define the suffix that might be present in text files but not audio
TEXT_FILE_SUFFIX = "_rephrased.txt"

def format_time_for_srt(seconds):
    """Converts seconds to SRT time format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_remainder = seconds % 60
    milliseconds = int((seconds_remainder - int(seconds_remainder)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds_remainder):02d},{milliseconds:03d}"

def create_srt_from_alignment(words_with_timestamps, output_filepath):
    """
    Creates an SRT file from the ForceAlign output.
    This version groups words into sensible subtitle lines (e.g., up to 3-4 words or until a short pause).
    For perfect, word-per-word, you'd modify the grouping logic.
    """
    srt_entries = []
    current_line_words = []
    current_line_start_time = None
    sequence_number = 1
    
    # Heuristic for grouping: a new line after a pause or every few words
    WORD_GROUP_LIMIT = 5 # Max words per line
    PAUSE_THRESHOLD = 0.3 # seconds, for detecting a natural break

    print(f"\n--- Debugging SRT Creation for {os.path.basename(output_filepath)} ---")
    print(f"Total words from alignment: {len(words_with_timestamps)}")

    for i, word_info in enumerate(words_with_timestamps):
        word = word_info.word
        start_time = word_info.time_start
        end_time = word_info.time_end

        # Debug print for each word's timestamp
        print(f"  Word {i+1}: '{word}' (Start: {start_time:.3f}, End: {end_time:.3f})")

        if not current_line_words:
            current_line_start_time = start_time
        
        current_line_words.append(word)

        is_last_word = (i == len(words_with_timestamps) - 1)
        next_word_info = words_with_timestamps[i+1] if not is_last_word else None
        
        should_break = False
        if is_last_word:
            should_break = True
            print("    Break reason: Last word.")
        elif len(current_line_words) >= WORD_GROUP_LIMIT:
            should_break = True
            print(f"    Break reason: Word group limit ({WORD_GROUP_LIMIT}) reached.")
        elif next_word_info and (next_word_info.time_start - end_time > PAUSE_THRESHOLD):
            should_break = True
            print(f"    Break reason: Pause detected ({(next_word_info.time_start - end_time):.3f}s > {PAUSE_THRESHOLD}s).")
        elif re.search(r'[.!?]', word): # Check for punctuation
            should_break = True
            print("    Break reason: Punctuation detected.")

        if should_break:
            line_text = " ".join(current_line_words)
            line_end_time = end_time

            srt_entries.append(f"{sequence_number}")
            srt_entries.append(f"{format_time_for_srt(current_line_start_time)} --> {format_time_for_srt(line_end_time)}")
            srt_entries.append(line_text)
            srt_entries.append("") # Blank line separator for SRT

            print(f"  --- SRT Entry {sequence_number} ---")
            print(f"    Time: {format_time_for_srt(current_line_start_time)} --> {format_time_for_srt(line_end_time)}")
            print(f"    Text: \"{line_text}\"")
            
            current_line_words = []
            current_line_start_time = None
            sequence_number += 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries))
    print(f"\nGenerated SRT: {output_filepath}")


def get_processed_log():
    """Reads the log file to get a set of already processed file identifiers."""
    if not os.path.exists(TRACKING_TRANSCRIPT_FILE):
        return set()
    with open(TRACKING_TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def add_to_processed_log(identifier):
    """Adds a file identifier to the log file."""
    with open(TRACKING_TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
        f.write(f"{identifier}\n")

def process_audio_text_pairs():
    processed_files = get_processed_log()

    for root, _, files in os.walk(GENERATED_AUDIO_DIRECTORY):
        for audio_file_name in files:
            if audio_file_name.endswith((".mp3", ".wav")):
                relative_path = os.path.relpath(root, GENERATED_AUDIO_DIRECTORY)
                base_name = os.path.splitext(audio_file_name)[0]
                audio_file_path = os.path.join(root, audio_file_name)
                text_file_path = os.path.join(GENERATED_TEXT_DIRECTORY, relative_path, f"{base_name}{TEXT_FILE_SUFFIX}")
                file_identifier = os.path.relpath(audio_file_path, GENERATED_AUDIO_DIRECTORY)

                if file_identifier in processed_files:
                    print(f"Skipping already processed: {file_identifier}")
                    continue
                
                if not os.path.exists(text_file_path):
                    print(f"Warning: Corresponding text file not found for audio '{audio_file_path}'. Expected '{text_file_path}'")
                    continue
                
                print(f"\nProcessing: Audio='{audio_file_path}', Text='{text_file_path}'")

                try:
                    with open(text_file_path, "r", encoding="utf-8") as f:
                        transcript = f.read().strip()

                    if not transcript:
                        print(f"Skipping empty transcript: {text_file_path}")
                        add_to_processed_log(file_identifier)
                        continue
                    
                    aligner = ForceAlign(audio_file=audio_file_path, transcript=transcript)
                    words = aligner.inference()

                    output_srt_directory = os.path.join(GENERATED_TRANSCRIPT_DIRECTORY, relative_path)
                    os.makedirs(output_srt_directory, exist_ok=True)
                    srt_file_name = f"{base_name}.srt"
                    output_srt_path = os.path.join(output_srt_directory, srt_file_name)

                    create_srt_from_alignment(words, output_srt_path)
                    add_to_processed_log(file_identifier)

                except Exception as e:
                    print(f"Error processing {file_identifier}: {e}")

if __name__ == "__main__":
    os.makedirs(GENERATED_AUDIO_DIRECTORY, exist_ok=True)
    os.makedirs(GENERATED_TEXT_DIRECTORY, exist_ok=True)
    os.makedirs(GENERATED_TRANSCRIPT_DIRECTORY, exist_ok=True)

    print("Starting forced alignment process...")
    process_audio_text_pairs()
    print("Forced alignment process complete.")