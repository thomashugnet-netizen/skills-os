# The build brief

This is the brief I work from for every site. The parts in `{braces}` come from
the intake and the research; everything else holds for every employer.

## Goal

Build a polished, modern, mobile-first careers site for {employer}. It should make
{employer} feel like a credible, people-centred place to build a career, not only a
place to find an hourly job, and it should attract every talent segment the employer
actually hires: {segments, from talent-segments.md and the research}.

## Before building

1. Research the employer's public brand, careers messaging, footprint, job categories,
   benefits, culture and candidate experience, using the employer's own sources first.
2. Read the existing careers site if there is one, and run `check_site.py --page` on a
   saved copy of its main page so the rebuild has a baseline to beat.
3. Keep the recognisable brand: colours, logo, tone. Make it more contemporary and more
   specific, not a different company.
4. **Invent nothing.** No statistics, benefits, quotes, awards or commitments that the
   research did not find. Anything the employer must confirm is wrapped in
   `<mark class="confirm">`, which shows on the page and lands on the launch list.
5. Ask only the questions that change the site and that research cannot answer.
   Otherwise make a reasonable assumption, say what it was, and keep going.

## Design direction

- {Adjectives from the brand}: confident, welcoming and recognisably {employer}
- Brand colour used boldly, balanced with white, charcoal and warm neutrals
- Strong type, generous spacing, clear hierarchy
- Documentary photography of real employees and real workplaces. Until the employer
  supplies it, labelled placeholders that say what the photo should show. Never stock
  people presented as staff.
- Polished without looking like a software company, friendly without looking juvenile
- Mobile first. Most frontline candidates apply from a phone.
- Subtle motion only where it helps, and none for people who ask for reduced motion

## The homepage, in this order

1. Hero: one concrete employer promise and a job search (keyword, location, area)
2. "Where are you right now?": know the job / still deciding / want to move up
3. Career areas, each with what the work involves, the schedule shape and starting pay
4. Why {employer}: three or four specific differences, not adjectives
5. Pay and benefits, in plain terms
6. Employee stories, as marked placeholders until real ones exist
7. Career growth: the actual ladder and typical timings
8. Where we are hiring: one link per location page
9. How we hire: the steps and how long each takes
10. Talent community for people whose job is not open yet
11. A useful footer: candidates, current employees, accommodations, privacy, EEO

## Supporting pages

Search jobs, one page per career area, culture and values, benefits, career growth,
employee stories, hiring process (with accommodations), FAQ. Internships and early
careers only if the employer offers them. Job pages and location pages are generated
by `build_site.py` from the jobs file.

## Candidate experience

- Search jobs is reachable from every page, in the header
- The fewest possible clicks from arrival to relevant jobs
- Location-based discovery is the easiest path, because distance decides most
  frontline applications
- Works for people who know the role and people still exploring
- Explains what each job is actually like, including the hard parts
- Shows real career paths with real timings
- Answers the questions candidates ask before applying: schedule, requirements, pay,
  benefits, application status, accommodations
- The jump to the applicant tracking system is announced, so it does not feel like a
  different company
- WCAG 2.2 AA: keyboard navigation, contrast, visible focus, semantic structure,
  reduced motion

## Before handing over

- `check_site.py --site` passes with no blocking findings
- Look at the home page and one job page at phone width and at desktop width
- Every claim is either sourced or marked for confirmation
- The homepage reads as one story, from first interest to a job search
- A short launch list: content, photos and integrations the employer must supply
