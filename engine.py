import os
from PIL import Image
import pytesseract
import pyttsx3
import torch
from transformers import CLIPProcessor, CLIPModel
import spacy
import graphviz
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
import glob
from moviepy.editor import ImageSequenceClip
import subprocess
import sys

# =====================
# DEVICE SETUP
# =====================
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Using device: {device}")

# =====================
# TESSERACT SETUP
# =====================
if os.name == "nt":
    default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default):
        pytesseract.pytesseract.tesseract_cmd = default

# =====================
# MODELS
# =====================
nlp = spacy.load("en_core_web_sm")

clip_model = CLIPModel.from_pretrained(
    "openai/clip-vit-base-patch32",
    torch_dtype="auto",
    use_safetensors=True
).to(device)

clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

print("[INFO] CLIP loaded")

# =====================
# GLOBAL MEMORY
# =====================
TEXT = ""
POINTS = []
IMAGE_FEATURES = None

# =====================
# OCR
# =====================
def run_ocr(path):
    global TEXT
    TEXT = pytesseract.image_to_string(Image.open(path))
    return TEXT

# =====================
# NLP (limit to 6–7 points)
# =====================
def run_nlp(text):
    global POINTS
    doc = nlp(text)
    all_points = [s.text.strip() for s in doc.sents]

    max_points = 7
    POINTS = all_points[:max_points]

    os.makedirs("static/output", exist_ok=True)
    with open("static/output/points.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(POINTS))

    print(f"[INFO] Key points found: {len(POINTS)}")  # Confirm number of points
    return POINTS

# =====================
# CLIP
# =====================
def run_clip(path):
    global IMAGE_FEATURES
    img = Image.open(path)
    inputs = clip_processor(images=img, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    IMAGE_FEATURES = clip_model.get_image_features(**inputs)
    return IMAGE_FEATURES

# =====================
# PROMPTS
# =====================
ANIMATE_BASE = "educational anime style, smooth motion, "
COMIC_BASE = "comic panel style, educational "
FLOW_BASE = "professional flowchart "

def build_prompt(mode):
    if mode == "animate":
        return ANIMATE_BASE + " ".join(POINTS)
    if mode == "comic":
        return COMIC_BASE + " ".join(POINTS)
    if mode == "flow":
        return FLOW_BASE + " ".join(POINTS)

# =====================
# MASTER
# =====================
def process_file(path):
    run_nlp(run_ocr(path))
    run_clip(path)

# =====================
# COMIC
# =====================
def run_comic():
    with open("static/output/comic_prompt.txt","w") as f:
        f.write(build_prompt("comic"))

# =====================
# FLOWCHART
# =====================
def run_flowchart():
    dot = graphviz.Digraph()
    for i,p in enumerate(POINTS):
        dot.node(str(i), p)
        if i>0:
            dot.edge(str(i-1), str(i))
    dot.render("static/output/flowchart.gv",format="png")

# =====================
# VIDEO BUILD
# =====================
def build_video():
    imgs = sorted(glob.glob("static/output/scenes/*.png"))
    if not imgs:
        print("[ERROR] No frames")
        return

    # slower video playback (2 sec per frame)
    clip = ImageSequenceClip(imgs, fps=0.5)  # 0.5 FPS = 2 sec per frame

    os.makedirs("static/output/videos", exist_ok=True)
    idx = len(glob.glob("static/output/videos/video_*.mp4"))+1
    path = f"static/output/videos/video_{idx}.mp4"
    clip.write_videofile(path, codec="libx264")
    print("[INFO] Video:", path)

# =====================
# VOICE (SMART POINTS)
# =====================
def generate_voice():
    text = ". ".join(POINTS)
    engine = pyttsx3.init()
    engine.setProperty("rate", 160)
    engine.save_to_file(text,"static/output/voice.wav")
    engine.runAndWait()

# =====================
# ANIMATION (Updated)
# =====================
def run_animation():
    os.makedirs("static/output/scenes", exist_ok=True)

    # clear old frames
    for f in os.listdir("static/output/scenes"):
        os.remove("static/output/scenes/"+f)

    print("[INFO] Running Stable Diffusion animation...")

    # ------------------------
    # call new generator.py
    try:
        subprocess.run([sys.executable, "scripts/generate.py"], check=True)
    except subprocess.CalledProcessError:
        print("[ERROR] Stable Diffusion generation failed")
        return
    # ------------------------

    frames = glob.glob("static/output/scenes/*.png")
    if not frames:
        print("[ERROR] No frames generated")
        return

    print(f"[INFO] Frames generated: {len(frames)}")

    # build slow video and merge voice
    build_video()
    generate_voice()
    merge_audio()

# =====================
# MERGE AUDIO
# =====================
def merge_audio():
    vids = sorted(glob.glob("static/output/videos/video_*.mp4"))
    if not vids:
        return

    video = VideoFileClip(vids[-1])
    audio = AudioFileClip("static/output/voice.wav")

    final = video.set_audio(audio)
    idx = len(glob.glob("static/output/final_*.mp4"))+1
    out = f"static/output/final_{idx}.mp4"

    final.write_videofile(out, codec="libx264", audio_codec="aac")
    print("[INFO] FINAL:", out) 