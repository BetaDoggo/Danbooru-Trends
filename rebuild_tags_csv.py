import csv
import os
from datetime import datetime

TAGS_DIR = "tags"
OUTPUT_PATH = "tags.csv"


def rebuild_tags_csv():
    if not os.path.exists(TAGS_DIR):
        print(f"Directory '{TAGS_DIR}' not found.")
        return

    files = sorted(f for f in os.listdir(TAGS_DIR) if f.endswith(".csv"))

    if not files:
        print(f"No CSV files found in '{TAGS_DIR}'.")
        return

    dates = []
    for f in files:
        date_str = f.replace("danbooru-", "").replace(".csv", "")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            print(f"Skipping unrecognized file: {f}")
            continue

    if not dates:
        print("No valid date files found.")
        return

    print(f"Found {len(dates)} daily snapshots ({dates[0]} to {dates[-1]})")

    tags = {}

    for i, date_str in enumerate(dates):
        filepath = os.path.join(TAGS_DIR, f"danbooru-{date_str}.csv")
        print(f"Processing {date_str} ({i + 1}/{len(dates)})...")

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                tag_name = row[0]
                category = row[1]
                count = row[2]
                aliases = row[3] if len(row) > 3 else ""

                if tag_name not in tags:
                    tags[tag_name] = {
                        "category": category,
                        "aliases": aliases,
                        "counts": {},
                    }

                tags[tag_name]["counts"][date_str] = count

    header = ["Tag Name", "Category", "Aliases"] + dates

    def sort_key(tag_name):
        counts = tags[tag_name]["counts"]
        if not counts:
            return -1
        latest = max(counts.keys())
        val = counts[latest]
        return int(val) if val else -1

    sorted_names = sorted(tags.keys(), key=sort_key, reverse=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for tag_name in sorted_names:
            entry = tags[tag_name]
            row = [tag_name, entry["category"], entry["aliases"]]
            for date_str in dates:
                row.append(entry["counts"].get(date_str, ""))
            writer.writerow(row)

    print(
        f"Wrote {OUTPUT_PATH} with {len(sorted_names)} tags across {len(dates)} dates."
    )


if __name__ == "__main__":
    rebuild_tags_csv()
