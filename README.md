# 黒寝ゼミ ファンサーバー Bot

| ファイル | 役割 |
| --- | --- |
| `setup_server.py` | ロール・カテゴリ・チャンネル・権限を一括作成し、受付3チャンネルに案内文を投稿（何度実行してもOK） |
| `update_welcome.py` | 受付3チャンネルの案内文（Bot投稿）だけを `setup_server.py` の最新文面に書き換える。権限・チャンネルには触らない |
| `fan_check.py` | 毎週、サブスク系ロールを持たない人を抽出してレポート投稿（`KICK_LAPSED=true` でDM→キック） |
| `notify.py` | YouTubeのショート・動画を 🎬｜動画ショート通知 に、YouTubeライブ・Twitchの配信開始を 🔴｜配信通知 に自動投稿 |
| `.github/workflows/notify.yml` | 5分おきに `notify.py` を自動実行 |
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

6. 最後に表示される値を GitHub の Secrets に登録: `DISCORD_TOKEN` `GUILD_ID` `REPORT_CHANNEL_ID` `SUB_ROLE_IDS` `EXEMPT_ROLE_IDS`
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
