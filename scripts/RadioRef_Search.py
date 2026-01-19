import requests
from bs4 import BeautifulSoup

# RadioReference county page URL for Cook County, IL
url = "https://www.radioreference.com/apps/db/?ctid=606"

# Make the HTTP request
response = requests.get(url)
response.raise_for_status()

soup = BeautifulSoup(response.text, 'html.parser')

# Find all frequency tables on the page
tables = soup.select("table.db-table")

all_freqs = []

for table in tables:
    headers = [th.get_text(strip=True) for th in table.select("thead th")]
    rows = []
    for tr in table.select("tbody tr"):
        values = [td.get_text(strip=True) for td in tr.find_all("td")]
        if values:
            # Convert row into dict {header: value}
            row_data = dict(zip(headers, values))
            rows.append(row_data)
    all_freqs.extend(rows)

# Print frequencies extracted
for entry in all_freqs:
    print(entry)
# Example output processing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             