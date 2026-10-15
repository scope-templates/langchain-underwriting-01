# Ketterly underwriting desk

Ketterly Underwriting is a managing general underwriter in Marquand Bluff, Iowa, about forty-five people. We write
commercial package policies (general liability and property, with liquor liability for the places that pour) for
independent restaurants, bars, caterers and small food producers in eight Midwest states, on paper from Callander
Indemnity Company and Coteau Casualty Company, through about 120 independent insurance brokerages. This is our
underwriting desk. It keeps every submission a brokerage sends us, with its inspection reports and broker calls, the
facts we have checked about the business, our notes and each quote, referral, decline and bind, along with the
policies we have written and their claims. Five underwriters and two senior underwriters work submissions from it,
broker relations and claims staff read it, and its assistant answers questions about one submission from the desk's
own records.

## What is in it

FastAPI over one SQLite file (`desk.db`, created on first start and loaded from `data/seed.json` when empty).

| Table | Holds |
| --- | --- |
| `staff` | name, email, role |
| `sessions` | hashed bearer token, staff member, created at |
| `brokerages` | name, city, state, appointed on, status (`active`, `inactive`) |
| `submissions` | business, DBA, state, address, class of business, requested limits, total insured value, brokerage, broker contact, received on, who entered it, the policy it renews, status, decided by, decided on, annual premium, deductible, terms |
| `inspections_and_calls` | kind (`inspection` or `broker_call`), with whom, held on, recorded by, findings as typed |
| `facts` | field, value, `checked_on`, `checked_by`, `note` |
| `notes` | author, written at, body |
| `decisions` | append-only: actor, submission, action (`quote`, `decline`, `confirm`, `bind`, `not_taken`), premium, deductible, terms, at |
| `activity` | append-only: actor, action, the submission, policy, claim or brokerage it is about, detail, at. Actions: `save_note`, `scope_refused`, `tool_refused` and `tool_failed` from the assistant; `policy_started`, `policy_ended`, `policy_cancelled`, `claim_closed` and `brokerage_status` from the book |
| `policies` | insured, state, carrier, brokerage, effective, expires, annual premium, limits, status (`pending`, `in_force`, `expired`, `cancelled`, `non_renewed`), cancelled on, the prior term it renews, the submission that bound it |
| `claims` | policy, date of loss, reported on, kind (`slip_and_fall`, `kitchen_fire`, `liquor_liability`, `spoilage`, `theft`), paid, reserve, status (`open`, `closed`) |

An underwriter types each fact in after checking it, with the date it was checked and a note on how they know. Fact
fields are `years_in_business`, `owner`, `locations`, `headcount`, `operations`, `building`, `parent_company` and
`recent_change`.

| Route | Does | Refuses |
| --- | --- | --- |
| `POST /session` | issues a bearer token to a staff email; a token works for 30 days | an email not in `staff` (401) |
| `DELETE /session` | signs out: the bearer token stops working (204) | a token with no session (401) |
| `GET /submissions` | lists submissions, `?status=` filters | no token (401), an unknown status (422) |
| `POST /submissions` | records a submission, entered by the signed-in person; `renewal_of` links the expiring policy | viewers (403); a state the desk does not write, a future `received_on` (422); an unknown or inactive brokerage (422 `unknown_brokerage`, `brokerage_inactive`); a `renewal_of` that is unknown or not in force (422 `unknown_policy`, `policy_not_in_force`), whose term ended with no renewal term (409 `policy_lapsed`: it comes in as new business), or that already has a renewal open or bound (409 `renewal_open`, `renewal_bound`) |
| `GET /submissions/{id}` | the submission, its brokerage, notes, decision entries and the policy a bind opened; for underwriters and seniors also its inspections and calls and its facts | unknown id (404) |
| `POST /submissions/{id}/inspections` | records an inspection report or a broker call, recorded by the signed-in person | viewers, a future `held_on`, another `kind` |
| `POST /submissions/{id}/facts` | records a fact, checked by the signed-in person | viewers, a missing or future `checked_on`, an unknown field |
| `POST /submissions/{id}/notes` | adds a note, written by the signed-in person | viewers |
| `POST /submissions/{id}/decide` | `quote`, `decline`, `confirm`, `bind` or `not_taken`, as below | viewers; a field the action does not use (422 `field_not_used`) |
| `GET /brokerages` | lists brokerages, `?status=` filters | no token, an unknown status |
| `POST /brokerages/{id}/status` | sets a brokerage `active` or `inactive`, with a `brokerage_status` entry in `activity` | anyone but a senior (403), the status it already has (409 `status_unchanged`) |
| `GET /policies` | lists policies, `?status=` filters | no token, an unknown status |
| `GET /policies/{id}/losses` | the policy and each earlier term it renews, newest first, each with its claims, and paid and reserve totals | unknown id (404) |
| `POST /policies/{id}/cancel` | cancels a policy as of `cancelled_on`, with the `reason` in a `policy_cancelled` entry; a pending policy is cancelled flat, as of its effective date | anyone but a senior (403); a policy that is neither pending nor in force (409); for a pending policy any other date (422 `flat_cancellation_only`); for one in force a date after today (422 `future_date`), outside the term (422 `outside_term`), or on or before a claim's date of loss (422 `loss_on_or_after_cancellation`) |
| `POST /claims/{id}/close` | closes an open claim with the amount `paid`, sets its reserve to 0, with a `claim_closed` entry | anyone but a senior (403); a closed claim (409 `claim_closed`); less paid than already recorded (422 `paid_lowered`) |
| `POST /assistant/submissions/{id}` | body `{"question": ...}`, answers `{"answer", "tool_calls"}` | viewers (403), unknown id (404), `OPENAI_API_KEY` unset or a placeholder (503 `assistant_unconfigured`), a failed or empty model answer (502 `model_call_failed`) |

A policy's status follows its dates. A policy bound to take effect later is `pending` until its effective date and
`in_force` from then until its `expires` date, whether or not its renewal has been bound, declined or let go. On that
date its term ends: `non_renewed` when its renewal was declined or not taken and no renewal term follows, `expired`
otherwise. Before the desk lists policies, shows losses, records a submission that renews a policy, decides a
submission, cancels a policy or answers an assistant question, it moves every policy whose date has come, each with
a `policy_started` or `policy_ended` entry in `activity` naming the signed-in person.

Deciding a submission:

- `quote` takes an open submission with an annual `premium` and a `deductible` in dollars (422 `quote_incomplete`
  without them) and optional `terms`. It becomes `quoted` when the premium is $20,000 or less and the total insured
  value $5,000,000 or less, and `referred` when either is above.
- `confirm` moves a `referred` submission to `quoted`. Only a senior underwriter confirms (403 `role_refused`), never
  the one who wrote the quote (403 `senior_is_quoter`), and confirming keeps the quoted premium, deductible and terms
  (422 `confirm_changes_quote`).
- `decline` closes an open or referred submission.
- `bind` records that the brokerage accepted a quoted submission and opens a one-year policy at the quoted premium
  with the requested limits, `pending` until its effective date. New business needs an `effective` date from today to
  90 days out and a `carrier` (422 `bind_incomplete`, `effective_out_of_range`). A renewal takes effect the day the
  expiring policy ends (422 `renewal_effective_fixed` for another date), keeps that policy's carrier unless one is
  given, and binds only while that policy is in force (409 `policy_lapsed` once its term has ended,
  `policy_not_in_force` otherwise).
- `not_taken` records that the brokerage let a quoted submission go.
- An action the submission's status does not allow is 409 (`submission_decided`, `not_referred`, `not_quoted`). Two
  decisions sent at the same time from the same status cannot both land: the second gets 409 `status_changed`.

Every text field is trimmed and refused when blank; ids, premiums, deductibles, insured values and paid amounts have
bounds, and money fields take whole numbers only (not `true`, `"5000"` or `5000.0`). Dates before 1990 are refused.
A role that cannot use a route gets 403 whatever the request body holds. Errors come back as
`application/problem+json` with `type`, `title`, `status`, `code` and `detail`, including unexpected failures (500
`internal_error`).

The store enforces these rules underneath the routes, with CHECK constraints, triggers and unique indexes:

- every date column holds an ISO date (and every timestamp an ISO date and time) between 1990 and 2040;
- a fact needs `checked_on` and `checked_by`, a note its author, an inspection or call its recorder, a submission the
  person who entered it, a decision and an activity entry their actor (NOT NULL). That each of these is a row in
  `staff` is a foreign key, which SQLite checks only on connections with `PRAGMA foreign_keys = ON`;
  `app.db.connect` turns it on for every connection the app opens;
- a decision entry's actor is an underwriter or a senior, and a `confirm` comes from a senior who did not write the
  quote; a `quote` entry carries a premium and a deductible;
- a decision entry matches the submission's status when it is written: `quote` only while open, `decline` while open
  or referred, `confirm` only while referred, `bind` and `not_taken` only while quoted;
- `decisions` and `activity` entries cannot be updated, deleted or replaced; `inspections_and_calls`, `facts` and
  `notes` rows cannot be updated or deleted; no row of `brokerages`, `policies`, `submissions` or `claims` can be
  replaced by an insert over its id; each activity entry names exactly the kind of subject its action is about;
- a submission is inserted open and undecided, from an active brokerage, and keeps its total insured value and its
  renewal link; once bound, declined or not taken it keeps its business, DBA, state, address, class, limits,
  brokerage, broker contact, receipt date and enterer;
- a policy has at most one open renewal (open, referred or quoted) and at most one renewal term;
- a submission's status changes only with a matching entry as its most recent decision: `quote` takes an open
  submission to `quoted` (premium up to $20,000 and insured value up to $5,000,000) or `referred` (either above),
  only `confirm` moves `referred` to `quoted`, `decline` closes an open or referred one, and `bind` and `not_taken`
  close a quoted one;
- while a submission is open or referred, its premium, deductible, terms, decider and decision date change only with
  a matching `quote` or `decline` entry; once it is quoted, declined, bound or not taken they do not change;
- a policy expires after it takes effect, keeps its terms once written, and a renewal term starts the day its prior
  term expires; its status moves only forward and only with its entry in `activity`: `pending` to `in_force` after a
  `policy_started` entry dated on or after its effective date; `in_force` to `non_renewed` (its renewal declined or
  not taken, and no renewal term) or else `expired` after a `policy_ended` entry dated on or after its expiry;
  `pending` or `in_force` to `cancelled` after a `policy_cancelled` entry, a pending policy only as of its effective
  date; a cancellation date is set once, inside the term and after every claim's date of loss;
- a claim's date of loss falls inside its policy's term (and before a cancellation), it is reported on or after the
  loss, and a closed claim holds no reserve; a claim moves only forward (open to closed, its paid amount never
  lowered, its policy, dates and kind never changed) and is never deleted;
- a brokerage's status changes only with a matching `brokerage_status` entry as its most recent activity.

The schema carries its version in `PRAGMA user_version`. `app.db.MIGRATIONS` lists the desk's schema changes in the
order they were made (the underwriting desk, the assistant's activity log, then policy terms that follow the calendar,
cancellations, claim closing and brokerage status, which rebuilds `policies` to add `pending`); `app.db.init_db`
applies, each in its own transaction, the ones past a file's version, with foreign keys checked once they are all in.

## The assistant

`app/assistant/model.py` builds a `ChatOpenAI` model from `OPENAI_API_KEY`. `app/assistant/loop.py` runs the
tool-calling loop. A question gets at most six model calls: the first five go to `model.bind_tools(TOOLS)`, and if
the loop reaches a sixth it goes to `model.bind_tools(TOOLS, tool_choice="none")`, so it answers in text. A question
may make at most 12 tool calls and save at most one note. It has 90 seconds in all, counted from when the loop starts
and including the time its tool calls take: each model call waits at most 30 seconds or the time left, whichever is
less, a failed call is tried once more only while time is left, and no model call starts once the time is up. A tool
call whose arguments cannot be read gets an error result, as does one whose tool fails, and the loop carries on.
The answer comes back with the list of tool calls that returned a result, name and arguments; refused and failed
calls are recorded in `activity` instead.

| Tool | Reads or writes | Scope |
| --- | --- | --- |
| `submission_summary` | reads the submission, its brokerage, who entered and decided it, its notes and its decision entries | the submission in the path |
| `inspections` | reads the inspection reports and broker calls, findings as typed | the submission in the path |
| `facts` | reads the fact rows with `checked_on`, `checked_by` and `note` | the submission in the path |
| `loss_history` | for a renewal, reads the expiring policy and each earlier term it renews, with their claims | the policy the submission in the path renews |
| `save_note` | writes a note of up to 2,000 characters with the signed-in person as author, stamped when it is written, and records it in `activity` | the submission in the path |

The tools run on the submission id from the request path. A call that leaves `submission_id` out reads the
submission in the path; one that names a different submission (anything but that number or a string of its ASCII
digits) is refused and recorded in `activity` as `scope_refused`. A call to an unknown tool, a second `save_note` and
a call past the twelve are refused and recorded as `tool_refused`, and a call whose tool fails is recorded as
`tool_failed` with the tool's name. The assistant does not quote, bind or write a premium; those go through the
decide route.

## Roles

| Role | Can |
| --- | --- |
| `underwriter` | read everything, enter submissions, record inspections, calls, facts and notes, quote, decline, bind, mark not taken, ask the assistant |
| `senior` | everything an underwriter can, confirm a referred quote someone else wrote, cancel a policy, close a claim, and set a brokerage active or inactive |
| `viewer` | read submissions without their inspections, calls or facts, read brokerages, policies and losses |

Seeded staff: Margit Olafsen and Calvin Ruehl (seniors), Priya Ramaswamy, Jonah Feldkamp, Lucia Brandvold, Terrence
Okafor and Sabine Mulvaney (underwriters), Gretchen Hasselbring and Ruthann Bisbee in broker relations and Omar
Keddie and Lorna Fitzhugh in claims (viewers). Emails are `first.last@ketterlyuw.com`.

## Running locally

Python 3.12.

```sh
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app               # listens on 127.0.0.1:$PORT, default 8000
```

Settings, listed in `.env.example`:

- `OPENAI_API_KEY`: the key for the assistant's model. Without it, or with a placeholder such as `changeme` or
  `<your key>`, the assistant route answers 503 `assistant_unconfigured` and every other route works.
- `PORT`: the port `python -m app` listens on. If another process holds it, `python -m app` says so and exits.

The app reads them from the process environment and from no file, so export them in the shell that starts it.

```sh
curl -s -X POST localhost:8000/session -H 'content-type: application/json' \
  -d '{"email": "priya.ramaswamy@ketterlyuw.com"}'
curl -s localhost:8000/submissions?status=open -H "authorization: Bearer <token>"
```

## Tests

```sh
python -m pytest
```

The tests use FastAPI's `TestClient`, a fixed clock and scripted models in `tests/fake_model.py`, one of them the
OpenAI chat model with each request built and recorded instead of sent; they need no key and make no network calls.
Each test runs on its own copy of the seeded store.

## The data

`data/seed.json` holds eleven staff, 120 brokerages (112 active, 8 inactive), and 290 policies with effective dates
from October 2022 to November 2026, with statuses as of the morning of October 1, 2026: 4 pending, 63 in force, 180
expired, 25 non-renewed and 18 cancelled. A renewal's loss history reaches back up to two terms before the expiring
one. 62 of the policies carry claims, 66 in all (35 slips and falls, 13 spoilage, 8 kitchen fires, 6 liquor
liability, 4 thefts), 30 of them open. It also holds 203 submissions received from October 2025 through September
2026 from 67 of the brokerages, 44 of them renewals: 61 bound, 64 declined, 62 not taken, 6 quoted, 1 referred and 9
open. The submissions still quoted came in since mid-August, and the open and referred ones during September. With
them are 107 inspection reports, 254 broker calls, 691 fact rows with `checked_on` dates from June 2025 to September
2026, 430 notes, 331 decision entries and 93 activity entries from the book since the log began in April 2026 (34
terms started, 44 ended, 2 cancellations and 13 claim closings). Calls, inspections, checks, notes, decisions,
activity entries, claim reports and brokerage appointments fall on weekdays. No two businesses share a legal name,
its initials or a DBA.

On load the rows are inserted and the decision entries are replayed in order through `app.decisions.record`, the
step the decide route uses to write an entry and move the submission's status; the policies those binds opened,
every policy's status as of October 1 and the activity entries for the book are already in the seed. The
file is written by `python scripts/make_seed.py`, which gives the same bytes on every run; a test checks the
committed file against it. Delete `desk.db` to load the seed again.
