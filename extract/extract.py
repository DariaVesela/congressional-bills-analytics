import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from config import BASE_URL, COLLECTION, CONGRESS, BILL_TYPES


def fetch_directory_listing(bill_type: str) -> dict:
    url = f"{BASE_URL}/json/{COLLECTION}/{CONGRESS}/{bill_type}"
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()


def check_policy_area(link: str) -> str:
    response = requests.get(link, timeout=30)
    response.raise_for_status()
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        print(f"FAILED to parse: {link}")
        print(f"Status code: {response.status_code}")
        print(f"First 200 chars: {response.content[:200]}")
        raise

    root = ET.fromstring(response.content)
    bill = root.find("bill")
    assert bill is not None, f"expected <bill> in {link}"

    policy_area = bill.find("policyArea")
    if policy_area is None:
        return "missing_entirely"

    name = policy_area.find("name")
    if name is None or not name.text or not name.text.strip():
        return "present_but_empty"

    return "has_name"


if __name__ == "__main__":
    listing = fetch_directory_listing("s")
    xml_files = [f for f in listing["files"] if f["fileExtension"] == "xml"]

    newest_first = sorted(
        xml_files,
        key=lambda f: datetime.strptime(f["formattedLastModifiedTime"], "%d-%b-%Y %H:%M"),
        reverse=True,
    )
    sample = newest_first[:20]

    counts = {"has_name": 0, "present_but_empty": 0, "missing_entirely": 0}
    for file in sample:
        result = check_policy_area(file["link"])
        counts[result] += 1
        print(file["name"], "->", result)

    print()
    print(counts)