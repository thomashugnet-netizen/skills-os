# Career Site Builder: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/build_site.py --site site --demo && python3 scripts/check_site.py --site site

## Example prompt

> Show me a demo of the career site builder.

## Example output

From the skill's demo, which builds a careers site for a fictional chain of fuel stations and stores (`--demo`) and then scores it with its own checker. With your own company ("Redo our careers page: [company], [website]") you get the same three things: a styled preview in the chat, the full site as a zip, and this report.

**A landing page with 22 example roles in 7 locations, plus `robots.txt`, `sitemap.xml` and `llms.txt`.**

| Check | Passed |
|---|---:|
| Search | 17 of 17 |
| AI visibility | 5 of 5 |
| Conversion | 9 of 9 |
| Accessibility | 7 of 7 |
| Legal | 3 of 3 |
| Honesty | 3 of 3 |
| Speed | 3 of 3 |

**Marked for you to confirm before launch: 19.** Pay rates ($15.00, $15.50, $18.00 an hour), timing promises ("48 hours", "14 days") and the contact address are flagged for someone at the company to confirm. The team quotes ship as labelled placeholders ("Quote from a driver about routes, schedule and being home at night"), never as invented testimonials.
