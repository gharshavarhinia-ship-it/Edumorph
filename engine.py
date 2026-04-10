import os
import glob
import json
import random
import requests
import logging
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import numpy as np
import pyttsx3
import textwrap 
import spacy
import google.generativeai as genai
from dotenv import load_dotenv
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, CompositeVideoClip
from io import BytesIO

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise Exception("GEMINI_API_KEY missing")
genai.configure(api_key=GEMINI_KEY)

voice_model = genai.GenerativeModel("gemini-flash-latest")

# ================= MODEL SERVER CONFIG =================
MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:5001")
logger.info(f"[ENGINE] Using model server: {MODEL_SERVER_URL}")

if os.name == "nt":
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

nlp = spacy.load("en_core_web_sm")

POINTS = []

def run_ocr(path):
    return pytesseract.image_to_string(Image.open(path))

def run_nlp(text):
    global POINTS
    doc = nlp(text)
    POINTS = [s.text.strip() for s in doc.sents][:10]
 
    os.makedirs("static/output", exist_ok=True)
    with open("static/output/points.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(POINTS))

def process_file(path):
    run_nlp(run_ocr(path))

def summarize_points():
    joined = ". ".join(POINTS)
    prompt = f"""
You are a friendly teacher who explains topics through a short animated story.
Explain the concept in simple spoken English in about one minute.
Instead of a lecture, make it feel like an adventure where characters such as Hans, Flora,
and a curious explorer travel around and discover the idea together. 
Let the characters talk, ask questions, and react to what they see.
Show the concept through small scenes, like walking through a forest, visiting a busy city, or observing nature, 
so the audience learns by exploration. Keep the narration lively and natural, avoid repeating sentences, 
and make the explanation feel like a fun animated journey that clearly teaches the topic

{joined}
"""
    return voice_model.generate_content(prompt).text

def generate_voice():
    with open("static/output/script.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        script = data["animation"] 

    narration_text = " ".join(scene["narration"] for scene in script)

    engine = pyttsx3.init()
    engine.setProperty("rate", 150)

    os.makedirs("static/output", exist_ok=True)

    output_path = "static/output/voice.wav"

    engine.save_to_file(narration_text, output_path)
    engine.runAndWait()

    print("[INFO] Voice generated:", output_path)
    
from moviepy.editor import AudioFileClip, concatenate_audioclips

from moviepy.editor import concatenate_audioclips, AudioFileClip

def merge_voices(voice_paths):

    clips = [AudioFileClip(v) for v in voice_paths]

    final_audio = concatenate_audioclips(clips)

    final_audio.write_audiofile("static/output/voice.wav")

#  VISUALS
#generate scripts
def generate_script(age_group):
    import json

    # ✅ READ POINTS FROM points.txt (not global POINTS)
    with open("static/output/points.txt", "r", encoding="utf-8") as f:
        points = [l.strip() for l in f if l.strip()]

    joined = ". ".join(points)
    print("[DEBUG] Points used for Gemini:", joined)

    # Determine age-based tone
    if age_group == "6-8":
        age_tone = "Use VERY simple words, short sentences. Make it playful and fun like you're talking to a small child. Use simple concepts and lots of enthusiasm. Narration should be MAXIMUM 8 words per sentence."
    elif age_group == "9-10":
        age_tone = "Use simple but slightly more detailed sentences. Explain clearly with examples. Make it engaging and moderately fun. Narration should be MAXIMUM 12 words per sentence for class 9 to 10."
    elif age_group == "11-12":
        age_tone = "Explain clearly like a teacher in a classroom. You can use slightly advanced vocabulary but keep it understandable. Make the content educational and engaging for students in clas 11 and 12 "
    else:
        age_tone = "Explain clearly like a teacher in a classroom. You can use slightly advanced vocabulary but keep it understandable. Make the content educational and engaging for college students so make it more clear and use know technology terms as teaching for a college students"

    # --- Original animation prompt with age tone ---
    prompt = f"""
You are an educational animation script writer.

{age_tone}

Convert the following study material into a short animated script.

Rules:
- Divide into 5 scenes
- Each scene about 12 seconds
- Total video duration about 1 minute
- Give narration and visual prompt
- Return ONLY valid JSON

Format:
[
 {{
   "scene": 1,
   "narration": "text",
   "visual": "image description"
 }}
]

Study Material:
{joined}
"""

    # Generate animation script
    response = voice_model.generate_content(prompt)
    text = response.text.strip()

    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == -1:
            raise ValueError("Could not find JSON brackets in Gemini response")
        animation_script = json.loads(text[start:end])
    except Exception as e:
        print("[ERROR] Failed to parse animation JSON:", e)
        print("[DEBUG] Gemini raw response:", text)
        return []  # Stop here so old script.json is not used

    # --- Comic prompt ---
    comic_prompt = f"""
You are a professional comic writer.

{age_tone}

Based on the following animation content, create a **12-panel comic script**.
- Each panel should have 1-2 short, punchy sentences.
- Make the story continuous and engaging for children.
- Include a 'visual' description for each panel (what the comic image should show).
- Return ONLY valid JSON in this format:

[
 {{
   "scene": 1,
   "narration": "text",
   "visual": "image description"
 }}
]

Animation content:
{joined}
"""

    # --- Save combined JSON safely ---
    data = {"animation": animation_script}

    try:
        comic_response = voice_model.generate_content(comic_prompt)
        comic_text = comic_response.text.strip()
        start = comic_text.find("[")
        end = comic_text.rfind("]") + 1
        comic_script = json.loads(comic_text[start:end])
        data["comic"] = comic_script
    except Exception as e:
        print("[ERROR] Failed to parse comic JSON:", e)
        print("[DEBUG] Gemini raw comic response:", comic_text)
        data["comic"] = []  # fallback empty array

    os.makedirs("static/output", exist_ok=True)
    with open("static/output/script.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # --- DEBUG: check animation output ---
    print("[DEBUG] Animation scenes to save:", len(animation_script))
    for i, scene in enumerate(animation_script):
        print(f"Scene {i+1}: {scene.get('narration','')[:50]}...")

    # Save captions for animation voice
    captions = " ".join(scene["narration"] for scene in animation_script)
    with open("static/output/caption.txt", "w", encoding="utf-8") as f:
        f.write(captions)

    print("[INFO] script.json saved with animation and comic")
    return animation_script
def generate_visual_prompts(max_images=5):
    prompts = []

    # Read the generated script
    script_path = "static/output/script.json"

    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            script = data["animation"]

        for scene in script[:max_images]:
            prompts.append(scene["visual"])
        return prompts

    # Fallback if script not generated yet
    for point in POINTS[:max_images]:
        prompts.append(point)

    return prompts

def generate_images():
    """
    Generate images using the local model server
    Calls HTTP endpoint at MODEL_SERVER_URL/generate
    """
    logger.info("[GENERATE_IMAGES] Starting image generation via model server...")
    os.makedirs("static/output/scenes", exist_ok=True)

    # Clear old images
    for f in os.listdir("static/output/scenes"):
        os.remove(os.path.join("static/output/scenes", f))

    prompts = generate_visual_prompts()
    negative = "realistic photo, portrait, face, people, human face, text, logo, watermark, blurry, low quality"

    for i, scene in enumerate(prompts[:5]):
        prompt = f"""
colorful storybook illustration of {scene},
soft cartoon style characters,
educational animation look,
friendly environment,
rounded shapes,
clean outlines,
simple expressive characters,
bright colors,
high detail,
children story illustration,
no text,
masterpiece
"""

        try:
            logger.info(f"[GENERATE_IMAGES] Generating image {i} from model server...")
            
            # Call the model server
            response = requests.post(
                f"{MODEL_SERVER_URL}/generate",
                json={
                    "prompt": prompt,
                    "negative_prompt": negative,
                    "guidance_scale": 7,
                    "num_inference_steps": 35
                },
                timeout=300  # 5 minute timeout for image generation
            )
            
            if response.status_code == 200:
                # Save the image
                image_data = response.content
                with open(f"static/output/scenes/{i:03d}.png", "wb") as f:
                    f.write(image_data)
                logger.info(f"[GENERATE_IMAGES] ✅ Image saved: {i:03d}.png")
            else:
                logger.error(f"[GENERATE_IMAGES] ❌ Model server error: {response.status_code} - {response.text}")
                raise Exception(f"Model server error: {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            logger.error(f"[GENERATE_IMAGES] ❌ Cannot connect to model server at {MODEL_SERVER_URL}")
            raise Exception(f"Cannot reach model server at {MODEL_SERVER_URL}. Is model_server.py running?")
        except Exception as e:
            logger.error(f"[GENERATE_IMAGES] ❌ Error generating image {i}: {e}")
            raise

# ---------------- VIDEO ----------------
# ---------------- VIDEO ----------------
transitions = ["fade","slide_left","slide_right","zoom","flip","split"]
random.shuffle(transitions)
transition_index = 0
def apply_transition(clip):

    global transition_index

    t = transitions[transition_index % len(transitions)]
    transition_index += 1

    if t == "fade":
        clip = clip.fadein(0.5).fadeout(0.5)

    elif t == "slide_left":
        clip = clip.set_position(lambda x: (-200*x, 'center'))

    elif t == "slide_right":
        clip = clip.set_position(lambda x: (200*x, 'center'))

    elif t == "zoom":
        clip = clip.resize(lambda x: 1 + 0.1*x)

    elif t == "flip":
        clip = clip.rotate(lambda x: 10*x)

    elif t == "split":
        clip = clip.fadein(0.3)

    return clip
def build_video(output_path):
    
    global transition_index
    random.shuffle(transitions)
    transition_index = 0
    image_files = sorted(glob.glob("static/output/scenes/*.png"))

    if not image_files:
        raise Exception("No images found in static/output/scenes")

    audio_path = "static/output/voice.wav"

    if not os.path.exists(audio_path):
        raise Exception("Voice file not found")

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # 5 images → each about 12 seconds for 1 minute video
    per = duration / len(image_files)

    clips = []
    for img in image_files:
        clip = ImageClip(img).set_duration(per)

        clip = apply_transition(clip)

        clips.append(clip)

    video = concatenate_videoclips(clips).set_audio(audio)

    # -------- CAPTIONS --------

    caption_path = "static/output/caption.txt"

    caption_clips = []

    if os.path.exists(caption_path):

        with open(caption_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = textwrap.wrap(text, 120)

        W, H = video.size

        segment = duration / max(len(chunks), 1)

        for i, chunk in enumerate(chunks):

            wrapped = "\n".join(textwrap.wrap(chunk, 45))

            box = Image.new("RGBA", (W,160), (0,0,0,180))
            draw = ImageDraw.Draw(box)
            font = ImageFont.load_default()

            draw.multiline_text(
                (20,20),
                wrapped,
                font=font,
                fill="white"
            )

            clip = (
                ImageClip(np.array(box))
                .set_duration(segment)
                .set_start(i * segment)
                .set_position(("center","bottom"))
            )

            caption_clips.append(clip)

    final = CompositeVideoClip(
        [video.set_position("center")] + caption_clips
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )

    print("[INFO] Final video saved:", output_path)
# New
def run_animation(output_path, uploaded_file_path, age_group="11+"):
    # 1️⃣ Process the uploaded file (OCR → NLP)
    process_file(uploaded_file_path)  # This updates POINTS and points.txt

    # 2️⃣ Generate scripts based on new POINTS and age_group
    generate_script(age_group)      # Updates script.json
    generate_voice()       # Generates voice.wav
    generate_images()      # Generates new visuals
    build_video(output_path)  # Builds final video
# ---------------- COMIC ----------------

# ---------------- COMIC ----------------
def generate_comic_script():
    import json

    # Read points.txt (latest study material)
    with open("static/output/points.txt", "r", encoding="utf-8") as f:
        points = [l.strip() for l in f if l.strip()]

    joined = ". ".join(points)
    print("[DEBUG] Points used for comic Gemini:", joined)

    comic_prompt = f"""
You are a professional comic writer.

Based on the following study material, create a **12-panel comic script**.
- Each panel should have 1-2 short, punchy sentences.
- Make the story continuous and engaging for children.
- Include a 'visual' description for each panel (what the comic image should show).
- Return ONLY valid JSON in this format:

[
 {{
   "scene": 1,
   "narration": "text",
   "visual": "image description"
 }}
]

Study Material:
{joined}
"""

    try:
        response = voice_model.generate_content(comic_prompt)
        text = response.text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        comic_script = json.loads(text[start:end])
    except Exception as e:
        print("[ERROR] Failed to parse comic JSON:", e)
        print("[DEBUG] Gemini raw comic response:", text)
        comic_script = []

    # Save/update in script.json
    script_path = "static/output/script.json"
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    data["comic"] = comic_script

    os.makedirs("static/output", exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("[INFO] Comic JSON saved with latest points.txt")
    return comic_script
def run_comic():
    """Generate comic by calling the model server via HTTP"""
    logger.info("[RUN_COMIC] Starting comic generation...")
    os.makedirs("static/comic", exist_ok=True)

    # 1️⃣ Generate comic JSON from latest points.txt
    comic_script = generate_comic_script()

    if not comic_script:
        logger.error("[RUN_COMIC] No comic script to generate images.")
        raise Exception("No comic script generated")

    comic_paths = []
    negative_prompt = "anime, cartoon, illustration, painting, text, logo, watermark, blurry, human face, person, people, portrait, face"

    for idx, scene in enumerate(comic_script):
        narration = scene["narration"]
        visual_prompt = scene["visual"]

        # -------- IMAGE GENERATION VIA MODEL SERVER --------
        sd_prompt = f"""
comic style colourful or blackwhite illustration of {visual_prompt},
storybook style,
soft lighting,
clean outlines,
high detail,
no text,
comic style no realistic images
"""
        try:
            logger.info(f"[RUN_COMIC] Generating comic panel {idx} via model server...")
            
            # Call the model server
            response = requests.post(
                f"{MODEL_SERVER_URL}/generate",
                json={
                    "prompt": sd_prompt,
                    "negative_prompt": negative_prompt,
                    "guidance_scale": 7,
                    "num_inference_steps": 30
                },
                timeout=300  # 5 minute timeout
            )
            
            if response.status_code != 200:
                logger.error(f"[RUN_COMIC] Model server error: {response.status_code} - {response.text}")
                raise Exception(f"Model server error: {response.status_code}")
            
            # Save the image
            img = Image.open(BytesIO(response.content))
            
            # -------- ADD TEXT BOX --------
            draw = ImageDraw.Draw(img)
            W, H = img.size

            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except:
                font = ImageFont.load_default()

            wrapped = "\n".join(textwrap.wrap(narration, 42)[:5])
            box_height = 40 + len(wrapped.split("\n")) * font.getbbox("Ay")[3] + 20

            box = Image.new("RGBA", (W, box_height), (255, 255, 255, 170))
            img.paste(box, (0, H - box_height - 40), box)

            draw.multiline_text(
                (20, H - box_height - 40 + 20),
                wrapped,
                fill="black",
                font=font
            )

            out = f"static/comic/panel_{idx}.png"
            img.save(out)
            comic_paths.append(out)
            logger.info(f"[RUN_COMIC] ✅ Panel {idx} saved")

        except requests.exceptions.ConnectionError:
            logger.error(f"[RUN_COMIC] Cannot connect to model server at {MODEL_SERVER_URL}")
            raise Exception(f"Cannot reach model server at {MODEL_SERVER_URL}. Is model_server.py running?")
        except Exception as e:
            logger.error(f"[RUN_COMIC] Error generating panel {idx}: {e}")
            raise

    # -------- COMBINE PANELS INTO COLLAGE --------
    logger.info("[RUN_COMIC] Creating comic collage...")
    imgs = [Image.open(p) for p in comic_paths]
    w, h = imgs[0].size
    cols = 3
    rows = int(np.ceil(len(imgs)/cols))

    canvas = Image.new("RGB", (w*cols, h*rows), "white")
    for i, im in enumerate(imgs):
        x = (i % cols) * w
        y = (i // cols) * h
        canvas.paste(im, (x, y))

    final_path = f"static/comic/comic_final.png"
    canvas.save(final_path)

    logger.info(f"[RUN_COMIC] ✅ Comic collage saved: {final_path}")
    return final_path

# ---------------- FLOWCHART ----------------
def extract_flow_points(points):

    structure = {
        "main": "",
        "branches": {}
    }

    if not points:
        return structure

    # first sentence = main topic
    structure["main"] = points[0]

    stop_words = {
        "the","a","an","this","that","these","those",
        "is","are","was","were","called","present"
    }

    for sentence in points[1:]:

        # remove watermark / junk
        if "shutter" in sentence.lower():
            continue

        doc = nlp(sentence)

        words = []

        for token in doc:

            # keep nouns, verbs, adjectives
            if token.pos_ in ["NOUN","VERB","ADJ"]:

                w = token.text.lower()

                if w not in stop_words:
                    words.append(w)

        # take first meaningful words
        phrase = " ".join(words[:6]).capitalize()

        if len(phrase) < 6:
            continue

        structure["branches"][phrase] = [sentence]

    return structure


def run_flowchart():
    import os
    import textwrap
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs("static/flowchart", exist_ok=True)

    # Read points
    with open("static/output/points.txt", "r", encoding="utf-8") as f:
        raw_points = [l.strip() for l in f if l.strip()]

    # Extract structure
    structure = extract_flow_points(raw_points)

    # Convert structure → list for drawing
    points = []
    points.append(structure["main"])

    for branch in structure["branches"]:
        points.append(branch)

    # Debug print
    print("FLOWCHART KEY POINTS:")
    for p in points:
        print("-", p)

    width = 900
    img_height = 150 * len(points)

    img = Image.new("RGB", (width, img_height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    x_center = width // 2
    y = 40

    centers = []

    # ---------- DRAW RECTANGLES ----------
    for p in points:

        wrapped = textwrap.wrap(p, 30)

        line_widths = []
        line_heights = []

        for line in wrapped:
            bbox = font.getbbox(line)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_widths.append(w)
            line_heights.append(h)

        text_w = max(line_widths)
        text_h = sum(line_heights) + (len(wrapped)-1)*5

        padding_x = 40
        padding_y = 20

        box_w = text_w + padding_x
        box_h = text_h + padding_y

        draw.rectangle(
            [x_center - box_w//2, y, x_center + box_w//2, y + box_h],
            outline="black",
            width=2
        )

        current_y = y + padding_y//2

        for line in wrapped:
            bbox = font.getbbox(line)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]

            draw.text(
                (x_center - lw//2, current_y),
                line,
                fill="black",
                font=font
            )

            current_y += lh + 5

        centers.append((x_center, y, box_w, box_h))
        y += box_h + 40

    # ---------- DRAW ARROWS ----------
    for i in range(len(centers)-1):

        x1, y1, w1, h1 = centers[i]
        x2, y2, w2, h2 = centers[i+1]

        start = (x1, y1 + h1)
        end = (x2, y2)

        draw.line([start, end], fill="black", width=2)

        arrow_size = 10

        draw.polygon([
            (end[0] - arrow_size, end[1] - arrow_size),
            (end[0] + arrow_size, end[1] - arrow_size),
            (end[0], end[1])
        ], fill="black")

    # ---------- SAVE ----------
    existing = os.listdir("static/flowchart")
    idx = len(existing) + 1

    path = f"static/flowchart/flowchart_{idx}.png"
    img.save(path)

    print("[INFO] Flowchart saved:", path)

    return path
# ---------------- QUIZ ----------------


# Load API key from environment (kept secret)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

# Configure the SDK globally — no need to pass api_key anywhere else
genai.configure(api_key=GEMINI_API_KEY)

def generate_quiz():
    import json
    try:
        with open("static/output/points.txt", "r", encoding="utf-8") as f:
            points = [l.strip() for l in f if l.strip()]

        if not points:
            print("No study material found!")
            return []

        joined_points = ". ".join(points)

        prompt = f"""
Generate 4 multiple choice questions from the following study material.

Strictly return ONLY valid JSON in this format:

[
  {{
    "question": "Question text",
    "options": ["Option1", "Option2", "Option3", "Option4"],
    "answer": "Correct Option"
  }}
]

Study Material:
{joined_points}
"""

        response = voice_model.generate_content(prompt)
        text = response.text.strip()

        print("RAW GEMINI RESPONSE:\n", text)

        start = text.find("[")
        end = text.rfind("]") + 1

        if start != -1 and end != -1:
            text = text[start:end]

        quiz_data = json.loads(text)

        print("Generated Quiz:", quiz_data)
        return quiz_data

    except Exception as e:
        print("Quiz generation error:", e)  
        return []   