# Latifa's Journal ✳

An original **dynamic website** built for **Khalifa University — CCEN 448 Cloud Infrastructure & Services, Lab Exercise 6 (Fall 2026)** by **Latifa Alnuaimi**.

A warm, responsive private journal app where visitors can create accounts, log in, write/edit/delete notes, and search/filter their notes. It uses **Flask** for server-side logic, **password hashing and authenticated sessions**, and a real **SQL database** for persistent data.

## Features

- 🌷 Original responsive design (HTML, CSS and a little JavaScript)
- 🔐 Register, log in, and log out; passwords are hashed, not stored as plain text
- 📝 Create, edit, delete, search and filter private journal notes
- 💾 SQLite database for the basic lab; optional shared MySQL database for extra credit
- 🔎 Health check at `/health` for load balancer and database checks
- 🖥️ Every response includes `X-Served-By` and the page footer shows its server name for failover demonstration
- 🛡️ CSRF tokens on all modifying forms and author checks on private notes
- 🌐 Runs on port **8000**, matching the Lab 6 reference deployment

## Folder structure

```text
latifa-journal/
├── app.py                 # Flask app, authentication, note CRUD, database models
├── requirements.txt       # Python packages
├── .env.example           # Optional local settings (no secrets here)
├── .gitignore             # Keeps secrets, private keys, database out of GitHub
├── README.md              # Instructions
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── auth.html
│   ├── dashboard.html
│   ├── note_form.html
│   └── error.html
└── static/
    ├── css/style.css
    └── js/main.js
```

## 1. Run it on your Mac

Open Terminal **inside this folder** and run these commands, one at a time:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Go to **http://127.0.0.1:8000** and try **Get started → Create account → Write a note**.

Press `Control + C` to stop the server.

**Note:** SQLite automatically creates `instance/journal.sqlite3` on the first launch. This folder is ignored by Git and must not be pushed to GitHub.

## 2. Upload to your own PUBLIC GitHub repository

1. Sign in to GitHub and select **New repository**.
2. Name it `latifa-journal` and set visibility to **Public**.
3. On your Mac, unzip this project (if downloaded as ZIP).
4. In GitHub's repository, choose **Add file → Upload files**.
5. Select the **contents inside** the `latifa-journal` folder: `app.py`, `requirements.txt`, `README.md`, `templates/`, and `static/` (and optionally `.env.example` and `.gitignore`). GitHub's browser upload may not include hidden files.
6. Commit the changes. Verify your repo contains `app.py` at the **root** level (not inside another `latifa-journal` folder).
7. Copy the public repository HTTPS URL for later deployment. **Do not add any AWS credentials, .pem files, .env, or local database.**

For the lab report **Figure 5**, screenshot your public repo page showing the `app.py`, `templates`, `static`, and `requirements.txt` files.

## 3. Deploy on Amazon Lightsail (Task 3; later)

The professor provides `lightsail-website.tf` on Blackboard. Use **that file** for provisioning; do not invent a replacement template.

Your OpenTofu template should clone the **public** repository into `/opt/website`. On the Ubuntu server, the Python app can then be installed with:

```bash
cd /opt/website
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Visit `http://YOUR_LIGHTSAIL_STATIC_IP:8000` while public website access is enabled. For a persistent server, use Gunicorn and systemd (we can configure these once your actual instance is available):

```bash
cd /opt/website
.venv/bin/gunicorn --bind 0.0.0.0:8000 --workers 2 app:app
```

> The project runs on port **8000**. Use the same port when editing the supplied OpenTofu template, the SSH port-forward command, and the Cloudflare Quick Tunnel instructions.

## 4. Where the database and authentication run (Task 2 written answer)

Flask runs the website's server-side code and authentication. Passwords are hashed using Werkzeug, and SQLAlchemy manages the SQLite database storing users and notes. In the basic Lightsail deployment, Flask and SQLite both run on the Ubuntu Lightsail instance. **Unlike Amazon S3 static website hosting from Lab 5, S3 serves files but cannot run Python login routes or execute these database queries.**

## 5. Extra Credit #1: Direct HTTPS

The Flask application is designed to work **behind Nginx** on the Lightsail instance. Keep the application bound to port 8000 and configure Nginx to proxy traffic from **port 443** to `127.0.0.1:8000`. Obtain a Let's Encrypt **IP address certificate** using a Certbot version that supports short-lived IP certificates, set up renewal, and verify the certificate. Configure public HTTP port 80 for ACME validation as required, and HTTPS port 443. These are **infrastructure setup tasks**, not automatic features of this repository.

## 6. Extra Credit #2: Two web servers + shared database

This app supports a shared MySQL database, so both copies of the site can use the **same users and notes**:

1. Create a private shared **MySQL** database reachable from your web instances.
2. On **both** instances set `DATABASE_URL` to the **same** MySQL database connection string.
3. On **both** instances set **exactly the same** strong `SECRET_KEY` (needed to validate login session cookies across servers).
4. Set `INSTANCE_LABEL=web-a` on one instance, and `INSTANCE_LABEL=web-b` on the other.
5. Use Ansible to deploy requirements and the app to both servers; use OpenTofu to create the cloud resources and load balancer.
6. Configure the load balancer's health endpoint as `/health` on port **8000**, and use Cloudflare to serve the load-balanced site over HTTPS.
7. Register/log in, add a note, and make repeated requests: the page footer and `X-Served-By` header identify the serving instance. Stop the app on one instance and verify the other still displays the saved note.

For MySQL, an example connection string **format** is:

```text
mysql+pymysql://journal_user:YOUR_URL_ENCODED_PASSWORD@YOUR_PRIVATE_DATABASE_HOST:3306/journal?charset=utf8mb4
```

**Do not commit real database credentials or `SECRET_KEY` to GitHub.** Store them in environment variables or a secure root-readable environment file on each server. Use `SECURE_COOKIES=true` for HTTPS-only deployment (but **not** during plain HTTP tests in Task 3).

## 7. Cleanup

When finished with all screenshots and the final report, stop your tunnel/SSH connections and run `tofu destroy` for resources managed by OpenTofu. Delete any manually created resources (key pair, access keys, policies, IAM lab user, optional extra-credit resources) as requested in Task 5. Do not leave billable infrastructure active.

---

**Developer:** Latifa Alnuaimi  
**Course:** CCEN 448 — Cloud Infrastructure & Services  
**Instructor:** Prof. Khaled Salah  
**Project:** Lab Exercise 6, Fall 2026
