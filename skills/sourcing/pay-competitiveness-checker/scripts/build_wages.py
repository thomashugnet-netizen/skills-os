#!/usr/bin/env python3
"""
Rebuilds references/wages.csv from the BLS OEWS metropolitan and
nonmetropolitan area file. Run it once a year, when BLS publishes the next
May estimates; the checker itself never needs it.

    python3 build_wages.py --from oesm25ma.zip --period "May 2025" --released 2026-05-15

Keeps only the frontline occupations listed in references/occupations.json, so
the shipped table stays small. Standard library only: the .xlsx inside the zip
is read as the XML it is.
"""

import csv
import io
import json
import os
import re
import sys
import zipfile
from datetime import date
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
KEEP = ["AREA", "AREA_TITLE", "AREA_TYPE", "PRIM_STATE", "OCC_CODE", "OCC_TITLE", "O_GROUP", "TOT_EMP",
        "H_MEAN", "H_PCT10", "H_PCT25", "H_MEDIAN", "H_PCT75", "H_PCT90", "HOURLY"]


def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def rows_of_xlsx(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    for _, el in ET.iterparse(z.open(sheet)):
        if el.tag != "{%s}row" % NS["m"]:
            continue
        out = {}
        for c in el.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is None:
                inline = c.find("m:is/m:t", NS)
                val = inline.text if inline is not None else ""
            else:
                val = v.text or ""
                if c.get("t") == "s":
                    val = shared[int(val)]
            out[col_index(c.get("r"))] = val
        width = max(out) + 1 if out else 0
        yield [out.get(i, "") for i in range(width)]
        el.clear()


def main(argv):
    src = argv[argv.index("--from") + 1]
    period = argv[argv.index("--period") + 1]
    released = argv[argv.index("--released") + 1]
    occs = json.load(open(os.path.join(REF, "occupations.json"), encoding="utf-8"))["occupations"]
    keep_codes = set(occs)

    outer = zipfile.ZipFile(src)
    # metropolitan areas and the nonmetropolitan "balance of state" areas ship as two workbooks
    books = [n for n in outer.namelist() if n.lower().endswith("_dl.xlsx")]
    if not books:
        sys.exit("no *_dl.xlsx workbook in the zip")

    def all_rows():
        for book in books:
            rows = rows_of_xlsx(outer.read(book))
            header = [h.strip().upper() for h in next(rows)]
            missing = [h for h in KEEP if h not in header and h != "HOURLY"]
            if missing:
                sys.exit(f"{book}: unexpected layout, missing " + ", ".join(missing))
            for r in rows:
                yield header, r

    def num(v):
        v = (v or "").strip()
        if v in ("", "*", "**", "#", "~"):
            return ""
        try:
            return f"{float(v):.2f}"
        except ValueError:
            return ""

    kept = areas = 0
    seen_areas = set()
    with open(os.path.join(REF, "wages.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["area_code", "area_title", "area_type", "state", "soc", "employment",
                    "p10", "p25", "median", "p75", "p90", "mean"])
        for header, r in all_rows():
            idx = {h: header.index(h) for h in KEEP if h in header}
            get = lambda k: r[idx[k]] if k in idx and idx[k] < len(r) else ""
            if get("OCC_CODE") not in keep_codes or get("O_GROUP").lower() not in ("detailed", ""):
                continue
            vals = [num(get(k)) for k in ("H_PCT10", "H_PCT25", "H_MEDIAN", "H_PCT75", "H_PCT90", "H_MEAN")]
            if not vals[2]:
                continue
            emp = re.sub(r"\D", "", get("TOT_EMP") or "")
            w.writerow([get("AREA"), get("AREA_TITLE"), get("AREA_TYPE"), get("PRIM_STATE"),
                        get("OCC_CODE"), emp] + vals)
            kept += 1
            seen_areas.add(get("AREA"))
    meta = {
        "source": "U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics (OEWS)",
        "dataset": "Metropolitan and nonmetropolitan area estimates, all industries",
        "reference_period": period,
        "released": released,
        "reference_date": "2025-05-15" if period == "May 2025" else None,
        "page": "https://www.bls.gov/oes/2025/may/oessrcma.htm",
        "file": os.path.basename(src) + " (" + ", ".join(os.path.basename(b) for b in books) + ")",
        "built": date.today().isoformat(),
        "rows": kept,
        "areas": len(seen_areas),
        "licence": "Public domain. BLS asks to be cited as the source: https://www.bls.gov/opub/copyright-information.htm",
        "note": "Hourly wages. Estimates BLS does not publish (too few responses, or over the top-coded value) are left blank and reported as such.",
    }
    json.dump(meta, open(os.path.join(REF, "wages_meta.json"), "w", encoding="utf-8"), indent=2)
    print(f"{kept} rows across {len(seen_areas)} areas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
