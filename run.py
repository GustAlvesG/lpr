"""Atalho de execução: `python run.py [caminho/para/config.yaml]`."""
import sys

from src.main import main

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    main(config_path)
