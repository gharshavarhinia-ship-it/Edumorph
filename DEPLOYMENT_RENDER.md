# Render Deployment Guide

This application uses a **microservice architecture** with separate Model Server and Flask Backend.

## Architecture

```
Render (Model Server) port 5001
        ↑ HTTP requests
Render (Flask Backend) port 10000
```

Both services run on Render. Model stays local to the model server.

---

## Deployment Steps

### 1. Create Two Render Services

**A) Model Server Service**

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repo
4. Configure:
   - **Name:** `animation-model-server`
   - **Runtime:** Python 3.11
   - **Build Command:** `pip install -r requirements_model_server.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:${PORT} model_server:app`
   - **Plan:** Standard (or Standard Plus if GPU available)
   - **Environment Variables:**
     ```
     MODEL_SERVER_PORT=10000
     ```

5. Advanced Settings:
   - **Disk:** Add persistent disk (20GB+ for model file)
   - **Mount Path:** `/model_data`

6. Deploy

**B) Flask Backend Service**

1. Click "New +" → "Web Service" again
2. Connect same GitHub repo
3. Configure:
   - **Name:** `animation-flask-backend`
   - **Runtime:** Python 3.11
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:${PORT} app:app`
   - **Plan:** Standard
   - **Environment Variables:**
     ```
     MODEL_SERVER_URL=https://animation-model-server.onrender.com
     PORT=10000
     GEMINI_API_KEY=your_key
     SUPABASE_URL=your_url
     SUPABASE_KEY=your_key
     ```

4. Deploy

---

## 2. Update Model Path for Render

Edit **`model_server.py`** line ~47:

```python
# For Render deployment
if os.environ.get('RENDER'):
    model_path = "/model_data/realisticVisionV60B1_v51HyperVAE.safetensors"
else:
    model_path = os.path.join(BASE, "models", "stable-diffusion", "realisticVisionV60B1_v51HyperVAE.safetensors")
```

---

## 3. Upload Model File

Model file **must be placed** on the Model Server persistent disk:

**Option A: During first deployment**
1. Use Render Shell to upload via SFTP
2. Or include in repo (if < 100MB, split if needed)

**Option B: Download on startup**
Add to `model_server.py` startup to download from Hugging Face if not exists.

---

## 4. Environment Variables

**Model Server (.env on Render):**
```
MODEL_SERVER_PORT=10000
RENDER=true
```

**Flask Backend (.env on Render):**
```
MODEL_SERVER_URL=https://animation-model-server.onrender.com
GEMINI_API_KEY=sk-...
SUPABASE_URL=https://...
SUPABASE_KEY=...
PORT=10000
```

---

## 5. Deploy with Git

```bash
# Push to your repo
git add .
git commit -m "Deploy to Render"
git push origin main

# Render auto-deploys
# Model Server: https://animation-model-server.onrender.com
# Flask Backend: https://animation-flask-backend.onrender.com
```

---

## After Deployment

1. Check both services are running:
   ```
   https://animation-model-server.onrender.com/health
   https://animation-flask-backend.onrender.com/
   ```

2. Test image generation:
   - Upload image at Flask backend URL
   - Should call model server via HTTPS

---

## Troubleshooting

### Model Server Times Out
- Increase timeout in Render settings
- Check model file is on persistent disk
- Monitor logs in Render dashboard

### Model Server Can't Reach Backend
- Check `MODEL_SERVER_URL` in Flask .env
- Must use HTTPS (Render auto-provides)
- No localhost URLs - use full domain

### Memory Issues
- Model file is 5GB+ - need sufficient disk
- First request will be slow (model loading)

---

## Local Development (Before Pushing)

```powershell
# Terminal 1
python -m venv venv_model
.\venv_model\Scripts\Activate.ps1
pip install -r requirements_model_server.txt
python model_server.py

# Terminal 2
python -m venv venv_backend
.\venv_backend\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py

# Browser: http://localhost:10000
```

---

## File Structure for Render

```
repo/
├── model_server.py          [Model Server]
├── app.py                   [Flask Backend]
├── engine.py                [Business Logic]
├── requirements.txt         [Backend]
├── requirements_model_server.txt [Model Server]
├── .env.example             [Config template]
├── DEPLOYMENT_RENDER.md     [This file]
├── models/
│   └── stable-diffusion/
│       └── realisticVisionV60B1_v51HyperVAE.safetensors  [MODEL FILE]
├── templates/               [HTML files]
└── static/                  [CSS, JS, uploads, output]
```

---

## Cost Estimate

- **Model Server:** $12/month (Standard) or $29/month (Standard Plus with GPU)
- **Flask Backend:** $12/month (Standard)
- **Persistent Disk:** ~$5/month for 20GB
- **Total:** ~$29-46/month

---

## Quick Reference

### Service URLs (After Deployment)
```
Model Server:  https://animation-model-server.onrender.com
Flask Backend: https://animation-flask-backend.onrender.com
```

### Commands
```bash
# View logs
tail -f ~/output.log  # In Render Shell

# Check services
curl https://animation-model-server.onrender.com/health
curl https://animation-flask-backend.onrender.com/

# Redeploy
# Push to GitHub, Render auto-deploys
```

---

Done! Push this repo to GitHub and Render will auto-deploy. 🚀
