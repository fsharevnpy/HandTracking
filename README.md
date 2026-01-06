# HandTracking

Hand tracking project using **Python 3.10.7**, **OpenCV**, and **MediaPipe**.  
This demo allows you to control the mouse cursor with hand gestures.

---

## Requirements
- Python **3.10.7**
- Libraries: `numpy`, `opencv-python`, `mediapipe`

---

## Setup (Windows PowerShell)

```powershell
# Create virtual environment in project folder
python -m venv .venv

# Activate environment
.venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
python -m pip install numpy opencv-python mediapipe

# Run hand tracking (camera)
python hand.py

# Open another terminal and run cursor control
python cursor.py