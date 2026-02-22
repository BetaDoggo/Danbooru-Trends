import os
import requests
import collections
import csv
import time
import datetime

class Complete(Exception): pass

# Hardcoded settings
minimum_count = 50
filename_date = datetime.datetime.now().strftime('%Y-%m-%d')
csv_filename_only = f"danbooru-{filename_date}.csv"

# Setup output directory
output_dir = "tags"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

csv_filename = os.path.join(output_dir, csv_filename_only)

# Base URLs
base_url = 'https://danbooru.donmai.us/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
alias_url = 'https://danbooru.donmai.us/tag_aliases.json?commit=Search&limit=1000&search[order]=tag_count'

session = requests.Session()
dan_aliases = collections.defaultdict(list)


def get_aliases(url):
    try:
        aliases = collections.defaultdict(list)
        for page in range(1, 1001):
            # Update the URL with the current page
            url = f'{url}&page={page}'
            # Fetch the JSON data
            while True:
                response = session.get(url, headers={"User-Agent": "tag-trends/1.0"})
                if response.status_code == 200:
                    break
                else:
                    print(f"Couldn't reach server, Status: {response.status_code}.\nRetrying in 5 seconds")
                    time.sleep(5)
            data = response.json()
            # Break the loop if the data is empty
            if not data:
                print(f'No more alias data found at page {page}. Stopping.', flush=True)
                break
            for item in data:
                # Store aliases mapping the valid tag (consequent) to the alias (antecedent)
                aliases[item['consequent_name']] += [[item['antecedent_name'], item['created_at']]]
            print(f'Page {page} aliases processed.', flush=True)
            time.sleep(0.3) # avoid rate limit
    except Exception as e:
        print(f"Error fetching aliases: {e}")
    return aliases

def upload_to_huggingface(csv_file_path, date_str):
    from huggingface_hub import HfApi
    
    hf_token = os.getenv('HF_TOKEN')
    if not hf_token:
        print("HF_TOKEN not found - skipping HuggingFace upload")
        return False
    
    api = HfApi()
    repo_id = "HDiffusion/historical-danbooru-tag-counts"
    filename = f"danbooru-{date_str}.csv"
    
    try:
        api.upload_file(
            path_or_fileobj=csv_file_path,
            path_in_repo=filename,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"Add daily tag counts for {date_str}",
        )
        print(f"Uploaded {filename} to HuggingFace")
        return True
    except Exception as e:
        print(f"Failed to upload to HuggingFace: {e}")
        return False

def merge_into_tags_csv(daily_csv_path, date_str):
    """Merge today's data into tags.csv"""
    tags_csv_path = "tags.csv"
    
    # Read today's daily CSV
    daily_data = {}
    with open(daily_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            daily_data[row[0]] = row  # tag_name -> [name, category, count, aliases]
    
    # Merge strategy:
    # - If tags.csv exists: Read it, add/replace today's column, write back
    # - If tags.csv doesn't exist: Create new with first date column
    
    if os.path.exists(tags_csv_path):
        # Read existing tags.csv
        with open(tags_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            existing_data = {row[0]: row for row in reader}
        
        # Add date column if not exists
        date_col = date_str
        if date_col not in header:
            header.append(date_col)
            for row in existing_data.values():
                row.append('')
        
        # Update existing tags with today's counts
        for tag_name, daily_row in daily_data.items():
            if tag_name in existing_data:
                # Find date column index and update
                date_idx = header.index(date_col)
                existing_data[tag_name][date_idx] = daily_row[2]  # post_count
        
        # Add new tags (not in existing)
        new_tags = set(daily_data.keys()) - set(existing_data.keys())
        for tag_name in new_tags:
            new_row = [
                daily_data[tag_name][0],  # name
                daily_data[tag_name][1],  # category
                daily_data[tag_name][3],  # aliases
            ] + [''] * (len(header) - 3)  # Fill date columns with empty
            date_idx = header.index(date_col)
            new_row[date_idx] = daily_data[tag_name][2]  # post_count
            existing_data[tag_name] = new_row
        
        # Write merged data sorted by latest date count (highest first)
        # Find the latest date column (the last one)
        latest_date_idx = len(header) - 1
        def sort_by_latest_count(tag_name):
            count = existing_data[tag_name][latest_date_idx]
            if not count:
                return -1
            return int(count)
        
        sorted_tags = sorted(existing_data.keys(), key=sort_by_latest_count, reverse=True)
        
        with open(tags_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for tag_name in sorted_tags:
                writer.writerow(existing_data[tag_name])
    else:
        # Create new tags.csv
        header = ['Tag Name', 'Category', 'Aliases', date_str]
        rows = []
        
        # Sort by count (highest first)
        sorted_daily = sorted(daily_data.items(), key=lambda x: int(x[1][2]), reverse=True)
        for tag_name, row in sorted_daily:
            rows.append([row[0], row[1], row[3], row[2]])  # [name, category, aliases, count]
        
        with open(tags_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    
    print(f"Merged data into {tags_csv_path}")

# Get Tags
dan_tags = {}
try:
    for page in range(1, 1001):
        url = f'{base_url}&page={page}'
        while True:
            response = session.get(url, headers={"User-Agent": "tag-list/2.0"})
            if response.status_code == 200:
                break
            else:
                print(f"Couldn't reach server, Status: {response.status_code}.\nRetrying in 5 seconds")
                time.sleep(5)
        data = response.json()
        if not data:
            print(f'No more data found at page {page}. Stopping.', flush=True)
            break
        
        for item in data:
            if int(item['post_count']) < minimum_count:
                raise Complete
            # Storing: [Category, Post Count, Created At]
            dan_tags[item['name']] = [item['category'], item['post_count'], item['created_at']]
        print(f'Danbooru page {page} processed.', flush=True)
        time.sleep(0.3)
except Complete:
    pass

# Get Aliases
dan_aliases = get_aliases(alias_url)

# Merge Aliases
for key in dan_tags:
    if key in dan_aliases:
        # Extract just the alias names and join them with commas
        alias_list = [alias[0] for alias in dan_aliases[key]]
        dan_tags[key].append(",".join(alias_list))
    else:
        dan_tags[key].append("") # No aliases

# Write to file
print(f"writing to file: {csv_filename}")
with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    for key, value in dan_tags.items():
        # value structure: [Category, Count, Created At, Alias String]
        writer.writerow([key, value[0], value[1], value[3]])

print("Scraping complete.")

merge_into_tags_csv(csv_filename, filename_date)
upload_to_huggingface(csv_filename, filename_date)