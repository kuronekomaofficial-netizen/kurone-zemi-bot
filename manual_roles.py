"""
手動（半自動）のロール付け ― FANBOX・YouTube・Twitch の自動連携が使えるようになるまでのつなぎ

使い方（運営）
  1. ファンが 🎫｜支援の確認 に「支援しているサイトとプランが分かる画面」を貼る
  2. 運営（教授・TA）がその投稿にリアクションを2つ付ける
       サイト：💗 FANBOX ／ ❤️ YouTube ／ 💜 Twitch
       プラン：🎧 聴講生 ／ 📝 ゼミ生 ／ 🔬 研究室メンバー ／ 🌟 特別研究員（FANBOXのみ）
     → 数分以内にBotがロールを付け、🗂️｜ログ に記録し、本人にDMして、投稿を消す
     ❌ を付けると「確認できませんでした」とDMして投稿を消す（ロールは付けない）
  3. 支援が終わった人は、運営が 🎫｜支援の確認 に「取り消し @その人」と書く
     → プランのロールを外して記録し、その書き込みを消す

記録は 🗂️｜ログ に残り、fan_check.py（毎週の出席確認）が「どのサイトのどのプランか」として読みます。
GitHub Actions で5分おきに動かす想定（notify.yml の中で一緒に実行）。
"""
import json
import os
from datetime import datetime, timedelta, timezone

import dapi
from dapi import api, norm_emoji, q

PLANS = ["聴講生", "ゼミ生", "研究室メンバー", "特別研究員"]
SITE_EMOJI = {"💗": "FANBOX", "❤": "YouTube", "💜": "Twitch"}
PLAN_EMOJI = {"🎧": "聴講生", "📝": "ゼミ生", "🔬": "研究室メンバー", "🌟": "特別研究員"}
REJECT_EMOJI = "❌"
JST = timezone(timedelta(hours=9))


def plan_roles(path):
    """roles.json の FANBOX 欄＝サーバーのプランロール {プラン名: ロールID}"""
    with open(path, encoding="utf-8") as f:
        fanbox = json.load(f).get("FANBOX", {})
    return {p: str(ids[0]) for p, ids in fanbox.items() if ids}


def decide(msg, staff_reactions):
    """
    投稿1つについて、運営が付けたリアクションから何をするか決める（テストしやすいよう純粋関数）
    staff_reactions: 運営が付けた絵文字（norm_emoji 済み）の集合
    戻り値: ("approve", site, plan) / ("reject",) / ("error", 理由) / None（まだ何もしない）
    """
    if REJECT_EMOJI in staff_reactions:
        return ("reject",)
    sites = [SITE_EMOJI[e] for e in SITE_EMOJI if e in staff_reactions]
    plans = [PLAN_EMOJI[e] for e in PLAN_EMOJI if e in staff_reactions]
    if not sites or not plans:
        return None
    if len(sites) > 1 or len(plans) > 1:
        return ("error", "サイトとプランのリアクションは1つずつにしてください")
    site, plan = sites[0], plans[0]
    if plan == "特別研究員" and site != "FANBOX":
        return ("error", "特別研究員はFANBOX限定のプランです")
    return ("approve", site, plan)


class Runner:
    def __init__(self, guild_id, apply_ch, log_ch, staff_role_ids, roles):
        self.g, self.apply_ch, self.log_ch = guild_id, apply_ch, log_ch
        self.staff = set(staff_role_ids)
        self.roles = roles  # {プラン: ロールID}
        self.me = api("GET", "/users/@me")["id"]
        self._member_cache = {}

    def member(self, uid):
        if uid not in self._member_cache:
            try:
                self._member_cache[uid] = api("GET", f"/guilds/{self.g}/members/{uid}")
            except Exception:
                self._member_cache[uid] = None
        return self._member_cache[uid]

    def is_staff(self, uid):
        m = self.member(uid)
        return bool(m and self.staff & set(m.get("roles", [])))

    def staff_reactions(self, msg):
        got = set()
        for r in msg.get("reactions", []):
            name = r["emoji"].get("name") or ""
            if r["emoji"].get("id"):  # サーバー独自の絵文字は対象外
                continue
            users = api("GET", f"/channels/{self.apply_ch}/messages/{msg['id']}/reactions/{q(name)}?limit=100") or []
            if any(u["id"] != self.me and self.is_staff(u["id"]) for u in users):
                got.add(norm_emoji(name))
        return got

    def staff_who_reacted(self, msg, emojis):
        for r in msg.get("reactions", []):
            name = r["emoji"].get("name") or ""
            if norm_emoji(name) in emojis:
                for u in api("GET", f"/channels/{self.apply_ch}/messages/{msg['id']}/reactions/{q(name)}?limit=100") or []:
                    if u["id"] != self.me and self.is_staff(u["id"]):
                        return u["id"]
        return None

    def log(self, text):
        api("POST", f"/channels/{self.log_ch}/messages",
            {"content": text, "allowed_mentions": {"parse": []}})

    def dm(self, uid, text):
        try:
            ch = api("POST", "/users/@me/channels", {"recipient_id": uid})
            api("POST", f"/channels/{ch['id']}/messages", {"content": text})
        except Exception:
            pass  # DMを閉じている人もいる

    def set_plan(self, uid, plan):
        """他のプランロールを外して、そのプランのロールを付ける（plan=None なら全部外す）"""
        current = set((self.member(uid) or {}).get("roles", []))
        for p, rid in self.roles.items():
            if p != plan and rid in current:
                api("DELETE", f"/guilds/{self.g}/members/{uid}/roles/{rid}")
        if plan:
            api("PUT", f"/guilds/{self.g}/members/{uid}/roles/{self.roles[plan]}")

    def delete(self, msg):
        try:
            api("DELETE", f"/channels/{self.apply_ch}/messages/{msg['id']}")
        except Exception:
            pass

    def run(self):
        msgs = list(reversed(api("GET", f"/channels/{self.apply_ch}/messages?limit=50") or []))
        today = datetime.now(JST).strftime("%Y-%m-%d")
        done = 0
        for m in msgs:
            author = m["author"]["id"]
            if author == self.me or m["author"].get("bot"):
                continue

            # 取り消し（運営の書き込み）
            if m.get("content", "").strip().startswith("取り消し") and self.is_staff(author):
                for u in m.get("mentions", []):
                    self.set_plan(u["id"], None)
                    self.log(f"🎫 [取消] <@{u['id']}> uid={u['id']} {today} by <@{author}>")
                    done += 1
                self.delete(m)
                continue

            if self.is_staff(author):
                continue  # 運営のふつうの書き込みはそのまま

            d = decide(m, self.staff_reactions(m))
            if d is None:
                continue
            if d[0] == "error":
                api("POST", f"/channels/{self.apply_ch}/messages/{m['id']}/reactions/{q('⚠️')}/@me")
                print(f"⚠️ {m['id']}: {d[1]}")
                continue
            if d[0] == "reject":
                self.dm(author, "🖤 黒寝ゼミです。送ってもらった画面では支援を確認できませんでした。"
                                "サイトとプランが分かる画面で、もう一度 🎫｜支援の確認 に送ってください。")
                self.log(f"🎫 [却下] <@{author}> uid={author} {today}")
                self.delete(m)
                done += 1
                continue

            _, site, plan = d
            if plan not in self.roles:
                print(f"⚠️ roles.json の FANBOX 欄に「{plan}」のロールIDがありません")
                continue
            staff = self.staff_who_reacted(m, set(PLAN_EMOJI)) or ""
            self.set_plan(author, plan)
            self.log(f"🎫 [認証] <@{author}> uid={author} site={site} plan={plan} {today}"
                     + (f" by <@{staff}>" if staff else ""))
            self.dm(author, f"🖤🐈‍⬛💤 黒寝ゼミへようこそ！ {site} の **{plan}** として確認できたので、"
                            "お部屋が見えるようになりました。送ってもらった画面は消してあります。")
            self.delete(m)
            done += 1
        print(f"手動ロール：処理 {done} 件")


if __name__ == "__main__":
    if not dapi.TOKEN:
        print("DISCORD_TOKEN が未設定のため、何もせず終了します")
        raise SystemExit(0)
    Runner(
        guild_id=os.environ["GUILD_ID"],
        apply_ch=os.environ["APPLY_CHANNEL_ID"],
        log_ch=os.environ["LOG_CHANNEL_ID"],
        staff_role_ids=[x.strip() for x in os.environ["STAFF_ROLE_IDS"].split(",") if x.strip()],
        roles=plan_roles(os.environ.get("ROLES_FILE", "roles.json")),
    ).run()
