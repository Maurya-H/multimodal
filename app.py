import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Request ceiling: 10 MB total
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Model name configuration, defaulting to gemini-3.8-flash
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Limits: 5 MB image, 8 MB audio
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_AUDIO_SIZE = 8 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}
ALLOWED_AUDIO_MIMES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/mp4", "audio/x-m4a", "audio/ogg"
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multimodal-chatbot")


def validate_image_signature(data: bytes, mime_type: str) -> bool:
    """Verifies binary magic bytes match the declared image MIME type."""
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    elif mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    elif mime_type == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return False


def validate_audio_signature(data: bytes, mime_type: str) -> bool:
    """Verifies binary magic bytes match the declared audio MIME type."""
    if mime_type in ("audio/wav", "audio/x-wav"):
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    elif mime_type in ("audio/mpeg", "audio/mp3"):
        # ID3 tag or MPEG sync word (11 consecutive 1s)
        return data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    elif mime_type == "audio/ogg":
        return data.startswith(b"OggS")
    elif mime_type in ("audio/mp4", "audio/x-m4a"):
        return len(data) >= 8 and data[4:8] == b"ftyp"
    return False


# Custom error handlers returning JSON instead of HTML
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "error": "Payload Too Large",
        "message": "Total request size exceeds the 10 MB limit."
    }), 413


@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        "error": "Bad Request",
        "message": getattr(error, "description", "Malformed or invalid request.")
    }), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested resource was not found."
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method Not Allowed",
        "message": "The method is not allowed for the requested URL."
    }), 405


@app.errorhandler(415)
def unsupported_media_type(error):
    return jsonify({
        "error": "Unsupported Media Type",
        "message": getattr(error, "description", "Unsupported media type.")
    }), 415


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "error": "Internal Server Error",
        "message": "An internal server error occurred."
    }), 500


@app.route("/")
def index():
    """Serves the single-page chat UI."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handles chat submissions supporting text, image, and audio attachments."""
    # Enforce multipart/form-data
    if not request.content_type or not request.content_type.startswith("multipart/form-data"):
        return jsonify({
            "error": "Bad Request",
            "message": "Request must be multipart/form-data."
        }), 400

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return jsonify({
            "error": "Server Configuration Error",
            "message": "Gemini API key is not configured on the server."
        }), 500

    prompt = request.form.get("prompt", "").strip()
    image_file = request.files.get("image")
    audio_file = request.files.get("audio")

    # Validate that at least a prompt, an image, or an audio attachment is supplied
    has_image = bool(image_file and image_file.filename)
    has_audio = bool(audio_file and audio_file.filename)

    if not prompt and not has_image and not has_audio:
        return jsonify({
            "error": "Bad Request",
            "message": "At least a prompt or an attachment is required."
        }), 400

    contents = []
    if prompt:
        contents.append(prompt)

    # Process and validate image attachment if provided
    if has_image:
        ext = os.path.splitext(image_file.filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({
                "error": "Unsupported Media Type",
                "message": f"Image extension '{ext}' is not supported. Use .jpg, .jpeg, .png, or .webp."
            }), 415

        # Normalize MIME type
        mime = (image_file.mimetype or "").lower()
        if mime not in ALLOWED_IMAGE_MIMES:
            if ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ext == ".png":
                mime = "image/png"
            elif ext == ".webp":
                mime = "image/webp"
            else:
                return jsonify({
                    "error": "Unsupported Media Type",
                    "message": f"MIME type '{image_file.mimetype}' is not supported for images."
                }), 415

        image_bytes = image_file.read()
        if len(image_bytes) == 0:
            return jsonify({
                "error": "Bad Request",
                "message": "Uploaded image file is empty (0 bytes)."
            }), 400

        if len(image_bytes) > MAX_IMAGE_SIZE:
            return jsonify({
                "error": "Payload Too Large",
                "message": f"Image file exceeds the 5 MB limit ({len(image_bytes) / (1024 * 1024):.1f} MB)."
            }), 413

        if not validate_image_signature(image_bytes, mime):
            return jsonify({
                "error": "Unsupported Media Type",
                "message": "Image file signature does not match its declared type."
            }), 415

        # Append inline image part to contents
        contents.append(
            types.Part.from_bytes(data=image_bytes, mime_type=mime)
        )

    # Process and validate audio attachment if provided
    if has_audio:
        ext = os.path.splitext(audio_file.filename)[1].lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return jsonify({
                "error": "Unsupported Media Type",
                "message": f"Audio extension '{ext}' is not supported. Use .mp3, .wav, .m4a, or .ogg."
            }), 415

        # Normalize MIME type
        audio_mime = (audio_file.mimetype or "").lower()
        if audio_mime not in ALLOWED_AUDIO_MIMES:
            if ext == ".mp3":
                audio_mime = "audio/mpeg"
            elif ext == ".wav":
                audio_mime = "audio/wav"
            elif ext == ".ogg":
                audio_mime = "audio/ogg"
            elif ext == ".m4a":
                audio_mime = "audio/mp4"
            else:
                return jsonify({
                    "error": "Unsupported Media Type",
                    "message": f"MIME type '{audio_file.mimetype}' is not supported for audio."
                }), 415

        audio_bytes = audio_file.read()
        if len(audio_bytes) == 0:
            return jsonify({
                "error": "Bad Request",
                "message": "Uploaded audio file is empty (0 bytes)."
            }), 400

        if len(audio_bytes) > MAX_AUDIO_SIZE:
            return jsonify({
                "error": "Payload Too Large",
                "message": f"Audio file exceeds the 8 MB limit ({len(audio_bytes) / (1024 * 1024):.1f} MB)."
            }), 413

        if not validate_audio_signature(audio_bytes, audio_mime):
            return jsonify({
                "error": "Unsupported Media Type",
                "message": "Audio file signature does not match its declared type."
            }), 415

        # Append inline audio part to contents
        contents.append(
            types.Part.from_bytes(data=audio_bytes, mime_type=audio_mime)
        )

    try:
        # Client initialized with verified 30-second timeout (30,000 ms)
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30_000)
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents
        )

        reply_text = response.text or "No response generated."
        return jsonify({"reply": reply_text})

    except errors.APIError as e:
        logger.error("Upstream Gemini API error: %s", str(e))
        err_str = str(e).upper()
        if e.code in (401, 403) or "API_KEY" in err_str or "PERMISSION_DENIED" in err_str:
            return jsonify({
                "error": "Authentication Failed",
                "message": "Upstream authentication failed. Please verify server credentials."
            }), 502
        elif e.code == 429 or "RESOURCE_EXHAUSTED" in err_str:
            return jsonify({
                "error": "Rate Limit Exceeded",
                "message": "Model provider rate limit reached. Please wait a moment and try again."
            }), 429
        elif e.code in (408, 504) or "DEADLINE_EXCEEDED" in err_str:
            return jsonify({
                "error": "Provider Timeout",
                "message": "Model provider request timed out (30s limit). Please retry."
            }), 504
        elif e.code == 503 or "UNAVAILABLE" in err_str or "DEMAND" in err_str:
            return jsonify({
                "error": "Model Temporarily Unavailable (503)",
                "message": "This model is currently experiencing high demand upstream on Google's servers. Please retry in a few moments, or configure GEMINI_MODEL in .env to a model like gemini-3.5-flash."
            }), 503
        else:
            return jsonify({
                "error": "Provider Error",
                "message": "The upstream AI model provider encountered an error."
            }), 502

    except TimeoutError as e:
        logger.error("Request timeout: %s", str(e))
        return jsonify({
            "error": "Provider Timeout",
            "message": "The request to the model provider timed out."
        }), 504

    except Exception as e:
        logger.error("Unexpected error in /api/chat: %s", str(e))
        return jsonify({
            "error": "Internal Error",
            "message": "An unexpected server error occurred."
        }), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)


