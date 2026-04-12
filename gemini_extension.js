// ============================================================
//  Scratch × Gemini AI エクステンション
//  TurboWarp用カスタムエクステンション
//  フローチャート: Scratch → このエクステンション → Flaskサーバー → Supabase + Gemini
//
//  読み込み方: TurboWarp > 拡張機能 > カスタム拡張機能を読み込む
//              → このファイルを選択 または URLを入力
// ============================================================

(function (Scratch) {
  "use strict";

  // ── 状態 ────────────────────────────────────────────────
  let _serverUrl   = "https://web-production-82403.up.railway.app";
  let _model       = "gemini-2.0-flash";
  let _sessionId   = "scratch_" + Math.random().toString(36).slice(2, 8);
  let _lastResp    = "";
  let _lastError   = "";
  let _isThinking  = false;
  let _lastId      = "";
  let _durationMs  = 0;

  const MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
  ];

  // ── Geminiに送信 ─────────────────────────────────────────
  async function askGemini(prompt) {
    _isThinking = true;
    _lastError  = "";
    try {
      const res = await fetch(`${_serverUrl}/api/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          model:      _model,
          session_id: _sessionId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        _lastError = data.error || `サーバーエラー ${res.status}`;
        _lastResp  = "";
      } else {
        _lastResp   = data.response ?? "";
        _lastId     = data.id       ?? "";
        _durationMs = data.duration_ms ?? 0;
        _lastError  = "";
      }
    } catch (e) {
      _lastError = `接続エラー: ${e.message}`;
      _lastResp  = "";
    } finally {
      _isThinking = false;
    }
  }

  // ── エクステンション定義 ──────────────────────────────────
  class GeminiExtension {
    getInfo() {
      return {
        id:    "geminiAI",
        name:  "✨ Gemini AI",
        color1: "#1a73e8",
        color2: "#0d47a1",
        color3: "#0a3580",
        blocks: [
          // 設定
          {
            opcode: "setServer",
            blockType: Scratch.BlockType.COMMAND,
            text: "サーバーURLを [URL] にする",
            arguments: {
              URL: { type: Scratch.ArgumentType.STRING, defaultValue: "http://localhost:5000" },
            },
          },
          {
            opcode: "setModel",
            blockType: Scratch.BlockType.COMMAND,
            text: "モデルを [MODEL] にする",
            arguments: {
              MODEL: { type: Scratch.ArgumentType.STRING, menu: "modelMenu", defaultValue: "gemini-2.0-flash" },
            },
          },
          "---",
          // 送信
          {
            opcode: "ask",
            blockType: Scratch.BlockType.COMMAND,
            text: "[PROMPT] をGeminiに聞く",
            arguments: {
              PROMPT: { type: Scratch.ArgumentType.STRING, defaultValue: "こんにちは！" },
            },
          },
          "---",
          // レポーター
          {
            opcode:    "getResponse",
            blockType: Scratch.BlockType.REPORTER,
            text:      "Geminiの返答",
          },
          {
            opcode:    "getError",
            blockType: Scratch.BlockType.REPORTER,
            text:      "エラーメッセージ",
          },
          {
            opcode:    "isThinking",
            blockType: Scratch.BlockType.BOOLEAN,
            text:      "返答待ち中か？",
          },
          {
            opcode:    "getDuration",
            blockType: Scratch.BlockType.REPORTER,
            text:      "応答時間 (ms)",
          },
          {
            opcode:    "getModel",
            blockType: Scratch.BlockType.REPORTER,
            text:      "現在のモデル",
          },
          {
            opcode:    "getSession",
            blockType: Scratch.BlockType.REPORTER,
            text:      "セッションID",
          },
        ],
        menus: {
          modelMenu: {
            acceptReporters: false,
            items: MODELS,
          },
        },
      };
    }

    setServer({ URL }) { _serverUrl = String(URL).replace(/\/$/, ""); }
    setModel({ MODEL }) { _model = MODEL; }
    async ask({ PROMPT }) { await askGemini(String(PROMPT)); }
    getResponse()  { return _lastResp; }
    getError()     { return _lastError; }
    isThinking()   { return _isThinking; }
    getDuration()  { return _durationMs; }
    getModel()     { return _model; }
    getSession()   { return _sessionId; }
  }

  Scratch.extensions.register(new GeminiExtension());
})(Scratch);
