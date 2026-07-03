# ShopZen — Production Deployment Guide

Architecture:

```
                        ┌─────────────────────────┐
   Browser  ──HTTP──▶   │  FRONTEND EC2 (Nginx)   │
                        │  serves static files    │
                        │  reverse-proxies /api/  │──┐
                        └─────────────────────────┘  │
                                                       │ private network
                        ┌─────────────────────────┐  │ (port 5000)
                        │  BACKEND EC2 (Gunicorn  │◀─┘
                        │  + Flask app.py)        │
                        └───────────┬─────────────┘
                                    │ private network (port 3306)
                        ┌───────────▼─────────────┐
                        │   RDS  (MySQL/MariaDB)  │
                        └─────────────────────────┘
```

The browser only ever talks to the **frontend** EC2. Nginx there serves
static files directly and reverse-proxies `/api/*` to the backend EC2 over
the private network — the backend and RDS are never exposed to the public
internet at all. This is both more secure and avoids CORS entirely (see the
comments in `nginx/shopzen.conf`).

---

## 0. Before you start

Run all three of these in your own terminal now, not this guide's placeholders:

```bash
# generate a real SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Also have ready: your Gmail address + an **App Password** (Google Account →
Security → 2-Step Verification → App Passwords) — don't use your normal
Gmail password, it won't work with SMTP and shouldn't be used here anyway.

---

## 1. RDS (MySQL/MariaDB)

1. **RDS Console → Create database**
   - Engine: MySQL (or MariaDB)
   - Templates: Free tier (for testing) or Production
   - DB instance identifier: `shopzen-db`
   - Master username: e.g. `admin`
   - Master password: set a strong one — you'll put this in the backend's `.env`
   - **Public access: No** (keep it private — only the backend EC2 should reach it)
   - VPC: same VPC you'll launch both EC2 instances into
   - Initial database name: `shopzen`

2. **Security group for RDS** — after creation, edit its security group:
   - Inbound rule: `MySQL/Aurora (3306)` — Source: the **backend EC2's security group** (not an IP range; select the SG by name so it stays correct even if the EC2's IP changes)

3. **Load the schema** — once the backend EC2 is up (step 2) and can reach RDS:
   ```bash
   mysql -h <RDS_ENDPOINT> -u admin -p shopzen < backend/test.sql
   ```
   (Run this from the backend EC2, or from your own machine if you temporarily
   allow your IP in the RDS security group — remove that rule again afterward.)

---

## 2. Backend EC2

1. **Launch an EC2 instance** (Amazon Linux 2023 or Ubuntu), e.g. `t3.small`.
   - Security group inbound rules:
     - `SSH (22)` from your IP (for management)
     - `Custom TCP (5000)` from the **frontend EC2's security group** (not from the internet — only Nginx should reach this)

2. **Install dependencies:**
   ```bash
   sudo yum update -y                     # (or apt update && apt upgrade -y on Ubuntu)
   sudo yum install -y python3 python3-pip git mysql   # mysql client, for loading test.sql
   ```

3. **Upload the backend code** (from your local machine):
   ```bash
   scp -r Projectaws/backend ec2-user@<BACKEND_PUBLIC_IP>:/home/ec2-user/Projectaws/backend
   ```

4. **Set up the Python environment:**
   ```bash
   cd /home/ec2-user/Projectaws/backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Edit `.env`** with your real values:
   ```bash
   nano .env
   ```
   Fill in:
   - `SECRET_KEY` — the random value you generated in step 0
   - `DB_HOST` — your RDS endpoint (RDS Console → your DB → "Endpoint")
   - `DB_PASSWORD` — your RDS master password
   - `MAIL_USERNAME` / `MAIL_PASSWORD` — your Gmail address + App Password
   - Leave `FLASK_DEBUG=0` in production

6. **Load the database schema** (see step 1.3 above) if you haven't already.

7. **Test it manually first**, before wiring up systemd:
   ```bash
   source venv/bin/activate
   python3 app.py
   ```
   From another terminal on the same instance:
   ```bash
   curl http://localhost:5000/api/health
   curl http://localhost:5000/api/categories
   ```
   Both should return JSON. Fix any DB connection errors here before moving on
   (common cause: RDS security group not yet allowing this EC2's SG). Stop it
   with `Ctrl+C` once confirmed.

8. **Run it permanently with Gunicorn + systemd:**
   ```bash
   pip install gunicorn   # already in requirements.txt, but confirm it's installed
   sudo cp /home/ec2-user/Projectaws/deploy/shopzen-backend.service /etc/systemd/system/
   sudo nano /etc/systemd/system/shopzen-backend.service   # fix paths/user if different
   sudo systemctl daemon-reload
   sudo systemctl enable shopzen-backend
   sudo systemctl start shopzen-backend
   sudo systemctl status shopzen-backend
   ```
   Check logs any time with:
   ```bash
   sudo journalctl -u shopzen-backend -f
   ```

9. **Note this instance's private IP** (EC2 Console → Instances → your backend
   instance → "Private IPv4 address"). You'll need it for the Nginx config.

---

## 3. Frontend EC2

1. **Launch a second EC2 instance**, in the same VPC.
   - Security group inbound rules:
     - `SSH (22)` from your IP
     - `HTTP (80)` from `0.0.0.0/0` (public — this is the one users actually hit)
     - (add `HTTPS (443)` too once you set up a certificate)

2. **Install Nginx:**
   ```bash
   sudo yum install -y nginx      # Amazon Linux
   # or: sudo apt install -y nginx   (Ubuntu)
   sudo systemctl enable nginx
   ```

3. **Upload the frontend files:**
   ```bash
   scp -r Projectaws/frontend ec2-user@<FRONTEND_PUBLIC_IP>:/tmp/frontend
   ```
   Then on the frontend EC2:
   ```bash
   sudo mkdir -p /var/www/shopzen
   sudo mv /tmp/frontend /var/www/shopzen/frontend
   sudo chown -R nginx:nginx /var/www/shopzen    # or www-data:www-data on Ubuntu
   ```

4. **Install the Nginx config:**
   ```bash
   sudo cp /path/to/nginx/shopzen.conf /etc/nginx/conf.d/shopzen.conf
   sudo nano /etc/nginx/conf.d/shopzen.conf
   ```
   Replace the two placeholders:
   - `<YOUR_DOMAIN_OR_PUBLIC_IP>` → this EC2's public IP or your domain name
   - `<BACKEND_PRIVATE_IP>` → the backend EC2's private IP from step 2.9

5. **Test and reload Nginx:**
   ```bash
   sudo nginx -t          # should say "syntax is ok" / "test is successful"
   sudo systemctl restart nginx
   ```

6. **Verify end-to-end** from your own machine:
   ```bash
   curl http://<FRONTEND_PUBLIC_IP>/                      # should return the homepage HTML
   curl http://<FRONTEND_PUBLIC_IP>/api/health             # should return {"status":"ok",...} via the proxy
   ```
   Then open `http://<FRONTEND_PUBLIC_IP>/` in a browser and try signing up.

---

## 4. Verifying the full user flow

1. Open the site → click **Sign In** → **Create an account**
2. Sign up with a real email address you can check
3. **Check that inbox** — you should receive a "Welcome to ShopZen" email
4. Browse a category, add a couple of items to the cart
5. Open the cart drawer, click **Proceed to ShopZen Pay**
6. Click **Pay Now**
7. **Check your inbox again** — you should receive an "Order Confirmed" email
8. Log out, log back in — you should receive a "New sign-in" email each time

If an email doesn't arrive:
```bash
sudo journalctl -u shopzen-backend -f
```
Emails are sent on a background thread and failures are logged but never
crash the request — so check the backend logs for the actual SMTP error
(most common cause: wrong App Password, or Gmail blocking the login — see
Google's "less secure app" / App Password documentation).

---

## 5. Common issues

| Symptom | Likely cause |
|---|---|
| Frontend loads but `/api/...` calls fail | Nginx `proxy_pass` IP wrong, or backend EC2 security group doesn't allow port 5000 from the frontend's SG |
| Signup/login works but no email arrives | Wrong `MAIL_PASSWORD` (must be a Gmail **App Password**, not your account password), or check `sudo journalctl -u shopzen-backend` for the SMTP error |
| `Access denied for user...` in backend logs | `DB_USER`/`DB_PASSWORD` in `.env` don't match RDS master credentials |
| `Can't connect to MySQL server` | RDS security group doesn't allow the backend EC2's security group on port 3306 |
| Cart says "Login required" even after logging in | Cookie not being sent — confirm you're accessing the site through the **frontend EC2's** URL (not the backend's IP directly), so the reverse proxy keeps everything same-origin |
| Load balancer/health check shows unhealthy | Health check should hit `/api/health` on the **backend**, and `/` on the **frontend** — both must return `200` directly, not a redirect |

---

## 6. Going further (optional hardening)

- Put an **Application Load Balancer** in front of the frontend EC2 (or use
  an Auto Scaling Group of frontend instances behind one) for redundancy.
- Add an SSL certificate (AWS Certificate Manager + ALB, or Let's Encrypt +
  Nginx directly) and set `SESSION_COOKIE_SECURE=1` in the backend `.env`
  once everything is served over HTTPS.
- Replace Gmail SMTP with **Amazon SES** for production-grade email deliverability.
- Move `DB_PASSWORD` and `MAIL_PASSWORD` out of the `.env` file and into
  **AWS Secrets Manager** or **SSM Parameter Store**, injected at instance
  boot instead of stored in a plaintext file.
- Put RDS in **Multi-AZ** mode for automatic failover.
