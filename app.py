import os
import glob
import uuid
from datetime import datetime, timezone
import engine
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = "edumorph_secret"

# ---------------- SUPABASE ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_public_url(result):
    """Extract public URL from Supabase response - handles multiple formats"""
    print(f"[extract_public_url] Input type: {type(result)}, value: {result}")
    
    # If it's already a string, return it
    if isinstance(result, str):
        if result and (result.startswith('http') or result.startswith('/')):
            return result
        return None
    
    # If it's a dict, try various keys
    if isinstance(result, dict):
        # Try direct keys
        for key in ['publicUrl', 'public_url', 'publicURL', 'path', 'fullPath']:
            if key in result and result[key]:
                return result[key]
        
        # Try data nested object
        if 'data' in result:
            data = result['data']
            if isinstance(data, dict):
                for key in ['publicUrl', 'public_url', 'publicURL', 'path', 'fullPath']:
                    if key in data and data[key]:
                        return data[key]
        
        return None
    
    # If it has a .data attribute
    if hasattr(result, 'data'):
        data = getattr(result, 'data')
        if isinstance(data, dict):
            for key in ['publicUrl', 'public_url', 'publicURL', 'path', 'fullPath']:
                if key in data and data[key]:
                    return data[key]
    
    return None


def insert_user_library_item(user_id, filename, file_url, content_type):
    base_data = {
        "user_id": user_id,
        "file_name": filename,
        "file_url": file_url,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    insert_data = {**base_data, "content_type": content_type}
    print("DB insert data:", insert_data)
    try:
        supabase.table("user_library").insert(insert_data).execute()
        return
    except Exception as e:
        err_msg = str(e)
        print("DB insert failed, retrying with file_type if needed:", err_msg)
        if "content_type" in err_msg or "Could not find the 'content_type'" in err_msg:
            fallback_data = {**base_data, "file_type": content_type}
            print("Fallback DB insert data:", fallback_data)
            supabase.table("user_library").insert(fallback_data).execute()
            return
        raise

# ---------------- CONFIG ----------------
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/output/final_videos', exist_ok=True)

# ================= FRONTEND =================

@app.route("/")
def landing():
    return render_template("first.html")

@app.route("/owl")
def owl():
    return render_template("owl_animation.html")

@app.route("/home")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    # Get user
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user = res.data[0] if res.data else None

    # Count library
    res = supabase.table("user_library").select("*", count="exact").eq("user_id", user_id).execute()
    total_generated = res.count if res.count else 0

    goal = 100
    progress = int((total_generated / goal) * 100)

    last_quiz_score = session.get("last_quiz_score", 0)

    return render_template(
        "home1.html",
        user=user,
        total_generated=total_generated,
        progress=progress,
        last_quiz_score=last_quiz_score
    )

@app.route("/pro")
def pro():
    if "user_id" not in session:
        return redirect("/")
    return render_template("pro.html")

@app.route("/payment")
def payment():
    if "user_id" not in session:
        return redirect("/")
    return render_template("payment.html")

@app.context_processor
def inject_dashboard_data():
    if "user_id" not in session:
        return dict(total_generated=0, progress=0)

    user_id = session["user_id"]

    res = supabase.table("user_library").select("*", count="exact").eq("user_id", user_id).execute()
    total_generated = res.count if res.count else 0

    goal = 100
    progress = int((total_generated / goal) * 100)

    last_quiz_score = session.get("last_quiz_score", 0)

    return dict(
        total_generated=total_generated,
        progress=progress,
        last_quiz_score=last_quiz_score
    )

@app.context_processor
def inject_user():
    if "user_id" not in session:
        return dict(user=None)

    user_id = session["user_id"]

    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user = res.data[0] if res.data else None

    return dict(user=user)

@app.route("/age")
def age():
    if "uploaded_file" not in session:
        return redirect(url_for("dashboard"))
    return render_template("age.html")

@app.route("/select_age", methods=["POST"])
def select_age():
    age_group = request.form.get("age_group")
    if age_group in ["6-8", "9-10", "11+"]:
        session["age_group"] = age_group
        return redirect(url_for("slider"))
    return redirect(url_for("age"))

@app.route("/slider")
def slider():
    uploaded_file = session.get("uploaded_file")
    video_file = session.pop("video", None)
    comic_file = session.pop("comic", None)
    flowchart_file = session.pop("flowchart", None)

    return render_template(
        "slider.html",
        files=[],
        uploaded_file=uploaded_file,
        video=video_file,
        comic=comic_file,
        flowchart=flowchart_file
    )

@app.route("/library")
def library():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    res = supabase.table("user_library") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    library_items = res.data

    return render_template("library.html", library_items=library_items)

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user = res.data[0] if res.data else None

    res = supabase.table("user_library").select("*", count="exact").eq("user_id", user_id).execute()
    total_generated = res.count if res.count else 0

    return render_template(
        "user-profile.html",
        user=user,
        total_generated=total_generated
    )

# ================= QUIZ =================

@app.route("/quiz")
def quiz():
    questions = engine.generate_quiz()
    session["quiz_questions"] = questions
    return render_template("quiz.html", questions=questions)

@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():
    questions = session.get("quiz_questions", [])
    score = 0

    for i, q in enumerate(questions):
        selected = request.form.get(f"q{i}")
        if selected == q["answer"]:
            score += 1

    session["last_quiz_score"] = score
    return render_template("quiz.html", questions=questions, score=score)

# ================= AUTH =================

@app.route("/register", methods=["POST"])
def register():
    data = request.json

    try:
        res = supabase.auth.sign_up({
            "email": data["email"],
            "password": data["password"]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

    if res.session:
        supabase.table("profiles").insert({
            "id": res.user.id,
            "fname": data["firstname"],
            "lname": data["lastname"],
            "email": data["email"]
        }).execute()

        return jsonify({"success": True, "msg": "Registered Successfully"})

    return jsonify({"success": False, "message": "Signup failed"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json

    res = supabase.auth.sign_in_with_password({
        "email": data["email"],
        "password": data["password"]
    })

    if res.user:
        session["user_id"] = res.user.id
        session["user_email"] = res.user.email
        return jsonify({"success": True, "msg": "Login Success"})

    return jsonify({"success": False, "msg": "Invalid Credentials"}), 401

# ================= UPLOAD =================

@app.route("/home/upload", methods=["POST"])
def home_upload():
    file = request.files["file"]

    try:
        img = Image.open(file)
        img.verify()
    except Exception as e:
        return f"Invalid image: {str(e)}", 400

    safe_filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
    file.seek(0)
    file.save(filepath)

    engine.process_file(filepath)

    session["uploaded_file"] = unique_filename

    return redirect(url_for("age"))

# ================= GENERATION =================

@app.route("/animate", methods=["POST"])
def animate():
    if "user_id" not in session or "uploaded_file" not in session:
        return redirect("/home")

    user_id = session["user_id"]

    try:
        uploaded_file_path = os.path.join(
            app.config["UPLOAD_FOLDER"], session["uploaded_file"]
        )

        filename = f"{uuid.uuid4().hex}.mp4"
        out_path = os.path.join("static/output/final_videos", filename)

        age_group = session.get("age_group", "11+")

        engine.run_animation(out_path, uploaded_file_path, age_group)

        # Upload to Supabase
        storage_path = f"{user_id}/{filename}"
        print(f"Uploading file to Supabase path: {storage_path}")
        with open(out_path, "rb") as f:
            upload_result = supabase.storage.from_("user-files").upload(
                storage_path,
                f,
                {"upsert": True}
            )

        print("[ANIMATE] Getting public URL...")
        url_result = supabase.storage.from_("user-files").get_public_url(storage_path)
        print(f"[ANIMATE] URL result type: {type(url_result)}, value: {url_result}")
        
        public_url = extract_public_url(url_result)
        
        if not public_url or not isinstance(public_url, str):
            print(f"[ANIMATE] ❌ Invalid public URL: {public_url}")
            raise Exception(f"Invalid public URL returned: {public_url}")
        
        print(f"[ANIMATE] ✅ Public URL: {public_url}")

        insert_user_library_item(user_id, filename, public_url, "animation")

        return redirect(url_for("animation_page", file=public_url))
    except Exception as e:
        print(f"[ANIMATE] ❌ Final error: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Error uploading animation</h1><p>{str(e)}</p><p><a href='/'>← Back to Home</a></p>", 500

@app.route("/comic", methods=["POST"])
def comic():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    try:
        path = engine.run_comic()
        filename = f"{uuid.uuid4().hex}_{os.path.basename(path)}"
        storage_path = f"{user_id}/{filename}"
        print(f"Uploading file to Supabase path: {storage_path}")
        with open(path, "rb") as f:
            supabase.storage.from_("user-files").upload(
                storage_path,
                f,
                {"upsert": True}
            )

        print("[COMIC] Getting public URL...")
        url_result = supabase.storage.from_("user-files").get_public_url(storage_path)
        print(f"[COMIC] URL result type: {type(url_result)}, value: {url_result}")
        
        public_url = extract_public_url(url_result)
        
        if not public_url or not isinstance(public_url, str):
            print(f"[COMIC] ❌ Invalid public URL: {public_url}")
            raise Exception(f"Invalid public URL returned: {public_url}")
        
        print(f"[COMIC] ✅ Public URL: {public_url}")

        insert_user_library_item(user_id, filename, public_url, "comic")

        return redirect(url_for("comic_page", file=public_url))
    except Exception as e:
        print(f"[COMIC] ❌ Final error: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Error uploading comic</h1><p>{str(e)}</p><p><a href='/'>← Back to Home</a></p>", 500

@app.route("/flowchart", methods=["POST"])
def flowchart():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    try:
        path = engine.run_flowchart()
    except FileNotFoundError as e:
        return f"<h1>⚠️ Error</h1><p>{str(e)}</p><p><a href='/'>← Back to Home</a></p>", 400
    except Exception as e:
        return f"<h1>❌ Error generating flowchart</h1><p>{str(e)}</p><p><a href='/'>← Back to Home</a></p>", 500

    try:
        filename = f"{uuid.uuid4().hex}_{os.path.basename(path)}"
        storage_path = f"{user_id}/{filename}"
        print(f"Uploading file to Supabase path: {storage_path}")
        with open(path, "rb") as f:
            supabase.storage.from_("user-files").upload(
                storage_path,
                f,
                {"upsert": True}
            )

        print("[FLOWCHART] Getting public URL...")
        url_result = supabase.storage.from_("user-files").get_public_url(storage_path)
        print(f"[FLOWCHART] URL result type: {type(url_result)}, value: {url_result}")
        
        public_url = extract_public_url(url_result)
        
        if not public_url or not isinstance(public_url, str):
            print(f"[FLOWCHART] ❌ Invalid public URL: {public_url}")
            raise Exception(f"Invalid public URL returned: {public_url}")
        
        print(f"[FLOWCHART] ✅ Public URL: {public_url}")

        insert_user_library_item(user_id, filename, public_url, "flowchart")

        return redirect(url_for("flowchart_page", file=public_url))
    except Exception as e:
        print(f"[FLOWCHART] ❌ Final error: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Error uploading flowchart</h1><p>{str(e)}</p><p><a href='/'>← Back to Home</a></p>", 500

# ================= PAGES =================

@app.route("/animation")
def animation_page():
    if "user_id" not in session:
        return redirect("/")
    file_url = request.args.get("file") or session.pop("last_generated_url", None)
    return render_template("animation.html", file_url=file_url)

@app.route("/comic")
def comic_page():
    if "user_id" not in session:
        return redirect("/")
    file_url = request.args.get("file") or session.pop("last_generated_url", None)
    return render_template("comic.html", file_url=file_url)

@app.route("/flowchart")
def flowchart_page():
    if "user_id" not in session:
        return redirect("/")
    file_url = request.args.get("file") or session.pop("last_generated_url", None)
    return render_template("flowchart.html", file_url=file_url)

# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)