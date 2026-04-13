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
  let _history     = []; // Array of {prompt, response}

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
        _lastResp  = "⚠️ エラー: " + _lastError;
      } else {
        _lastResp   = data.response ?? "";
        _lastId     = data.id       ?? "";
        _durationMs = data.duration_ms ?? 0;
        _lastError  = "";
      }
    } catch (e) {
      _lastError = `[Fetch Error] ${e.message}. ブラウザやネットワーク（広告ブロック等）が ${ _serverUrl } への接続を遮断していないか確認してください。`;
      _lastResp  = "⚠️ 接続失敗: " + _lastError;
      console.error("Gemini Fetch Error:", e);
    } finally {
      _isThinking = false;
    }
  }

  async function fetchHistory() {
    _isThinking = true;
    try {
      const res = await fetch(`${_serverUrl}/api/history`);
      const data = await res.json();
      if (data.history) {
        _history = data.history.map(item => ({
          prompt:   item.prompt,
          response: item.response
        }));
      }
    } catch (e) {
      console.error("History fetch failed", e);
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
          {
            opcode:    "fetchHistory",
            blockType: Scratch.BlockType.COMMAND,
            text:      "会話履歴を取得する",
          },
          {
            opcode:    "historySize",
            blockType: Scratch.BlockType.REPORTER,
            text:      "履歴の件数",
          },
          {
            opcode:    "getHistoryPrompt",
            blockType: Scratch.BlockType.REPORTER,
            text:      "履歴 [INDEX] の自分の質問",
            arguments: {
              INDEX: { type: Scratch.ArgumentType.NUMBER, defaultValue: 1 },
            },
          },
          {
            opcode:    "getHistoryResponse",
            blockType: Scratch.BlockType.REPORTER,
            text:      "履歴 [INDEX] のGeminiの回答",
            arguments: {
              INDEX: { type: Scratch.ArgumentType.NUMBER, defaultValue: 1 },
            },
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
    async fetchHistory() { await fetchHistory(); }
    historySize() { return _history.length; }
    getHistoryPrompt({ INDEX }) {
      const idx = Math.floor(INDEX) - 1;
      return _history[idx] ? _history[idx].prompt : "";
    }
    getHistoryResponse({ INDEX }) {
      const idx = Math.floor(INDEX) - 1;
      return _history[idx] ? _history[idx].response : "";
    }
    getResponse()  { return _lastResp; }
    getError()     { return _lastError; }
    isThinking()   { return _isThinking; }
    getDuration()  { return _durationMs; }
    getModel()     { return _model; }
    getSession()   { return _sessionId; }
  }

  Scratch.extensions.register(new GeminiExtension());
})(Scratch);
