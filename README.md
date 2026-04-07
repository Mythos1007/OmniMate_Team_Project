# OmniMate Assistant Workspace

This repository is tracked from the assistant directory root.
Current git root: /home/mythos/assistant_ws/src/assistant

## Required Versions (Recommended)

- OS: Ubuntu 22.04 LTS
- ROS 2: Humble Hawksbill
- Python: 3.10.x (ROS 2 Humble default)
- Colcon: 0.15+

## Python Packages

Install in your active environment:

```bash
pip install \
  PySide6==6.7.2 \
  requests==2.32.3 \
  SpeechRecognition==3.10.4 \
  edge-tts==6.1.13 \
  faster-whisper==1.0.3 \
  PyYAML==6.0.2 \
  numpy==1.26.4 \
  opencv-python==4.10.0.84
```

Optional cloud TTS SDKs (if using direct SDK path):

```bash
pip install elevenlabs==1.8.0 cartesia==1.0.0
```

## ROS 2 Packages (apt)

```bash
sudo apt update
sudo apt install -y \
  ros-humble-nav2-msgs \
  ros-humble-geometry-msgs \
  ros-humble-std-msgs \
  ros-humble-std-srvs \
  ros-humble-launch \
  ros-humble-launch-ros
```

## API Secrets Setup

Do not hardcode API keys in source.

1) Copy example file:

```bash
mkdir -p ~/.config/assistant
cp secrets.example.json ~/.config/assistant/secrets.json
```

2) Fill key fields in ~/.config/assistant/secrets.json:

- weather_api_key
- elevenlabs_api_key
- elevenlabs_voice_id
- cartesia_api_key
- cartesia_voice_id

3) Export shared secrets path:

```bash
export ASSISTANT_SECRETS_FILE=~/.config/assistant/secrets.json
```

The secrets example already includes API issue links:

- KMA weather API: https://www.data.go.kr/data/15084084/openapi.do
- ElevenLabs API: https://elevenlabs.io/app/settings/api-keys
- Cartesia API: https://play.cartesia.ai/

## Build

```bash
cd /home/mythos/assistant_ws
colcon build --base-paths src/assistant
source install/setup.bash
```
