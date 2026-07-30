import requests
from config import BASE_URL, COLLECTION, CONGRESS, BILL_TYPES

def fetch_directory_listing(bill_type: str) -> dict:
    url = f"{BASE_URL}/json/{COLLECTION}/{CONGRESS}/{bill_type}"
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    for bill_type in BILL_TYPES:
        listing = fetch_directory_listing(bill_type)
        files = listing["files"]  
        print(f"{bill_type}: {len(files)} files found, e.g. {files[0]['name']}")