# Strategic Leadership Diagnostic: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the renderer's output changes,
re-run this and update the excerpt:

    python3 scripts/diagnose.py --demo

## Example prompt

> Our COO wants recruiting to increase applicant volume because six stores keep losing new hires: 41% leave within 30 days, against 19% elsewhere, while applications are flat. I believe we need to examine the employee experience, but I haven't built a convincing case or aligned with Operations. The COO and CHRO decide on $60,000 of extra advertising on 24 November. Use the five values from The Power of HR to diagnose my leadership approach, challenge my assumptions, and help me prepare a recommendation.

## Example output

From the skill's demo: the worked example it ships for this situation (`references/sample/halden_situation.md`, a fictional grocer, with the answers to the diagnostic's questions), and its checker's verdict. An excerpt.

**Leadership strength**

**Own Your Expertise.** You separate hiring volume from early turnover and you have the numbers that tell them apart: volume is flat, while 30-day turnover at the six stores is twice the rest and sits under three managers.
*Next step:* Lead with those numbers and with the explanation you have not ruled out yet, rather than with a conclusion about store leadership.

**Development opportunities**

**Be Part Coach, Part Cheerleader.** The case has gone to the COO as a verdict on store leadership, the people it is about have not been asked, and one district manager already hears it as blame.
*Rests on:* "I sent the COO a two-page memo saying the problem is store leadership, not sourcing. He didn't reply"; "One district manager told me HR is blaming the stores for a recruiting problem"; "I haven't spoken to the store managers at the six stores"

**Bring Clarity From the Clouds.** The meeting is set up to decide on advertising spend, but nobody has agreed whether the six stores need more applicants or fewer early leavers.

**What I would challenge.** You say you are sure the real problem is the stores. The numbers show a retention problem at six stores; they do not yet say why. The wait from offer to first shift is untested and the store managers have not been heard.

**Priority leadership move.** Ask the COO for thirty minutes with the district manager over the six stores before 24 November, to agree which problem the meeting is solving.

**The ask.** "Before we commit the $60,000, I recommend HR and Operations jointly review early turnover at the six stores over the next two weeks. We will come back on 8 December with an agreed problem statement, the evidence behind it, and a 90-day test, including the buddy programme that cut 30-day turnover from 33% to 21% in last year's pilot."

**Checker:** all five values examined, certainty pushback answered. READY to share.
