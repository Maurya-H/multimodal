document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const promptInput = document.getElementById("prompt-input");
  const sendBtn = document.getElementById("send-btn");
  const messagesList = document.getElementById("messages-list");
  const emptyState = document.getElementById("empty-state");
  const loadingIndicator = document.getElementById("loading-indicator");
  const errorBanner = document.getElementById("error-banner");
  const errorTitle = document.getElementById("error-title");
  const errorMessage = document.getElementById("error-message");
  const errorCloseBtn = document.getElementById("error-close-btn");
  const messagesContainer = document.getElementById("messages-container");

  // Image attachment elements
  const attachImageBtn = document.getElementById("attach-image-btn");
  const imageInput = document.getElementById("image-input");
  const imagePreviewContainer = document.getElementById("image-preview-container");
  const imagePreviewThumb = document.getElementById("image-preview-thumb");
  const imagePreviewName = document.getElementById("image-preview-name");
  const removeImageBtn = document.getElementById("remove-image-btn");

  // Audio attachment elements
  const attachAudioBtn = document.getElementById("attach-audio-btn");
  const audioInput = document.getElementById("audio-input");
  const audioPreviewContainer = document.getElementById("audio-preview-container");
  const audioPreviewName = document.getElementById("audio-preview-name");
  const removeAudioBtn = document.getElementById("remove-audio-btn");

  let selectedImageFile = null;
  let imagePreviewUrl = null;

  let selectedAudioFile = null;
  let audioPreviewUrl = null;

  const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5 MB
  const MAX_AUDIO_SIZE = 8 * 1024 * 1024; // 8 MB

  const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
  const ALLOWED_AUDIO_EXTENSIONS = [".mp3", ".wav", ".m4a", ".ogg"];

  // Dismiss error banner
  errorCloseBtn.addEventListener("click", () => {
    errorBanner.hidden = true;
  });

  // Auto-resize textarea as user types
  promptInput.addEventListener("input", () => {
    promptInput.style.height = "auto";
    promptInput.style.height = Math.min(promptInput.scrollHeight, 150) + "px";
  });

  // Submit on Enter (Shift+Enter for newline)
  promptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  function showError(title, message) {
    errorTitle.textContent = title;
    errorMessage.textContent = message;
    errorBanner.hidden = false;
  }

  function hideError() {
    errorBanner.hidden = true;
  }

  // --- Image attachment interactions ---
  attachImageBtn.addEventListener("click", () => {
    imageInput.click();
  });

  imageInput.addEventListener("change", () => {
    hideError();
    const file = imageInput.files[0];
    if (!file) return;

    if (file.size > MAX_IMAGE_SIZE) {
      showError("Validation Error", `Image exceeds the 5 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
      imageInput.value = "";
      return;
    }

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      showError("Validation Error", "Unsupported image format. Please select a JPG, PNG, or WebP image.");
      imageInput.value = "";
      return;
    }

    selectedImageFile = file;
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
    }
    imagePreviewUrl = URL.createObjectURL(file);
    imagePreviewThumb.src = imagePreviewUrl;
    imagePreviewName.textContent = file.name;
    imagePreviewContainer.hidden = false;
  });

  function clearImageSelection() {
    selectedImageFile = null;
    imageInput.value = "";
    imagePreviewContainer.hidden = true;
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
      imagePreviewUrl = null;
    }
  }

  removeImageBtn.addEventListener("click", () => {
    clearImageSelection();
  });

  // --- Audio attachment interactions ---
  attachAudioBtn.addEventListener("click", () => {
    audioInput.click();
  });

  audioInput.addEventListener("change", () => {
    hideError();
    const file = audioInput.files[0];
    if (!file) return;

    if (file.size > MAX_AUDIO_SIZE) {
      showError("Validation Error", `Audio exceeds the 8 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
      audioInput.value = "";
      return;
    }

    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_AUDIO_EXTENSIONS.includes(ext) && !file.type.startsWith("audio/")) {
      showError("Validation Error", "Unsupported audio format. Please select an MP3, WAV, M4A, or OGG file.");
      audioInput.value = "";
      return;
    }

    selectedAudioFile = file;
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl);
    }
    audioPreviewUrl = URL.createObjectURL(file);
    audioPreviewName.textContent = file.name;
    audioPreviewContainer.hidden = false;
  });

  function clearAudioSelection() {
    selectedAudioFile = null;
    audioInput.value = "";
    audioPreviewContainer.hidden = true;
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl);
      audioPreviewUrl = null;
    }
  }

  removeAudioBtn.addEventListener("click", () => {
    clearAudioSelection();
  });

  function appendMessage(role, text, imageSrc = null, audioSrc = null) {
    // Hide empty state once the first message is sent
    if (emptyState) {
      emptyState.style.display = "none";
    }

    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    // If an image was attached, render thumbnail safely
    if (imageSrc) {
      const img = document.createElement("img");
      img.className = "message-image";
      img.src = imageSrc;
      img.alt = "Attached image";
      bubble.appendChild(img);
    }

    // If an audio file was attached, render playable audio element
    if (audioSrc) {
      const audio = document.createElement("audio");
      audio.className = "message-audio";
      audio.controls = true;
      audio.src = audioSrc;
      bubble.appendChild(audio);
    }

    // XSS defense: safely inject text via textContent
    if (text) {
      const textDiv = document.createElement("div");
      textDiv.textContent = text;
      bubble.appendChild(textDiv);
    }

    row.appendChild(bubble);
    messagesList.appendChild(row);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function setLoading(isLoading) {
    if (isLoading) {
      loadingIndicator.hidden = false;
      sendBtn.disabled = true;
      promptInput.disabled = true;
      attachImageBtn.disabled = true;
      attachAudioBtn.disabled = true;
      removeImageBtn.disabled = true;
      removeAudioBtn.disabled = true;
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    } else {
      loadingIndicator.hidden = true;
      sendBtn.disabled = false;
      promptInput.disabled = false;
      attachImageBtn.disabled = false;
      attachAudioBtn.disabled = false;
      removeImageBtn.disabled = false;
      removeAudioBtn.disabled = false;
      promptInput.focus();
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    const promptText = promptInput.value.trim();
    if (!promptText && !selectedImageFile && !selectedAudioFile) {
      showError("Validation Error", "Please enter a message or attach a file.");
      return;
    }

    // Prepare multipart form data
    const formData = new FormData();
    if (promptText) {
      formData.append("prompt", promptText);
    }
    if (selectedImageFile) {
      formData.append("image", selectedImageFile);
    }
    if (selectedAudioFile) {
      formData.append("audio", selectedAudioFile);
    }

    // Snapshot preview URLs for chat bubbles
    const currentImagePreview = imagePreviewUrl;
    const currentAudioPreview = audioPreviewUrl;

    // Enter loading state
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        body: formData
      });

      const data = await response.json().catch(() => ({
        error: "Response Error",
        message: "Failed to parse server response."
      }));

      if (!response.ok) {
        // On failure: show error, KEEP user prompt and selected files intact for retry
        showError(data.error || "Request Failed", data.message || `Server returned status ${response.status}`);
      } else {
        // On success: render user message with media preview(s), then clear inputs
        appendMessage("user", promptText, currentImagePreview, currentAudioPreview);
        appendMessage("bot", data.reply || "No response received.");

        // Clear inputs and attachments
        promptInput.value = "";
        promptInput.style.height = "auto";
        clearImageSelection();
        clearAudioSelection();
      }
    } catch (err) {
      // Network drop: preserve inputs for retry
      showError("Network Error", "Unable to connect to the server. Please check your connection and retry.");
    } finally {
      setLoading(false);
    }
  });
});



