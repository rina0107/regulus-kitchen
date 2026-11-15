import os
import json
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "regulus-kitchen-secret-key-2026")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
JST = timezone(timedelta(hours=9))
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def get_today_str():
    return datetime.now(JST).strftime("%Y-%m-%d")


def format_date_ja(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}({WEEKDAYS_JA[dt.weekday()]})"
    except Exception:
        return date_str


def normalize_schedule(row):
    """単日データ（旧形式）と複数日合宿データ（新形式）を統一フォーマットに変換"""
    item = dict(row)
    raw_event = item.get("event", "") or ""
    days = []

    if raw_event.startswith("__DAYS__:"):
        try:
            days = json.loads(raw_event[len("__DAYS__:"):])
        except Exception:
            days = []

    if not days:
        days = [{
            "date": item.get("date", ""),
            "event": raw_event if not raw_event.startswith("__DAYS__:") else "",
            "morning": item.get("morning", ""),
            "lunch_menu": item.get("lunch_menu", ""),
            "lunch_url": item.get("lunch_url", ""),
            "dinner_menu": item.get("dinner_menu", ""),
            "dinner_url": item.get("dinner_url", ""),
        }]

    for d in days:
        d["date_ja"] = format_date_ja(d.get("date", ""))

    item["days"] = days
    item["start_date"] = days[0].get("date", item.get("date", ""))
    item["end_date"] = days[-1].get("date", item.get("date", ""))
    item["start_date_ja"] = format_date_ja(item["start_date"])
    item["end_date_ja"] = format_date_ja(item["end_date"])
    item["is_multi_day"] = len(days) > 1
    return item


def load_schedules():
    try:
        res = supabase.table("schedules").select("*").execute()
        return [normalize_schedule(r) for r in (res.data or [])]
    except Exception:
        return []


@app.route("/")
def index():
    all_schedules = load_schedules()
    today_str = get_today_str()

    upcoming_schedules = sorted(
        [s for s in all_schedules if s.get("end_date", "") >= today_str],
        key=lambda x: x.get("start_date", "")
    )
    past_schedules = sorted(
        [s for s in all_schedules if s.get("end_date", "") < today_str],
        key=lambda x: x.get("start_date", ""),
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

    dates = request.form.getlist("day_date[]")
    events = request.form.getlist("day_event[]")
    mornings = request.form.getlist("day_morning[]")
    lunch_menus = request.form.getlist("day_lunch_menu[]")
    lunch_urls = request.form.getlist("day_lunch_url[]")
    dinner_menus = request.form.getlist("day_dinner_menu[]")
    dinner_urls = request.form.getlist("day_dinner_url[]")

    days = []
    for i, d in enumerate(dates):
        d_clean = d.strip()
        if not d_clean:
            continue
        days.append({
            "date": d_clean,
            "event": events[i].strip() if i < len(events) else "",
            "morning": mornings[i].strip() if i < len(mornings) else "",
            "lunch_menu": lunch_menus[i].strip() if i < len(lunch_menus) else "",
            "lunch_url": lunch_urls[i].strip() if i < len(lunch_urls) else "",
            "dinner_menu": dinner_menus[i].strip() if i < len(dinner_menus) else "",
            "dinner_url": dinner_urls[i].strip() if i < len(dinner_urls) else "",
        })

    if days:
        first = days[0]
        new_item = {
            "id": str(random.randint(100000, 999999)),
            "date": first["date"],
            "event": "__DAYS__:" + json.dumps(days, ensure_ascii=False),
            "morning": first["morning"],
            "lunch_menu": first["lunch_menu"],
            "lunch_url": first["lunch_url"],
            "dinner_menu": first["dinner_menu"],
            "dinner_url": first["dinner_url"],
            "recipe_note": request.form.get("recipe_note", "").strip(),
            "shoppers": request.form.get("shoppers", "").strip(),
        }
        supabase.table("schedules").insert(new_item).execute()
        flash("練習・合宿のご飯＆買い出し予定をまとめて登録しました！")

    return redirect(url_for("index"))


@app.route("/delete_schedule/<item_id>", methods=["POST"])
def delete_schedule(item_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    supabase.table("schedules").delete().eq("id", item_id).execute()
    flash("予定を削除しました。")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
