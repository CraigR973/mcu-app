# AC5 — Cinema trips: owner checkpoint

Drafted 7 Nov, 00:30 GMT, for Group AC sitting 4 (#335's go covers the sitting; this checkpoint
still stops it). **Answered 7 Nov: "Approve all 8" (#345).** The text below is the proposal he
approved, unchanged; it is the build's contract. Main was green before the sitting (CI
42280363025, 6 Nov). The build's own record is **#346**.

What AC5 asks for (`docs/phase-batches.md`, AC5): a trip holds its proposer, the chosen showing
kept as a snapshot, invitees from any active profile in any number, and one reply per invitee:
Invited, Going, Not going or Another time. Everyone on a trip sees everyone's reply. The proposer
can accept a suggested time (the trip moves, the other replies reset to Invited, everyone is told)
and can cancel. A showing the source withdraws or cancels is flagged on the trip. Five pushes under
the Movie night switch, through the outbox. No guests, and no reply link that works without
sign-in (#335).

Live facts used below (read-only, 7 Nov, through `mcu_readonly`): 2 active profiles; all nine
venues enabled; the stored programme holds 2,518 confirmed and 15 unconfirmed showings and **no
withdrawn or cancelled ones**, so the withdrawn flag can be proved only in tests until a cinema
withdraws something. The worked example is real: Wild Horse Nine (TMDB 891621) at ODEON Glasgow
Quay on Mon 9 Nov at 20:10, and at Cineworld Glasgow Silverburn on Tue 10 Nov at 20:00.

---

## Decisions for Craig

1. **The two tables in §1, as written.** Recommended. Cost: migration 072, additive; its downgrade
   refuses while any trip exists, as 071's does for cinema data.
2. **The reminder goes out on the morning of the showing**, in the existing 08:00 UTC pass (08:00
   GMT, 09:00 BST). Recommended: no hosting change. Cost: no reminder for a trip made or moved to
   the same day after 08:00; and if your quiet hours or digest mode would hold it, the next pass is
   the following morning, after the film, so it is recorded as not sent ("it would have arrived
   after the showing") rather than arriving late. *Rejected:* a fixed lead such as three hours
   before. It needs a delivery pass every 15 to 30 minutes, which is a new Railway cron service: a
   hosting change that is yours to apply, with a usage cost not measured.
3. **A reply pushes only the proposer.** Recommended: with more people, every reply would buzz
   every phone on the trip; everyone still sees every reply on the trip. Cost: an invitee learns of
   another invitee's reply only by opening the trip. Alternative: everyone on the trip.
4. **The proposer can also move the trip to a time of their own, and invite more people later.**
   Recommended: when a cinema withdraws the time, the proposer otherwise has to wait for an invitee
   to suggest one. A move by the proposer is the same transition as accepting a suggestion
   (everyone back to Invited, everyone told). Cost: two more controls and tests. Removing an
   invitee stays out (they can say Not going).
5. **The proposer can turn down a suggestion ("Keep this time").** Recommended: otherwise the
   suggestion sits in their Needs you until the film. The suggester goes back to Invited and is told
   (a sixth push wording, below). Cost: one push beyond AC5's five.
6. **After an accepted suggestion, its suggester is Going** (they picked the time); everyone else
   resets to Invited. Recommended. Alternative: the suggester resets to Invited too and is asked
   again.
7. **Needs you also tells the proposer** about a suggestion waiting for them and about a showing
   the cinema no longer lists; and **Home's top slot shows your next trip** when it is sooner than
   your next planned movie night. Recommended: both are things only that person can act on, from
   the read Home already makes. Cost: two more Needs you items and one additive field; AC5 names
   only "awaiting this person's reply".
8. **The push wording in §5 and the switch's new description.** Approve, or edit any line.

---

## 1. The two tables (migration 072)

All timestamps are naive UTC (`DateTime(timezone=False)`) with `UTC_NOW` defaults, as every
table here. `created_at`/`updated_at` come from the house mixin.

### `cinema_trips` — one row per trip

| Column | Type | Null | Default | Holds |
|---|---|---|---|---|
| `id` | uuid | no | | primary key |
| `client_request_id` | uuid | no | | the app's id for this send; a retried send returns the same trip |
| `proposer_id` | uuid | no | | FK `profiles.id`, on delete cascade |
| `film_key` | varchar(80) | no | | AC4's film address when proposed: `tmdb-<id>`, `listing-<uuid>`, `movie-<uuid>` or `imdb-tt…` |
| `film_title` | varchar(500) | no | | snapshot |
| `poster_path` | varchar(255) | yes | | snapshot (TMDB path) |
| `showing_id` | uuid | yes | | FK `cinema_screenings.id`, **on delete set null**: the live row, for the flag and the ticket rule |
| `venue_id` | uuid | yes | | FK `cinema_venues.id`, on delete set null |
| `venue_name` | varchar(200) | no | | snapshot |
| `venue_timezone` | varchar(50) | no | `Europe/London` | snapshot; times are shown in the cinema's time |
| `starts_utc` | timestamp | no | | snapshot |
| `ends_utc` | timestamp | yes | | snapshot |
| `screen` | varchar(200) | yes | | snapshot |
| `formats` | jsonb | no | `[]` | snapshot, e.g. `["IMAX"]` |
| `booking_url` | varchar(2048) | yes | | snapshot, history only (see §3) |
| `revision` | integer | no | `1` | +1 each time the trip moves |
| `moved_at_utc` | timestamp | yes | | the last move |
| `cancelled_at_utc` | timestamp | yes | | set once, by the proposer |
| `created_at`, `updated_at` | timestamp | no | `UTC_NOW` | |

Constraints:
- `uq_cinema_trip_request` unique (`proposer_id`, `client_request_id`).
- `ck_cinema_trip_film_key`: `film_key` matches AC4's address pattern exactly.
- `ck_cinema_trip_revision`: `revision >= 1`; `ck_cinema_trip_moved`: `moved_at_utc` is null
  exactly when `revision = 1`.
- `ck_cinema_trip_ends`: `ends_utc` is null or after `starts_utc`.
- `ck_cinema_trip_formats`: `formats` is a JSON array.

Indexes: `ix_cinema_trips_proposer` (`proposer_id`); `ix_cinema_trips_upcoming` (`starts_utc`)
where `cancelled_at_utc` is null, for lists and the reminder pass; `ix_cinema_trips_film`
(`film_key`); `ix_cinema_trips_showing` (`showing_id`), so the programme's 30-day clean-up, which
deletes up to 500 showings at a time, does not scan trips to null their link.

### `cinema_trip_invitees` — one row per invitee, holding their one reply

| Column | Type | Null | Default | Holds |
|---|---|---|---|---|
| `id` | uuid | no | | primary key |
| `trip_id` | uuid | no | | FK `cinema_trips.id`, on delete cascade |
| `profile_id` | uuid | no | | FK `profiles.id`, on delete cascade |
| `reply` | varchar(20) | no | `invited` | `invited`, `going`, `not_going` or `another_time` |
| `reply_revision` | integer | no | `0` | +1 on every change to this reply, a reset included |
| `replied_at_utc` | timestamp | yes | | when the current reply was given; null while Invited |
| `suggested_showing_id` | uuid | yes | | FK `cinema_screenings.id`, on delete set null |
| `suggested_venue_name` | varchar(200) | yes | | snapshot of the suggested time |
| `suggested_starts_utc` | timestamp | yes | | snapshot |
| `suggested_formats` | jsonb | yes | | snapshot |
| `created_at`, `updated_at` | timestamp | no | `UTC_NOW` | `created_at` is when they were invited |

Constraints:
- `uq_cinema_trip_invitee` unique (`trip_id`, `profile_id`).
- `ck_cinema_trip_reply`: `reply` in the four values.
- `ck_cinema_trip_reply_revision`: `reply_revision >= 0`.
- `ck_cinema_trip_replied`: `replied_at_utc` is null exactly when `reply = 'invited'`.
- `ck_cinema_trip_suggestion`: the suggested start and cinema name are present exactly when
  `reply = 'another_time'`, together; `suggested_formats` is null or a JSON array. The suggested
  showing's id is left out of the check, because the clean-up may null it.

Indexes: `ix_cinema_trip_invitees_profile` (`profile_id`, `reply`), for "my trips" and "awaiting
my reply"; `ix_cinema_trip_invitees_suggested` (`suggested_showing_id`) where it is not null. The
unique key covers lookups by trip.

**The proposer is not an invitee row.** They are `cinema_trips.proposer_id` and always count as
going; to drop out they cancel. A database check cannot see across the two tables, so the API
refuses the proposer as an invitee and a test pins it.

### Grants, upgrade and downgrade

Both tables go to both roles in one guarded block, as 070 and 071 do, so CI's database (which has
neither role) still migrates:

```sql
DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='<role>') THEN
GRANT SELECT ON cinema_trips, cinema_trip_invitees TO <role>; END IF; END $$
```

run once for `mcu_readonly` and once for `mcu_backup`. **Neither table holds a credential**:
there is no token, because no reply link works without sign-in. So nothing goes in
`CREDENTIAL_TABLES` or `CREDENTIAL_COLUMNS`, and the weekly backup copies both tables whole. The
read-only role will see who is invited to what, as it already sees movie nights and loans.

Downgrade refuses while either table holds a row ("Cinema trips exist; downgrade 072 requires
owner review"), then drops invitees and trips. CI's `upgrade head` → `downgrade base` runs on an
empty database, so reversal is proved there. After deploy, the live proof is four
`has_table_privilege(…, 'SELECT')` answers, both roles on both tables, read through `live_sql`.

---

## 2. States and transitions

**A trip is Upcoming, Cancelled or Past.** Cancelled is `cancelled_at_utc` set. Past is derived:
the showing has started. Nothing writes "past", so no job is needed. Cancelled and Past trips are
frozen: no reply, move or invitation changes.

**A reply is one of four:** Invited (shown as "No reply yet"), Going, Not going, Another time
(a different showing of the same film, at any of the nine).

```
Invited ──► Going ◄──► Not going ◄──► Another time
              any reply can change to any other,
              until the showing starts

The trip moves ──► everyone back to Invited,
                   except an accepted suggester ──► Going
```

| Who | Action | Allowed when | Effect | Push |
|---|---|---|---|---|
| Proposer | Propose | showing confirmed and still to start; at least one active profile picked | trip + one Invited row each | Invitation, to each invitee |
| Invitee | Reply Going / Not going | trip upcoming, request names the trip's current revision | their reply; suggestion cleared | Reply, to the proposer |
| Invitee | Another time | as above; a confirmed, still-to-start showing of this film that is not the trip's own | their reply + suggestion snapshot; replaces an earlier suggestion of theirs | Reply (suggestion), to the proposer |
| Invitee | The same reply again | always | nothing changes | none |
| Proposer | Accept a suggestion | trip upcoming; that invitee's reply unchanged since it was shown; the showing still confirmed, still to start, still at the suggested time | trip re-snapshotted from the live showing, revision +1; suggester Going (decision 6); everyone else Invited, suggestions cleared | Change, to everyone except the proposer |
| Proposer | Move to a time of their own (decision 4) | as accepting, with any showing of this film | as above, everyone Invited | Change, to everyone except the proposer |
| Proposer | Keep this time (decision 5) | that invitee's suggestion unchanged | suggester Invited, suggestion cleared | Keep, to the suggester |
| Proposer | Invite more (decision 4) | trip upcoming | new Invited rows | Invitation, to the new invitees only |
| Proposer | Cancel | trip upcoming | `cancelled_at_utc` set, everything frozen | Cancellation, to each invitee not Not going |
| Source | Withdraws or cancels the showing | the morning programme run | nothing on the trip changes; the flag is derived (§3) | none (decision 7 puts it in the proposer's Needs you; the reminder says it) |
| Clock | The showing starts | | trip is Past | none |
| 08:00 pass | Reminder | showing's cinema-local date is today, still to start, trip not cancelled | | Reminder, to the proposer and everyone Going |

**Several people at once.** Every write on a trip first locks that trip's row, so writes to one
trip run one after another. Two invitees replying at the same moment both land, and the proposer
gets two pushes. A reply or move names the trip `revision` it was made against, and accepting
names the suggestion's `reply_revision`, so a write made against a screen that is now out of date
is refused instead of applied to the wrong time.

**Refusals, in words:**
- Not on the trip: "Trip not found" (the same answer as no trip at all).
- An invitee trying a proposer's control: "Only Craig can change this trip".
- After a cancel: "Craig cancelled this trip". After the start: "This showing has started".
- A stale revision: "The trip has moved. Check the new time and reply again."
- Accepting a changed suggestion: "Mark changed their reply".
- A showing no longer confirmed, started or gone: "That time is no longer listed".
- "That's already the trip's time"; "That time isn't a showing of this film"; "Pick at least one
  person"; "Not everyone named can be invited" (inactive, unknown, or yourself).

**Retries.** The send carries `client_request_id`, so a send whose answer was lost returns the
same trip and invites nobody twice. A repeated reply changes nothing. A repeated cancel is a
no-op. Each push's dedupe key carries the revision it is about (§5), so a retry inserts nothing
and a genuine later change still pushes. The write and its outbox rows commit together; delivery
follows, as movie nights do, and a failed delivery never fails the request.

**Trip writes are online-only.** They do not join the catalogue's offline queue; offline, the
buttons say "You're offline. Reply when you have signal."

---

## 3. The showing: snapshot, flag and ticket link

**The trip shows its snapshot**, so a programme change never rewrites it and a trip still reads
correctly after the 30-day clean-up deletes the showing. **The flag comes from the live row**,
read whenever the trip is read, so it clears by itself if a cinema lists the time again:

| Live row | Flag on the trip |
|---|---|
| confirmed | none |
| unconfirmed | "Not on ODEON Glasgow Quay's latest listing. It may have been withdrawn." |
| withdrawn, or gone while the trip is upcoming | "ODEON Glasgow Quay no longer lists this time." + to the proposer: "Pick another time or cancel." |
| cancelled | "ODEON Glasgow Quay has cancelled this showing." + the same line to the proposer |

**Check tickets follows AB7's rule, live.** The link shows only while the live showing would
carry one on the film page (confirmed, seen within 30 hours, the cinema's run not failed or
stale). The stored `booking_url` is history and is never shown as a link on its own. A cinema
changing a time usually appears as a new showing plus the old one withdrawn; the trip never
follows it automatically, because a different row could be a different showing. The proposer
moves the trip.

---

## 4. Who sees what

| Person | Sees | Can do |
|---|---|---|
| Proposer | the trip in every place in §6; every reply and suggestion | move, accept or keep a suggestion, invite more, cancel |
| Invitee | the same | their own reply only |
| Any other profile, admins included | nothing: no card, no film-page block, no push; the address answers "Trip not found" | |
| A profile made inactive later | cannot sign in; others still see their last reply | not invitable, and no pushes are queued to them |

Who can be invited: active, non-deleted profiles with a PIN, except the proposer: the rule movie
nights already use to send a night. Nothing assumes two people.

---

## 5. Push wording

All under **Movie night** (the existing switch); quiet hours and digest mode apply as for every
push; a switched-off category leaves a suppressed outbox row, and Needs you still shows the
invitation. Times are the cinema's own (UK), written "Mon 9 Nov at 20:10"; a format that is not
plain digital follows the time ("20:00 IMAX"). Every push opens `/movie-night/trips/<trip id>`.
Titles longer than the outbox's 200 characters are shortened.

Example: Craig proposes Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay, to Mark; Mark
suggests Tue 10 Nov at 20:00, Cineworld Glasgow Silverburn.

| Event | To | Title | Body | Dedupe key |
|---|---|---|---|---|
| Invitation | each invitee | Craig invited you to the cinema | Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay. Going, not going, or another time? | `cinema-trip-invite:<trip>:<person>` |
| Reply: Going | proposer | Mark is going | Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay. | `cinema-trip-reply:<trip>:<invitee>:<reply_revision>` |
| Reply: Not going | proposer | Mark can't make it | Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay. | same |
| Reply: Another time | proposer | Mark suggests another time | Wild Horse Nine: Tue 10 Nov at 20:00, Cineworld Glasgow Silverburn, instead of Mon 9 Nov at 20:10. Open it to accept or keep your time. | same |
| Change (accepted) | the suggester | Craig accepted your time | Wild Horse Nine, Tue 10 Nov at 20:00, Cineworld Glasgow Silverburn. You're down as going. | `cinema-trip-change:<trip>:<revision>:<person>` |
| Change (accepted) | everyone else | Cinema trip moved: Wild Horse Nine | Now Tue 10 Nov at 20:00, Cineworld Glasgow Silverburn, Mark's suggestion. Going or not? | same |
| Change (proposer's own move) | every invitee | Cinema trip moved: Wild Horse Nine | Craig moved it to Tue 10 Nov at 20:00, Cineworld Glasgow Silverburn. Going or not? | same |
| Keep (decision 5) | the suggester | Craig is keeping the original time | Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay. Going or not? | `cinema-trip-keep:<trip>:<invitee>:<reply_revision>` |
| Cancellation | invitees not Not going | Cinema trip cancelled | Craig cancelled Wild Horse Nine on Mon 9 Nov at 20:10, ODEON Glasgow Quay. | `cinema-trip-cancel:<trip>:<person>` |
| Reminder | proposer and everyone Going | Cinema today: Wild Horse Nine | 20:10 at ODEON Glasgow Quay, with Mark. | `cinema-trip-reminder:<trip>:<revision>:<person>` |

Variations, each tested:
- **With more people,** a reply push adds the tally when the trip has two or more invitees:
  "… ODEON Glasgow Quay. 2 of 3 going." The reminder names up to two others ("with Mark and
  Alex"), then "and 2 others"; with nobody else going it ends at the cinema.
- **A flagged showing** adds to the reminder: "The cinema no longer lists this time; check before
  you go." or "The cinema has cancelled this showing."
- **A reminder held past the pass** is written as not sent, reason `too_late`; Notifications
  reads "Not sent — it would have arrived after the showing" (decision 2).

**The switch's description** in Notification settings changes from "Votes and matches while a
movie night is running." to: **"Movie nights and cinema trips: invitations, replies, changes and
reminders."** Its label stays "Movie night".

---

## 6. Where trips appear

```
Into a trip page (/movie-night/trips/<id>):
  any push in §5
  Home → Needs you, or the top slot
  Movie night → Cinema trips, or Past trips (n)
  Film page → Your trips

Starting one:
  Film page → Propose a trip
  Movie night → Plan a cinema trip
    → At the cinema → film page → Propose a trip
```

- **Movie night**: a "Cinema trips" section below the nights: your upcoming trips, soonest first,
  each with poster, film, "Mon 9 Nov · 20:10 · ODEON Glasgow Quay", your reply, "1 going · 1 no
  reply yet", and its flag. "Past trips (n)" holds past and cancelled trips, closed, as AC4 folds
  past screenings. With no trips the section is not drawn. "Plan a cinema trip" stays where AC4
  put it and opens At the cinema.
- **Film page** (`/movie-night/cinema/<key>`): "Your trips" above the days, for trips whose
  address is this page's or whose showing is on it (so a trip proposed on a listing still shows
  once a morning links the film). **"Propose a trip"** under the title opens a sheet: pick a time
  (this page's confirmed, still-to-start times, by day then cinema), pick people (everyone you can
  invite, none ticked), then "Send invitations". The time chips stay ticket links.
- **Trip page** (`/movie-night/trips/<id>`, behind sign-in): the film (opening its film page), the
  showing, Check tickets under §3's rule, the flag, everyone's replies (Craig · Organising first,
  then invitees by name), your reply buttons, and the proposer's controls.
- **Needs you** on Home: "Craig invited you: Wild Horse Nine, Mon 9 Nov 20:10" while your reply is
  Invited; with decision 7, to the proposer, "Mark suggests another time for Wild Horse Nine" and
  "ODEON Glasgow Quay no longer lists your Wild Horse Nine time". Trip items come before disc
  items, soonest showing first. They arrive as a new additive `trips` field rather than new kinds
  in `items`, so a build installed before AC5 still reads Needs you.
- **Home's top slot** (decision 7): "Next: Wild Horse Nine, Mon 9 Nov 20:10 at ODEON Glasgow
  Quay, with Mark" when that is sooner than your next planned movie night; one additive field on
  the same read, so Home makes no new request.

---

## 7. The API, briefly

New router `cinema_trips`, under `/api/v1/`, each answer with its zod schema in `packages/shared`
in the same PR: list mine (upcoming and past); read one; who I can invite; propose; reply; move
(accept or own time); keep a suggestion; invite more; cancel. Additive: Needs you's `trips` and
next trip, both defaulted in zod so a cached answer from before AC5 still parses. No change to the
movie-night or programme reads. A page left open refreshes on focus and after each write; trips
get no live channel (movie nights keep theirs).

---

## 8. Regressions and checks

AC5's own: simultaneous replies; a reply after cancellation; two suggested times at once (accept
one: its suggester Going, the other suggester back to Invited and told of the move); an accepted
suggestion; a withdrawn showing; three profiles on one trip.

Added here: a reply against an old revision after a move is refused; a retried send makes one trip
and one invitation each; a repeated reply pushes once; the reminder pass run twice sends one
reminder; a reminder held by quiet hours or digest is `too_late`; a fourth active profile not on
the trip sees nothing and gets "Trip not found"; an inactive invitee gets no push; a trip still
reads from its snapshot after the clean-up deletes its showing; a suggestion whose showing is
withdrawn cannot be accepted; the proposer cannot be invited; Needs you from a pre-AC5 build still
parses; migration up, down and up; the switch off leaves suppressed rows while Needs you still
shows the invitation.

Full gate and E2E with two signed-in people at 375 px in both themes: Craig proposes, Mark
suggests another time, Craig accepts, Mark sees the move and Going; then cancel. **Push receipt on
a phone stays Craig's observation.** After deploy: the grants proof above, both tables empty and
readable, and the API and web at the merged commit. **No production test trip**: a real one would
push Mark's phone, so the first real trip is Craig's to propose.

---

## 9. Choices made on Craig's behalf, open to overrule

- Trips list in their own section on Movie night, not mixed into the nights.
- The proposer always counts as going; to drop out they cancel.
- Another time needs a specific showing; "none suit" is Not going.
- Nobody is ticked by default in the invite sheet.
- Showings that are unconfirmed, cancelled or started cannot be proposed or suggested; stale
  coverage can, with the page's existing staleness words.
- A withdrawn showing raises no push of its own; the trip, Needs you and the reminder say it.
- No note or message field on a trip; no live updates on an open trip page.
- Trips are kept indefinitely (a few rows a month); nothing deletes them.

## 10. Found in passing, not AC5's to fix

**Digest mode can deliver a day late in winter.** The only all-person delivery passes run at 03:00
and 08:00 UTC, and a digest is due at 09:00 local. In GMT, 08:00 is before 09:00, so a digest
queued during the day waits for the morning after next unless the person does something that
delivers on the spot. Quiet hours ending after 08:00 UTC behave the same. This is existing
behaviour; decision 2 is shaped around it. Not checked against anyone's actual settings.
