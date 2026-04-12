# Scratch × Gemini AI — デプロイガイド

## 全体像

```
turbowarp.org (Scratch)
    ↓ gemini_extension.js (カスタムエクステンション)
    ↓ HTTPS リクエスト
Railway (クラウドサーバー・常時稼働) ← server.py
    ├── Supabase (クラウドDB) ← 会話履歴を保存
    └── Gemini API ← AI応答を生成
```

> **Railway を選んだ理由**
> Render の無料プランは15分使用がないとスリープしますが、
> Railway は**常時稼働**（無料で $5/月クレジット付き）。

---

## Step 1: Supabase セットアップ

1. [supabase.com](https://supabase.com) でアカウント作成・新規プロジェクト
2. `SQL Editor` を開き `supabase_setup.sql` の内容をペーストして実行
3. 以下の2つをメモ：
   - **Project URL** (`https://xxxx.supabase.co`)
   - **anon public key** (Settings > API)

---

## Step 2: GitHub にプッシュ

```bash
cd scratch-gemini
git init
git add .
git commit -m "Scratch Gemini AI Server"
git remote add origin https://github.com/あなたのユーザー名/scratch-gemini.git
git push -u origin main
```

---

## Step 3: Railway にデプロイ（スリープなし）

1. [railway.app](https://railway.app) でアカウント作成（GitHub でログイン）
2. **New Project → Deploy from GitHub repo** → リポジトリを選択
3. **Variables** タブで環境変数を追加：

   | キー | 値 |
   |---|---|
   | `SUPABASE_URL` | Supabase の Project URL |
   | `SUPABASE_KEY` | Supabase の anon key |
   | `GEMINI_API_KEY` | Google AI Studio のAPIキー |
   | `GEMINI_MODEL` | `gemini-2.0-flash` |

4. **Deploy** → しばらく待つとURLが発行される
   例: `https://scratch-gemini-production.up.railway.app`

5. ブラウザでURLを開いて `{"status":"ok"...}` が表示されれば成功！

---

## Step 4: TurboWarp でエクステンションを読み込む

1. [turbowarp.org](https://turbowarp.org) を開く
2. **拡張機能を追加** → **カスタム拡張機能を読み込む**
3. `gemini_extension.js` ファイルを選択

---

## Step 5: Scratch でブロックを組む

```
[緑の旗が押されたとき]
サーバーURLを [https://scratch-gemini-production.up.railway.app] にする
モデルを [gemini-2.0-flash] にする

ずっと
  [Geminiへの質問:] と聞いて待つ
  (答え) をGeminiに聞く
  (Geminiの返答) と言う
```

---

## ブロック一覧

| ブロック | 説明 |
|---|---|
| `サーバーURLを [url] にする` | Railway のサーバーを指定 |
| `モデルを [model] にする` | Geminiのモデルを選択 |
| `[prompt] をGeminiに聞く` | 送信（完了まで待機） |
| `Geminiの返答` | 最後の返答テキスト |
| `エラーメッセージ` | エラーが出た場合の内容 |
| `返答待ち中か？` | 処理中かどうかのフラグ |
| `応答時間 (ms)` | 何ミリ秒かかったか |

---

## 会話履歴の確認

Supabase ダッシュボード → `scratch_gemini` テーブルで全会話を確認できます。

または Railway サーバー経由で取得:
```
GET https://scratch-gemini-production.up.railway.app/api/history
```
