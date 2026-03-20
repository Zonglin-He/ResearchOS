from app.core.config import load_config
from app.db.sqlite import SQLiteDatabase


def main() -> None:
    config = load_config()
    database = SQLiteDatabase(config.db_path)
    database.initialize()
    print(f"Bootstrapped ResearchOS at {config.db_path}")


if __name__ == "__main__":
    main()
