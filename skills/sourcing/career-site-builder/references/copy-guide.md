# Copy

## Voice

Direct, optimistic, grounded. Short sentences. Specific numbers over adjectives. Write
what a good store manager would say to a candidate standing in front of them.

Prioritise what candidates want to know, in this order: what the work involves, who
does well, how schedules and pay work, how people grow, and why this employer is
different from the one across the road.

## Never

- "Work hard, play hard", "we're a family", "rockstar", "ninja", "self-starter",
  "fast-paced environment", "wear many hats", "limitless opportunities",
  "competitive pay". `check_site.py` flags these.
- Claims about awards, rankings or "best place to work" unless the research found them
  and the employer confirms them. Unmarked, `check_site.py` flags them.
- Statistics, benefits, quotes or commitments the research did not find.

## Marking what needs confirmation

Anything the employer has to confirm before launch goes inside
`<mark class="confirm">...</mark>`. It shows on the page with "(to confirm)" after it,
so nobody can ship it without seeing it, and `check_site.py` lists every one at the end
of its report. That list is the launch checklist.

Use it for: pay figures not taken from a live job, benefit eligibility periods, hiring
timings, minimum ages, employee counts, store counts, quotes, and anything else that
could be wrong by the time the site goes live.

Do not use it to hedge things the research confirmed. A page full of marks reads as
a draft.

## Employee stories

Placeholders until real ones exist. Each placeholder says what the real story should
cover and what photo should go with it. Never write a quote in an employee's voice,
even as an example, without marking it: an invented testimonial on a live site is a
false statement about a real company.

## Headlines

Specific beats clever. "Run the shift people count on" says what the job is.
"Unleash your potential" says nothing. A headline should survive being read by
someone who has never heard of the employer.
