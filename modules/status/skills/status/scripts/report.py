#!/usr/bin/env python3
"""Report the dates and structure of a project's `status.md`.

Reads the project only and never writes. The report depends on nothing but the
file and today's date, so the skill reading it interprets facts rather than
computing them.

Output, with empty groups left out:

    today: YYYY-MM-DD
    updated: YYYY-MM-DD, N days ago
    passed:          dated `Upcoming` items before today
    within 7 days:   dated items from today through the next 7 days
    later:           dated items after that
    not dated:       every other item: recurrences and `no date`
    structure:       missing sections, sections over their line limit, and
                     lines that could not be read

An item is dated when its text starts with `YYYY-MM-DD`. Nothing else is
interpreted: a recurrence stays text for the reader.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

SECTIONS = ["Last session", "In progress", "Next", "Upcoming"]
LINE_LIMITS = {"Last session": 5, "In progress": 5}
SOON_DAYS = 7
STALE_DAYS = 14

DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(?!\S)")


def fail(result, reason, next_step):
    print(f"result: {result}")
    print(f"reason: {reason}")
    print(f"next: {next_step}")
    return 1


def parse_date(text):
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def split_sections(lines):
    """The `Updated` value and the lines under each `##` heading."""
    updated = None
    sections = {}
    current = None
    for line in lines:
        heading = re.match(r"##\s+(.*?)\s*$", line)
        if heading:
            current = heading.group(1)
            sections[current] = []
            continue
        if current is None:
            match = re.match(r"Updated:\s*(.*?)\s*$", line)
            if match:
                updated = match.group(1)
            continue
        sections[current].append(line)
    return updated, sections


def list_items(lines):
    """Top-level `- ` items, with indented continuation lines joined on."""
    items = []
    for line in lines:
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif items and line.startswith(" ") and line.strip():
            items[-1] += " " + line.strip()
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", default=".", help="project directory to read (default: .)"
    )
    parser.add_argument(
        "--today", help="date to report against, YYYY-MM-DD (default: today)"
    )
    args = parser.parse_args()

    if args.today:
        today = parse_date(args.today)
        if today is None:
            return fail(
                f"refused to report: --today {args.today}",
                "the date is not in YYYY-MM-DD form",
                "pass a valid date, or omit --today",
            )
    else:
        today = datetime.date.today()

    path = Path(args.target).expanduser().resolve() / "status.md"
    if not path.is_file():
        return fail(
            f"no status file: {path}",
            "the project has no status.md",
            "create it from the status module's scaffold, or pass --target",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return fail(
            f"refused to report: {path}",
            f"the file could not be read: {error}",
            "repair the file and retry",
        )

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    updated, sections = split_sections(text.splitlines())
    structure = []

    print(f"today: {today.isoformat()}")
    if updated is None:
        print("updated: missing")
        structure.append("no `Updated:` line under the title")
    elif updated == "never":
        print("updated: never")
    else:
        updated_date = parse_date(updated)
        if updated_date is None:
            print(f"updated: {updated}")
            structure.append(f"`Updated: {updated}` is not a YYYY-MM-DD date")
        else:
            age = (today - updated_date).days
            days = "day" if age == 1 else "days"
            line = f"updated: {updated_date.isoformat()}, {age} {days} ago"
            if age > STALE_DAYS:
                line += f" - stale, over {STALE_DAYS} days"
            print(line)

    for name in SECTIONS:
        if name not in sections:
            structure.append(f"missing section: ## {name}")
    for name, limit in LINE_LIMITS.items():
        count = sum(1 for line in sections.get(name, []) if line.strip())
        if count > limit:
            structure.append(f"{name}: {count} lines, about {limit} expected")

    passed, soon, later, undated = [], [], [], []
    for item in list_items(sections.get("Upcoming", [])):
        match = DATE.match(item)
        if not match:
            undated.append(item)
            continue
        date = parse_date(match.group(1))
        if date is None:
            structure.append(f"not a valid date: {item}")
            undated.append(item)
        elif date < today:
            passed.append((date, item))
        elif (date - today).days <= SOON_DAYS:
            soon.append((date, item))
        else:
            later.append((date, item))

    groups = [
        ("passed", [item for _date, item in sorted(passed)]),
        (f"within {SOON_DAYS} days", [item for _date, item in sorted(soon)]),
        ("later", [item for _date, item in sorted(later)]),
        ("not dated", undated),
        ("structure", structure),
    ]
    for title, items in groups:
        if items:
            print()
            print(f"{title}:")
            for item in items:
                print(f"  {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
