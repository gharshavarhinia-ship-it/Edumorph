"""
Stable Diffusion Model Server
Runs locally on port 5001
Loads model once at startup
Provides HTTP API for image generation
"""

import os
import torch
from flask import Flask, request, jsonify, send_file
from diffusers import StableDiffusionPipeline
from io import BytesIO
from dotenv import load_dotenv
import logging

# ================= CONFIG =================
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ================= MODEL LOADING =================

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"[MODEL] Device: {device}")

BASE = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE, "models", "stable-diffusion", "realisticVisionV60B1_v51HyperVAE.safetensors")

logger.info(f"[MODEL] Loading model from: {model_path}")

try:
    pipe = StableDiffusionPipeline.from_single_file(
        model_path,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32
    ).to(device)
    pipe.enable_attention_slicing()
    logger.info("[MODEL] ✅ Model loaded successfully")
except Exception as e:
    logger.error(f"[MODEL] ❌ Failed to load model: {e}")
    raise

# ================= HEALTH CHECK =================

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "device": device}), 200

# ================= IMAGE GENERATION =================

@app.route("/generate", methods=["POST"])
def generate():
    """
    Generate image from prompt
    
    Request JSON:
    {
        "prompt": "description of image",
        "negative_prompt": "what NOT to include",
        "guidance_scale": 7.5,
        "num_inference_steps": 35
    }
    
    Returns: PNG image bytes
    """
    try:
        data = request.json
        
        if not data or "prompt" not in data:
            return jsonify({"error": "Missing 'prompt' in request"}), 400
        
        prompt = data.get("prompt", "")
        negative_prompt = data.get("negative_prompt", "realistic photo, portrait, face, people, human face, text, logo, watermark, blurry, low quality")
        guidance_scale = data.get("guidance_scale", 7.0)
        num_inference_steps = data.get("num_inference_steps", 35)
        
        if not prompt:
            return jsonify({"error": "Prompt cannot be empty"}), 400
        
        logger.info(f"[GENERATE] Generating image from prompt: {prompt[:100]}...")
        
        # Generate image
        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
        ).images[0]
        
        # Convert to PNG bytes
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        logger.info("[GENERATE] ✅ Image generated successfully")
        
        return send_file(
            img_bytes,
            mimetype="image/png",
            as_attachment=True,
            download_name="generated.png"
        )
    
    except Exception as e:
        logger.error(f"[GENERATE] ❌ Error generating image: {e}")
        return jsonify({"error": str(e)}), 500

# ================= BATCH GENERATION =================

@app.route("/generate-batch", methods=["POST"])
def generate_batch():
    """
    Generate multiple images from multiple prompts
    
    Request JSON:
    {
        "prompts": ["prompt1", "prompt2", ...],
        "negative_prompt": "optional",
        "guidance_scale": 7.0,
        "num_inference_steps": 35
    }
    
    Returns: JSON with list of base64-encoded images
    """
    try:
        data = request.json
        
        if not data or "prompts" not in data:
            return jsonify({"error": "Missing 'prompts' in request"}), 400
        
        prompts = data.get("prompts", [])
        
        if not prompts or not isinstance(prompts, list):
            return jsonify({"error": "'prompts' must be a non-empty list"}), 400
        
        negative_prompt = data.get("negative_prompt", "realistic photo, portrait, face, people, human face, text, logo, watermark, blurry, low quality")
        guidance_scale = data.get("guidance_scale", 7.0)
        num_inference_steps = data.get("num_inference_steps", 35)
        
        logger.info(f"[BATCH] Generating {len(prompts)} images...")
        
        results = []
        
        for i, prompt in enumerate(prompts, 1):
            try:
                logger.info(f"[BATCH] Image {i}/{len(prompts)}: {prompt[:100]}...")
                
                image = pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    guidance_scale=guidance_scale,
                    num_inference_steps=num_inference_steps,
                ).images[0]
                
                # Convert to base64 for JSON response
                import base64
                img_bytes = BytesIO()
                image.save(img_bytes, format="PNG")
                img_bytes.seek(0)
                img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
                
                results.append({
                    "index": i,
                    "prompt": prompt,
                    "image_base64": img_base64,
                    "success": True
                })
            
            except Exception as e:
                logger.error(f"[BATCH] ❌ Failed to generate image {i}: {e}")
                results.append({
                    "index": i,
                    "prompt": prompt,
                    "success": False,
                    "error": str(e)
                })
        
        logger.info(f"[BATCH] ✅ Batch generation complete")
        
        return jsonify({
            "total": len(prompts),
            "successful": sum(1 for r in results if r["success"]),
            "results": results
        }), 200
    
    except Exception as e:
        logger.error(f"[BATCH] ❌ Batch error: {e}")
        return jsonify({"error": str(e)}), 500

# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("MODEL_SERVER_PORT", 5001))
    logger.info(f"[SERVER] Starting Stable Diffusion Model Server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
