#!/usr/bin/env python3
"""
Checks a careers site against what SKILL.md promises it will be: findable by
search engines, readable by AI assistants, quick to apply from on a phone,
accessible, light, and honest about what is not yet confirmed.

Why this exists
---------------
A generated site always looks finished. Whether Google can read its job
markup, whether an AI crawler sees anything but an empty div, whether a
keyboard user can see where focus is, whether a claim like "award-winning"
was ever true: none of that is visible in a screenshot. Each of those is a
mechanical property of the files, so it is checked by code before the site is
handed over, and a site that fails a blocking check is not finished, whatever
it looks like.

    check_site.py --site SITE_DIR [--json report.json]
    check_site.py --page saved_page.html        audit one page of an existing site
    check_site.py --test

The report counts checks passed per area. It is a count, not a grade: a
missing JobPosting date is not worth "three points", and no number of passes
elsewhere makes a blocking failure acceptable. With --page, checks that need
the whole site (sitemap, links, llms.txt) are reported as not checked rather
than failed, because one saved page cannot show them.

Standard library only. No network. It reads the files you point it at.
"""

import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

# --------------------------------------------------------------------------
# The checks. Every id here is described in references/rubric.md.
# scope: page = evaluated on every page; site = needs the whole folder.
# --------------------------------------------------------------------------
CHECKS = {
    # id: (area, severity, scope, what it means)
    "seo.title": ("Search", "blocking", "page", "every page has a <title>"),
    "seo.title_length": ("Search", "advisory", "page", "titles fit in a search result (70 characters or fewer)"),
    "seo.meta_description": ("Search", "blocking", "page", "every page has a meta description"),
    "seo.h1": ("Search", "blocking", "page", "exactly one <h1> per page"),
    "seo.heading_order": ("Search", "advisory", "page", "headings do not skip a level"),
    "seo.canonical": ("Search", "advisory", "page", "a canonical URL on every page"),
    "seo.jobposting_required": ("Search", "blocking", "page", "JobPosting markup has every field Google requires"),
    "seo.jobposting_recommended": ("Search", "advisory", "page", "JobPosting markup has pay, employment type, closing date and id"),
    "seo.job_pages": ("Search", "advisory", "site", "each job has its own page with JobPosting markup"),
    "seo.location_pages": ("Search", "advisory", "site", "a page per location people search for"),
    "seo.sitemap": ("Search", "blocking", "site", "sitemap.xml lists every page"),
    "seo.robots": ("Search", "blocking", "site", "robots.txt does not block the site"),
    "seo.broken_links": ("Search", "blocking", "site", "every internal link and asset resolves"),
    "ai.content_in_html": ("AI visibility", "blocking", "page", "the content is in the HTML, not only painted in by JavaScript"),
    "ai.jobs_in_html": ("AI visibility", "blocking", "site", "every job page is linked from a plain HTML page"),
    "ai.llms_txt": ("AI visibility", "advisory", "site", "an llms.txt summary at the root"),
    "ai.organization": ("AI visibility", "advisory", "site", "Organization markup on the home page"),
    "ai.faq_schema": ("AI visibility", "advisory", "site", "FAQ pages carry FAQPage markup"),
    "conv.mobile_viewport": ("Conversion", "blocking", "page", "a mobile viewport on every page"),
    "conv.search_jobs_nav": ("Conversion", "blocking", "page", "a jobs link in the header of every page"),
    "conv.dead_ends": ("Conversion", "blocking", "page", "every link goes somewhere: a section, a page, or the preview dialog"),
    "conv.home_search": ("Conversion", "advisory", "site", "a job search form on the home page"),
    "conv.apply_link": ("Conversion", "blocking", "page", "every job page has an Apply link"),
    "conv.pay_shown": ("Conversion", "advisory", "page", "every job page shows pay as a number"),
    "conv.schedule_shown": ("Conversion", "advisory", "page", "every job page says what the hours are"),
    "conv.ats_handoff": ("Conversion", "advisory", "page", "the jump to an external application site is explained"),
    "a11y.lang": ("Accessibility", "blocking", "page", "the page declares its language"),
    "a11y.img_alt": ("Accessibility", "blocking", "page", "every image has alt text (empty for decoration)"),
    "a11y.form_labels": ("Accessibility", "blocking", "page", "every form field has a label"),
    "a11y.dialog": ("Accessibility", "blocking", "page", "the preview dialog has a name and a way to close it"),
    "a11y.focus_visible": ("Accessibility", "blocking", "site", "focus is never hidden without a visible replacement"),
    "a11y.contrast": ("Accessibility", "blocking", "site", "text colour pairs meet 4.5:1"),
    "a11y.reduced_motion": ("Accessibility", "advisory", "site", "motion switches off for people who ask for less"),
    "content.placeholder": ("Honesty", "blocking", "page", "no lorem ipsum, TODO or unfilled placeholders"),
    "content.cliche": ("Honesty", "advisory", "page", "none of the phrases candidates have learned to ignore"),
    "content.unverified_claim": ("Honesty", "advisory", "page", "awards and rankings are marked for confirmation"),
    "perf.page_weight": ("Speed", "advisory", "page", "HTML, CSS and JS under 500 KB per page"),
    "perf.image_weight": ("Speed", "advisory", "site", "no image over 400 KB"),
    "perf.third_party_scripts": ("Speed", "advisory", "page", "four or fewer third-party scripts per page"),
}
AREAS = ["Search", "AI visibility", "Conversion", "Accessibility", "Honesty", "Speed"]

JOBPOSTING_REQUIRED = ["title", "description", "datePosted", "hiringOrganization"]
JOBPOSTING_RECOMMENDED = ["baseSalary", "employmentType", "validThrough", "identifier"]
PLACEHOLDER_RE = re.compile(r"(?i)\b(lorem ipsum|dolor sit amet|todo|tbd)\b|\[insert|\{\{|xxx+")
CLICHES = ["work hard, play hard", "work hard play hard", "we're a family", "we are a family",
           "like a family", "rockstar", "ninja", "limitless opportunit", "unlimited opportunit",
           "fast-paced environment", "competitive pay", "competitive salary", "competitive wages",
           "self-starter", "wear many hats", "passionate team"]
CLAIM_RE = re.compile(r"(?i)\b(award[- ]winning|#\s?1\b|number one|best place to work|great place to work|"
                      r"top employer|voted\b|ranked\b|certified great)")
MONEY_RE = re.compile(r"(\$|£|€)\s?\d|\d[\d,.]*\s?(usd|eur|gbp|aed)\b", re.I)
SCHEDULE_RE = re.compile(r"(?i)\b(schedule|shift|hours|full-time|part-time|days?|nights?|weekends?|\d\s?(am|pm))\b")
HANDOFF_RE = re.compile(r"(?i)(continue|finish|complete)[^.]{0,60}(application|apply)[^.]{0,80}\b(on|at|with|via)\b")
PLACEHOLDER = "https://careers.example.com"
JOBS_LINK_RE = re.compile(r"(?i)\bjobs?\b|\bcareers?\b.*\bsearch|\bopenings?\b|\bpositions?\b|\bapply\b")


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = ""
        self.meta = {}
        self.links = []            # (tag, attr, url, text)
        self.canonical = None
        self.headings = []         # levels
        self.imgs_no_alt = 0
        self.fields = []           # (id, has_aria, inside_label)
        self.label_for = set()
        self.jsonld = []
        self.text = []
        self.text_unmarked = []
        self.scripts = []
        self.forms = []
        self.header_links = []     # link texts and hrefs inside header/nav
        self.has_faq_details = False
        self.marks = []
        self.styles = []
        self.ids = set()
        self.anchors = []          # (href or None, has_upsell)
        self.dialogs = []          # dicts: id, labelled, buttons
        self._dialog = None
        self._stack = []
        self._in_title = self._in_jsonld = self._in_style = self._skip = 0
        self._in_label = 0
        self._in_header = 0
        self._in_mark = 0
        self._mark_buf = []
        self._a = None
        self._buf = []
        self._form_fields = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "dialog" or a.get("role") == "dialog":
            self._dialog = {"id": a.get("id"), "labelledby": a.get("aria-labelledby"),
                            "label": a.get("aria-label"), "buttons": 0}
            self.dialogs.append(self._dialog)
        if tag == "button" and self._dialog is not None:
            self._dialog["buttons"] += 1
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = 1
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key.lower()] = a.get("content", "")
        elif tag == "link":
            if "canonical" in a.get("rel", ""):
                self.canonical = a.get("href")
            if a.get("href"):
                self.links.append(("link", "href", a["href"], ""))
        elif tag == "script":
            if a.get("type") == "application/ld+json":
                self._in_jsonld = 1
                self._buf = []
            else:
                self._skip += 1
                if a.get("src"):
                    self.scripts.append(a["src"])
                    self.links.append(("script", "src", a["src"], ""))
        elif tag in ("style", "noscript", "template"):
            self._skip += 1
            if tag == "style":
                self._in_style = 1
                self._buf = []
        elif re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        elif tag == "img":
            if "alt" not in a:
                self.imgs_no_alt += 1
            if a.get("src"):
                self.links.append(("img", "src", a["src"], ""))
        elif tag == "a":
            self._a = [a.get("href", ""), []]
            self.anchors.append((a.get("href"), "data-upsell" in a))
        elif tag == "label":
            self._in_label += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            if a.get("type", "").lower() not in ("hidden", "submit", "button", "reset", "image"):
                self.fields.append((a.get("id"), bool(a.get("aria-label") or a.get("aria-labelledby") or a.get("title")),
                                    self._in_label > 0))
                if self._form_fields is not None:
                    self._form_fields += 1
        elif tag == "form":
            self._form_fields = 0
        elif tag in ("header", "nav"):
            self._in_header += 1
        elif tag == "mark" and "confirm" in a.get("class", ""):
            self._in_mark += 1
            self._mark_buf = []
        elif tag == "details":
            self.has_faq_details = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = 0
        elif tag == "script":
            if self._in_jsonld:
                self.jsonld.append("".join(self._buf))
                self._in_jsonld = 0
            elif self._skip:
                self._skip -= 1
        elif tag in ("style", "noscript", "template"):
            if tag == "style" and self._in_style:
                self.styles.append("".join(self._buf))
                self._in_style = 0
            if self._skip:
                self._skip -= 1
        elif tag == "a" and self._a is not None:
            href, parts = self._a
            text = " ".join("".join(parts).split())
            self.links.append(("a", "href", href, text))
            if self._in_header:
                self.header_links.append((href, text))
            self._a = None
        elif tag == "label":
            self._in_label = max(0, self._in_label - 1)
        elif tag == "form":
            self.forms.append(self._form_fields or 0)
            self._form_fields = None
        elif tag in ("header", "nav"):
            self._in_header = max(0, self._in_header - 1)
        elif tag == "dialog":
            self._dialog = None
        elif tag == "mark" and self._in_mark:
            self._in_mark -= 1
            self.marks.append(" ".join("".join(self._mark_buf).split()))

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_jsonld or self._in_style:
            self._buf.append(data)
            return
        if self._skip:
            return
        self.text.append(data)
        if self._in_mark:
            self._mark_buf.append(data)
        else:
            self.text_unmarked.append(data)
        if self._a is not None:
            self._a[1].append(data)


def parse(path):
    p = Page()
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    p.feed(raw)
    p.raw = raw
    p.visible = " ".join(" ".join(p.text).split())
    p.unmarked = " ".join(" ".join(p.text_unmarked).split())
    p.jsonld_objects = []
    for block in p.jsonld:
        try:
            data = json.loads(block)
        except ValueError:
            p.jsonld_objects.append({"@type": "__invalid__"})
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        p.jsonld_objects.extend(x for x in items if isinstance(x, dict))
    return p


def jsonld_of(p, kind):
    return [o for o in p.jsonld_objects if o.get("@type") == kind]


# --------------------------------------------------------------------------
# CSS: contrast, focus, motion
# --------------------------------------------------------------------------

def css_rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def decls(body):
    out = {}
    for part in body.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def hex_rgb(v):
    v = v.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def css_findings(css):
    rules = css_rules(css)
    tokens = {}
    for sel, body in rules:
        if ":root" in sel:
            for k, v in decls(body).items():
                if k.startswith("--"):
                    tokens[k] = v

    def resolve(v, depth=0):
        m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)", v.strip())
        if m and depth < 5:
            return resolve(tokens.get(m.group(1), m.group(2) or ""), depth + 1)
        return v.strip()

    low = []
    for sel, body in rules:
        d = decls(body)
        fg = d.get("color")
        bg = d.get("background-color") or d.get("background")
        if not fg or not bg:
            continue
        a, b = hex_rgb(resolve(fg)), hex_rgb(resolve(bg.split()[0] if bg.startswith("#") else bg))
        if a and b:
            r = contrast(a, b)
            if r < 4.5:
                low.append(f"{sel}: {r:.1f}:1")

    hides_focus = any(re.search(r"outline\s*:\s*(none|0)\b", body) and "focus" in sel
                      for sel, body in rules)
    shows_focus = any(":focus-visible" in sel and re.search(r"outline\s*:\s*(?!none|0\b)\S", body)
                      for sel, body in rules)
    moves = bool(re.search(r"\b(animation|transition)\s*:\s*(?!none)", re.sub(r"/\*.*?\*/", "", css, flags=re.S)))
    reduced = "prefers-reduced-motion" in css
    return {"contrast": low, "focus_ok": (not hides_focus) or shows_focus,
            "motion_ok": (not moves) or reduced}


# --------------------------------------------------------------------------
# Running the checks
# --------------------------------------------------------------------------

def local_target(page_rel, url, site):
    url = url.split("#")[0].split("?")[0]
    if not url or re.match(r"^(https?:|mailto:|tel:|data:|javascript:|//)", url):
        return None
    if url.startswith("/"):
        return os.path.normpath(os.path.join(site, url.lstrip("/")))
    return os.path.normpath(os.path.join(site, os.path.dirname(page_rel), url))


def is_job_page(p):
    return bool(jsonld_of(p, "JobPosting"))


def run(site=None, page=None):
    if page:
        root = os.path.dirname(os.path.abspath(page))
        rels = [os.path.basename(page)]
        site_mode = False
    else:
        root = os.path.abspath(site)
        rels = []
        for dp, _, names in os.walk(root):
            for n in names:
                if n.endswith((".html", ".htm")):
                    rels.append(os.path.relpath(os.path.join(dp, n), root).replace(os.sep, "/"))
        rels.sort()
        site_mode = True
    if not rels:
        raise SystemExit("check_site: no HTML pages found")

    pages = {r: parse(os.path.join(root, r)) for r in rels}
    fails = {cid: [] for cid in CHECKS}

    # CSS: linked local stylesheets plus inline <style>
    css_text = ""
    seen_css = set()
    for r, p in pages.items():
        css_text += "\n".join(p.styles)
        for tag, attr, url, _ in p.links:
            if tag == "link" and url.endswith(".css"):
                t = local_target(r, url, root)
                if t and t not in seen_css and os.path.exists(t):
                    seen_css.add(t)
                    css_text += "\n" + open(t, encoding="utf-8", errors="replace").read()

    for r, p in pages.items():
        title = " ".join(p.title.split())
        if not title:
            fails["seo.title"].append(r)
        elif len(title) > 70:
            fails["seo.title_length"].append(f"{r} ({len(title)} characters)")
        if not p.meta.get("description", "").strip():
            fails["seo.meta_description"].append(r)
        h1 = p.headings.count(1)
        if h1 != 1:
            fails["seo.h1"].append(f"{r} ({h1} found)")
        prev = 0
        for lvl in p.headings:
            if prev and lvl > prev + 1:
                fails["seo.heading_order"].append(f"{r} (h{prev} then h{lvl})")
                break
            prev = lvl
        if not p.canonical:
            fails["seo.canonical"].append(r)
        if any(o.get("@type") == "__invalid__" for o in p.jsonld_objects):
            fails["seo.jobposting_required"].append(f"{r} (structured data is not valid JSON)")
        for jp in jsonld_of(p, "JobPosting"):
            miss = [k for k in JOBPOSTING_REQUIRED if not jp.get(k)]
            loc = jp.get("jobLocation")
            remote = jp.get("jobLocationType") == "TELECOMMUTE"
            addr = (loc or {}).get("address", {}) if isinstance(loc, dict) else {}
            if not remote and not (isinstance(addr, dict) and addr.get("addressCountry")
                                   and (addr.get("addressLocality") or addr.get("addressRegion"))):
                miss.append("jobLocation address")
            if miss:
                fails["seo.jobposting_required"].append(f"{r} (missing {', '.join(miss)})")
            rec = [k for k in JOBPOSTING_RECOMMENDED if not jp.get(k)]
            if rec:
                fails["seo.jobposting_recommended"].append(f"{r} (missing {', '.join(rec)})")

        words = len(p.visible.split())
        if words < 50 and p.scripts:
            fails["ai.content_in_html"].append(f"{r} ({words} word{'' if words == 1 else 's'} of text in the HTML)")

        vp = p.meta.get("viewport", "")
        if "width=device-width" not in vp.replace(" ", ""):
            fails["conv.mobile_viewport"].append(r)
        if not any(JOBS_LINK_RE.search(t) or re.search(r"(?i)jobs?/|careers?/|search", h)
                   for h, t in p.header_links):
            fails["conv.search_jobs_nav"].append(r)
        if is_job_page(p):
            applies = [(h, t) for tag, _, h, t in p.links if tag == "a" and re.search(r"(?i)\bapply\b", t)]
            if not applies:
                fails["conv.apply_link"].append(r)
            if not MONEY_RE.search(p.visible):
                fails["conv.pay_shown"].append(r)
            if not SCHEDULE_RE.search(p.visible):
                fails["conv.schedule_shown"].append(r)
            if any(h.startswith("http") for h, _ in applies) and not HANDOFF_RE.search(p.visible):
                fails["conv.ats_handoff"].append(r)

        dead = []
        for href, upsell in p.anchors:
            h = (href or "").strip()
            if not h or h == "#" or h.lower().startswith("javascript:"):
                if not upsell:
                    dead.append(h or "(no href)")
            elif h.startswith("#") and h[1:] not in p.ids:
                dead.append(h)
        if dead:
            fails["conv.dead_ends"].append(f"{r} ({', '.join(sorted(set(dead))[:5])})")
        if any(up for _, up in p.anchors):
            targets = {(h or "").lstrip("#") for h, up in p.anchors if up}
            good = [d for d in p.dialogs if d["id"] in targets and d["buttons"]
                    and (d["label"] or (d["labelledby"] and d["labelledby"] in p.ids))]
            if not good:
                fails["a11y.dialog"].append(f"{r} (links open a dialog that is missing, unnamed or has no close button)")

        if not p.lang:
            fails["a11y.lang"].append(r)
        if p.imgs_no_alt:
            fails["a11y.img_alt"].append(f"{r} ({p.imgs_no_alt} images)")
        unlabeled = [fid or "unnamed field" for fid, aria, inside in p.fields
                     if not aria and not inside and (not fid or fid not in p.label_for)]
        if unlabeled:
            fails["a11y.form_labels"].append(f"{r} ({', '.join(unlabeled)})")

        m = PLACEHOLDER_RE.search(p.visible)
        if m:
            fails["content.placeholder"].append(f"{r} (\"{m.group(0)}\")")
        low = p.visible.lower().replace("’", "'")
        hit = [c for c in CLICHES if c in low]
        if hit:
            fails["content.cliche"].append(f"{r} ({', '.join(hit)})")
        claim = CLAIM_RE.search(p.unmarked)
        if claim:
            fails["content.unverified_claim"].append(f"{r} (\"{claim.group(0)}\" is not marked for confirmation)")

        weight = len(p.raw.encode("utf-8"))
        for tag, attr, url, _ in p.links:
            if tag in ("link", "script") and url.endswith((".css", ".js")):
                t = local_target(r, url, root)
                if t and os.path.exists(t):
                    weight += os.path.getsize(t)
        if weight > 500_000:
            fails["perf.page_weight"].append(f"{r} ({weight // 1000} KB)")
        third = [s for s in p.scripts if re.match(r"^(https?:)?//", s)]
        if len(third) > 4:
            fails["perf.third_party_scripts"].append(f"{r} ({len(third)} scripts)")

    css = css_findings(css_text)
    if css["contrast"]:
        fails["a11y.contrast"] += css["contrast"]
    if not css["focus_ok"]:
        fails["a11y.focus_visible"].append("an outline is removed on focus and no :focus-visible style replaces it")
    if not css["motion_ok"]:
        fails["a11y.reduced_motion"].append("animations or transitions with no prefers-reduced-motion rule")

    skipped = set()
    if site_mode:
        job_pages = [r for r, p in pages.items() if is_job_page(p)]
        listings = [r for r, p in pages.items() if re.search(r"(?i)job", r)]
        if not job_pages and listings:
            fails["seo.job_pages"].append("no page carries JobPosting markup")
        if job_pages and not any(re.search(r"(?i)locations?/|jobs-in-|/jobs-in", r) or
                                 re.match(r"(?i)jobs in ", " ".join(p.title.split())) for r, p in pages.items()):
            fails["seo.location_pages"].append("no location pages found")

        sm = os.path.join(root, "sitemap.xml")
        if not os.path.exists(sm):
            fails["seo.sitemap"].append("sitemap.xml is missing")
        else:
            listed = {re.sub(r"^https?://[^/]+/", "", u.strip()) for u in
                      re.findall(r"<loc>(.*?)</loc>", open(sm, encoding="utf-8").read())}
            missing = [r for r in rels if r not in listed and not (r == "index.html" and "" in listed)]
            if missing:
                fails["seo.sitemap"].append(f"{len(missing)} pages not listed, e.g. {missing[0]}")
        rb = os.path.join(root, "robots.txt")
        if os.path.exists(rb):
            block, agent_all = False, False
            for line in open(rb, encoding="utf-8").read().splitlines():
                line = line.split("#")[0].strip()
                if re.match(r"(?i)user-agent:\s*\*", line):
                    agent_all = True
                elif re.match(r"(?i)user-agent:", line):
                    agent_all = False
                elif agent_all and re.fullmatch(r"(?i)disallow:\s*/", line):
                    block = True
            if block:
                fails["seo.robots"].append("robots.txt disallows the whole site")

        broken = []
        for r, p in pages.items():
            for tag, attr, url, _ in p.links:
                t = local_target(r, url, root)
                if t is None:
                    continue
                if os.path.isdir(t):
                    t = os.path.join(t, "index.html")
                if not os.path.exists(t):
                    broken.append(f"{r} -> {url}")
        if broken:
            fails["seo.broken_links"] += broken[:20]

        linked = set()
        for r, p in pages.items():
            for tag, attr, url, _ in p.links:
                t = local_target(r, url, root)
                if tag == "a" and t:
                    linked.add(os.path.relpath(t, root).replace(os.sep, "/"))
        orphans = [r for r in job_pages if r not in linked]
        if orphans:
            fails["ai.jobs_in_html"].append(f"{len(orphans)} job pages no HTML page links to, e.g. {orphans[0]}")

        if not os.path.exists(os.path.join(root, "llms.txt")):
            fails["ai.llms_txt"].append("llms.txt is missing")
        home = pages.get("index.html")
        if home is not None and not jsonld_of(home, "Organization"):
            fails["ai.organization"].append("index.html")
        for r, p in pages.items():
            if (p.has_faq_details or "faq" in r.lower()) and not jsonld_of(p, "FAQPage"):
                fails["ai.faq_schema"].append(r)
        if home is not None and not any(n >= 2 for n in home.forms):
            fails["conv.home_search"].append("index.html has no search form with at least two fields")

        big = []
        for dp, _, names in os.walk(root):
            for n in names:
                if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")):
                    f = os.path.join(dp, n)
                    if os.path.getsize(f) > 400_000:
                        big.append(f"{os.path.relpath(f, root)} ({os.path.getsize(f) // 1000} KB)")
        fails["perf.image_weight"] += big
    else:
        skipped = {cid for cid, (_, _, scope, _) in CHECKS.items() if scope == "site"}
        # Some site checks can still be judged from one page
        skipped -= {"a11y.contrast", "a11y.focus_visible", "a11y.reduced_motion"}

    to_confirm = []
    for r, p in pages.items():
        for m in p.marks:
            to_confirm.append(f"{r}: {m}")

    return {"pages": len(pages), "fails": {k: v for k, v in fails.items() if v and k not in skipped},
            "skipped": sorted(skipped), "to_confirm": to_confirm, "site_mode": site_mode}


def report(res):
    fails, skipped = res["fails"], set(res["skipped"])
    applicable = [c for c in CHECKS if c not in skipped]
    passed = [c for c in applicable if c not in fails]
    out = [f"Careers site check: {len(passed)} of {len(applicable)} checks pass "
           f"({res['pages']} page{'s' if res['pages'] != 1 else ''} read)", ""]
    for area in AREAS:
        ids = [c for c in applicable if CHECKS[c][0] == area]
        ok = [c for c in ids if c not in fails]
        out.append(f"  {area:<15} {len(ok)}/{len(ids)}")
    blocking = [c for c in fails if CHECKS[c][1] == "blocking"]
    advisory = [c for c in fails if CHECKS[c][1] == "advisory"]
    for label, ids in (("Blocking, fix before launch", blocking), ("Worth a look", advisory)):
        if ids:
            out += ["", label + ":"]
            for c in ids:
                out.append(f"  [{c}] {CHECKS[c][3]}")
                for item in fails[c][:5]:
                    out.append(f"      {item}")
                if len(fails[c]) > 5:
                    out.append(f"      ...and {len(fails[c]) - 5} more")
    if res["to_confirm"]:
        out += ["", f"Marked for the employer to confirm before launch ({len(res['to_confirm'])}):"]
        out += [f"  {x}" for x in res["to_confirm"][:40]]
    if skipped:
        out += ["", "Not checked from a single page (need the whole site): " + ", ".join(sorted(skipped))]
    return "\n".join(out)


# --------------------------------------------------------------------------
# Test suite: build the demo site, then break it one way at a time
# --------------------------------------------------------------------------

def _load_builder():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_site", os.path.join(HERE, "build_site.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _edit(path, old, new, count=1):
    t = open(path, encoding="utf-8").read()
    if isinstance(old, str):
        if old not in t:
            raise AssertionError(f"fixture setup: text not found in {path}")
        t = t.replace(old, new, count)
    else:
        pat = re.compile(old.pattern, re.S)
        if not pat.search(t):
            raise AssertionError(f"fixture setup: pattern not found in {path}")
        t = pat.sub(lambda _: new, t, count=count)
    open(path, "w", encoding="utf-8").write(t)


def _first_job(site):
    return sorted(f for f in os.listdir(os.path.join(site, "jobs")) if f.endswith(".html"))[0]


def _first_location(site):
    return sorted(os.listdir(os.path.join(site, "locations")))[0]


# (name, base, setup(site), must_fail, must_not_fail, exact)
# base "landing" is the one-page preview with example roles; "full" has job and
# location pages built from a real export.
MUTATIONS = [
    ("no viewport", "landing", lambda s: _edit(f"{s}/index.html", '<meta name="viewport" content="width=device-width, initial-scale=1">\n', ""),
     {"conv.mobile_viewport"}, set(), True),
    ("no h1", "full", lambda s: (_edit(f"{s}/locations/{_first_location(s)}", "<h1>", "<h2>"), _edit(f"{s}/locations/{_first_location(s)}", "</h1>", "</h2>")),
     {"seo.h1"}, {"conv.search_jobs_nav"}, True),
    ("two h1", "landing", lambda s: _edit(f"{s}/index.html", "</main>", "<h1>A second title</h1></main>"),
     {"seo.h1"}, set(), True),
    ("image without alt", "landing", lambda s: _edit(f"{s}/index.html", '<main id="main">', '<main id="main"><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">'),
     {"a11y.img_alt"}, {"seo.broken_links"}, True),
    ("unlabelled search field", "landing", lambda s: _edit(f"{s}/index.html", '<label for="q">Job or keyword</label>', ""),
     {"a11y.form_labels"}, set(), True),
    ("lorem ipsum", "landing", lambda s: _edit(f"{s}/index.html", "Specifics, not slogans.", "Lorem ipsum dolor sit amet."),
     {"content.placeholder"}, set(), True),
    ("broken link", "full", lambda s: _edit(f"{s}/locations/{_first_location(s)}", "</main>", '<p><a href="benefits.html">Benefits</a></p></main>'),
     {"seo.broken_links"}, set(), True),
    ("link to nowhere", "landing", lambda s: _edit(f"{s}/index.html", '<a href="#full-version" data-upsell="page" data-topic="Benefits">', '<a href="#">'),
     {"conv.dead_ends"}, set(), True),
    ("anchor to a missing section", "landing", lambda s: _edit(f"{s}/index.html", '<li><a href="index.html#faq">FAQ</a></li>', '<li><a href="#questions">FAQ</a></li>'),
     {"conv.dead_ends"}, set(), True),
    ("preview dialog missing", "landing", lambda s: _edit(f"{s}/index.html", re.compile(r'<dialog class="upsell".*?</dialog>'), ""),
     {"a11y.dialog", "conv.dead_ends"}, set(), True),
    ("preview dialog without a name", "landing", lambda s: _edit(f"{s}/index.html", ' aria-labelledby="upsell-title"', ""),
     {"a11y.dialog"}, {"conv.dead_ends"}, True),
    ("JobPosting without datePosted", "full", lambda s: _edit(f"{s}/jobs/{_first_job(s)}", re.compile(r'\n\s*"datePosted": "[^"]*",'), ""),
     {"seo.jobposting_required"}, {"seo.jobposting_recommended"}, True),
    ("JobPosting without salary", "full", lambda s: _edit(f"{s}/jobs/{_first_job(s)}", re.compile(r',\n\s*"baseSalary": \{.*?\n  \}'), ""),
     {"seo.jobposting_recommended"}, {"conv.pay_shown", "seo.jobposting_required"}, True),
    ("pay missing from a job page", "full", lambda s: _edit(f"{s}/jobs/{_first_job(s)}", re.compile(r'<p class="pay">.*?</p>'), ""),
     {"conv.pay_shown"}, {"seo.jobposting_recommended"}, True),
    ("JavaScript-only home page", "landing", lambda s: (_edit(f"{s}/index.html", re.compile(r"<body>.*</body>"), '<body><div id="root"></div><script src="app.js"></script></body>'),
                                              open(f"{s}/app.js", "w").write("render();")),
     {"ai.content_in_html"}, {"seo.broken_links", "a11y.img_alt"}, False),
    ("focus outline removed", "landing", lambda s: _edit(f"{s}/css/site.css", ":focus-visible { outline: 3px solid var(--focus);", ":focus { outline: none;"),
     {"a11y.focus_visible"}, set(), True),
    ("low contrast brand colour", "landing", lambda s: _edit(f"{s}/css/tokens.css", "--accent-ink: #1a1a1a;", "--accent-ink: #ffd27a;"),
     {"a11y.contrast"}, set(), True),
    ("motion with no opt-out", "landing", lambda s: _edit(f"{s}/css/site.css", "prefers-reduced-motion: reduce", "min-width: 1px"),
     {"a11y.reduced_motion"}, set(), True),
    ("cliche", "landing", lambda s: _edit(f"{s}/index.html", "Four steps,", "We work hard, play hard. Four steps,") if "Four steps," in open(f"{s}/index.html").read()
     else _edit(f"{s}/index.html", "Specifics, not slogans.", "We work hard, play hard."),
     {"content.cliche"}, {"content.unverified_claim"}, True),
    ("unverified award", "landing", lambda s: _edit(f"{s}/index.html", "Specifics, not slogans.", "An award-winning employer."),
     {"content.unverified_claim"}, {"content.cliche"}, True),
    ("award marked for confirmation", "landing", lambda s: _edit(f"{s}/index.html", "Specifics, not slogans.", '<mark class="confirm">An award-winning employer.</mark>'),
     set(), {"content.unverified_claim"}, True),
    ("sitemap missing", "full", lambda s: os.remove(f"{s}/sitemap.xml"),
     {"seo.sitemap"}, set(), True),
    ("sitemap misses a page", "full", lambda s: _edit(f"{s}/sitemap.xml", re.compile(r"  <url><loc>[^<]*locations/[^<]*</loc>.*?</url>\n"), ""),
     {"seo.sitemap"}, set(), True),
    ("robots blocks everything", "landing", lambda s: _edit(f"{s}/robots.txt", "Allow: /", "Disallow: /"),
     {"seo.robots"}, set(), True),
    ("no llms.txt", "landing", lambda s: os.remove(f"{s}/llms.txt"),
     {"ai.llms_txt"}, set(), True),
    ("no jobs link in a header", "full", lambda s: _edit(f"{s}/locations/{_first_location(s)}", re.compile(r'<header class="site-header">.*?</header>'), '<header class="site-header"><a href="../index.html">Home</a></header>'),
     {"conv.search_jobs_nav"}, set(), True),
    ("orphan job page", "full", lambda s: (_edit(f"{s}/index.html", re.compile(r'<li><a href="jobs/%s">.*?</li>' % re.escape(_first_job(s))), ""),
                                           [_edit(f"{s}/locations/{n}", re.compile(r'<li><a href="\.\./jobs/%s">.*?</li>' % re.escape(_first_job(s))), "")
                                            for n in os.listdir(f"{s}/locations") if _first_job(s) in open(f"{s}/locations/{n}").read()]),
     {"ai.jobs_in_html"}, {"seo.broken_links"}, True),
    ("external apply not explained", "full", lambda s: _edit(f"{s}/jobs/{_first_job(s)}", re.compile(r'<p class="handoff-note">.*?</p>'), ""),
     {"conv.ats_handoff"}, {"conv.apply_link"}, True),
    ("FAQ without markup", "landing", lambda s: _edit(f"{s}/index.html", re.compile(r'<script type="application/ld\+json" id="faq-jsonld">.*?</script>'), ""),
     {"ai.faq_schema"}, set(), True),
    ("five third-party scripts", "landing", lambda s: _edit(f"{s}/index.html", "</body>", "".join(f'<script src="https://t{i}.example.net/x.js"></script>' for i in range(5)) + "</body>"),
     {"perf.third_party_scripts"}, set(), True),
]


def run_tests():
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"  {detail}" if detail and not ok else ""))
        if ok:
            passed += 1
        else:
            failed += 1

    import contextlib
    import io
    import zipfile
    builder = _load_builder()
    tmp = tempfile.mkdtemp(prefix="career-site-")
    try:
        bases = {}
        print("Landing page, the demo")
        landing = os.path.join(tmp, "landing")
        with contextlib.redirect_stdout(io.StringIO()):
            ls = builder.build(landing, builder.SAMPLE, "https://careers.northline.example", pages=False)
        bases["landing"] = landing
        res = run(site=landing)
        check("landing page passes every check", not res["fails"], json.dumps(res["fails"])[:300])
        check("it is one page: no job or location pages", not os.path.exists(os.path.join(landing, "jobs"))
              and not os.path.exists(os.path.join(landing, "locations")) and res["pages"] == 1)
        home = parse(os.path.join(landing, "index.html"))
        upsell_jobs = sum(1 for h, up in home.anchors if up and h == "#full-version")
        examples = sum(1 for _ in open(builder.SAMPLE, encoding="utf-8")) - 1
        check("every example job opens the preview dialog", upsell_jobs >= examples, f"{upsell_jobs} vs {examples}")
        check("example listings are labelled as examples", "example listings" in home.visible.lower())
        check("unconfirmed facts are listed for the employer", len(res["to_confirm"]) >= 10, str(len(res["to_confirm"])))
        preview = open(ls["preview"], encoding="utf-8").read()
        check("the preview is one self-contained file",
              'rel="stylesheet"' not in preview and "<style>" in preview and 'src="js/' not in preview)

        print("\nFull site, from a jobs export")
        full = os.path.join(tmp, "full")
        with contextlib.redirect_stdout(io.StringIO()):
            stats = builder.build(full, builder.SAMPLE, "https://careers.northline.example", pages=True)
        bases["full"] = full
        res = run(site=full)
        check("full site passes every check", not res["fails"], json.dumps(res["fails"])[:300])
        jobs_csv = examples
        check("one page per job", stats["jobs"] == jobs_csv, f"{stats['jobs']} vs {jobs_csv}")
        jp = [r for r in os.listdir(os.path.join(full, "jobs")) if r.endswith(".html")]
        check("every job page carries JobPosting markup",
              all(is_job_page(parse(os.path.join(full, "jobs", r))) for r in jp))
        check("base URL replaced everywhere",
              "careers.example.com" not in open(os.path.join(full, "sitemap.xml")).read()
              and "careers.example.com" not in open(os.path.join(full, "index.html")).read())
        search = parse(os.path.join(full, "index.html"))
        check("every job is listed in the landing page HTML",
              sum(1 for t, _, u, _ in search.links if t == "a" and u.startswith("jobs/") and u[5:] in jp) == len(jp))
        with zipfile.ZipFile(stats["archive"]) as z:
            names = set(z.namelist())
        check("the download holds every page of the site",
              all(f"full/{r}" in names for r in ["index.html", "sitemap.xml", "llms.txt", "js/jobs.js"])
              and sum(1 for n in names if n.startswith("full/jobs/") and n.endswith(".html")) == len(jp))
        with contextlib.redirect_stdout(io.StringIO()):
            builder.build(full, builder.SAMPLE, "https://careers.northline.example", pages=True)
        check("rebuilding is idempotent", not run(site=full)["fails"])
        with contextlib.redirect_stdout(io.StringIO()):
            builder.build(os.path.join(tmp, "switch"), builder.SAMPLE, PLACEHOLDER, pages=True)
            builder.build(os.path.join(tmp, "switch"), builder.SAMPLE, PLACEHOLDER, pages=False)
        check("switching back to a landing page leaves no stale job pages",
              not os.path.exists(os.path.join(tmp, "switch", "jobs")) and not run(site=os.path.join(tmp, "switch"))["fails"])

        import importlib.util
        spec = importlib.util.spec_from_file_location("fill_brief", os.path.join(HERE, "fill_brief.py"))
        fb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fb)
        brief = fb.fill("Northline", "deep blue", "store team members and drivers", ["Store Careers", "Driving"])
        tpl = fb.template()
        restored = (brief.replace("- Store Careers\n- Driving", "{segment pages}")
                    .replace("store team members and drivers", "{talent segments}")
                    .replace("deep blue", "{brand colour}").replace("Northline", "{Company}"))
        check("the brief is filled word for word, with no blank left", "{" not in brief and restored == tpl)

        rubric = open(os.path.join(SKILL, "references", "rubric.md"), encoding="utf-8").read()
        undocumented = [c for c in CHECKS if f"`{c}`" not in rubric]
        check("every check is documented in references/rubric.md", not undocumented, str(undocumented))

        print("\nSingle-page audit")
        single = run(page=os.path.join(full, "index.html"))
        check("site-wide checks are skipped, not failed",
              not ({"seo.sitemap", "seo.broken_links", "ai.llms_txt"} & set(single["fails"]))
              and "seo.sitemap" in single["skipped"])

        print("\nPlanted faults")
        for name, base, setup, must, must_not, exact in MUTATIONS:
            site = os.path.join(tmp, re.sub(r"\W+", "-", name))
            shutil.copytree(bases[base], site)
            setup(site)
            got = set(run(site=site)["fails"])
            missing = must - got
            wrong = got & must_not
            extra = (got - must) if exact else set()
            check(name, not missing and not wrong and not extra,
                  f"missing {sorted(missing)} unexpected {sorted(wrong | extra)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0


def main():
    ap = argparse.ArgumentParser(description="Check a careers site.")
    ap.add_argument("--site", help="the site folder")
    ap.add_argument("--page", help="one saved HTML page, to audit an existing site")
    ap.add_argument("--json", help="also write the findings as JSON here")
    ap.add_argument("--test", action="store_true", help="run the self-test suite")
    a = ap.parse_args()
    if a.test:
        sys.exit(0 if run_tests() else 1)
    if not (a.site or a.page):
        ap.error("give --site or --page")
    res = run(site=a.site, page=a.page)
    print(report(res))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
    blocking = [c for c in res["fails"] if CHECKS[c][1] == "blocking"]
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
