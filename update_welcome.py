"""
受付3チャンネル（ようこそ・ルール・ロール連携のしかた）の案内文だけを書き換える。
文面は setup_server.py の WELCOME をそのまま使う。権限・チャンネル・ロールには一切触らない。

  pip install discord.py
  DISCORD_TOKEN=... GUILD_ID=... python update_welcome.py

DRY_RUN=true を付けると、書き換えずに「どこが変わるか」だけ表示します。
"""
import os
import discord

import setup_server as S  # LAYOUT と WELCOME を読むだけ（setup は実行されません）

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    try:
        await run()
    finally:
        await client.close()


async def run():
    g = client.get_guild(S.GUILD_ID) or await client.fetch_guild(S.GUILD_ID)
    channels = await g.fetch_channels()

    # 絵文字なしの名前 → 実際のチャンネル
    by_name = {}
    for _cat, _level, chs in S.LAYOUT:
        for _kind, emoji, name, _ro, _topic in chs:
            ch = discord.utils.get(channels, name=f"{emoji}｜{name}")
            if ch:
                by_name[name] = ch

    for name, text in S.WELCOME.items():
        ch = by_name.get(name)
        if ch is None:
            print(f"⚠️ チャンネルが見つかりません: {name}（名前が setup_server.py の LAYOUT と一致しているか確認）")
            continue
        texts = text if isinstance(text, list) else [text]

        mine = []
        async for m in ch.history(limit=100, oldest_first=True):
            if m.author.id == client.user.id and m.type == discord.MessageType.default:
                mine.append(m)

        for i, t in enumerate(texts):
            for cname, c in by_name.items():
                t = t.replace(f"<#{cname}>", c.mention)
            if i >= len(mine):
                print(f"⚠️ {name}: Botの投稿が{i + 1}通目まで見つかりません（新規投稿はしません）")
                continue
            if mine[i].content == t:
                print(f"変更なし {name} ({i + 1}通目)")
            elif DRY_RUN:
                print(f"[DRY_RUN] 書き換え予定 {name} ({i + 1}通目)")
            else:
                await mine[i].edit(content=t)
                print(f"書き換え完了 {name} ({i + 1}通目)")


if __name__ == "__main__":
    client.run(S.TOKEN)
