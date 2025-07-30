import subprocess
import sys
import os # Added for os.path.join

# List of scripts to run, in order
scripts_to_run = [
    "scraper.py",
    "ai-api-calls.py",
    "transcript-gen.py",
    "video-gen.py",
    "youtube-upload.py",
]

print("Starting the automated workflow...")

for script in scripts_to_run:

    
    print(f"\n--- Running: {script} ---")
    
    try:
        # sys.executable ensures the current Python interpreter is used
        # check=False means it won't raise an error if the script exits non-zero
        # capture_output=False means output goes directly to console
        subprocess.run([sys.executable, script], check=False, capture_output=False)
    except FileNotFoundError:
        print(f"ERROR: Script not found: {script}. Skipping.")
    except Exception as e:
        print(f"ERROR: An unexpected issue occurred while trying to run {script}: {e}")

print("\nWorkflow completed.")