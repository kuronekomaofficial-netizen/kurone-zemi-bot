# 黒寝ゼミ ファンサーバー Bot

| ファイル | 役割 |
| --- | --- |
| `setup_server.py` | ロール・カテゴリ・チャンネル・権限を一括作成し、受付3チャンネルに案内文を投稿（何度実行してもOK） |
| `update_welcome.py` | 受付3チャンネルの案内文（Bot投稿）だけを `setup_server.py` の最新文面に書き換える。権限・チャンネルには触らない |
| `fan_check.py` | 毎週、「どのプランで、どのサイトから来たか」をサイト×プランの人数表と出席簿CSVにして投稿。サブスク系ロールを持たない人も抽出（`KICK_LAPSED=true` でDM→キック） |
| `roles.json` | 連携で付くロールIDと「サイト×プラン」の対応表。`fan_check.py` と `setup_server.py` の両方が読む |
| `notify.py` | YouTubeのショート・動画を 🎬｜動画ショート通知 に、YouTubeライブ・Twitchの配信開始を 🔴｜配信通知 に自動投稿 |
| `manual_roles.py` | 自動連携が使えるまでのつなぎ。🎫｜支援の確認 の投稿に運営がリアクションするとロールを付けて 🗂️｜ログ に記録 |
| `switch_check.py` | FANBOX・Twitch・YouTube の自動連携に切り替えられるようになったら 🛠️｜運営連絡 にお知らせ |
| `dapi.py` | 上の2つが使う Discord API の小さな道具 |
| `.github/workflows/notify.yml` | 5分おきに `notify.py` と `manual_roles.py` を自動実行 |
| `.github/workflows/switch-check.yml` | 毎日9時ごろに `switch_check.py` を自動実行 |
| `.github/workflows/weekly-fan-check.yml` | 毎週月曜10:00(JST)に `fan_check.py` を自動実行 |

## 手順

1. Discordで「黒寝ゼミ」サーバーを作成。ユーザー設定 → 詳細設定 → 開発者モードをON → サーバー名を右クリック →「サーバーIDをコピー」（= `GUILD_ID`）
2. Discord Developer Portal で Application を作成 → Bot → トークン発行 → **SERVER MEMBERS INTENT をON**
3. OAuth2 → URL Generator で `bot` ＋ `Administrator`（セットアップ中だけ）を選び、サーバーに招待。サーバー設定のロールで Bot のロールを一番上へ
4. セットアップ実行

```bash
pip install -r requirements.txt
export DISCORD_TOKEN=...   # 絶対に公開しない
export GUILD_ID=...
python setup_server.py
```

5. YouTube / Twitch（サーバー設定 → 連携サービス）と FANBOX を連携 → できたロールIDを設定して再実行

```bash
export SUB_ROLE_IDS=...    # 聴講生 / YouTubeメンバー / Twitch Tier1
export ZEMI_ROLE_IDS=...   # ゼミ生 / Twitch Tier2
export LAB_ROLE_IDS=...    # 研究室メンバー・特別研究員 / Twitch Tier3
python setup_server.py
```

6. GitHub の Secrets に `DISCORD_TOKEN` を登録（サーバー・チャンネル・ロールのIDは各 yml に直接書いてあるので Secrets は不要）
7. Actions タブで `weekly-fan-check` を手動実行して、`✅｜週次チェック` にレポートが届くか確認
8. 数週間レポートを確認して問題なければ、yml の `KICK_LAPSED` を `"true"` に変更。Bot の管理者権限は外してOK

## 注意

- トークンは `.env` や Secrets にのみ置き、リポジトリにコミットしない
- `fan_check.py` の `SUB_ROLE_IDS` には3段階すべてのロールIDをカンマ区切りで入れる（setup_server.py が最後に結合した値を表示します）
- 退出の案内文は「毎週月曜の確認のときに自動で退出」としているため、`KICK_LAPSED` を `false` のままにする間は案内と実際の動作がずれます

## 自動通知（notify.py）の準備

1. **YouTube Data API キー**（YouTubeライブの開始を見分けるのに使う。なくてもショート・動画の通知は動く）
   Google Cloud Console でプロジェクトを作成 →「YouTube Data API v3」を有効化 → 認証情報 → APIキーを作成
2. **Twitch**：https://dev.twitch.tv/console/apps でアプリを登録（OAuthリダイレクトURLは `http://localhost` でOK、カテゴリは Other）→ Client ID を控え、「新しいシークレット」で Client Secret を発行
3. GitHub の Secrets に追加：`YT_API_KEY` `TWITCH_CLIENT_ID` `TWITCH_CLIENT_SECRET`（`DISCORD_TOKEN` は週次チェックと共通）
4. Actions タブで `notify` を手動実行して動作を確認
   - 初回は、直近12時間以内に上がったショート・動画が通知されます（`MAX_AGE_HOURS` で変更）
   - ローカルで試すときは `DRY_RUN=true` を付けると投稿せずに内容だけ表示します

メモ
- Bot が 🎬・🔴 のチャンネルで「メッセージを見る・送信・埋め込みリンク・メッセージ履歴を読む」をできる必要があります（Botの管理者権限を外した場合は確認）
- 配信開始のメンションは `notify.yml` の `LIVE_MENTION`（`everyone` かロールID）
- 公開リポジトリは60日間更新がないと定期実行が止まります。止まったら Actions タブから再開

## 出席確認（プラン・サイトの管理）

1. FANBOX・YouTube・Twitch をサーバーと連携すると、それぞれロールができます
2. サーバー設定 → ロール → ロールを右クリック →「ロールIDをコピー」で、各ロールのIDを `roles.json` の「サイト → プラン」の欄に入れる
   - 例：Twitch の Tier1 ロール → `"Twitch": {"聴講生": [ロールID]}`
3. `roles.json` を GitHub に上げれば、次の月曜から ✅｜週次チェック に
   - サイト別（FANBOX / YouTube / Twitch）のプラン人数
   - プラン別の人数（複数サイトから入っている人は一番上のプランで1回）
   - 全員の出席簿CSV（表示名・最上位プラン・来たサイト・サイトごとのプラン・状態・参加日）
   が届きます
4. `setup_server.py` も `roles.json` を読むので、もう一度実行するとプランごとの部屋の権限も揃います（`SUB_ROLE_IDS` などの環境変数は不要になります）

## 自動連携が使えるまでの手動ロール付け（manual_roles.py）

FANBOX（支援者10人から）・Twitch（アフィリエイトから）・YouTube（メンバーシップ開始から）の自動連携が使えるまでのつなぎです。

**ファン**：🎫｜支援の確認 に、支援しているサイトとプランが分かる画面を貼る（ほかの人の投稿は見えないチャンネルです）

**運営（教授・TA）**：その投稿にリアクションを2つ付ける
| サイト | プラン |
| --- | --- |
| 💗 FANBOX | 🎧 聴講生 |
| ❤️ YouTube | 📝 ゼミ生 |
| 💜 Twitch | 🔬 研究室メンバー |
| | 🌟 特別研究員（FANBOXのみ） |

- 5〜15分ほどでBotがロールを付け、🗂️｜ログ に `[認証]` を記録、本人にDMして、投稿を消します
- ❌ を付けると「確認できませんでした」とDMして投稿を消します
- 組み合わせがおかしいとき（特別研究員なのにYouTubeなど）は ⚠️ が付きます。リアクションを直してください
- 支援が終わった人は、🎫｜支援の確認 に `取り消し @その人` と書く → ロールを外して `[取消]` を記録
- 毎週の出席確認は、この記録を読んで「どのサイトのどのプランか」を数えます（出席簿の「確認方法」が「手動」）

## 自動連携への切り替えのお知らせ（switch_check.py）

毎日、次のどれかを満たしたら 🛠️｜運営連絡 に 🐈‍⬛ 教授 あてでお知らせします（それぞれ1回だけ）
- FANBOX：手動認証した FANBOX の支援者が10人以上
- Twitch：30_desu がアフィリエイトになった（`TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` が必要）
- YouTube：チャンネルに「メンバーになる」ボタンが出た

お知らせには、切り替えの手順も書いてあります。
