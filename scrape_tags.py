import os
import requests
import collections
import csv
import time
import datetime
import subprocess

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

# Add file to repo
print("Running git commands...")
try:
    # Add file
    subprocess.run(["git", "add", csv_filename], check=True)
    
    # Commit
    commit_msg = f"Update danbooru tags {filename_date}"
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    
    # Push
    subprocess.run(["git", "push"], check=True)
    
    print("Git add, commit, and push successful.")
except subprocess.CalledProcessError as e:
    print(f"An error occurred during git operations: {e}")