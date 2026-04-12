"""
Scratch × Gemini AI サーバー
============================
Supabase（クラウドDB）を使ってGeminiとの会話を管理するFlaskサーバー。

使い方:
  1. .env に Supabase・Gemini の設定を記入
  2. pip install -r requirements.txt
  3. python server.py
  4. TurboWarp でエクステンション(gemini_extension.js)を読み込む
"""

import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# ── ライブラリ読み込み ──────────────────────────────────────────
try:
    from supabase import create_client
except ImportError:
    raise SystemExit("❌ pip install supabase を実行してください")

try:
    import google.generativeai as genai
except ImportError:
    raise SystemExit("❌ pip install google-generativeai を実行してください")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv がなくても環境変数から読む

# ── 設定 ───────────────────────────────────────────────────────
SUPABASE_URL     = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY     = os.environ.get("SUPABASE_KEY", "")
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
TABLE_NAME       = "scratch_gemini"

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY]):
    raise SystemExit(
        "❌ 環境変数が不足しています。.env ファイルを確認してください：\n"
        "   SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY"
    )

# ── Supabase 初期化 ─────────────────────────────────────────────
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Gemini 初期化 ───────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)

# モデルインスタンスのキャッシュ
_model_cache: dict = {}

def get_model(model_name: str):
    if model_name not in _model_cache:
        _model_cache[model_name] = genai.GenerativeModel(model_name)
    return _model_cache[model_name]

# ── Flask アプリ ────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins=["https://turbowarp.org", "http://localhost", "http://127.0.0.1", "*"])


# ── ヘルスチェック ──────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "message": "Scratch × Gemini AI サーバー 稼働中",
        "endpoints": {
            "POST /api/chat":     "Gemini に質問する",
            "GET  /api/history":  "会話履歴を取得",
            "GET  /api/models":   "利用可能なモデル一覧",
        }
    })


# ── チャット ────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    """Gemini に質問し、Supabase に記録して返答を返す"""
    data  = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    model_name = data.get("model") or DEFAULT_MODEL
    session_id = data.get("session_id") or "default"

    if not prompt:
        return jsonify({"error": "prompt が空です"}), 400

    # ── Supabase に pending レコードを作成 ──────────────────────
    try:
        insert_res = supabase.table(TABLE_NAME).insert({
            "prompt":     prompt,
            "model":      model_name,
            "session_id": session_id,
            "status":     "pending",
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
        record_id = insert_res.data[0]["id"]
    except Exception as e:
        return jsonify({"error": f"DB書き込みエラー: {e}"}), 500

    # ── Gemini 呼び出し ─────────────────────────────────────────
    start_ms = time.time()
    try:
        model    = get_model(model_name)
        response = model.generate_content(prompt)
        reply    = response.text
        status   = "done"
        error_msg = None
    except Exception as e:
        reply     = ""
        status    = "error"
        error_msg = str(e)

    elapsed_ms = int((time.time() - start_ms) * 1000)

    # ── Supabase にレスポンスを更新 ─────────────────────────────
    try:
        supabase.table(TABLE_NAME).update({
            "response":    reply,
            "status":      status,
            "error":       error_msg,
            "duration_ms": elapsed_ms,
            "updated_at":  datetime.utcnow().isoformat(),
        }).eq("id", record_id).execute()
    except Exception as e:
        # 記録失敗でも返答はそのまま返す
        app.logger.warning(f"DB更新エラー (無視): {e}")

    if status == "error":
        return jsonify({"error": error_msg}), 500

    return jsonify({
        "id":          record_id,
        "response":    reply,
        "model":       model_name,
        "duration_ms": elapsed_ms,
    })


# ── 会話履歴 ────────────────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
def history():
    """Supabase から会話履歴を取得する"""
    session_id = request.args.get("session_id", "default")
    limit      = min(int(request.args.get("limit", 20)), 100)

    try:
        res = (
            supabase.table(TABLE_NAME)
            .select("id, prompt, response, model, status, duration_ms, created_at")
            .eq("session_id", session_id)
            .eq("status", "done")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return jsonify({"history": res.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── モデル一覧 ──────────────────────────────────────────────────
@app.route("/api/models", methods=["GET"])
def models():
    return jsonify({
        "models": [
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "default": DEFAULT_MODEL,
    })


# ── エントリポイント ────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 サーバー起動: http://localhost:{port}")
    print(f"   Supabase: {SUPABASE_URL[:40]}...")
    print(f"   モデル:   {DEFAULT_MODEL}")
    print(f"   テーブル: {TABLE_NAME}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
