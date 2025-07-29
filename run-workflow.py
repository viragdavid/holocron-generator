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

# this way the run-workflow.py script can be run from any directory
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(current_dir, 'scripts')

print("Starting the automated workflow...")

for script_name in scripts_to_run:
    script_path = os.path.join(scripts_dir, script_name)
    
    print(f"\n--- Running: {script_name} ---")
    
    try:
        # sys.executable ensures the current Python interpreter is used
        # check=False means it won't raise an error if the script exits non-zero
        # capture_output=False means output goes directly to console
        subprocess.run([sys.executable, script_path], check=False, capture_output=False)
    except FileNotFoundError:
        print(f"ERROR: Script not found: {script_path}. Skipping.")
    except Exception as e:
        print(f"ERROR: An unexpected issue occurred while trying to run {script_name}: {e}")

print("\nWorkflow completed.")