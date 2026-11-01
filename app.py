from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models import db, Visit, User
import requests
import os

app = Flask(__name__)
app.secret_key = "xrpl-admin-secret-2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

ADMIN_PASSWORD = "admin123"  # Change this!

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_location(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=country,city,status",
                          timeout=3)
        data = res.json()
        if data.get('status') == 'success':
            return data.get('country', '—'), data.get('city', '—')
    except:
        pass
    return '—', '—'

def track_visit(page='/'):
    try:
        ip = get_client_ip()
        ua = request.headers.get('User-Agent', '')

        # Simple device detection
        if 'Mobile' in ua or 'Android' in ua:
            device = 'Mobile'
        elif 'Tablet' in ua or 'iPad' in ua:
            device = 'Tablet'
        else:
            device = 'Desktop'

        # Simple browser detection
        if 'Chrome' in ua and 'Edg' not in ua:
            browser = 'Chrome'
        elif 'Firefox' in ua:
            browser = 'Firefox'
        elif 'Safari' in ua and 'Chrome' not in ua:
            browser = 'Safari'
        elif 'Edg' in ua:
            browser = 'Edge'
        else:
            browser = 'Other'

        country, city = get_location(ip)

        # Log visit
        visit = Visit(ip=ip, country=country, city=city,
                     device=device, browser=browser, page=page)
        db.session.add(visit)

        # Update or create user
        user = User.query.filter_by(ip=ip).first()
        if user:
            user.last_seen = datetime.utcnow()
            user.visit_count += 1
        else:
            user = User(ip=ip, country=country, city=city,
                       device=device, browser=browser)
            db.session.add(user)

        db.session.commit()
    except Exception as e:
        print(f"Track error: {e}")

def get_tokens(sort="volume_24h", start=0, limit=20):
    try:
        res = requests.get(
            "https://s1.xrplmeta.org/v2/tokens",
            params={
                "limit": limit,
                "offset": start,
                "sort_by": sort,
                "sort_order": "desc",
                "include_changes": "true"
            },
            headers=HEADERS,
            timeout=8
        )
        if res.status_code == 200:
            raw = res.json()
            items = raw.get("tokens", [])

            tokens = []
            for t in items:
                meta = t.get("meta", {})
                token_meta = meta.get("token", {})
                metrics = t.get("metrics", {})
                changes = metrics.get("changes", {})
                change_24h = changes.get("24h", {})
                change_7d = changes.get("7d", {})

                def safe_float(val):
                    try:
                        v = float(val or 0)
                        return v if abs(v) < 1e15 else 0
                    except:
                        return 0

                pro24h = safe_float(change_24h.get("price", {}).get("percent", 0))
                pro7d = safe_float(change_7d.get("price", {}).get("percent", 0))
                price = safe_float(metrics.get("price"))

                sparkline = []
                if price > 0:
                    price_7d_ago = price / (1 + pro7d / 100) if pro7d != -100 else price
                    price_24h_ago = price / (1 + pro24h / 100) if pro24h != -100 else price
                    for i in range(6):
                        sparkline.append(price_7d_ago + (price_24h_ago - price_7d_ago) * i / 5)
                    sparkline.append(price_24h_ago)
                    sparkline.append(price)

                icon = token_meta.get("icon", "") or meta.get("issuer", {}).get("icon", "")

                tokens.append({
                    "currency": t.get("currency", ""),
                    "issuer": t.get("issuer", ""),
                    "name": token_meta.get("name", "") or meta.get("issuer", {}).get("name", ""),
                    "icon": icon,
                    "exch": price,
                    "marketcap": safe_float(metrics.get("marketcap")),
                    "tvl": safe_float(metrics.get("marketcap")),
                    "vol24hxrp": safe_float(metrics.get("volume_24h")),
                    "vol7dxrp": safe_float(metrics.get("volume_7d")),
                    "pro24h": pro24h,
                    "pro7d": pro7d,
                    "txns24h": int(metrics.get("exchanges_24h") or 0),
                    "trustlines": int(metrics.get("trustlines") or 0),
                    "holders": int(metrics.get("holders") or 0),
                    "dateon": 0,
                    "sparkline": sparkline,
                    "md5": None,
                    "ext": None,
                })

            total = raw.get("count", len(tokens))
            return {"tokens": tokens, "total": total}

    except Exception as e:
        print(f"xrplmeta v2 failed: {e}")

    return {"tokens": [], "total": 0}


# ─── MAIN ROUTES ───────────────────────────────────────────

@app.route("/")
def index():
    track_visit('/')
    return render_template("index.html")


@app.route("/api/latest")
def latest():
    start = int(request.args.get("start", 0))
    limit = int(request.args.get("limit", 20))
    return jsonify(get_tokens("volume_24h", start, limit))


@app.route("/api/trending")
def trending():
    start = int(request.args.get("start", 0))
    limit = int(request.args.get("limit", 20))
    return jsonify(get_tokens("marketcap", start, limit))


@app.route("/api/sparkline/<path:token_id>")
def sparkline(token_id):
    return jsonify([])


@app.route("/api/image")
def image_proxy():
    url = request.args.get("url", "")
    if not url.startswith("https://s1.xrplmeta.org/") and \
       not url.startswith("https://s2.xrplmeta.org/"):
        return '', 403
    try:
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://xrplmeta.org"},
            timeout=8
        )
        return Response(res.content,
                       content_type=res.headers.get('Content-Type', 'image/png'))
    except Exception as e:
        print(f"Image proxy error: {e}")
        return '', 404


# ─── ADMIN ROUTES ──────────────────────────────────────────

@app.route("/admin")
def admin_redirect():
    return redirect(url_for('admin_login'))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        error = "Wrong password"
    return render_template("admin/login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    total_users = User.query.count()
    total_visits = Visit.query.count()
    today = datetime.utcnow().date()
    visits_today = Visit.query.filter(
        db.func.date(Visit.timestamp) == today
    ).count()
    users_today = User.query.filter(
        db.func.date(User.first_seen) == today
    ).count()

    # Device breakdown
    desktop = User.query.filter_by(device='Desktop').count()
    mobile = User.query.filter_by(device='Mobile').count()
    tablet = User.query.filter_by(device='Tablet').count()

    # Top countries
    from sqlalchemy import func
    top_countries = db.session.query(
        User.country,
        func.count(User.id).label('count')
    ).group_by(User.country).order_by(func.count(User.id).desc()).limit(5).all()

    # Recent users
    recent_users = User.query.order_by(User.last_seen.desc()).limit(20).all()

    return render_template("admin/dashboard.html",
        total_users=total_users,
        total_visits=total_visits,
        visits_today=visits_today,
        users_today=users_today,
        desktop=desktop,
        mobile=mobile,
        tablet=tablet,
        top_countries=top_countries,
        recent_users=recent_users
    )


@app.route("/admin/users")
def admin_users():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    page = int(request.args.get('page', 1))
    users = User.query.order_by(User.last_seen.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template("admin/users.html", users=users)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)