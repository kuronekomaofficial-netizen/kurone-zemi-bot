"""
黒寝ゼミ 自動通知（YouTube / Twitch）
- YouTubeのショート・動画が公開されたら      → 🎬｜動画ショート通知
- YouTubeライブ・Twitchの配信が始まったら    → 🔴｜配信通知

実行後すぐ終わる「1回だけ動く」スクリプト。GitHub Actions で5分おきに起動する想定。
外部ライブラリ不要（Python標準ライブラリのみ）。

二重通知の防止：投稿先チャンネルの直近のBot投稿を見て、同じ動画・配信がすでにあれば送らない。
（記録用のファイルは使わないので、何度実行しても大丈夫）

環境変数
  必須  DISCORD_TOKEN      Botのトークン（setup_server.py と同じBot）
  必須  YT_CHANNEL_ID      YouTubeのチャンネルID（UC…）
  必須  VIDEO_CHANNEL_ID   🎬｜動画ショート通知 のチャンネルID
  必須  LIVE_CHANNEL_ID    🔴｜配信通知 のチャンネルID
  任意  YT_API_KEY         YouTube Data API のキー。あるとYouTubeライブの開始を見分けられる
                           （ないときは、ショート以外はすべて「動画」として通知）
  任意  TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET / TWITCH_LOGIN   Twitchの配信開始通知
  任意  LIVE_MENTION       配信開始時のメンション。ロールID か everyone。空ならメンションなし
  任意  MAX_AGE_HOURS      これより古いショート・動画は通知しない（初回に昔の動画が流れないように）。既定 12
  任意  DRY_RUN=true       投稿せずに、送る予定の内容だけ表示
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DISCORD_API = "https://discord.com/api/v10"
UA = "kurone-zemi-notify/1.0"

TOKEN = os.environ.get("DISCORD_TOKEN", "")
if not TOKEN:  # Secrets を登録する前は何もしないで終わる（失敗メールが届かないように）
    print("DISCORD_TOKEN が未設定のため、何もせず終了します")
    raise SystemExit(0)
YT_CHANNEL_ID = os.environ["YT_CHANNEL_ID"]
VIDEO_CHANNEL_ID = os.environ["VIDEO_CHANNEL_ID"]
LIVE_CHANNEL_ID = os.environ["LIVE_CHANNEL_ID"]
YT_API_KEY = os.environ.get("YT_API_KEY", "")
TW_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TW_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")
TW_LOGIN = os.environ.get("TWITCH_LOGIN", "30_desu")
LIVE_MENTION = os.environ.get("LIVE_MENTION", "").strip()
MAX_AGE = timedelta(hours=float(os.environ.get("MAX_AGE_HOURS", "12")))
LIVE_MAX_AGE = timedelta(hours=12)  # 始まってからこれ以上たった配信は通知しない
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

GOLD = 0xC9A227
ROYAL_BLUE = 0x2F4FB5
YT_RED = 0xFF0000
TW_PURPLE = 0x9146FF
FOOTER = {"text": "🖤🐈‍⬛💤 黒寝ゼミ"}


# ---------- HTTP ----------
def http(method, url, headers=None, body=None, form=None):
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
        raw = r.read()
        ctype = r.headers.get("Content-Type", "")
    return json.loads(raw) if "json" in ctype else raw.decode("utf-8", "replace")


def discord(method, path, body=None):
    return http(method, DISCORD_API + path, {"Authorization": f"Bot {TOKEN}"}, body=body)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------- YouTube ----------
def youtube_feed():
    xml = http("GET", f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}")
    return parse_feed(xml)


def parse_feed(xml):
    items = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        def tag(pattern):
            m = re.search(pattern, entry, re.S)
            return m.group(1) if m else ""
        vid = tag(r"<yt:videoId>([^<]+)</yt:videoId>")
        link = tag(r'<link rel="alternate" href="([^"]+)"')
        title = tag(r"<title>(.*?)</title>")
        title = (title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                 .replace("&quot;", '"').replace("&#39;", "'"))
        items.append({
            "id": vid,
            "title": title,
            "url": link,
            "is_short": "/shorts/" in link,
            "published": parse_time(tag(r"<published>([^<]+)</published>")),
        })
    return items


def youtube_details(ids):
    """videoId → (liveBroadcastContent, liveStreamingDetails)。APIキーがなければ空"""
    if not YT_API_KEY or not ids:
        return {}
    q = urllib.parse.urlencode({"part": "snippet,liveStreamingDetails",
                                "id": ",".join(ids), "key": YT_API_KEY})
    data = http("GET", f"https://www.googleapis.com/youtube/v3/videos?{q}")
    return {v["id"]: (v["snippet"].get("liveBroadcastContent", "none"),
                      v.get("liveStreamingDetails"))
            for v in data.get("items", [])}


def classify(items, details, now):
    """通知するもの: [(種類, item)]。種類 = short / video / yt_live"""
    out = []
    for it in items:
        if it["is_short"]:
            if now - it["published"] <= MAX_AGE:
                out.append(("short", it))
            continue
        if it["id"] in details:
            state, live = details[it["id"]]
            if state == "live":
                start = live.get("actualStartTime") if live else None
                if not start or now - parse_time(start) <= LIVE_MAX_AGE:
                    out.append(("yt_live", it))
                continue
            if state == "upcoming" or live:  # 配信予約の待機所・配信のアーカイブは通知しない
                continue
        if now - it["published"] <= MAX_AGE:
            out.append(("video", it))
    return out


# ---------- Twitch ----------
def twitch_stream():
    if not (TW_ID and TW_SECRET):
        return None
    tok = http("POST", "https://id.twitch.tv/oauth2/token",
               form={"client_id": TW_ID, "client_secret": TW_SECRET,
                     "grant_type": "client_credentials"})["access_token"]
    q = urllib.parse.urlencode({"user_login": TW_LOGIN})
    data = http("GET", f"https://api.twitch.tv/helix/streams?{q}",
                {"Client-Id": TW_ID, "Authorization": f"Bearer {tok}"})
    streams = data.get("data", [])
    return streams[0] if streams else None


# ---------- Discord ----------
def recent_bot_posts(channel_id):
    me = discord("GET", "/users/@me")["id"]
    msgs = discord("GET", f"/channels/{channel_id}/messages?limit=50")
    return [m for m in msgs if m["author"]["id"] == me]


def already_posted(posts, key):
    for m in posts:
        for e in m.get("embeds", []):
            if key in (e.get("url") or ""):
                return True
    return False


def mention():
    if not LIVE_MENTION:
        return "", {"parse": []}
    if LIVE_MENTION.lower() == "everyone":
        return "@everyone ", {"parse": ["everyone"]}
    return f"<@&{LIVE_MENTION}> ", {"roles": [LIVE_MENTION]}


def build_message(kind, it):
    vid = it["id"]
    if kind == "short":
        return VIDEO_CHANNEL_ID, vid, {
            "content": "🖤 新しいショートが上がったよ！",
            "embeds": [{"title": it["title"], "url": f"https://www.youtube.com/shorts/{vid}",
                        "color": GOLD, "image": {"url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"},
                        "footer": FOOTER}],
            "allowed_mentions": {"parse": []},
        }
    if kind == "video":
        return VIDEO_CHANNEL_ID, vid, {
            "content": "🎬 新しい動画が公開されたよ！",
            "embeds": [{"title": it["title"], "url": f"https://www.youtube.com/watch?v={vid}",
                        "color": ROYAL_BLUE,
                        "image": {"url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"},
                        "footer": FOOTER}],
            "allowed_mentions": {"parse": []},
        }
    # yt_live
    pre, allowed = mention()
    return LIVE_CHANNEL_ID, vid, {
        "content": f"{pre}🔴 こまがYouTubeで配信を始めました！🖤🐈‍⬛💤",
        "embeds": [{"title": it["title"], "url": f"https://www.youtube.com/watch?v={vid}",
                    "color": YT_RED, "author": {"name": "YouTube Live"},
                    "image": {"url": f"https://i.ytimg.com/vi/{vid}/hqdefault_live.jpg"},
                    "footer": FOOTER}],
        "allowed_mentions": allowed,
    }


def build_twitch_message(s):
    pre, allowed = mention()
    thumb = s["thumbnail_url"].replace("{width}", "1280").replace("{height}", "720")
    url = f"https://www.twitch.tv/{TW_LOGIN}?stream={s['id']}"  # 配信ごとに別URLにして二重通知を防ぐ
    embed = {"title": s.get("title") or "配信中", "url": url, "color": TW_PURPLE,
             "author": {"name": "Twitch"},
             "image": {"url": f"{thumb}?t={s['id']}"}, "footer": FOOTER,
             "timestamp": s["started_at"]}
    if s.get("game_name"):
        embed["fields"] = [{"name": "ゲーム", "value": s["game_name"], "inline": True}]
    return LIVE_CHANNEL_ID, f"stream={s['id']}", {
        "content": f"{pre}💜 こまがTwitchで配信を始めました！🖤🐈‍⬛💤",
        "embeds": [embed], "allowed_mentions": allowed,
    }


def send(channel_id, key, payload, cache):
    if channel_id not in cache:
        cache[channel_id] = recent_bot_posts(channel_id)
    if already_posted(cache[channel_id], key):
        return
    title = payload["embeds"][0]["title"]
    if DRY_RUN:
        print(f"[DRY_RUN] {channel_id} ← {payload['content']} / {title}")
        return
    msg = discord("POST", f"/channels/{channel_id}/messages", payload)
    cache[channel_id].append(msg)
    print(f"送信 {channel_id} ← {title}")


def main():
    now = datetime.now(timezone.utc)
    cache = {}
    errors = []

    try:
        items = youtube_feed()
        long_ids = [it["id"] for it in items if not it["is_short"]]
        details = youtube_details(long_ids)
        # 古い順に送る（同時に複数あっても投稿順が公開順になるように）
        for kind, it in sorted(classify(items, details, now), key=lambda x: x[1]["published"]):
            send(*build_message(kind, it), cache)
    except Exception as e:  # YouTubeが失敗してもTwitchは続ける
        errors.append(f"YouTube: {e!r}")

    try:
        s = twitch_stream()
        if s and now - parse_time(s["started_at"]) <= LIVE_MAX_AGE:
            send(*build_twitch_message(s), cache)
    except Exception as e:
        errors.append(f"Twitch: {e!r}")

    if errors:
        raise SystemExit("\n".join(errors))
    print("チェック完了")


if __name__ == "__main__":
    main()
