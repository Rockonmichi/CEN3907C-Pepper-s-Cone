import cv2
import numpy as np
import mediapipe as mp

# === CONFIGURATION ===
frame_size = 300           # Webcam frame input resolution
canvas_size = 600          # Output display resolution

# === VIDEO SETUP ===
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("Could not open webcam.")

mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# === GENERATE CONE WARP MAP ===
map_x = np.zeros((canvas_size, canvas_size), dtype=np.float32)
map_y = np.zeros((canvas_size, canvas_size), dtype=np.float32)

center_x = canvas_size // 2
center_y = canvas_size // 2
max_radius = canvas_size // 2

for y in range(canvas_size):
    for x in range(canvas_size):
        dx = x - center_x
        dy = y - center_y
        radius = np.sqrt(dx ** 2 + dy ** 2)
        if radius > max_radius:
            continue  # skip values outside the cone base

        angle = np.arctan2(dy, dx)  # full -π to π
        if -np.pi / 2 <= angle <= np.pi / 2:
            # Normalize angle from [-π/2, π/2] → [0, 1]
            norm_angle = (angle + (np.pi / 2)) / np.pi
            norm_radius = 1.0 - (radius / max_radius)  # Flipped!

            src_x = int(norm_angle * frame_size)
            src_y = int(norm_radius * frame_size)

            # Clip to valid input range
            src_x = np.clip(src_x, 0, frame_size - 1)
            src_y = np.clip(src_y, 0, frame_size - 1)

            map_x[y, x] = src_x
            map_y[y, x] = src_y
        else:
            map_x[y, x] = 0
            map_y[y, x] = 0

# === MAIN LOOP ===
print("🎥 Press 'q' to quit.")
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (frame_size, frame_size))

    # === BACKGROUND REMOVAL ===
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = segmentor.process(rgb)
    mask = result.segmentation_mask > 0.5
    bg_removed = np.zeros_like(frame)
    bg_removed[mask] = frame[mask]

    # === CENTER + SCALE SUBJECT ===
    padded = np.zeros_like(bg_removed)
    scale = 0.6
    scaled = cv2.resize(bg_removed, (0, 0), fx=scale, fy=scale)
    y_off = (frame_size - scaled.shape[0]) // 2
    x_off = (frame_size - scaled.shape[1]) // 2
    padded[y_off:y_off+scaled.shape[0], x_off:x_off+scaled.shape[1]] = scaled

    # === APPLY CONE WARP ===
    warped = cv2.remap(padded, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # === DISPLAY ===
    cv2.imshow("Pepper's Cone Preview", warped)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
