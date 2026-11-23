# System Specification: Multimodal Chatbot

## 1. Purpose & Scope
This document defines the functional and non-functional requirements, architectural constraints, and manual verification procedures for the Multimodal Chatbot (Lab MVP).

The purpose of this system is to provide students with a clean, beginner-readable reference implementation of a multimodal conversational interface capable of processing text, image, and audio inputs using the Google Gemini API.

---

## 2. Functional Requirements (FR)

### FR-1: Browser Chat Interface
- **FR-1.1**: The system shall serve a responsive, browser-accessible chat interface at `GET /`.
- **FR-1.2**: The interface shall display an **Empty State** when no messages have been sent, providing a clear greeting and guidance on how to submit prompts and attachments.
- **FR-1.3**: The interface shall display a scrollable message list containing user prompt bubbles and model response bubbles.
- **FR-1.4**: The interface shall provide a prominent **Privacy Notice** informing users that submitted text, images, and audio are sent to Google's Gemini API for processing.

### FR-2: Input Submission & Attachment Handling
- **FR-2.1**: The interface shall provide a multiline text input for user prompts, supporting submission via the Send button or Enter key (Shift+Enter for newline).
- **FR-2.2**: The interface shall support selecting a single image file (`.jpg`, `.jpeg`, `.png`, `.webp`).
- **FR-2.3**: The interface shall support selecting a single audio file (`.mp3`, `.wav`, `.m4a`, `.ogg`).
- **FR-2.4**: When a file is selected, the interface shall display an attachment badge/preview showing the filename and a remove button ("x") to detach the file before sending.

### FR-3: Client-Side State Management & Resilience
- **FR-3.1 (Loading State)**: While a request is in flight, the Send button and input controls shall be disabled, and a loading spinner / "Thinking..." indicator shall be displayed.
- **FR-3.2 (Success State)**: Upon a successful response (`HTTP 200`), the user's prompt and attachment badges shall be added to the chat history, the assistant's reply rendered, and the input fields cleared.
- **FR-3.3 (Error State & Retry Preservation)**: Upon request failure (`HTTP 4xx/5xx` or network drop), an error banner shall display the error message. The user's prompt text and selected file attachments **must remain preserved in the inputs**, and input controls shall be re-enabled so the user can retry without re-entering data.
- **FR-3.4 (Ephemeral History)**: Chat messages shall be stored exclusively in the browser DOM/memory. Reloading the page shall cleanly reset the conversation.

### FR-4: Safe Response Rendering (XSS Defense)
- **FR-4.1**: Model responses shall be rendered using safe DOM text injection (`textContent`) or strict entity escaping to prevent any script or arbitrary HTML execution.

### FR-5: Server Endpoint & Upstream Integration
- **FR-5.1**: The server shall expose a single endpoint `POST /api/chat` that accepts `multipart/form-data`.
- **FR-5.2**: The server shall read `GEMINI_API_KEY` from the environment (`.env`). If missing, it shall return `HTTP 500` ("Server Configuration Error") without invoking the provider.
- **FR-5.3**: The model name shall be loaded from `GEMINI_MODEL`, defaulting to `gemini-3.8-flash`.
- **FR-5.4**: The server shall instantiate the Gemini client with a 30-second timeout using `types.HttpOptions(timeout=30_000)`.
- **FR-5.5**: Image and audio files shall be forwarded to the model as inline byte buffers paired with their validated MIME types using `types.Part.from_bytes(data=bytes, mime_type=mime_type)`.

### FR-6: Server-Side Validation & Error Mapping
- **FR-6.1 (Request Type)**: Non-multipart requests shall return `HTTP 400 Bad Request`.
- **FR-6.2 (Missing Inputs)**: If both the prompt (whitespace-trimmed) and all attachments are absent, return `HTTP 400 Bad Request`.
- **FR-6.3 (Empty Files)**: If an attached file contains 0 bytes, return `HTTP 400 Bad Request`.
- **FR-6.4 (Unsupported Types)**: If an attached file extension or MIME type is not on the allowed list, return `HTTP 415 Unsupported Media Type`.
- **FR-6.5 (Magic Byte Validation)**: If the binary header of an attachment does not match its declared type, return `HTTP 415 Unsupported Media Type`.
- **FR-6.6 (Individual File Limits)**: If an image exceeds 5 MB or audio exceeds 8 MB, return `HTTP 413 Payload Too Large`.
- **FR-6.7 (Total Request Limit)**: If the total request exceeds 10 MB, Flask shall return `HTTP 413 Payload Too Large` in JSON format.
- **FR-6.8 (Upstream Error Mapping)**:
  - Authentication / permission errors $\rightarrow$ `HTTP 502 Bad Gateway` ("Upstream authentication failed").
  - Rate limit / quota errors $\rightarrow$ `HTTP 429 Too Many Requests` ("Provider rate limit reached").
  - Upstream timeout $\rightarrow$ `HTTP 504 Gateway Timeout` ("Model provider timed out").
  - Other provider errors $\rightarrow$ `HTTP 502 Bad Gateway` ("Upstream AI provider error").
- **FR-6.9 (Sanitization)**: Under no circumstances shall raw API keys, secrets, or internal stack traces be included in HTTP response payloads.

---

## 3. Non-Functional Requirements (NFR)

### NFR-1: Usability & Readability
- The codebase shall adhere strictly to beginner-readable conventions with zero bundlers or build steps.
- Code files shall contain clear comments explaining each validation stage and SDK call.

### NFR-2: Security
- **NFR-2.1**: The API key must never be transmitted to, or exposed within, the browser client.
- **NFR-2.2**: The `.env` file shall be excluded by `.gitignore` by default.
- **NFR-2.3**: Uploaded media must be processed purely in memory and never written to permanent disk storage.
- **NFR-2.4**: Client-rendered responses must be immune to stored/reflected XSS attacks.

### NFR-3: Performance & Reliability
- **NFR-3.1**: Request timeouts to Google Gemini API must strictly abort at 30,000 ms (30 seconds).
- **NFR-3.2**: All application errors must return standard JSON payloads rather than default HTML error pages.

---

## 4. System Constraints & Out-of-Scope Items

1. **Platform**: Windows, macOS, or Linux running Python 3.12+.
2. **Network**: Outbound HTTPS connectivity to Google Gemini API (`generativelanguage.googleapis.com`).
3. **Out of Scope (Explicit Future Phases)**:
   - RAG (Retrieval-Augmented Generation) and external vector databases.
   - Generated image/audio output from the model (text responses only).
   - Server-side session storage or multi-turn conversational persistence.
   - Dedicated emotional-support system or domain-specific conversational therapy logic.

---

## 5. Manual Verification Test Cases (TC)

| ID | Test Case | Action / Input | Expected Result |
| :--- | :--- | :--- | :--- |
| **TC-01** | Empty State Verification | Open `http://127.0.0.1:5000` in browser. | Welcome greeting, guidance, and privacy notice are displayed; chat list is empty. |
| **TC-02** | Text-Only Prompt | Type "Explain quantum superposition in one sentence." and click Send. | Loading indicator appears; Send button disabled; model replies with text; input clears. |
| **TC-03** | Image Attachment | Attach a valid PNG image (<5MB) and ask "What is in this image?". | Image badge shows filename; model accurately describes image content. |
| **TC-04** | Audio Attachment | Attach a valid MP3 file (<8MB) and ask "Summarize this audio.". | Audio badge shows filename; model transcribes or summarizes audio accurately. |
| **TC-05** | Multimodal Combination | Attach valid PNG + MP3 with a prompt. | Both badges visible; model generates coherent answer addressing both attachments. |
| **TC-06** | Missing Input Validation | Click Send with blank prompt and no attachments. | `400 Bad Request` JSON; UI displays warning; form remains usable. |
| **TC-07** | Empty File Validation | Create a 0-byte file (`empty.png`) and attempt upload. | `400 Bad Request` JSON ("Uploaded file is empty"); inputs preserved for retry. |
| **TC-08** | Disguised File (Magic Byte) | Rename a `.txt` file to `sample.png` and submit. | `415 Unsupported Media Type` JSON ("File signature does not match declared type"); inputs preserved. |
| **TC-09** | Individual File Limit | Upload an image file > 5 MB (e.g., 6 MB). | `413 Payload Too Large` JSON ("Image file exceeds the 5 MB limit"); inputs preserved. |
| **TC-10** | Total Request Limit | Submit total payload > 10 MB. | Flask custom error handler returns `413 Payload Too Large` JSON (not HTML). |
| **TC-11** | Missing Server API Key | Remove `GEMINI_API_KEY` from `.env` and restart server; submit prompt. | `500 Server Configuration Error` JSON ("Gemini API key is not configured on the server"); inputs preserved. |
| **TC-12** | Invalid Upstream Key | Set `GEMINI_API_KEY="invalid_key"` in `.env` and submit prompt. | `502 Bad Gateway` JSON ("Upstream authentication failed"); raw key is never leaked in response. |
| **TC-13** | XSS Defense Test | Ask model: "Repeat back: `<script>alert('xss')</script>`". | Script tags display as visible plain text; no alert box or script executes. |
| **TC-14** | Ephemeral History Test | Submit two messages, then refresh browser. | Chat resets to initial Empty State; no prior messages or server sessions remain. |

