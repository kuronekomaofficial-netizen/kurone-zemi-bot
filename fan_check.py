"""
ファン鯖 週次サブスク継続チェック
- YouTubeメンバー / Twitchサブスク / FANBOX支援者 のどのロールも持っていない人を抽出
- 管理用チャンネルにレポートを投稿
- KICK_LAPSED=true のときは該当者をキック（事前にDMでお知らせ）

実行後すぐ終了する「1回だけ動く」スクリプト。GitHub Actions等で週1回起動する想定。
必要: pip install discord.py
Bot設定: Developer Portal で「SERVER MEMBERS INTENT」をON、
         権限は「メンバーをキック」「メッセージ送信」「ロールの閲覧」
"""
import os
import asyncio
from datetime import datetime, timezone, timedelta

import discord

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
REPORT_CHANNEL_ID = int(os.environ["REPORT_CHANNEL_ID"])

# サブスク系ロール（どれか1つあれば継続中とみなす）。カンマ区切りのロールID
SUB_ROLE_IDS = {int(x) for x in os.environ["SUB_ROLE_IDS"].split(",") if x.strip()}
# チェック対象外ロール（運営・モデレーター・招待ゲスト等）
EXEMPT_ROLE_IDS = {int(x) for x in os.environ.get("EXEMPT_ROLE_IDS", "").split(",") if x.strip()}

# 参加して間もない人は除外（連携の反映待ち対策）
GRACE_DAYS = int(os.environ.get("GRACE_DAYS", "3"))
KICK_LAPSED = os.environ.get("KICK_LAPSED", "false").lower() == "true"

DM_TEXT = (
    "こんにちは、黒寝こまのファンサーバー「黒寝ゼミ」運営です。\n"
    "YouTubeメンバーシップ / Twitchサブスク / FANBOX支援 のいずれも確認できなかったため、"
    "サーバーから退出処理を行いました。\n"
    "再開された場合は、各サービスとDiscordの連携後にまたご参加ください。ありがとうございました！"
)

JST = timezone(timedelta(hours=9))

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    try:
        await run_check()
    finally:
        await client.close()


async def run_check():
    guild = client.get_guild(GUILD_ID) or await client.fetch_guild(GUILD_ID)
    channel = guild.get_channel(REPORT_CHANNEL_ID) or await client.fetch_channel(REPORT_CHANNEL_ID)

    now = datetime.now(timezone.utc)
    role_counts = {rid: 0 for rid in SUB_ROLE_IDS}
    lapsed, waiting = [], []

    async for m in guild.fetch_members(limit=None):
        if m.bot:
            continue
        ids = {r.id for r in m.roles}
        if ids & EXEMPT_ROLE_IDS:
            continue
        for rid in ids & SUB_ROLE_IDS:
            role_counts[rid] += 1
        if ids & SUB_ROLE_IDS:
            continue
        if m.joined_at and now - m.joined_at < timedelta(days=GRACE_DAYS):
            waiting.append(m)
        else:
            lapsed.append(m)

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
    breakdown = "\n".join(
        f"{(guild.get_role(rid).name if guild.get_role(rid) else rid)}：{n}人"
        for rid, n in role_counts.items()
    )
    embed.add_field(name="ロール別人数", value=breakdown or "-", inline=False)
    embed.add_field(
        name=f"❌ 継続確認できず（{len(lapsed)}人）" + ("→キック済み" if KICK_LAPSED else ""),
        value=names(lapsed), inline=False,
    )
    if waiting:
        embed.add_field(name=f"⏳ 参加{GRACE_DAYS}日以内・連携待ち（{len(waiting)}人）",
                        value=names(waiting), inline=False)
    if failed:
        embed.add_field(name=f"⚠️ キック失敗（{len(failed)}人）", value=names(failed), inline=False)

    await channel.send(embed=embed)


if __name__ == "__main__":
    client.run(TOKEN)
