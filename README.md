# ESP32 Object Detection
This program lets you use your ESP32 with a camera attachment to detect specific objects. A local webserver is created to display the stream in a simple dashboard which also has settings like enabling Telegram
notifications if an object enters/leaves and changing the object detection behavior.

The libraries/frameworks used include: **Flask, OpenCV, YOLO, the Python *requests* library**.

The frontend uses **Tailwind CSS** and **Alpine.js**. 

## Video showcase ##

**TAKE VIDEO AND EMBED HERE**

## Items/programs you'll need
- PC 
- ESP32 with camera attachment
- Arduino IDE
- WiFi connection

## Installation   
### First steps 
1. Clone the repository on your PC
2. Open a powershell terminal in the project directory and run `Set-ExecutionPolicy Unrestricted -Scope Process`
3. Create a virtual environment (venv) in the directory root with `python -m venv .venv`
4. Activate the venv with `.venv\Scripts\Activate`. You should now see (.venv) in green on your terminal.
5. To install the dependencies run `pip install -r requirements.txt`

### Creating credential files   (credentials.h and secret_consts.env)
1. In `backend/esp32_camera_webserver/`, create a new file named credentials.h and paste the following code (edit with actual info):
   
   ```
   #ifndef CREDENTIALS_H
   #define CREDENTIALS_H
  
   #define WIFI_SSID "Your SSID"
   #define WIFI_PASS "Your Wifi password"
  
   #endif
   ```
2. In `backend/`, create a new file named secret_consts.env and paste the following :

   ```
   ESP_IP_ADDRESS = xxx.xxx.x.xxx

   TELEGRAM_BOT_TOKEN = xxxxxxxxxxxx
   TELEGRAM_CHAT_ID = xxxxxxxxxxx
   ```

   1. To get the ESP IP address, follow the steps below in [Flashing ESP32](#flashing-esp32), then come back 
   2. To get the Telegram tokens, first install the Telegram app on your phone and sign in.
   3. Search for @BotFather, and send it /newbot. Follow the prompts.
   4. BotFather will give you a token, use that in `TELEGRAM_BOT_TOKEN`
   5. Run this quick python script anywhere on your PC
      ```
      import requests

      BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN"
      response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates")
      print(response.json())
      ```
      The output will contain a lot of text, but look for text in the form of:

      ```
      "chat": {
        "id": 123456789,
        ...
      }
      ```
      Use that id in `TELEGRAM_CHAT_ID` 

### Flashing ESP32
1. Connect your ESP32 with camera attachment to your PC via USB. 
2. Go to *File > Open* and go into `backend/esp32_camera_webserver/` then select `esp32_camera_webserver.ino`
   If the ESP32 isn't detected automatically as an ESP32, select *ESP32 Dev Module* as the board for whichever COM port it's connected to.
3. In *Tools* at the top bar select, *Partition Scheme* > *Huge APP* and *PSRAM* > *Enabled*
4. Click on *Upload* to flash the ESP32. Take note of the IP address of the ESP web server, you'll need it for secret_consts.env

**Now the ESP32 is programmed to start a video stream webserver using the camera. You don't need to flash it everytime, just connect your ESP to your laptop or another power source.**

## How to run
Run *web_server.py* :

If you use vscode and have the run button, try that. If not or if it doesn't work, in the project directory run:

`& ./.venv/Scripts/python.exe ./backend/web_server.py`

To exit, spam Ctrl+C

## How it works

### Project Diagram
<img width="908" height="558" alt="esp32 proj diagram" src="https://github.com/user-attachments/assets/6105b7fa-5459-4993-884b-be25d36073b5" />

Since the ESP32 hardware is too weak to run the YOLO object detection model, the PC takes care of that heavy load and also hosts the Flask webserver (`web_server.py`). If the PC has an Nvidia GPU, the YOLO can take advantage of CUDA to accelerate the object detection.

The job of the ESP32 instead is to take pictures in rapid succession and upload them to its own webserver to create a video stream. The PC (in `object_detection.py`) then grabs those frames and processes them with YOLO. Once the bounding boxes are drawn with OpenCV, these final "*annotated*" frames are sent to the Flask webserver.

## Things to add in the future
- Add a way to gracefully close the entire program instead of spamming Ctrl+C in the terminal
- Release project as actual website with user database and login system OR Create some sort of executable file to compress project and make running the program cleaner
- Let user input credentials/keys in a nicer way than creating the files themselves
- Add setting to change object of interest in web site
- Train model to achieve higher accuracy and speed

## License
This project is licensed under GNU General Public License v3.0 
See the [COPYING](COPYING) file for details.

## Credits
The code in `esp32_camera_webserver.ino` was written by Rui Santos and can be found at:
https://randomnerdtutorials.com/esp32-cam-video-streaming-web-server-camera-home-assistant/
