import os
import pandas as pd
import requests
import re
from flask import Flask, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import time
import random

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

# Define keywords to search for in job titles
keywords = [
    "data science",
    "data",
    "ai", 
    "software",
    "new grad",
    "entry",
    "2025"
]

ban_keywords = [
    'manager',
    'senior'
]

# Define regex pattern for job titles
keyword_pattern = re.compile(r'\b(?:' + '|'.join(re.escape(keyword) for keyword in keywords) + r')\b', re.IGNORECASE)
ban_keywords_pattern = re.compile(r'\b(?:' + '|'.join(re.escape(keyword) for keyword in ban_keywords) + r')\b', re.IGNORECASE)
# Headers to mimic a browser request
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.110 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Load previous job listings if the file exists, ignoring the header
previous_jobs_file = "parsed_job_listings.txt"
try:
    previous_jobs_df = pd.read_table(previous_jobs_file, delimiter="|", skiprows=1, names=["Company", "URL", "Job Title"])
    previous_jobs_set = set((row.URL.strip(), row["Job Title"].strip()) for _, row in previous_jobs_df.iterrows())
except FileNotFoundError:
    previous_jobs_set = set()
    print("No previous job listings found. This is the first run.")

def fetch_jobs(url):
    """Fetch and parse unique job titles from a URL, including nested tags."""
    print("looking at ", url)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    jobs = []
    seen_jobs = set()  # Set to track unique job titles for this URL

    # Traverse all specified tags and their nested descendants
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'a', 'span', 'div', 'li', 'button', 'section', 'main', 'body']):
        # Use .descendants to go through all nested tags within each found tag
        for descendant in tag.descendants:
            if descendant.get_text(strip=True):
                text = descendant.get_text(strip=True).lower()
                if keyword_pattern.search(text) and len(text) < 60 and not ban_keywords_pattern.search(text):
                    company_name = url.split("//")[1].split("/")[0]
                    job_entry = (company_name, url, text)
                    # Only add if this job title hasn't been seen on this page
                    if job_entry not in seen_jobs:
                        jobs.append(job_entry)
                        seen_jobs.add(job_entry)  # Mark this job as seen
                        print(f"Found job title: {text}")

    return jobs


@app.route('/api/parse-jobs', methods=['GET'])
def parse_jobs():
    """Parse jobs from local Excel file and return results."""
    file_path = './jobs-parsing.xlsx'
    if not os.path.exists(file_path):
        return jsonify({"error": "jobs-parsing.xlsx file not found."}), 404

    df = pd.read_excel(file_path)
    new_jobs = []
    current_output = []

    for _, row in df.iterrows():
        url = row.get('website')
        if not url:
            continue

        jobs = fetch_jobs(url)
        for job in jobs:
            current_output.append({"company": job[0], "url": job[1], "title": job[2]})
            if (job[1].strip(), job[2].strip()) not in previous_jobs_set:
                new_jobs.append({"company": job[0], "url": job[1], "title": job[2]})

        # Add a random sleep to avoid overwhelming the server
        time.sleep(random.uniform(1, 3))

    # Save all current job listings for next comparison
    with open(previous_jobs_file, "w") as f:
        f.write("Company Name | Link to Job | Title Of Job\n")
        for job in current_output:
            f.write(f"{job['company']} | {job['url']} | {job['title']}\n")

    # Save new job listings to `new_job_listings.txt` for next run
    if new_jobs:
        with open("new_job_listings.txt", "w") as f:
            f.write("Company Name | Link to Job | Title Of Job\n")
            for job in new_jobs:
                f.write(f"{job['company']} | {job['url']} | {job['title']}\n")
    else:
        # Clear the file if there are no new roles
        open("new_job_listings.txt", "w").close()
        print("No new roles found. new_job_listings.txt has been cleared.")

    return jsonify({
        "currentOutput": current_output,
        "differenceOutput": new_jobs
    })

if __name__ == '__main__':
    app.run(debug=True)
