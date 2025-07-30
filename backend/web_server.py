
from flask import Flask, render_template, Response, jsonify, request
from threading import Thread
from object_detection import generate_frame, run_object_detection, update_settings, get_obj_count

app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")

        
@app.route("/cv2_stream")
def stream():
    return Response(generate_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/update-settings", methods=["POST"])
def updatesettings():
    new_settings = request.get_json()
    update_settings(new_settings)
    return jsonify({"status": "Settings updated and sent to backend"})

@app.route("/get-obj-count")
def getobjcount():
    return jsonify({"detectedCount": get_obj_count()})

@app.route("/settings")
def settings():
    return render_template("settings.html", icon_route="/")

@app.route("/")
def index():
    return render_template("index.html", icon_route="/settings")

if __name__ == "__main__":
    # run object detection on separate thread so Flask server can start at same time
    Thread(target=run_object_detection, daemon=True).start()
    app.run(port=5000)