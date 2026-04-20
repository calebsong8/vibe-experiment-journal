# Bird Waveform Synthesizer Mapped to Dual-Hand Free Motion

Mediapipe webcam overlay that maps waveform output to usage of two hands. Displays closest matched waveform of one of 25 birds with image. Outputs frequency with dynamic changes on speaker.

## usage

### getting started

1. Clone the repository.
2. Serve the directory via a local server (e.g., `python -m http.server` or VS Code Live Server).
3. Open in a modern browser (Chrome/Edge recommended for MediaPipe performance).
4. Click **Enable Audio Synthesis** and allow camera access.

### how to use

**First hand:** wave-form curves generated between each fingertip to generate frequency. height of hand on screen raises or lowers pitch accordingly.

**Second hand:** picture of bird mapped between thumb and pinky finger. size of bird picture increases or decreases volume accordingly.

**Modes:** click on "mode: synthesis" button to switch to "mode: bird call" and vice versa

## stack

- **Computer Vision:** MediaPipe Hands (21-point landmark tracking)
- **Audio Engine:** Web Audio API (low-latency oscillator synthesis)
- **Graphics:** HTML5 Canvas API (AR overlays & hologram masking)
- **Data Source:** Wikipedia REST API (dynamic species metadata)
- **Video:** MediaPipe Camera Utils (synchronized stream management)
- **Logic:** Euclidean distance matching for gesture-to-bird identification
- **Frontend:** Vanilla JS (ES6+), CSS3 (Flexbox/Grid), HTML5

astrolabe-esque style

## credit

inspired by @sugiyamer on [instagram](https://www.instagram.com/sugiyamer/) and [youtube](https://www.youtube.com/@sugiyamer)

see this video: [90-Second Tutorial on Vibe Coding for Computer Vision Using Gemini](https://youtube.com/shorts/MzUMk9KCBpA?si=F__FAt-RwFMzc-L0)
