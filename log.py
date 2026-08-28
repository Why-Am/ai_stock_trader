def log(filename: str, message: str):
    with open(f"log/{filename}", "w", encoding="utf-8") as file:
        file.write(message)