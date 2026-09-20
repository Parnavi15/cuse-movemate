# ♻️ Cuse-MoveMate

> **One student's move-out is another student's move-in.**

A student-to-student move-out marketplace built around three ideas: **reuse**, **distance-aware matching**, and a **reward loop** that gives students a reason to come back next semester.

**Stack:** Django REST Framework · React (Vite) · SQLite

---

## 🚀 Quick start

Two terminals, about two minutes.

### 1. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py makemigrations core
python manage.py migrate
python manage.py seed --reset      # demo campus: 6 students, 22 listings, wallet history
python manage.py runserver
```
- **API** → http://127.0.0.1:8000/api/
- **Admin** → http://127.0.0.1:8000/admin/ (`admin` / `movemate`)

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
App → http://localhost:5173. Vite proxies `/api` to Django, so there's nothing to configure.

---

## 🔧 If something 500s after an update

Migrations are generated per-copy. A database first created from an older `0001_initial` has that name recorded as *applied*, so a newer `0001_initial` with extra fields gets skipped — `migrate` reports "No migrations to apply," the new columns never appear, and the first request that touches one returns a 500.

```bash
python manage.py repair_schema --dry-run   # show what's missing
python manage.py repair_schema             # add it — data untouched
```

---

## 🎓 Students only

Account creation is restricted to Syracuse University email addresses. `shsitole@syr.edu` gets in; `someone@gmail.com` does not, and neither does a lookalike like `someone@syr.edu.evil.com`. Real university subdomains (`@g.syr.edu`, `@mail.syr.edu`) are accepted.

Signing up sends a **6-digit code** to that address. Until it's confirmed, an account can browse but **cannot list an item, claim an item, or redeem points**. In DEBUG the code is printed to the Django console and returned in the API response, so the flow is demonstrable without a mail server.

Open it to another campus without touching code:
```bash
export MOVEMATE_STUDENT_DOMAINS="syr.edu,esf.edu"
```

---

## 👤 Demo accounts

All seeded students use the password `movemate` and are verified on `@syr.edu`: **demo, maya, devin, priya, jules, sam**. Sign in with the username or the full campus address.

Start with **demo** — that account already has completed handoffs, posted points, badges, and one request waiting for approval.

---

## 📅 Scheduling the pickup

One side proposes a time (quick chips, or a date picker), the other agrees. Proposing always clears any previous agreement, so a changed time can never silently stay "agreed" for the person who didn't change it. The server rejects times in the past and times past the listing's own pickup deadline.

Once agreed, both students get an **Add to Google Calendar** link and an **.ics download** for Apple Calendar or Outlook — generated client-side, no API key.

---

## 💬 Chat

Each handoff has its own conversation, opened from the request card. It's scoped to the transaction rather than being a general inbox: two students are talking because of a specific desk, and the thread ends when that desk moves. That scoping is also what makes moderation tractable — every message has a transaction attached.

Polls every **8 seconds** while open; a new message notifies the other side.

---

## 🗺️ Getting there

`core/routing.py` answers "how long will this actually take" for walking, cycling, bus, and driving:

- **With `GOOGLE_MAPS_API_KEY`** — real road distances and transit schedules via the Distance Matrix API.
- **Without one** — estimated from distance (road factor 1.3, plus fixed overhead for waiting and parking) and clearly labeled as an estimate.

Either way, each option links out to real turn-by-turn Google Maps directions — plain URLs that need no key at all.

---

## 🔔 Notifications

Every state change writes a Notification row in the **same database transaction** that caused it, so a notification can never describe something that didn't happen. The bell in the nav polls every **20 seconds**.

Only **two** events also send email — *somebody wants your item* and *your request was accepted*. Everything else stays in-app, because noisy apps get muted. Students can turn email off from their profile.

**Test both sides on one machine:**
```bash
python manage.py create_student pranavi --at euclid
```
Creates a verified student instantly — no signup, no email. Sign in as her in a private window so both accounts stay live, claim one of your listings, and watch your bell light up.

**Test with a friend, on two machines:**
1. Start Django: `python manage.py runserver 0.0.0.0:8000`
2. Find your IP: `ipconfig getifaddr en0`
3. Add it to `CORS_ALLOWED_ORIGINS` in `movemate/settings.py`
4. Your friend opens `http://YOUR_IP:5173` on the same wifi and signs up
5. She claims one of your listings — your bell lights up within 20 seconds and an email lands in your inbox

---

## 🔁 Roles

There is no "buyer account" or "seller account," deliberately. The same student sells a futon in May and claims a desk in August, and splitting them would mean a seller needs a second account just to take a free desk.

Role is a property of a **transaction**, not a person: every listing form asks you to confirm you're passing the item on, every request card says whether you're the seller or the claimant, and your profile keeps both counts.

---

## 📸 Photos

Listings take a photo straight from the phone camera or camera roll. Files upload to `POST /api/uploads/photo/` and land in `backend/media/listings/` — JPG, PNG, WebP, and GIF up to 5 MB. A URL field is still there as a fallback.

> For production, swap `default_storage` for S3 — local disk doesn't survive a redeploy.

---

## 📧 Email verification

Verification codes go to the student's real campus inbox. Set two environment variables before starting Django:
```bash
export EMAIL_HOST_USER="you@gmail.com"
export EMAIL_HOST_PASSWORD="abcdefghijklmnop"   # 16-char App Password, no spaces
```
Gmail needs an **App Password**, not your account password: turn on 2-Step Verification, then create one at myaccount.google.com/apppasswords.

Prefer not to set up mail at all? Verify from the command line:
```bash
python manage.py verify_user sshitole@syr.edu          # show the pending code
python manage.py verify_user sshitole@syr.edu --force  # verify outright
```
Test SMTP before you rely on it:
```bash
python manage.py test_email sshitole@syr.edu
```
With no credentials set, Django prints the email to the console and the app shows the code on screen, so the project still runs for anyone who clones it.

Sending **to** an `@syr.edu` address works from any provider. Sending **from** one usually doesn't — most university tenants disable SMTP auth, so use a personal Gmail as the sender.

---

## 📍 Location

Students set their location one of two ways, and both end up as a **coordinate pair** — which is what the distance search actually runs on:

- **Use my current location** — the browser's Geolocation API. Exact, free, no key.
- **Type a street** — debounced address search with suggestions.

Campus places come from a gazetteer in `core/geo.py` rather than the geocoder. OpenStreetMap doesn't index "South Campus," "Skytop," or "Ernie Davis" under the names students actually use — searching "south campus" was returning Westcott, and a confidently wrong answer is worse than no answer. Roughly **28 campus and Syracuse landmarks** resolve instantly; anything else falls through to the geocoder.

Coordinates are turned into readable names ("Euclid Ave") by `core/geo.py`, which uses Google Maps when a key is present and OpenStreetMap's Nominatim when it isn't. Both calls go through Django, so the API key never reaches the browser.
```bash
export GOOGLE_MAPS_API_KEY=...   # optional; enable "Geocoding API" on the key
```
Other students only ever see the neighbourhood name and a distance — never an address.

---

## 🤖 Optional: Claude-powered matching
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
With a key set, natural-language requests are parsed by Claude. Without one, a deterministic rule parser handles the same job. **The demo never depends on the network.**

---

## 🎬 The three-minute demo script

1. **Home page** — live campus stats: items available, kilograms diverted, dollars saved.
2. **"What do I need?"** — paste *"I'm moving into an apartment next week and need a desk, chair and kitchen supplies for under $50."* Show the *Here's what we understood* panel (item, budget, radius, deadline), then the grouped results and the *you might also need* row.
3. **Open a listing** — point at the distance, the pickup deadline, the owner's star rating and verified badge. Scroll to *You might also need*: a paint brush surfaces a roller, tape, and drop cloth, all from real nearby listings.
4. **Sign in as demo → Requests** — Maya wants the desk. Accept it, add a pickup note.
5. **Confirm handoff** — in another browser, sign in as maya and confirm too. Watch the state flip to *completed* and the points land as *pending*.
6. **Wallet** — Impact Wallet card, ledger with the pending row, badge progress. Hit *Fast-forward 24h*, then redeem 100 points for $5.00 of credit.
7. **Close on the loop:** List → Match → Hand off → Confirm → Review → Earn → Redeem → List again.

---

## 🧩 What's in here — feature map

| Feature | Where it lives |
|---|---|
| User authentication | `core/views.py` (register / login / logout / me), DRF token auth |
| Students-only signup | `core/campus.py` domain gate, enforced in `RegisterSerializer` |
| Verified student identity | `verify_request` / `verify_confirm` — gates listing, claiming, redeeming |
| Item management (create, edit, delete) | `ListingViewSet`, `frontend/src/pages/NewListing.jsx` |
| Distance-based search | `core/search.py` — haversine + weighted ranking |
| Booking with accept / reject | `TransactionViewSet` state machine |
| Owner + claimant confirm flow | `TransactionViewSet.confirm` — the only point-creating call |
| Wallet & reward points | `core/rewards.py`, `frontend/src/pages/Wallet.jsx` |
| Feedback / star reviews | `create_review`, `ReviewPanel` in `Bookings.jsx` |
| "What do I need?" recommendations | `core/matching.py` `parse_need` |
| Related-item recommendations | `core/matching.py` `COMPANIONS`, `/listings/<id>/related/` |
| Impact Wallet analytics | `rewards.impact_for`, constants in the `Category` table |

---

## 🛡️ Design decisions worth defending

- **Points are created by exactly one event.** Both students tapping *confirm handoff* moves a transaction `accepted → completed` and writes the ledger rows. Nothing else in the system mints points — that single chokepoint is what makes the economy auditable.
- **The wallet balance is never edited directly.** It's a cached sum of an append-only `PointEntry` ledger, with a unique constraint on `(wallet, rule, transaction)` so a double-tapped button can't award twice. Money-adjacent code should be boring.
- **Giving something away earns more than selling it** — 50 vs 20 points, both plus a 25-point circulation bonus. The item most likely to hit the curb is the one nobody wants to bother pricing, so letting it go is the most rewarding thing a student can do.
- **A points system is a fraud problem wearing a friendly hat.** Guardrails in `rewards.py`: both-sides confirmation, a 24-hour pending window, a pair limit of 2 earning handoffs per 30 days, a 300-point weekly ceiling, a listing quality gate, and `.edu` verification required before redemption.
- **One function decides who is a student.** `core/campus.py` holds the domain rule, and registration, verification, and the frontend all read from it — the React signup form pulls the allowed domains from `/api/config/` rather than hardcoding them. There is no second copy of the rule to drift.
- **Distance is a ranking signal, not a filter.** A desk two blocks away beats a slightly better desk across the city, because the student carrying it doesn't have a truck. Weights live at the top of `search.py`: relevance 0.34, distance 0.30, budget 0.18, timing 0.10, condition 0.08.
- **Impact constants live in the database, not in code.** A university sustainability office could replace the per-category weight and CO₂e figures without a redeploy. Every figure on the Impact Wallet is labeled as an estimate.

---

## 🔌 API

```
POST   /api/auth/register/              POST   /api/auth/login/
GET    /api/auth/me/                    POST   /api/auth/verify/request/
                                        POST   /api/auth/verify/confirm/

GET    /api/listings/?q=&category=&mode=&radius_km=&max_cents=
POST   /api/listings/                   PATCH  /api/listings/<id>/
GET    /api/listings/mine/              DELETE /api/listings/<id>/
GET    /api/listings/<id>/related/      GET    /api/categories/

POST   /api/match/                      {"text": "cheap desk near campus before Friday"}

POST   /api/transactions/               GET    /api/transactions/?role=owner|claimant
POST   /api/transactions/<id>/accept/   POST   /api/transactions/<id>/reject/
POST   /api/transactions/<id>/confirm/  POST   /api/transactions/<id>/cancel/
POST   /api/transactions/<id>/dispute/  POST   /api/reviews/

GET    /api/wallet/                     GET    /api/wallet/ledger/
GET    /api/wallet/impact/              POST   /api/wallet/redeem/
POST   /api/wallet/settle/              (DEBUG only — skips the 24h wait for demos)

GET    /api/geo/reverse/?lat=&lng=      GET    /api/geo/search/?q=
GET    /api/config/                     GET    /api/stats/
GET    /api/leaderboard/
```

---

## 🚢 Before you deploy

- Set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0`. The dev secret in `settings.py` is not a secret.
- Swap SQLite for Postgres.
- Replace the printed verification code with real email (`django.core.mail`).
- Move `rewards.settle()` off the lazy wallet read and onto an hourly Celery beat job.
- Add rate limiting on `/api/match/` if you're paying for Claude calls.

---

## 🔮 What's next

AI-generated move-in checklists · apartment and sublease discovery · roommate matching · bulk move-out listings · pickup and logistics coordination · university sustainability partnerships · savings and diversion analytics for the sustainability office.
