import os, json, base64, zipfile, io, mimetypes
from flask import Flask, request, jsonify, session, Response
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
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DB_URL = os.environ.get("DATABASE_URL", "")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "owner@example.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FREE_MODELS = [
    {"id": "llama-3.1-8b-instant",  "name": "Llama 3.1 8B",  "desc": "Fast & lightweight",        "vision": False},
    {"id": "gemma2-9b-it",          "name": "Gemma 2 9B",    "desc": "Google efficient model",     "vision": False},
    {"id": "llama3-8b-8192",        "name": "Llama 3 8B",    "desc": "Meta open model",            "vision": False},
]

PAID_MODELS = [
    {"id": "llama-3.3-70b-versatile",   "name": "Llama 3.3 70B",       "desc": "Most capable open model",   "vision": False, "plan": "basic"},
    {"id": "llama-3.1-70b-versatile",   "name": "Llama 3.1 70B",       "desc": "High-performance reasoning","vision": False, "plan": "basic"},
    {"id": "mixtral-8x7b-32768",        "name": "Mixtral 8x7B MoE",    "desc": "Mixture of experts",        "vision": False, "plan": "basic"},
    {"id": "llama3-70b-8192",           "name": "Llama 3 70B",         "desc": "Meta flagship model",       "vision": False, "plan": "basic"},
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct",    "name": "Llama 4 Scout",    "desc": "Next-gen multimodal",       "vision": True,  "plan": "pro"},
    {"id": "meta-llama/llama-4-maverick-17b-128e-instruct","name": "Llama 4 Maverick", "desc": "Elite multimodal beast",    "vision": True,  "plan": "pro"},
    {"id": "llama-3.2-90b-vision-preview","name": "Llama 3.2 90B Vision","desc": "90B vision powerhouse",   "vision": True,  "plan": "pro"},
    {"id": "llama-3.2-11b-vision-preview","name": "Llama 3.2 11B Vision","desc": "Fast vision model",       "vision": True,  "plan": "basic"},
    {"id": "deepseek-r1-distill-llama-70b","name": "DeepSeek R1 70B",  "desc": "Chain-of-thought reasoning","vision": False, "plan": "elite"},
    {"id": "qwen-qwq-32b",              "name": "Qwen QwQ 32B",        "desc": "Advanced reasoning model",  "vision": False, "plan": "elite"},
    {"id": "llama-3.3-70b-specdec",     "name": "Llama 3.3 70B SpecDec","desc": "Speculative decoding",    "vision": False, "plan": "pro"},
]

PLANS = {
    "basic": {"name": "Basic Hacker",  "price_monthly": 99,  "price_yearly": 799,  "price_3month": 249},
    "pro":   {"name": "Pro Hacker",    "price_monthly": 199, "price_yearly": 1599, "price_3month": 499},
    "elite": {"name": "Elite Hacker",  "price_monthly": 399, "price_yearly": 2999, "price_3month": 999},
}

HTML_CONTENT = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width,initial-scale=1.0"/>\n<title>HACKER AI — Elite Intelligence</title>\n<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&family=JetBrains+Mono:wght@300;400;600&display=swap" rel="stylesheet"/>\n<style>\n:root{\n  --green:#00ff88;--cyan:#00e5ff;--red:#ff3366;--orange:#ff6b35;\n  --bg:#000;--bg1:#030a03;--bg2:#050d0a;--card:#0a1a0f;\n  --border:#1a3a1f;--text:#c0ffc0;--dim:#446644;\n  --font-mono:\'JetBrains Mono\',monospace;--font-hud:\'Share Tech Mono\',monospace;\n  --font-title:\'Orbitron\',sans-serif;\n}\n*{margin:0;padding:0;box-sizing:border-box;}\nhtml,body{height:100%;background:var(--bg);color:var(--text);font-family:var(--font-mono);overflow-x:hidden;}\n\n/* ── STARS ── */\n#stars-canvas{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;}\n\n/* ── SCANLINES ── */\nbody::before{content:\'\';position:fixed;top:0;left:0;width:100%;height:100%;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,136,0.015) 2px,rgba(0,255,136,0.015) 4px);z-index:1;pointer-events:none;}\n\n/* ── LAYOUT ── */\n#app{position:relative;z-index:2;min-height:100vh;}\n\n/* ══════════════════════════════════════════════\n   AUTH SCREEN\n══════════════════════════════════════════════ */\n#auth-screen{\n  display:flex;flex-direction:column;align-items:center;justify-content:center;\n  min-height:100vh;padding:20px;\n}\n.auth-logo{\n  font-family:var(--font-title);font-size:clamp(2rem,6vw,3.5rem);\n  font-weight:900;letter-spacing:6px;color:var(--green);\n  text-shadow:0 0 30px var(--green),0 0 60px rgba(0,255,136,0.3);\n  margin-bottom:8px;animation:flicker 4s infinite;\n}\n.auth-sub{font-family:var(--font-hud);color:var(--cyan);font-size:0.75rem;letter-spacing:4px;margin-bottom:40px;opacity:0.7;}\n@keyframes flicker{0%,95%,100%{opacity:1}96%,99%{opacity:0.7}97%,98%{opacity:0.3}}\n\n.auth-card{\n  background:linear-gradient(135deg,rgba(10,26,15,0.95),rgba(3,10,3,0.98));\n  border:1px solid var(--border);border-top:1px solid var(--green);\n  width:100%;max-width:420px;padding:40px;position:relative;\n  box-shadow:0 0 40px rgba(0,255,136,0.08),inset 0 0 40px rgba(0,0,0,0.5);\n}\n.auth-card::before{\n  content:\'\';position:absolute;top:0;left:0;width:100%;height:2px;\n  background:linear-gradient(90deg,transparent,var(--green),var(--cyan),transparent);\n  animation:scan-h 3s infinite;\n}\n@keyframes scan-h{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}\n\n.tab-row{display:flex;gap:0;margin-bottom:32px;border:1px solid var(--border);overflow:hidden;}\n.tab-btn{\n  flex:1;padding:12px;background:none;border:none;cursor:pointer;\n  font-family:var(--font-hud);font-size:0.8rem;letter-spacing:2px;\n  color:var(--dim);transition:.2s;\n}\n.tab-btn.active{background:rgba(0,255,136,0.1);color:var(--green);border-bottom:2px solid var(--green);}\n\n.input-group{margin-bottom:18px;}\n.input-label{font-family:var(--font-hud);font-size:0.7rem;letter-spacing:2px;color:var(--cyan);margin-bottom:6px;display:block;}\n.input-field{\n  width:100%;background:rgba(0,0,0,0.6);border:1px solid var(--border);\n  color:var(--green);font-family:var(--font-mono);font-size:0.9rem;\n  padding:12px 16px;outline:none;transition:.2s;\n}\n.input-field:focus{border-color:var(--green);box-shadow:0 0 12px rgba(0,255,136,0.15);}\n.input-field::placeholder{color:var(--dim);}\n\n.btn-primary{\n  width:100%;padding:14px;background:transparent;\n  border:1px solid var(--green);color:var(--green);\n  font-family:var(--font-title);font-size:0.85rem;letter-spacing:3px;\n  cursor:pointer;transition:.3s;position:relative;overflow:hidden;margin-top:8px;\n}\n.btn-primary::before{\n  content:\'\';position:absolute;top:0;left:-100%;width:100%;height:100%;\n  background:linear-gradient(90deg,transparent,rgba(0,255,136,0.15),transparent);\n  transition:.4s;\n}\n.btn-primary:hover::before{left:100%;}\n.btn-primary:hover{background:rgba(0,255,136,0.1);box-shadow:0 0 20px rgba(0,255,136,0.2);}\n.btn-primary:active{transform:scale(0.98);}\n\n.auth-error{color:var(--red);font-size:0.8rem;font-family:var(--font-hud);margin-top:10px;text-align:center;min-height:20px;}\n\n/* ══════════════════════════════════════════════\n   MAIN APP\n══════════════════════════════════════════════ */\n#main-app{display:none;height:100vh;flex-direction:column;}\n\n/* NAV */\n.nav{\n  display:flex;align-items:center;justify-content:space-between;\n  padding:0 20px;height:54px;border-bottom:1px solid var(--border);\n  background:rgba(0,0,0,0.9);backdrop-filter:blur(10px);flex-shrink:0;\n}\n.nav-logo{font-family:var(--font-title);font-size:1.1rem;font-weight:700;color:var(--green);letter-spacing:3px;text-shadow:0 0 10px var(--green);}\n.nav-right{display:flex;align-items:center;gap:12px;}\n.nav-btn{\n  background:none;border:1px solid var(--border);color:var(--text);\n  font-family:var(--font-hud);font-size:0.7rem;letter-spacing:1px;\n  padding:6px 14px;cursor:pointer;transition:.2s;\n}\n.nav-btn:hover{border-color:var(--green);color:var(--green);}\n.nav-btn.danger:hover{border-color:var(--red);color:var(--red);}\n.plan-badge{\n  font-family:var(--font-hud);font-size:0.65rem;letter-spacing:2px;\n  padding:4px 10px;border:1px solid;\n}\n.plan-badge.free{color:var(--dim);border-color:var(--dim);}\n.plan-badge.basic{color:var(--green);border-color:var(--green);}\n.plan-badge.pro{color:var(--cyan);border-color:var(--cyan);}\n.plan-badge.elite{color:var(--orange);border-color:var(--orange);}\n\n/* PAGE TABS */\n.page-tabs{\n  display:flex;gap:0;border-bottom:1px solid var(--border);\n  background:rgba(0,0,0,0.7);flex-shrink:0;\n}\n.page-tab{\n  padding:10px 24px;background:none;border:none;cursor:pointer;\n  font-family:var(--font-hud);font-size:0.75rem;letter-spacing:2px;\n  color:var(--dim);border-bottom:2px solid transparent;transition:.2s;\n}\n.page-tab.active{color:var(--green);border-bottom-color:var(--green);}\n.page-tab:hover{color:var(--text);}\n\n/* ══ CHAT PAGE ══ */\n#page-chat{flex:1;display:flex;overflow:hidden;}\n\n.sidebar{\n  width:240px;flex-shrink:0;border-right:1px solid var(--border);\n  background:rgba(3,10,3,0.95);display:flex;flex-direction:column;\n  overflow-y:auto;\n}\n.sidebar-section{padding:12px 16px;border-bottom:1px solid var(--border);}\n.sidebar-label{font-family:var(--font-hud);font-size:0.65rem;letter-spacing:3px;color:var(--dim);margin-bottom:10px;}\n\n.model-item{\n  display:flex;align-items:center;gap:8px;padding:8px 10px;cursor:pointer;\n  border:1px solid transparent;margin-bottom:4px;transition:.2s;border-radius:2px;\n}\n.model-item:hover{border-color:var(--border);background:rgba(0,255,136,0.03);}\n.model-item.active{border-color:var(--green);background:rgba(0,255,136,0.07);}\n.model-item.locked{opacity:0.35;cursor:not-allowed;}\n.model-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}\n.dot-free{background:var(--green);box-shadow:0 0 6px var(--green);}\n.dot-basic{background:#00ff88;box-shadow:0 0 6px #00ff88;}\n.dot-pro{background:var(--cyan);box-shadow:0 0 6px var(--cyan);}\n.dot-elite{background:var(--orange);box-shadow:0 0 6px var(--orange);}\n.dot-locked{background:var(--dim);}\n.model-info{min-width:0;}\n.model-name{font-size:0.72rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}\n.model-desc{font-size:0.6rem;color:var(--dim);}\n.vision-tag{font-size:0.55rem;color:var(--cyan);letter-spacing:1px;}\n\n/* Chat area */\n.chat-area{flex:1;display:flex;flex-direction:column;overflow:hidden;}\n\n.chat-header{\n  padding:12px 20px;border-bottom:1px solid var(--border);\n  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;\n}\n.active-model-name{font-family:var(--font-hud);font-size:0.75rem;color:var(--cyan);letter-spacing:2px;}\n.vision-indicator{font-size:0.65rem;color:var(--cyan);background:rgba(0,229,255,0.1);border:1px solid var(--cyan);padding:2px 8px;letter-spacing:1px;}\n\n.messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px;}\n.messages::-webkit-scrollbar{width:4px;}\n.messages::-webkit-scrollbar-track{background:transparent;}\n.messages::-webkit-scrollbar-thumb{background:var(--border);}\n\n.msg{display:flex;gap:12px;max-width:100%;}\n.msg.user{flex-direction:row-reverse;}\n.msg-avatar{\n  width:32px;height:32px;flex-shrink:0;display:flex;align-items:center;\n  justify-content:center;font-family:var(--font-hud);font-size:0.65rem;\n  border:1px solid;\n}\n.msg.ai .msg-avatar{border-color:var(--green);color:var(--green);background:rgba(0,255,136,0.08);}\n.msg.user .msg-avatar{border-color:var(--cyan);color:var(--cyan);background:rgba(0,229,255,0.08);}\n.msg-bubble{\n  max-width:75%;padding:14px 18px;\n  font-size:0.85rem;line-height:1.7;word-break:break-word;\n}\n.msg.ai .msg-bubble{\n  background:rgba(10,26,15,0.7);border:1px solid var(--border);\n  border-left:2px solid var(--green);\n}\n.msg.user .msg-bubble{\n  background:rgba(0,10,20,0.7);border:1px solid rgba(0,229,255,0.2);\n  border-right:2px solid var(--cyan);\n}\n.msg-bubble pre{\n  background:rgba(0,0,0,0.5);border:1px solid var(--border);\n  padding:12px;margin:10px 0;overflow-x:auto;font-size:0.8rem;\n  border-left:2px solid var(--orange);\n}\n.msg-bubble code{color:var(--orange);font-family:var(--font-mono);}\n.msg-bubble pre code{color:#c0ffa0;}\n\n.typing-indicator{display:flex;gap:4px;align-items:center;padding:12px 18px;}\n.typing-dot{width:6px;height:6px;background:var(--green);border-radius:50%;animation:typing 1.2s infinite;}\n.typing-dot:nth-child(2){animation-delay:.2s;}\n.typing-dot:nth-child(3){animation-delay:.4s;}\n@keyframes typing{0%,60%,100%{opacity:0.2;transform:scale(0.8)}30%{opacity:1;transform:scale(1)}}\n\n/* Input bar */\n.input-bar{\n  border-top:1px solid var(--border);padding:14px 20px;\n  background:rgba(0,0,0,0.8);flex-shrink:0;\n}\n.file-preview{\n  display:flex;align-items:center;gap:10px;padding:8px 12px;\n  background:rgba(0,255,136,0.05);border:1px solid var(--border);\n  margin-bottom:10px;font-size:0.75rem;color:var(--cyan);\n}\n.file-preview .rm{cursor:pointer;color:var(--red);margin-left:auto;font-size:1rem;}\n.input-row{display:flex;gap:10px;align-items:flex-end;}\n.msg-input{\n  flex:1;background:rgba(0,0,0,0.6);border:1px solid var(--border);\n  color:var(--text);font-family:var(--font-mono);font-size:0.85rem;\n  padding:12px 16px;resize:none;outline:none;max-height:160px;min-height:46px;\n  transition:.2s;\n}\n.msg-input:focus{border-color:var(--green);}\n.attach-btn,.send-btn{\n  background:none;border:1px solid var(--border);color:var(--dim);\n  padding:11px 14px;cursor:pointer;font-size:1.1rem;transition:.2s;flex-shrink:0;\n  height:46px;display:flex;align-items:center;\n}\n.attach-btn:hover{border-color:var(--cyan);color:var(--cyan);}\n.send-btn{border-color:var(--green);color:var(--green);}\n.send-btn:hover{background:rgba(0,255,136,0.1);box-shadow:0 0 10px rgba(0,255,136,0.2);}\n.send-btn:disabled{opacity:0.3;cursor:not-allowed;}\n\n/* ══ PLANS PAGE ══ */\n#page-plans{\n  flex:1;overflow-y:auto;padding:40px 20px;\n  display:none;\n}\n.plans-title{font-family:var(--font-title);font-size:1.8rem;color:var(--green);text-align:center;margin-bottom:6px;letter-spacing:4px;}\n.plans-sub{text-align:center;color:var(--dim);font-family:var(--font-hud);font-size:0.75rem;letter-spacing:2px;margin-bottom:30px;}\n\n.duration-toggle{display:flex;justify-content:center;gap:0;margin-bottom:36px;border:1px solid var(--border);}\n.dur-btn{\n  padding:10px 24px;background:none;border:none;cursor:pointer;\n  font-family:var(--font-hud);font-size:0.75rem;letter-spacing:2px;color:var(--dim);transition:.2s;\n}\n.dur-btn.active{background:rgba(0,255,136,0.1);color:var(--green);}\n\n.plans-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;max-width:960px;margin:0 auto 40px;}\n\n.plan-card{\n  background:linear-gradient(160deg,rgba(10,26,15,0.9),rgba(3,10,3,0.98));\n  border:1px solid var(--border);padding:28px;position:relative;\n  transition:.3s;overflow:hidden;\n}\n.plan-card::before{\n  content:\'\';position:absolute;top:0;left:0;right:0;height:2px;\n}\n.plan-card.basic::before{background:linear-gradient(90deg,transparent,#00ff88,transparent);}\n.plan-card.pro::before{background:linear-gradient(90deg,transparent,var(--cyan),transparent);}\n.plan-card.elite::before{background:linear-gradient(90deg,transparent,var(--orange),transparent);}\n.plan-card:hover{transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,255,136,0.08);}\n\n.plan-card-name{font-family:var(--font-title);font-size:1rem;letter-spacing:3px;margin-bottom:6px;}\n.plan-card.basic .plan-card-name{color:#00ff88;}\n.plan-card.pro .plan-card-name{color:var(--cyan);}\n.plan-card.elite .plan-card-name{color:var(--orange);}\n\n.plan-price{font-family:var(--font-title);font-size:2.2rem;font-weight:900;margin:16px 0 4px;}\n.plan-price-sub{font-family:var(--font-hud);font-size:0.7rem;color:var(--dim);letter-spacing:1px;margin-bottom:20px;}\n.plan-features{list-style:none;margin-bottom:24px;}\n.plan-features li{font-size:0.78rem;color:var(--text);padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);}\n.plan-features li::before{content:\'▶ \';font-size:0.6rem;margin-right:6px;}\n.plan-features li.locked{color:var(--dim);}\n.plan-features li.locked::before{content:\'🔒 \';}\n\n.plan-buy-btn{\n  width:100%;padding:12px;border:1px solid;background:transparent;\n  font-family:var(--font-title);font-size:0.8rem;letter-spacing:2px;cursor:pointer;transition:.3s;\n}\n.plan-card.basic .plan-buy-btn{border-color:#00ff88;color:#00ff88;}\n.plan-card.pro .plan-buy-btn{border-color:var(--cyan);color:var(--cyan);}\n.plan-card.elite .plan-buy-btn{border-color:var(--orange);color:var(--orange);}\n.plan-buy-btn:hover{background:rgba(255,255,255,0.06);}\n\n/* Payment Modal */\n.modal-overlay{\n  position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:100;\n  display:flex;align-items:center;justify-content:center;padding:20px;\n  backdrop-filter:blur(4px);\n}\n.modal{\n  background:var(--bg2);border:1px solid var(--border);border-top:2px solid var(--green);\n  width:100%;max-width:480px;padding:32px;position:relative;max-height:90vh;overflow-y:auto;\n}\n.modal-title{font-family:var(--font-title);font-size:1rem;color:var(--green);letter-spacing:3px;margin-bottom:24px;}\n.modal-close{position:absolute;top:16px;right:16px;background:none;border:none;color:var(--dim);font-size:1.2rem;cursor:pointer;}\n.modal-close:hover{color:var(--red);}\n.qr-container{\n  display:flex;flex-direction:column;align-items:center;padding:20px;\n  border:1px dashed var(--border);margin-bottom:20px;\n}\n.qr-img{width:180px;height:180px;border:2px solid var(--green);object-fit:contain;background:#fff;}\n.qr-label{font-family:var(--font-hud);font-size:0.7rem;color:var(--cyan);letter-spacing:2px;margin-top:10px;text-align:center;}\n.amount-display{\n  font-family:var(--font-title);font-size:1.5rem;color:var(--green);\n  text-align:center;margin:12px 0 4px;\n}\n.modal-info{font-family:var(--font-hud);font-size:0.7rem;color:var(--dim);text-align:center;margin-bottom:20px;}\n\n/* Admin panel */\n#page-admin{flex:1;overflow-y:auto;padding:30px 20px;display:none;}\n.admin-title{font-family:var(--font-title);font-size:1.2rem;color:var(--orange);letter-spacing:3px;margin-bottom:24px;}\n.payment-row{\n  display:flex;align-items:center;justify-content:space-between;\n  padding:14px 18px;border:1px solid var(--border);margin-bottom:8px;\n  background:rgba(10,26,15,0.5);flex-wrap:wrap;gap:10px;\n}\n.payment-info{font-size:0.8rem;}\n.payment-info strong{color:var(--green);}\n.approve-btn{\n  background:none;border:1px solid var(--green);color:var(--green);\n  font-family:var(--font-hud);font-size:0.7rem;letter-spacing:1px;\n  padding:6px 16px;cursor:pointer;transition:.2s;\n}\n.approve-btn:hover{background:rgba(0,255,136,0.1);}\n\n/* Toast */\n.toast{\n  position:fixed;bottom:24px;right:24px;z-index:999;\n  background:rgba(10,26,15,0.98);border:1px solid var(--green);\n  color:var(--green);font-family:var(--font-hud);font-size:0.8rem;letter-spacing:1px;\n  padding:14px 20px;transform:translateY(100px);opacity:0;transition:.3s;max-width:300px;\n}\n.toast.show{transform:translateY(0);opacity:1;}\n.toast.error{border-color:var(--red);color:var(--red);}\n\n/* Responsive */\n@media(max-width:680px){\n  .sidebar{width:200px;}\n  .model-desc{display:none;}\n  .msg-bubble{max-width:88%;}\n}\n@media(max-width:520px){\n  .sidebar{display:none;}\n  #page-chat{flex-direction:column;}\n}\n</style>\n</head>\n<body>\n\n<canvas id="stars-canvas"></canvas>\n\n<div id="app">\n\n<!-- ══════════ AUTH SCREEN ══════════ -->\n<div id="auth-screen">\n  <div class="auth-logo">HACKER AI</div>\n  <div class="auth-sub">// ELITE INTELLIGENCE SYSTEM v2.0</div>\n\n  <div class="auth-card">\n    <div class="tab-row">\n      <button class="tab-btn active" onclick="switchTab(\'login\')">LOGIN</button>\n      <button class="tab-btn" onclick="switchTab(\'register\')">REGISTER</button>\n    </div>\n\n    <div id="login-form">\n      <div class="input-group">\n        <label class="input-label">// EMAIL</label>\n        <input class="input-field" type="email" id="login-email" placeholder="user@domain.com"/>\n      </div>\n      <div class="input-group">\n        <label class="input-label">// PASSWORD</label>\n        <input class="input-field" type="password" id="login-pass" placeholder="••••••••" onkeydown="if(event.key===\'Enter\')doLogin()"/>\n      </div>\n      <button class="btn-primary" onclick="doLogin()">ACCESS SYSTEM</button>\n      <div class="auth-error" id="login-err"></div>\n    </div>\n\n    <div id="register-form" style="display:none">\n      <div class="input-group">\n        <label class="input-label">// EMAIL</label>\n        <input class="input-field" type="email" id="reg-email" placeholder="user@domain.com"/>\n      </div>\n      <div class="input-group">\n        <label class="input-label">// PASSWORD</label>\n        <input class="input-field" type="password" id="reg-pass" placeholder="Min 6 characters"/>\n      </div>\n      <div class="input-group">\n        <label class="input-label">// CONFIRM PASSWORD</label>\n        <input class="input-field" type="password" id="reg-pass2" placeholder="••••••••" onkeydown="if(event.key===\'Enter\')doRegister()"/>\n      </div>\n      <button class="btn-primary" onclick="doRegister()">CREATE ACCOUNT</button>\n      <div class="auth-error" id="reg-err"></div>\n    </div>\n  </div>\n</div>\n\n<!-- ══════════ MAIN APP ══════════ -->\n<div id="main-app">\n\n  <!-- NAV -->\n  <nav class="nav">\n    <div class="nav-logo">⬡ HACKER AI</div>\n    <div class="nav-right">\n      <span class="plan-badge" id="nav-plan-badge">FREE</span>\n      <span style="font-family:var(--font-hud);font-size:0.7rem;color:var(--dim)" id="nav-email"></span>\n      <button class="nav-btn" onclick="logout()">LOGOUT</button>\n    </div>\n  </nav>\n\n  <!-- PAGE TABS -->\n  <div class="page-tabs">\n    <button class="page-tab active" onclick="showPage(\'chat\')">⚡ CHAT</button>\n    <button class="page-tab" onclick="showPage(\'plans\')">💎 PLANS</button>\n    <button class="page-tab" id="admin-tab" style="display:none" onclick="showPage(\'admin\')">🔐 ADMIN</button>\n  </div>\n\n  <!-- ── CHAT PAGE ── -->\n  <div id="page-chat" style="display:flex;">\n\n    <!-- Sidebar -->\n    <div class="sidebar">\n      <div class="sidebar-section">\n        <div class="sidebar-label">FREE MODELS</div>\n        <div id="free-model-list"></div>\n      </div>\n      <div class="sidebar-section">\n        <div class="sidebar-label">PREMIUM MODELS</div>\n        <div id="paid-model-list"></div>\n      </div>\n    </div>\n\n    <!-- Chat -->\n    <div class="chat-area">\n      <div class="chat-header">\n        <div>\n          <div class="active-model-name" id="active-model-label">LLAMA 3.1 8B</div>\n          <div style="font-size:0.65rem;color:var(--dim);font-family:var(--font-hud)">llama-3.1-8b-instant</div>\n        </div>\n        <div id="vision-badge" style="display:none" class="vision-indicator">👁 VISION</div>\n      </div>\n\n      <div class="messages" id="messages">\n        <div class="msg ai">\n          <div class="msg-avatar">AI</div>\n          <div class="msg-bubble">\n            <strong style="color:var(--green);font-family:var(--font-hud)">// HACKER AI ONLINE</strong><br><br>\n            System initialized. I\'m your elite AI assistant — specialized in cybersecurity, programming, code analysis, and technical research.<br><br>\n            Select a model from the sidebar. Upload files, images, or code for analysis. Elite models require a premium plan. 🔥\n          </div>\n        </div>\n      </div>\n\n      <div class="input-bar">\n        <div class="file-preview" id="file-preview" style="display:none">\n          <span id="file-name"></span>\n          <span class="rm" onclick="removeFile()">✕</span>\n        </div>\n        <div class="input-row">\n          <button class="attach-btn" onclick="document.getElementById(\'file-input\').click()" title="Attach file/image">📎</button>\n          <input type="file" id="file-input" style="display:none" onchange="onFileSelect()" accept="image/*,.py,.js,.php,.html,.css,.ts,.json,.txt,.md,.sh,.rb,.go,.java,.c,.cpp,.rs,.sql,.yaml,.toml,.xml,.csv,.zip,.tar">\n          <textarea class="msg-input" id="msg-input" placeholder="Enter command... (Shift+Enter for newline)" rows="1"\n            onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>\n          <button class="send-btn" id="send-btn" onclick="sendMessage()">➤</button>\n        </div>\n      </div>\n    </div>\n  </div>\n\n  <!-- ── PLANS PAGE ── -->\n  <div id="page-plans">\n    <div class="plans-title">UPGRADE PLAN</div>\n    <div class="plans-sub">// UNLOCK ELITE MODELS & CAPABILITIES</div>\n\n    <div class="duration-toggle">\n      <button class="dur-btn active" onclick="setDuration(\'monthly\')">MONTHLY</button>\n      <button class="dur-btn" onclick="setDuration(\'3month\')">3 MONTHS</button>\n      <button class="dur-btn" onclick="setDuration(\'yearly\')">YEARLY</button>\n    </div>\n\n    <div class="plans-grid">\n      <!-- BASIC -->\n      <div class="plan-card basic">\n        <div class="plan-card-name">BASIC HACKER</div>\n        <div class="plan-price" id="price-basic" style="color:#00ff88">₹99</div>\n        <div class="plan-price-sub" id="price-basic-sub">/month</div>\n        <ul class="plan-features">\n          <li>Llama 3.3 70B Versatile</li>\n          <li>Mixtral 8x7B MoE</li>\n          <li>Llama 3.2 11B Vision</li>\n          <li>File & Code Analysis</li>\n          <li>ZIP Archive Reading</li>\n          <li class="locked">Llama 4 Scout/Maverick</li>\n          <li class="locked">DeepSeek R1 / Qwen QwQ</li>\n        </ul>\n        <button class="plan-buy-btn" onclick="openPayment(\'basic\')">GET BASIC</button>\n      </div>\n\n      <!-- PRO -->\n      <div class="plan-card pro">\n        <div class="plan-card-name">PRO HACKER</div>\n        <div class="plan-price" id="price-pro" style="color:var(--cyan)">₹199</div>\n        <div class="plan-price-sub" id="price-pro-sub">/month</div>\n        <ul class="plan-features">\n          <li>Everything in Basic</li>\n          <li>Llama 4 Scout 17B</li>\n          <li>Llama 4 Maverick 17B</li>\n          <li>Llama 3.2 90B Vision</li>\n          <li>Advanced Multimodal</li>\n          <li>Priority Processing</li>\n          <li class="locked">DeepSeek R1 / Qwen QwQ</li>\n        </ul>\n        <button class="plan-buy-btn" onclick="openPayment(\'pro\')">GET PRO</button>\n      </div>\n\n      <!-- ELITE -->\n      <div class="plan-card elite">\n        <div class="plan-card-name">ELITE HACKER</div>\n        <div class="plan-price" id="price-elite" style="color:var(--orange)">₹399</div>\n        <div class="plan-price-sub" id="price-elite-sub">/month</div>\n        <ul class="plan-features">\n          <li>ALL Models Unlocked</li>\n          <li>DeepSeek R1 70B</li>\n          <li>Qwen QwQ 32B Reasoning</li>\n          <li>PlayAI Text-to-Speech</li>\n          <li>Max Context Windows</li>\n          <li>Full Vision + File Support</li>\n          <li>⚡ Highest Priority</li>\n        </ul>\n        <button class="plan-buy-btn" onclick="openPayment(\'elite\')">GO ELITE</button>\n      </div>\n    </div>\n  </div>\n\n  <!-- ── ADMIN PAGE ── -->\n  <div id="page-admin">\n    <div class="admin-title">⚡ OWNER PANEL</div>\n    <button class="nav-btn" onclick="loadAdminPayments()" style="margin-bottom:20px">↻ REFRESH</button>\n    <div id="admin-payments"></div>\n  </div>\n\n</div>\n</div>\n\n<!-- ══════ PAYMENT MODAL ══════ -->\n<div class="modal-overlay" id="payment-modal" style="display:none">\n  <div class="modal">\n    <button class="modal-close" onclick="closePayment()">✕</button>\n    <div class="modal-title">// COMPLETE PAYMENT</div>\n\n    <div class="qr-container">\n      <!-- Replace this src with your actual UPI QR image URL -->\n      <img class="qr-img" src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=upi://pay?pa=your-upi@okaxis&pn=HackerAI&am=AMOUNT" id="qr-img" alt="UPI QR"/>\n      <div class="qr-label">SCAN TO PAY VIA UPI</div>\n    </div>\n\n    <div class="amount-display" id="modal-amount">₹99</div>\n    <div class="modal-info" id="modal-info">Basic Hacker — Monthly Plan</div>\n\n    <div class="input-group" style="margin-bottom:10px">\n      <label class="input-label">// YOUR UPI UTR / TRANSACTION ID</label>\n      <input class="input-field" type="text" id="utr-input" placeholder="Enter UTR after payment"/>\n    </div>\n    <div class="input-group" style="margin-bottom:20px">\n      <label class="input-label">// YOUR EMAIL (for confirmation)</label>\n      <input class="input-field" type="email" id="modal-email" readonly/>\n    </div>\n\n    <button class="btn-primary" onclick="submitPayment()">SUBMIT PAYMENT REQUEST</button>\n    <div style="font-family:var(--font-hud);font-size:0.65rem;color:var(--dim);text-align:center;margin-top:12px;line-height:1.8">\n      Owner will verify & activate your plan within 1-2 hrs<br>\n      Confirmation email will be sent to your registered email\n    </div>\n    <div class="auth-error" id="payment-err"></div>\n  </div>\n</div>\n\n<!-- ══════ TOAST ══════ -->\n<div class="toast" id="toast"></div>\n\n<script>\n// ══ STARS ══\n(function(){\n  const c=document.getElementById(\'stars-canvas\');\n  const ctx=c.getContext(\'2d\');\n  let W,H,stars=[];\n  function resize(){W=c.width=window.innerWidth;H=c.height=window.innerHeight;}\n  function make(){\n    stars=[];\n    for(let i=0;i<200;i++)stars.push({\n      x:Math.random()*W,y:Math.random()*H,\n      r:Math.random()*1.2+0.2,\n      o:Math.random(),speed:Math.random()*0.3+0.05,\n      twinkle:Math.random()*Math.PI*2\n    });\n  }\n  function draw(){\n    ctx.clearRect(0,0,W,H);\n    const t=Date.now()/1000;\n    stars.forEach(s=>{\n      s.twinkle+=s.speed*0.05;\n      const o=s.o*(0.5+0.5*Math.sin(s.twinkle));\n      ctx.beginPath();\n      ctx.arc(s.x,s.y,s.r,0,Math.PI*2);\n      ctx.fillStyle=`rgba(0,255,136,${o})`;\n      ctx.fill();\n    });\n    requestAnimationFrame(draw);\n  }\n  window.addEventListener(\'resize\',()=>{resize();make();});\n  resize();make();draw();\n})();\n\n// ══ STATE ══\nlet currentUser = null;\nlet selectedModel = \'llama-3.1-8b-instant\';\nlet selectedModelInfo = null;\nlet chatHistory = [];\nlet attachedFile = null;\nlet currentDuration = \'monthly\';\nlet paymentPlan = null;\n\nconst PRICES = {\n  basic:  {monthly:99,  \'3month\':249, yearly:799},\n  pro:    {monthly:199, \'3month\':499, yearly:1599},\n  elite:  {monthly:399, \'3month\':999, yearly:2999},\n};\nconst DUR_LABEL = {monthly:\'/month\', \'3month\':\'/3 months\', yearly:\'/year\'};\n\n// ══ INIT ══\nwindow.onload = async () => {\n  const res = await fetch(\'/api/me\');\n  const data = await res.json();\n  if(data.logged_in){\n    currentUser = data;\n    showApp();\n    loadModels();\n  }\n};\n\n// ══ AUTH ══\nfunction switchTab(t){\n  document.getElementById(\'login-form\').style.display = t===\'login\'?\'\':\'none\';\n  document.getElementById(\'register-form\').style.display = t===\'register\'?\'\':\'none\';\n  document.querySelectorAll(\'.tab-btn\').forEach((b,i)=>{\n    b.classList.toggle(\'active\', (i===0&&t===\'login\')||(i===1&&t===\'register\'));\n  });\n}\n\nasync function doLogin(){\n  const email = document.getElementById(\'login-email\').value.trim();\n  const pass = document.getElementById(\'login-pass\').value;\n  document.getElementById(\'login-err\').textContent=\'\';\n  const res = await fetch(\'/api/login\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({email,password:pass})});\n  const data = await res.json();\n  if(data.error){document.getElementById(\'login-err\').textContent=data.error;return;}\n  currentUser = data;\n  const me = await (await fetch(\'/api/me\')).json();\n  currentUser = me;\n  showApp();\n  loadModels();\n}\n\nasync function doRegister(){\n  const email = document.getElementById(\'reg-email\').value.trim();\n  const pass = document.getElementById(\'reg-pass\').value;\n  const pass2 = document.getElementById(\'reg-pass2\').value;\n  document.getElementById(\'reg-err\').textContent=\'\';\n  if(pass!==pass2){document.getElementById(\'reg-err\').textContent=\'Passwords do not match\';return;}\n  const res = await fetch(\'/api/register\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({email,password:pass})});\n  const data = await res.json();\n  if(data.error){document.getElementById(\'reg-err\').textContent=data.error;return;}\n  const me = await (await fetch(\'/api/me\')).json();\n  currentUser = me;\n  showApp();\n  loadModels();\n}\n\nasync function logout(){\n  await fetch(\'/api/logout\',{method:\'POST\'});\n  currentUser=null;chatHistory=[];\n  document.getElementById(\'auth-screen\').style.display=\'flex\';\n  document.getElementById(\'main-app\').style.display=\'none\';\n}\n\nfunction showApp(){\n  document.getElementById(\'auth-screen\').style.display=\'none\';\n  document.getElementById(\'main-app\').style.display=\'flex\';\n  document.getElementById(\'main-app\').style.flexDirection=\'column\';\n  // Nav\n  const planBadge = document.getElementById(\'nav-plan-badge\');\n  planBadge.textContent = (currentUser.plan||\'free\').toUpperCase();\n  planBadge.className = \'plan-badge \'+(currentUser.plan||\'free\');\n  document.getElementById(\'nav-email\').textContent = currentUser.email;\n  if(currentUser.is_owner) document.getElementById(\'admin-tab\').style.display=\'\';\n  document.getElementById(\'modal-email\').value = currentUser.email;\n}\n\n// ══ MODELS ══\nasync function loadModels(){\n  const res = await fetch(\'/api/models\');\n  const data = await res.json();\n  const plan = currentUser.plan||\'free\';\n  const hierarchy = [\'free\',\'basic\',\'pro\',\'elite\'];\n\n  // Free models\n  const freeList = document.getElementById(\'free-model-list\');\n  freeList.innerHTML=\'\';\n  data.free.forEach(m=>{\n    freeList.appendChild(makeModelItem(m, false, false));\n  });\n\n  // Paid models\n  const paidList = document.getElementById(\'paid-model-list\');\n  paidList.innerHTML=\'\';\n  data.paid.forEach(m=>{\n    const locked = hierarchy.indexOf(plan) < hierarchy.indexOf(m.plan);\n    paidList.appendChild(makeModelItem(m, true, locked));\n  });\n\n  selectModel(\'llama-3.1-8b-instant\', {id:\'llama-3.1-8b-instant\',name:\'Llama 3.1 8B\',vision:false});\n}\n\nfunction makeModelItem(m, isPaid, locked){\n  const div = document.createElement(\'div\');\n  div.className = \'model-item\'+(locked?\' locked\':\'\');\n  div.id=\'model-\'+m.id.replace(/\\//g,\'_\').replace(/\\./g,\'_\');\n  const dotClass = locked?\'dot-locked\':isPaid?`dot-${m.plan||\'basic\'}`:\'dot-free\';\n  div.innerHTML=`\n    <div class="model-dot ${dotClass}"></div>\n    <div class="model-info">\n      <div class="model-name">${m.name}</div>\n      <div class="model-desc">${m.desc}${m.vision?\'<span class="vision-tag"> 👁</span>\':\'\'}</div>\n    </div>\n  `;\n  if(!locked) div.onclick=()=>selectModel(m.id,m);\n  return div;\n}\n\nfunction selectModel(id, info){\n  selectedModel=id;\n  selectedModelInfo=info;\n  document.querySelectorAll(\'.model-item\').forEach(el=>el.classList.remove(\'active\'));\n  const el = document.getElementById(\'model-\'+id.replace(/\\//g,\'_\').replace(/\\./g,\'_\'));\n  if(el) el.classList.add(\'active\');\n  document.getElementById(\'active-model-label\').textContent=info.name.toUpperCase();\n  document.querySelector(\'.chat-header div div:last-child\').textContent=id;\n  document.getElementById(\'vision-badge\').style.display=info.vision?\'\':\'none\';\n}\n\n// ══ CHAT ══\nfunction handleKey(e){\n  if(e.key===\'Enter\'&&!e.shiftKey){e.preventDefault();sendMessage();}\n}\nfunction autoResize(el){\n  el.style.height=\'auto\';\n  el.style.height=Math.min(el.scrollHeight,160)+\'px\';\n}\n\nfunction onFileSelect(){\n  const f=document.getElementById(\'file-input\').files[0];\n  if(!f) return;\n  attachedFile=f;\n  document.getElementById(\'file-name\').textContent=`📎 ${f.name} (${(f.size/1024).toFixed(1)}KB)`;\n  document.getElementById(\'file-preview\').style.display=\'flex\';\n}\nfunction removeFile(){\n  attachedFile=null;\n  document.getElementById(\'file-input\').value=\'\';\n  document.getElementById(\'file-preview\').style.display=\'none\';\n}\n\nasync function sendMessage(){\n  const input=document.getElementById(\'msg-input\');\n  const msg=input.value.trim();\n  if(!msg&&!attachedFile) return;\n  \n  const btn=document.getElementById(\'send-btn\');\n  btn.disabled=true;\n\n  if(msg) appendMsg(\'user\',msg);\n  input.value=\'\';input.style.height=\'auto\';\n  if(attachedFile&&!msg) appendMsg(\'user\',`📎 Uploaded: ${attachedFile.name}`);\n\n  const typingId=appendTyping();\n\n  const fd=new FormData();\n  fd.append(\'model\',selectedModel);\n  fd.append(\'message\',msg);\n  fd.append(\'history\',JSON.stringify(chatHistory));\n  if(attachedFile) fd.append(\'file\',attachedFile);\n\n  chatHistory.push({role:\'user\',content:msg||(attachedFile?`[File: ${attachedFile.name}]`:\'\')});\n  removeFile();\n\n  try{\n    const res=await fetch(\'/api/chat\',{method:\'POST\',body:fd});\n    const data=await res.json();\n    removeTyping(typingId);\n    if(data.error){\n      appendMsg(\'ai\',`⚠️ Error: ${data.error}`);\n      if(data.error.includes(\'Upgrade\')) showPage(\'plans\');\n    } else {\n      appendMsg(\'ai\',data.reply);\n      chatHistory.push({role:\'assistant\',content:data.reply});\n    }\n  } catch(e){\n    removeTyping(typingId);\n    appendMsg(\'ai\',\'⚠️ Connection error. Try again.\');\n  }\n  btn.disabled=false;\n}\n\nfunction appendMsg(role,text){\n  const msgs=document.getElementById(\'messages\');\n  const div=document.createElement(\'div\');\n  div.className=`msg ${role===\'user\'?\'user\':\'ai\'}`;\n  div.innerHTML=`\n    <div class="msg-avatar">${role===\'user\'?\'YOU\':\'AI\'}</div>\n    <div class="msg-bubble">${formatMsg(text)}</div>\n  `;\n  msgs.appendChild(div);\n  msgs.scrollTop=msgs.scrollHeight;\n}\n\nfunction formatMsg(text){\n  // Code blocks\n  text=text.replace(/```(\\w*)\\n?([\\s\\S]*?)```/g,(_,lang,code)=>`<pre><code>${escHtml(code.trim())}</code></pre>`);\n  // Inline code\n  text=text.replace(/`([^`]+)`/g,\'<code>$1</code>\');\n  // Bold\n  text=text.replace(/\\*\\*(.*?)\\*\\*/g,\'<strong style="color:var(--cyan)">$1</strong>\');\n  // Newlines\n  text=text.replace(/\\n/g,\'<br>\');\n  return text;\n}\nfunction escHtml(t){return t.replace(/&/g,\'&amp;\').replace(/</g,\'&lt;\').replace(/>/g,\'&gt;\');}\n\nfunction appendTyping(){\n  const id=\'typing-\'+Date.now();\n  const msgs=document.getElementById(\'messages\');\n  const div=document.createElement(\'div\');\n  div.className=\'msg ai\';div.id=id;\n  div.innerHTML=`<div class="msg-avatar">AI</div><div class="msg-bubble"><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>`;\n  msgs.appendChild(div);msgs.scrollTop=msgs.scrollHeight;\n  return id;\n}\nfunction removeTyping(id){document.getElementById(id)?.remove();}\n\n// ══ PAGES ══\nfunction showPage(page){\n  document.getElementById(\'page-chat\').style.display=page===\'chat\'?\'flex\':\'none\';\n  document.getElementById(\'page-plans\').style.display=page===\'plans\'?\'block\':\'none\';\n  document.getElementById(\'page-admin\').style.display=page===\'admin\'?\'block\':\'none\';\n  document.querySelectorAll(\'.page-tab\').forEach((t,i)=>{\n    t.classList.toggle(\'active\',[\'chat\',\'plans\',\'admin\'][i]===page);\n  });\n  if(page===\'admin\') loadAdminPayments();\n}\n\n// ══ PLANS ══\nfunction setDuration(d){\n  currentDuration=d;\n  document.querySelectorAll(\'.dur-btn\').forEach(b=>{\n    b.classList.toggle(\'active\',b.textContent.toLowerCase().includes(d.slice(0,3)));\n  });\n  [\'basic\',\'pro\',\'elite\'].forEach(p=>{\n    const price=PRICES[p][d];\n    document.getElementById(`price-${p}`).textContent=`₹${price}`;\n    document.getElementById(`price-${p}-sub`).textContent=DUR_LABEL[d];\n  });\n}\n\nfunction openPayment(plan){\n  paymentPlan=plan;\n  const amt=PRICES[plan][currentDuration];\n  document.getElementById(\'modal-amount\').textContent=`₹${amt}`;\n  document.getElementById(\'modal-info\').textContent=`${plan.charAt(0).toUpperCase()+plan.slice(1)} Hacker — ${currentDuration} plan`;\n  // Update QR with amount\n  document.getElementById(\'qr-img\').src=`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=upi://pay?pa=your-upi@okaxis%26pn=HackerAI%26am=${amt}`;\n  document.getElementById(\'payment-err\').textContent=\'\';\n  document.getElementById(\'utr-input\').value=\'\';\n  document.getElementById(\'payment-modal\').style.display=\'flex\';\n}\nfunction closePayment(){document.getElementById(\'payment-modal\').style.display=\'none\';}\n\nasync function submitPayment(){\n  const utr=document.getElementById(\'utr-input\').value.trim();\n  if(!utr){document.getElementById(\'payment-err\').textContent=\'Enter UTR / Transaction ID\';return;}\n  const res=await fetch(\'/api/payment/request\',{\n    method:\'POST\',headers:{\'Content-Type\':\'application/json\'},\n    body:JSON.stringify({plan:paymentPlan,duration:currentDuration,utr})\n  });\n  const data=await res.json();\n  if(data.error){document.getElementById(\'payment-err\').textContent=data.error;return;}\n  closePayment();\n  toast(\'Payment request sent! Owner will verify & activate within 1-2 hrs ✅\');\n}\n\n// ══ ADMIN ══\nasync function loadAdminPayments(){\n  const res=await fetch(\'/api/admin/payments\');\n  const data=await res.json();\n  const container=document.getElementById(\'admin-payments\');\n  if(data.error){container.innerHTML=`<div style="color:var(--red)">${data.error}</div>`;return;}\n  if(!data.requests.length){container.innerHTML=\'<div style="color:var(--dim);font-family:var(--font-hud)">No pending requests.</div>\';return;}\n  container.innerHTML=data.requests.map(r=>`\n    <div class="payment-row">\n      <div class="payment-info">\n        <strong>${r.email}</strong> — ${r.plan.toUpperCase()} (${r.duration})<br>\n        <span style="color:var(--cyan)">₹${r.amount}</span> &nbsp;|&nbsp; UTR: <span style="color:var(--orange)">${r.utr||\'N/A\'}</span><br>\n        <span style="color:var(--dim);font-size:0.7rem">${new Date(r.created_at).toLocaleString()} | ID: #${r.id}</span>\n      </div>\n      <button class="approve-btn" onclick="approvePayment(${r.id})">✓ APPROVE</button>\n    </div>\n  `).join(\'\');\n}\n\nasync function approvePayment(id){\n  const res=await fetch(\'/api/admin/approve\',{\n    method:\'POST\',headers:{\'Content-Type\':\'application/json\'},\n    body:JSON.stringify({request_id:id})\n  });\n  const data=await res.json();\n  if(data.ok){toast(\'Plan activated & email sent ✅\');loadAdminPayments();}\n  else toast(data.error||\'Error\',\'error\');\n}\n\n// ══ TOAST ══\nfunction toast(msg,type=\'\'){\n  const t=document.getElementById(\'toast\');\n  t.textContent=msg;t.className=\'toast show \'+(type===\'error\'?\'error\':\'\');\n  setTimeout(()=>t.className=\'toast\',3500);\n}\n\n// Init prices\nsetDuration(\'monthly\');\n</script>\n</body>\n</html>\n'

def get_db():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    try:
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
        print("DB initialized OK")
    except Exception as e:
        print(f"DB init warning: {e}")

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
    cur.execute("INSERT INTO users (email, password_hash) VALUES (%s,%s) RETURNING id", (email, hash_password(pw)))
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
    content = []
    if message:
        content.append({"type": "text", "text": message})
    model_info = next((m for m in PAID_MODELS + FREE_MODELS if m["id"] == model_id), None)
    supports_vision = model_info and model_info.get("vision", False)
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
    messages = [{"role": "system", "content": "You are HACKER AI — an elite AI assistant specialized in cybersecurity, programming, and technical research. Be direct and precise."}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": content if len(content) > 1 else content[0]["text"]})
    try:
        resp = client.chat.completions.create(model=model_id, messages=messages, max_tokens=4096)
        reply = resp.choices[0].message.content
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO chat_history (user_id, model, role, content) VALUES (%s,%s,'user',%s)", (uid, model_id, message))
            cur.execute("INSERT INTO chat_history (user_id, model, role, content) VALUES (%s,%s,'assistant',%s)", (uid, model_id, reply))
            conn.commit(); cur.close(); conn.close()
        except:
            pass
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/models")
def models():
    return jsonify({"free": FREE_MODELS, "paid": PAID_MODELS})

@app.route("/api/payment/request", methods=["POST"])
def payment_request():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    plan = data.get("plan")
    duration = data.get("duration")
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
    try:
        user = get_user_by_id(uid)
        send_email(OWNER_EMAIL, "New Payment - HACKER AI",
                   f"User: {user['email']}\nPlan: {plan} ({duration})\nAmount: Rs.{amount}\nUTR: {utr}\nID: {req_id}")
    except:
        pass
    return jsonify({"ok": True, "request_id": req_id})

@app.route("/api/admin/payments")
def admin_payments():
    uid = session.get("user_id")
    user = get_user_by_id(uid) if uid else None
    if not user or not user["is_owner"]:
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pr.*, u.email FROM payment_requests pr JOIN users u ON pr.user_id = u.id WHERE pr.status='pending' ORDER BY pr.created_at DESC")
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
    pr = dict(cur.fetchone())
    dur_map = {"monthly": 30, "3month": 90, "yearly": 365}
    days = dur_map.get(pr["duration"], 30)
    expires = datetime.now() + timedelta(days=days)
    cur.execute("UPDATE users SET plan=%s, plan_expires=%s WHERE id=%s", (pr["plan"], expires, pr["user_id"]))
    cur.execute("UPDATE payment_requests SET status='approved' WHERE id=%s", (req_id,))
    conn.commit()
    target_user = get_user_by_id(pr["user_id"])
    try:
        send_email(target_user["email"], "HACKER AI Plan Activated!",
                   f"Plan: {pr['plan'].upper()}\nDuration: {pr['duration']}\nExpires: {expires.strftime('%Y-%m-%d')}\n\nLogin now and enjoy!")
    except:
        pass
    cur.close(); conn.close()
    return jsonify({"ok": True})

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

@app.route("/")
def index():
    return Response(HTML_CONTENT, mimetype="text/html")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
