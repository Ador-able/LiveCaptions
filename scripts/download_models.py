import os
import subprocess
import sys

def install_spacy_model(model_name, url):
    print(f"Checking {model_name}...")
    try:
        # Check if model is already installed by trying to load it
        import spacy
        spacy.load(model_name)
        print(f"{model_name} is already installed.")
    except (ImportError, OSError):
        print(f"Installing {model_name} from {url}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", url])
        print(f"{model_name} installed successfully.")

if __name__ == "__main__":
    install_spacy_model("en_core_web_sm", "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl")
    install_spacy_model("zh_core_web_sm", "https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.7.0/zh_core_web_sm-3.7.0-py3-none-any.whl")
