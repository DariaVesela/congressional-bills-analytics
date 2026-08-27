import xml.etree.ElementTree as ET
from typing import Optional

import duckdb
import requests
from config import BASE_URL, BILL_TYPES, COLLECTION, CONGRESS
from pydantic import BaseModel

# ---------- Models ----------


class Committee(BaseModel):
    systemCode: str
    name: str
    order: int


class Action(BaseModel):
    date: str
    text: str
    type: str
    action_code: Optional[str] = None
    source_system: str
    committees: list[Committee]


class Cosponsor(BaseModel):
    bioguideId: str
    fullName: str
    party: str


class Bill(BaseModel):
    congress: int
    bill_type: str
    number: str
    origin_chamber: str
    introduced_date: str
    sponsor_bioguide_id: str
    sponsor_full_name: str
    sponsor_party: str
    primary_policy_area: Optional[str] = None
    actions: list[Action]
    cosponsors: list[Cosponsor]


# ---------- Parsers ----------


def parse_committee(item: ET.Element, order: int) -> Committee:
    system_code_el = item.find("systemCode")
    assert system_code_el is not None, "no systemCode found"
    system_code = system_code_el.text
    name_el = item.find("name")
    assert name_el is not None, "no name found"
    name = name_el.text
    return Committee(systemCode=system_code, name=name, order=order)


def parse_action(item: ET.Element) -> Action:
    date_el = item.find("actionDate")
    assert date_el is not None, "no date found"
    text_el = item.find("text")
    assert text_el is not None, "no text found"
    type_el = item.find("type")
    assert type_el is not None, "no type found"

    action_code_el = item.find("actionCode")
    action_code = action_code_el.text if action_code_el is not None else None

    source_system_el = item.find("sourceSystem")
    assert source_system_el is not None, "no sourceSystem found"
    source_system_name_el = source_system_el.find("name")
    assert source_system_name_el is not None, "no sourceSystem name found"

    committees_el = item.find("committees")
    committees = (
        [
            parse_committee(c, order=i)
            for i, c in enumerate(committees_el.findall("item"))
        ]
        if committees_el is not None
        else []
    )

    return Action(
        date=date_el.text,
        text=text_el.text,
        type=type_el.text,
        action_code=action_code,
        source_system=source_system_name_el.text,
        committees=committees,
    )


def parse_cosponsor(item: ET.Element) -> Cosponsor:
    bioguide_id_el = item.find("bioguideId")
    assert bioguide_id_el is not None, "no bioguideId found"
    full_name_el = item.find("fullName")
    assert full_name_el is not None, "no fullName found"
    party_el = item.find("party")
    assert party_el is not None, "no party found"
    return Cosponsor(
        bioguideId=bioguide_id_el.text, fullName=full_name_el.text, party=party_el.text
    )


def parse_bill(root: ET.Element) -> Bill:
    # TODO: harden with explicit asserts before final review pass (Section 9)
    bill_el = root.find("bill")
    assert bill_el is not None, "expected <bill> element"

    sponsor_item = bill_el.find("sponsors").find("item")
    assert sponsor_item is not None, "no sponsor found"

    policy_area_el = bill_el.find("policyArea")
    primary_policy_area = None
    if policy_area_el is not None:
        name_el = policy_area_el.find("name")
        if name_el is not None and name_el.text and name_el.text.strip():
            primary_policy_area = name_el.text

    actions_el = bill_el.find("actions")
    actions = (
        [parse_action(i) for i in actions_el.findall("item")]
        if actions_el is not None
        else []
    )

    cosponsors_el = bill_el.find("cosponsors")
    cosponsors = (
        [parse_cosponsor(i) for i in cosponsors_el.findall("item")]
        if cosponsors_el is not None
        else []
    )

    return Bill(
        congress=int(bill_el.find("congress").text),
        bill_type=bill_el.find("type").text,
        number=bill_el.find("number").text,
        origin_chamber=bill_el.find("originChamber").text,
        introduced_date=bill_el.find("introducedDate").text,
        sponsor_bioguide_id=sponsor_item.find("bioguideId").text,
        sponsor_full_name=sponsor_item.find("fullName").text,
        sponsor_party=sponsor_item.find("party").text,
        primary_policy_area=primary_policy_area,
        actions=actions,
        cosponsors=cosponsors,
    )


# ---------- Extraction ----------


def fetch_directory_listing(bill_type: str) -> dict:
    url = f"{BASE_URL}/json/{COLLECTION}/{CONGRESS}/{bill_type}"
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_all_bills(limit_per_type: Optional[int] = None) -> list[Bill]:
    bills, errors = [], []
    for bill_type in BILL_TYPES:
        listing = fetch_directory_listing(bill_type)
        xml_files = [f for f in listing["files"] if f["fileExtension"] == "xml"]
        if limit_per_type:
            xml_files = xml_files[:limit_per_type]

        for f in xml_files:
            try:
                response = requests.get(f["link"], timeout=30)
                response.raise_for_status()
                bills.append(parse_bill(ET.fromstring(response.content)))
            except Exception as e:  # noqa: BLE001 — deliberate: one bad bill logs and continues, per E01-S05
                errors.append((f["link"], str(e)))

    print(f"Extracted {len(bills)} bills, {len(errors)} errors")
    for link, err in errors[:20]:
        print(f"  FAILED: {link} -> {err}")
    return bills


# ---------- Load ----------


def load_to_duckdb(bills: list[Bill], db_path: str = "../warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)
    con.execute(
        "CREATE OR REPLACE TABLE raw_bills (bill_id VARCHAR, congress INTEGER, bill_type VARCHAR, number VARCHAR, origin_chamber VARCHAR, introduced_date VARCHAR, sponsor_bioguide_id VARCHAR, sponsor_full_name VARCHAR, sponsor_party VARCHAR, primary_policy_area VARCHAR)"
    )
    con.execute(
        "CREATE OR REPLACE TABLE raw_actions (action_id VARCHAR, bill_id VARCHAR, action_date VARCHAR, text VARCHAR, type VARCHAR, action_code VARCHAR, source_system VARCHAR)"
    )
    con.execute(
        "CREATE OR REPLACE TABLE raw_action_committees (action_id VARCHAR, bill_id VARCHAR, system_code VARCHAR, name VARCHAR, committee_order INTEGER)"
    )
    con.execute(
        "CREATE OR REPLACE TABLE raw_cosponsors (bill_id VARCHAR, bioguide_id VARCHAR, full_name VARCHAR, party VARCHAR)"
    )

    bills_rows, actions_rows, committees_rows, cosponsors_rows = [], [], [], []
    for bill in bills:
        bill_id = f"{bill.bill_type}{bill.number}-{bill.congress}"
        bills_rows.append(
            (
                bill_id,
                bill.congress,
                bill.bill_type,
                bill.number,
                bill.origin_chamber,
                bill.introduced_date,
                bill.sponsor_bioguide_id,
                bill.sponsor_full_name,
                bill.sponsor_party,
                bill.primary_policy_area,
            )
        )
        for i, action in enumerate(bill.actions):
            action_id = f"{bill_id}-a{i}"
            actions_rows.append(
                (
                    action_id,
                    bill_id,
                    action.date,
                    action.text,
                    action.type,
                    action.action_code,
                    action.source_system,
                )
            )
            for c in action.committees:
                committees_rows.append(
                    (action_id, bill_id, c.systemCode, c.name, c.order)
                )
        for cs in bill.cosponsors:
            cosponsors_rows.append((bill_id, cs.bioguideId, cs.fullName, cs.party))

    con.executemany("INSERT INTO raw_bills VALUES (?,?,?,?,?,?,?,?,?,?)", bills_rows)
    con.executemany("INSERT INTO raw_actions VALUES (?,?,?,?,?,?,?)", actions_rows)
    con.executemany(
        "INSERT INTO raw_action_committees VALUES (?,?,?,?,?)", committees_rows
    )
    con.executemany("INSERT INTO raw_cosponsors VALUES (?,?,?,?)", cosponsors_rows)
    con.close()
    print(
        f"Loaded {len(bills_rows)} bills, {len(actions_rows)} actions, {len(committees_rows)} committee links, {len(cosponsors_rows)} cosponsors"
    )


if __name__ == "__main__":
    bills = extract_all_bills(limit_per_type=50)
    load_to_duckdb(bills)
