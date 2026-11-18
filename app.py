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
MEMBER_RECORD_ID = "MEMBER_MASTER_DATA"


def get_today_str():
    return datetime.now(JST).strftime("%Y-%m-%d")


def format_date_ja(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}({WEEKDAYS_JA[dt.weekday()]})"
    except Exception:
        return date_str


def get_month_week_label(date_str):
    """日付から '11月第3週' のようなラベルを自動計算"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # その月の中で同じ曜日が何回目か（1〜7日=第1週、8〜14日=第2週、15〜21日=第3週...）
        week_num = (dt.day - 1) // 7 + 1
        return f"{dt.month}月第{week_num}週"
    except Exception:
        return ""


def load_members():
    """部員マスタ（呼び名・本名）を schedules テーブルの専用レコードから取得"""
    try:
        res = supabase.table("schedules").select("*").eq("id", MEMBER_RECORD_ID).execute()
        if res.data:
            raw = res.data[0].get("recipe_note", "") or "[]"
            return json.loads(raw)
    except Exception:
        pass
    return []


def save_members(members):
    """部員マスタを Supabase に保存（追加・編集・削除に対応）"""
    payload = {
        "id": MEMBER_RECORD_ID,
        "date": "1900-01-01",
        "event": "__MEMBER_MASTER__",
        "recipe_note": json.dumps(members, ensure_ascii=False),
    }
    try:
        res = supabase.table("schedules").select("id").eq("id", MEMBER_RECORD_ID).execute()
        if res.data:
            supabase.table("schedules").update(payload).eq("id", MEMBER_RECORD_ID).execute()
        else:
            supabase.table("schedules").insert(payload).execute()
    except Exception:
        pass


def build_mention_text(shoppers_str, members):
    """呼び名から本名を引いて '@本名 買い出しお願いします！' を生成"""
    if not shoppers_str:
        return ""
    nick_to_real = {
        m.get("nickname", "").strip(): m.get("real_name", "").strip()
        for m in members
        if m.get("nickname")
    }
    names = [s.strip() for s in shoppers_str.replace(",", "、").split("、") if s.strip()]
    mentions = []
    for nick in names:
        real = nick_to_real.get(nick) or nick
        mentions.append(f"@{real}")
    if not mentions:
        return ""
    return f"{' '.join(mentions)} 買い出しお願いします！"


def normalize_schedule(row, members):
    """単日データと複数日合宿データを統一フォーマットに変換"""
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

    shoppers_str = item.get("shoppers", "") or ""
    item["days"] = days
    item["start_date"] = days[0].get("date", item.get("date", ""))
    item["end_date"] = days[-1].get("date", item.get("date", ""))
    item["week_label"] = get_month_week_label(item["start_date"])
    item["start_date_ja"] = format_date_ja(item["start_date"])
    item["end_date_ja"] = format_date_ja(item["end_date"])
    item["is_multi_day"] = len(days) > 1
    item["selected_shoppers"] = [
        s.strip() for s in shoppers_str.replace(",", "、").split("、") if s.strip()
    ]
    item["mention_text"] = build_mention_text(shoppers_str, members)
    return item


def load_schedules(members):
    try:
        res = supabase.table("schedules").select("*").execute()
        rows = [
            r for r in (res.data or [])
            if r.get("id") != MEMBER_RECORD_ID and r.get("event") != "__MEMBER_MASTER__"
        ]
        return [normalize_schedule(r, members) for r in rows]
    except Exception:
        return []


@app.route("/")
def index():
    members = load_members()
    all_schedules = load_schedules(members)
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
        members=members,
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


@app.route("/save_member", methods=["POST"])
def save_member():
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    member_id = request.form.get("member_id", "").strip()
    nickname = request.form.get("nickname", "").strip()
    real_name = request.form.get("real_name", "").strip()

    if not nickname or not real_name:
        flash("呼び名と本名の両方を入力してください。")
        return redirect(url_for("index"))

    members = load_members()
    if member_id:
        for m in members:
            if m.get("id") == member_id:
                m["nickname"] = nickname
                m["real_name"] = real_name
                break
        flash(f"部員「{nickname}」の情報を更新しました！")
    else:
        members.append({
            "id": str(random.randint(100000, 999999)),
            "nickname": nickname,
            "real_name": real_name,
        })
        flash(f"部員「{nickname}（{real_name}）」を登録しました！")

    save_members(members)
    return redirect(url_for("index"))


@app.route("/delete_member/<member_id>", methods=["POST"])
def delete_member(member_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    members = [m for m in load_members() if m.get("id") != member_id]
    save_members(members)
    flash("部員を削除しました。")
    return redirect(url_for("index"))


@app.route("/save_schedule", methods=["POST"])
def save_schedule():
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    schedule_id = request.form.get("schedule_id", "").strip()
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

    selected_shoppers = [s.strip() for s in request.form.getlist("shoppers_select[]") if s.strip()]
    extra_shoppers = request.form.get("shoppers_extra", "").strip()
    if extra_shoppers:
        for e in extra_shoppers.replace(",", "、").split("、"):
            if e.strip() and e.strip() not in selected_shoppers:
                selected_shoppers.append(e.strip())
    shoppers_str = "、".join(selected_shoppers)

    if days:
        first = days[0]
        record = {
            "date": first["date"],
            "event": "__DAYS__:" + json.dumps(days, ensure_ascii=False),
            "morning": first["morning"],
            "lunch_menu": first["lunch_menu"],
            "lunch_url": first["lunch_url"],
            "dinner_menu": first["dinner_menu"],
            "dinner_url": first["dinner_url"],
            "recipe_note": request.form.get("recipe_note", "").strip(),
            "shoppers": shoppers_str,
        }
        if schedule_id:
            supabase.table("schedules").update(record).eq("id", schedule_id).execute()
            flash("予定の変更を保存しました！")
        else:
            record["id"] = str(random.randint(100000, 999999))
            supabase.table("schedules").insert(record).execute()
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
