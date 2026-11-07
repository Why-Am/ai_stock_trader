from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_SAVE_FILE_PATH = _PROJECT_ROOT / "data" / "ai_save.csv"
TEST_AI_SAVE_FILE_PATH = _PROJECT_ROOT / "data" / "test_ai_save.csv"
CONTROL_SAVE_FILE_PATH = _PROJECT_ROOT / "data" / "control_save.csv"
TEST_CONTROL_SAVE_FILE_PATH = _PROJECT_ROOT / "data" / "test_control_save.csv"
LOG_DIRECTORY_PATH = _PROJECT_ROOT / "log"
STARTING_MONEY = 500
MAXIMUM_TRIES = 2
S_AND_P_500_TICKER = "VOO"

if __name__ == "__main__":
    print(AI_SAVE_FILE_PATH)
