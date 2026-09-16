# Answer Key: PawWalk Mock

The answer key has four parts:
1. [How to explore, and what to ask while exploring](#part-1-exploring-the-codebase)
2. [Answers to the exploration questions](#part-2-exploration-question-answers)
3. [Feature design](#part-3-feature-design-payout-statements)
4. [PR review](#part-4-pr-review)
5. [Communication cheat sheet](#part-5-communication-cheat-sheet)

---

## Part 1: Exploring the codebase

### The method (don't go line by line)

| Step | What you do | What you say out loud |
|---|---|---|
| 1. Map the repo (1 min) | Look at the folder names: `api/`, `services/`, `storage/`, `tests/`. There's no README. | "No README, so I'll use the folder structure. It looks layered: HTTP, business logic, storage." |
| 2. Find the entry point (2 min) | `app.py` has `create_app` and `__main__`. | "This is the composition root. It builds the store, injects it into the service, registers routes, and turns `ServiceError` into JSON." |
| 3. Read the imports | `app.py` imports from all 3 layers. `routes.py` only imports `errors`. The service imports only `errors`. The store imports nothing internal. | "Dependencies point one way: routes → service → store. The service gets the store injected, so tests can swap it." |
| 4. Pick ONE method and trace it | `POST /walks` touches every layer and has the most rules. | "I'll trace the write path because it touches the most code." |
| 5. Check the data | Open the CSVs. Note the column types and the seed rows. | "IDs are ints once parsed. Times have no timezone. Money is in cents." |
| 6. Skim the tests | `conftest.py` pins the clock and makes a fresh store per test. | "Tests show the intended behavior. They're also a list of what's covered." |
| 7. Note weak spots | Keep a running list, and verify each one before stating it. | "I think X would 500. Let me confirm by following the value..." |

### The POST /walks trace (memorize this shape)

```
HTTP POST /walks
 └─ routes.create_walk
     ├─ request.get_json(silent=True) → not a dict? raise ValidationError → 400
     └─ service.create_walk(payload)
         ├─ required fields present?                 → 400
         ├─ _require("walkers", id) → store.get      → 404
         ├─ _require("dogs", id)    → store.get      → 404
         ├─ walker.active?                           → 409
         ├─ duration in (30, 60)?                    → 400
         ├─ _parse_time(start_time)                  → 400
         ├─ start <= clock()?                        → 400
         ├─ list_walks(walker, "scheduled") + _overlaps
         │    ├─ len(overlapping) >= max_dogs        → 409
         │    └─ dog already in overlapping          → 409
         ├─ price = rate * duration // 60 (+500 if large)
         └─ store.insert("walks", {...}) → id = max(ids) + 1
     └─ jsonify(record), 201
Errors: ServiceError subclass → app.handle_service_error → {"error": msg}, status_code
Any other exception → Flask default 500 (HTML, not JSON)
```

### Questions you should have asked the interviewer *while* exploring

Asking these shows you're clarifying scope instead of guessing.

- "Is it OK if I start at the entry point and trace one endpoint instead of reading every file?"
- "Is this run with the Flask dev server, or behind gunicorn with multiple workers/threads?" (This matters for the in-memory store and race conditions.)
- "Is the CSV only seed data, or should writes persist back to disk?"
- "What timezone are `start_time` values in? Are callers expected to send offsets?"
- "Who calls this API: an internal ops UI, a mobile app, or third parties? Is there auth in front of it?"
- "Is a dog allowed to be booked with two walkers at once, or is that a bug?"
- "Is `max_dogs` meant to be 'dogs at the same moment' or 'overlapping bookings'?"
- "Are the tests the source of truth for intended behavior, or might they be stale?"
- "I'm assuming the `if __name__` block is only for local dev. Is that right?"

---

## Part 2: Exploration question answers

**1. What does it do?** It's a Flask JSON API for booking dog walks. It stores walkers, dogs, and walks. It validates bookings against walker availability and capacity, prices each walk, and supports cancellation. Data is loaded from CSVs into memory.

**2. Where did you start?** `app.py`, because it wires everything together. Then I read the imports to learn the layers, then traced `POST /walks`. I skipped the CSV parsing details and the simple GET endpoints at first.

**3.** "What endpoints exist?" → `api/routes.py`. "What are the business rules?" → `services/walk_service.py`.

**4. Layers:**
- `routes.py` handles HTTP only: parsing requests, status codes on success.
- `walk_service.py` holds business rules and raises typed errors.
- `errors.py` maps each error type to a status code.
- `csv_store.py` does generic table CRUD in memory.
- `app.py` wires things together and handles errors.
- `conftest.py` and `tests/` hold test setup and tests.

**5.** See the trace above.

**6.** `201` is hardcoded in `routes.create_walk`. `404` and `409` come from `NotFoundError` and `ConflictError` class attributes. The `@app.errorhandler(ServiceError)` in `app.py` catches any subclass and returns `{"error": message}` with that class's `status_code`.

**7. POST /walks codes:**
- `201` created
- `400` body isn't a JSON object, fields missing, bad duration, bad time format, or time in the past
- `404` unknown walker or dog
- `409` inactive walker, walker full, or dog double-booked
- `500` anything unhandled (see #13, #14)

**8.** Walker 1 costs 2400/hr. 60 min → 2400. Dog 5 (Juniper) is large → +500 = **2900**. Maya has a scheduled walk on 09-21, but 09-25 doesn't overlap. Result: **201**, `price_cents: 2900`, `id: 15`.

**9.** `WalkService` takes a `clock` callable (default `datetime.now`). Tests inject a fixed time (2026-09-16 09:00) so "in the future" checks are deterministic. This is dependency injection for testability.

**10.** `CsvStore` reads the 3 CSVs once at startup into dicts keyed by id. Writes only change memory. **A restart loses every new booking and cancellation.** Each process also has its own copy, so with multiple gunicorn workers, each worker sees different data.

**11.** `max(existing ids) + 1`. Problems:
- It isn't atomic. Two concurrent inserts can get the same id, and one overwrites the other.
- In a real DB, deleting the max row would reuse its id.

**12.** `get()` returns a **copy** (`dict(record)`). `all()` returns a new list, but the **same dict objects** stored inside. A caller that mutates an item from `all()` silently changes the store. Nothing does that today, but it's a trap for the next feature.

**13.** `store.get("walkers", "1")` looks up the string key `"1"`, but keys are ints, so it returns None. That gives **404 "walker 1 not found"**, which is misleading. It should be a **400**. There's no type validation of the payload.

**14.** Python 3.11+ `fromisoformat` accepts `Z`, so you get a timezone-aware datetime. Comparing it to the naive `clock()` raises `TypeError`, which is **not** a `ServiceError`. Result: a **500**. (Verified.)

**15.** `request.args.get("walker_id", type=int)` returns `None` when conversion fails. The filter is skipped and you get **all walks** with a 200. It fails silently instead of returning 400.

**16. Yes.** The dog-conflict check only looks at `overlapping`, which only has *that walker's* walks. Booking Biscuit with Maya and Jordan at the same time succeeds.

**17. Race condition.** Both requests read the scheduled walks, see 0 overlapping, and pass the capacity check before either inserts. Both insert, so Priya is double-booked, and they may even get the same id. Flask's dev server is threaded by default. Fixes include a lock around check-and-insert, a DB transaction or unique constraint, or optimistic concurrency.

**18.**
- `30.0 in (30, 60)` is True because `30.0 == 30`. The walk is stored with `30.0`, and the price becomes a float (`2000*30.0//60 = 1000.0`).
- `True` is `1` in Python, not in `(30, 60)`, so 400. But `walker_id: true` would look up id 1.

The takeaway: there's no strict type validation.

**19.** The clock is injected with a fixed datetime. The `client` fixture builds a **new `CsvStore()` per test**, so each test starts from the seed CSVs. (`collect_ignore` in `conftest.py` skips the `pr_review` folder.)

**20. Not tested:**
- all the GET endpoints except `/walkers`, and `GET /walks` filters
- 404 for an unknown walker
- dog double-booking
- adjacent (non-overlapping) walks at the boundary, e.g. 10:00–10:30 then 10:30
- timezone input
- wrong types
- concurrency
- the cancel-then-rebook flow

**21. Top 3 fixes (ownership, "the next 5 things"):**
1. Real persistence plus atomic check-and-insert (data loss and race conditions).
2. Input validation layer: types, timezone handling, bad query params → 400 instead of 404/500.
3. Pagination on `GET /walks` (it's unbounded), and make dog double-booking check all walkers.

Also worth mentioning: a JSON error handler for 500s, auth, and `all()` leaking mutable records.

**22.** Good honest answer: "I wasn't sure whether `max_dogs` means concurrent dogs or overlapping bookings. The code counts every overlapping walk, even if two of them don't overlap *each other*, so it's stricter than it might need to be. I'd ask a teammate what the intended rule is."

---

## Part 3: Feature design: payout statements

### Step 0: Clarifying questions (ask these first)
- Which statuses count? (Assume **completed only**.)
- Is `to` inclusive? (Assume the caller thinks in whole days, so **inclusive**. Implement it as `start < to + 1 day`.)
- Is a walk counted by its start time? (Yes.)
- Does the walker get 100% of `price_cents`, or is there a platform cut? (Assume 100% for v1, but keep that calculation in one place.)
- Who calls it? Ops UI (internal, auth required). Do walkers see their own?
- What timezone define "a day"? (Assume company-local naive, like the rest of the app.)
- Max range? (Suggest 31 or 92 days. Pay periods are 2 weeks.)
- Can past statements change? (Yes, if a walk is cancelled after the fact. Is that OK, or do we need snapshots?)
- Rough scale? (Hundreds of walks per period, per the prompt.)

### Step 1: API contract

```
GET /walkers/{walker_id}/payouts?from=2026-09-01&to=2026-09-14&page=1&page_size=50
```
**Why this URL:** a payout statement is a sub-resource of a walker. It's a read-only, idempotent, cacheable `GET`. It also lets you return 404 cleanly when the walker doesn't exist. (`GET /payouts?walker_id=` is fine if you later want payouts across many walkers. Mention that as a trade-off.)

| Param | Required | Default | Rules |
|---|---|---|---|
| `from` | yes | none | `YYYY-MM-DD`, inclusive |
| `to` | yes | none | `YYYY-MM-DD`, inclusive, `>= from`, range ≤ 92 days |
| `page` | no | 1 | int ≥ 1 |
| `page_size` | no | 50 | int 1–100 |

**Response `200`:**
```json
{
  "walker_id": 1,
  "from": "2026-09-01",
  "to": "2026-09-14",
  "summary": { "walk_count": 7, "total_earnings_cents": 13000, "currency": "USD" },
  "walks": [ { "id": 1, "dog_id": 1, "start_time": "2026-09-01T08:00", "duration_minutes": 30, "price_cents": 1200 } ],
  "pagination": { "page": 1, "page_size": 50, "total_pages": 1, "total_items": 7, "has_more": false }
}
```
Key points to say out loud:
- **Summary is computed over the whole range, not the page.** The ops person needs the payout total no matter which page they're on.
- Money is **integer cents** (never floats), plus a currency field.
- Echo `from`/`to` back so the response describes itself.
- `has_more` so clients don't do math.

### Step 2: Business logic (service layer)
1. `_require("walkers", walker_id)` → 404. (Keep inactive walkers **allowed**, since they still need to get paid for past work.)
2. Filter walks: `walker_id` matches, `status == "completed"`, `from 00:00 <= start < (to + 1 day) 00:00`.
3. **Sort** by `(start_time, id)`. Pagination is meaningless without a stable, deterministic order. `id` breaks ties.
4. `total_items = len(filtered)`, `total_earnings = sum(price for all filtered)`.
5. `total_pages = ceil(total_items / page_size)`, i.e. `(n + size - 1) // size`.
6. `offset = (page - 1) * page_size`, `items = filtered[offset : offset + page_size]`.
7. Return copies of records, not store references (see exploration answer #12).

### Step 3: Validation (route layer) and error codes

| Case | Code | Reasoning |
|---|---|---|
| Walker not found | **404** | Resource in the path doesn't exist |
| Walker inactive | **200** | They still need past pay. Don't block it |
| `from`/`to` missing | **400** | Required param |
| `from=yesterday` / `2026-13-01` | **400** | Malformed. Never let `fromisoformat` raise a 500 |
| `from` has a time or timezone | **400** | Contract is dates only (avoids naive/aware 500) |
| `from > to` | **400** | Invalid range (or 422. Pick one and be consistent. This app uses 400 for validation) |
| Range > 92 days | **400** | Bounds cost. The message says the max |
| `page_size=0`, negative, or > 100 | **400** | Or clamp to 100. State which. Rejecting is more explicit |
| `page=0`, `-1`, `abc` | **400** | Never `int()` a query param unguarded |
| `page` beyond last page | **200** with `walks: []` | Valid request, just empty. Totals still present |
| No walks in range | **200**, count 0, total 0 | An empty statement is still a statement |
| Unexpected exception | **500** JSON | Add a generic JSON error handler |
| Unauthenticated / not ops | 401 / 403 | Out of scope for v1, but mention it |

### Step 4: Edge cases to name (fully)
- A walk exactly at `from 00:00` (included) and exactly at `to 23:59` (included). A walk at `to+1 00:00` (excluded).
- Walk starts on the last day and ends after midnight: counted by start time.
- Cancelled, scheduled, and past-but-not-completed walks are excluded.
- Two walks with the same `start_time` → tie broken by `id`, so pages don't overlap or skip.
- Data changes between page requests. Offset pagination can skip or duplicate items. That's acceptable for an ops report. Alternatives: **cursor pagination** (`after=(start_time,id)`), or a snapshot/statement id.
- Totals across pages must be consistent: the summary is the same on every page.
- Last page is a partial chunk (7 items, size 3 → pages of 3, 3, 1).
- `page_size` larger than the total → 1 page.
- A walk cancelled after a payout was issued → the statement changes. A future "finalized payouts" table would fix it.
- Price rounding: already integer cents from booking, so just sum integers.
- DST and timezone: naive local times. Flag this as a known limitation.

### Step 5: Files touched
- `api/routes.py`: new route, parse and validate query params, raise `ValidationError`.
- `services/walk_service.py`: `payout_statement(...)` with filter, sort, total, and slice.
- `app.py`: optionally a generic JSON 500 handler.
- `tests/test_walks.py`: new tests.
- The store doesn't change for v1.

### Step 6: Performance
- CSV store: O(all walks) scan per request. Fine for thousands of walks.
- Real DB: index on `(walker_id, status, start_time, id)`. Use `COUNT` + `SUM` in one aggregate query and `LIMIT/OFFSET` (or keyset) for the page. Deep offsets get slow, which is another reason for cursors.
- Could cache finalized past periods.

### Step 7: Tests to list
- Happy path, exact numbers: walker 1, 09-01 → 09-14 = 7 walks, 13000 cents (includes walk 10 on 09-14 → inclusive `to`).
- Cancelled walk 5 excluded. Scheduled walks excluded.
- `page_size=3`: page 1 = [1,2,3], page 2 = [6,7,9], page 3 = [10], page 4 = [] and still 200. Summary is identical on every page.
- `total_pages == 3`, `has_more` true, true, false.
- Every error in the table gets its own test with the exact status code.
- Unknown walker → 404. Inactive walker → 200.
- Tie ordering.

### Step 8: Out of scope for v1
Auth, CSV/PDF export, platform fee percentage, finalized/immutable payouts, multi-currency, cursor pagination (unless the interviewer pushes for it).

---

## Part 4: PR review

### Review approach (say this first)
"First I'll check completeness against the description and the original ask. Then I'll trace one real request end to end using the seed data, reusing the method from exploration. Then I'll hunt edge cases: pagination boundaries, filters, and input validation. Last, I'll check whether the tests would actually catch any of it."

### Q3: Default request trace, `GET /walkers/1/payouts?from=2026-09-01&to=2026-09-14`

Maya's walks: 1,2,3 (completed), 5 (**cancelled**), 6,7,9 (completed), 10 (**completed, 09-14 18:00**), 12,14 (scheduled).

**What the PR actually returns (verified by running it):**
```json
{ "total_walks": 7, "total_earnings_cents": 0, "page": 1, "page_size": 20,
  "total_pages": 0, "walks": [] }
```
**What it should return:** 7 walks `[1,2,3,6,7,9,10]`, `total_earnings_cents: 13000`, `total_pages: 1`.

The trap: `total_walks: 7` *looks* right, but it's the **wrong 7**. The cancelled walk 5 got in, and walk 10 on the `to` day got dropped. Two bugs cancel out in the count. That's why you verify contents, not just counts.

### Q4: Pagination chunks, `page_size=3`

| Request | PR returns | Earnings shown | Should return |
|---|---|---|---|
| `page=1` | `[5, 6, 7]` | 5300 | `[1, 2, 3]` |
| `page=2` | `[9]` | 1700 | `[6, 7, 9]` |
| `page=3` | `[]` | 0 | `[10]` |
| `page=0` (invalid) | `[1, 2, 3]` | 6500 | 400 |
| `total_pages` | **2** | none | **3** |

Walks 1, 2, 3 can only be reached with an undocumented `page=0`.

### Q5: Bugs ranked

#### 🟢 Simple #1: Off-by-one page offset (logic/chunk)
- **Where:** `offset = page * page_size` in `payout_statement`.
- **Problem:** `page` is 1-indexed per the PR description, so page 1 skips the first chunk. With the defaults (`page=1, page_size=20`), any walker with ≤20 walks gets **an empty list**. That's most walkers.
- **Verify:** 7 walks, default page_size 20 → offset 20 → `walks[20:40]` = `[]`.
- **Fix:** `offset = (page - 1) * page_size`, and validate `page >= 1`.

#### 🟢 Simple #2: `total_pages` drops the last partial chunk
- **Where:** `len(walks) // page_size`.
- **Problem:** Floor division. 7 walks / 3 → 2 pages, but walk 10 is on page 3. Clients that stop at `total_pages` never see the last walks. 7 walks / 20 → **0 pages**.
- **Fix:** `math.ceil(len(walks) / page_size)` or `(n + size - 1) // size`. Consider `has_more`.

#### 🟡 Medium: Earnings summed over the page, not the period
- **Where:** `sum(... for walk in page_walks)`.
- **Problem:** The feature is "how much the walker earned in the period." This returns only the current chunk's total, so it **changes per page** and is 0 on the default request. Ops would underpay walkers. This is the highest business impact. It's a **completeness** bug: the code runs fine but doesn't do what was asked.
- **Fix:** sum over `walks` (the full filtered list) before slicing.

#### 🔴 Also wrong (correctness)
4. **Cancelled walks counted as pay.** `status != "scheduled"` lets in `cancelled` (and any future status). The description says "completed walks." Walker 1 gets paid 1700 for walk 5. **Fix:** `status == "completed"` (an allowlist, not a denylist).
5. **`to` isn't inclusive.** `fromisoformat("2026-09-14")` is midnight, and `start < to` excludes everything on 09-14. Walk 10 is missing. The description says inclusive. **Fix:** `start < to + timedelta(days=1)`.
6. **No sorting.** Results come in store insertion order. Walks inserted later (or loaded from an unordered source) break pagination: pages can skip or repeat. **Fix:** sort by `(start_time, id)`.

#### 🟠 Error handling (edge cases for error codes)
7. `page_size=0` → `ZeroDivisionError` → **500**. (Verified.)
8. `page=abc` / `page_size=abc` → `int()` raises `ValueError` → **500**. (Verified.)
9. `from=nope` → `fromisoformat` raises `ValueError` → **500**. (Verified.) `from=2026-09-01T00:00Z` → aware vs naive comparison → **500**.
10. Unknown walker `99` → **200** with empty data instead of **404**. It never calls `_require`. (Verified.)
11. No `from <= to` check, no max range, no `page_size` cap (`page_size=1000000` is allowed), negative `page` → negative slice → empty, or odd results.

#### 🔵 Non-blocking / design notes
- The route passes `datetime` objects but the API contract is dates. It should parse with `date.fromisoformat` and reject times.
- `walks` returns the store's **live dict references** (from `all()`), so a later mutation of the response data would corrupt the store.
- The response shape mixes pagination and summary fields at the top level. Consider grouping them.
- No JSON 500 handler, so crashes return HTML to an API client.

### Q6: Why the tests didn't catch it
- `page=0` in the test **avoids** the offset bug. The test uses behavior the description says is invalid.
- `page_size=10` makes everything fit on one page, so page-sum equals period-sum. The medium bug is hidden.
- `len(walks) == total_walks` is **self-consistent**, not **correct**. It never checks actual ids or amounts.
- `total_earnings_cents > 0` would pass with almost any wrong value.
- `to=2026-09-15` sidesteps the inclusive-`to` bug.
- No test for cancelled walks, `total_pages`, multiple pages, 404, or any 400/500 case.
- "Tests pass" ≠ "feature works." Tests have to assert **exact expected values from known seed data**.

### Q7: Tests to request
- Default params → 7 walks, 13000, ids `[1,2,3,6,7,9,10]`.
- `page_size=3`, pages 1/2/3/4 → `[1,2,3]`, `[6,7,9]`, `[10]`, `[]`. `total_pages == 3`. Earnings is 13000 on **every** page.
- Walk on the `to` date included. Cancelled walk excluded.
- 404 unknown walker. 400 for: missing dates, bad date, `from > to`, `page=0`, `page=abc`, `page_size=0`, `page_size=1000`.

### Q8: Example review comment (top bug)
> **Blocking: total earnings is per-page, not per-period.**
> `total_earnings_cents` sums `page_walks`, so it only covers the current page. With the default params, `GET /walkers/1/payouts?from=2026-09-01&to=2026-09-14` returns `0` (the page is empty because of the offset issue below). With `page_size=3&page=1` it returns `5300`. The correct period total from the seed data is `13000`. Ops would use this number to pay walkers, so they'd be underpaid.
> Suggestion: compute the sum over `walks` before slicing, and add a test that asserts the same total on every page.

Structure: **severity → what → concrete repro with real data → impact → suggested fix → test.**

### Q9: Verdict
**Request changes.** Several blocking correctness bugs affect money (wrong totals, paying for cancelled walks, missing walks), the default request returns nothing, and bad input crashes with 500s. The structure is good, though: the route/service split matches the codebase and the URL shape is right. Say something positive. It's a teammate.

### Q10: Non-bug feedback
Add input validation helpers (reusable for `GET /walks` too), group the response into `summary`/`pagination`, add a JSON 500 handler, and consider cursor pagination as a follow-up.

---

## Part 5: Communication cheat sheet

**Orienting:** "I'm going to skim the structure first, then pick one endpoint and trace it end to end instead of reading every line."

**Verifying before claiming:** "I *think* this returns 404 instead of 400. Let me follow the value... `store.get` with key `"1"`, keys are ints... yes, confirmed."

**Stating impact:** "This matters because ___ would happen to ___ users."

**Asking for help without losing points:**
- "I'm stuck on X. I've ruled out A and B. Is C the right direction?"
- "I'm not familiar with `request.args.get(type=...)`. I'm assuming it returns None on failure. Is that right?"
- "I'm going to assume ___ for now. Tell me if that's wrong."

**When you're running out of time:** "I have more edge cases, but let me prioritize: the most important three are ___."

**Design, step by step:** clarify → API contract → logic → errors → edge cases → files → tests → scale → out of scope. Say the steps up front, then go deep on whichever one the interviewer picks.

**Engineering values to show** (from the Datadog guide):
- Pragmatism: simple offset pagination for v1, cursors later.
- Honesty: "I don't know, here's how I'd find out."
- Ownership: "the next things I'd fix."
- Humility: take hints and adapt out loud.

### Questions to ask your interviewer
- "How does your team use Datadog products to debug your own services? Any dogfooding story that changed a design?"
- "What does code review look like on your team? What makes a PR easy for you to approve?"
- "What does a successful intern project look like, and how do interns get paired with teams?"
- "What's something you changed your mind about technically since joining?"
