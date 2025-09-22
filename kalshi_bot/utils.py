import csv
import datetime

def log_to_csv(filepath, row: dict, header: list[str]):
    file_exists = False
    try:
        with open(filepath, "r"):
            file_exists = True
    except FileNotFoundError:
        pass

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def timestamp():
    return datetime.datetime.utcnow().isoformat()

