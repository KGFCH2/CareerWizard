
import os, json, re, secrets, string, sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Recommender
from utils.recommender import CareerRecommender

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR/'db.sqlite3'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------- Models ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    security_question = db.Column(db.String(255), nullable=False)
    security_answer_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_security_answer(self, answer):
        self.security_answer_hash = generate_password_hash(answer.lower().strip())

    def check_security_answer(self, answer):
        return check_password_hash(self.security_answer_hash, answer.lower().strip())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- Recommender instance ----------
recommender = CareerRecommender(BASE_DIR / "data" / "careers.json")

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        sec_q = request.form.get("security_question", "").strip()
        sec_a = request.form.get("security_answer", "").strip()
        if not username or not email or not password or not sec_q or not sec_a:
            flash("All fields are required.", "error")
            return render_template("signup.html")
        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash("Username or email already exists.", "error")
            return render_template("signup.html")
        user = User(username=username, email=email, security_question=sec_q)
        user.set_password(password)
        user.set_security_answer(sec_a)
        db.session.add(user)
        db.session.commit()
        flash("Signup successful. You can log in now.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        answer = request.form.get("security_answer", "").strip()
        new_password = request.form.get("new_password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_security_answer(answer):
            user.set_password(new_password)
            db.session.commit()
            flash("Password reset successful.", "success")
            return redirect(url_for("login"))
        flash("Incorrect username or answer.", "error")
    return render_template("forgot.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# ---- API: recommendations ----
@app.route("/api/recommend", methods=["POST"])
@login_required
def api_recommend():
    payload = request.get_json(force=True, silent=True) or {}
    skills = payload.get("skills", [])
    topn = int(payload.get("topn", 10))
    results = recommender.recommend_by_skills(skills, topn=topn)
    return jsonify({"results": results})

# ---- API: suggestions (typeahead) ----
@app.route("/api/suggest")
def api_suggest():
    q = request.args.get("q", "").strip()
    return jsonify(recommender.suggest(q))

# ---- API: chat ----
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    payload = request.get_json(force=True, silent=True) or {}
    msg = (payload.get("message") or "").strip()
    if not msg:
        return jsonify({"reply": "Say something like: 'I know Python and SQL, what roles fit me?'"})

    lower = msg.lower()
    # Simple intents
    if any(g in lower for g in ["hi", "hello", "hey"]):
        return jsonify({"reply": "Hello! Tell me a few skills you have or want to learn, and I’ll suggest careers."})
    if "help" in lower:
        return jsonify({"reply": "You can type your skills (e.g., Python, Excel, communication) or ask 'what should I learn for data analyst?'."})
    if "thank" in lower:
        return jsonify({"reply": "You’re welcome! Keep exploring skills and roles."})

    # Extract comma-separated skills or words
    words = [w.strip() for w in re.split(r"[,;/]| and | with ", msg) if w.strip()]
    # If user asks "what should I learn for X", search by career
    if "what should i learn for" in lower or "skills for" in lower:
        # pull the last noun phrase naively (end)
        target = msg.split("for")[-1].strip(" ?.!").lower()
        suggestions = recommender.skills_for_career(target)
        if suggestions:
            return jsonify({"reply": "For **{}**, focus on: {}".format(target.title(), ", ".join(suggestions[:12]))})
        return jsonify({"reply": "I couldn't find that role. Try a common title like 'Data Analyst' or 'Web Developer'."})

    # Otherwise, recommend by skills
    results = recommender.recommend_by_skills(words, topn=5)
    if results:
        bullets = "\n".join([f"- {r['career']}  • match {int(r['match']*100)}% • learn: {', '.join(r['top_skills'][:5])}" for r in results])
        return jsonify({"reply": f"Top matches:\n{bullets}"})
    return jsonify({"reply": "Hmm, I couldn't match that. Try listing 3–5 skills (e.g., Python, statistics, SQL)."})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
