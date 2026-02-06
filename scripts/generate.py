import os
import torch
from diffusers import StableDiffusionPipeline
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

# Path to your Stable Diffusion model
model_path = BASE / "models/stable-diffusion/anything-v5.safetensors"

# Load Stable Diffusion pipeline
pipe = StableDiffusionPipeline.from_single_file(model_path, torch_dtype=torch.float32)
pipe = pipe.to("cuda")

# Read points (6–7 max)
with open(BASE / "static/output/points.txt", "r", encoding="utf-8") as f:
    POINTS = [line.strip() for line in f if line.strip()]

# ------------------------
# limit to 4–5 points for slow video
points_to_use = POINTS[:5]
# ------------------------

out = BASE / "static/output/scenes"
out.mkdir(parents=True, exist_ok=True)

print(f"[INFO] Generating Stable Diffusion frames for {len(points_to_use)} points...")

for idx, point in enumerate(points_to_use):
    # ------------------------
    # improved prompt for clarity and quality
    prompt = (
        f"high-quality educational anime illustration, {point}, "
        "sharp, clear, vibrant, detailed, professional style, well-lit, readable text, clean composition"
    )
    # ------------------------
    print(f"[INFO] Generating frame {idx+1}/{len(points_to_use)}: {point}")
    image = pipe(prompt, guidance_scale=9, num_inference_steps=30).images[0]
    image.save(out / f"{idx:03d}.png")

print("[INFO] Stable Diffusion frames saved.")