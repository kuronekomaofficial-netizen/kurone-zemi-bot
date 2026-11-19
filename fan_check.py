"""
ファン鯖 週次サブスク継続チェック（出席確認）
- メンバーごとに「どのサイト（FANBOX / YouTube / Twitch）の、どのプランで来たか」をロールで判定
- サイト×プランの人数表をレポートし、全員の一覧（出席簿）をCSVで添付
- どのプランのロールも持っていない人を抽出
- KICK_LAPSED=true のときは該当者をキック（事前にDMでお知らせ）

ロールとサイト・プランの対応は roles.json に書く（ロールIDは秘密ではないのでリポジトリに置いてOK）。

実行後すぐ終了する「1回だけ動く」スクリプト。GitHub Actions等で週1回起動する想定。
必要: pip install discord.py
Bot設定: Developer Portal で「SERVER MEMBERS INTENT」をON、
         権限は「メンバーをキック」「メッセージ送信」「ファイルを添付」「ロールの閲覧」

環境変数
  DISCORD_TOKEN / GUILD_ID / REPORT_CHANNEL_ID
  EXEMPT_ROLE_IDS  チェック対象外ロール（教授・TA・ゲスト講師など。カンマ区切り）
  SUB_ROLE_IDS     （任意）roles.json 以外にも「継続中」とみなすロール
  ROLES_FILE       （任意）対応表のパス。既定 roles.json
  LOG_CHANNEL_ID   （任意）🗂️｜ログ。manual_roles.py の手動認証の記録を読み、「どのサイトから来たか」に反映する
"""
import csv
import io
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta

import discord

import dapi

PLANS = ["聴講生", "ゼミ生", "研究室メンバー", "特別研究員"]  # 下位 → 上位
SITES = ["FANBOX", "YouTube", "Twitch"]
SITE_ICON = {"FANBOX": "💛", "YouTube": "❤", "Twitch": "💜"}


def _ids(key):
    return {int(x) for x in os.environ.get(key, "").split(",") if x.strip()}


def load_role_map(path):
    """roles.json → {ロールID: (サイト, プラン)}"""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    role_map = {}
    for site in SITES:
        for plan, ids in (raw.get(site) or {}).items():
            if plan not in PLANS:
                raise SystemExit(f"roles.json: {site} の「{plan}」はプラン名にありません（{'/'.join(PLANS)}）")
            for rid in ids:
                role_map[int(rid)] = (site, plan)
    return role_map


def plans_of(role_ids, role_map):
    """{サイト: そのサイトでの最上位プラン}"""
    out = {}
    for rid in role_ids:
        if rid in role_map:
            site, plan = role_map[rid]
            if site not in out or PLANS.index(plan) > PLANS.index(out[site]):
                out[site] = plan
    return out


def top_plan(site_plans):
    return max(site_plans.values(), key=PLANS.index) if site_plans else None


def apply_manual(sp, rec):
    """手動認証の記録 (サイト, プラン) を反映する。
    手動のときはプランロールが FANBOX 欄のロールなので、YouTube・Twitch の人は FANBOX から付け替える"""
    if not rec:
        return sp
    site, plan = rec
    sp = dict(sp)
    if site != "FANBOX" and sp.get("FANBOX") == plan:
        del sp["FANBOX"]
    if site not in sp or PLANS.index(plan) > PLANS.index(sp[site]):
        sp[site] = plan
    return sp


DM_TEXT = (
    "こんにちは、黒寝こまのファンサーバー「黒寝ゼミ」運営です。\n"
    "YouTubeメンバーシップ / Twitchサブスク / FANBOX支援 のいずれも確認できなかったため、"
    "サーバーから退出処理を行いました。\n"
    "再開された場合は、各サービスとDiscordの連携後にまたご参加ください。ありがとうございました！"
)

JST = timezone(timedelta(hours=9))


async def run_check(client):
    guild = client.get_guild(GUILD_ID) or await client.fetch_guild(GUILD_ID)
    channel = guild.get_channel(REPORT_CHANNEL_ID) or await client.fetch_channel(REPORT_CHANNEL_ID)

    now = datetime.now(timezone.utc)
    table = {s: {p: 0 for p in PLANS} for s in SITES}  # サイト×プランの人数
    top_counts = {p: 0 for p in PLANS}                   # 最上位プラン別の人数（1人1回）
    multi, other_only = 0, 0
    lapsed, waiting = [], []
    roster = []  # 出席簿（CSV）用
    manual, synced = {}, set()
    if LOG_CHANNEL_ID:
        try:
            manual = dapi.manual_records(LOG_CHANNEL_ID, str(client.user.id))
            synced = dapi.sync_grants(LOG_CHANNEL_ID, str(client.user.id))
        except Exception as e:
            print(f"⚠️ 手動認証・同期の記録を読めませんでした: {e!r}")

    async for m in guild.fetch_members(limit=None):
        if m.bot:
            continue
        ids = {r.id for r in m.roles}
        if ids & EXEMPT_ROLE_IDS:
            continue
        rec = manual.get(str(m.id)) if ids & set(ROLE_MAP) else None  # ロールが外れていれば記録は使わない
        # sync_roles.py が Twitch/YouTube 連携から付けたプランロールは、FANBOX としては数えない
        own = ids - {int(r) for (u, r) in synced if u == str(m.id)}
        sp = apply_manual(plans_of(own, ROLE_MAP), rec)
        for s, p in sp.items():
            table[s][p] += 1
        if sp:
            top_counts[top_plan(sp)] += 1
        if len(sp) > 1:
            multi += 1

        if ids & SUB_ROLE_IDS:
            status = "継続中"
            if not sp:
                other_only += 1
        elif m.joined_at and now - m.joined_at < timedelta(days=GRACE_DAYS):
            status = "連携待ち"
            waiting.append(m)
        else:
            status = "確認できず"
            lapsed.append(m)

        roster.append({
            "表示名": m.display_name,
            "ユーザー名": m.name,
            "ユーザーID": str(m.id),
            "プラン（最上位）": top_plan(sp) or "-",
            "来たサイト": " / ".join(s for s in SITES if s in sp) or "-",
            **{f"{s}のプラン": sp.get(s, "-") for s in SITES},
            "確認方法": "手動" if rec else ("自動" if sp else "-"),
            "状態": status,
            "参加日": m.joined_at.astimezone(JST).strftime("%Y-%m-%d") if m.joined_at else "",
        })

    kicked, failed = [], []
    if KICK_LAPSED:
        for m in lapsed:
            try:
                try:
                    await m.send(DM_TEXT)
                except discord.Forbidden:
                    pass  # DM拒否の人もいるのでキックは続行
                await m.kick(reason="週次チェック: サブスク系ロールなし")
                kicked.append(m)
            except discord.HTTPException:
                failed.append(m)
            await asyncio.sleep(1)
        kicked_ids = {str(m.id) for m in kicked}
        for row in roster:
            if row["ユーザーID"] in kicked_ids:
                row["状態"] = "キック済み"

    # レポート作成
    def names(ms, limit=40):
        s = "\n".join(f"・{m.display_name}（{m.name}）" for m in ms[:limit])
        if len(ms) > limit:
            s += f"\n…ほか{len(ms) - limit}人"
        return s or "なし"

    embed = discord.Embed(
        title="📋 週次サブスク継続チェック",
        description=now.astimezone(JST).strftime("%Y-%m-%d %H:%M 時点"),
        color=0xC9A227,  # 金
    )

    if ROLE_MAP:
        for s in SITES:
            plans = [p for p in PLANS if p in RAW_PLANS.get(s, ())]
            total = sum(table[s].values())
            body = "\n".join(f"{p}：{table[s][p]}人" for p in plans) or "-"
            embed.add_field(name=f"{SITE_ICON[s]} {s}（{total}人）", value=body, inline=True)
        lines = [f"{p}：{top_counts[p]}人" for p in PLANS]
        if multi:
            lines.append(f"🔁 複数サイトから：{multi}人（サイト別の表では重複して数えています）")
        if other_only:
            lines.append(f"❔ サイト不明（SUB_ROLE_IDS のロールのみ）：{other_only}人")
        embed.add_field(name="🎓 プラン別（1人につき一番上のプランで1回）", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="どのプランで、どのサイトから来たか",
                        value="⚠️ roles.json にロールIDがまだ入っていません", inline=False)

    embed.add_field(
        name=f"❌ 継続確認できず（{len(lapsed)}人）" + ("→キック済み" if KICK_LAPSED else ""),
        value=names(lapsed), inline=False,
    )
    if waiting:
        embed.add_field(name=f"⏳ 参加{GRACE_DAYS}日以内・連携待ち（{len(waiting)}人）",
                        value=names(waiting), inline=False)
    if failed:
        embed.add_field(name=f"⚠️ キック失敗（{len(failed)}人）", value=names(failed), inline=False)
    embed.set_footer(text="全員の一覧は添付の出席簿（CSV）をExcelやスプレッドシートで開いてください")

    # 出席簿CSV（Excelで文字化けしないようにBOM付きUTF-8）。上位プラン → サイト → 参加日 の順
    fields = ["表示名", "ユーザー名", "ユーザーID", "プラン（最上位）", "来たサイト",
              *[f"{s}のプラン" for s in SITES], "確認方法", "状態", "参加日"]
    order = {p: i for i, p in enumerate(reversed(PLANS))}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(sorted(roster, key=lambda r: (order.get(r["プラン（最上位）"], 99),
                                               r["来たサイト"], r["参加日"])))
    data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    fname = now.astimezone(JST).strftime("出席簿_%Y-%m-%d.csv")

    await channel.send(embed=embed, file=discord.File(data, filename=fname))


if __name__ == "__main__":
    TOKEN = os.environ["DISCORD_TOKEN"]
    GUILD_ID = int(os.environ["GUILD_ID"])
    REPORT_CHANNEL_ID = int(os.environ["REPORT_CHANNEL_ID"])
    ROLES_FILE = os.environ.get("ROLES_FILE", "roles.json")
    ROLE_MAP = load_role_map(ROLES_FILE)
    with open(ROLES_FILE, encoding="utf-8") as f:
        _raw = json.load(f)
    RAW_PLANS = {s: list((_raw.get(s) or {}).keys()) for s in SITES}  # 表に出すプランの欄
    # どれか1つあれば継続中とみなすロール ＝ roles.json の全ロール ＋ SUB_ROLE_IDS
    SUB_ROLE_IDS = set(ROLE_MAP) | _ids("SUB_ROLE_IDS")
    EXEMPT_ROLE_IDS = _ids("EXEMPT_ROLE_IDS")
    LOG_CHANNEL_ID = os.environ.get("LOG_CHANNEL_ID", "")
    GRACE_DAYS = int(os.environ.get("GRACE_DAYS", "3"))
    KICK_LAPSED = os.environ.get("KICK_LAPSED", "false").lower() == "true"

    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            await run_check(client)
        finally:
            await client.close()

    client.run(TOKEN)
