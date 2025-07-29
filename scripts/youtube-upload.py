import os
import glob
import pickle
import datetime
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

# --- Configuration ---
CLIENT_SECRETS_FILE = r'C:\egyetem\github-ml\holocron-generator\client_secret_12090445080-o5mvqmklk0ac7uu7q4co9hib5sgi01fn.apps.googleusercontent.com.json'
UPLOADED_LOG_FILE = '../data/uploaded_shorts.log'
BASE_VIDEO_DIR = '../data/generated_shorts'
BASE_TEXT_DIR = '../data/generated_text'

# YouTube API scopes - 'youtube.upload' is essential for uploading
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

# General hashtags to append to all descriptions
GLOBAL_HASHTAGS = [
    '#shorts',
    '#starwars',
    '#anakin',
    '#legends',
    '#starwarsfans', 
    '#jedi',
    '#sith',
    '#lightsaber',
    '#starwarslegends',
    '#starwarsfan',
    '#starwarscommunity',
    '#yoda',
    '#darthvader',
    '#kenobi',
    '#starwarsreels',
    '#force'
]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("uploader.log"), # Log to a file
                        logging.StreamHandler() # Also log to console
                    ])

# --- OAuth Authentication Function ---
def get_authenticated_service():
    """Authenticates with Google OAuth and returns a YouTube API service."""
    credentials = None
    # Load credentials from token.pickle if it exists
    if os.path.exists('token.pickle'):
        try:
            with open('token.pickle', 'rb') as token:
                credentials = pickle.load(token)
            logging.info("Loaded credentials from token.pickle")
        except Exception as e:
            logging.warning(f"Error loading token.pickle: {e}. Will re-authenticate.")
            credentials = None

    # If no valid credentials, initiate the OAuth flow
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            logging.info("Access token expired, attempting to refresh...")
            try:
                credentials.refresh(Request())
                logging.info("Access token refreshed successfully.")
            except Exception as e:
                logging.error(f"Error refreshing token: {e}. Re-initiating full OAuth flow.")
                credentials = None # Force full re-authentication
        else:
            logging.info("No valid credentials, initiating new OAuth flow...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRETS_FILE, SCOPES)
                # This will open a browser for the user to authorize
                credentials = flow.run_local_server(port=0)
                logging.info("OAuth flow completed successfully.")
            except Exception as e:
                logging.error(f"Failed to complete OAuth flow: {e}")
                raise # Re-raise the exception to stop execution

        # Save the new/refreshed credentials
        try:
            with open('token.pickle', 'wb') as token:
                pickle.dump(credentials, token)
            logging.info("Credentials saved to token.pickle")
        except Exception as e:
            logging.error(f"Failed to save credentials to token.pickle: {e}")
            # Non-fatal, but user might need to re-auth more often

    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

# --- Video Upload Function ---
def upload_video(youtube_service, video_path, title, description, tags, category_id='24', privacy_status='public'):
    """
    Uploads a video to YouTube.

    Args:
        youtube_service: An authenticated YouTube API service object.
        video_path (str): Path to the video file.
        title (str): Title of the video.
        description (str): Description of the video.
        tags (list): List of tags for the video.
        category_id (str): YouTube category ID (default '22' for People & Blogs).
        privacy_status (str): 'public', 'private', or 'unlisted'.

    Returns:
        str: The YouTube video ID if successful, None otherwise.
    """
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': privacy_status
        },
        'recordingDetails': { # Optional: for Shorts, you might want to specify this
            'recordingDate': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    }

    media_body = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    try:
        request = youtube_service.videos().insert(
            part='snippet,status,recordingDetails',
            body=body,
            media_body=media_body
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logging.info(f"Uploaded {int(status.resumable_progress * 100)}% of {os.path.basename(video_path)}")

        if 'id' in response:
            logging.info(f"Successfully uploaded: '{title}' (Video ID: {response['id']})")
            return response['id']
        else:
            logging.error(f"Upload failed for {os.path.basename(video_path)} with unexpected response: {response}")
            return None

    except HttpError as e:
        logging.error(f"An HTTP error occurred during upload for {os.path.basename(video_path)}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during upload for {os.path.basename(video_path)}: {e}")
        return None

# --- File Management and Logging ---
def get_uploaded_videos():
    """Reads the log file and returns a set of already uploaded video file paths."""
    uploaded_files = set()
    if os.path.exists(UPLOADED_LOG_FILE):
        with open(UPLOADED_LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(' | ')
                if len(parts) >= 2:
                    # Get the path from the log file
                    logged_path = parts[1]

                    # --- NEW CHANGE HERE ---
                    # Normalize the logged path to match os.path.relpath's output
                    # This often means converting '/' to '\' on Windows or vice versa.
                    # os.path.normpath() is good for this, it handles / and \ consistently.
                    normalized_logged_path = os.path.normpath(logged_path)

                    uploaded_files.add(normalized_logged_path)
                    # --- END OF NEW CHANGE ---

    return uploaded_files

def log_uploaded_video(video_path, video_id, title):
    """Appends the details of an uploaded video to the log file."""
    timestamp = datetime.datetime.now().isoformat()
    # It's good practice to normalize path for logging as well, to ensure consistency
    # with how it's read back. os.path.normpath will use native separators.
    normalized_video_path = os.path.normpath(video_path)
    with open(UPLOADED_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | {normalized_video_path} | {video_id} | {title}\n")
    logging.info(f"Logged upload: {os.path.basename(video_path)}")

# --- Main Logic ---
def main():
    try:
        youtube = get_authenticated_service()
    except Exception as e:
        logging.critical(f"Failed to authenticate. Exiting: {e}")
        return

    uploaded_videos = get_uploaded_videos()
    logging.info(f"Found {len(uploaded_videos)} already uploaded videos in log.")

    # Iterate through categories (subdirectories in BASE_VIDEO_DIR)
    for category_dir in os.listdir(BASE_VIDEO_DIR):
        category_video_path = os.path.join(BASE_VIDEO_DIR, category_dir)
        # --- IMPORTANT: Adjust category_text_path based on how it's relative to main_uploader.py ---
        # If BASE_TEXT_DIR is already relative to the script's execution directory
        # e.g., 'data/generated_text' in the project root
        category_text_path = os.path.join(BASE_TEXT_DIR, category_dir)
        # If your 'data' folder is one level up from your script
        # script_dir = os.path.dirname(__file__)
        # category_text_path = os.path.join(script_dir, '..', BASE_TEXT_DIR, category_dir) # Example: if script in 'scripts/' and data in project root

        if not os.path.isdir(category_video_path):
            continue # Skip if it's not a directory

        logging.info(f"Processing category: {category_dir}")

        # Find all MP4 files in the current category
        for video_file in glob.glob(os.path.join(category_video_path, '*.mp4')):
            relative_video_path = os.path.relpath(video_file) # Store relative path for consistency in log

            if relative_video_path in uploaded_videos:
                logging.info(f"Skipping already uploaded video: {os.path.basename(video_file)}")
                continue

            # Determine corresponding text file path
            video_basename_with_ext = os.path.basename(video_file)
            video_name_without_ext_full = os.path.splitext(video_basename_with_ext)[0] # e.g., "Mission to Batuu_short"

            # Remove the "_short" suffix if present to get the base name for text file
            if video_name_without_ext_full.endswith('_short'):
                video_name_for_text_file = video_name_without_ext_full.removesuffix('_short')
            else:
                video_name_for_text_file = video_name_without_ext_full

            # *** --- NEW CHANGE: Append "_rephrased.txt" for text file path --- ***
            text_file_path_for_video = os.path.join(category_text_path, f"{video_name_for_text_file}_rephrased.txt")

            if not os.path.exists(text_file_path_for_video): # Use the newly constructed path here
                logging.warning(f"No description file found for {os.path.basename(video_file)} ({text_file_path_for_video}). Skipping.")
                continue

            # Read description
            with open(text_file_path_for_video, 'r', encoding='utf-8') as f: # Use the newly constructed path here
                description_content = f.read().strip()

            # Construct full description with hashtags
            full_description = f"{description_content}\n\n" + " ".join(GLOBAL_HASHTAGS)

            # Use the clean name for the video title (still without _short or _rephrased)
            video_title = video_name_for_text_file.replace('_', ' ').title() # Basic title formatting

            # Prepare tags (example: based on categories and global hashtags)
            tags = [category_dir.replace('_', ' ').lower()] + [h.strip('#') for h in GLOBAL_HASHTAGS]
            tags = list(set(tags)) # Remove duplicates

            logging.info(f"Attempting to upload: {video_title}")
            logging.info(f"Description: {full_description[:100]}...") # Show first 100 chars
            logging.info(f"Tags: {', '.join(tags)}")

            # Perform the upload
            video_id = upload_video(youtube, video_file, video_title, full_description, tags)

            if video_id:
                log_uploaded_video(relative_video_path, video_id, video_title)
            else:
                logging.error(f"Failed to upload or log: {os.path.basename(video_file)}")

if __name__ == '__main__':
    main()