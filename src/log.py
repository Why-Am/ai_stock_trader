from constants import LOG_DIRECTORY_PATH


def log(filename: str, message: str):
    with open(LOG_DIRECTORY_PATH / filename, "w", encoding="utf-8") as file:
        file.write(message)