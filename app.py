import os
import json
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "regulus-kitchen-secret-key-2026")

# ★管理者ログイン用のパスワード（好きなものに変更してください）
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")

DATA_FILE = "data.json"

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
    schedules = sorted(data.get("schedules", []), key=lambda x: x.get("date", ""))
    members = data.get("members", [])
    is_admin = session.get("is_admin", False)
    app_url = request.url_root.rstrip("/")
    return render_template(
        "index.html",
        schedules=schedules,
        members=members,
        is_admin=is_admin,
        app_url=app_url
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
        "menu": request.form.get("menu", "").strip(),
        "recipe_url": request.form.get("recipe_url", "").strip(),
        "recipe_note": request.form.get("recipe_note", "").strip(),
        "shoppers": request.form.get("shoppers", "").strip(),
    }
    if new_item["date"] and new_item["menu"]:
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

@app.route("/update_members", methods=["POST"])
def update_members():
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    raw = request.form.get("members_text", "")
    members = [m.strip() for m in raw.replace("、", ",").split(",") if m.strip()]
    data = load_data()
    data["members"] = members
    save_data(data)
    flash("買い出し候補メンバーを更新しました！")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
