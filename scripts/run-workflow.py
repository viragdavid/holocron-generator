import subprocess
import sys
import os

# List of scripts to run, in order
scripts_to_run = [
    "scraper.py",
    "ai-api-calls.py",
    "transcript-gen.py",
    "video-gen.py",
    "youtube-upload.py",
]

# Get the directory of the current script (run-workflow.py)
script_dir = os.path.dirname(os.path.abspath(__file__))

print("Starting the automated workflow...")

for script in scripts_to_run:
    print(f"\n--- Running: {script} ---")
    
    try:
        # We don't need to build the full path here because we're setting the cwd
        subprocess.run([sys.executable, script], 
                       cwd=script_dir, 
                       check=False, 
                       capture_output=False)
    except FileNotFoundError:
        print(f"ERROR: Script not found: {script}. Skipping.")
    except Exception as e:
        print(f"ERROR: An unexpected issue occurred while trying to run {script}: {e}")

print("\nWorkflow completed.")