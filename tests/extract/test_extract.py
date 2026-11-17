import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "extract"))

import xml.etree.ElementTree as ET

import pytest

from extract import parse_action, parse_bill

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def bill_zero_cosponsors():
    xml_content = (FIXTURES_DIR / "bill_zero_cosponsors.xml").read_text()
    return ET.fromstring(xml_content)


def test_parse_bill_zero_cosponsors(bill_zero_cosponsors):
    bill = parse_bill(bill_zero_cosponsors)
    assert bill.cosponsors == []


@pytest.fixture
def bill_became_law():
    xml_content = (FIXTURES_DIR / "bill_became_law.xml").read_text()
    return ET.fromstring(xml_content)


def test_parse_bill_became_law(bill_became_law):
    bill = parse_bill(bill_became_law)
    action_types = [action.type for action in bill.actions]
    assert "BecameLaw" in action_types


@pytest.fixture
def bill_missing_action_code():
    xml_content = (FIXTURES_DIR / "bill_missing_action_code.xml").read_text()
    return ET.fromstring(xml_content)


def test_parse_action_missing_action_code(bill_missing_action_code):
    root = bill_missing_action_code
    first_action = root.find("bill").find("actions").find("item")
    action = parse_action(first_action)

    assert action.action_code is None
    assert action.type == "IntroReferral"
    assert action.source_system == "Senate"


@pytest.fixture
def bill_multiple_committees():
    xml_content = (FIXTURES_DIR / "bill_multiple_committees.xml").read_text()
    return ET.fromstring(xml_content)


def test_parse_action_multiple_committees(bill_multiple_committees):
    root = bill_multiple_committees
    all_actions = root.find("bill").find("actions").findall("item")
    target_action = next(
        a
        for a in all_actions
        if a.find("committees") is not None
        and len(a.find("committees").findall("item")) > 1
    )
    action = parse_action(target_action)

    assert len(action.committees) == 2
    assert action.committees[0].order == 0
    assert action.committees[1].order == 1
