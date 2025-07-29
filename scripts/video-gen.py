### VIDEO GENERATION SCRIPT WITH TRANSCRIPT (WITH DEBUGGING) ###
import os
import re
import random
import requests
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import glob
from urllib.parse import urlparse

# --- Configuration ---

# Main Minecraft parkour footage path
MINECRAFT_FOOTAGE_PATH = "../data/minecraft_footage/minecraft01.mp4"

# Directory where AI generated audio files are stored
GENERATED_AUDIO_DIRECTORY = "../data/generated_audio"

# Directory where AI generated article text files are stored (assuming same structure as audio)
GENERATED_ARTICLES_DIRECTORY = "../data/generated_articles"

# Directory where the generated SRT transcripts are saved (new)
GENERATED_TRANSCRIPT_DIRECTORY = "../data/generated_transcripts"

# Directory where the final YouTube Shorts will be saved
GENERATED_SHORTS_DIRECTORY = "../data/generated_shorts"

# Temporary directory for downloaded images
TEMP_IMAGE_DIRECTORY = "../data/temp_images"

# Tracking file for already created shorts
TRACKING_SHORTS_FILE = "../data/generated_shorts.log"

# Target resolution for YouTube Shorts (e.g., 1080x1920 for 9:16 aspect ratio)
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920 # For 9:16 aspect ratio

# --- Helper Functions for Tracking ---

# 1. Function to get previously processed shorts titles
def get_processed_shorts_titles(tracking_file):
    """Reads the shorts tracking file and returns a set of titles that have already had shorts created."""
    if not os.path.exists(tracking_file):
        return set()
    with open(tracking_file, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

# 2. Function to log a newly processed short title
def log_processed_short_title(title, tracking_file):
    """Appends a new title to the shorts tracking file."""
    with open(tracking_file, 'a', encoding='utf-8') as f:
        f.write(title + '\n')

# --- Image Handling Functions ---

# 1. Function to extract image URLs from the article content
def extract_image_urls_from_article(article_content):
    """Extracts image URLs from the 'Images:' line in the article content."""
    urls = []
    match = re.search(r"Images:\s*(.*)", article_content, re.IGNORECASE)
    if match:
        url_string = match.group(1).strip()
        potential_urls = url_string.split()
        for url in potential_urls:
            if url.startswith("http://") or url.startswith("https://"):
                urls.append(url)
    return urls

# 2. Function to download an image from a URL
def download_image(url, destination_folder):
    """Downloads an image from a URL to a specified folder and returns its local path."""
    os.makedirs(destination_folder, exist_ok=True)
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        if not filename:
            filename = "downloaded_image.png"

        base, ext = os.path.splitext(filename)
        if ext.lower() == '.svg':
            print(f"Skipping SVG image {url} as direct SVG support is not enabled.")
            return None # Skip SVG for now

        local_filepath = os.path.join(destination_folder, f"{base}_{random.randint(1000,9999)}{ext}")

        with open(local_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded image from {url} to {local_filepath}")
        return local_filepath
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image from {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during image download from {url}: {e}")
        return None
    
# 3. Function to create a temporary image from a URL
def clean_temp_images(directory):
    """Removes all files from the temporary image directory."""
    if os.path.exists(directory):
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting temporary file {file_path}: {e}")
        print(f"Cleaned temporary image directory: {directory}")

# --- Subtitle Handling Functions ---

def parse_srt(srt_filepath):
    """Parses an SRT file and returns a list of dictionaries, each containing
    'start', 'end', and 'text' for a subtitle entry."""
    
    subtitles = []
    current_block = []
    
    if not os.path.exists(srt_filepath):
        print(f"SRT file not found: {srt_filepath}")
        return subtitles

    with open(srt_filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: # Empty line indicates end of a subtitle block
                if current_block:
                    try:
                        sequence_number = int(current_block[0])
                        time_str = current_block[1]
                        start_time_str, end_time_str = time_str.split(' --> ')
                        
                        def srt_time_to_seconds(time_str_val):
                            parts = time_str_val.replace(',', '.').split(':')
                            if len(parts) == 3:
                                h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
                                return h * 3600 + m * 60 + s
                            return 0

                        start_seconds = srt_time_to_seconds(start_time_str)
                        end_seconds = srt_time_to_seconds(end_time_str)
                        text = " ".join(current_block[2:])
                        
                        subtitles.append({
                            'start': start_seconds,
                            'end': end_seconds,
                            'text': text
                        })
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not parse SRT block: {current_block}. Error: {e}")
                    current_block = []
            else:
                current_block.append(line)
        
        if current_block:
            try:
                sequence_number = int(current_block[0])
                time_str = current_block[1]
                start_time_str, end_time_str = time_str.split(' --> ')
                
                def srt_time_to_seconds(time_str_val):
                    parts = time_str_val.replace(',', '.').split(':')
                    if len(parts) == 3:
                        h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
                        return h * 3600 + m * 60 + s
                    return 0

                start_seconds = srt_time_to_seconds(start_time_str)
                end_seconds = srt_time_to_seconds(end_time_str)
                text = " ".join(current_block[2:])
                
                subtitles.append({
                    'start': start_seconds,
                    'end': end_seconds,
                    'text': text
                })
            except (ValueError, IndexError) as e:
                print(f"Warning: Could not parse final SRT block: {current_block}. Error: {e}")
    
    return subtitles

# --- Video Processing Function ---

# 1. Function to wrap text into multiple lines dynamically based on width
def dynamic_wrap_text(text, font, max_width):
    """
    Dynamically wraps text into multiple lines to fit within a max_width,
    returning a list of lines.
    """
    lines = []
    if not text:
        return lines

    words = text.split()
    current_line = []
    
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1,1)))

    for word in words:
        test_line = " ".join(current_line + [word])
        
        try:
            bbox = dummy_draw.textbbox((0,0), test_line, font=font)
            test_line_width = bbox[2] - bbox[0]
        except AttributeError:
            test_line_width, _ = dummy_draw.textsize(test_line, font=font)

        if test_line_width <= max_width:
            current_line.append(word)
        else:
            if not current_line:
                lines.append(word)
                current_line = []
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
    
    if current_line:
        lines.append(" ".join(current_line))

    return lines

# 2. Function to create a YouTube Short from Minecraft footage and AI audio
def create_youtube_short(
    audio_filepath,
    minecraft_footage_path,
    output_base_dir,
    article_title,
    category_folder,
    image_urls,
    srt_filepath,
    target_width=1080,
    target_height=1920
):
    """
    Creates a YouTube Short by combining a random segment of Minecraft footage with AI audio,
    cropping it to 9:16 aspect ratio, and saving it. Includes title text, image overlay, and subtitles.
    """
    clean_temp_images(TEMP_IMAGE_DIRECTORY)

    subtitles = parse_srt(srt_filepath)
    print(f"Loaded {len(subtitles)} subtitle entries from: {srt_filepath}")

    try:
        audio_clip = AudioFileClip(audio_filepath)
        audio_duration = audio_clip.duration
        
        print(f"Loaded audio: {os.path.basename(audio_filepath)} (Duration: {audio_duration:.2f}s)")

        main_video_clip = VideoFileClip(minecraft_footage_path)
        full_video_duration = main_video_clip.duration
        
        print(f"Loaded main video: {os.path.basename(minecraft_footage_path)} (Duration: {full_video_duration:.2f}s)")

        max_start_time_based_on_80_percent = full_video_duration * 0.8
        max_possible_start_time_for_audio_fit = full_video_duration - audio_duration

        actual_max_start_time = min(max_start_time_based_on_80_percent, max_possible_start_time_for_audio_fit)

        if actual_max_start_time < 0:
            print(f"Warning: Audio duration ({audio_duration:.2f}s) is longer than main video ({full_video_duration:.2f}s). Skipping {article_title}.")
            main_video_clip.close()
            audio_clip.close()
            return False
            
        if actual_max_start_time == 0 and full_video_duration > audio_duration:
            random_start_time = 0
            print(f"Video is short, starting at 0s.")
        else:
            random_start_time = random.uniform(0, actual_max_start_time)

        end_time = random_start_time + audio_duration
        
        if end_time > full_video_duration + 0.01:
             end_time = full_video_duration
             if (end_time - random_start_time) < audio_duration * 0.95:
                 print(f"Warning: Adjusted video end time. Clip might be slightly shorter than audio for {article_title}.")
                 
        print(f"Selected video segment: {random_start_time:.2f}s to {end_time:.2f}s (Clip duration: {(end_time - random_start_time):.2f}s)")

        video_clip = main_video_clip.subclip(random_start_time, end_time)
        video_clip = video_clip.set_audio(None)
        video_clip = video_clip.set_audio(audio_clip)

        original_width, original_height = video_clip.size
        target_aspect_ratio = target_width / target_height 
        original_aspect_ratio = original_width / original_height

        if original_aspect_ratio > target_aspect_ratio:
            new_width = int(original_height * target_aspect_ratio)
            x_center = original_width / 2
            x1 = int(x_center - new_width / 2)
            y1 = 0
            cropped_clip = video_clip.crop(x1=x1, y1=y1, width=new_width, height=original_height)
            print(f"Cropping width from {original_width} to {new_width} to fit 9:16.")
        else:
            new_height = int(original_width / target_aspect_ratio)
            y_center = original_height / 2
            y1 = int(y_center - new_height / 2)
            x1 = 0
            cropped_clip = video_clip.crop(x1=x1, y1=y1, width=original_width, height=new_height)
            print(f"Cropping height from {original_height} to {new_height} to fit 9:16.")

        final_clip = cropped_clip.resize(newsize=(target_width, target_height))
        print(f"Resized to final resolution: {final_clip.size[0]}x{final_clip.size[1]}")

        # --- Image Overlay Logic ---
        downloaded_image_paths = []
        if image_urls:
            print(f"Attempting to download {len(image_urls)} images for '{article_title}'...")
            for url in image_urls:
                path = download_image(url, TEMP_IMAGE_DIRECTORY)
                if path:
                    downloaded_image_paths.append(path)
            
            if downloaded_image_paths:
                image_duration_per_clip = audio_duration / len(downloaded_image_paths)
                print(f"Images will switch every {image_duration_per_clip:.2f} seconds.")
            else:
                print("No images successfully downloaded for overlay.")
        else:
            print("No image URLs found for overlay.")

        def draw_elements_on_frame(get_frame, t_in_clip):
            image_array = get_frame(t_in_clip)
            # Convert to RGBA for consistent handling of potential transparent overlays
            img_pil = Image.fromarray(image_array.astype('uint8'), 'RGB').convert("RGBA")
            draw = ImageDraw.Draw(img_pil)

            t_actual_transcript = t_in_clip
            
            if int(t_in_clip * 10) % 10 == 0:
                print(f"  Frame at t_in_clip: {t_in_clip:.2f}s (Time for subtitle lookup: {t_actual_transcript:.2f}s)")

            # --- TITLE DRAWING LOGIC ---
            font_path = "../data/fonts/sf-distant-galaxy-font/SfDistantGalaxy-0l3d.ttf"
            text_color = (255, 255, 255, 255) # White, fully opaque RGBA

            dynamic_fontsize = int(target_height * 0.055)
            try:
                title_font = ImageFont.truetype(font_path, dynamic_fontsize)
            except IOError:
                print(f"Warning: Could not load font '{font_path}' for title. Falling back to default.")
                title_font = ImageFont.load_default()

            max_title_line_width = int(target_width * 0.85)
            title_lines = dynamic_wrap_text(article_title, title_font, max_title_line_width)

            current_y_for_text = target_height * 0.02
            total_title_height = 0

            for line in title_lines:
                try:
                    bbox = draw.textbbox((0,0), line, font=title_font)
                    line_width = bbox[2] - bbox[0]
                    line_height = bbox[3] - bbox[1]
                except AttributeError:
                    line_width, line_height = draw.textsize(line, font=title_font)

                x_pos = (img_pil.width - line_width) / 2
                
                draw.text((x_pos, current_y_for_text), line, font=title_font, fill=text_color)
                
                current_y_for_text += line_height + int(target_height * 0.005)
                total_title_height += line_height + int(target_height * 0.005)

            # --- IMAGE OVERLAY LOGIC ---
            image_bottom_y = current_y_for_text
            
            if downloaded_image_paths:
                image_index = int(t_in_clip / image_duration_per_clip) % len(downloaded_image_paths)
                current_image_path = downloaded_image_paths[image_index]

                try:
                    img_pil_overlay = Image.open(current_image_path).convert("RGBA")

                    target_image_max_dim = int(target_width * 0.96)

                    orig_img_w, orig_img_h = img_pil_overlay.size

                    scale_w = target_image_max_dim / orig_img_w
                    scale_h = target_image_max_dim / orig_img_h
                    scale = min(scale_w, scale_h)

                    resized_img_w = int(orig_img_w * scale)
                    resized_img_h = int(orig_img_h * scale)
                    img_pil_overlay = img_pil_overlay.resize((resized_img_w, resized_img_h), Image.LANCZOS)

                    image_x_pos = (target_width - resized_img_w) / 2
                    image_y_pos = int((target_height * 0.02) + total_title_height + target_height * 0.03)
                    
                    # Paste the RGBA overlay onto the RGBA base image, using the overlay's alpha as a mask
                    img_pil.paste(img_pil_overlay, (int(image_x_pos), int(image_y_pos)), img_pil_overlay)
                    
                    image_bottom_y = image_y_pos + resized_img_h + int(target_height * 0.03)

                except Exception as img_e:
                    print(f"Error overlaying image {current_image_path} at time {t_in_clip:.2f}s: {img_e}")

            # --- SUBTITLE DRAWING LOGIC ---
            # Using same font size and style as title for consistency, but positioned at bottom
            subtitle_font_size = int(target_height * 0.05) # Slightly smaller than title for readability
            try:
                subtitle_font = ImageFont.truetype(font_path, subtitle_font_size)
            except IOError:
                print(f"Warning: Could not load font '{font_path}' for subtitle. Falling back to default.")
                subtitle_font = ImageFont.load_default()
            
            # Subtitle color: Bright yellow, fully opaque RGBA
            subtitle_fill_color = (255, 255, 0, 255) # Yellow, fully opaque RGBA

            current_subtitle_text = ""
            for sub in subtitles:
                if sub['start'] <= t_actual_transcript < sub['end']:
                    current_subtitle_text = sub['text']
                    if int(t_in_clip * 10) % 10 == 0:
                        print(f"    Subtitle found: \"{current_subtitle_text}\" (SRT range: {sub['start']:.2f}-{sub['end']:.2f})")
                    break
            
            if not current_subtitle_text and int(t_in_clip * 10) % 10 == 0:
                 print(f"    No subtitle found for actual transcript time {t_actual_transcript:.2f}s.")

            if current_subtitle_text:
                max_subtitle_line_width = int(target_width * 0.9)
                subtitle_lines = dynamic_wrap_text(current_subtitle_text, subtitle_font, max_subtitle_line_width)

                total_subtitle_height = 0
                dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1,1))) # Use RGBA for dummy
                for line in subtitle_lines:
                     try:
                        bbox = dummy_draw.textbbox((0,0), line, font=subtitle_font)
                        total_subtitle_height += (bbox[3] - bbox[1]) + int(target_height * 0.005)
                     except AttributeError:
                        _, line_h = dummy_draw.textsize(line, font=subtitle_font)
                        total_subtitle_height += line_h + int(target_height * 0.005)

                target_bottom_margin = int(target_height * 0.18)
                # Calculate the Y position for the bottom of the lowest subtitle line
                desired_y_for_bottom_of_subtitles = target_height - target_bottom_margin
                
                # Calculate the starting Y position for the *first* subtitle line
                current_y_for_subtitle = desired_y_for_bottom_of_subtitles - total_subtitle_height

                # Ensure subtitles don't overlap with images/title if they are too long
                subtitle_y_start_after_elements = image_bottom_y + int(target_height * 0.02) # Add a small buffer below image
                if current_y_for_subtitle < subtitle_y_start_after_elements:
                    current_y_for_subtitle = subtitle_y_start_after_elements
                    print(f"      Adjusted subtitle start Y to {current_y_for_subtitle:.0f} to avoid overlap.")

                for line in subtitle_lines:
                    try:
                        bbox = draw.textbbox((0,0), line, font=subtitle_font)
                        line_width = bbox[2] - bbox[0]
                        line_height = bbox[3] - bbox[1]
                    except AttributeError:
                        line_width, line_height = draw.textsize(line, font=subtitle_font)

                    x_pos = (img_pil.width - line_width) / 2
                    
                    if int(t_in_clip * 10) % 10 == 0:
                        print(f"      Drawing subtitle: '{line}' at X={x_pos}, Y={current_y_for_subtitle}, W={line_width}, H={line_height}, Color={subtitle_fill_color}")
                    
                    # Draw a solid black rectangle behind the subtitle for better contrast,
                    # ensuring it's opaque and drawn *before* the text.
                    padding_x = int(target_width * 0.01) # Small padding around text
                    padding_y = int(target_height * 0.005)
                    background_box_x1 = x_pos - padding_x
                    background_box_y1 = current_y_for_subtitle - padding_y
                    background_box_x2 = x_pos + line_width + padding_x
                    background_box_y2 = current_y_for_subtitle + line_height + padding_y
                    
                    # Ensure coordinates are within bounds
                    background_box_x1 = max(0, background_box_x1)
                    background_box_y1 = max(0, background_box_y1)
                    background_box_x2 = min(target_width, background_box_x2)
                    background_box_y2 = min(target_height, background_box_y2)

                    draw.rectangle([background_box_x1, background_box_y1, background_box_x2, background_box_y2],
                                   fill=(0, 0, 0, 180)) # Semi-transparent black background

                    draw.text((x_pos, current_y_for_subtitle), line, font=subtitle_font, fill=subtitle_fill_color)
                    current_y_for_subtitle += line_height + int(target_height * 0.005)
            
            # Convert back to RGB before returning to MoviePy
            return np.array(img_pil.convert("RGB"))

        final_clip_with_elements = final_clip.fl(draw_elements_on_frame)

        sanitized_category_folder = re.sub(r'[\\/*?:"<>|]', "", category_folder).strip()
        if not sanitized_category_folder:
            sanitized_category_folder = "Uncategorized_Shorts"

        output_category_dir = os.path.join(output_base_dir, sanitized_category_folder)
        os.makedirs(output_category_dir, exist_ok=True)

        sanitized_title = re.sub(r'[\\/*?:"<>\'"]', "", article_title.replace('/', '_'))
        output_filepath = os.path.join(output_category_dir, f"{sanitized_title}_short.mp4")

        print(f"Writing final video to: {output_filepath}")
        final_clip_with_elements.write_videofile(
            output_filepath, 
            codec="libx264", 
            audio_codec="libmp3lame", 
            fps=30, 
            preset="medium",
            threads=os.cpu_count(),
            verbose=True, 
            logger='bar'
        )

        audio_clip.close()
        main_video_clip.close()
        video_clip.close() 
        cropped_clip.close() 
        final_clip.close()

        print(f"Successfully created short for '{article_title}'.")
        return True

    except Exception as e:
        print(f"Error creating short for '{article_title}': {e}")
        import traceback
        traceback.print_exc() # Print full traceback for better debugging
        try:
            if 'audio_clip' in locals() and audio_clip: audio_clip.close()
            if 'main_video_clip' in locals() and main_video_clip: main_video_clip.close()
            if 'video_clip' in locals() and video_clip: video_clip.close()
            if 'cropped_clip' in locals() and cropped_clip: cropped_clip.close()
            if 'final_clip' in locals() and final_clip: final_clip.close()
        except Exception as close_e:
            print(f"Error closing clips: {close_e}")
        return False
    finally:
        clean_temp_images(TEMP_IMAGE_DIRECTORY)

# --- Main Execution Logic ---
if __name__ == "__main__":
    os.makedirs(GENERATED_SHORTS_DIRECTORY, exist_ok=True)
    os.makedirs(TEMP_IMAGE_DIRECTORY, exist_ok=True)

    processed_shorts_titles = get_processed_shorts_titles(TRACKING_SHORTS_FILE)
    print(f"Loaded {len(processed_shorts_titles)} previously created shorts titles.")

    for root, dirs, files in os.walk(GENERATED_AUDIO_DIRECTORY):
        category_folder = os.path.basename(root)

        for filename in files:
            if filename.endswith(".mp3"):
                audio_filepath = os.path.join(root, filename)
                
                article_title = os.path.splitext(filename)[0]

                if article_title in processed_shorts_titles:
                    print(f"\n'{article_title}' has already had a short created. Skipping.")
                    continue

                print(f"\nProcessing audio file: {audio_filepath} for short creation.")
                
                article_content = ""
                article_text_filepath = os.path.join(GENERATED_ARTICLES_DIRECTORY, category_folder, f"{article_title}.txt")
                if os.path.exists(article_text_filepath):
                    with open(article_text_filepath, 'r', encoding='utf-8') as f:
                        article_content = f.read()
                    print(f"Loaded article content from: {article_text_filepath}")
                else:
                    print(f"Warning: No article text file found for '{article_title}' at {article_text_filepath}. No images will be extracted.")
                
                image_urls = extract_image_urls_from_article(article_content)
                if image_urls:
                    print(f"Found {len(image_urls)} image URLs in article.")
                else:
                    print("No image URLs found in article content.")

                srt_filepath = os.path.join(GENERATED_TRANSCRIPT_DIRECTORY, category_folder, f"{article_title}.srt")

                short_created = create_youtube_short(
                    audio_filepath,
                    MINECRAFT_FOOTAGE_PATH,
                    GENERATED_SHORTS_DIRECTORY,
                    article_title,
                    category_folder,
                    image_urls,
                    srt_filepath 
                )

                if short_created:
                    log_processed_short_title(article_title, TRACKING_SHORTS_FILE)
                    print(f"Short creation and logging complete for '{article_title}'.")
                else:
                    print(f"Short creation failed for '{article_title}'. Not logging.")
    
    print("\n--- All short creations complete. ---")
    clean_temp_images(TEMP_IMAGE_DIRECTORY)