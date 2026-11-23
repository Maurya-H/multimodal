# Multimodal Chatbot - Architecture and Implementation Plan

## 1. Overview & MVP Scope
This document specifies the minimal, beginner-readable architecture for a small multimodal chatbot built for a student lab.

### In Scope (MVP)
- **Browser-Based Chat Interface**: Built using semantic HTML5, clean modern CSS3, and Vanilla JavaScript (ES6+). No build tools, bundlers, or frontend frameworks.
- **Multimodal Message Submission**:
  - Text message prompts via input textarea.
  - Optional image attachment (JPEG, PNG, WebP up to 5 MB).
  - Optional audio attachment (MP3, WAV, M4A, OGG up to 8 MB).
- **Backend API Endpoint**: Single Flask endpoint (`POST /api/chat`) accepting `multipart/form-data`.
- **Multimodal AI Provider**: Google Gemini API via official SDK using `gemini-3.8-flash` by default.
- **Configurable Provider Settings**:
  - `GEMINI_API_KEY`: Kept strictly server-side in `.env`.
  - `GEMINI_MODEL`: Configurable via `.env`, defaulting to `gemini-3.8-flash`.
- **Multi-Tier Validation**:
  - Client-side pre-validation for instant feedback.
  - Server-side extension check, MIME type whitelist, pure Python binary signature (magic byte) verification, 0-byte check, and strict size limits.
  - Request size ceiling: 10 MB total.
- **Error Handling & Resilience**:
  - Custom Flask error handlers returning structured JSON for all error statuses (400, 413, 415, 429, 500, 502, 504).
  - Missing server API key treated as a `500 Server Configuration Error`.
  - Upstream provider authentication and permission issues mapped to `502 Bad Gateway` without assuming a 401 code.
  - Zero leakage of secrets, API keys, or raw stack traces to the client.
- **Timeout Management**: Client configured with `types.HttpOptions(timeout=30_000)` (30,000 milliseconds / 30 seconds).
- **Safe Rendering**: AI responses rendered using DOM text nodes or entity-escaped text to prevent Cross-Site Scripting (XSS).
- **Input Preservation on Failure**: In-flight failure preserves prompt text and attached files in the form fields for retry.
- **Privacy Notice**: Visible UI notice informing users that data is sent to Google's Gemini API.

### Explicitly Out of Scope (Future Phases)
- Retrieval-Augmented Generation (RAG) or external document indexing.
- Generated image or audio output from the model (text responses only).
- Persistent conversation history, server-side database storage, or multi-turn conversational memory.
- Dedicated emotional-support system, sentiment tracking, or conversational guardrails outside standard model safety settings.
- User authentication, accounts, or multi-tenant session isolation.

---

## 2. Technology Stack & Dependencies

### Frontend
- **HTML5**: Semantic layout with chat container, message feed, attachment preview chips, and privacy banner.
- **CSS3**: Modern, responsive styling with clean transitions for empty, loading, success, and error states.
- **Vanilla JavaScript (ES6+)**: `fetch` API for `multipart/form-data`, DOM event handlers, dynamic file preview chips, and safe text-node rendering. Zero build tools or bundlers.

### Backend
- **Python 3.12+**
- **Flask (>=3.0.0)**: Lightweight WSGI micro-framework for serving the web client and routing `/api/chat`.
- **python-dotenv (>=1.0.0)**: Loads environment variables from `.env`.
- **google-genai==3.6.1**: Pinned official Google GenAI SDK.

### requirements.txt Specification
```text
flask>=3.0.0
python-dotenv>=1.0.0
google-genai==3.6.1
```

---

## 3. High-Level Architecture Diagram

```
+-------------------------------------------------------------+
| Browser Client (Vanilla HTML / CSS / JS)                    |
| - Text prompt input                                         |
| - File attachment selectors (Image <= 5MB, Audio <= 8MB)    |
| - Client-side validation & preview chips                    |
| - Privacy notice display                                    |
| - Safe text rendering (XSS defense)                         |
+-------------------------------------------------------------+
                           |
                           | POST /api/chat
                           | Content-Type: multipart/form-data
                           v
+-------------------------------------------------------------+
| Flask Application Server (app.py)                           |
|                                                             |
| 1. Request Ceiling: MAX_CONTENT_LENGTH = 10 MB              |
| 2. Input Validation:                                        |
|    - Non-empty prompt or attachment                         |
|    - 0-byte file check                                      |
|    - Extension & MIME whitelist                             |
|    - Binary file signature (magic byte) verification        |
|    - Individual size limits (5MB image / 8MB audio)         |
| 3. Environment Check:                                       |
|    - GEMINI_API_KEY present (500 Config Error if missing)   |
|    - GEMINI_MODEL (defaults to "gemini-3.8-flash")          |
| 4. Upstream Integration:                                    |
|    - client = genai.Client(                                 |
|        api_key=...,                                         |
|        http_options=types.HttpOptions(timeout=30_000)       |
|      )                                                      |
|    - Packaging contents with types.Part.from_bytes(...)     |
| 5. Exception & Error Mapping:                               |
|    - Upstream auth/permission errors -> 502                 |
|    - Upstream rate limits -> 429                            |
|    - Upstream timeouts -> 504                               |
|    - No secrets or stack traces leaked                      |
+-------------------------------------------------------------+
                           |
                           | HTTPS
                           v
+-------------------------------------------------------------+
| Google Gemini API (gemini-3.8-flash)                        |
| - Multimodal processing                                     |
| - Text generation                                           |
+-------------------------------------------------------------+
```

---

## 4. Detailed Component Specifications

### 4.1 Upstream Timeout Configuration
In `google-genai==3.6.1`, the `timeout` field in `types.HttpOptions` is an integer specifying the timeout in **milliseconds**:
- 30 seconds = `30_000` ms.
- Client instantiation:
  ```python
  from google import genai
  from google.genai import types

  client = genai.Client(
      api_key=os.getenv("GEMINI_API_KEY"),
      http_options=types.HttpOptions(timeout=30_000)
  )
  ```

### 4.2 Multi-Tier File Validation
1. **Extension Check**:
   - Images: `.jpg`, `.jpeg`, `.png`, `.webp`
   - Audio: `.mp3`, `.wav`, `.m4a`, `.ogg`
2. **MIME Type Whitelist**:
   - Images: `image/jpeg`, `image/png`, `image/webp`
   - Audio: `audio/mpeg`, `audio/wav`, `audio/mp4`, `audio/x-m4a`, `audio/ogg`
3. **Magic Byte Signature Check**:
   - Pure Python header inspection to verify actual binary structure against declared types:
     - JPEG: `b'\xff\xd8\xff'`
     - PNG: `b'\x89PNG\r\n\x1a\n'`
     - WebP: `b'RIFF'....b'WEBP'`
     - WAV: `b'RIFF'....b'WAVE'`
     - MP3: `b'ID3'` or sync header `0xFFE0` mask
     - OGG: `b'OggS'`
     - M4A: `b'ftyp'` at offset 4
4. **Size Bounds**:
   - `len(data) > 0`
   - Image file $\le$ 5 MB (`5 * 1024 * 1024` bytes)
   - Audio file $\le$ 8 MB (`8 * 1024 * 1024` bytes)
   - Total request body $\le$ 10 MB (`10 * 1024 * 1024` bytes)

### 4.3 Error Handling & Custom JSON Error Handlers
All errors return consistent JSON:
```json
{
  "error": "Error Title",
  "message": "Human-readable explanation."
}
```
Custom Flask error handlers are registered for `400`, `413`, `415`, and `500` to prevent default HTML error responses.

### 4.4 Client-Side Resilience & XSS Prevention
- **In-flight**: Form inputs disabled, "Thinking..." indicator displayed.
- **On Failure**: Form inputs re-enabled immediately; prompt and attached files remain untouched in the form inputs so the user can retry without re-entering data.
- **XSS Defense**: Responses are rendered using DOM text nodes (`textContent = reply`) or escaped string insertion. No unsanitized strings are ever placed into `innerHTML`.
- **Ephemeral State**: Chat history is held only in the browser DOM. No persistence layer exists on the server.

---

## 5. File Tree Structure

```
multimodal/
├── docs/
│   └── plan.md             # Architecture, scope, decisions & implementation plan
├── SPEC.md                 # Complete functional & non-functional requirements and test cases
├── .env.example            # Environment configuration template
├── .gitignore              # Git exclusions (venv, .env, __pycache__)
├── requirements.txt        # Pinned dependencies (flask, python-dotenv, google-genai==3.6.1)
├── app.py                  # Flask server, routes, validations, error handlers, Gemini API integration
├── templates/
│   └── index.html          # Semantic HTML5 chat interface & privacy notice
└── static/
    ├── style.css           # Responsive styling & UI state transitions
    └── app.js              # Client logic, file preview, validation, XSS-safe DOM rendering
```

---

## 6. Setup & Execution Commands

```powershell
# 1. Create and activate virtual environment
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install pinned dependencies
pip install -r requirements.txt

# 3. Create .env file and set your API key
Copy-Item .env.example .env
# Edit .env and set GEMINI_API_KEY="your-api-key"

# 4. Start the application server
python app.py
# Application accessible at http://127.0.0.1:5000
```

