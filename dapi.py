"""Discord REST API を標準ライブラリだけで呼ぶための小さな道具（manual_roles.py / switch_check.py 用）"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://discord.com/api/v10"
UA = "kurone-zemi-bot/1.0"
TOKEN = os.environ.get("DISCORD_TOKEN", "")


def http(method, url, headers=None, body=None, form=None, raw=False):
    h = {"User-Agent": UA, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        content = r.read()
        ctype = r.headers.get("Content-Type", "")
    if raw:
        return content.decode("utf-8", "replace")
    if not content:
        return None
    return json.loads(content) if "json" in ctype else content.decode("utf-8", "replace")


def api(method, path, body=None):
    """Discord API。レート制限(429)のときは待ってから1回だけやり直す"""
    for attempt in range(2):
        try:
            return http(method, API + path, {"Authorization": f"Bot {TOKEN}"}, body=body)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                try:
                    wait = float(json.loads(e.read()).get("retry_after", 2))
                except Exception:
                    wait = 2
                time.sleep(min(wait, 10) + 0.5)
                continue
            raise


def q(s):
    return urllib.parse.quote(s, safe="")


def norm_emoji(s):
    """❤️ と ❤ のような異体字セレクタの違いを無視して比べる"""
    return (s or "").replace("️", "")


def history(channel_id, limit=1000):
    """チャンネルのメッセージを新しい順に最大 limit 件"""
    out, before = [], None
    while len(out) < limit:
        path = f"/channels/{channel_id}/messages?limit=100" + (f"&before={before}" if before else "")
        batch = api("GET", path) or []
        out += batch
        if len(batch) < 100:
            break
        before = batch[-1]["id"]
    return out[:limit]


RECORD_RE = re.compile(r"\[(認証|取消)\][^\n]*?uid=(\d+)(?:[^\n]*?site=(\S+)[^\n]*?plan=(\S+))?")


def manual_records(log_channel_id, bot_id):
    """🗂️｜ログ のBotの記録から、ユーザーごとの最新の手動認証 {uid: (site, plan) or None}"""
    recs = {}
    for m in reversed(history(log_channel_id)):  # 古い順に見て、最後のものを残す
        if m["author"]["id"] != bot_id:
            continue
        for kind, uid, site, plan in RECORD_RE.findall(m.get("content", "")):
            recs[uid] = (site, plan) if kind == "認証" else None
    return recs


SYNC_RE = re.compile(r"\[(同期付与|同期解除|認証|取消)\][^\n]*?uid=(\d+)(?:[^\n]*?role=(\d+))?")


def parse_sync(contents):
    """ログ本文（古い順）から、sync_roles.py が付けて今も有効なプランロール {(uid, role_id)} を求める。
    手動認証・取消（[認証]/[取消]）があった人は、その時点で手動の管理に切り替わったとみなして記録を消す"""
    active = set()
    for text in contents:
        for kind, uid, rid in SYNC_RE.findall(text or ""):
            if kind == "同期付与" and rid:
                active.add((uid, rid))
            elif kind == "同期解除" and rid:
                active.discard((uid, rid))
            elif kind in ("認証", "取消"):
                active = {x for x in active if x[0] != uid}
    return active


def sync_grants(log_channel_id, bot_id):
    msgs = [m for m in reversed(history(log_channel_id)) if m["author"]["id"] == bot_id]
    return parse_sync(m.get("content", "") for m in msgs)
