# ShopZen — Full-Stack E-Commerce App (Production Architecture)

ShopZen is a multi-page e-commerce app: a Flask + MySQL (RDS) REST API with
real authentication and email notifications, powering nine frontend pages
served by Nginx.

> **For step-by-step AWS deployment** (2 EC2 instances + RDS + Nginx reverse
> proxy), see **[`DEPLOYMENT.md`](./DEPLOYMENT.md)**. This README covers what
> the app does and how the pieces fit together.

---

## Architecture

```
Browser ──HTTP──▶ Frontend EC2 (Nginx)
                     ├─ serves frontend/ static files
                     └─ reverse-proxies /api/* ──▶ Backend EC2 (Gunicorn + Flask)
                                                        └─ MySQL ──▶ RDS
```

The browser only ever talks to the frontend's Nginx. Because `/api/*` is
reverse-proxied onto the *same origin* as the frontend, there's no CORS to
configure and the login session cookie works normally. See
`nginx/shopzen.conf` for the exact config.

---

## What the app does

- **Sign up / log in** — real accounts, passwords hashed with Werkzeug
  (never stored in plain text)
- **Browse** — 8 product categories, all public, no login required
- **Add to cart** — requires login; cart is stored server-side in MySQL,
  tied to your account (not a cookie/localStorage gimmick — it's a real
  per-user cart)
- **Checkout** — "Pay Now" on the ShopZen Pay page creates a real order row
  in the database and empties the cart
- **Email notifications** — sent automatically for:
  - New account created (welcome email)
  - Every login (security notification)
  - Every order placed (confirmation with itemized total)

Emails are sent on a background thread — if your SMTP server is slow or
misconfigured, it's logged as a warning but never blocks or breaks the
actual login/checkout request.

---

## 🗂 Project Structure

```
Projectaws/
├── README.md
├── DEPLOYMENT.md              # full AWS deployment walkthrough
├── nginx/
│   └── shopzen.conf            # reverse proxy config for the frontend EC2
├── deploy/
│   └── shopzen-backend.service # systemd unit to run the backend via Gunicorn
├── backend/
│   ├── .env                    # DB + mail + secret key config
│   ├── app.py                  # Flask API: auth, products, cart, checkout, email
│   ├── requirements.txt
│   └── test.sql                # MySQL schema + seed data (run manually against RDS)
└── frontend/
    ├── auth/                   # login.html, signup.html
    ├── main/                   # Homepage — categories, best sellers, deals
    ├── computers/ | earphones/ | electronics/ | phones/
    ├── googleclothes/ | googlegrocery/ | googlemusic/
    └── googlepay/               # Wallet + real checkout (calls /api/checkout)
```

Each category folder contains `index.html`, `script.js`, `style.css`, and
`scan.jpg` — same structure as before. `auth/` follows the same pattern
minus the product banner image.

---

## ⚙️ Backend

### Setup (see DEPLOYMENT.md for the full AWS version)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Fill in `backend/.env` — see the comments in that file for what each value
means. You'll need:
- A MySQL RDS endpoint, user, and password
- A `SECRET_KEY` (generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`)
- SMTP credentials (Gmail App Password, or Amazon SES)

Load the schema once against your database:
```bash
mysql -h <RDS_ENDPOINT> -u <DB_USER> -p <DB_NAME> < test.sql
```

Run it locally for testing:
```bash
python3 app.py
```
In production, it's run via Gunicorn under systemd — see
`deploy/shopzen-backend.service` and `DEPLOYMENT.md`.

### API Reference

| Method | Endpoint | Auth required? | Description |
|---|---|---|---|
| GET | `/api/health` | No | Liveness check — point your health check here |
| GET | `/api/categories` | No | List all categories |
| GET | `/api/products?category=<slug>` | No | List products (optionally filtered) |
| GET | `/api/products/<id>` | No | Get a single product |
| GET | `/api/products/search?q=<term>` | No | Search products by name |
| POST | `/api/auth/signup` | No | `{name, email, password}` → creates account, logs in, sends welcome email |
| POST | `/api/auth/login` | No | `{email, password}` → logs in, sends login notification email |
| POST | `/api/auth/logout` | No | Clears the session |
| GET | `/api/auth/me` | Yes | Current logged-in user, or `401` |
| GET | `/api/cart` | Yes | Get your cart |
| POST | `/api/cart` | Yes | Add item `{product_id, quantity}` |
| PUT | `/api/cart/<product_id>` | Yes | Update quantity `{quantity}` |
| DELETE | `/api/cart/<product_id>` | Yes | Remove one item |
| DELETE | `/api/cart` | Yes | Clear the cart |
| POST | `/api/checkout` | Yes | Place an order, sends confirmation email |

"Auth required" routes return `401 {"error": "Login required"}` if you're
not logged in — the frontend automatically redirects to the login page
when this happens (see `addToCart()` / `requireLoginOrRedirect()` in any
`script.js`).

---

## 🖥 Frontend

Plain HTML/CSS/JS, no build step. Every internal link uses **absolute**
paths (`/frontend/computers/index.html`, `/frontend/main/style.css`, etc.)
rather than relative ones — this matters because it lets Nginx (or Flask,
in local dev) serve `/` directly without a redirect, which keeps load
balancer health checks happy while still resolving every asset correctly
regardless of which page you're on.

### Auth-aware shared shell

Every page's `script.js` starts with the same shared block of functions
(`renderShell`, `renderFooter`, `checkAuth`, cart drawer logic,
`fetchProducts`) so the navbar, login state, and cart behave identically
everywhere:

- On load, every page calls `checkAuth()` (`GET /api/auth/me`) to find out
  if you're logged in, and shows either "Hello, Sign In" or
  "Hello, `<your name>`" in the top nav accordingly.
- `addToCart()` checks login state first — if you're not logged in, it
  redirects you to `/frontend/auth/login.html?next=<current page>`, and
  sends you right back after you sign in.
- The cart drawer and the ShopZen Pay checkout page both read the cart
  live from `/api/cart` — there's no separate client-side cart to keep in
  sync, it's a single source of truth in MySQL.

### Category pages

`computers`, `earphones`, `electronics`, `phones`, `googleclothes`,
`googlegrocery`, `googlemusic` — each fetches its products from
`/api/products?category=<slug>`, with a bundled static fallback so the
page still renders something even if the API is briefly unreachable
(though cart/checkout always require the real backend).

### `googlepay` — wallet + checkout

Shows a simulated wallet balance and saved payment methods (client-side
only — not tied to a real payment processor), but the **Pay Now** button
calls the real `/api/checkout` endpoint, which creates an actual order row
and triggers the confirmation email.

---

## 🗄 Database Schema (`test.sql`)

| Table | Purpose |
|---|---|
| `users` | Accounts — name, email, hashed password |
| `categories` | One row per frontend folder |
| `products` | All product listings |
| `cart_items` | Per-user cart, `UNIQUE(user_id, product_id)` so adding the same item twice just increments quantity |
| `orders` / `order_items` | Created by `/api/checkout`; `order_items` snapshots the price paid at that moment |

Re-run at any time to reset all data (⚠️ this drops and recreates every table):
```bash
mysql -h <RDS_ENDPOINT> -u <DB_USER> -p <DB_NAME> < backend/test.sql
```

---

## 🚀 Next Steps / Ideas

- Add a "My Orders" page reading from the `orders`/`order_items` tables
- Move `DB_PASSWORD`/`MAIL_PASSWORD` into AWS Secrets Manager instead of `.env`
- Add HTTPS (ACM + ALB, or Let's Encrypt on the frontend EC2) and flip
  `SESSION_COOKIE_SECURE=1`
- Switch Gmail SMTP to Amazon SES for production email deliverability
- Add password reset (forgot-password email flow)

---

## 📄 License

Demo project for educational purposes.
