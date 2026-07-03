"""
ShopZen Backend API  (production layout: MySQL on RDS + email notifications)
------------------------------------------------------------------------------
Runs on its own EC2 instance. Talks to a MySQL RDS instance for data and to
an SMTP server for email notifications. The frontend (served separately by
Nginx on a different EC2) reverse-proxies `/api/*` requests here.

Endpoints:
  GET  /api/health                      -> liveness check (point your ALB/target-group health check here)
  GET  /api/categories                  -> list all categories
  GET  /api/products?category=<slug>    -> list products (optionally filtered)
  GET  /api/products/<id>               -> single product
  GET  /api/products/search?q=<term>    -> search products by name

  POST /api/auth/signup                 -> {name, email, password} -> creates account, logs in, sends welcome email
  POST /api/auth/login                  -> {email, password} -> logs in, sends "new login" email
  POST /api/auth/logout                 -> clears the session
  GET  /api/auth/me                     -> current logged-in user, or 401

  GET  /api/cart                        -> current user's cart              [login required]
  POST /api/cart                        -> add item {product_id, quantity}  [login required]
  PUT  /api/cart/<product_id>           -> update quantity {quantity}       [login required]
  DELETE /api/cart/<product_id>         -> remove item                      [login required]
  DELETE /api/cart                      -> clear cart                      [login required]
  POST /api/checkout                    -> place an order, sends confirmation email [login required]

Authentication uses Flask's signed session cookie (no separate sessions
table needed) -- the cookie is HttpOnly + SameSite=Lax and signed with
SECRET_KEY, so it can't be read or forged by JavaScript or a third party.
Because the frontend is reverse-proxied through Nginx onto the SAME origin
as this API (see /nginx/shopzen.conf), the cookie works normally with no
CORS complications.
"""

import os
import re
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - CORS is optional; not needed when
    CORS = None       # Nginx reverse-proxies frontend+backend to one origin.

# ── Config ──────────────────────────────────────────────────────────
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
PORT = int(os.getenv("PORT", "5000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "shopzen")

MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "ShopZen")
MAIL_ENABLED = bool(MAIL_USERNAME and MAIL_PASSWORD)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
# Cookie hardening -- adjust SESSION_COOKIE_SECURE to True once you're on HTTPS.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

if CORS is not None and CORS_ORIGINS != "*":
    # Only needed if you call the API from a different origin than the
    # frontend is served from (i.e. you are NOT using the Nginx reverse
    # proxy setup described in nginx/shopzen.conf).
    CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS.split(",")}}, supports_credentials=True)


# ── Database helpers ────────────────────────────────────────────────
def get_db():
    """Open a fresh MySQL connection for this request.

    PyMySQL connections are lightweight and not safely shared across
    threads, so (unlike the old SQLite version) we open/close one per
    request rather than caching it on `g`. For higher traffic, swap this
    for a connection pool (e.g. DBUtils' PooledDB or SQLAlchemy).
    """
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=5,
    )


def row_to_product(row):
    return {
        "id": row["id"],
        "category_id": row["category_id"],
        "emoji": row["emoji"],
        "name": row["name"],
        "price": row["price"],
        "original": row["original"],
        "rating": float(row["rating"]) if row["rating"] is not None else None,
        "reviews": row["reviews"],
        "badge": row["badge"],
        "off": row["off_pct"],
        "stock": row["stock"],
    }


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Email helper (best-effort, non-blocking) ──────────────────────────
def _send_email_now(to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_USERNAME}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as server:
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, [to_email], msg.as_string())


def send_email(to_email, subject, html_body):
    """Fire-and-forget email send on a background thread.

    Never let a slow/broken SMTP server block or fail an API response --
    login and checkout must still succeed even if the email fails to send.
    Errors are printed to the Flask log for visibility.
    """
    if not MAIL_ENABLED:
        app.logger.warning("MAIL_USERNAME/MAIL_PASSWORD not set -- skipping email to %s", to_email)
        return

    def _worker():
        try:
            _send_email_now(to_email, subject, html_body)
        except Exception as exc:  # noqa: BLE001 - log and move on, never crash the request
            app.logger.error("Failed to send email to %s: %s", to_email, exc)

    threading.Thread(target=_worker, daemon=True).start()


def send_login_email(user):
    send_email(
        user["email"],
        "New sign-in to your ShopZen account",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto">
          <h2 style="color:#0f1923">Hi {user['name']},</h2>
          <p>We noticed a new sign-in to your ShopZen account.</p>
          <p>If this was you, no action is needed. If you don't recognize this
          activity, please change your password immediately.</p>
          <p style="color:#8c8078;font-size:12px;margin-top:24px">— The ShopZen Team</p>
        </div>
        """,
    )


def send_welcome_email(user):
    send_email(
        user["email"],
        "Welcome to ShopZen 🎉",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto">
          <h2 style="color:#0f1923">Welcome, {user['name']}!</h2>
          <p>Your ShopZen account has been created successfully. Start exploring
          categories and add your favorites to the cart.</p>
          <p style="color:#8c8078;font-size:12px;margin-top:24px">— The ShopZen Team</p>
        </div>
        """,
    )


def send_order_confirmation_email(user, order_id, items, total):
    rows_html = "".join(
        f"<tr><td style='padding:6px 0'>{i['emoji']} {i['name']} × {i['quantity']}</td>"
        f"<td style='padding:6px 0;text-align:right'>₹{i['price'] * i['quantity']:,}</td></tr>"
        for i in items
    )
    send_email(
        user["email"],
        f"Order Confirmed — #ShopZen{order_id}",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto">
          <h2 style="color:#0f1923">Thanks for your order, {user['name']}!</h2>
          <p>Your order <strong>#ShopZen{order_id}</strong> has been placed successfully.</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">{rows_html}</table>
          <div style="border-top:2px solid #eee;padding-top:8px;display:flex;justify-content:space-between;font-weight:bold">
            <span>Total</span><span>₹{total:,}</span>
          </div>
          <p style="color:#8c8078;font-size:12px;margin-top:24px">— The ShopZen Team</p>
        </div>
        """,
    )


# ── Auth helpers ────────────────────────────────────────────────────
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def current_user_row(db):
    if "user_id" not in session:
        return None
    with db.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users WHERE id=%s", (session["user_id"],))
        return cur.fetchone()


# ── API: health ─────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "shopzen-api"})


# ── API: auth ────────────────────────────────────────────────────────
@app.post("/api/auth/signup")
def signup():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({"error": "An account with this email already exists"}), 409

            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password)),
            )
            db.commit()
            user_id = cur.lastrowid

        session["user_id"] = user_id
        user = {"id": user_id, "name": name, "email": email}
        send_welcome_email(user)
        return jsonify({"message": "Account created", "user": user}), 201
    finally:
        db.close()


@app.post("/api/auth/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, name, email, password_hash FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            return jsonify({"error": "Invalid email or password"}), 401

        session["user_id"] = row["id"]
        user = {"id": row["id"], "name": row["name"], "email": row["email"]}
        send_login_email(user)
        return jsonify({"message": "Logged in", "user": user})
    finally:
        db.close()


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.get("/api/auth/me")
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    db = get_db()
    try:
        user = current_user_row(db)
        if not user:
            session.clear()
            return jsonify({"error": "Not logged in"}), 401
        return jsonify({"user": user})
    finally:
        db.close()


# ── API: categories ─────────────────────────────────────────────────
@app.get("/api/categories")
def list_categories():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM categories ORDER BY id")
            rows = cur.fetchall()
        return jsonify(rows)
    finally:
        db.close()


# ── API: products ────────────────────────────────────────────────────
@app.get("/api/products")
def list_products():
    category_slug = request.args.get("category")
    db = get_db()
    try:
        with db.cursor() as cur:
            if category_slug and category_slug != "main":
                cur.execute(
                    """
                    SELECT p.* FROM products p
                    JOIN categories c ON c.id = p.category_id
                    WHERE c.slug = %s
                    ORDER BY p.id
                    """,
                    (category_slug,),
                )
            else:
                cur.execute("SELECT * FROM products ORDER BY id")
            rows = cur.fetchall()
        return jsonify([row_to_product(r) for r in rows])
    finally:
        db.close()


@app.get("/api/products/search")
def search_products():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE name LIKE %s ORDER BY id", (f"%{q}%",))
            rows = cur.fetchall()
        return jsonify([row_to_product(r) for r in rows])
    finally:
        db.close()


@app.get("/api/products/<int:product_id>")
def get_product(product_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            row = cur.fetchone()
        if row is None:
            return jsonify({"error": "Product not found"}), 404
        return jsonify(row_to_product(row))
    finally:
        db.close()


# ── API: cart (requires login) ─────────────────────────────────────────
@app.get("/api/cart")
@login_required
def get_cart():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT ci.product_id, ci.quantity, p.name, p.price, p.emoji
                FROM cart_items ci
                JOIN products p ON p.id = ci.product_id
                WHERE ci.user_id = %s
                """,
                (session["user_id"],),
            )
            items = cur.fetchall()
        total = sum(i["price"] * i["quantity"] for i in items)
        return jsonify({"items": items, "total": total, "count": sum(i["quantity"] for i in items)})
    finally:
        db.close()


@app.post("/api/cart")
@login_required
def add_to_cart():
    data = request.get_json(force=True, silent=True) or {}
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))
    if not product_id:
        return jsonify({"error": "product_id is required"}), 400

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
                (session["user_id"], product_id, quantity),
            )
        db.commit()
        return jsonify({"message": "added"}), 201
    finally:
        db.close()


@app.put("/api/cart/<int:product_id>")
@login_required
def update_cart_item(product_id):
    data = request.get_json(force=True, silent=True) or {}
    quantity = int(data.get("quantity", 1))
    db = get_db()
    try:
        with db.cursor() as cur:
            if quantity <= 0:
                cur.execute(
                    "DELETE FROM cart_items WHERE user_id=%s AND product_id=%s",
                    (session["user_id"], product_id),
                )
            else:
                cur.execute(
                    "UPDATE cart_items SET quantity=%s WHERE user_id=%s AND product_id=%s",
                    (quantity, session["user_id"], product_id),
                )
        db.commit()
        return jsonify({"message": "updated"})
    finally:
        db.close()


@app.delete("/api/cart/<int:product_id>")
@login_required
def remove_cart_item(product_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "DELETE FROM cart_items WHERE user_id=%s AND product_id=%s",
                (session["user_id"], product_id),
            )
        db.commit()
        return jsonify({"message": "removed"})
    finally:
        db.close()


@app.delete("/api/cart")
@login_required
def clear_cart():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM cart_items WHERE user_id=%s", (session["user_id"],))
        db.commit()
        return jsonify({"message": "cleared"})
    finally:
        db.close()


# ── API: checkout (requires login, sends confirmation email) ──────────
@app.post("/api/checkout")
@login_required
def checkout():
    data = request.get_json(force=True, silent=True) or {}
    payment_method = data.get("payment_method", "ShopZen Pay")
    user_id = session["user_id"]

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT ci.product_id, ci.quantity, p.price, p.name, p.emoji
                FROM cart_items ci JOIN products p ON p.id = ci.product_id
                WHERE ci.user_id = %s
                """,
                (user_id,),
            )
            items = cur.fetchall()
            if not items:
                return jsonify({"error": "Cart is empty"}), 400

            total = sum(i["price"] * i["quantity"] for i in items)
            cur.execute(
                "INSERT INTO orders (user_id, total_amount, payment_method) VALUES (%s, %s, %s)",
                (user_id, total, payment_method),
            )
            order_id = cur.lastrowid
            for i in items:
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)",
                    (order_id, i["product_id"], i["quantity"], i["price"]),
                )
            cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
            user = current_user_row(db)
        db.commit()

        send_order_confirmation_email(user, order_id, items, total)
        return jsonify({"message": "order placed", "order_id": order_id, "total": total}), 201
    finally:
        db.close()


if __name__ == "__main__":
    # Local/dev only. In production this app is run via Gunicorn
    # (see deploy/shopzen-backend.service) -- app.run() is never used there.
    app.run(debug=DEBUG, port=PORT, host="0.0.0.0")
