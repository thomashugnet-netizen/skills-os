"""
Generates one static page per skill for fountain.com/claude-skills/<slug>.

Each page is self-contained (CSS inlined, no asset-path assumptions) and built
on the Cue Design System tokens. Content per page is unique and substantial --
these are meant to rank, not to be doorway pages.

Run: python3 build.py   ->   ./out/<slug>.html
"""

import json, os, re, html

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
BASE = "https://www.fountain.com/claude-skills"
REPO = "https://github.com/fountain/claude-skills-hr-ops"
# Where the download button points. Defaults to the local server's route so the
# site works standalone; set DOWNLOAD_BASE to a CDN or the repo when publishing.
DOWNLOAD_BASE = os.environ.get("DOWNLOAD_BASE", "/download")

# ----------------------------------------------------------------- design system

CSS = """
:root{
  --font-sans:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  --brand-50:#eef2ff;--brand-100:#e0e7ff;--brand-600:#4f46e5;--brand-800:#3730a3;
  --neutral-white:#ffffff;--neutral-50:#f8fafc;--neutral-100:#f1f5f9;--neutral-200:#e2e8f0;
  --neutral-300:#b7c0cb;--neutral-400:#687281;--neutral-600:#404d5f;--neutral-900:#0f172a;
  --blue-50:#e7f3ff;--blue-600:#357fef;--blue-800:#0c4497;--teal-600:#39d4d6;
  --amber-50:#fff8e1;--amber-600:#f68006;--amber-800:#92400e;
  --green-50:#d8f9d3;--green-600:#4ea441;--green-800:#145b2f;
  --gradient-ai:linear-gradient(180deg,#3935ff 0%,#8f00ff 100%);
  --gradient-brand:var(--gradient-ai);
  --gradient-panel-deep:linear-gradient(107.436deg,#0e3575 0%,#030121 100%);
  --gradient-sky:linear-gradient(180deg,#ffffff 0%,#d0deff 50.96%,#ffffff 100%);
  --h1:56px;--h2:40px;--h3:32px;--h5:26px;--h6:22px;
  --text-xl:22px;--text-l:18px;--text-m:16px;--text-s:14px;--text-xs:12px;
  --lh-display:1;--lh-tight:1.1;--lh-snug:1.3;--lh-body:1.4;
  --track-display:-0.03em;--track-tight:-0.02em;
  --space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:20px;--space-6:24px;
  --space-8:32px;--space-10:40px;--space-12:48px;--space-14:56px;--space-16:64px;--space-20:80px;
  --radius-lg:8px;--radius-2xl:16px;--radius-full:999px;
  --container-large:1280px;--margin-lr:80px;--section-pad:80px;
  --ring-focus:inset 0 0 0 1px var(--brand-600),0 0 0 3px rgba(79,70,229,.15);
  --shadow-sm:0 1px 8px 0 rgba(0,0,0,.05);--shadow-card:0 4px 24px 0 rgba(15,23,42,.06);
  --mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{font-family:var(--font-sans);font-size:var(--text-m);line-height:var(--lh-body);
  color:var(--neutral-900);background:var(--neutral-white);-webkit-font-smoothing:antialiased}
img{max-width:100%}
a{color:var(--brand-600)}

.fx-section{width:100%;padding:var(--section-pad) var(--margin-lr);background:var(--neutral-white)}
.fx-section--muted{background:var(--neutral-50)}
.fx-section--sky{background:var(--gradient-sky)}
.fx-container{width:100%;max-width:var(--container-large);margin-inline:auto}
.fx-eyebrow{font-size:var(--text-l);line-height:var(--lh-body);color:var(--brand-600);font-weight:400;margin:0}
.fx-h1{font-size:var(--h1);line-height:var(--lh-display);letter-spacing:var(--track-display);font-weight:700;margin:0;text-wrap:balance}
.fx-h2{font-size:var(--h2);line-height:var(--lh-tight);letter-spacing:var(--track-display);font-weight:700;margin:0;text-wrap:balance}
.fx-h3{font-size:var(--h3);line-height:var(--lh-tight);letter-spacing:var(--track-tight);font-weight:700;margin:0}
.fx-h5{font-size:var(--h5);line-height:var(--lh-snug);letter-spacing:var(--track-tight);font-weight:700;margin:0}
.fx-h6{font-size:var(--h6);line-height:var(--lh-snug);letter-spacing:var(--track-tight);font-weight:600;margin:0}
.fx-lead{font-size:var(--text-xl);line-height:var(--lh-snug);color:var(--neutral-600);margin:0}
.fx-body{font-size:var(--text-l);line-height:var(--lh-body);color:var(--neutral-600);margin:0}
.fx-small{font-size:var(--text-s);line-height:var(--lh-body);color:var(--neutral-400);margin:0}

.fx-btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--space-2);
  padding:15px 23px;border-radius:var(--radius-full);font-family:inherit;font-size:var(--text-l);
  font-weight:500;line-height:24px;white-space:nowrap;border:1px solid transparent;cursor:pointer;
  overflow:hidden;text-decoration:none;transition:transform .15s ease,box-shadow .15s ease,opacity .15s ease}
.fx-btn--primary{background:var(--gradient-brand);color:var(--neutral-white)}
.fx-btn--secondary{background:var(--neutral-white);color:var(--neutral-900);border-color:var(--neutral-300)}
.fx-btn--inverse{background:var(--neutral-white);color:var(--neutral-900)}
.fx-btn--sm{padding:var(--space-3) var(--space-5);font-size:var(--text-m)}
.fx-btn:hover{transform:translateY(-1px);box-shadow:var(--shadow-sm)}
.fx-btn:focus-visible{outline:none;box-shadow:var(--ring-focus)}
.fx-btn__icon{width:16px;height:16px;flex:none}
.fx-card{background:var(--neutral-white);border:1px solid var(--neutral-200);border-radius:var(--radius-2xl);padding:var(--space-8)}
.fx-card--muted{background:var(--neutral-50);border-color:transparent}

/* nav */
.nav{display:flex;align-items:center;justify-content:space-between;gap:var(--space-8);
  padding:var(--space-5) var(--margin-lr);border-bottom:1px solid var(--neutral-200);
  background:var(--neutral-white);position:sticky;top:0;z-index:20}
.nav__brand{display:flex;align-items:center;gap:var(--space-3);text-decoration:none;color:var(--neutral-900)}
.nav__mark{width:28px;height:28px;border-radius:var(--radius-lg);background:var(--gradient-brand);flex:none}
.nav__word{font-size:var(--text-xl);font-weight:800;letter-spacing:var(--track-tight)}
.nav__links{display:flex;align-items:center;gap:var(--space-8)}
.nav__links a{color:var(--neutral-600);text-decoration:none;font-size:var(--text-m);font-weight:500}
.nav__links a:hover{color:var(--neutral-900)}

/* breadcrumb */
.crumb{display:flex;flex-wrap:wrap;align-items:center;gap:var(--space-2);font-size:var(--text-s);color:var(--neutral-400);margin-bottom:var(--space-6)}
.crumb a{color:var(--neutral-400);text-decoration:none}
.crumb a:hover{color:var(--brand-600)}
.crumb span[aria-hidden]{color:var(--neutral-300)}

/* chips */
.chip{display:inline-flex;align-items:center;font-size:11px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;padding:3px 8px;border-radius:var(--radius-full);flex:none}
.chip--export{background:var(--amber-50);color:var(--amber-800)}
.chip--ready{background:var(--green-50);color:var(--green-800)}
.chip--cat{background:var(--brand-50);color:var(--brand-800)}

/* layout */
.hero{display:grid;gap:var(--space-5);max-width:820px}
.hero__chips{display:flex;flex-wrap:wrap;gap:var(--space-2)}
.hero__actions{display:flex;flex-wrap:wrap;gap:var(--space-3);margin-top:var(--space-4)}
.cols{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:var(--space-16);align-items:start}
.main{display:grid;gap:var(--space-16);min-width:0}
.aside{display:grid;gap:var(--space-6);position:sticky;top:96px}
.block{display:grid;gap:var(--space-5)}
.block__h{display:grid;gap:var(--space-3)}

/* tables */
.tbl-wrap{overflow-x:auto;border:1px solid var(--neutral-200);border-radius:var(--radius-2xl)}
table{width:100%;border-collapse:collapse;font-size:var(--text-s);min-width:520px}
th,td{text-align:left;padding:var(--space-4) var(--space-5);border-bottom:1px solid var(--neutral-200);vertical-align:top}
th{font-weight:700;color:var(--neutral-900);background:var(--neutral-50);font-size:var(--text-xs);
  text-transform:uppercase;letter-spacing:.05em}
tr:last-child td{border-bottom:0}
td code{font-family:var(--mono);font-size:.92em;background:var(--neutral-100);padding:2px 6px;border-radius:5px}
td:first-child{color:var(--neutral-900);font-weight:600}
td:last-child{color:var(--neutral-600)}

/* method steps */
.steps{display:grid;gap:var(--space-5)}
.stp{display:grid;grid-template-columns:32px minmax(0,1fr);gap:var(--space-2) var(--space-4);align-items:start}
.stp__n{width:32px;height:32px;border-radius:var(--radius-full);background:var(--brand-50);
  color:var(--brand-600);display:grid;place-items:center;font-size:var(--text-s);font-weight:700}
.stp__t{font-size:var(--text-l);font-weight:700;letter-spacing:var(--track-tight);padding-top:5px}
.stp__d{grid-column:2;font-size:var(--text-m);color:var(--neutral-600);line-height:var(--lh-body);margin:0}

/* output sample */
.sample{border:1px solid var(--neutral-200);border-radius:var(--radius-2xl);overflow:hidden;background:var(--neutral-white)}
.sample__bar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-4);
  padding:var(--space-3) var(--space-5);background:var(--neutral-50);border-bottom:1px solid var(--neutral-200);
  font-size:var(--text-xs);font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--neutral-400)}
.sample__body{padding:var(--space-6);font-family:var(--mono);font-size:13px;line-height:1.65;
  color:var(--neutral-900);white-space:pre-wrap;overflow-x:auto;margin:0}
.sample__note{padding:var(--space-4) var(--space-5);border-top:1px solid var(--neutral-200);
  background:var(--neutral-50);font-size:var(--text-s);color:var(--neutral-400);margin:0}

/* prompt */
.prompt{position:relative;border:1px solid var(--neutral-200);border-radius:var(--radius-2xl);background:var(--neutral-50);padding:var(--space-6)}
.prompt code{display:block;font-family:var(--mono);font-size:13px;line-height:1.7;color:var(--neutral-900);
  white-space:pre-wrap;background:none;padding:0}
.copy{position:absolute;top:var(--space-4);right:var(--space-4);border:1px solid var(--neutral-300);
  background:var(--neutral-white);color:var(--neutral-900);border-radius:var(--radius-full);
  padding:6px 14px;font-family:inherit;font-size:var(--text-xs);font-weight:600;cursor:pointer}
.copy:hover{background:var(--neutral-100)}
.copy:focus-visible{outline:none;box-shadow:var(--ring-focus)}

/* callout */
.callout{border-left:3px solid var(--amber-600);background:var(--amber-50);
  border-radius:0 var(--radius-lg) var(--radius-lg) 0;padding:var(--space-6) var(--space-8);display:grid;gap:var(--space-3)}
.callout h3{color:var(--amber-800)}
.callout p{color:var(--neutral-600);font-size:var(--text-m);line-height:var(--lh-body);margin:0}
.callout--legal{border-left-color:var(--blue-600);background:var(--blue-50)}
.callout--legal h3{color:var(--blue-800)}

/* aside cards */
.meta{display:grid;gap:0}
.meta__row{display:grid;gap:var(--space-1);padding:var(--space-3) 0;border-bottom:1px solid var(--neutral-200)}
.meta__row:last-child{border-bottom:0}
.meta__k{font-size:var(--text-xs);text-transform:uppercase;letter-spacing:.05em;color:var(--neutral-400);font-weight:700}
.meta__v{font-size:var(--text-s);color:var(--neutral-900);font-weight:600}
.rel{display:grid;gap:0}
.rel__i{display:grid;gap:var(--space-1);padding:var(--space-4) 0;border-bottom:1px solid var(--neutral-200)}
.rel__i:last-child{border-bottom:0}
.rel__n{font-size:var(--text-m);font-weight:600}
.rel__n a{color:var(--neutral-900);text-decoration:none}
.rel__n a:hover{color:var(--brand-600);text-decoration:underline;text-underline-offset:2px}
.rel__d{font-size:var(--text-s);color:var(--neutral-400);margin:0}

/* faq */
.faq{display:grid;gap:0;border-top:1px solid var(--neutral-200)}
.faq details{border-bottom:1px solid var(--neutral-200)}
.faq summary{padding:var(--space-5) 0;font-size:var(--text-l);font-weight:600;cursor:pointer;
  letter-spacing:var(--track-tight);list-style:none;display:flex;justify-content:space-between;gap:var(--space-4)}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";color:var(--brand-600);font-weight:400;flex:none}
.faq details[open] summary::after{content:"\\2013"}
.faq details p{padding:0 0 var(--space-5);font-size:var(--text-m);color:var(--neutral-600);line-height:var(--lh-body);margin:0;max-width:70ch}

/* cue panel */
.panel{background:var(--gradient-panel-deep);border-radius:var(--radius-2xl);
  padding:var(--space-16) var(--space-14);color:var(--neutral-white);display:grid;gap:var(--space-5)}
.panel__eyebrow{color:var(--teal-600);font-size:var(--text-l);font-weight:700;letter-spacing:.02em;
  text-transform:uppercase;margin:0}
.panel .fx-h2{color:var(--neutral-white);max-width:22ch}
.panel p{font-size:var(--text-l);line-height:var(--lh-snug);color:rgba(255,255,255,.78);margin:0;max-width:64ch}
.panel__actions{display:flex;flex-wrap:wrap;gap:var(--space-3);margin-top:var(--space-4)}

/* footer */
.foot{border-top:1px solid var(--neutral-200);padding:var(--space-16) var(--margin-lr);background:var(--neutral-white)}
.foot__in{max-width:var(--container-large);margin-inline:auto;display:flex;flex-wrap:wrap;
  gap:var(--space-8);justify-content:space-between;align-items:flex-start}
.foot__links{display:flex;flex-wrap:wrap;gap:var(--space-6)}
.foot__links a{font-size:var(--text-s);color:var(--neutral-400);text-decoration:none}
.foot__links a:hover{color:var(--neutral-900)}

ul.bare{margin:0;padding-left:var(--space-5);display:grid;gap:var(--space-2)}
ul.bare li{font-size:var(--text-m);color:var(--neutral-600);line-height:var(--lh-body)}
ul.bare li strong{color:var(--neutral-900)}

@media(max-width:1080px){
  :root{--h1:44px;--h2:34px;--margin-lr:40px;--section-pad:64px}
  .cols{grid-template-columns:minmax(0,1fr);gap:var(--space-12)}
  .aside{position:static}
  .nav__links{display:none}
}
@media(max-width:640px){
  :root{--h1:34px;--h2:28px;--h3:24px;--margin-lr:20px;--section-pad:48px}
  .fx-lead{font-size:var(--text-l)}
  .panel{padding:var(--space-10) var(--space-6)}
  .fx-card{padding:var(--space-6)}
  .fx-btn{width:100%}
  .copy{position:static;margin-bottom:var(--space-4)}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}.fx-btn:hover{transform:none}}
"""

# ----------------------------------------------------------------- content

PRIVACY = (
    "Remove personal data before you export. Drop or hash names, emails, phone numbers, "
    "addresses (send a distance band instead), dates of birth, national ID numbers and free-text "
    "notes — notes reliably contain both names and information about protected characteristics. "
    "This skill is written to refuse a file that looks like it contains identities and to ask you "
    "to re-export. Candidate records belong inside your own systems, under your own access controls; "
    "nothing in this analysis needs to know who anybody is."
)

SKILLS = [
  {
    "slug": "funnel-drop-off-analyst",
    "name": "Funnel Drop-off Analyst",
    "cat": "Analysing",
    "export": True,
    "title": "Funnel Drop-off Analyst — Claude skill for hiring funnel analysis",
    "meta": "A free Claude skill that reads your pipeline export, finds where candidates drop out of your hiring funnel, separates correlation from cause, and ranks the fixes by hires recovered.",
    "h1": "Find where your hiring funnel leaks — and which fix recovers the most hires",
    "lead": "Give it a pipeline export. It tells you where candidates leave, what kind of problem each loss is, and which fix is worth doing first. Ranked by hires at stake, not by which percentage looks worst.",
    "does": [
      "Most funnel analysis stops at a conversion table, which tells you where the rate is low but not where the volume went. A stage converting at 42% matters less than one converting at 71% if far more people are standing on the second one.",
      "This skill ranks every loss by absolute volume, localises it to the sites or sources carrying it, classifies what kind of problem it is, and then tests each finding against the confounds that most often turn a plausible correlation into a wrong recommendation."
    ],
    "inputs": [
      ("application_id", "Row key", "req"),
      ("applied_at", "Time trends and seasonality", "req"),
      ("stage_reached", "The furthest stage each application got to", "req"),
      ("location_id, region", "Whether a problem is systemic or lives in a few sites", "rec"),
      ("source", "Whether you are buying applicants who never convert", "rec"),
      ("role", "Whether one job is dragging the aggregate", "rec"),
      ("exit_reason", "Rule-driven losses vs. candidate-driven losses", "rec"),
      ("Stage timestamps", "Where the wait is — usually where the loss is", "rec"),
    ],
    "method": [
      ("Build the funnel honestly", "Step conversion and reach rate are computed separately, because they answer different questions. Absolute loss at each step is the number everything gets ranked on."),
      ("Localise every material loss", "Each large loss is cut by location, region, source and role to establish whether it is systemic or concentrated. Concentrated losses are cheaper to fix, and the skill says so."),
      ("Classify the mechanism", "Rule-driven, capacity-driven, candidate-driven or quality-driven. Each has a different signature in the exit reasons and timings, and a different owner."),
      ("Test against confounds", "Source mix, role mix, seasonality and elapsed time. A driver only gets reported if it survives when the most plausible alternative explanation is held constant. Anything that fails appears under Ruled out, with the check that killed it."),
      ("Size the fix", "Hires recoverable, using your own better-performing segments as the target rather than an industry benchmark. The assumption is always stated so you can argue with it."),
    ],
    "outputs": [
      "A funnel table — every stage with reached, step conversion, reach rate and absolute loss",
      "Three to six ranked findings, each with evidence, mechanism, confounds tested, hires at stake and a confidence label",
      "<strong>Ruled out</strong> — correlations that did not survive, and what killed each one",
      "What it could not determine, stated honestly",
      "A fix list ordered by hires per unit of effort, tagged with who owns each",
    ],
    "sample_title": "Finding 1 of 4",
    "sample_note": "Real output, run against the synthetic sample dataset published with this library. The rejected-region pattern, the confound check and the sizing are all reproducible from that file.",
    "sample": """FINDING 1  ·  Rule-driven  ·  Confidence: high

A screening rule applied only in the Midwest region is rejecting
applicants the rest of the estate accepts.

EVIDENCE
  Screening pass rate     Midwest  33.3%   (4,242 applications)
                          Rest     59.9%   (13,942 applications)

  Rejection reason mix    Midwest  76.8%  availability_mismatch
                          Rest     16.9%  availability_mismatch

MECHANISM
  Availability is distributed near-identically across regions
  (full 46.3% vs 45.8%), so this is not a different applicant
  pool. It is a different rule.

CONFOUNDS TESTED
  Source mix    Near-identical across regions. Gap survives
                within every individual source (0.32 vs 0.67
                career_site; 0.34 vs 0.62 jobboard_a).
  Seasonality   Gap is stable across all 12 months.

HIRES AT STAKE
  ~1,129 applicants recoverable over 12 months
  × 22.1% post-screen start rate  =  ~248 hires
  Assumes recovered applicants convert at the current
  post-screen rate, which is conservative.

OWNER
  Whoever owns the Midwest screening configuration.""",
    "prompt": "Read this skill file and follow it. I'm attaching our pipeline export for the last 12 months. Tell me where we're losing candidates and what to fix first.",
    "faqs": [
      ("Do I need to give it real candidate data?", "No, and you shouldn't give it identities at all. It works on counts, categories and dates — stage names, sources, locations, timestamps. Strip names, emails, phone numbers and addresses before exporting. If you want to try it before touching your own data, use the synthetic sample dataset published with the library."),
      ("What if my export is missing some columns?", "It works with what you have and tells you which findings it could not reach. It won't fill a gap with an assumption — that's the failure mode that produces confident nonsense."),
      ("How is this different from the reports in our ATS?", "ATS reporting tells you the conversion rate at each stage. This ranks losses by volume rather than rate, works out what kind of problem each one is, tests whether an apparent cause survives the obvious confounds, and estimates the hires a fix would recover. It's the analysis step after the report."),
      ("Can it fix anything?", "No. It reads a file you exported, so it sees one moment and changes nothing. Every recommendation is yours to carry out by hand, and you'd export again to find out whether it worked."),
    ],
    "related": ["no-show-pattern-finder", "knockout-logic-auditor", "turnover-analyst"],
  },
  {
    "slug": "no-show-pattern-finder",
    "name": "No-Show Pattern Finder",
    "cat": "Analysing",
    "export": True,
    "title": "No-Show Pattern Finder — Claude skill for first-shift no-shows",
    "meta": "A free Claude skill that finds why new hires don't turn up for their first shift and which single change would recover the most starts. Reads a CSV export.",
    "h1": "Work out why your hires don't turn up for shift one",
    "lead": "You made the offer, they accepted, they never came. This finds the conditions that predict it, ranks them against each other, and names the one change worth making first.",
    "does": [
      "In frontline hiring this is usually the most expensive loss in the whole funnel, because you paid for the entire pipeline before losing the person.",
      "The skill tests the offer-to-start wait first, because in hourly hiring it is usually both the largest driver and the most fixable. Everything else — distance, source, role, shift pattern — is then re-tested holding that wait constant, since most of those correlate with it and would otherwise be credited with its effect."
    ],
    "inputs": [
      ("application_id", "Row key", "req"),
      ("offer_at or onboarding_started_at", "Start of the wait", "req"),
      ("scheduled_first_shift_at", "The single most valuable field here", "req"),
      ("first_shift_at", "Blank when they never came — this is the outcome", "req"),
      ("location_id, region", "Site problem or policy problem", "rec"),
      ("source", "Whether a channel sends people who never intended to start", "rec"),
      ("commute_band_km", "Distance effects — real, but smaller than people assume", "rec"),
      ("availability_match", "Whether you hired people for shifts they can't work", "rec"),
    ],
    "method": [
      ("Establish the base rate", "Overall no-show rate and its month-to-month movement. Peak periods worsen it, so seasonal drift is separated out before any driver is examined — otherwise a Q4 export produces four confident findings that are all the same finding."),
      ("Test the wait", "The gap between offer and scheduled first shift, banded. Then: is the gap being created somewhere specific? A fortnightly induction, a compliance step that queues, a manager who only starts people on Mondays. A long wait is a symptom; the queue behind it is the cause."),
      ("Rank everything else against the wait", "Each remaining driver is tested, then re-tested within a single wait band. If the spread collapses, it was carrying the wait's effect. If it survives, it's real and gets sized."),
      ("Check interactions", "Some combinations are far worse than either factor alone — a long wait and a 40+ km commute. Where the interaction beats the sum of its parts it becomes its own finding, because the fix is narrow and cheap."),
      ("Size it", "Starts recoverable against your own best-performing band, with the assumption stated."),
    ],
    "outputs": [
      "Base rate, overall and by month, with the seasonal component called out",
      "The wait curve — no-show rate by offer-to-start gap, with volume in each band",
      "Ranked drivers, each showing whether it survived the wait-controlled test",
      "Interactions worth acting on",
      "<strong>The one change</strong> — a single recommendation with the starts it should recover, plus two runners-up",
    ],
    "sample_title": "The wait curve",
    "sample_note": "Run against the synthetic sample dataset. Note the second table: the gap effect holds inside a single commute band, which is what establishes it as the driver rather than a passenger.",
    "sample": """NO-SHOW RATE BY OFFER-TO-FIRST-SHIFT GAP

  gap band      no-show rate    hires in band
  1–3 days           15.5%              621
  4–7 days           25.4%            1,110
  8–11 days          37.8%              969
  12+ days           40.2%              333

  Base rate 28.9%.  2.6x spread across the curve.

DOES IT SURVIVE, HOLDING COMMUTE CONSTANT?
Within the 0–5 km band only — so distance cannot explain it:

  1–3 days           10.9%              183
  4–7 days           22.7%              326
  8–11 days          32.1%              274
  12+ days           40.2%               92

  Effect holds. The wait is the driver.

AND THE REVERSE, HOLDING THE GAP CONSTANT?
Within the 1–3 day band only:

  0–5 km             10.9%              183
  6–10 km            14.2%              169
  11–20 km           17.1%              123
  40+ km             29.6%               54

  Distance is real but materially weaker, and concentrated
  in the 40+ km tail.

THE ONE CHANGE
  Move offers in the 8+ day bands under 7 days.
  1,302 hires sit in those bands at 38.4% combined.
  At the 4–7 day rate of 25.4%: ~169 starts recovered.""",
    "prompt": "Read this skill file and follow it. I'm attaching an export of everyone who accepted an offer in the last six months, including the ones who never showed. Tell me why and what to change.",
    "faqs": [
      ("What if my export only has actual start dates?", "Then the wait can't be measured for the people who didn't show — the group that matters most. Ask for the scheduled first shift date before exporting; it's the single most valuable field for this analysis."),
      ("Isn't the answer always ‘pay more’?", "Sometimes, and this skill can't see local pay competitiveness. What it can show is how much of your no-show rate is explained by things you control — the wait, the availability match, the handover — before you conclude it's the market."),
      ("Can it tell me who is likely to no-show this week?", "No. It reads a file you exported, so it describes a period that has already happened. It can't see who is scheduled for a first shift right now, and it can't message any of them."),
    ],
    "related": ["funnel-drop-off-analyst", "day-one-readiness-checklist", "turnover-analyst"],
  },
  {
    "slug": "turnover-analyst",
    "name": "Turnover Analyst",
    "cat": "Analysing",
    "export": True,
    "title": "Turnover Analyst — Claude skill for early attrition analysis",
    "meta": "A free Claude skill that breaks 30, 60 and 90-day attrition down by location, manager, source and role, and untangles which one is actually driving it.",
    "h1": "Find out which of your sites, managers or sources is really driving early attrition",
    "lead": "Early attrition in frontline work is rarely spread evenly. It concentrates — in a few sites, a few managers, a few sources. That concentration is the finding, and separating it from its confounds is the hard part.",
    "does": [
      "Managers, roles and sites are entangled. A manager with bad early attrition may simply run the site that hires the hardest role, and a naive cut will blame the role and leave the real problem in place.",
      "This skill cohorts hires properly, measures concentration, then re-tests every apparent driver within a fixed level of the other two. Whatever survives all its within-strata tests is the driver; the rest are reported as explained by it."
    ],
    "inputs": [
      ("employee_id", "Row key", "req"),
      ("first_shift_at", "Cohort anchor", "req"),
      ("separation_at", "Blank if still employed — include current staff or there is no rate", "req"),
      ("hiring_manager_id", "The manager effect, usually the largest single one", "rec"),
      ("location_id, region", "Concentration, at site or group level", "rec"),
      ("source", "Whether a channel sends people who leave", "rec"),
      ("separation_reason", "Voluntary vs. involuntary, and the mechanism", "rec"),
      ("shift_pattern, contracted_hours", "Scheduling as a cause, which it very often is", "rec"),
    ],
    "method": [
      ("Cohort properly", "Hires are grouped by start month and measured at 30, 60 and 90 days. Anyone without a full window is excluded from that window, and the count of exclusions is reported — including them silently deflates the rate."),
      ("Measure concentration", "What proportion of early leavers come from what proportion of sites. If 20% of locations produce 55% of 30-day leavers, that is the headline and everything else is secondary."),
      ("Untangle manager from role from site", "Every apparent driver is re-tested within a fixed level of the others. Where volume is too thin to run the test, the skill says the test could not be run rather than reporting the naive number as if it were clean."),
      ("Read the mechanism", "Separation-reason distributions per segment. Schedule conflict and attendance point at hiring people for shifts they can't work; ‘job not as described’ points at the ad or the interview. Cross-referencing with availability at application is often the most useful cut in the whole analysis."),
      ("Size the fix", "Leavers avoidable against your own best comparable segment, over a stated period."),
    ],
    "outputs": [
      "Survival table — 30/60/90-day retention by start-month cohort, with exclusion counts",
      "Concentration summary — how much of the problem sits in how little of the estate",
      "Ranked drivers with within-strata test results, volume, mechanism and confidence",
      "<strong>Explained by</strong> — dimensions that looked like drivers but resolved into another",
      "Where the sample is too thin to conclude, named explicitly",
    ],
    "sample_title": "The manager/role confound",
    "sample_note": "Run against the synthetic sample dataset. The naive cut blames the role; the within-role cut finds the managers. This is the whole point of step 3.",
    "sample": """30-DAY ATTRITION — THE NAIVE CUT, BY ROLE

  Delivery Driver        24.1%      481 hires
  Cashier                16.1%      409
  Team Member            13.4%      753
  Stocker                13.0%      315
  Shift Supervisor       10.7%      197

  Reads as: we have a Delivery Driver problem.

THE SAME DATA, BY HIRING MANAGER GROUP

  5 flagged managers     38.0%      237 hires
  All others             13.3%    1,918

WITHIN DELIVERY DRIVER ONLY
Holding role constant, so role cannot explain it:

  5 flagged managers     39.7%      136
  All others             18.0%      345

WITHIN TEAM MEMBER ONLY

  5 flagged managers     33.3%       39   ⚠ thin sample
  All others             12.3%      714

CONCLUSION
  The manager effect survives within role. The role effect
  shrinks from 24.1% to 18.0% once the five managers are
  removed — most of the apparent role problem was those
  managers, whose sites happen to be driver-heavy.

  Driver:       hiring manager  (high confidence)
  Explained by: role            (small genuine residual)

  ⚠ Per-manager rates are unadjusted for site difficulty,
    local labour market and team size. Treat as a list of
    places to go and look, not a verdict on a person.""",
    "prompt": "Read this skill file and follow it. I'm attaching a hire-level export for the last 12 months including people still employed. Tell me what's driving our 30-day attrition.",
    "faqs": [
      ("Can I use this to performance-manage a manager?", "Be careful. The numbers are unadjusted for site difficulty, local labour market, team size and role mix, and small teams produce wild rates from tiny differences. The skill always reports volume alongside rate and flags samples too small to conclude from. Treat it as a list of places to investigate, and check your own jurisdiction's rules before using anything like this in a performance process."),
      ("Why do I need to include people who are still employed?", "Because a file of leavers only cannot produce a rate — you'd have no denominator. The skill needs the full cohort."),
      ("What if we don't record separation reasons?", "It still works, but you lose the mechanism step, which is where the actionable answer usually is. The skill will tell you that's what it's missing."),
    ],
    "related": ["no-show-pattern-finder", "funnel-drop-off-analyst", "day-one-readiness-checklist"],
  },
  {
    "slug": "knockout-logic-auditor",
    "name": "Knockout Logic Auditor",
    "cat": "Screening",
    "export": True,
    "title": "Knockout Logic Auditor — Claude skill to audit screening rules",
    "meta": "A free Claude skill that reviews your existing screening and knockout rules against funnel data to find the questions quietly rejecting applicants who would have worked out.",
    "h1": "Find the screening rules that are quietly killing your applicant flow",
    "lead": "Screening rules get added over years and almost never removed. Each one was reasonable when someone added it. Together they can reject half your applicants before a human looks at anyone.",
    "does": [
      "The audit starts from your actual constraint. A screen passing 60% when your interviewers can only handle 30% isn't over-filtering — it's pushing the bottleneck downstream. A screen passing 25% when you're short of staff is destroying supply. Neither number is right on its own.",
      "It then costs each rule individually, finds configuration drift between groups, and — where the data allows — checks whether the rejected group would actually have performed worse. That last question is the one nobody asks, because the rule makes the rejected group invisible."
    ],
    "inputs": [
      ("Your current rules", "Screenshot, pasted list, or just describe them", "req"),
      ("application_id, stage_reached", "Who got past screening", "req"),
      ("exit_reason", "The critical one — which rule fired", "req"),
      ("location_id, region", "Whether one group runs a different config", "rec"),
      ("source", "Whether a rule only bites one channel", "rec"),
      ("Screening answers", "Lets it model what removing a rule would recover", "rec"),
      ("Downstream outcomes", "Whether the rejected group would have succeeded", "rec"),
    ],
    "method": [
      ("Rate the screen against your constraint", "Pass rate compared with what your downstream interview and onboarding capacity actually needs, so ‘too tight’ means something specific."),
      ("Cost every rule", "Volume rejected, share of all rejections, and overlap. A rule that only ever fires on applicants another rule already rejected is free to remove — it isn't doing anything."),
      ("Find configuration drift", "Where one region or brand has a different pass rate, the exit-reason mix reveals whether that's different applicants or different settings. This is usually the most valuable finding, because it's a settings change rather than a policy debate."),
      ("Ask whether the rule was right", "Where both the answer and the outcome are visible, it checks whether the rejected group actually performed worse. Any group that slipped through — a different site, a period before the rule, a manual override — is the sample that answers this."),
      ("Flag adverse impact", "Availability, distance and shift-pattern rules can proxy for caring responsibilities, disability and access to transport. The skill flags; it does not clear."),
    ],
    "outputs": [
      "Screen-level verdict — pass rate against your actual constraint",
      "Rule-by-rule table — volume rejected, share, overlap, verdict",
      "Configuration drift — any group running a different screen, and what it costs them",
      "For each rule: <strong>keep</strong>, <strong>loosen</strong>, <strong>move later</strong> or <strong>remove</strong>, with applicants recovered and downstream load created",
      "Adverse impact flags, with an explicit note on what could not be checked",
    ],
    "sample_title": "Rule verdicts",
    "sample_note": "Run against the synthetic sample dataset. Note the last column: a recommendation that recovers applicants your interviewers can't absorb isn't a recommendation.",
    "sample": """SCREEN-LEVEL VERDICT
  Pass rate 53.7% overall — but 33.3% in one region and
  ~60% in the other three. The aggregate hides the finding.

RULE-BY-RULE

  Rule                  Rejected   Share   Verdict
  availability_knockout    2,171   25.8%   LOOSEN
  incomplete_application   2,043   24.3%   KEEP
  failed_knockout          1,853   22.0%   MOVE LATER
  withdrew (not a rule)    1,247   14.8%   —
  other                    1,098   13.1%   review

CONFIGURATION DRIFT  — the headline
  The availability knockout runs as a hard reject in the
  Midwest and as a scored factor everywhere else.

    Midwest    partial availability →  15.3% pass
               limited availability →   1.8% pass
    Elsewhere  partial availability →  60.8% pass
               limited availability →  58.9% pass

  Availability is distributed identically across regions.
  This is a settings difference, not an applicant difference.

WAS THE RULE RIGHT?
  Partial-availability hires who got through elsewhere:
    start rate      11.8%   vs  12.1% for full availability
    30-day retention 86.4%  vs  87.1%
  No material difference. The rule is rejecting people who
  would have worked out.

RECOMMENDATION
  Loosen to scored, matching the other three regions.
  Recovers ~1,129 applicants/year → ~248 hires.
  Requires ~1,129 additional screens and ~510 additional
  interview slots in the Midwest. Check that capacity
  exists before flipping the setting.

⚠ ADVERSE IMPACT FLAG
  Availability knockouts can proxy for caring
  responsibilities, disability and transport access.
  Flagged for qualified review — not cleared. Absence of
  further flags is not a clean bill of health; your export
  cannot show demographics and should not.""",
    "prompt": "Read this skill file and follow it. Here are our current screening rules, and a pipeline export with exit reasons. Tell me which rules are costing us hires we'd have wanted.",
    "faqs": [
      ("What if we don't have exit reasons in our export?", "Then it can tell you that screening is over-filtering but not which rule is doing it. That column is worth chasing before running this."),
      ("How can it know how rejected applicants would have performed?", "Only from whatever group slipped past — a different site, a period before the rule, a manual override. The skill tells you how large that group is, and where it's too small the honest answer isn't a recommendation, it's a deliberate test: loosen one rule at a handful of sites for a month, then re-run."),
      ("Is the adverse impact check a compliance sign-off?", "No. It flags rules that could proxy for a protected characteristic so someone qualified can look properly, with demographic data the skill doesn't have and shouldn't. An absence of flags is not a clean bill of health."),
    ],
    "related": ["screening-question-builder", "funnel-drop-off-analyst", "job-ad-writer"],
  },
  {
    "slug": "job-ad-writer",
    "name": "Job Ad Writer",
    "cat": "Writing",
    "export": False,
    "title": "Job Ad Writer — Claude skill for hourly job adverts",
    "meta": "A free Claude skill that writes high-volume hourly job ads built for mobile, with a rewritten variant for every channel you post to and an interpretable A/B test.",
    "h1": "Write hourly job ads that work on a phone",
    "lead": "Built for volume roles where the goal is qualified applications per pound spent, not the most polished prose. One primary ad, then a genuinely rewritten version for each channel — not a truncated one.",
    "does": [
      "Structure follows what an hourly applicant actually decides on, in the order they decide it: can I get there, can I work those hours, what does it pay, what will I be doing, how do I apply. Culture statements go last or not at all — not because they don't matter, but because nobody reads past the shift pattern to find them.",
      "Written at a controlled reading level for a phone on a slow connection, and honest about the hard parts of the job. Overselling a shift role is the most reliable way to buy 30-day attrition."
    ],
    "inputs": [
      ("Role, location, pay, shift pattern", "The four things it can't write without", "req"),
      ("Hard requirements", "Licence, certification, minimum age, physical demands", "rec"),
      ("What beats the job across the street", "Same-day pay, free meals, a bus route, predictable hours", "rec"),
      ("Channels and character limits", "Which variants to produce", "rec"),
      ("Reading level or language needs", "If you know your applicant pool", "rec"),
    ],
    "method": [
      ("Lead with the deciding facts", "Location, shift pattern and pay in the first screen. In hourly hiring an ad without pay converts materially worse than one with it, and in a growing number of jurisdictions omitting it isn't optional."),
      ("Write for a phone", "Short paragraphs, no tables, no dependence on formatting surviving a job board's rendering. Most frontline applications happen on mobile, often standing up."),
      ("Keep the language plain", "Around a 12–14 year reading level by default — not to condescend, but because it converts better across a workforce that includes second-language speakers and people applying in two spare minutes."),
      ("Strip the false filters", "Requirements that proxy for something else get flagged: ‘own car’ where you mean ‘be here for a 6am start’, ‘flexible’ where you mean a specific rotating pattern."),
      ("Preview the job honestly", "If the work is repetitive, cold, physical or eight hours on your feet, the ad says so. It costs applications and buys starts."),
    ],
    "outputs": [
      "A primary ad, full length, ready to post",
      "Channel variants — job board, social, SMS, in-store QR poster, and a referral message your staff can forward without embarrassment",
      "Two A/B variants changing exactly one thing each, with the hypothesis stated so the test is interpretable",
      "A title set, with the trade-off named between what people search for and your internal job title",
      "What it pushed back on, and why",
    ],
    "sample_title": "SMS and in-store variants",
    "sample_note": "Excerpt. The full output includes the primary ad, four other channel variants, two A/B variants and the title set.",
    "sample": """SMS / WHATSAPP  (154 characters)

  Warehouse work in Dagenham. £12.60/hr, 6am–2pm Mon–Fri.
  No experience needed. Paid weekly. Apply in 2 mins: [link]


IN-STORE POSTER / QR  (readable from two metres)

  WE'RE HIRING
  Warehouse Assistant
  £12.60 an hour
  6am – 2pm, Monday to Friday
  Paid every Friday
  Scan to apply — takes 2 minutes


A/B VARIANT B  — one change from the primary ad

  Changed:     opening line only
  Hypothesis:  leading with the shift pattern rather than the
               role title raises apply rate among people who
               are screening for hours first, and lowers
               applications from people who can't work
               mornings — so total applications may fall
               while qualified applications rise.
  Measure:     apply rate, and pass rate at screening.
               If applications drop but screen-pass rises,
               B wins even on lower volume.


WHAT I PUSHED BACK ON

  • "Flexible hours" — you described a fixed 6am–2pm shift.
    Applicants read "flexible" as flexibility for them,
    discover it means flexibility for you, and leave in
    week two. Changed to the actual pattern.

  • "Competitive rates" — replaced with £12.60. This is the
    single highest-impact change in the ad.

  • "Must be physically fit" — vague and risks excluding
    people you'd hire. Changed to the actual requirement:
    "lifting up to 15kg repeatedly through the shift".""",
    "prompt": "Read this skill file and follow it. I need a job ad for a warehouse assistant in Dagenham, £12.60/hr, 6am-2pm Monday to Friday, no experience needed. We post on Indeed, Facebook and in-store.",
    "faqs": [
      ("Will it write an ad without the pay rate?", "It will, and it'll tell you what that's likely costing you. In hourly hiring pay is the field applicants filter on first."),
      ("Can it post the ad for me?", "No. It writes the copy; posting, testing and measuring are yours. It'll set the A/B test up so the result is interpretable, but it can't run it or see the outcome."),
      ("Does it work for non-UK/US roles?", "Yes — tell it the market and the currency. It doesn't know local pay-transparency law, so check that separately."),
    ],
    "related": ["screening-question-builder", "knockout-logic-auditor", "funnel-drop-off-analyst"],
  },
  {
    "slug": "screening-question-builder",
    "name": "Screening Question Builder",
    "cat": "Screening",
    "export": False,
    "title": "Screening Question Builder — Claude skill for high-volume screening",
    "meta": "A free Claude skill that builds knockout and scoring logic for hourly roles, tuned to a target pass rate derived from your actual interview capacity.",
    "h1": "Build screening logic tuned to a target pass rate, not a target shortlist",
    "lead": "Most screening designs start from ‘who do we want’ and end up rejecting more people than the business can afford to lose. This one starts from arithmetic.",
    "does": [
      "Hires needed, divided by your interview-to-hire and offer-to-start rates, gives the interviews you need, which gives the pass rate your screen has to hit. The design then lands there. If your requirements can't produce that pass rate from your current applicant flow, that is the finding — and no amount of question design fixes it.",
      "Questions are then split into three tiers rather than one, because grouping everything as pass/fail is what produces over-filtering."
    ],
    "inputs": [
      ("The role", "And what genuinely disqualifies someone — not preferences", "req"),
      ("Target pass rate, or the inputs for it", "Applications/week, hires needed/week, interview capacity", "req"),
      ("Whether a human reviews borderline cases", "Or the logic runs fully automatic", "rec"),
      ("How many questions before applicants abandon", "On mobile, five is a lot", "rec"),
    ],
    "method": [
      ("Derive the pass rate first", "Everything else depends on it, and it's shown as working so you can argue with the inputs."),
      ("Tier the questions", "Tier 1 hard knockouts — small list, each surviving the test ‘what happens if we hire someone without this’. Tier 2 scored with weights and a threshold, which is where most requirements belong. Tier 3 captured but not scored, so you can place someone rather than reject them."),
      ("Handle availability as overlap", "The most common design error in frontline screening is a hard availability knockout. It rejects people who could work most of your shifts and it carries adverse-impact risk. The better design scores overlap with the shifts you need and routes rather than rejects."),
      ("Write each question for how it'll be answered", "One idea per question, concrete over abstract, answer options covering the awkward middle, and nothing that invites an answer revealing a protected characteristic — including indirect routes."),
      ("Review for adverse impact", "Every Tier 1 and Tier 2 question checked for whether it could proxy for a protected characteristic, with a safer alternative offered where the intent is legitimate."),
    ],
    "outputs": [
      "The pass-rate calculation, shown",
      "The question set, tiered, with exact wording and answer options",
      "Scoring logic — weights, thresholds, and what happens at each band",
      "Predicted pass rate and how it moves as you shift the threshold",
      "<strong>Routing rules</strong> for the middle band — usually the most valuable part, and usually the part nobody builds",
      "The three numbers to check after two weeks",
    ],
    "sample_title": "The availability question, done properly",
    "sample_note": "Excerpt. The full output includes the pass-rate derivation, all three tiers, the scoring table, routing rules and the risk notes.",
    "sample": """PASS RATE DERIVATION

  Hires needed / week                        14
  Offer-to-start rate                     71.1%   → 20 offers
  Interview-to-offer rate                 68.7%   → 29 interviews
  Interview capacity / week                  35   ✓ fits
  Applications / week                      ~350
  Required screening pass rate            ~8.3%

  ⚠ This is unusually tight. A screen at 8% will reject
    people you'd hire. The cheaper fix is more interview
    capacity, not a stricter screen — at 35 interviews you
    are capacity-bound, not applicant-bound.


TIER 2 — SCORED   (not a knockout)

  Q. Which of these shifts could you work?
     Tick everything that applies. You don't need to
     tick them all.

     [ ] Weekday mornings    (6am – 2pm)
     [ ] Weekday afternoons  (2pm – 10pm)
     [ ] Weekday nights      (10pm – 6am)
     [ ] Saturday
     [ ] Sunday

  Scored on OVERLAP with the shifts you need filled,
  not on total availability:

     overlap ≥ 80% of needed shifts        6 pts
     overlap 50–79%                        4 pts
     overlap 25–49%                        2 pts
     overlap < 25%                         0 pts

  Why not a knockout: someone who can't do Saturday
  evening may be exactly who you need on Tuesday
  mornings. Availability knockouts also correlate with
  caring responsibilities, disability and transport
  access, so they carry adverse-impact risk as well as
  costing you supply.


ROUTING — the middle band

  Score 8–12   → advance to interview
  Score 5–7    → hold, and offer the sites/shifts their
                  availability DOES cover. Do not reject.
  Score 0–4    → reject, with the reason recorded

  The 5–7 band is ~22% of applicants. Most screens
  reject them. Routing them to a different site or
  shift is the cheapest supply you have.""",
    "prompt": "Read this skill file and follow it. I need screening logic for a team member role. We get about 350 applications a week per site, need 14 hires a week, and can run about 35 interviews a week.",
    "faqs": [
      ("Can it tell me how my current screen performs?", "Not from a description — for that use Knockout Logic Auditor, which reads your funnel data and finds which existing rules are rejecting people who would have worked out."),
      ("Is the adverse impact review a legal check?", "No. It flags wording and requirements that could proxy for a protected characteristic and offers safer alternatives. Automated screening is regulated in a growing number of jurisdictions and the specifics change — anything you deploy should be reviewed by someone qualified with your own legal position in front of them."),
      ("Why 1-3 scoring and not 1-5?", "That's the interview guide skill, but the same logic applies: untrained scorers cluster on the middle of a five-point scale and the extra granularity is noise."),
    ],
    "related": ["knockout-logic-auditor", "structured-interview-guide", "job-ad-writer"],
  },
  {
    "slug": "structured-interview-guide",
    "name": "Structured Interview Guide",
    "cat": "Interviewing",
    "export": False,
    "title": "Structured Interview Guide — Claude skill for frontline interviews",
    "meta": "A free Claude skill that builds a fifteen-minute structured interview guide a store or site manager can run consistently, with anchored scoring and no training needed.",
    "h1": "Build an interview a site manager will actually run",
    "lead": "Short, scripted, scored on the spot, and the same every time. Designed for the reality of frontline hiring, where the interviewer is a GM between deliveries who has had no interview training.",
    "does": [
      "Structured interviews predict job performance substantially better than free-form conversations, and are far more defensible if a hiring decision is challenged. Every departure from structure is a place where a decision gets made on rapport.",
      "So the design constraint here isn't the candidate — it's the interviewer. One page, scoring anchors printed under each question rather than in a separate rubric nobody opens, and a script for the awkward parts where untrained interviewers improvise."
    ],
    "inputs": [
      ("The role", "And what separates a six-month hire from a three-week one — usually not skills", "req"),
      ("How long the interview can realistically be", "Be honest; a great 30-minute guide that gets abandoned is worth nothing", "req"),
      ("Who runs it", "Recruiter, GM, shift lead, or whoever is free", "rec"),
      ("In person, phone or video", "And whether it's walk-in", "rec"),
      ("Required competencies or values", "If you have to assess them", "rec"),
    ],
    "method": [
      ("Four to six questions, no more", "In fifteen minutes, six questions means two minutes each including the answer. Four asked properly beats eight rushed."),
      ("Pick for retention, not polish", "Reliability and getting here; a realistic job preview tested against the hardest genuine part of the role; availability confirmed out loud; one role-critical behaviour; and their questions, which are diagnostic."),
      ("Anchor the scoring 1–3", "Not 1–5 — untrained interviewers cluster on the middle of a five-point scale. Each point gets a written description of what an answer at that level sounds like, scored during the interview, because scores written afterwards are memory reconstructions."),
      ("Script the awkward parts", "The opening, the close, and a follow-up probe for every question, for the interviewer who gets a one-word answer."),
      ("Keep it legally careful", "Nothing about, or inviting answers about, age, health, disability, pregnancy, caring responsibilities, nationality beyond right to work, or religion. Availability and transport get asked in ways that don't route into those subjects — which takes care, because the obvious phrasings do."),
    ],
    "outputs": [
      "The one-page guide — opening script, questions with anchors inline, closing script, decision rule",
      "Follow-up probes for each question",
      "A print-ready scoring sheet that produces a defensible record",
      "The decision rule — stated as a rule, so the same answer produces the same outcome at every site",
      "Three red flags and three green flags, concrete and observable",
      "<strong>What not to ask</strong>, with the safe alternative beside each",
    ],
    "sample_title": "Question 1, with anchors",
    "sample_note": "Excerpt. The full output is a one-page guide with all questions, probes, the scoring sheet, the decision rule and the what-not-to-ask list.",
    "sample": """Q1  GETTING HERE          (3 minutes)

  Ask exactly:
  "This role starts at 6am. Walk me through how you'd
   get here for a 6am start on a Tuesday."

  Listen for a specific plan, not a promise.

  SCORE NOW — circle one:

  3  Names the actual route and how long it takes.
     Has done a similar start time before, or has
     clearly worked it out.
     e.g. "Bus 128 from Barking, 20 minutes, I'd get
     the 5:20. I did 6am starts at my last job."

  2  Has a plan but it's vague or has one weak point
     they acknowledge.
     e.g. "I'd drive, about 25 minutes I think. Might
     be tight if there's traffic."

  1  No specific plan, or the plan depends on someone
     else with no fallback.
     e.g. "I'd figure it out." / "My partner would
     drop me if he's not working."

  PROBE if you get a one-word answer:
  "How long would that take you door to door?"
  "Have you worked a start that early before?"


WHAT NOT TO ASK

  Don't ask                     Ask instead
  ──────────────────────    ─────────────────────────
  Do you have kids /            Which of these shifts
  childcare sorted?             could you work?

  Do you have a car?            How would you get here
                                for a 6am start?

  Any health issues that        This role involves
  would stop you?               lifting up to 15kg
                                repeatedly. Can you do
                                that with or without
                                adjustments?

  How old are you?              Are you 18 or over?
                                (only if legally required
                                 for the role)

  Where are you from?           Do you have the right to
                                work in the UK?""",
    "prompt": "Read this skill file and follow it. I need a 15-minute interview guide for a team member role, run by store managers who've had no interview training.",
    "faqs": [
      ("Our interviews are ten minutes. Is that too short?", "No — tell it ten and it designs for ten, which means about four questions. A guide built for the time you actually have gets used; one built for the time you wish you had gets abandoned."),
      ("How do we keep several interviewers consistent?", "Ask for the calibration pack: three written candidate answers per question at different quality levels, for your interviewers to score independently and compare. Where they disagree, the anchor wording needs sharpening. Twenty minutes, and worth more than most interview training."),
      ("Our interviews get booked and then missed.", "Then a better guide won't help — that's a scheduling and comms problem. Interview No-Show Playbook diagnoses it from funnel data."),
    ],
    "related": ["screening-question-builder", "day-one-readiness-checklist", "job-ad-writer"],
  },
  {
    "slug": "day-one-readiness-checklist",
    "name": "Day-One Readiness Checklist",
    "cat": "Onboarding",
    "export": False,
    "title": "Day-One Readiness Checklist — Claude skill for new hire onboarding",
    "meta": "A free Claude skill that builds the checklist of everything that must be true before a new hire's first shift, by role and location, with an owner and deadline on every line.",
    "h1": "Turn “they start Monday” into a list with owners and deadlines",
    "lead": "Frontline starts fail on small logistics far more often than on anything to do with the hire. This builds the list backwards from the first shift, and flags which items mean the person legally or practically cannot work that shift.",
    "does": [
      "Every item gets a deadline expressed as days before start rather than a date, so the checklist works for any hire. Items with external dependencies — background checks, certifications, anything with a queue — are placed by their realistic turnaround, not their best case.",
      "And it includes the category everyone skips: the human one. Who greets them, where to park, what to bring. Nothing breaks if you miss it, but they don't come back."
    ],
    "inputs": [
      ("Role and location", "State or country matters for the compliance items", "req"),
      ("Start date and offer-acceptance date", "The gap determines what's actually achievable", "req"),
      ("What you already have in place", "It would rather refine your list than replace it", "rec"),
      ("Who does the work", "Central onboarding team, or the site manager", "rec"),
      ("Role-specific items", "Vehicle, licence, food handling, safety equipment, systems access", "rec"),
    ],
    "method": [
      ("Work backwards from the first shift", "Deadlines as days-before-start. Queued items placed by realistic turnaround."),
      ("Sort into four categories, because they fail differently", "Blocking — they cannot legally work the shift. Operational — they turn up and can't do the job. Human — nothing breaks, but they don't come back. Confirmation — the cheapest intervention against a first-shift no-show."),
      ("Name one owner per line", "A role, not a team. Shared ownership on an onboarding checklist means nobody does it."),
      ("Flag the gap", "A long accepted-to-start gap is one of the strongest predictors of first-shift no-shows, and no checklist quality compensates for it. A short gap gets a different warning: which items realistically won't clear, and whether to re-sequence, move the start, or accept a conditional start where that's lawful."),
      ("Cover shift two", "A surprising share of frontline attrition happens between the first and second shift, and nobody's checklist covers that gap."),
    ],
    "outputs": [
      "The checklist, grouped by category, sequenced by days-before-start, with owner and blocking status per line",
      "<strong>The blocking subset</strong>, extracted — what a manager can check in thirty seconds on the Friday before",
      "Role and location notes — what changes versus your standard flow",
      "Escalation triggers for each blocking item, and who decides whether the start moves",
      "A day-one SMS to the hire — the highest-return item on the whole list",
    ],
    "sample_title": "The blocking subset and the day-one message",
    "sample_note": "Excerpt. The full output includes all four categories sequenced by days-before-start, escalation triggers and the shift-two follow-up.",
    "sample": """BLOCKING — check these on the Friday before
If any line is unticked, the shift cannot go ahead.

  [ ] Right-to-work verified and recorded
      owner: Site Manager        due: T-3 days
  [ ] Food handling certificate on file
      owner: Site Manager        due: T-5 days
  [ ] Under-18 hour restrictions applied to rota
      owner: Scheduler           due: T-2 days
      (only if hire is 16–17)
  [ ] Safety induction booked
      owner: Shift Lead          due: T-1 day

  ⚠ GAP WARNING
    Offer accepted 14 Sep, first shift 6 Oct = 22 days.
    That gap is in the highest no-show band. Two options:
      (a) bring the start forward to the 22nd — all four
          blocking items clear comfortably by then
      (b) keep the date and add a T-7 and T-2 contact
    Do not do neither.


DAY-ONE MESSAGE — send at T-2 days
Highest-return item on this list. Send as SMS.

  Hi Sam — you're starting with us on Monday 6 Oct.

  Where:  Dagenham store, staff entrance at the BACK
          of the building (not the shop door)
  When:   5:50am for a 6am start
  Ask for: Priya, she's expecting you
  Bring:  photo ID, and your bank details
  Wear:   dark trousers and closed-toe shoes.
          We'll give you the shirt.
  Parking: free in the staff bays, first left off
          Chequers Lane

  Any problem at all, call or text me on 07xxx xxxxxx.
  See you Monday.

  — Priya, Store Manager


BETWEEN SHIFT ONE AND SHIFT TWO
Most-skipped step in frontline onboarding.

  [ ] Shift-two time confirmed before they leave
      on day one          owner: Shift Lead
  [ ] Day-7 check-in      owner: Site Manager""",
    "prompt": "Read this skill file and follow it. I need a day-one readiness checklist for a team member starting at our Dagenham store on 6 October. Offer was accepted on 14 September. Site managers do the onboarding.",
    "faqs": [
      ("Does it know the compliance requirements for my state or country?", "It knows roughly what category an item falls into and when to start it, not how to complete it correctly. For the US I-9 and E-Verify process specifically, use I-9 Readiness Checker — and read the caveat at the top of that page. Neither is legal advice."),
      ("We already have an onboarding checklist.", "Give it yours. It would rather refine what you have — and tell you which items are mis-sequenced or missing an owner — than hand you a replacement your team has to adopt."),
      ("Can it track completion?", "No. It builds the list; it can't see who's missing a document, nudge anyone, or tell you whether a start is at risk."),
    ],
    "related": ["no-show-pattern-finder", "i9-readiness-checker", "turnover-analyst"],
  },
  {
    "slug": "i9-readiness-checker",
    "name": "I-9 Readiness Checker",
    "cat": "Complying",
    "export": False,
    "title": "I-9 Readiness Checker — Claude skill for Form I-9 process prep",
    "meta": "A free Claude skill that maps your Form I-9 process, flags the errors that show up most in audits, and builds a manager-facing completion checklist. Not legal advice.",
    "h1": "Map your I-9 process and find where the errors come from",
    "lead": "High volume, distributed completion, untrained completers — that combination is where I-9 errors originate. This helps you build a process that produces fewer of them, and know where to look for the ones you already have.",
    "legal": "This is not legal advice. It helps you prepare — organise your process, build checklists, understand where things typically go wrong. It is not a compliance opinion and does not substitute for the official instructions or qualified counsel. Two limits matter especially: requirements change and this skill does not, so always work from the current form and handbook at uscis.gov/i-9 and e-verify.gov; and it cannot see your records and should not — never paste completed I-9s, document numbers or employee identifiers into a chat.",
    "does": [
      "The common failures are structural rather than individual. Section 2 completed outside the required window. Over-documentation — asking for more documents than required, or specifying which ones, which can constitute unlawful discrimination rather than merely being an error. Missed reverification dates. And the highest-yield one in a multi-site employer: the same error repeating at one site because one manager was taught wrong once, which is invisible in an aggregate error rate.",
      "For each error class it separates what has to be corrected on a record from what has to change in the process, because fixing three hundred forms and leaving the process alone means you'll fix three hundred more next year."
    ],
    "inputs": [
      ("How you do it now", "Paper or electronic, at site or centrally, who completes Section 2, E-Verify or not", "req"),
      ("Volume and pattern", "Steady, or seasonal spikes where hundreds start in a fortnight", "req"),
      ("Which states you operate in", "Some mandate E-Verify for some employers; some restrict verification practice", "rec"),
      ("What prompted this", "Audit prep, an inherited acquisition, or building new — three different jobs", "rec"),
      ("Aggregate counts only", "Completions by site, count outside the window — never individual records", "opt"),
    ],
    "method": [
      ("Map your process against where errors originate", "Section 1, Section 2, reverification and retention, and distribution. Each has its own characteristic failures and its own fix."),
      ("Separate record correction from process change", "And where a correction is needed, verify the current method against the official handbook — correction practice has specifics that matter and that change."),
      ("Design for your actual volume", "What works at twenty hires a month fails at four hundred. Where completion happens, who is authorised for Section 2, the timing trigger driven by actual start dates, and who trains the completers through fast manager turnover."),
      ("Plan for the spike", "Peak hiring is when error rates rise, because the same people complete far more forms under time pressure."),
      ("Map E-Verify, if you use it", "Enrolment, timing relative to the I-9, what a tentative non-confirmation requires, and the constraints on adverse action while a case is open."),
    ],
    "outputs": [
      "Process map with the error-prone points marked",
      "Error-class checklist, in likelihood order for an employer of your shape",
      "Structural fixes, distinguished from record corrections, each with an owner",
      "<strong>A one-page completion checklist for managers</strong> — usually the highest-value output, because most errors are made by someone who was never given one",
      "A self-audit plan, sampled rather than exhaustive, so it actually happens",
      "<strong>A verification list</strong> — everything you must confirm against the current official source before relying on it",
    ],
    "sample_title": "Manager completion checklist",
    "sample_note": "Excerpt. The full output includes the process map, error-class checklist, structural fixes, self-audit plan and the verification list.",
    "sample": """SECTION 2 — ONE PAGE FOR THE PERSON FILLING IT IN

  WHEN
  [ ] Complete within the required window after their
      first day of work. If the start date moved, the
      clock moved with it — check the actual first day.

  WHAT YOU LOOK AT
  [ ] The employee chooses which documents to show you.
      You do NOT ask for specific ones.
      You do NOT ask for more than required.
      → Asking for extra or specific documents is not
        just an error. It can be unlawful.
  [ ] Either ONE List A document,
      OR one List B AND one List C.
      Never a List A plus others.
  [ ] Documents must be unexpired and appear genuine
      and relate to the person in front of you.

  WHAT YOU WRITE
  [ ] Document title, issuing authority, number and
      expiry — exactly as printed
  [ ] The employee's first day of employment
  [ ] Your own name, title, signature and today's date
  [ ] Business name and address

  NEVER
  [ ] Never backdate anything
  [ ] Never erase or white out — corrections have a
      required method
  [ ] Never complete Section 2 for someone you did not
      personally examine documents for

  STUCK?
  Don't guess. Stop and contact [named owner].
  A blank field is easier to fix than a wrong one.


VERIFICATION LIST — confirm before you rely on this
  • Current form version and edition date
  • The Section 2 completion window as it stands now
  • Current Lists A/B/C acceptable documents
  • Retention periods and the clock for terminated staff
  • Remote/alternative examination eligibility
  • The required correction method
  • Any state-level requirement on top of the federal
  Source: uscis.gov/i-9 and the current M-274 handbook.""",
    "prompt": "Read this skill file and follow it. We hire about 400 people a month across 42 sites, site managers complete Section 2 on paper, we use E-Verify, and we're preparing for an internal audit.",
    "faqs": [
      ("Is this legal advice?", "No. It helps you organise your process and know where errors typically come from. It is not a compliance opinion and does not substitute for the official instructions or qualified counsel. An I-9 question with money or an active audit attached is a question for employment counsel — use this to arrive at that conversation organised."),
      ("Can I paste our completed I-9s in for checking?", "No, and the skill will refuse. Completed I-9s are sensitive records with their own storage and access requirements. Send aggregate counts if you want to look at completion status — completions by site, count completed outside the window — never individual records."),
      ("How current is the information?", "The skill is explicit that requirements change and it does not. Form versions, acceptable documents, retention periods and remote-examination provisions have all changed in recent years. It outputs a verification list precisely so you check the moving parts against the current official source rather than trusting it."),
      ("We're not in the US.", "Then this doesn't apply. Ask instead for the right-to-work process in your jurisdiction, and treat the answer with the same caution."),
    ],
    "related": ["day-one-readiness-checklist", "turnover-analyst", "screening-question-builder"],
  },
]

BY_SLUG = {s["slug"]: s for s in SKILLS}

# ----------------------------------------------------------------- template

SCRIPT = """<script>
document.querySelectorAll('[data-copy]').forEach(function (b) {
  b.addEventListener('click', function () {
    var t = document.getElementById('prompt-text');
    if (!t) return;
    var done = function () {
      b.textContent = 'Copied';
      setTimeout(function () { b.textContent = 'Copy'; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t.textContent).then(done, function () {
        b.textContent = 'Press Ctrl+C';
      });
    } else {
      var r = document.createRange();
      r.selectNodeContents(t);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(r);
      done();
    }
  });
});
</script>"""


def esc(t):
    return html.escape(t, quote=False)

def nav():
    return """<nav class="nav">
  <a class="nav__brand" href="/claude-skills"><span class="nav__mark" aria-hidden="true"></span><span class="nav__word">Fountain</span></a>
  <div class="nav__links">
    <a href="/claude-skills#install">How it works</a>
    <a href="/claude-skills#skills">All 40 skills</a>
    <a href="/claude-skills#data">Sample data</a>
    <a href="/claude-skills#cue">Cue</a>
  </div>
  <a class="fx-btn fx-btn--secondary fx-btn--sm" href="#" data-cta="demo">Book a demo</a>
</nav>"""

def inputs_table(rows):
    body = ""
    for col, why, kind in rows:
        tag = {"req": '<span class="chip chip--ready">required</span>',
               "rec": "", "opt": ""}.get(kind, "")
        label = f"<code>{esc(col)}</code>" if re.match(r"^[a-z_,\s]+$", col) else esc(col)
        body += f"    <tr><td>{label}</td><td>{esc(why)}</td><td>{tag}</td></tr>\n"
    return f"""<div class="tbl-wrap"><table>
  <thead><tr><th>Give it</th><th>What it unlocks</th><th></th></tr></thead>
  <tbody>
{body}  </tbody>
</table></div>"""

def cue_panel(s):
    return f"""<section class="fx-section">
  <div class="fx-container">
    <div class="panel">
      <p class="panel__eyebrow">Run It.</p>
      <h2 class="fx-h2">This reads an export. Cue reads the pipeline.</h2>
      <p>{esc(s['name'])} works from a file you produced by hand, so it sees one moment and changes nothing. Every recommendation it makes is yours to carry out, and you would export again to find out whether it worked.</p>
      <p>Cue is Fountain's Frontline Superintelligence — one agent that reads your live data and executes across the full Fountain suite, inside your own permissions and governance. You state the objective, Cue proposes a plan, you approve, Cue does the work and summarises what changed. Powered by Anthropic's Claude, the same models you just used here.</p>
      <div class="panel__actions">
        <a class="fx-btn fx-btn--inverse" href="#" data-cta="cue.demo">See Cue on your pipeline</a>
        <a class="fx-btn fx-btn--secondary" href="#" data-cta="cue.trial" style="background:transparent;color:#fff;border-color:rgba(255,255,255,.4)">Start with Cue credits</a>
      </div>
    </div>
  </div>
</section>"""

def jsonld(s):
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in s["faqs"]
        ],
    }
    art = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": s["h1"],
        "description": s["meta"],
        "url": f"{BASE}/{s['slug']}",
        "isPartOf": {"@type": "WebSite", "name": "Claude Skills for HR Ops", "url": BASE},
        "publisher": {"@type": "Organization", "name": "Fountain", "url": "https://www.fountain.com"},
        "license": "https://opensource.org/licenses/MIT",
        "about": {"@type": "Thing", "name": f"{s['cat']} — frontline HR operations"},
    }
    crumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Claude Skills for HR Ops", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": s["cat"], "item": f"{BASE}#skills"},
            {"@type": "ListItem", "position": 3, "name": s["name"], "item": f"{BASE}/{s['slug']}"},
        ],
    }
    out = ""
    for obj in (art, faq, crumb):
        out += '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>\n"
    return out

def page(s):
    chips = f'<span class="chip chip--cat">{esc(s["cat"])}</span><span class="chip chip--ready">available now</span>'
    if s["export"]:
        chips += '<span class="chip chip--export">works from your export</span>'

    does = "\n".join(f'      <p class="fx-body">{esc(p)}</p>' for p in s["does"])

    method = ""
    for i, (t, d) in enumerate(s["method"], 1):
        method += (f'        <div class="stp"><div class="stp__n">{i}</div>'
                   f'<div class="stp__t">{esc(t)}</div>'
                   f'<p class="stp__d">{esc(d)}</p></div>\n')

    outputs = "\n".join(f"        <li>{o}</li>" for o in s["outputs"])

    faqs = ""
    for q, a in s["faqs"]:
        faqs += f"      <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>\n"

    rel = ""
    for r in s["related"]:
        o = BY_SLUG.get(r)
        if not o:
            continue
        rel += (f'        <div class="rel__i"><div class="rel__n">'
                f'<a href="/claude-skills/{o["slug"]}">{esc(o["name"])}</a></div>'
                f'<p class="rel__d">{esc(o["cat"])}</p></div>\n')

    privacy = ""
    if s["export"]:
        privacy = f"""      <div class="callout">
        <h3 class="fx-h6">Before you paste anything</h3>
        <p>{esc(PRIVACY)}</p>
      </div>"""

    legal = ""
    if s.get("legal"):
        legal = f"""      <div class="callout callout--legal">
        <h3 class="fx-h6">Read this first</h3>
        <p>{esc(s['legal'])}</p>
      </div>"""

    cue = cue_panel(s) if s["export"] else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(s['title'])}</title>
<meta name="description" content="{html.escape(s['meta'])}">
<link rel="canonical" href="{BASE}/{s['slug']}">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(s['title'])}">
<meta property="og:description" content="{html.escape(s['meta'])}">
<meta property="og:url" content="{BASE}/{s['slug']}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
{jsonld(s)}<style>{CSS}</style>
</head>
<body>

{nav()}

<section class="fx-section" style="padding-bottom:var(--space-12)">
  <div class="fx-container">
    <nav class="crumb" aria-label="Breadcrumb">
      <a href="/claude-skills">Claude Skills for HR Ops</a>
      <span aria-hidden="true">/</span>
      <a href="/claude-skills#skills">{esc(s['cat'])}</a>
      <span aria-hidden="true">/</span>
      <span>{esc(s['name'])}</span>
    </nav>
    <div class="hero">
      <div class="hero__chips">{chips}</div>
      <p class="fx-eyebrow">{esc(s['name'])}</p>
      <h1 class="fx-h1">{esc(s['h1'])}</h1>
      <p class="fx-lead">{esc(s['lead'])}</p>
      <div class="hero__actions">
        <a class="fx-btn fx-btn--primary" href="{DOWNLOAD_BASE}/{s['slug']}.zip" data-cta="skill.download.{s['slug']}">
          Download {esc(s['name'])}
          <svg class="fx-btn__icon" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 2v8m0 0L4.5 6.5M8 10l3.5-3.5M2.5 12.5h11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </a>
        <a class="fx-btn fx-btn--secondary" href="/claude-skills" data-cta="skill.all">All 43 skills</a>
      </div>
    </div>
  </div>
</section>

<section class="fx-section" style="padding-top:0">
  <div class="fx-container">
    <div class="cols">
      <div class="main">

        <div class="block">
          <div class="block__h"><h2 class="fx-h2">What it does</h2></div>
{does}
        </div>

        <div class="block">
          <div class="block__h">
            <h2 class="fx-h2">What you give it</h2>
            <p class="fx-body">If you don't have some of these, it works with what you have and tells you which findings it could not reach. It will not fill a gap with an assumption.</p>
          </div>
          {inputs_table(s['inputs'])}
        </div>

        <div class="block">
          <div class="block__h"><h2 class="fx-h2">What it gives you back</h2></div>
          <ul class="bare">
{outputs}
          </ul>
          <div class="sample">
            <div class="sample__bar"><span>{esc(s['sample_title'])}</span><span>sample output</span></div>
            <pre class="sample__body">{esc(s['sample'])}</pre>
            <p class="sample__note">{esc(s['sample_note'])}</p>
          </div>
        </div>

        <div class="block">
          <div class="block__h">
            <h2 class="fx-h2">How it works</h2>
            <p class="fx-body">The method is written into the file so you can challenge it rather than take the output on trust.</p>
          </div>
          <div class="steps">
{method}          </div>
        </div>

{legal}
{privacy}

        <div class="block">
          <div class="block__h"><h2 class="fx-h2">Use it in three steps</h2></div>
          <div class="steps">
            <div class="stp"><div class="stp__n">1</div><div class="stp__t">Download the skill</div><p class="stp__d">One <code>.zip</code>. No terminal, no <code>npx</code>, nothing to build.</p></div>
            <div class="stp"><div class="stp__n">2</div><div class="stp__t">Add it in Claude</div><p class="stp__d">Settings, then Customize, then Skills, then <code>+</code> and upload the file. Works on the free plan. Team owners can add it for everyone at once.</p></div>
            <div class="stp"><div class="stp__n">3</div><div class="stp__t">Send this</div><p class="stp__d">Then add your own detail. The more specific you are about your operation, the better the output.</p></div>
          </div>
          <div class="prompt">
            <button class="copy" type="button" data-copy>Copy</button>
            <code id="prompt-text">{esc(s['prompt'])}</code>
          </div>
        </div>

        <div class="block">
          <div class="block__h"><h2 class="fx-h2">Questions</h2></div>
          <div class="faq">
{faqs}          </div>
        </div>

      </div>

      <aside class="aside">
        <div class="fx-card fx-card--muted">
          <h2 class="fx-h6" style="margin-bottom:var(--space-4)">At a glance</h2>
          <div class="meta">
            <div class="meta__row"><span class="meta__k">Category</span><span class="meta__v">{esc(s['cat'])}</span></div>
            <div class="meta__row"><span class="meta__k">Needs your data</span><span class="meta__v">{'Yes — a CSV export' if s['export'] else 'No'}</span></div>
            <div class="meta__row"><span class="meta__k">Claude plan</span><span class="meta__v">Any, including free</span></div>
            <div class="meta__row"><span class="meta__k">Setup</span><span class="meta__v">None</span></div>
            <div class="meta__row"><span class="meta__k">Licence</span><span class="meta__v">MIT</span></div>
            <div class="meta__row"><span class="meta__k">File</span><span class="meta__v">{s['slug']}.zip</span></div>
          </div>
        </div>

        {'<div class="fx-card"><h2 class="fx-h6" style="margin-bottom:var(--space-3)">Try it without your own data</h2><p class="fx-small" style="font-size:var(--text-m);color:var(--neutral-600);margin-bottom:var(--space-5)">18,184 synthetic applications across 42 locations. No real people in it, and real problems built in — including two deliberate confounds.</p><a class="fx-btn fx-btn--secondary fx-btn--sm" href="/data/frontline_pipeline_sample.csv" data-cta="skill.sample-data">Get the sample data</a></div>' if s['export'] else ''}

        <div class="fx-card">
          <h2 class="fx-h6" style="margin-bottom:var(--space-3)">Related skills</h2>
          <div class="rel">
{rel}          </div>
        </div>
      </aside>
    </div>
  </div>
</section>

{cue}

<section class="fx-section fx-section--sky">
  <div class="fx-container" style="text-align:center;display:grid;gap:var(--space-6);justify-items:center">
    <h2 class="fx-h2" style="max-width:24ch">Take the whole library. It's free.</h2>
    <p class="fx-lead" style="max-width:56ch">Nine skills available today, forty by the end of October. MIT licensed, issues open.</p>
    <div style="display:flex;flex-wrap:wrap;gap:var(--space-3);justify-content:center">
      <a class="fx-btn fx-btn--primary" href="/claude-skills" data-cta="skills.all-footer">Browse all 40 skills</a>
      <a class="fx-btn fx-btn--secondary" href="{REPO}" data-cta="skills.github">View on GitHub</a>
    </div>
  </div>
</section>

<footer class="foot">
  <div class="foot__in">
    <div style="display:grid;gap:var(--space-3);max-width:44ch">
      <a class="nav__brand" href="/claude-skills"><span class="nav__mark" aria-hidden="true"></span><span class="nav__word">Fountain</span></a>
      <p class="fx-small">The AI-native platform for the global frontline workforce. Built for retail, QSR, logistics and staffing.</p>
    </div>
    <div class="foot__links">
      <a href="/claude-skills#skills">All 40 skills</a>
      <a href="/claude-skills#install">How it works</a>
      <a href="/claude-skills#data">Sample data</a>
      <a href="/claude-skills#cue">Cue</a>
      <a href="{REPO}">GitHub</a>
      <a href="#">Book a demo</a>
    </div>
  </div>
  <div class="foot__in" style="margin-top:var(--space-10);padding-top:var(--space-6);border-top:1px solid var(--neutral-200)">
    <p class="fx-small">Skills are MIT licensed. Nothing on this page is legal advice — the compliance skills help you prepare, and say so.</p>
    <p class="fx-small">© 2026 Fountain</p>
  </div>
</footer>

{SCRIPT}
</body>
</html>
"""

# ----------------------------------------------------------------- sitemap

def sitemap():
    urls = "".join(
        f"  <url><loc>{BASE}/{s['slug']}</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>\n"
        for s in SKILLS
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'  <url><loc>{BASE}</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
            f'{urls}</urlset>\n')

# ----------------------------------------------------------------- run

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in SKILLS:
        p = os.path.join(OUT, s["slug"] + ".html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(page(s))
        print(f"{s['slug']+'.html':44s} {os.path.getsize(p)//1024:4d} KB")
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap())
    print(f"\n{len(SKILLS)} pages + sitemap.xml -> {OUT}")
