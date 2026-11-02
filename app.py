"""Latifa's Journal — dynamic Flask notes website for CCEN 448 Lab 6.

Run locally: python3 app.py  (http://127.0.0.1:8000)
Runs on SQLite by default, or MySQL when DATABASE_URL is configured.
"""
from __future__ import annotations

import os
import re
import secrets
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
load_dotenv(BASE_DIR / ".env")

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to open your journal."
login_manager.login_message_category = "info"

MOODS = {
    "inspired": "Inspired",
    "grateful": "Grateful",
    "reflective": "Reflective",
    "focused": "Focused",
}


def secret_key() -> str:
    """Stable local development secret. For multi-instance deployments set SECRET_KEY."""
    configured = os.getenv("SECRET_KEY", "").strip()
    if configured:
        return configured
    if os.getenv("APP_ENV", "").lower() == "production":
        raise RuntimeError("Set SECRET_KEY for production and use the same value on all web instances.")
    secret_file = INSTANCE_DIR / ".local-secret"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32))
        secret_file.chmod(0o600)
    return secret_file.read_text().strip()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    notes = db.relationship("Note", backref="author", cascade="all, delete-orphan", lazy=True)


class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(20), nullable=False, default="reflective")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


def create_app() -> Flask:
    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.update(
        SECRET_KEY=secret_key(),
        SQLALCHEMY_DATABASE_URI=(os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{INSTANCE_DIR / 'journal.sqlite3'}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SECURE_COOKIES", "false").lower() in ("1", "true", "yes"),
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    db.init_app(app)
    login_manager.init_app(app)
    instance_label = os.getenv("INSTANCE_LABEL", "").strip() or socket.gethostname()

    @app.context_processor
    def inject_globals():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return {"csrf_token": token, "instance_label": instance_label, "moods": MOODS}

    @app.before_request
    def verify_csrf():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            provided = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not secrets.compare_digest(provided, expected):
                abort(400, "Your session expired. Reload the page and try again.")

    @app.after_request
    def add_headers(response):
        response.headers["X-Served-By"] = instance_label
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.get("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("home.html", title="A little space for your thoughts")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not (2 <= len(name) <= 80):
                flash("Please enter your name (2–80 characters).", "error")
            elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                flash("Please enter a valid email address.", "error")
            elif len(password) < 8 or len(password) > 128:
                flash("Choose a password between 8 and 128 characters.", "error")
            elif db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
                flash("That email is already registered. Please sign in.", "error")
            else:
                user = User(name=name, email=email, password_hash=generate_password_hash(password))
                db.session.add(user)
                try:
                    db.session.commit()
                    login_user(user)
                    session.permanent = True
                    flash("Your journal is ready. Welcome in!", "success")
                    return redirect(url_for("dashboard"))
                except IntegrityError:
                    db.session.rollback()
                    flash("That email is already registered. Please sign in.", "error")
        return render_template("auth.html", title="Create your account", action="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                session.permanent = True
                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))
            flash("Email or password is incorrect.", "error")
        return render_template("auth.html", title="Welcome back", action="login")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("See you soon!", "info")
        return redirect(url_for("home"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        search = request.args.get("q", "").strip()[:100]
        mood_filter = request.args.get("mood", "").strip()
        notes_query = db.select(Note).where(Note.user_id == current_user.id)
        if search:
            term = f"%{search}%"
            notes_query = notes_query.where(db.or_(Note.title.ilike(term), Note.content.ilike(term)))
        if mood_filter in MOODS:
            notes_query = notes_query.where(Note.mood == mood_filter)
        notes = db.session.execute(notes_query.order_by(Note.created_at.desc(), Note.id.desc())).scalars().all()
        total = db.session.execute(db.select(db.func.count(Note.id)).where(Note.user_id == current_user.id)).scalar_one()
        return render_template("dashboard.html", title="My journal", notes=notes, total=total, search=search, selected_mood=mood_filter)

    def validate_note():
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        mood = request.form.get("mood", "reflective")
        if not 1 <= len(title) <= 100:
            return None, "Please add a title (up to 100 characters)."
        if not 1 <= len(content) <= 4000:
            return None, "Write a note between 1 and 4,000 characters."
        if mood not in MOODS:
            return None, "Please choose a mood."
        return {"title": title, "content": content, "mood": mood}, None

    @app.route("/notes/new", methods=["GET", "POST"])
    @login_required
    def new_note():
        if request.method == "POST":
            values, error = validate_note()
            if error:
                flash(error, "error")
            else:
                db.session.add(Note(user_id=current_user.id, **values))
                db.session.commit()
                flash("Your note was saved!", "success")
                return redirect(url_for("dashboard"))
        return render_template("note_form.html", title="New note", note=None)

    def owned_note(note_id: int) -> Note:
        note = db.session.get(Note, note_id)
        if note is None or note.user_id != current_user.id:
            abort(404)
        return note

    @app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_note(note_id: int):
        note = owned_note(note_id)
        if request.method == "POST":
            values, error = validate_note()
            if error:
                flash(error, "error")
            else:
                note.title, note.content, note.mood = values["title"], values["content"], values["mood"]
                note.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                flash("Your changes were saved.", "success")
                return redirect(url_for("dashboard"))
        return render_template("note_form.html", title="Edit note", note=note)

    @app.post("/notes/<int:note_id>/delete")
    @login_required
    def delete_note(note_id: int):
        note = owned_note(note_id)
        db.session.delete(note)
        db.session.commit()
        flash("Note deleted.", "info")
        return redirect(url_for("dashboard"))

    @app.get("/health")
    def health():
        """Load balancer health endpoint, including shared database connectivity."""
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(status="ok", instance=instance_label, database="connected"), 200
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(status="unhealthy", instance=instance_label, database="unavailable"), 503

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", title="Page not found", error_code="404", message="We couldn't find that page."), 404

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", title="Something went wrong", error_code="400", message="Your request couldn't be completed. Please refresh and try again."), 400

    with app.app_context():
        db.create_all()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
