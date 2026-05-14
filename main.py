import os, json, base64, zipfile, io, mimetypes
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from groq import Groq
import psycopg2
import psycopg2.extras
import hashlib, secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hacker-ai-secret-2025-panda")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.wdenzjnjtytuvwfzisci:YOUR_PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "owner@example.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Models ──────────────────────────────────────────────────────────────────
FREE_MODELS = [
    {"id": "llama-3.1-8b-instant",       "name": "Llama 3.1 8B",         "desc": "Fast & lightweight",           "vision": False},
    {"id": "gemma2-9b-it",               "name": "Gemma 2 9B",           "desc": "Google's efficient model",     "vision": False},
    {"id": "llama3-8b-8192",             "name": "Llama 3 8B",           "desc": "Meta's open model",            "vision": False},
]

PAID_MODELS = [
    {"id": "llama-3.3-70b-versatile",    "name": "Llama 3.3 70B",        "desc": "Most capable open model",      "vision": False, "plan": "basic"},
    {"id": "llama-3.1-70b-versatile",    "name": "Llama 3.1 70B",        "desc": "High-performance reasoning",   "vision": False, "plan": "basic"},
    {"id": "mixtral-8x7b-32768",         "name": "Mixtral 8x7B MoE",     "desc": "Mixture of experts",           "vision": False, "plan": "basic"},
    {"id": "llama3-70b-8192",            "name": "Llama 3 70B",          "desc": "Meta's flagship open model",   "vision": False, "plan": "basic"},
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "name": "Llama 4 Scout", "desc": "Next-gen multimodal", "vision": True, "plan": "pro"},
    {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "name": "Llama 4 Maverick", "desc": "Elite multimodal beast", "vision": True, "plan": "pro"},
    {"id": "llama-3.2-90b-vision-preview","name": "Llama 3.2 90B Vision","desc": "90B vision powerhouse",        "vision": True, "plan": "pro"},
    {"id": "llama-3.2-11b-vision-preview","name": "Llama 3.2 11B Vision","desc": "Fast vision model",            "vision": True, "plan": "basic"},
    {"id": "deepseek-r1-distill-llama-70b","name": "DeepSeek R1 70B",    "desc": "Chain-of-thought reasoning",   "vision": False, "plan": "elite"},
    {"id": "qwen-qwq-32b",               "name": "Qwen QwQ 32B",         "desc": "Advanced reasoning model",     "vision": False, "plan": "elite"},
    {"id": "llama-3.3-70b-specdec",      "name": "Llama 3.3 70B SpecDec","desc": "Speculative decoding speed",  "vision": False, "plan": "pro"},
    {"id": "playai-tts",                 "name": "PlayAI TTS",           "desc": "Text-to-speech synthesis",     "vision": False, "plan": "elite"},
]

PLANS = {
    "basic":  {"name": "Basic Hacker",   "price_monthly": 99,  "price_yearly": 799,  "price_3month": 249, "models": ["basic"], "color": "#00ff88"},
    "pro":    {"name": "Pro Hacker",     "price_monthly": 199, "price_yearly": 1599, "price_3month": 499, "models": ["basic","pro"], "color": "#00ccff"},
    "elite":  {"name": "Elite Hacker",   "price_monthly": 399, "price_yearly": 2999, "price_3month": 999, "models": ["basic","pro","elite"], "color": "#ff6b35"},
}

# ── DB ───────────────────────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT DEFAULT 'free',
            plan_expires TIMESTAMP,
            is_owner BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS payment_requests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            plan TEXT NOT NULL,
            duration TEXT NOT NULL,
            amount INTEGER NOT NULL,
            utr TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            model TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_user(email):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close(); conn.close()
    return dict(user) if user else None

def get_user_by_id(uid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    user = cur.fetchone()
    cur.close(); conn.close()
    return dict(user) if user else None

# ── Auth ─────────────────────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email","").strip().lower()
    pw = data.get("password","")
    if not email or not pw or len(pw) < 6:
        return jsonify({"error": "Invalid email or password (min 6 chars)"}), 400
    if get_user(email):
        return jsonify({"error": "Email already registered"}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (email, password_hash) VALUES (%s,%s) RETURNING id",
                (email, hash_password(pw)))
    uid = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()
    session["user_id"] = uid
    session["email"] = email
    return jsonify({"ok": True, "email": email})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email","").strip().lower()
    pw = data.get("password","")
    user = get_user(email)
    if not user or user["password_hash"] != hash_password(pw):
        return jsonify({"error": "Invalid email or password"}), 401
    session["user_id"] = user["id"]
    session["email"] = email
    return jsonify({"ok": True, "email": email, "plan": user["plan"], "is_owner": user["is_owner"]})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"logged_in": False})
    user = get_user_by_id(uid)
    if not user:
        return jsonify({"logged_in": False})
    # Check plan expiry
    plan = user["plan"]
    if plan != "free" and user.get("plan_expires"):
        if datetime.now() > user["plan_expires"]:
            plan = "free"
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE users SET plan='free' WHERE id=%s", (uid,))
            conn.commit(); cur.close(); conn.close()
    return jsonify({
        "logged_in": True,
        "email": user["email"],
        "plan": plan,
        "is_owner": user["is_owner"],
        "plan_expires": str(user["plan_expires"]) if user.get("plan_expires") else None
    })

# ── Chat ─────────────────────────────────────────────────────────────────────
def can_use_model(user_plan, model_id):
    for m in FREE_MODELS:
        if m["id"] == model_id:
            return True
    for m in PAID_MODELS:
        if m["id"] == model_id:
            req = m["plan"]
            hierarchy = ["free","basic","pro","elite"]
            return hierarchy.index(user_plan) >= hierarchy.index(req)
    return False

def read_file_content(file_path, filename):
    ext = filename.lower().split(".")[-1]
    text_exts = ["py","js","php","html","css","ts","json","txt","md","sh","rb","go","java","c","cpp","rs","sql","yaml","yml","toml","xml","csv"]
    if ext in text_exts:
        with open(file_path, "r", errors="ignore") as f:
            return f.read()[:15000]
    elif ext == "zip":
        content = []
        with zipfile.ZipFile(file_path, "r") as z:
            for name in z.namelist()[:20]:
                try:
                    data = z.read(name).decode("utf-8", errors="ignore")
                    content.append(f"=== {name} ===\n{data[:3000]}")
                except:
                    content.append(f"=== {name} === [binary]")
        return "\n\n".join(content)
    return None

@app.route("/api/chat", methods=["POST"])
def chat():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401

    user = get_user_by_id(uid)
    model_id = request.form.get("model", "llama-3.1-8b-instant")
    message = request.form.get("message", "")
    history_raw = request.form.get("history", "[]")
    history = json.loads(history_raw)

    if not can_use_model(user["plan"], model_id):
        return jsonify({"error": "Upgrade your plan to use this model"}), 403

    client = Groq(api_key=GROQ_API_KEY)

    # Build message content
    content = []
    if message:
        content.append({"type": "text", "text": message})

    # Check if model supports vision
    model_info = next((m for m in PAID_MODELS + FREE_MODELS if m["id"] == model_id), None)
    supports_vision = model_info and model_info.get("vision", False)

    # Handle uploaded files
    file_text = ""
    if "file" in request.files:
        f = request.files["file"]
        filename = secure_filename(f.filename)
        fpath = os.path.join(UPLOAD_FOLDER, filename)
        f.save(fpath)
        mime = mimetypes.guess_type(filename)[0] or ""

        if mime.startswith("image/") and supports_vision:
            with open(fpath, "rb") as img:
                b64 = base64.b64encode(img.read()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        else:
            file_content = read_file_content(fpath, filename)
            if file_content:
                file_text = f"\n\n[File: {filename}]\n```\n{file_content}\n```"

    if file_text:
        if content and content[0]["type"] == "text":
            content[0]["text"] += file_text
        else:
            content.insert(0, {"type": "text", "text": file_text})

    if not content:
        content = [{"type": "text", "text": "Hello"}]

    # Build messages
    messages = [{"role": "system", "content": "You are HACKER AI — an elite AI assistant with deep expertise in hacking, cybersecurity, programming, and system exploitation. You speak with confidence and technical precision. You help with penetration testing, code analysis, vulnerability research, and advanced programming. Always be direct and technical."}]
    
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    
    messages.append({"role": "user", "content": content if len(content) > 1 else content[0]["text"]})

    try:
        resp = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=4096,
            stream=False
        )
        reply = resp.choices[0].message.content

        # Save to history
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO chat_history (user_id, model, role, content) VALUES (%s,%s,'user',%s)", (uid, model_id, message))
        cur.execute("INSERT INTO chat_history (user_id, model, role, content) VALUES (%s,%s,'assistant',%s)", (uid, model_id, reply))
        conn.commit(); cur.close(); conn.close()

        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Models List ───────────────────────────────────────────────────────────────
@app.route("/api/models")
def models():
    return jsonify({"free": FREE_MODELS, "paid": PAID_MODELS})

# ── Payment ───────────────────────────────────────────────────────────────────
@app.route("/api/payment/request", methods=["POST"])
def payment_request():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    plan = data.get("plan")
    duration = data.get("duration")  # monthly, yearly, 3month
    utr = data.get("utr", "")

    amounts = {
        "basic":  {"monthly": 99,  "yearly": 799,  "3month": 249},
        "pro":    {"monthly": 199, "yearly": 1599, "3month": 499},
        "elite":  {"monthly": 399, "yearly": 2999, "3month": 999},
    }
    amount = amounts.get(plan, {}).get(duration, 0)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO payment_requests (user_id, plan, duration, amount, utr) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (uid, plan, duration, amount, utr))
    req_id = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()

    # Notify owner
    try:
        user = get_user_by_id(uid)
        send_email(OWNER_EMAIL, "New Payment Request - HACKER AI",
                   f"User: {user['email']}\nPlan: {plan} ({duration})\nAmount: ₹{amount}\nUTR: {utr}\nRequest ID: {req_id}\n\nVerify at your admin panel.")
    except:
        pass

    return jsonify({"ok": True, "request_id": req_id})

# ── Owner Admin ───────────────────────────────────────────────────────────────
@app.route("/api/admin/payments")
def admin_payments():
    uid = session.get("user_id")
    user = get_user_by_id(uid) if uid else None
    if not user or not user["is_owner"]:
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT pr.*, u.email FROM payment_requests pr
        JOIN users u ON pr.user_id = u.id
        WHERE pr.status='pending' ORDER BY pr.created_at DESC
    """)
    reqs = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify({"requests": reqs})

@app.route("/api/admin/approve", methods=["POST"])
def admin_approve():
    uid = session.get("user_id")
    user = get_user_by_id(uid) if uid else None
    if not user or not user["is_owner"]:
        return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    req_id = data.get("request_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payment_requests WHERE id=%s", (req_id,))
    pr = cur.fetchone()
    if not pr:
        return jsonify({"error": "Not found"}), 404

    pr = dict(pr)
    dur_map = {"monthly": 30, "3month": 90, "yearly": 365}
    days = dur_map.get(pr["duration"], 30)
    expires = datetime.now() + timedelta(days=days)

    cur.execute("UPDATE users SET plan=%s, plan_expires=%s WHERE id=%s", (pr["plan"], expires, pr["user_id"]))
    cur.execute("UPDATE payment_requests SET status='approved' WHERE id=%s", (req_id,))
    conn.commit()

    target_user = get_user_by_id(pr["user_id"])
    plan_info = PLANS.get(pr["plan"], {})
    try:
        send_email(target_user["email"], "✅ HACKER AI Plan Activated!",
                   f"""
Your {plan_info.get('name','Plan')} has been activated!

Plan: {pr['plan'].upper()}
Duration: {pr['duration']}
Expires: {expires.strftime('%Y-%m-%d')}

Login now: https://hacker-ai.onrender.com

Welcome to the elite. 🔥
— HACKER AI Team
""")
    except:
        pass

    cur.close(); conn.close()
    return jsonify({"ok": True})

# ── Email helper ──────────────────────────────────────────────────────────────
def send_email(to, subject, body):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

# ── Serve frontend ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        print(f"DB init warning: {e}")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
