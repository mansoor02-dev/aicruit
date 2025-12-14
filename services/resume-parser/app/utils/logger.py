import json
import os
from preprocessing import preprocess_resume

def process_batch_cvs(input_folder="raw_cvs"):
    cleaning_log = []
    seen_hashes = set()

    for filename in os.listdir(input_folder):
        file_path = os.path.join(input_folder, filename)

        if not os.path.isfile(file_path):
            continue

        log_entry, _ = preprocess_resume(file_path)

        if log_entry["hash"] in seen_hashes:
            log_entry["is_duplicate"] = True
        else:
            seen_hashes.add(log_entry["hash"])

        cleaning_log.append(log_entry)

    with open("cleaning_logs/cleaning_log.json", "w", encoding="utf-8") as f:
        json.dump(cleaning_log, f, indent=4)

    return cleaning_log