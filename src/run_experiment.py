from sys import argv, exit

from constants import AI_SAVE_FILE_PATH
from exceptions import AIRunError, EmptySaveError
from finnhub_helper import create_finnhub_client
from run_ai import run_ai

USAGE = "Usage: run_experiment.py [--initialize]"

argc = len(argv)
if argc > 2:
    exit(USAGE)

initialize = False
if len(argv) == 2:
    if argv[1] == "--initialize":
        initialize = True
    else:
        print(f"Unrecognized argument `{argv[1]}`")
        exit(USAGE)

finnhub_client = create_finnhub_client()

print("Running AI...")
try:
    run_ai(initialize, AI_SAVE_FILE_PATH, finnhub_client)
except AIRunError as e:
    print(f"Encountered an error while running AI: {e}")
    print("Exiting.")
    exit(1)
except EmptySaveError:
    print("AI save is empty or does not exist. Use --initialize to initialize.")
    print("Exiting.")
    exit(1)

print("Running Control (S&P 500)...")
