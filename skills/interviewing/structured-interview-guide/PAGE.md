# Structured Interview Guide: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/check_guide.py --questions references/sample/manager_questions.txt

## Example prompt

> Check the questions our store managers ask before we roll them out: Tell me about yourself. Do you have kids? How old are you? Can you work weekends? What were you making at your last job? Have you ever been arrested? Where are you from originally? Tell me about a time a customer was angry with you, what did you do? Do you own a car? What's your biggest weakness? How would you get here for a 6am start? Any health problems we should know about?

## Example output

From the checker's run on the demo list (`references/sample/manager_questions.txt`: twelve questions a store manager actually asks). An excerpt.

**12 questions: 6 legal risk, 1 needs care, 3 weak, 2 no rule matched.**

| Question | Verdict | Ask this instead |
|---|---|---|
| Do you have kids? | Legal risk | "This role works Saturday and Sunday mornings, starting at 6am. Can you work those shifts?" Ask everyone, in the same words. |
| How old are you? | Legal risk | Only if the role has a legal minimum age: "This role requires you to be at least 18. Can you confirm you are?" |
| What were you making at your last job? | Legal risk | State the rate: "The rate for this role is $17 an hour. Does that work for you?" |
| Any health problems we should know about? | Legal risk | "This role involves lifting boxes of up to 40 pounds throughout a shift. Can you do that, with or without a reasonable accommodation?" |
| Do you own a car? | Needs care | "The shift starts at 6am at our Elm Street store. How would you get here for that start?" |
| Can you work weekends? | Weak | A yes/no question gets a yes. Ask for a time they did it. |
| Tell me about a time a customer was angry with you. What did you do? | No rule matched | Kept. |

"No rule matched" is not a clearance: the checker matches the phrasings it knows, in English, and says so on every run.
