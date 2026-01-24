import csv
import os
import argparse
import json
from datetime import datetime

TAGS_DIR = "tags"
MIN_COUNT_THRESHOLD = 50
TOP_COUNT = 20

TAG_TYPES = {
    'general': 0,
    'artist': 1,
    'series': 3,
    'character': 4
}

def get_touhou_tags(filename="touhous.txt"):
    """Reads the list of Touhou tags from a text file."""
    tags = set()
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                tag = line.strip()
                if tag:
                    tags.add(tag)
    else:
        print(f"Warning: '{filename}' not found. Touhou category will be empty.")
    return tags

def get_sorted_files(directory):
    # We assume filenames contain dates or sortable numbers
    files = sorted([f for f in os.listdir(directory) if f.endswith('.csv')])
    return files

def read_tags(filepath, tag_type_id=None, allowed_tags=None):
    tags = {}
    try:
        with open(filepath, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                try:
                    if tag_type_id is not None:
                        if int(row[1]) != tag_type_id:
                            continue
                    
                    if allowed_tags is not None:
                        if row[0] not in allowed_tags:
                            continue

                    tags[row[0]] = int(row[2])
                except (IndexError, ValueError):
                    continue
    except FileNotFoundError:
        pass
    return tags

def calculate_growth(old_tags, new_tags):
    growth = []
    for tag, new_count in new_tags.items():
        if tag in old_tags and new_count >= MIN_COUNT_THRESHOLD:
            old_count = old_tags[tag]
            if old_count > 0:
                pct = ((new_count - old_count) / old_count) * 100
                growth.append({
                    'tag': tag,
                    'old': old_count,
                    'new': new_count,
                    'diff': new_count - old_count,
                    'percent': pct
                })
    return growth

def get_display_name(f):
    name = os.path.splitext(f)[0]
    return name

def process_comparison(old_filename, new_filename, touhou_whitelist, entry_id=None):
    """Process a single comparison between two files."""
    new_name = get_display_name(new_filename)
    old_name = get_display_name(old_filename)
    
    range_label = f"{old_name} to {new_name}"
    data_entry = {'date': range_label, 'id': entry_id or new_filename, 'stats': {}}
    
    types_to_process = list(TAG_TYPES.keys()) + ['all', 'touhou']
    
    for t_type in types_to_process:
        type_id = None
        allowed = None
        
        if t_type == 'all':
            type_id = None
        elif t_type == 'touhou':
            allowed = touhou_whitelist
        else:
            type_id = TAG_TYPES[t_type]
        
        old_tags = read_tags(os.path.join(TAGS_DIR, old_filename), type_id, allowed)
        new_tags = read_tags(os.path.join(TAGS_DIR, new_filename), type_id, allowed)
        
        raw_growth = calculate_growth(old_tags, new_tags)
        
        data_entry['stats'][t_type] = {
            'percent': sorted(raw_growth, key=lambda x: x['percent'], reverse=True)[:TOP_COUNT],
            'diff': sorted(raw_growth, key=lambda x: x['diff'], reverse=True)[:TOP_COUNT]
        }
    
    return data_entry

def generate_daily_comparisons(files, touhou_whitelist):
    """Generate daily comparisons comparing consecutive days."""
    comparisons = []
    
    for i in range(1, len(files)):
        new_filename = files[i]
        old_filename = files[i-1]
        
        data_entry = process_comparison(old_filename, new_filename, touhou_whitelist)
        comparisons.append(data_entry)
    
    return list(reversed(comparisons))

def generate_weekly_comparisons(files, touhou_whitelist):
    """
    Generates weekly comparisons comparing Monday vs previous Monday.
    Only creates comparisons when full weeks exist.
    """
    monday_files = []
    for f in files:
        try:
            date_str = f.replace('danbooru-', '').replace('.csv', '')
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if date.weekday() == 0:
                monday_files.append((f, date))
        except:
            continue
    
    comparisons = []
    for i in range(1, len(monday_files)):
        old_file, old_date = monday_files[i-1]
        new_file, new_date = monday_files[i]
        
        data_entry = process_comparison(old_file, new_file, touhou_whitelist, f'weekly-{new_file}')
        comparisons.append(data_entry)
    
    return list(reversed(comparisons))

def export_json(filename="tag_stats.json"):
    files = get_sorted_files(TAGS_DIR)
    touhou_whitelist = get_touhou_tags()
    
    if len(files) < 2:
        print("Not enough files to generate JSON.")
        return

    daily_comparisons = generate_daily_comparisons(files, touhou_whitelist)
    weekly_comparisons = generate_weekly_comparisons(files, touhou_whitelist)
    
    final_data = {
        "daily": daily_comparisons,
        "weekly": weekly_comparisons
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4)
    print(f"Successfully generated {filename} with {len(daily_comparisons)} daily and {len(weekly_comparisons)} weekly comparisons.")

def main():
    parser = argparse.ArgumentParser(description="Compare tag stats between CSV files.")
    parser.add_argument("--sort", choices=['percent', 'diff'], default='percent', help="Sort metric")
    parser.add_argument("--type", choices=list(TAG_TYPES.keys()) + ['all', 'touhou'], default='all', help="Tag type filter")
    parser.add_argument("--json", action="store_true", help="Generate JSON for web.")
    
    args = parser.parse_args()

    if not os.path.exists(TAGS_DIR):
        print(f"Directory '{TAGS_DIR}' not found.")
        return

    if args.json:
        export_json()
        return

    # Original Console Logic (Latest only)
    files = get_sorted_files(TAGS_DIR)
    if len(files) < 2:
        print("Need at least 2 files to compare.")
        return

    old_file, new_file = files[-2], files[-1]
    
    type_id = None
    allowed_tags = None

    if args.type == 'all':
        type_id = None
    elif args.type == 'touhou':
        allowed_tags = get_touhou_tags()
    else:
        type_id = TAG_TYPES[args.type]

    old_tags = read_tags(os.path.join(TAGS_DIR, old_file), type_id, allowed_tags)
    new_tags = read_tags(os.path.join(TAGS_DIR, new_file), type_id, allowed_tags)

    risers = calculate_growth(old_tags, new_tags)
    risers = sorted(risers, key=lambda x: x[args.sort], reverse=True)

    print(f"Comparing {old_file} -> {new_file}")
    filter_text = f" ({args.type})" if args.type != 'all' else ""
    print(f"--- Top {TOP_COUNT} Risers{filter_text} (Sorted by {args.sort}) ---")
    print(f"{'Tag':<30} | {'Old':<10} | {'New':<10} | {'Diff':<10} | {'%':<10}")
    print("-" * 80)
    
    for item in risers[:TOP_COUNT]:
        print(f"{item['tag']:<30} | {item['old']:<10} | {item['new']:<10} | {item['diff']:<10} | {item['percent']:.2f}%")

if __name__ == "__main__":
    main()