#!/usr/bin/env python3
"""
Data Validation Script for CivicAssist Greenfield Municipal Knowledge Base
Validates waste_schedule.json, permits.csv, and events.json for:
- Missing fields / missing values
- Duplicate IDs
- Invalid dates
- Invalid pickup days
- Invalid permit fees
- JSON/CSV structure integrity
"""

import os
import sys
import json
import csv
import re
from datetime import datetime

# Configure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
WASTE_FILE = os.path.join(DATA_DIR, "waste_schedule.json")
PERMITS_FILE = os.path.join(DATA_DIR, "permits.csv")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")

VALID_DAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "daily (monday through sunday)"
}

def validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def validate_waste_data():
    issues = []
    zones_seen = set()

    if not os.path.exists(WASTE_FILE):
        return ["CRITICAL: waste_schedule.json does not exist"], 0

    try:
        with open(WASTE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"CRITICAL: Failed to parse waste_schedule.json: {e}"], 0

    if not isinstance(data, list) or len(data) < 10:
        issues.append(f"Warning: Expected at least 10 zones in waste_schedule.json, found {len(data)}")

    required_fields = [
        "zone", "area", "waste_type", "pickup_days", "pickup_time",
        "special_instructions", "contact_information", "last_updated"
    ]

    for idx, item in enumerate(data):
        identifier = item.get("zone", f"Index {idx}")

        for field in required_fields:
            if field not in item or item[field] is None or (isinstance(item[field], str) and not item[field].strip()):
                issues.append(f"[{identifier}] Missing required field: {field}")

        zone = item.get("zone", "").strip()
        if zone in zones_seen:
            issues.append(f"[{identifier}] Duplicate zone identifier: {zone}")
        zones_seen.add(zone)

        days = item.get("pickup_days", [])
        if not isinstance(days, list) or len(days) == 0:
            issues.append(f"[{identifier}] pickup_days must be a non-empty list")
        else:
            for d in days:
                if d.lower() not in VALID_DAYS:
                    issues.append(f"[{identifier}] Invalid pickup day: '{d}'")

        last_updated = item.get("last_updated", "")
        if not validate_date(last_updated):
            issues.append(f"[{identifier}] Invalid last_updated date: '{last_updated}' (expected YYYY-MM-DD)")

    return issues, len(data)

def validate_permits_data():
    issues = []
    permit_ids_seen = set()

    if not os.path.exists(PERMITS_FILE):
        return ["CRITICAL: permits.csv does not exist"], 0

    required_columns = [
        "permit_id", "permit_type", "description", "requirements", "documents",
        "fee", "processing_time", "application_method", "office", "contact", "last_updated"
    ]

    records = []
    try:
        with open(PERMITS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Check headers
            missing_cols = [c for c in required_columns if c not in (reader.fieldnames or [])]
            if missing_cols:
                issues.append(f"CRITICAL: Missing columns in permits.csv: {missing_cols}")

            for row in reader:
                records.append(row)
    except Exception as e:
        return [f"CRITICAL: Failed to parse permits.csv: {e}"], 0

    if len(records) < 10:
        issues.append(f"Warning: Expected at least 10 permit records, found {len(records)}")

    for idx, row in enumerate(records):
        pid = row.get("permit_id", f"Row {idx+1}").strip()
        if pid in permit_ids_seen:
            issues.append(f"[{pid}] Duplicate permit_id: {pid}")
        permit_ids_seen.add(pid)

        for col in required_columns:
            val = row.get(col, "").strip()
            if not val:
                issues.append(f"[{pid}] Missing or empty value for column: '{col}'")

        fee = row.get("fee", "").strip()
        if fee and not re.search(r"\$\d+", fee) and fee.lower() != "free":
            issues.append(f"[{pid}] Unrecognized fee format: '{fee}'")

        last_updated = row.get("last_updated", "").strip()
        if not validate_date(last_updated):
            issues.append(f"[{pid}] Invalid last_updated date: '{last_updated}'")

    return issues, len(records)

def validate_events_data():
    issues = []
    event_ids_seen = set()

    if not os.path.exists(EVENTS_FILE):
        return ["CRITICAL: events.json does not exist"], 0

    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"CRITICAL: Failed to parse events.json: {e}"], 0

    if not isinstance(data, list) or len(data) < 15:
        issues.append(f"Warning: Expected at least 15 events in events.json, found {len(data)}")

    required_fields = [
        "event_id", "name", "category", "date", "start_time",
        "end_time", "location", "description", "organizer", "outdoor", "last_updated"
    ]

    for idx, item in enumerate(data):
        eid = item.get("event_id", f"Index {idx}")
        if eid in event_ids_seen:
            issues.append(f"[{eid}] Duplicate event_id: {eid}")
        event_ids_seen.add(eid)

        for field in required_fields:
            if field not in item or item[field] is None:
                issues.append(f"[{eid}] Missing field: {field}")
            elif isinstance(item[field], str) and not item[field].strip():
                issues.append(f"[{eid}] Empty string for required field: {field}")

        date_val = item.get("date", "")
        if not validate_date(date_val):
            issues.append(f"[{eid}] Invalid event date format: '{date_val}' (expected YYYY-MM-DD)")

        if not isinstance(item.get("outdoor"), bool):
            issues.append(f"[{eid}] 'outdoor' field must be boolean (true/false)")

    return issues, len(data)

def run_validation():
    print("============================================================")
    print("CIVICASSIST - GREENFIELD MUNICIPAL DATA VALIDATION REPORT")
    print("============================================================")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("Municipal Entity: Greenfield Municipal Corporation (Synthetic / Demo)")
    print("------------------------------------------------------------\n")

    all_passed = True

    # 1. Waste
    waste_issues, waste_count = validate_waste_data()
    print(f"1. Waste Management Schedule ({WASTE_FILE}):")
    print(f"   • Total Zones Validated: {waste_count}")
    if waste_issues:
        all_passed = False
        print(f"   ❌ Found {len(waste_issues)} issue(s):")
        for iss in waste_issues:
            print(f"     - {iss}")
    else:
        print("   ✅ PASSED: All zones have complete fields, valid days, and format.")

    print()

    # 2. Permits
    permit_issues, permit_count = validate_permits_data()
    print(f"2. Municipal Permits Registry ({PERMITS_FILE}):")
    print(f"   • Total Permits Validated: {permit_count}")
    if permit_issues:
        all_passed = False
        print(f"   ❌ Found {len(permit_issues)} issue(s):")
        for iss in permit_issues:
            print(f"     - {iss}")
    else:
        print("   ✅ PASSED: All permits contain fees, requirements, SLAs, and contact info.")

    print()

    # 3. Events
    event_issues, event_count = validate_events_data()
    print(f"3. City Events & Public Schedules ({EVENTS_FILE}):")
    print(f"   • Total Events Validated: {event_count}")
    if event_issues:
        all_passed = False
        print(f"   ❌ Found {len(event_issues)} issue(s):")
        for iss in event_issues:
            print(f"     - {iss}")
    else:
        print("   ✅ PASSED: All events have verified dates, outdoor flags, and locations.")

    print("\n------------------------------------------------------------")
    if all_passed:
        print("SUMMARY: 100% DATA VALIDATION SUCCESSFUL. NO INTEGRITY ISSUES.")
        print("============================================================")
        return 0
    else:
        print("SUMMARY: VALIDATION FAILED WITH ISSUES FOUND.")
        print("============================================================")
        return 1

if __name__ == "__main__":
    exit_code = run_validation()
    sys.exit(exit_code)
