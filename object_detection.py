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
load_dotenv("secret_consts.env")

# # for benchmarking
# from collections import deque

# inf_time_deque = deque(maxlen=30)
# conf_deque = deque(maxlen=30)

# NOTES:
# The video that is embedded into the Flask web server cannot be
# straight from esp32 stream, it has to be the cv2 render with boxes 
# and everything. 

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

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

annotated_frame = set_status_frame("Starting Object Detection...")
last_frame_time = time.time()
disconnect_threshold = 10 # in sec
stream_active = True

# run on separate thread to check if camera disconnected. Stream stuck on frame too long = disconnect
def check_disconnect():
    while stream_active:
        time.sleep(1)
        if(time.time() - last_frame_time >= disconnect_threshold):
            stream_active = False

# frame generator for Response object
# https://stackoverflow.com/questions/48909132/reading-mjpeg-stream-from-flask-server-with-opencv-python
def generate_frame():
    while True:       # Threading.lock() ????
        try:
            _, jpeg = cv2.imencode(".jpg", annotated_frame)
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        except():
            print("generate_frame() couldn't yield frame")
            return
        
# Object detection should only run while the Flask server is running
def run_object_detection():
    # # trying cpu/gpu if no diff or worse
    # # can mess around with model sizes s,m,l
    model = torch.hub.load("ultralytics/yolov5", "yolov5m")
    model.to("cuda:0")
    # Making it so that it only detects Humans (0) (change to cars (2) later)
    # See for class list: https://gist.github.com/rcland12/dc48e1963268ff98c8b2c4543e7a9be8
    model.classes = [0]
    model.conf = 0.5
    label = model.names[0]

    stream = requests.get(f"http://{os.getenv("ESP_IP_ADDRESS")}:80/", stream=True)
    byte_arr = b''
    global annotated_frame
    global last_frame_time

    x_scale = 640/416
    y_scale = 480/416

    frame_count = 3 # start at 3 to run model() on first frame available
    detected_count = 0
    old_count = detected_count

    debounce_count = -1
    debounce_start = True
    start_time = time.time()
    entry_type = -1
    debounce_threshold = 2 # in sec

    print("Running Object Detection")
    # https://stackoverflow.com/questions/21702477/how-to-parse-mjpeg-http-stream-from-ip-camera/21844162#21844162
    for chunk in stream.iter_content(chunk_size=1024*8): # less than 1024*8 is choppy, delayed
        if(stream.status_code != 200):
            print("Unexpected status code:", stream.status_code)
            break

        byte_arr += chunk
        # find jpeg image boundaries
        a = byte_arr.find(b'\xff\xd8')
        b = byte_arr.find(b'\xff\xd9')

        if(a != -1 and b != -1):
            jpeg = byte_arr[a:b+2]      # Use this for send_telegram_photo?
            byte_arr = byte_arr[b+2:]

            frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
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
                if(time.time() - start_time >= debounce_threshold):
                    if(entry_type==0 and detected_count <= debounce_count):
                        print("Obj leaving")
                        send_telegram_photo(jpeg, "Obj leaving")
                        debounce_count = -1 # prevent infinite obj leaving notif
                    elif(entry_type==1 and detected_count >= debounce_count):
                        print("Obj entering")
                        send_telegram_photo(jpeg, "Obj entering")
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

            cv2.putText(frame, f"# Obj Detected: {detected_count}",
                        (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
            
            annotated_frame = frame
            last_frame_time = time.time()
            
            #cv2.imshow("YOLOv5 Video", frame)


        # if cv2.waitKey(1) & 0xFF == ord('q'):
        #     break

    # cv2.destroyAllWindows()

    # # benchmark
    # print(torch.cuda.get_device_name(0))
    # print("Avg inference time:", avg_inf_time)
    # print("Avg confidence level:", avg_conf)