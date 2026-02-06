from flask import Flask, render_template, request
import engine
import glob
import os

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    path = "static/output/input.png"
    file.save(path)

    engine.process_file(path)

    return "File processed. Now click Animate / Comic / Flowchart."

@app.route("/animate")
def animate():
    # Run updated animation
    engine.run_animation()

    # Get latest final video
    videos = sorted(glob.glob("static/output/final_*.mp4"))

    if videos:
        latest = videos[-1]
        return render_template("index.html", video=latest)

    return "Animation failed"

@app.route("/comic")
def comic():
    engine.run_comic()
    return render_template("index.html", comic="static/output/comic.png")

@app.route("/flowchart")
def flowchart():
    engine.run_flowchart()
    return render_template("index.html", flowchart="static/output/flowchart.gv.png")

if __name__ == "__main__":
    app.run(debug=True)
