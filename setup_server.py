"""
黒寝ゼミ（黒寝こまファンサーバー）雛形セットアップ

FANBOXプランに対応:
  聴講生(620)           → 掲示板・講義室
  ゼミ生(1,200)          → ＋ゼミ室（Discord上位チャンネル）
  研究室メンバー(3,000)    → ＋研究室（限定ボイス・通話対談・ボツ企画）
  特別研究員(6,000)       → ＋特別研究員室（リアル関連の写真）

何度実行してもOK（既存のものは作り直さず、権限だけ揃えます）。
連携ロールができたらIDを登録して再実行してください。

  pip install discord.py
  DISCORD_TOKEN=... GUILD_ID=... \
  SUB_ROLE_IDS=... ZEMI_ROLE_IDS=... LAB_ROLE_IDS=... FELLOW_ROLE_IDS=... python setup_server.py

ロールIDの入れ方（上位プランは下位にも自動で含まれます）:
  SUB_ROLE_IDS    : 聴講生プラン, YouTubeメンバー全般, Twitch Tier1 など
  ZEMI_ROLE_IDS   : ゼミ生プラン, Twitch Tier2 など
  LAB_ROLE_IDS    : 研究室メンバープラン, Twitch Tier3 など
  FELLOW_ROLE_IDS : 特別研究員プラン（6,000円・FANBOX限定。YouTube/Twitchのロールは入れない）
"""
import os
import discord
from discord import PermissionOverwrite as PO

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])


def _ids(key):
    return [int(x) for x in os.environ.get(key, "").split(",") if x.strip()]


SUB_ROLE_IDS = _ids("SUB_ROLE_IDS")
ZEMI_ROLE_IDS = _ids("ZEMI_ROLE_IDS")
LAB_ROLE_IDS = _ids("LAB_ROLE_IDS")
FELLOW_ROLE_IDS = _ids("FELLOW_ROLE_IDS")

STAFF_ROLES = {
    "🐈‍⬛ 教授": (0xFF2D7D, discord.Permissions(administrator=True)),  # こま本人
    "🖤 TA": (0x00C7B7, discord.Permissions(
        manage_messages=True, kick_members=True, moderate_members=True,
        manage_nicknames=True, mute_members=True, move_members=True)),
    "🎓 ゲスト講師": (0xC9D0E8, discord.Permissions.none()),  # コラボ相手・招待ゲスト（講義室まで／週次チェック対象外）
}
R_TA = "🖤 TA"
R_GUEST = "🎓 ゲスト講師"

# level: public / sub(聴講生〜) / zemi(ゼミ生〜) / lab(研究室メンバー〜) / fellow(特別研究員のみ) / guest(ゲスト講師のみ) / staff
# チャンネルは (種類, 絵文字, 名前, 読むだけ?, トピック)。実際のチャンネル名は「絵文字｜名前」
LAYOUT = [
    ("🖤 受付", "public", [
        ("text", "🖤", "ようこそ", True, "🖤 まずはここから！"),
        ("text", "📜", "ルール", True, "📜 ゼミの約束ごと"),
        ("text", "🔗", "ロール連携のしかた", True, "🔗 連携しないと、毎週月曜の確認のときに自動で退出になります"),
    ]),
    ("📣 掲示板", "sub", [
        ("text", "📣", "お知らせ", True, "📢 こまからのお知らせ"),
        ("text", "🗓️", "配信予定", True, "🗓️ 週間スケジュール・ゲリラ告知"),
        ("text", "🔴", "配信通知", True, "🔴 YouTube・Twitchの配信開始を自動でお知らせ"),
        ("text", "🎬", "動画ショート通知", True, "🎬 新着動画・ショートの自動通知"),
        ("text", "🖼️", "限定イラスト", True, "🖼️ 限定イラスト・壁紙の配布（聴講生プラン以上・転載禁止）"),
    ]),
    ("🏫 講義室", "sub", [
        ("text", "💬", "雑談", False, "💬 なんでも気軽に話そう"),
        ("text", "🐈‍⬛", "自己紹介", False, "🐈‍⬛ ゼミ生名簿"),
        ("text", "📺", "配信実況", False, "📺 配信中のつぶやきはこちら"),
        ("text", "🎨", "こま絵馬", False, "🎨 ファンアート置き場 #こま絵馬"),
        ("text", "✂️", "黒寝ゼミ録画", False, "✂️ 切り抜きの共有 #黒寝ゼミ録画"),
        ("text", "⛩️", "山岳信仰と神社の話", False, "⛩️ お勉強枠の感想・質問・語り"),
        ("text", "🗻", "参拝おでかけ報告", False, "🗻 御朱印・山・神社の写真"),
        ("text", "🎰", "パチンコ収支報告", False, "🎰 月末の収支報告への反応・自分の戦績"),
        ("text", "🎮", "ゲーム", False, "🎮 ゲームの話・募集"),
        ("text", "💌", "質問箱", False, "💌 こまへの質問・配信ネタ募集"),
        ("voice", "💤", "作業通話", False, None),
        ("voice", "🍿", "同時視聴", False, None),
    ]),
    ("🎮 参加型", "sub", [
        ("text", "📝", "参加型の募集", False, "📝 参加型配信の参加希望・ゲームID・フレンド申請（サブスク限定）"),
        ("voice", "🎮", "参加型VC", False, None),
        ("voice", "🎮", "参加型VC2", False, None),
    ]),
    ("📝 ゼミ室", "zemi", [
        ("text", "🍵", "ゼミ雑談", False, "🍵 ゼミ生プラン以上のおしゃべり部屋"),
        ("text", "📷", "風景写真", False, "📷 お出かけ先の風景写真"),
        ("text", "📖", "裏話ブログの感想", False, "📖 配信・動画の裏話について"),
    ]),
    ("🔬 研究室", "lab", [
        ("text", "🧪", "研究室雑談", False, "🧪 研究室メンバープラン以上"),
        ("text", "🔊", "限定ボイス", True, "🔊 月1回の限定ボイス・雑談音声"),
        ("text", "🗒️", "ボツ企画と台本", True, "🗒️ ボツ企画・台本の先行公開"),
        ("text", "📞", "通話予約", False, "📞 月1回・15分の通話対談の日程調整"),
        ("voice", "🎙️", "対談室", False, None),
    ]),
    ("🌟 特別研究員室", "fellow", [
        ("text", "📸", "リアル写真", True, "📸 リアル関連の写真（FANBOX特別研究員プラン限定）"),
    ]),
    ("🛠 運営", "staff", [
        ("text", "🛠️", "運営連絡", False, None),
        ("text", "✅", "週次チェック", False, "✅ サブスク継続チェックのレポート"),
        ("text", "🗂️", "ログ", False, None),
    ]),
    ("🤝 コラボ", "guest", [
        ("text", "🤝", "コラボ打ち合わせ", False, "🤝 ゲスト講師との日程・内容の相談用（ゲスト講師と運営のみ）"),
        ("text", "🗓️", "コラボ予定", True, "🗓️ コラボの予定・告知の共有"),
        ("voice", "🎙️", "コラボ通話", False, None),
    ]),
]

# 受付チャンネルに最初に置く文章。<#名前> は実際のチャンネルリンクに置き換わる
WELCOME = {
    "ようこそ": (
        "## 🖤🐈‍⬛💤 黒寝ゼミへようこそ！ 💤🐈‍⬛🖤\n"
        "ここは **黒寝こま** のファンサーバー『黒寝ゼミ』です⛩️\n"
        "ご参加ありがとうございます、**黒寝ゼミ生** のみなさん！🖤\n\n"
        "### 🎒 はじめの3ステップ\n"
        "1️⃣ <#ルール> を読む 📜\n"
        "2️⃣ <#ロール連携のしかた> でサブスクを連携する 🔗\n"
        "3️⃣ <#自己紹介> で自己紹介する 🐈‍⬛\n\n"
        "### 🚪 プランごとに入れるお部屋\n"
        "🎧 **聴講生** → 📣 掲示板（🖼️ 限定イラスト・壁紙もここ）・🏫 講義室\n"
        "📝 **ゼミ生** → ＋ 📝 ゼミ室\n"
        "🔬 **研究室メンバー** → ＋ 🔬 研究室\n"
        "🌟 **特別研究員** → ＋ 🌟 特別研究員室（FANBOX限定プランです）\n\n"
        "### 🏷️ ハッシュタグ・ファンマーク\n"
        "📺 配信・動画 → **#黒寝ゼミ**\n"
        "🎨 ファンアート → **#こま絵馬**\n"
        "✂️ 切り抜き → **#黒寝ゼミ録画**\n"
        "🖤 ファンマーク → **🖤🐈‍⬛💤**（Xの名前などに付けてね）\n\n"
        "-# それでは、今日もゆるっと一緒に研究しましょう💤"
    ),
    "ルール": [
        (
            "## 📏 ゼミの約束\n"
            "黒寝ゼミは、こまと、こまの「好き」を一緒に楽しむ場所です。\n"
            "みんなが安心して過ごせるように、以下の約束をお願いします。"
            "サーバーに参加した時点で、内容に同意したものとさせていただきます。\n\n"
            "### 1. 基本のマナー\n"
            "・こまにも、ゼミ生同士にも、思いやりを持って接してください\n"
            "・誹謗中傷、差別的な発言、晒し、荒らし、煽りは禁止です\n"
            "・他の配信者・VTuberとの比較や、批判・悪口は禁止です\n"
            "・意見が合わないときも、相手を否定せず落ち着いて話しましょう\n\n"
            "### 2. プライバシーを守る\n"
            "・中の人や前世の詮索、推測の書き込みは禁止です\n"
            "・自分や他人の個人情報（本名・住所・勤務先・連絡先など）は書き込まないでください\n"
            "・こまのお出かけ写真などから、場所や生活圏を特定する書き込みは禁止です\n\n"
            "### 3. 限定コンテンツの扱い\n"
            "・限定チャンネル・限定ボイス・先行公開の台本や写真などを、"
            "スクショ・録画・書き起こしで外部に出すことは禁止です\n"
            "・通話対談の録音・録画・配信も禁止です\n"
            "・アカウントの共有や、招待リンクの転載はしないでください"
        ),
        (
            "### 4. 宗教・政治・勧誘\n"
            "・特定の信仰や思想への勧誘、政治的な主張の押しつけは禁止です\n"
            "・神社仏閣・神話・山岳信仰を「学ぶ」「語る」話は大歓迎です\n\n"
            "### 5. 宣伝・金銭・取引\n"
            "・他サーバーや自分のチャンネルの宣伝、URLの連投は禁止です（許可を取った場合を除く）\n"
            "・ゼミ生同士の金銭の貸し借り、物の売買、投資や副業の勧誘は禁止です\n"
            "・DMでの勧誘や、出会い目的の連絡は禁止です\n\n"
            "### 6. パチンコ・お酒の話\n"
            "・こまのパチンコ報告への反応や、ご自身の戦績の話はOKです\n"
            "・ギャンブルの勧誘、必勝法の売り込み、金銭のやり取りは禁止です\n"
            "・未成年の方へ、お酒・タバコ・ギャンブルを勧めることは禁止です\n\n"
            "### 7. 創作・共有\n"
            "・ファンアート（#こま絵馬）と切り抜き（#黒寝ゼミ録画）は大歓迎です\n"
            "・他の方の作品の無断転載や、素材の利用条件に反する投稿は禁止です\n\n"
            "### 8. 違反があったときは\n"
            "TAが内容を確認し、状況に応じて次の順で対応します。\n"
            "注意 → 発言の削除・タイムアウト → キック → BAN\n"
            "悪質な場合は、段階を踏まずに対応することがあります。\n\n"
            "### 9. 困ったときは\n"
            "嫌な思いをしたときや、気になる投稿を見つけたときは、TAにDMで教えてください。\n"
            "サブスクの連携や退出については <#ロール連携のしかた> をご確認ください。\n\n"
            "-# ルールは必要に応じて更新します。更新したときは <#お知らせ> でお伝えします。"
        ),
    ],
    "ロール連携のしかた": (
        "## 🔗✨ ロール連携のしかた ✨🔗\n"
        "サブスクを連携すると、プランに合わせたお部屋が見えるようになります🖤\n\n"
        "### 🧩 連携のしかた\n"
        "💗 **FANBOX**：FANBOXの支援ページからDiscord連携\n"
        "❤️ **YouTubeメンバー**：Discordの「ユーザー設定 → 接続」からYouTubeを連携\n"
        "💜 **Twitchサブスク**：同じく「接続」からTwitchを連携\n"
        "🌟 **特別研究員（6,000円）** は **FANBOX限定** のプランです。YouTube・Twitchでは入れません\n\n"
        "### ⏰ 気をつけてほしいこと\n"
        "⏳ 反映まで、少し時間がかかることがあります\n"
        "⚠️ **参加から3日たっても連携が確認できない場合は、毎週月曜の確認のときに自動で退出になります**\n"
        "🔄 サブスクが終了したときも、週1回の確認のあとに退出となります。"
        "再開したら、いつでも戻ってきてくださいね🐈‍⬛\n\n"
        "-# 困ったときは、🖤 TAまでどうぞ💤"
    ),
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)


async def ensure_role(g, name, color, perms):
    role = discord.utils.get(g.roles, name=name)
    if role:
        return role, False
    return await g.create_role(name=name, colour=discord.Colour(color), permissions=perms,
                               hoist=True, mentionable=False), True


def build_overwrites(g, level, ro, roles):
    def get(ids):
        return [g.get_role(i) for i in ids if g.get_role(i)]

    fellow = get(FELLOW_ROLE_IDS)
    lab = get(LAB_ROLE_IDS) + fellow
    zemi = get(ZEMI_ROLE_IDS) + lab
    sub = get(SUB_ROLE_IDS) + zemi
    ta, guest, me = roles[R_TA], roles[R_GUEST], g.me.top_role

    ow = {}
    if level == "public":
        ow[g.default_role] = PO(view_channel=True, send_messages=False if ro else None,
                                add_reactions=True)
    else:
        ow[g.default_role] = PO(view_channel=False)
        allowed = {"sub": sub + [guest], "zemi": zemi, "lab": lab,
                   "fellow": fellow, "guest": [guest], "staff": []}[level]
        for r in allowed:
            ow[r] = PO(view_channel=True, connect=True, send_messages=False if ro else None)
    ow[ta] = PO(view_channel=True, connect=True, send_messages=True)
    ow[me] = PO(view_channel=True, send_messages=True)
    return ow


@client.event
async def on_ready():
    try:
        await setup()
    finally:
        await client.close()


async def setup():
    g = client.get_guild(GUILD_ID)
    roles = {}
    for name, (color, perms) in STAFF_ROLES.items():
        roles[name], created = await ensure_role(g, name, color, perms)
        print(f"{'作成' if created else '既存'} ロール: {name}  id={roles[name].id}")

    if not (SUB_ROLE_IDS or ZEMI_ROLE_IDS or LAB_ROLE_IDS or FELLOW_ROLE_IDS):
        print("⚠️ 連携ロールIDが未設定です。連携後に登録して再実行してください")

    made = {}  # 絵文字なしの名前 → (チャンネル, 新規か)
    order = []  # 並び順を揃えるための (カテゴリ, [チャンネル...])
    for cat_name, level, channels in LAYOUT:
        cat_ow = build_overwrites(g, level, False, roles)
        cat = discord.utils.get(g.categories, name=cat_name)
        if cat:
            await cat.edit(overwrites=cat_ow)
        else:
            cat = await g.create_category(cat_name, overwrites=cat_ow)
        print(f"カテゴリ: {cat_name}")
        chs = []

        for kind, emoji, name, ro, topic in channels:
            full = f"{emoji}｜{name}"
            ow = build_overwrites(g, level, ro, roles)
            ch = discord.utils.get(cat.channels, name=full)
            if ch:
                if kind == "text" and topic:
                    await ch.edit(overwrites=ow, topic=topic)  # 説明文も最新に揃える
                else:
                    await ch.edit(overwrites=ow)
                new = False
            elif kind == "text":
                ch = await cat.create_text_channel(full, overwrites=ow, topic=topic)
                new = True
            else:
                ch = await cat.create_voice_channel(full, overwrites=ow)
                new = True
            made[name] = (ch, new)
            chs.append(ch)
            print(f"  {'作成' if new else '更新'} {full}  id={ch.id}")
        order.append((cat, chs))

    # カテゴリとチャンネルの並び順を、LAYOUT に書いた順に上書きする
    print("並び順を揃えています…")
    for idx, (cat, _) in enumerate(order):
        await cat.edit(position=idx)
    for cat, chs in order:
        for j, ch in enumerate(chs):
            await ch.edit(position=j)

    # 受付の案内文：新規なら投稿してピン留め、既にあればBot自身の投稿を最新の文面に書き換える
    for name, text in WELCOME.items():
        ch, new = made[name]
        texts = text if isinstance(text, list) else [text]

        mine = []
        if not new:
            async for m in ch.history(limit=100, oldest_first=True):
                if m.author.id == client.user.id and m.type == discord.MessageType.default:
                    mine.append(m)

        for i, t in enumerate(texts):
            for cname, (c, _) in made.items():
                t = t.replace(f"<#{cname}>", c.mention)
            if i < len(mine):
                if mine[i].content != t:
                    await mine[i].edit(content=t)
                    print(f"  案内文を更新 {name} ({i + 1}通目)")
            else:
                msg = await ch.send(t)
                if i == 0:
                    try:
                        await msg.pin()
                    except discord.HTTPException:
                        pass

    all_sub = SUB_ROLE_IDS + ZEMI_ROLE_IDS + LAB_ROLE_IDS + FELLOW_ROLE_IDS
    print("\n==== 週次チェック（fan_check.py）用 ====")
    print(f"REPORT_CHANNEL_ID = {made['週次チェック'][0].id}")
    print(f"SUB_ROLE_IDS      = {','.join(map(str, all_sub))}")
    print(f"EXEMPT_ROLE_IDS   = {','.join(str(roles[k].id) for k in ('🐈‍⬛ 教授', R_TA, R_GUEST))}")


if __name__ == "__main__":
    client.run(TOKEN)
