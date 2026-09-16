# Mock Technical Interview: PawWalk

**Rules for yourself**
- Don't open `ANSWERS.md` until the end.
- Don't open `pr_review/` until Phase 3. It gives away the feature.
- Talk out loud the whole time, even when you're alone. Record yourself if you can.
- Don't write any code. Everything is spoken, at a high level.

**Timeline (90 min, like the real thing)**

| Time | Phase |
|---|---|
| 0:00–0:10 | Intro + project discussion |
| 0:10–0:30 | **Phase 1:** explore the codebase (hard 20 min cutoff) |
| 0:30–0:40 | Exploration questions (below) |
| 0:40–1:05 | **Phase 2:** design a feature |
| 1:05–1:25 | **Phase 3:** review a PR |
| 1:25–1:30 | Your questions for the interviewer |

---

## Phase 0: Warm-up (answer out loud, about 2 min each)

1. Tell me about yourself and what kind of engineer you are.
2. Walk me through a project you're proud of. What was *your* part, and what did you do with teammates?
3. What went wrong on that project, and what would you do differently?
4. What area interests you most (frontend, backend, infra, security, data), and why?

---

## Phase 1: Explore the codebase (20 min)

> **Interviewer prompt:** "This is PawWalk, a small internal API a dog-walking company uses to book walks with walkers. Take about 20 minutes to get oriented. Think out loud and ask me anything. After that I'll ask you some questions about it."

You can't run anything, so reason about behavior from the code and the CSVs.

### Questions the interviewer asks after you explore

**Orientation**
1. In two sentences, what does this service do?
2. Where did you start, and why there? What did you skip on purpose?
3. Which file would you open first to answer "what endpoints exist?" What about "what are the business rules?"
4. Describe the layers of the app and what each one is responsible for.

**Data flow (trace)**

5. Trace `POST /walks` from the incoming HTTP request to storage and back to the response. Name every function it goes through.
6. Where does the `201` come from? Where does a `404` or `409` come from? How does an exception become JSON?
7. What status codes can `POST /walks` return? List each one and what triggers it.
8. For this body, what's the response code and price? Why?
   `{"walker_id": 1, "dog_id": 5, "start_time": "2026-09-25T08:00", "duration_minutes": 60}`
9. How does the app know what time "now" is, and why does the design do it that way?

**Storage**

10. How is data stored? What happens to a new booking when the server restarts?
11. How are new IDs generated? What could go wrong with that?
12. `store.all()` and `store.get()` return slightly different things. What's the difference, and why does it matter?

**Edge cases (verify before you claim)**

13. What happens if `walker_id` is the string `"1"` instead of the number `1`?
14. What happens if `start_time` is `"2026-09-20T10:00:00Z"`?
15. What does `GET /walks?walker_id=abc` return?
16. Can the same dog be booked with two *different* walkers at the same time?
17. Priya (walker 4) can take 1 dog. Two requests for her 10:00 slot arrive at the same moment. What happens?
18. What happens with `"duration_minutes": 30.0` or `"duration_minutes": true`?

**Tests and ownership**

19. How do the tests avoid depending on the real clock and on data from earlier tests?
20. What important behavior is *not* tested?
21. If this went to production tomorrow, what are the top 3 things you'd fix first?
22. Which part of this codebase were you least sure about? What would you have asked a teammate?

---

## Phase 2: Design a feature (25 min)

> **Interviewer prompt:** "Walkers get paid every two weeks. The ops team needs an API that returns a **payout statement** for one walker over a date range: which walks count toward pay, and how much the walker earned in total. Some walkers have hundreds of walks per period, so the response can't be unbounded. Walk me through how you'd design this. No code needed."

Break it into steps, then expect the interviewer to push hard on each step.

### Follow-up questions the interviewer drills

**Clarifying**
1. What questions would you ask me before designing anything?

**API contract**

2. What's the HTTP method and URL? Why that shape, and not `GET /payouts?walker_id=`?
3. What query parameters does it take? Which are required? What are the defaults?
4. Show me the JSON response shape. What fields are in it, and why?
5. Are `from` and `to` inclusive or exclusive? How do you make that clear to callers?

**Business logic**

6. Which walks count toward a payout? What about cancelled walks, or scheduled walks in the past?
7. Is the total earnings for the page or for the whole range? Why?
8. How do you represent money?

**Pagination**

9. Offset pagination or cursor pagination? What are the trade-offs here?
10. What order do results come back in, and why does order matter for pagination?
11. What happens when a new walk is completed between a caller fetching page 1 and page 2?
12. What happens if someone asks for page 50 when there are only 3 pages?

**Errors, with specific codes**

13. Walk me through the status code for each of these:
    - walker doesn't exist
    - walker exists but is inactive
    - `from` missing
    - `from` = `"yesterday"`
    - `from` after `to`
    - `page_size=0`, `page_size=10000`, `page=-1`, `page=abc`
    - a range of 3 years
    - a walker with no walks in the range

**Implementation and testing**

14. Which files would you change, and what goes in each layer?
15. How does this perform on the CSV store? What changes if it's a real database with 10M walks?
16. How would you test it? Name specific test cases.
17. What would you leave out of v1?

---

## Phase 3: Review a PR (20 min)

> **Interviewer prompt:** "A teammate implemented the payout feature. Here's their PR. Review it. Does it work, and does it do what was asked?"

### PR #42: Add walker payout statements

> Adds `GET /walkers/<id>/payouts?from=YYYY-MM-DD&to=YYYY-MM-DD&page=1&page_size=20`.
>
> Returns completed walks for the walker in the date range, paginated, plus the walker's total earnings for the period. `page` is 1-indexed. `from` and `to` are inclusive. Tests added and passing ✅

**Files changed** (full copies of the changed files live in `pr_review/`):
- `pr_review/api/routes.py`
- `pr_review/services/walk_service.py`
- `pr_review/tests/test_walks.py`

**How to see the diff without a terminal:** in VS Code, right-click `api/routes.py` → **Select for Compare**, then right-click `pr_review/api/routes.py` → **Compare with Selected**. Do the same for the other two files.

### Questions the interviewer asks

1. Before reading the code closely, what's your plan for reviewing this?
2. Does the PR match the description? Does the description match the feature we asked for?
3. Walker 1 calls `GET /walkers/1/payouts?from=2026-09-01&to=2026-09-14` with no other params. Using `storage/data/walks.csv`, what JSON comes back? What *should* come back?
4. Now try `page=1&page_size=3`, then `page=2`, then `page=3`. Which walks does each page return?
5. List every bug you found. For each one, how would you verify it's real? Rank them by severity.
6. The PR says tests pass. Why didn't the tests catch these bugs?
7. What tests would you ask the author to add?
8. Write out (say out loud) the review comment you'd leave for your top bug.
9. Approve, comment, or request changes? Why?
10. Anything you'd flag that isn't a bug, like style, API design, or follow-ups?

---

## Phase 4: Your questions for the interviewer

Have 3 ready. (Suggestions are in `ANSWERS.md`.)
