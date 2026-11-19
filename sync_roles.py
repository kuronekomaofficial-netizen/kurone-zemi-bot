"""
連携ロール → プランロールの同期（出席確認Bot・5分おき）

- 💜1⃣・💜2⃣・💜3⃣（Twitch連携）や YouTube連携のロールを持つ人に、
  対応するプランロール（🎧 聴講生 / 📝 ゼミ生 / 🔬 研究室メンバー）を付ける
- 連携ロールが外れたら、このBotが付けたプランロールだけを外す
  （FANBOX連携・手動認証で付いたロールは触らない）
- 連携ロールの色を、対応するプランロールの色に揃える
- roles.json の「予備ロール」（❤1⃣・💛1⃣ など、まだ連携に使っていないロール）が無ければ作り、色を揃える

対応は roles.json（FANBOX欄＝プランロール、YouTube/Twitch欄＝連携ロール）。
記録は 🗂️｜ログ に [同期付与] / [同期解除] として残し、fan_check.py が「どのサイトから来たか」に使う。
※ メンバー一覧を読むので、Developer Portal の「SERVER MEMBERS INTENT」をONにしておくこと
"""
import json
import os
import urllib.error
from datetime import datetime, timedelta, timezone

import dapi
from dapi import api

JST = timezone(timedelta(hours=9))
LINK_SITES = ["YouTube", "Twitch"]


def load(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    plan_role = {p: str(ids[0]) for p, ids in (raw.get("FANBOX") or {}).items() if ids}
    link = {}  # {連携ロールID: (サイト, プラン)}
    for site in LINK_SITES:
        for plan, ids in (raw.get(site) or {}).items():
            for rid in ids:
                link[str(rid)] = (site, plan)
    return plan_role, link


def plan_changes(uid, have, link, plan_role, grants):
    """1人分の (付けるロール, 外すロール) を決める（テスト用に純粋関数）"""
    want = {plan_role[p] for rid, (_, p) in link.items() if rid in have and p in plan_role}
    add = sorted(want - have)
    remove = sorted(r for (u, r) in grants if u == uid and r in have and r not in want)
    return add, remove


def color_fixes(roles, link, plan_role):
    """[(連携ロールID, 揃える色)]"""
    color = {r["id"]: r.get("color", 0) for r in roles}
    out = []
    for rid, (_, plan) in link.items():
        pr = plan_role.get(plan)
        if rid in color and pr in color and color[rid] != color[pr]:
            out.append((rid, color[pr]))
    return out


def load_spare(path):
    """roles.json の 予備ロール → [(ロール名, プラン)]"""
    with open(path, encoding="utf-8") as f:
        spare = json.load(f).get("予備ロール") or {}
    return [(name, plan) for plans in spare.values() for plan, name in plans.items()]


def spare_actions(roles, spare, plan_role):
    """予備ロールについて [("create", 名前, 色)] / [("color", ロールID, 色)]"""
    color = {r["id"]: r.get("color", 0) for r in roles}
    by_name = {r["name"]: r for r in roles}
    out = []
    for name, plan in spare:
        c = color.get(plan_role.get(plan), 0)
        if name not in by_name:
            out.append(("create", name, c))
        elif by_name[name].get("color", 0) != c:
            out.append(("color", by_name[name]["id"], c))
    return out


def members(guild_id):
    out, after = [], "0"
    while True:
        batch = api("GET", f"/guilds/{guild_id}/members?limit=1000&after={after}") or []
        out += batch
        if len(batch) < 1000:
            return out
        after = batch[-1]["user"]["id"]


def main():
    g, log_ch = os.environ["GUILD_ID"], os.environ["LOG_CHANNEL_ID"]
    path = os.environ.get("ROLES_FILE", "roles.json")
    plan_role, link = load(path)
    roles = api("GET", f"/guilds/{g}/roles") or []

    for act, key, c in spare_actions(roles, load_spare(path), plan_role):
        try:
            if act == "create":
                api("POST", f"/guilds/{g}/roles", {"name": key, "color": c, "permissions": "0"})
                print(f"予備ロールを作成: {key}")
            else:
                api("PATCH", f"/guilds/{g}/roles/{key}", {"color": c})
                print(f"予備ロールの色を揃えた: {key}")
        except urllib.error.HTTPError as e:
            print(f"⚠️ 予備ロール {key}: {e.code}")

    if not link:
        print("roles.json に連携ロールがないので終了")
        return

    for rid, c in color_fixes(roles, link, plan_role):
        try:
            api("PATCH", f"/guilds/{g}/roles/{rid}", {"color": c})
            print(f"色を揃えた: {rid} → #{c:06x}")
        except urllib.error.HTTPError as e:
            print(f"⚠️ 色を変えられません {rid}: {e.code}")

    try:
        mem = members(g)
    except urllib.error.HTTPError as e:
        print(f"⚠️ メンバー一覧を読めません（{e.code}）。Developer Portal で SERVER MEMBERS INTENT をONにしてください")
        return

    me = api("GET", "/users/@me")["id"]
    grants = dapi.sync_grants(log_ch, me)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    names = {v: k for k, v in plan_role.items()}
    n = 0
    for m in mem:
        if m["user"].get("bot"):
            continue
        uid, have = m["user"]["id"], set(m.get("roles", []))
        add, remove = plan_changes(uid, have, link, plan_role, grants)
        site = next((link[r][0] for r in have if r in link), "")
        for r in add:
            api("PUT", f"/guilds/{g}/members/{uid}/roles/{r}")
            api("POST", f"/channels/{log_ch}/messages", {"allowed_mentions": {"parse": []},
                "content": f"🔁 [同期付与] <@{uid}> uid={uid} site={site} plan={names[r]} role={r} {today}"})
            n += 1
        for r in remove:
            api("DELETE", f"/guilds/{g}/members/{uid}/roles/{r}")
            api("POST", f"/channels/{log_ch}/messages", {"allowed_mentions": {"parse": []},
                "content": f"🔁 [同期解除] <@{uid}> uid={uid} plan={names[r]} role={r} {today}"})
            n += 1
    print(f"ロール同期：{len(mem)}人を確認、変更 {n} 件")


if __name__ == "__main__":
    if not dapi.TOKEN:
        print("DISCORD_TOKEN が未設定のため、何もせず終了します")
        raise SystemExit(0)
    main()
