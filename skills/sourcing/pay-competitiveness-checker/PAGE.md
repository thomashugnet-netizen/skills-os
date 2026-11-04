# Pay Competitiveness Checker: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/checker.py --postings references/sample/northline_postings.csv --hours-per-week 30

## Example prompt

> Here are our postings and pay by city. Are we competitive, and what would it cost to fix the ones that aren't?

## Example output

From the engine's run on the demo file (`references/sample/northline_postings.csv`: a fictional grocer with stores in four metros and a distribution centre), against BLS wage estimates for May 2025. An excerpt.

**19 of 21 postings placed.** 2 in the bottom 10%, 7 below the 25th percentile covering 30 openings. Lifting them to the 25th: about **$47,455 a year** at 30 hours a week.

| Posting | Metro | Pays | Local 25th | Local median | Where it lands |
|---|---|---:|---:|---:|---|
| Crew Member (Deli), Store 201 | Phoenix | $13.00 | $15.29 | $16.61 | Bottom 10% |
| Cashier, Store 201 | Phoenix | $14.50 | $15.40 | $16.79 | Bottom 10% |
| Forklift Operator, DC 1 | Dallas | $18.00 | $18.89 | $22.71 | 14th percentile |
| Overnight Stocker, Store 401 | Columbus | $16.00 | $17.15 | $18.77 | 16th percentile |
| Cashier, Store 101 | Dallas | $14.50 | $13.03 | $14.38 | 51st percentile |

**One rate, four answers:** the same $14.50 cashier rate sits at the median in Dallas, Atlanta and Columbus, and below the 10th percentile in Phoenix.

**Same job, same metro, different pay:** cashiers in Dallas earn $14.50 at Store 101 and $16.00 at Store 103.

**Not placed, and why:** "Store Ambassador" is not a recognised title (confirm the occupation), and Plano is a suburb, not a principal city, so the checker asks which metro rather than guess.
