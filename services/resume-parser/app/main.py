import json
import sys
from pathlib import Path
from ingestion import ingest
from cleaner import clean_text
from inference import run_inference
from validator import validate

import time


def parse_resume(file_path: str) -> dict:
    raw_text = ingest(file_path)
    clean = clean_text(raw_text)
    raw_json = run_inference(clean)
    result = validate(raw_json)
    return result, clean, raw_json


if __name__ == "__main__":
    # file_path = sys.argv[1] if len(sys.argv) > 1 else "data/Mansoor_Abid_CV.pdf"
    file_path = "data/" + input("Enter file name: ")
    start_time = time.time()
    result, clean, raw_json = parse_resume(file_path)
    end_time = time.time()
    print(f"Processing took {end_time - start_time:.2f} seconds")
    print(json.dumps(result, indent=2))