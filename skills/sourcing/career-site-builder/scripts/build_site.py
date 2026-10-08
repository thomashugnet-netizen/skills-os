#!/usr/bin/env python3
"""
Turns a folder of hand-written pages and a CSV of jobs into a complete,
crawlable careers site.

Why this exists
---------------
The parts of a careers site that decide whether anyone finds it are also the
parts a person gets wrong by hand: one page per job with valid JobPosting
markup, one page per location, a sitemap that lists every page, an llms.txt
that tells AI assistants what the site contains, and a job list that is in
the HTML rather than painted in by JavaScript. Every one of those is
mechanical, so it is done by code, the same way every time.

The hand-written pages (home, career areas, FAQ, hiring process) stay hand
written. This script never edits their copy. It only fills the three slots it
owns (the job list, the location list, the FAQ markup) and copies the header
and footer from index.html onto every other page, so a nav change is made once.

    build_site.py --site SITE_DIR [--jobs jobs.csv] [--base-url URL] [--demo]

If SITE_DIR does not exist it is created from references/starter. --demo uses
the fictional sample in references/sample/northline_jobs.csv.

Standard library only. No network.
"""

import argparse
import csv
import datetime
import html
import json
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
STARTER = os.path.join(SKILL, "references", "starter")
SAMPLE = os.path.join(SKILL, "references", "sample", "northline_jobs.csv")
PLACEHOLDER_BASE = "https://careers.example.com"
GENERATOR = '<meta name="generator" content="career-site-builder">'

REQUIRED = ["job_id", "title", "category", "city", "region", "country",
            "pay_min", "pay_max", "pay_unit", "employment_type", "schedule",
            "date_posted", "apply_url", "summary"]
OPTIONAL = ["postal_code", "street_address", "currency", "valid_through",
            "duties", "requirements", "benefits"]

CATEGORY_LABELS = {
    "store-teams": "Store teams", "food-service": "Food service",
    "store-leadership": "Store leadership", "distribution": "Distribution and driving",
    "maintenance": "Maintenance and trades", "corporate": "Office and corporate",
}
EMPLOYMENT_LABELS = {
    "FULL_TIME": "Full-time", "PART_TIME": "Part-time", "CONTRACTOR": "Contract",
    "TEMPORARY": "Temporary", "SEASONAL": "Seasonal", "INTERN": "Internship",
    "PER_DIEM": "Per diem", "OTHER": "Other",
}
UNIT_WORDS = {"HOUR": "an hour", "DAY": "a day", "WEEK": "a week",
              "MONTH": "a month", "YEAR": "a year"}


def die(msg):
    print(f"build_site: {msg}", file=sys.stderr)
    sys.exit(2)


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "item"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def money(v, unit, cur):
    sym = "$" if cur in ("USD", "CAD", "AUD", "") else ""
    n = float(v)
    txt = f"{n:,.0f}" if unit == "YEAR" or n >= 1000 else f"{n:,.2f}"
    return f"{sym}{txt}" if sym else f"{txt} {cur}"


def fit_title(main, brand, limit=70):
    """Search results cut titles at roughly 60 to 70 characters, so the part a
    candidate searched for goes first and the brand is dropped before it is."""
    for t in (f"{main} | {brand} careers", f"{main} | {brand}", main):
        if len(t) <= limit:
            return t
    return main[:limit]


def pay_label(j):
    if not (j["pay_min"] or j["pay_max"]):
        return ""
    cur = j.get("currency") or "USD"
    unit = j["pay_unit"].upper()
    lo = money(j["pay_min"] or j["pay_max"], unit, cur)
    hi = money(j["pay_max"], unit, cur) if j["pay_max"] and j["pay_max"] != j["pay_min"] else ""
    rng = f"{lo} to {hi}" if hi else lo
    return f"{rng} {UNIT_WORDS.get(unit, '')}".strip()


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_jobs(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = [c.strip() for c in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            die("the jobs file is missing required columns: " + ", ".join(missing)
                + ". See references/seo-ai-spec.md for what each one is for.")
        rows = []
        for i, raw in enumerate(reader, start=2):
            j = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
            for k in OPTIONAL:
                j.setdefault(k, "")
            empty = [k for k in ("job_id", "title", "city", "apply_url", "date_posted") if not j[k]]
            if empty:
                die(f"row {i} has no {', '.join(empty)}; a job page cannot be built without it")
            if not (j["pay_min"] or j["pay_max"]):
                print(f"build_site: warning, {j['job_id']} has no pay. The page will say so, "
                      "and check_site.py will flag it.", file=sys.stderr)
            j["slug"] = f"{slugify(j['title'])}-{slugify(j['city'])}-{slugify(j['job_id'])}"
            j["loc_slug"] = f"{slugify(j['city'])}-{slugify(j['region'])}"
            j["category_label"] = CATEGORY_LABELS.get(j["category"], j["category"].replace("-", " ").capitalize())
            j["pay_label"] = pay_label(j)
            rows.append(j)
    ids = [j["job_id"] for j in rows]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        die("duplicate job_id values: " + ", ".join(dupes))
    return rows


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def meta(text, name):
    m = re.search(r'<meta\s+name="%s"\s+content="([^"]*)"' % name, text)
    return html.unescape(m.group(1)) if m else ""


def title_of(text):
    m = re.search(r"<title>(.*?)</title>", text, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def brand_of(index_html):
    for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', index_html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Organization" and data.get("name"):
            return data["name"]
    return "Our company"


# --------------------------------------------------------------------------
# Shared chrome
# --------------------------------------------------------------------------

HEADER_RE = re.compile(r'<header class="site-header">.*?</header>', re.S)
FOOTER_RE = re.compile(r'<footer class="site-footer">.*?</footer>', re.S)
DIALOG_RE = re.compile(r'<dialog class="upsell".*?</dialog>', re.S)
URL_ATTR_RE = re.compile(r'\b(href|src)="([^"]*)"')


def rebase(fragment, depth):
    """Make the root-relative links in a header or footer work from a page
    `depth` folders down. Absolute, anchor, mail and data URLs are left alone."""
    if depth == 0:
        return fragment
    prefix = "../" * depth

    def fix(m):
        attr, url = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|tel:|data:|#|/|\.\./)", url) or not url:
            return m.group(0)
        return f'{attr}="{prefix}{url}"'
    return URL_ATTR_RE.sub(fix, fragment)


def page(site, rel, head_extra, title, description, canonical_rel, body, chrome, brand, depth):
    header, footer, dialog = chrome
    css = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{GENERATOR}
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{PLACEHOLDER_BASE}/{canonical_rel}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<link rel="stylesheet" href="{css}css/tokens.css">
<link rel="stylesheet" href="{css}css/site.css">
{head_extra}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
{rebase(header, depth)}
<main id="main">
{body}
</main>
{rebase(footer, depth)}
{dialog}
<script src="{css}js/site.js" defer></script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Job pages
# --------------------------------------------------------------------------

def bullets(s):
    items = [x.strip() for x in (s or "").split("|") if x.strip()]
    return items


def job_jsonld(j, brand):
    desc = f"<p>{esc(j['summary'])}</p>"
    if bullets(j["duties"]):
        desc += "<p>What you will do:</p><ul>" + "".join(f"<li>{esc(x)}</li>" for x in bullets(j["duties"])) + "</ul>"
    if bullets(j["requirements"]):
        desc += "<p>What you need:</p><ul>" + "".join(f"<li>{esc(x)}</li>" for x in bullets(j["requirements"])) + "</ul>"
    desc += f"<p>Schedule: {esc(j['schedule'])}</p>"
    address = {"@type": "PostalAddress", "addressLocality": j["city"],
               "addressRegion": j["region"], "addressCountry": j["country"]}
    if j["postal_code"]:
        address["postalCode"] = j["postal_code"]
    if j["street_address"]:
        address["streetAddress"] = j["street_address"]
    data = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": j["title"],
        "description": desc,
        "identifier": {"@type": "PropertyValue", "name": brand, "value": j["job_id"]},
        "datePosted": j["date_posted"],
        "employmentType": j["employment_type"],
        "hiringOrganization": {"@type": "Organization", "name": brand, "sameAs": PLACEHOLDER_BASE + "/"},
        "jobLocation": {"@type": "Place", "address": address},
        "directApply": False,
    }
    if bullets(j["benefits"]):
        data["jobBenefits"] = ", ".join(bullets(j["benefits"]))
    if j["valid_through"]:
        data["validThrough"] = j["valid_through"] + ("T23:59" if len(j["valid_through"]) == 10 else "")
    if j["pay_min"] or j["pay_max"]:
        value = {"@type": "QuantitativeValue", "unitText": j["pay_unit"].upper()}
        if j["pay_min"]:
            value["minValue"] = float(j["pay_min"])
        if j["pay_max"]:
            value["maxValue"] = float(j["pay_max"])
        data["baseSalary"] = {"@type": "MonetaryAmount", "currency": j.get("currency") or "USD", "value": value}
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")
            + "\n</script>")


def job_page(j, brand, chrome):
    pay = (f'<p class="pay">{esc(j["pay_label"])}</p>' if j["pay_label"]
           else '<p class="pay">Pay is discussed at interview</p>')
    duties = "".join(f"<li>{esc(x)}</li>" for x in bullets(j["duties"]))
    reqs = "".join(f"<li>{esc(x)}</li>" for x in bullets(j["requirements"]))
    perks = "".join(f"<li>{esc(x)}</li>" for x in bullets(j["benefits"]))
    benefits = (f"<h2>Pay and benefits</h2><ul>{perks}</ul>" if perks else
                '<h2>Pay and benefits</h2><p>Benefits for this role are described under '
                '<a href="../index.html#benefits">pay and benefits</a>.</p>')
    emp = EMPLOYMENT_LABELS.get(j["employment_type"].upper(), j["employment_type"])
    body = f"""  <section class="job-head">
    <div class="wrap grid grid--2">
      <div>
        <p class="eyebrow">{esc(j['category_label'])} &middot; {esc(emp)}</p>
        <h1>{esc(j['title'])}</h1>
        <p class="lead">{esc(j['city'])}, {esc(j['region'])}</p>
        {pay}
        <p><strong>Schedule:</strong> {esc(j['schedule'])}</p>
      </div>
      <div class="apply-box">
        <p><strong>Applying takes about five minutes.</strong></p>
        <p><a class="btn btn--primary" href="{esc(j['apply_url'])}">Apply for this job</a></p>
        <p class="handoff-note">You will finish your application on our hiring partner's secure site, which looks different from this one. Your progress is saved as you go.</p>
      </div>
    </div>
  </section>
  <section class="section">
    <div class="wrap grid grid--2">
      <div>
        <h2>About the job</h2>
        <p>{esc(j['summary'])}</p>
        {"<h2>What you will do</h2><ul>" + duties + "</ul>" if duties else ""}
        {"<h2>What you need</h2><ul>" + reqs + "</ul>" if reqs else ""}
        {benefits}
      </div>
      <div class="card">
        <h2>More near {esc(j['city'])}</h2>
        <p>See every open job in {esc(j['city'])}, or search all locations.</p>
        <p><a href="../locations/{j['loc_slug']}.html">Jobs in {esc(j['city'])}, {esc(j['region'])}</a></p>
        <p><a href="../index.html#search">Search all jobs</a></p>
      </div>
    </div>
  </section>"""
    desc = f"{j['title']} in {j['city']}, {j['region']}. {j['pay_label'] + '. ' if j['pay_label'] else ''}{j['schedule']}. Apply in about five minutes."
    return page(None, None, job_jsonld(j, brand),
                fit_title(f"{j['title']} in {j['city']}, {j['region']}", brand),
                desc[:300], f"jobs/{j['slug']}.html", body, chrome, brand, 1)


def location_page(city, region, jobs, brand, chrome):
    items = "\n".join(
        f'        <li><a href="../jobs/{j["slug"]}.html">{esc(j["title"])}</a>'
        f'<p class="job-meta"><span>{esc(j["pay_label"])}</span><span>{esc(j["schedule"])}</span></p></li>'
        for j in jobs)
    cats = sorted({j["category_label"] for j in jobs})
    body = f"""  <section class="job-head">
    <div class="wrap">
      <p class="eyebrow">Jobs by location</p>
      <h1>Jobs in {esc(city)}, {esc(region)}</h1>
      <p class="lead">{len(jobs)} open {"job" if len(jobs) == 1 else "jobs"} at {esc(brand)} in {esc(city)}: {esc(", ".join(cats).lower())}. Pay and schedule are on every listing.</p>
      <p><a class="btn btn--primary" href="../index.html#search">Search all jobs</a></p>
    </div>
  </section>
  <section class="section">
    <div class="wrap">
      <ol class="job-list">
{items}
      </ol>
    </div>
  </section>"""
    desc = f"{len(jobs)} open jobs at {brand} in {city}, {region}, with pay and schedules listed. Apply from your phone in about five minutes."
    return page(None, None, "", fit_title(f"Jobs in {city}, {region}", brand), desc,
                f"locations/{slugify(city)}-{slugify(region)}.html", body, chrome, brand, 1)


# --------------------------------------------------------------------------
# Slots in hand-written pages
# --------------------------------------------------------------------------

def fill_slot(text, open_tag_re, inner):
    pat = re.compile(r"(" + open_tag_re + r")(.*?)(</(?:ol|ul)>)", re.S)
    if not pat.search(text):
        return text, False
    return pat.sub(lambda m: m.group(1) + "\n" + inner + "\n      " + m.group(3), text, count=1), True


def faq_jsonld(text):
    pairs = re.findall(r"<details>\s*<summary>(.*?)</summary>(.*?)</details>", text, re.S)
    if not pairs:
        return text
    def plain(s):
        return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": plain(q),
         "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in pairs]}
    block = ('<script type="application/ld+json" id="faq-jsonld">\n'
             + json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/") + "\n</script>")
    text = re.sub(r'<script type="application/ld\+json" id="faq-jsonld">.*?</script>\n?', "", text, flags=re.S)
    return text.replace("</head>", block + "\n</head>", 1)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def html_files(site):
    out = []
    for dp, _, names in os.walk(site):
        for n in names:
            if n.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dp, n), site).replace(os.sep, "/"))
    return sorted(out)


def build(site, jobs_csv, base_url, pages=True):
    """pages=True: one page per job and per location, from a real export.
    pages=False: a single landing page. The rows are example roles, listed on
    the landing page as examples, and every link to a job or location opens the
    preview dialog instead of a page."""
    if not os.path.isdir(site):
        shutil.copytree(STARTER, site)
        print(f"created {site} from the starter")
    index_path = os.path.join(site, "index.html")
    if not os.path.exists(index_path):
        die(f"{site} has no index.html")
    index = read(index_path)
    brand = brand_of(index)
    header = HEADER_RE.search(index)
    footer = FOOTER_RE.search(index)
    if not header or not footer:
        die('index.html needs a <header class="site-header"> and a <footer class="site-footer">; '
            "every other page copies them")
    dialog = DIALOG_RE.search(index)
    chrome = (header.group(0), footer.group(0), dialog.group(0) if dialog else "")

    # Remove what a previous run generated, and nothing else
    for rel in html_files(site):
        p = os.path.join(site, rel)
        if GENERATOR in read(p):
            os.remove(p)
    loc_dir = os.path.join(site, "locations")
    if os.path.isdir(loc_dir) and not os.listdir(loc_dir):
        os.rmdir(loc_dir)

    jobs = load_jobs(jobs_csv) if jobs_csv else []
    by_loc = {}
    for j in jobs:
        by_loc.setdefault((j["city"], j["region"], j["loc_slug"]), []).append(j)
    if pages:
        for j in jobs:
            write(os.path.join(site, "jobs", j["slug"] + ".html"), job_page(j, brand, chrome))
        for (city, region, ls), js in sorted(by_loc.items()):
            write(os.path.join(site, "locations", ls + ".html"), location_page(city, region, js, brand, chrome))

    if not pages:
        for d in ("jobs", "locations"):
            dd = os.path.join(site, d)
            if os.path.isdir(dd):
                shutil.rmtree(dd)

    # The job list lives in the landing page HTML, so crawlers and AI agents see
    # every job without running any JavaScript
    def job_link(j):
        if pages:
            return f'<a href="jobs/{j["slug"]}.html">{esc(j["title"])}</a>'
        return (f'<a href="#full-version" data-upsell="job" data-topic="{esc(j["title"])}">'
                f'{esc(j["title"])}</a>')
    items = "\n".join(
        f'        <li>{job_link(j)}'
        f'<p class="job-meta"><span>{esc(j["city"])}, {esc(j["region"])}</span>'
        f'<span>{esc(j["pay_label"])}</span><span>{esc(j["schedule"])}</span></p></li>'
        for j in sorted(jobs, key=lambda x: (x["city"], x["title"])))
    index, ok = fill_slot(index, r'<ol class="job-list" id="job-results"[^>]*>', items)
    if not ok:
        die('index.html has no <ol class="job-list" id="job-results"> to fill')
    status = ("Showing every open job. Use the search above to narrow it down." if pages else
              "These are example listings that show how search works. Your live jobs appear here in the full version.")
    if not pages:
        index = re.sub(r'(<h2 id="results-title">).*?(</h2>)',
                       lambda m: m.group(1) + "Example jobs" + m.group(2), index, count=1, flags=re.S)
    index = re.sub(r'(<p class="status" id="job-status"[^>]*>).*?(</p>)',
                   lambda m: m.group(1) + status + m.group(2), index, count=1, flags=re.S)
    feed = [{"title": j["title"], "url": (f"jobs/{j['slug']}.html" if pages else ""),
             "city": j["city"], "region": j["region"], "postal_code": j["postal_code"],
             "category": j["category"], "category_label": j["category_label"],
             "pay_label": j["pay_label"], "schedule": j["schedule"], "summary": j["summary"]}
            for j in jobs]
    write(os.path.join(site, "js", "jobs.js"),
          "window.JOBS = " + json.dumps(feed, indent=1, ensure_ascii=False) + ";\n")

    def loc_link(city, region, ls, n):
        label = f"{esc(city)}, {esc(region)} ({n})"
        if pages:
            return f'<a href="locations/{ls}.html">{label}</a>'
        return f'<a href="#full-version" data-upsell="location" data-topic="{esc(city)}, {esc(region)}">{label}</a>'
    locs = "\n".join(f"        <li>{loc_link(city, region, ls, len(js))}</li>"
                     for (city, region, ls), js in sorted(by_loc.items()))
    locs += '\n        <li><a href="index.html#search">All locations</a></li>'
    index, _ = fill_slot(index, r'<ul class="loc-list" id="location-list"[^>]*>', locs)
    write(index_path, index)

    # Header, footer and FAQ markup on every page
    for rel in html_files(site):
        p = os.path.join(site, rel)
        text = read(p)
        if rel != "index.html":
            depth = rel.count("/")
            text = HEADER_RE.sub(lambda _: rebase(chrome[0], depth), text, count=1)
            text = FOOTER_RE.sub(lambda _: rebase(chrome[1], depth), text, count=1)
        if 'class="wrap faq"' in text:
            text = faq_jsonld(text)
        write(p, text)

    # Real URLs everywhere the placeholder base appears
    base = base_url.rstrip("/")
    for dp, _, names in os.walk(site):
        for n in names:
            if n.endswith((".html", ".txt", ".xml", ".js")):
                p = os.path.join(dp, n)
                t = read(p)
                if PLACEHOLDER_BASE in t and base != PLACEHOLDER_BASE:
                    write(p, t.replace(PLACEHOLDER_BASE, base))

    # sitemap.xml
    today = datetime.date.today().isoformat()
    urls = []
    for rel in html_files(site):
        lastmod = today
        if rel.startswith("jobs/") and rel != "jobs/index.html":
            slug = rel[5:-5]
            match = [j for j in jobs if j["slug"] == slug]
            if match:
                lastmod = match[0]["date_posted"]
        urls.append(f"  <url><loc>{esc(base)}/{rel}</loc><lastmod>{lastmod}</lastmod></url>")
    write(os.path.join(site, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(urls) + "\n</urlset>\n")

    # robots.txt points at the sitemap
    robots = os.path.join(site, "robots.txt")
    rtext = read(robots) if os.path.exists(robots) else "User-agent: *\nAllow: /\n"
    rtext = re.sub(r"(?im)^sitemap:.*\n?", "", rtext).rstrip() + f"\n\nSitemap: {base}/sitemap.xml\n"
    write(robots, rtext)

    # llms.txt: a plain summary an AI assistant can read in one request
    lines = [f"# {brand} careers", ""]
    lines.append(f"> {meta(index, 'description')}")
    lines += ["", "## Pages", ""]
    ordered = ["index.html"] + [r for r in html_files(site) if r != "index.html"]
    for rel in ordered:
        if rel.startswith(("jobs/", "locations/")) and rel != "jobs/index.html":
            continue
        t = read(os.path.join(site, rel))
        lines.append(f"- [{title_of(t)}]({base}/{rel}): {meta(t, 'description')}")
    if jobs and pages:
        lines += ["", "## Open jobs by location", ""]
        for (city, region, ls), js in sorted(by_loc.items()):
            lines.append(f"- [{city}, {region}]({base}/locations/{ls}.html): {len(js)} open jobs")
    if jobs:
        lines += ["", "## Pay by job" if pages else "## Example roles (illustrative, not live openings)", ""]
        seen = set()
        for j in sorted(jobs, key=lambda x: (x["category"], x["title"])):
            key = (j["title"], j["pay_label"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {j['title']} ({j['city']}, {j['region']}): {j['pay_label'] or 'pay not listed'}; {j['schedule']}")
    lines += ["", "## How to apply", "",
              f"Search jobs at {base}/index.html#search. Each job lists pay and schedule.", ""]
    write(os.path.join(site, "llms.txt"), "\n".join(lines))

    preview, archive = package(site)

    if pages:
        print(f"built {site}: {len(jobs)} job pages, {len(by_loc)} location pages, "
              f"{len(html_files(site))} pages in the sitemap, brand '{brand}'")
    else:
        print(f"built {site}: landing page with {len(jobs)} example roles in {len(by_loc)} locations, "
              f"brand '{brand}'")
    print(f"preview: {preview}")
    print(f"download: {archive}")
    return {"jobs": len(jobs) if pages else 0, "locations": len(by_loc) if pages else 0,
            "examples": 0 if pages else len(jobs), "pages": len(html_files(site)),
            "preview": preview, "archive": archive}


def package(site):
    """Two things a person can open without a web server, written next to the
    site folder rather than inside it, so they never reach the sitemap:

    - SITE-preview.html: the home page with its CSS and JavaScript inlined, so
      a chat preview pane that shows one file at a time still shows it styled
    - SITE.zip: the whole site, ready to upload to any static host
    """
    site = os.path.normpath(site)
    name = os.path.basename(site)
    parent = os.path.dirname(os.path.abspath(site))
    text = read(os.path.join(site, "index.html"))

    def inline_css(m):
        path = os.path.join(site, m.group(1))
        return f"<style>\n{read(path)}\n</style>" if os.path.exists(path) else m.group(0)

    def inline_js(m):
        path = os.path.join(site, m.group(1))
        return f"<script>\n{read(path)}\n</script>" if os.path.exists(path) else m.group(0)

    text = re.sub(r'<link rel="stylesheet" href="([^"]+\.css)">', inline_css, text)
    text = re.sub(r'<script src="([^"]+\.js)"(?: defer)?></script>', inline_js, text)
    text = text.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
    banner = ('<p style="margin:0;padding:10px 16px;background:#1d1f22;color:#f5f3ef;'
              'font:600 14px/1.4 system-ui,sans-serif">Preview of the home page. '
              f'Links to other pages work in the full site, {esc(name)}.zip.</p>')
    text = text.replace("<body>", "<body>\n" + banner, 1)
    preview = os.path.join(parent, f"{name}-preview.html")
    write(preview, text)

    archive = os.path.join(parent, f"{name}.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, names in os.walk(site):
            for n in sorted(names):
                full = os.path.join(dp, n)
                z.write(full, os.path.join(name, os.path.relpath(full, site)))
    return preview, archive


def main():
    ap = argparse.ArgumentParser(description="Build the generated parts of a careers site.")
    ap.add_argument("--site", required=True, help="site folder; created from the starter if missing")
    ap.add_argument("--jobs", help="CSV of real open jobs: one page per job and per location")
    ap.add_argument("--examples", help="CSV of example roles: a single landing page, job links open the preview dialog")
    ap.add_argument("--base-url", default=PLACEHOLDER_BASE, help="where the site will live")
    ap.add_argument("--demo", action="store_true", help="landing page for the fictional sample employer")
    a = ap.parse_args()
    if a.jobs:
        build(a.site, a.jobs, a.base_url, pages=True)
    else:
        build(a.site, a.examples or (SAMPLE if a.demo else None), a.base_url, pages=False)


if __name__ == "__main__":
    main()
