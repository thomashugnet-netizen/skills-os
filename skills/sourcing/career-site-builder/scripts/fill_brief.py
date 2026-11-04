#!/usr/bin/env python3
"""
Fills references/brief.md for one employer and prints it, ready to copy.

The brief is used word for word; only four blanks change. Doing the
substitution in code rather than by hand is what guarantees the rest of the
text arrives unchanged.

    fill_brief.py --company "Northline Fuel & Market" --colour "deep blue" \
        --segments "store team members, store leadership, food service roles" \
        --pages "Store Careers|Store Leadership|Food Service Careers"

Standard library only.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRIEF = os.path.join(os.path.dirname(HERE), "references", "brief.md")


def template():
    text = open(BRIEF, encoding="utf-8").read()
    start = text.index("## The brief\n") + len("## The brief\n")
    end = text.index("## How I carry it out here")
    return text[start:end].strip() + "\n"


def fill(company, colour, segments, pages):
    out = template()
    out = out.replace("{segment pages}", "\n".join(f"- {p.strip()}" for p in pages if p.strip()))
    out = (out.replace("{Company}", company)
              .replace("{brand colour}", colour)
              .replace("{talent segments}", segments))
    left = re.findall(r"\{[a-z][a-z ]*\}|\{Company\}", out)
    if left:
        sys.exit(f"fill_brief: blanks left unfilled: {', '.join(sorted(set(left)))}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Fill the careers site brief for one employer.")
    ap.add_argument("--company", required=True)
    ap.add_argument("--colour", required=True, help='the brand colour by name, e.g. "red"')
    ap.add_argument("--segments", required=True, help="comma-separated talent segments")
    ap.add_argument("--pages", required=True, help="segment page names separated by |")
    a = ap.parse_args()
    print(fill(a.company, a.colour, a.segments, a.pages.split("|")))


if __name__ == "__main__":
    main()
