# Animation Generator - Microservice Architecture

Convert study materials into animated educational videos with AI-generated visuals.

## Quick Start

### Local Development (2 terminals)

```powershell
# Terminal 1: Model Server
python -m venv venv_model
.\venv_model\Scripts\Activate.ps1
pip install -r requirements_model_server.txt
python model_server.py
# Runs on: http://localhost:5001

# Terminal 2: Flask Backend
python -m venv venv_backend
.\venv_backend\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
# Runs on: http://localhost:10000
```

**Then:** Open browser to `http://localhost:10000`

### Configuration

1. Copy `.env.example` → `.env`
2. Fill in your API keys:
   - `GEMINI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

---

## Architecture

```
Flask Backend (port 10000)
    ↓ HTTP requests
Model Server (port 5001)
    ↓
Stable Diffusion (local)
```

Two separate services:
- **Backend:** Web routes, business logic, video generation
- **Model Server:** Stable Diffusion image generation via HTTP

---

## Deploy to Render

👉 See [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md)

Two services on Render:
1. Model Server (5GB disk required for model)
2. Flask Backend

---

## Files

### Code
- `model_server.py` - Stable Diffusion HTTP service
- `app.py` - Flask backend (port 10000)
- `engine.py` - Business logic (OCR, NLP, video generation)
- `requirements.txt` - Backend dependencies
- `requirements_model_server.txt` - Model server dependencies

### Config
- `.env.example` - Environment template

### Model
- `models/stable-diffusion/` - Model file required

---

## Features

✅ Upload study materials (PDF, images)
✅ Extract text with OCR
✅ Generate educational scripts with Gemini AI
✅ Create animated videos with AI-generated visuals
✅ Generate comic strips
✅ Create flowcharts
✅ Generate quiz questions
✅ Voice synthesis with pyttsx3
✅ Upload to Supabase storage

---

## Troubleshooting

**Model server won't start?**
- Check model file exists: `models/stable-diffusion/realisticVisionV60B1_v51HyperVAE.safetensors`
- Requires 20GB+ disk space

**Backend can't reach model server?**
- Ensure Terminal 1 shows "Running on http://0.0.0.0:5001"
- Check `.env` for `MODEL_SERVER_URL=http://localhost:5001`

**Installation fails?**
- Update pip: `python -m pip install --upgrade pip`
- Create separate virtual environments (don't share)

---

## Tech Stack

- **Backend:** Flask, Supabase, moviepy
- **ML:** Stable Diffusion, Gemini API
- **NLP:** spaCy, pytesseract (OCR)
- **Voice:** pyttsx3
- **Audio/Video:** moviepy, imageio

---

**Ready to deploy? → [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md)** 🚀
