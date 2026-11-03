# Proposed free Vue session investigation — 3 Nov

**Not approved. Report only; no implementation or production action.**

The approved 3 Nov pass returned 49 Vue showings for 3 Nov, then HTTP 401 for 4 Nov.
The same 4 Nov date failed in the separately approved 2 Nov experiment. This disproves
neither all future access nor all current-day access, but it does not establish the
accepted rolling today/tomorrow window. No further Vue request followed the refusal.

## Recommendation and reason

Test whether an ordinary anonymous visit to the public programme page is a prerequisite
for the previously refused date request. This is a hypothesis, not an identified cause or
a promised repair. The current collector calls the programme API without first visiting
Vue's public page. The website may provide ordinary anonymous session state or embedded
programme data; the existing evidence does not establish either explanation.

Do not change to today-only: the current successful date was already successful yesterday,
so rolling one-day feasibility is also unproved. Do not accept a failed prefix, change the
all-nine gate, reduce to eight venues, relax mappings/categories or build a browser service.
Those would change the approved contract before establishing the cause.

## Exact proposed request scope

At most **two GETs total**, in this order, in one ordinary anonymous HTTP session:

1. `https://www.myvue.com/cinema/glasgow-st-enoch/whats-on`
2. Only if the page is an ordinary successful public response, the previously observed
   programme URL for 4 Nov:
   `https://www.myvue.com/api/microservice/showings/cinemas/10097/films?showingDate=2026-11-04T00:00:00&minEmbargoLevel=3&includesSession=true&includeSessionAttributes=true`

Use the existing identifying User-Agent/ordinary Accept headers. Ordinary cookies set by
the public page may remain in that session's memory; do not save cookie values or headers.
No login, copied cookies, private token, challenge solving, browser/stealth, alternate host,
redirect following or guessed endpoints. No extra script/data/metadata request. If the
page itself includes sufficient dated programme data, inspect it without another request.
Stop on any refusal/challenge/non-200; no automatic retry or alternate request follows.
This would be a newly approved experiment after the completed refusal, not a retry allowed
by the previous 62-request pass. Run only on 3 Nov London date; later execution needs a
restated date scope so a date change is not mistaken for a session effect.

Limits: 45 seconds total, 15 seconds/request, 2 MiB/response, 4 MiB combined; one request
in flight and at least one second between request starts. Public Vue host only, no TMDB.
Source fees £0; existing compute/network use unpriced. No database or application write,
new credentials, hosting/service/schedule changes, code implementation or other sitting.

## Evidence and next stop

Save sanitised status/timing/body hashes, presence of ordinary session state (never values),
and only bounded programme/identity facts needed for feasibility. A different response is
not by itself proof of the session cause: note the changed time/context and remaining
alternatives. Do not infer recurring access or a complete horizon from one success.

After the report, stop for a concrete revised source/build contract if the findings change
scope. Fresh all-nine acceptance, selected mappings, exact configuration/deployment/import/
nine-row enable remain separate owner stops. New-release/Older classification remains
unproved independently; do not spend more TMDB calls or approve mappings under this plan.
AB7, AA10c and every other sitting remain unstarted.
