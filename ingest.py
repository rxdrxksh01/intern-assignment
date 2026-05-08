"""Command-line entrypoint for Netflix catalogue ingestion."""

from ingestion.pipeline import run_ingestion


if __name__ == "__main__":
    run_ingestion()
