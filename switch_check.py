"""
自動連携に切り替えられるようになったかを毎日確認して、🛠️｜運営連絡 にお知らせする

  FANBOX  ：手動で認証した FANBOX の支援者が10人以上（FANBOXのDiscord連携は支援者10人から）
  Twitch  ：30_desu がアフィリエイト（またはパートナー）になった
  YouTube ：チャンネルに「メンバーになる」ボタンが出た（チャンネルメンバーシップ開始）

同じお知らせは1回だけ（運営連絡に [切替通知:○○] が既にあれば送らない）。
GitHub Actions で1日1回動かす想定（switch-check.yml）。
"""
import os
import urllib.parse

import dapi
from dapi import api, http

FANBOX_NEEDED = 10

STEPS = {
    "FANBOX": (
        "FANBOX の手動認証が {n} 人になりました。FANBOX のDiscord連携（支援者10人以上）が使えるはずです。\n"
        "1. FANBOX の管理画面 → クリエイター設定 → Discord連携 でサーバー「黒寝ゼミ」をつなぐ\n"
        "2. 各プランに、Discordの 🎧 聴講生／📝 ゼミ生／🔬 研究室メンバー／🌟 特別研究員 を結びつける\n"
        "3. 連携を入れると、FANBOXで支援していない人からはFANBOXがロールを外す場合があります。"
        "YouTube・Twitchで手動認証した人は、それぞれの自動連携のロールに先に移しておいてください"
    ),
    "Twitch": (
        "Twitch（{login}）がアフィリエイトになりました！サブスクのロールを自動で付けられます。\n"
        "1. Discord のサーバー設定 → 連携サービス → Twitch でつなぐ（ロールが自動でできます）\n"
        "2. できたロール（Tier1〜3）のIDを roles.json の Twitch 欄（聴講生／ゼミ生／研究室メンバー）に入れる\n"
        "3. 手動認証した Twitch の人は、自動のロールが付いたのを確認してから「取り消し @その人」"
    ),
    "YouTube": (
        "YouTube のチャンネルメンバーシップが始まったようです！メンバーのロールを自動で付けられます。\n"
        "1. Discord のサーバー設定 → 連携サービス → YouTube でつなぐ（メンバーのレベルごとにロールができます）\n"
        "2. できたロールのIDを roles.json の YouTube 欄（聴講生／ゼミ生／研究室メンバー）に入れる\n"
        "3. 手動認証した YouTube の人は、自動のロールが付いたのを確認してから「取り消し @その人」"
    ),
}


def fanbox_count(log_ch, me):
    recs = dapi.manual_records(log_ch, me)
    return sum(1 for r in recs.values() if r and r[0] == "FANBOX")


def twitch_is_affiliate(client_id, secret, login):
    tok = http("POST", "https://id.twitch.tv/oauth2/token",
               form={"client_id": client_id, "client_secret": secret,
                     "grant_type": "client_credentials"})["access_token"]
    data = http("GET", "https://api.twitch.tv/helix/users?" + urllib.parse.urlencode({"login": login}),
                {"Client-Id": client_id, "Authorization": f"Bearer {tok}"})
    users = data.get("data", [])
    return bool(users) and users[0].get("broadcaster_type") in ("affiliate", "partner")


def youtube_has_membership(channel_id):
    html = http("GET", f"https://www.youtube.com/channel/{channel_id}",
                {"Accept-Language": "ja,en;q=0.8"}, raw=True)
    return '"sponsorButton"' in html


def main():
    if not dapi.TOKEN:
        print("DISCORD_TOKEN が未設定のため、何もせず終了します")
        return
    staff_ch = os.environ["STAFF_CHANNEL_ID"]
    log_ch = os.environ["LOG_CHANNEL_ID"]
    mention_role = os.environ.get("MENTION_ROLE_ID", "")
    login = os.environ.get("TWITCH_LOGIN", "30_desu")
    me = api("GET", "/users/@me")["id"]

    sent = " ".join(m.get("content", "") for m in dapi.history(staff_ch, 300) if m["author"]["id"] == me)
    ready = {}

    try:
        n = fanbox_count(log_ch, me)
        print(f"FANBOX 手動認証 {n} 人")
        if n >= FANBOX_NEEDED:
            ready["FANBOX"] = {"n": n}
    except Exception as e:
        print(f"FANBOX の確認に失敗: {e!r}")

    tw_id, tw_secret = os.environ.get("TWITCH_CLIENT_ID", ""), os.environ.get("TWITCH_CLIENT_SECRET", "")
    if tw_id and tw_secret:
        try:
            if twitch_is_affiliate(tw_id, tw_secret, login):
                ready["Twitch"] = {"login": login}
            print(f"Twitch アフィリエイト: {'Twitch' in ready}")
        except Exception as e:
            print(f"Twitch の確認に失敗: {e!r}")
    else:
        print("Twitch: TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET が未設定のため確認できません")

    yt = os.environ.get("YT_CHANNEL_ID", "")
    if yt:
        try:
            if youtube_has_membership(yt):
                ready["YouTube"] = {}
            print(f"YouTube メンバーシップ: {'YouTube' in ready}")
        except Exception as e:
            print(f"YouTube の確認に失敗: {e!r}")

    for key, fmt in ready.items():
        tag = f"[切替通知:{key}]"
        if tag in sent:
            print(f"{key}: お知らせ済み")
            continue
        pre = f"<@&{mention_role}> " if mention_role else ""
        api("POST", f"/channels/{staff_ch}/messages", {
            "content": f"{pre}🔔 {tag} {key} の自動連携に切り替えられます\n" + STEPS[key].format(**fmt),
            "allowed_mentions": {"roles": [mention_role]} if mention_role else {"parse": []},
        })
        print(f"{key}: お知らせを送信")


if __name__ == "__main__":
    main()
