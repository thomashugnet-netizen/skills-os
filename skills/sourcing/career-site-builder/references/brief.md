# The brief

When someone asks me to build or redo their careers page, I fill in this brief, show
it to them in a copyable block, and then follow it. The text below is used **word for
word**. Only the parts in `{braces}` change.

## How the blanks are filled

| Blank | What goes in it | Where it comes from |
|---|---|---|
| `{Company}` | the employer's name, as they write it | the request |
| `{brand colour}` | the main brand colour by name, for example "red" or "deep blue" | the employer's site and logo |
| `{talent segments}` | the segments the employer really hires for, as a comma-separated list | research, then `talent-segments.md` |
| `{segment pages}` | one bullet per segment, named the way a candidate would search | the same list |

Everything else stays exactly as written, including the internships line, which is
already conditional. The brief stays in English even when the conversation is not;
the site is written in the language of the employer's candidates.

## The brief

Build a polished, modern, mobile-responsive careers website for {Company}.
The goal is to make {Company} feel like an exciting, credible, people-centered place to build a career—not simply a place to find hourly jobs. The site should attract candidates across {Company}’s major talent segments, including {talent segments}.
Before building:

1. Research {Company}’s current public brand, careers messaging, business footprint, job categories, benefits, culture, and candidate experience using official {Company} sources wherever possible.
2. Review the existing {Company} careers site and several best-in-class career sites from comparable high-volume employers.
3. Preserve {Company}’s recognizable brand identity, but create a more elevated, contemporary and emotionally engaging experience.
4. Do not invent company statistics, benefits, employee quotes, awards or commitments. Clearly label any content that requires {Company} confirmation.
5. Ask me only the questions that materially affect the site and cannot be answered through research. Otherwise, make thoughtful assumptions and proceed.

Design direction:

- Energetic, confident, welcoming and distinctly {Company}
- Bold use of {Company} {brand colour}, balanced with white, charcoal and warm neutral backgrounds
- Strong typography, generous spacing and clear visual hierarchy
- Authentic, documentary-style employee and workplace photography rather than generic corporate imagery
- Modern and polished without feeling like a technology startup
- Friendly and approachable without looking juvenile
- Designed primarily for mobile job seekers, while feeling excellent on desktop
- Accessible, fast-loading and easy to navigate
- Use subtle motion and interaction where it improves the experience, but avoid visual clutter or gimmicks

Create a complete homepage experience with:

- A compelling hero section with a concise employer-value proposition and prominent “Search Jobs” call to action
- A simple job-search interface that lets candidates search by keyword, location and job category
- A section that helps visitors quickly choose a career path
- Featured career categories with meaningful descriptions, not just labels
- A strong “Why {Company}?” section communicating the employee experience
- Benefits and growth opportunities presented in a candidate-friendly way
- Employee stories or testimonials, using clearly marked placeholders if verified content is unavailable
- A section showing the breadth of {Company}’s operations and career progression
- Location or market discovery
- A clear explanation of the application and hiring process
- A talent-community call to action
- A substantial, useful footer with links for candidates, current employees, accommodations, privacy and equal-employment information

Develop supporting page concepts and navigation for:

- Search Jobs
{segment pages}
- Internships and Early Careers, if supported by current {Company} offerings
- Culture and Values
- Benefits
- Career Growth
- Employee Stories
- Hiring Process
- FAQs

Candidate-experience requirements:

- Keep “Search Jobs” persistently easy to find
- Minimize the number of clicks between arrival and relevant job results
- Make location-based discovery especially intuitive
- Support candidates who know the role they want and candidates who are still exploring
- Explain what different roles are actually like
- Show realistic career pathways within {Company}
- Anticipate common questions about scheduling, qualifications, benefits, application status and accommodations
- Make the transition to any external applicant-tracking system feel intentional and clearly communicated
- Include SEO-friendly page structure and job-seeker language
- Meet WCAG 2.2 AA accessibility standards, including keyboard navigation, contrast, focus states, semantic structure and reduced-motion support

Copy direction:
Write concise, specific and human copy. Avoid clichés such as “work hard, play hard,” “we’re a family” and vague claims about limitless opportunity. The voice should feel direct, optimistic, energetic and grounded. Prioritize what candidates want to know: what the work involves, who succeeds, how schedules and benefits work, how employees grow, and why {Company} is meaningfully different.

Build the site as a production-quality interactive prototype. Use reusable components and a clean design system. Include realistic responsive states, hover and focus interactions, loading and empty states for job search, and thoughtfully selected placeholder imagery where official assets are unavailable.

Before considering the work complete:

- Test the experience on mobile, tablet and desktop
- Verify that navigation and calls to action work
- Check accessibility and contrast
- Review the site for unsupported factual claims
- Confirm that the homepage tells a coherent story from initial interest through job search
- Provide a short list of the content, assets and integrations {Company} would need to supply before production launch

Begin by presenting the proposed information architecture, homepage narrative, design direction and any essential questions. Then build the site after I approve the direction.

## How I carry it out here

The brief describes the site. These are the decisions it leaves open, settled the same
way every time:

- **What gets built is the homepage**, as one landing page from `starter/`. The
  supporting pages are concepts: they appear in the navigation and the footer, and
  each link opens the preview dialog, which says what that page would contain in the
  full version. In-page links go to their section.
- **Job search works** on example roles drawn from the research: real job titles the
  employer hires for, labelled on the page as examples, with pay marked for
  confirmation unless it came from a live posting. Choosing a role opens the preview
  dialog. With a real jobs export instead, `build_site.py --jobs` makes one page per
  job and per location, and those links go to real pages.
- **Labelling** is `<mark class="confirm">`, which `check_site.py` lists as the launch
  list.
- **"Test the experience"** is `check_site.py`, plus one look at the preview at phone
  and desktop width.
- **On top of the brief**, whatever the scripts add is kept: the job list in plain
  HTML, Organization and FAQPage markup, sitemap, robots.txt, llms.txt, and pay shown
  as a number wherever a role is listed. See `seo-ai-spec.md` and `conversion.md`.
