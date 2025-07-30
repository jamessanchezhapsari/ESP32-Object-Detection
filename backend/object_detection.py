import cv2
import torch

import requests
import numpy as np

# disable annoying warning flooding terminal
import warnings
warnings.filterwarnings("ignore", message="`torch.cuda.amp.autocast", category=FutureWarning)

import time
from dotenv import load_dotenv
import os
load_dotenv("backend/secret_consts.env")

# # for benchmarking
# from collections import deque

# inf_time_deque = deque(maxlen=30)
# conf_deque = deque(maxlen=30)

######################## Globals ########################
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

annotated_frame = None             
stream_active = True
detected_count = 0 # num objs detected

settings = { # these change whenever new settings are saved in website
    "telegramNotif": True,
    "debounceThresh": 3,
    "minCount": 0,
    "maxCount": 100
}

######################## Functions ########################
def update_settings(new_settings):
    settings.update(new_settings)
    print(settings)

def get_obj_count():
    return detected_count

def send_telegram_photo(jpeg_buffer, caption):
    data = {"chat_id":chat_id, "caption":caption}
    files = {"photo":("photo.jpg", jpeg_buffer)}
    resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=data, files=files)
    return resp.status_code == 200

# create black frame with centered stream status text
def set_status_frame(status):
    frame = np.zeros((480,640,3), dtype=np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    thickness = 2
    
    (text_width, text_height), _ = cv2.getTextSize(status, font, font_scale, thickness)
    x_centered = (640 - text_width) // 2
    y_centered = (480 + text_height) // 2

    cv2.putText(frame, status, (x_centered, y_centered),
                font, font_scale, (255,255,255), thickness, cv2.LINE_AA)
    return frame

# frame generator for Flask Response object
# https://stackoverflow.com/questions/48909132/reading-mjpeg-stream-from-flask-server-with-opencv-python
def generate_frame():
    while True:       # Threading.lock() ????
        try:
            _, jpeg = cv2.imencode(".jpg", annotated_frame)
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        except():
            print("generate_frame() couldn't yield frame")
            return

def connect_stream():
    while True:
        try:
            # timeout(for initial connection, for read attempts)
            stream = requests.get(f"http://{os.getenv("ESP_IP_ADDRESS")}:80/", stream=True, timeout=(None, 5))
            return stream
        except requests.exceptions.RequestException:
            print("Attempting connection again")
            time.sleep(0.1)

######################## Main function ########################
def run_object_detection():
    global annotated_frame, stream_active, detected_count
    annotated_frame = set_status_frame("Connecting to stream...")

    # benchmark showed gpu better than cpu  
    # can mess around with model sizes s,m,l
    print("Loading object detection model...")
    model = torch.hub.load("ultralytics/yolov5", "custom", path="backend/yolov5m.pt")
    model.to("cuda:0")
    # Making it so that it only detects Humans (0) (change to cars (2) later)
    # See for class list: https://gist.github.com/rcland12/dc48e1963268ff98c8b2c4543e7a9be8
    model.classes = [0]
    model.conf = 0.5
    label = model.names[0]

    x_scale = 640/416
    y_scale = 480/416

    while True:          
        annotated_frame = set_status_frame("Connecting to stream...")

        print("Connecting to ESP32 stream...")
        stream = connect_stream()
        byte_arr = b''

        frame_count = 3 # start at 3 to run model() on first frame available
        old_count = 0

        debounce_count = -1
        debounce_start = True
        start_time = time.time()
        entry_type = -1

        annotated_frame = set_status_frame("Starting Object Detection...")
        print("Running Object Detection")
        stream_active = True
        try:
            # https://stackoverflow.com/questions/21702477/how-to-parse-mjpeg-http-stream-from-ip-camera/21844162#21844162
            for chunk in stream.iter_content(chunk_size=1024*8): # less than 1024*8 is choppy, delayed

                byte_arr += chunk        
                # find jpeg image boundaries
                a = byte_arr.find(b'\xff\xd8')
                b = byte_arr.find(b'\xff\xd9')

                if(a != -1 and b != -1):
                    jpeg = byte_arr[a:b+2]     
                    byte_arr = byte_arr[b+2:]

                    jpeg_2 = np.frombuffer(jpeg, dtype=np.uint8)
                    if(len(jpeg_2) == 0): # prevent cv2.imdecode() crashes
                        continue

                    frame = cv2.imdecode(jpeg_2, cv2.IMREAD_COLOR)
                    smaller_frame = cv2.resize(frame, (416,416)) # resize for faster detection
                    frame_count += 1

                    # Object detection
                    #start_time = time.time()  # benchmark
                    if(frame_count % 4 == 0):
                        results = model(smaller_frame)
                        detected_count = len(results.xyxy[0])
                        
                        # start debounce
                        if(debounce_start and detected_count != old_count):
                            if(detected_count < old_count):
                                entry_type = 0
                            elif(detected_count > old_count):
                                entry_type = 1

                            debounce_count = detected_count
                            start_time = time.time()
                            debounce_start = False

                        # end debounce
                        if(time.time() - start_time >= settings["debounceThresh"]):
                            if(entry_type==0 and detected_count <= debounce_count and detected_count in range(settings["minCount"], settings["maxCount"]+1)):
                                print("Obj leaving")
                                if(settings["telegramNotif"]): send_telegram_photo(jpeg, "Obj leaving")
                                debounce_count = -1 # prevent infinite obj leaving notif
                            elif(entry_type==1 and detected_count >= debounce_count and detected_count in range(settings["minCount"], settings["maxCount"]+1)):
                                print("Obj entering")
                                if(settings["telegramNotif"]): send_telegram_photo(jpeg, "Obj entering")
                                debounce_count = 999 # same thing but for entering
                            debounce_start = True

                        old_count = detected_count

                    # inf_time = time.time() - start_time
                    # inf_time_deque.append(inf_time)

                    for obj in results.xyxy[0]: # boxes
                        x1, y1, x2, y2 = map(int, obj[:4])
                        conf = float(obj[4])
                        # if(frame_count % 4 == 0):
                        #     conf_deque.append(conf)  # benchmark
                        
                        # Scale 416x416 x,y coords to 640x480
                        x1 = int(x1 * x_scale)
                        x2 = int(x2 * x_scale)
                        y1 = int(y1 * y_scale)
                        y2 = int(y2 * y_scale)

                        cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
                        cv2.putText(frame, f"{label} Conf:{conf:.2f}", (x1, y1-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
                        
                    # # print benchmarking data
                    # avg_inf_time = sum(inf_time_deque) / len(inf_time_deque) if inf_time_deque else 0
                    # avg_conf = sum(conf_deque) / len(conf_deque) if conf_deque else 0

                    # cv2.putText(frame, f"Avg inf time: {avg_inf_time}",
                    #             (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)
                    # cv2.putText(frame, f"Avg conf: {avg_conf}",
                    #             (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)

                    # cv2.putText(frame, f"# Obj Detected: {detected_count}",
                    #             (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
                    
                    annotated_frame = frame
                    
                    #cv2.imshow("YOLOv5 Video", frame)


                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
        except(requests.exceptions.RequestException):
            print("ESP32 server read timeout")
        finally:
            stream_active = False
            annotated_frame = set_status_frame("Camera Disconnected")
            detected_count = 0
            stream.close()

        print("Restarting stream + object detection...")
        time.sleep(3)

        # cv2.destroyAllWindows()

        # # benchmark
        # print(torch.cuda.get_device_name(0))
        # print("Avg inference time:", avg_inf_time)
        # print("Avg confidence level:", avg_conf)