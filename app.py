import os
import json
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "regulus-kitchen-secret-key-2026")

# ★管理者ログイン用のパスワード（好きなものに変更してください）
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")

DATA_FILE = "data.json"
JST = timezone(timedelta(hours=9))

def get_today_str():
    return datetime.now(JST).strftime("%Y-%m-%d")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"schedules": [], "members": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("schedules", [])
                data.setdefault("members", [])
                return data
            return {"schedules": [], "members": []}
    except Exception:
        return {"schedules": [], "members": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    data = load_data()
    all_schedules = data.get("schedules", [])
    today_str = get_today_str()

    # 今日以降の予定（日付昇順）
    upcoming_schedules = sorted(
        [s for s in all_schedules if s.get("date", "") >= today_str],
        key=lambda x: x.get("date", "")
    )
    # 過ぎた日の予定（新しい日付順）
    past_schedules = sorted(
        [s for s in all_schedules if s.get("date", "") < today_str],
        key=lambda x: x.get("date", ""),
        reverse=True
    )

    is_admin = session.get("is_admin", False)
    app_url = request.url_root.rstrip("/")
    return render_template(
        "index.html",
        upcoming_schedules=upcoming_schedules,
        past_schedules=past_schedules,
        is_admin=is_admin,
        app_url=app_url,
        today_str=today_str
    )

@app.route("/login", methods=["POST"])
def login():
    password = request.form.get("password", "")
    if password == ADMIN_PASSWORD:
        session["is_admin"] = True
        flash("管理者としてログインしました！")
    else:
        flash("パスワードが違います。")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    flash("ログアウトしました（閲覧専用モード）")
    return redirect(url_for("index"))

@app.route("/add_schedule", methods=["POST"])
def add_schedule():
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    data = load_data()
    new_item = {
        "id": str(random.randint(100000, 999999)),
        "date": request.form.get("date", "").strip(),
        "event": request.form.get("event", "").strip(),
        "morning": request.form.get("morning", "").strip(),
        "lunch_menu": request.form.get("lunch_menu", "").strip(),
        "lunch_url": request.form.get("lunch_url", "").strip(),
        "dinner_menu": request.form.get("dinner_menu", "").strip(),
        "dinner_url": request.form.get("dinner_url", "").strip(),
        "recipe_note": request.form.get("recipe_note", "").strip(),
        "shoppers": request.form.get("shoppers", "").strip(),
    }
    if new_item["date"]:
        data["schedules"].append(new_item)
        save_data(data)
        flash("練習日のご飯・買い出し予定を追加しました！")
    return redirect(url_for("index"))

@app.route("/delete_schedule/<item_id>", methods=["POST"])
def delete_schedule(item_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    data = load_data()
    data["schedules"] = [s for s in data["schedules"] if s.get("id") != item_id]
    save_data(data)
    flash("予定を削除しました。")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
