import csv
import os
import argparse
import json
from datetime import datetime

TAGS_CSV_PATH = "tags.csv"
MIN_COUNT_THRESHOLD = 50
TOP_COUNT = 20

TAG_TYPES = {"general": 0, "artist": 1, "series": 3, "character": 4}


def get_touhou_tags(filename="touhous.txt"):
    tags = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                tag = line.strip()
                if tag:
                    tags.add(tag)
    else:
        print(f"Warning: '{filename}' not found. Touhou category will be empty.")
    return tags


def load_tags_cache(tags_csv_path=TAGS_CSV_PATH):
    """Read tags.csv once into memory. Returns {date_str: {tag_name: (category_id, count)}}."""
    cache = {}
    if not os.path.exists(tags_csv_path):
        return cache

    date_cols = []
    with open(tags_csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, col in enumerate(header):
            try:
                datetime.strptime(col, "%Y-%m-%d")
                date_cols.append((i, col))
            except ValueError:
                continue

        for row in reader:
            tag_name = row[0]
            category = row[1]
            for idx, date_str in date_cols:
                if idx < len(row) and row[idx]:
                    if date_str not in cache:
                        cache[date_str] = {}
                    cache[date_str][tag_name] = (category, int(row[idx]))

    return cache


def get_tags(cache, date_str, tag_type_id=None, allowed_tags=None):
    tags = {}
    date_data = cache.get(date_str, {})
    for tag_name, (category, count) in date_data.items():
        if tag_type_id is not None and str(category) != str(tag_type_id):
            continue
        if allowed_tags is not None and tag_name not in allowed_tags:
            continue
        tags[tag_name] = count
    return tags


def calculate_growth(old_tags, new_tags):
    growth = []
    for tag, new_count in new_tags.items():
        if tag in old_tags and new_count >= MIN_COUNT_THRESHOLD:
            old_count = old_tags[tag]
            if old_count > 0:
                pct = ((new_count - old_count) / old_count) * 100
                growth.append(
                    {
                        "tag": tag,
                        "old": old_count,
                        "new": new_count,
                        "diff": new_count - old_count,
                        "percent": pct,
                    }
                )
    return growth


def process_comparison(cache, old_date, new_date, touhou_whitelist, entry_id=None):
    range_label = f"{old_date} to {new_date}"
    data_entry = {
        "date": range_label,
        "id": entry_id or f"danbooru-{new_date}.csv",
        "stats": {},
    }

    types_to_process = list(TAG_TYPES.keys()) + ["all", "touhou"]

    for t_type in types_to_process:
        type_id = None
        allowed = None

        if t_type == "all":
            type_id = None
        elif t_type == "touhou":
            allowed = touhou_whitelist
        else:
            type_id = TAG_TYPES[t_type]

        old_tags = get_tags(cache, old_date, type_id, allowed)
        new_tags = get_tags(cache, new_date, type_id, allowed)

        raw_growth = calculate_growth(old_tags, new_tags)

        data_entry["stats"][t_type] = {
            "percent": sorted(raw_growth, key=lambda x: x["percent"], reverse=True)[
                :TOP_COUNT
            ],
            "diff": sorted(raw_growth, key=lambda x: x["diff"], reverse=True)[
                :TOP_COUNT
            ],
        }

    return data_entry


def generate_daily_comparisons(dates, cache, touhou_whitelist):
    comparisons = []

    for i in range(1, len(dates)):
        old_date = dates[i - 1]
        new_date = dates[i]
        data_entry = process_comparison(cache, old_date, new_date, touhou_whitelist)
        comparisons.append(data_entry)

    return list(reversed(comparisons))


def generate_weekly_comparisons(dates, cache, touhou_whitelist):
    monday_dates = []
    for d in dates:
        try:
            date = datetime.strptime(d, "%Y-%m-%d")
            if date.weekday() == 0:
                monday_dates.append(d)
        except:
            continue

    comparisons = []
    for i in range(1, len(monday_dates)):
        old_date = monday_dates[i - 1]
        new_date = monday_dates[i]
        data_entry = process_comparison(
            cache,
            old_date,
            new_date,
            touhou_whitelist,
            f"weekly-danbooru-{new_date}.csv",
        )
        comparisons.append(data_entry)

    return list(reversed(comparisons))


def generate_monthly_comparisons(dates, cache, touhou_whitelist):
    fifth_dates = []
    for d in dates:
        try:
            date = datetime.strptime(d, "%Y-%m-%d")
            if date.day == 5:
                fifth_dates.append(d)
        except:
            continue

    comparisons = []
    for i in range(1, len(fifth_dates)):
        old_date = fifth_dates[i - 1]
        new_date = fifth_dates[i]
        data_entry = process_comparison(
            cache,
            old_date,
            new_date,
            touhou_whitelist,
            f"monthly-danbooru-{new_date}.csv",
        )
        comparisons.append(data_entry)

    return list(reversed(comparisons))


def export_json(filename="tag_stats.json", incremental=True):
    cache = load_tags_cache()
    if not cache:
        print("No data found in tags.csv.")
        return

    dates = sorted(cache.keys())
    touhou_whitelist = get_touhou_tags()

    if len(dates) < 2:
        print("Not enough dates in tags.csv to generate JSON.")
        return

    if incremental and os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

        daily_existing_ids = {entry["id"] for entry in existing_data.get("daily", [])}
        weekly_existing_ids = {entry["id"] for entry in existing_data.get("weekly", [])}
        monthly_existing_ids = {
            entry["id"] for entry in existing_data.get("monthly", [])
        }

        existing_daily = existing_data.get("daily", [])
        existing_weekly = existing_data.get("weekly", [])
        existing_monthly = existing_data.get("monthly", [])

        new_daily = []
        for i in range(len(dates) - 1, 0, -1):
            new_date = dates[i]
            old_date = dates[i - 1]
            entry_id = f"danbooru-{new_date}.csv"
            if entry_id not in daily_existing_ids:
                entry = process_comparison(
                    cache, old_date, new_date, touhou_whitelist, entry_id
                )
                new_daily.append(entry)
            else:
                break

        new_weekly = []
        monday_dates = []
        for d in dates:
            try:
                date = datetime.strptime(d, "%Y-%m-%d")
                if date.weekday() == 0:
                    monday_dates.append(d)
            except:
                continue
        for i in range(len(monday_dates) - 1, 0, -1):
            new_date = monday_dates[i]
            old_date = monday_dates[i - 1]
            entry_id = f"weekly-danbooru-{new_date}.csv"
            if entry_id not in weekly_existing_ids:
                entry = process_comparison(
                    cache, old_date, new_date, touhou_whitelist, entry_id
                )
                new_weekly.append(entry)
            else:
                break

        new_monthly = []
        fifth_dates = []
        for d in dates:
            try:
                date = datetime.strptime(d, "%Y-%m-%d")
                if date.day == 5:
                    fifth_dates.append(d)
            except:
                continue
        for i in range(len(fifth_dates) - 1, 0, -1):
            new_date = fifth_dates[i]
            old_date = fifth_dates[i - 1]
            entry_id = f"monthly-danbooru-{new_date}.csv"
            if entry_id not in monthly_existing_ids:
                entry = process_comparison(
                    cache, old_date, new_date, touhou_whitelist, entry_id
                )
                new_monthly.append(entry)
            else:
                break

        daily_comparisons = new_daily + existing_daily
        weekly_comparisons = new_weekly + existing_weekly
        monthly_comparisons = new_monthly + existing_monthly

        print(
            f"Incremental: computed {len(new_daily)} new daily, {len(new_weekly)} new weekly, {len(new_monthly)} new monthly comparisons."
        )
    else:
        daily_comparisons = generate_daily_comparisons(dates, cache, touhou_whitelist)
        weekly_comparisons = generate_weekly_comparisons(dates, cache, touhou_whitelist)
        monthly_comparisons = generate_monthly_comparisons(
            dates, cache, touhou_whitelist
        )

    final_data = {
        "daily": daily_comparisons,
        "weekly": weekly_comparisons,
        "monthly": monthly_comparisons,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
    print(
        f"Successfully generated {filename} with {len(daily_comparisons)} daily, {len(weekly_comparisons)} weekly, and {len(monthly_comparisons)} monthly comparisons."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare tag stats between dates in tags.csv."
    )
    parser.add_argument(
        "--sort", choices=["percent", "diff"], default="percent", help="Sort metric"
    )
    parser.add_argument(
        "--type",
        choices=list(TAG_TYPES.keys()) + ["all", "touhou"],
        default="all",
        help="Tag type filter",
    )
    parser.add_argument("--json", action="store_true", help="Generate JSON for web.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full regeneration of JSON (ignore incremental).",
    )

    args = parser.parse_args()

    if not os.path.exists(TAGS_CSV_PATH):
        print(f"'{TAGS_CSV_PATH}' not found.")
        return

    if args.json:
        export_json(incremental=not args.force)
        return

    cache = load_tags_cache()
    if not cache:
        print("No data found in tags.csv.")
        return

    dates = sorted(cache.keys())
    if len(dates) < 2:
        print("Need at least 2 dates in tags.csv to compare.")
        return

    old_date, new_date = dates[-2], dates[-1]

    type_id = None
    allowed_tags = None

    if args.type == "all":
        type_id = None
    elif args.type == "touhou":
        allowed_tags = get_touhou_tags()
    else:
        type_id = TAG_TYPES[args.type]

    old_tags = get_tags(cache, old_date, type_id, allowed_tags)
    new_tags = get_tags(cache, new_date, type_id, allowed_tags)

    risers = calculate_growth(old_tags, new_tags)
    risers = sorted(risers, key=lambda x: x[args.sort], reverse=True)

    print(f"Comparing {old_date} -> {new_date}")
    filter_text = f" ({args.type})" if args.type != "all" else ""
    print(f"--- Top {TOP_COUNT} Risers{filter_text} (Sorted by {args.sort}) ---")
    print(f"{'Tag':<30} | {'Old':<10} | {'New':<10} | {'Diff':<10} | {'%':<10}")
    print("-" * 80)

    for item in risers[:TOP_COUNT]:
        print(
            f"{item['tag']:<30} | {item['old']:<10} | {item['new']:<10} | {item['diff']:<10} | {item['percent']:.2f}%"
        )


if __name__ == "__main__":
    main()
