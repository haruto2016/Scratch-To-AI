"""
Scratch × Gemini AI — サーバー
Flask API + scratchattach クラウド変数ブリッジ + Supabase ログ
"""
import os, time, threading
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

try:
    from supabase import create_client
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as e:
    raise SystemExit(f"❌ pip install -r requirements.txt を実行してください: {e}")

# ── 設定 ──────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DEFAULT_MODEL  = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
TABLE          = "scratch_gemini"
CHARSET = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'

# ── クライアント初期化 ─────────────────────────────────────────────
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
_models: dict = {}

def get_model(name):
    if name not in _models:
        _models[name] = genai.GenerativeModel(name)
    return _models[name]

# ── エンコード / デコード ──────────────────────────────────────────
def encode(text: str) -> str:
    r = "1"
    for ch in text:
        r += str(CHARSET.index(ch) if ch in CHARSET else 0).zfill(2)
    return r

def decode(num_val) -> str:
    s = str(int(float(str(num_val))))[1:]   # 先頭の "1" を除去
    return "".join(
        CHARSET[int(s[i:i+2])]
        for i in range(0, len(s)-1, 2)
        if 0 <= int(s[i:i+2]) < len(CHARSET)
    )

def chunk_response(text: str):
    text = text[:345]  # 115文字 × 3チャンク
    body = "".join(str(CHARSET.index(c) if c in CHARSET else 0).zfill(2) for c in text)
    return [
        ("1" + body[i*230:(i+1)*230]) if body[i*230:(i+1)*230] else "0"
        for i in range(3)
    ]

# ── scratchattach ブリッジ ─────────────────────────────────────────
def scratch_bridge():
    user  = os.environ.get("SCRATCH_USERNAME")
    pwd   = os.environ.get("SCRATCH_PASSWORD")
    pid   = os.environ.get("SCRATCH_PROJECT_ID")
    if not all([user, pwd, pid]):
        print("⚠️  SCRATCH_* 環境変数が未設定 — ブリッジを無効化")
        return

    try:
        import scratchattach as sa
    except ImportError:
        print("❌ scratchattach がインストールされていません")
        return

    while True:
        try:
            print("🔗 Scratchクラウドに接続中...")
            session = sa.login(user, pwd)
            cloud   = session.connect_cloud(pid)
            print(f"✅ Scratch接続完了 (project={pid})")
            last = None

            while True:
                try:
                    status = str(cloud.get_var("☁ status") or "0").strip()

                    if status == "1":  # Scratch → 新しいプロンプト
                        raw = cloud.get_var("☁ prompt")
                        if not raw or str(raw) == last:
                            time.sleep(0.5); continue

                        last = str(raw)
                        prompt = decode(raw)
                        print(f"📥 プロンプト: {prompt[:60]}")
                        cloud.set_var("☁ status", 2)  # 処理中

                        # Supabase に記録
                        rec_id = None
                        try:
                            res = supabase.table(TABLE).insert({
                                "prompt": prompt, "model": DEFAULT_MODEL,
                                "session_id": f"scratch_{pid}", "status": "pending",
                                "created_at": datetime.utcnow().isoformat(),
                            }).execute()
                            rec_id = res.data[0]["id"]
                        except Exception as e:
                            print(f"⚠️  DB書き込み: {e}")

                        # Gemini 呼び出し
                        t0 = time.time()
                        try:
                            reply  = get_model(DEFAULT_MODEL).generate_content(prompt).text
                            status_db = "done"
                        except Exception as e:
                            reply     = "エラーが発生しました。"
                            status_db = "error"
                            print(f"❌ Gemini: {e}")

                        ms = int((time.time() - t0) * 1000)
                        print(f"💬 {reply[:60]}... ({ms}ms)")

                        # Supabase を更新
                        if rec_id:
                            try:
                                supabase.table(TABLE).update({
                                    "response": reply, "status": status_db,
                                    "duration_ms": ms,
                                    "updated_at": datetime.utcnow().isoformat(),
                                }).eq("id", rec_id).execute()
                            except Exception as e:
                                print(f"⚠️  DB更新: {e}")

                        # 応答を送信
                        r1, r2, r3 = chunk_response(reply)
                        cloud.set_var("☁ resp1", r1)
                        cloud.set_var("☁ resp2", r2)
                        cloud.set_var("☁ resp3", r3)
                        time.sleep(0.3)
                        cloud.set_var("☁ status", 3)  # 完了
                        print("✅ 応答送信完了")

                    time.sleep(0.5)

                except Exception as e:
                    print(f"⚠️  ループエラー: {e}")
                    time.sleep(2)

        except Exception as e:
            print(f"❌ 接続エラー: {e} — 15秒後に再接続")
            time.sleep(15)

# ── Flask ─────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Scratch × Gemini AI 稼働中"})

@app.route("/api/history")
def history():
    try:
        pid = os.environ.get("SCRATCH_PROJECT_ID", "")
        res = (supabase.table(TABLE)
               .select("prompt,response,model,duration_ms,created_at")
               .eq("session_id", f"scratch_{pid}")
               .eq("status", "done")
               .order("created_at", desc=True)
               .limit(20).execute())
        return jsonify({"history": res.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── 起動 ──────────────────────────────────────────────────────────
threading.Thread(target=scratch_bridge, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)
