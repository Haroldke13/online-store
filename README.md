# Online Store

A Flask e-commerce site with a product catalogue, cart, orders and an admin panel, wired to PayPal, Safaricom M-Pesa and Airtel Money sandbox payment APIs.

## What it does

Three blueprints, all mounted at `/` (`app/__init__.py`).

**Storefront (`app/views.py`).** Homepage listing flash-sale products, keyword search (`/search`) and a random-by-category browse (`/search_random/<category>`), cart add/remove, and an orders list. The homepage also renders an audio player that lists and streams the `.m4a` files sitting in the media folder via `/play/<filename>` — unrelated to commerce, but it is part of the running app.

**Payments (`app/views.py`, `app/paypal_client.py`).**

- *PayPal* — `/handle_payments` obtains an OAuth token, creates an order and redirects to the PayPal approval page; `/payment_success` captures it; `/payment_cancel` and a `/webhook` endpoint exist. All URLs are hardcoded to `api.sandbox.paypal.com` / `www.sandbox.paypal.com`.
- *M-Pesa* — `/mpesa/stk_push` builds the Daraja STK push password as `base64(shortcode + passkey + timestamp)` and posts to `https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest`. `/mpesa/callback` parses the STK callback and pulls out the receipt number.
- *Airtel Money* — `/airtel/pay` fetches an OAuth token and posts to `{AIRTEL_MONEY_API_URL}/merchant/v2/payments/`, signing the payload with an HMAC (`x-signature`). `/airtel-money/callback` verifies the signature. Configured against Airtel's UAT host.

**Auth (`app/auth.py`).** Signup, login, logout, profile view with picture upload, and change-password. Passwords are hashed with Werkzeug (`generate_password_hash` / `check_password_hash`); sessions via Flask-Login.

**Admin (`app/admin.py`).** Add / list / update / delete shop items, view and update orders, list customers, and an admin landing page. Authorisation is `@login_required` plus an inline `if current_user.id == 1` check — whoever holds customer row 1 is the admin.

**Data model (`app/models.py`).** `Customer`, `Product` (name, current/previous price, stock, picture, flash-sale flag), `Cart`, `Order` (quantity, price, status, payment id).

## Tech stack

From `requirements.txt`:

- `Flask==3.1.0`, `Flask-Login==0.6.3`, `flask_sqlalchemy` (unpinned), `flask_wtf` (unpinned), `SQLAlchemy==2.0.37`, `Werkzeug==3.1.3`, `Jinja2==3.1.5`
- `gunicorn==23.0.0`, `requests==2.32.3`, `python-dotenv==1.0.1`, `Faker==35.2.0`
- SQLite (`instance/database.sqlite3`), Bootstrap + Font Awesome in the templates
- `Dockerfile`: `python:3.11-slim`, serves `gunicorn --bind 0.0.0.0:80 main:app`

## Setup and running

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py                              # Flask dev server
# or
gunicorn --bind 0.0.0.0:8000 main:app
```

Docker:

```bash
docker build -t online-store .
docker run -p 80:80 online-store
```

No migrations. `create_app()` calls `db.create_all()` on startup, which creates `instance/database.sqlite3`.

Environment variables, read via `load_dotenv()` at the top of `app/views.py`:

| Variable | Used for |
| --- | --- |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_API_URL` | PayPal REST |
| `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET` | Daraja OAuth |
| `MPESA_SHORTCODE`, `MPESA_PASSKEY`, `MPESA_CALLBACK_URL` | STK push |
| `AIRTEL_MONEY_CLIENT_ID`, `AIRTEL_MONEY_CLIENT_SECRET`, `AIRTEL_MONEY_API_URL`, `AIRTEL_MONEY_CALLBACK_URL`, `AIRTEL_MONEY_HASH_KEY` | Airtel Money |

Two caveats about configuration, both verifiable in the code:

- `SECRET_KEY` and `SQLALCHEMY_DATABASE_URI` are **hardcoded** in `app/__init__.py`. The values of the same names in `.env` are read into module-level variables in `views.py` and then never applied to `app.config`, so setting them has no effect.
- The callback URLs default to a specific Render deployment. Payment callbacks will not reach a local instance without changing them and exposing the app publicly.

## Status

Deployed prototype. One commit, dated 2026-02-12. The site is/was live at `https://online-store-soch.onrender.com`.

Working: catalogue, search, cart, signup/login/profile, admin CRUD, and the three payment integrations against sandbox endpoints. The local `instance/database.sqlite3` holds 108 products and a single admin account.

Unfinished or broken:

- **CSRF protection is not active.** `main.py` does `csrf = CSRFProtect()` but never calls `csrf.init_app(app)`, so the extension is instantiated and discarded. Flask-WTF forms are used throughout, so this is almost certainly not intentional.
- `SECRET_KEY` is a hardcoded literal in source, so session cookies on any public deployment are forgeable.
- A populated `.env` with live-looking payment API credentials sits in the working directory. It is **not** tracked — `.gitignore` covers `.env` and it does not appear anywhere in git history — but it is present on any machine that has this checkout. See the note below.
- Admin authorisation is `current_user.id == 1`, not a role flag.
- There is a commented-out duplicate `/orders` view in `views.py` (line ~315) left in place.
- Airtel `AIRTEL_MONEY_CLIENT_ID` and `AIRTEL_MONEY_CLIENT_SECRET` in `.env` are the same UUID, which looks like a placeholder rather than a working credential pair. TODO: verify with the author whether the Airtel path was ever exercised.
- No tests, no CI.
- TODO: verify — the app was not launched while writing this README.

## Note on committed files

Checked against `git ls-files` on the single commit in this repository:

- `.env` is **not** committed and never has been — `.gitignore` covers `.env`, `.env.*`, `*.pem`, `*.key`, `*.db`, `*.sqlite3` and `instance/`. The populated `.env` in a local checkout is a local-machine exposure only.
- `instance/database.sqlite3` **is** committed (it predates the `instance/` ignore rule). It holds 108 products, 2 cart rows and one customer account — the admin — including that account's email and Werkzeug password hash.
- `SECRET_KEY` is a hardcoded literal in `app/__init__.py`, so it is public regardless of `.env`.
- 271 product photographs are committed (152 under `app/static/images/`, 119 under `media/`); many are filenames lifted from third-party retail listings.
- Ten full-length commercial worship tracks (`.m4a`, Elevation Worship / Maverick City and similar) are committed under `app/static/media/` and streamed by the `/play/<filename>` route. These are copyrighted recordings.

The image and audio files are a licensing problem rather than a secrets problem, but they should be reviewed before this repository stays public.

## License

GPL-3.0 (`LICENSE`).
