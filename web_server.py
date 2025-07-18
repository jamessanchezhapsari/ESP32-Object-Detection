
from flask import Flask, render_template, Response
from threading import Thread
from object_detection import run_object_detection, generate_frame, check_disconnect

app = Flask(__name__)

        
@app.route("/cv2_stream")
def stream():
    return Response(generate_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/")
def index():
    return render_template("index.html", stream_url = "/cv2_stream")

if __name__ == "__main__":
    # run object detection on separate thread so Flask server can start at same time
    Thread(target=run_object_detection, daemon=True).start()
    Thread(target=check_disconnect, daemon=True).start()
    app.run(port=5000)