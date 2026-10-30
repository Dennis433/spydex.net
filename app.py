from flask import Flask, render_template, jsonify, request, Response
import requests

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

def get_tokens(sort="volume_24h", start=0, limit=20):
    try:
        res = requests.get(
            "https://s1.xrplmeta.org/v2/tokens",
            params={
                "limit": limit,
                "offset": start,
                "sort_by": sort,
                "sort_order": "desc"
            },
            headers=HEADERS,
            timeout=8
        )
        if res.status_code == 200:
            raw = res.json()
            items = raw.get("tokens", [])
            print(f"Got {len(items)} tokens from API")

            tokens = []
            for t in items:
                meta = t.get("meta", {})
                token_meta = meta.get("token", {})
                metrics = t.get("metrics", {})

                def safe_float(val):
                    try:
                        v = float(val or 0)
                        return v if v < 1e15 else 0
                    except:
                        return 0

                tokens.append({
                    "currency": t.get("currency", ""),
                    "issuer": t.get("issuer", ""),
                    "name": token_meta.get("name", ""),
                    "icon": token_meta.get("icon", ""),
                    "exch": safe_float(metrics.get("price")),
                    "marketcap": safe_float(metrics.get("marketcap")),
                    "tvl": safe_float(metrics.get("marketcap")),
                    "vol24hxrp": safe_float(metrics.get("volume_24h")),
                    "vol7dxrp": safe_float(metrics.get("volume_7d")),
                    "pro24h": 0,
                    "txns24h": int(metrics.get("exchanges_24h") or 0),
                    "trustlines": int(metrics.get("trustlines") or 0),
                    "holders": int(metrics.get("holders") or 0),
                    "dateon": 0,
                    "md5": None,
                    "ext": None,
                })

            total = raw.get("count", len(tokens))
            print(f"Returning {len(tokens)} tokens")
            return {"tokens": tokens, "total": total}

    except Exception as e:
        print(f"xrplmeta v2 failed: {e}")

    return {"tokens": [], "total": 0}


@app.route("/")
def index():
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
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://xrplmeta.org"
            },
            timeout=8
        )
        return Response(
            res.content,
            content_type=res.headers.get('Content-Type', 'image/png')
        )
    except Exception as e:
        print(f"Image proxy error: {e}")
        return '', 404

@app.route("/api/test")
def test():
    try:
        res = requests.get(
            "https://s1.xrplmeta.org/v2/tokens",
            params={"limit": 3, "sort_by": "volume_24h", "sort_order": "desc"},
            headers=HEADERS,
            timeout=8
        )
        return jsonify({"status": res.status_code, "data": res.json()})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)