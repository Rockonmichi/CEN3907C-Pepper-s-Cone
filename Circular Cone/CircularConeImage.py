import cv2
import numpy as np
import mediapipe as mp

# === CONFIG ===
input_path = "IMG_8823.png"
output_path = "cone_warp_image.png"

frame_size = 300
canvas_size = 600
subject_scale = 0.6

# === STEP 1: Load image ===
img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
if img is None:
    raise ValueError("Could not load image.")

# Ensure we have BGR
if img.shape[2] == 4:
    bgr = img[:, :, :3]
else:
    bgr = img

# === STEP 2: Remove background with MediaPipe ===
mp_selfie_segmentation = mp.solutions.selfie_segmentation
with mp_selfie_segmentation.SelfieSegmentation(model_selection=1) as segmentor:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = segmentor.process(rgb)
    mask = result.segmentation_mask > 0.5

bg_removed = np.zeros_like(bgr)
bg_removed[mask] = bgr[mask]

# === STEP 3: Center + scale subject in square frame ===
src_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)

h, w = bg_removed.shape[:2]
fit_scale = min(frame_size / max(h, w), 1.0) * subject_scale
new_w, new_h = max(1, int(w * fit_scale)), max(1, int(h * fit_scale))

resized = cv2.resize(bg_removed, (new_w, new_h), interpolation=cv2.INTER_AREA)
y_off = (frame_size - new_h) // 2
x_off = (frame_size - new_w) // 2
src_frame[y_off : y_off + new_h, x_off : x_off + new_w] = resized

# === STEP 4: Build cone warp map (same as live) ===
map_x = np.zeros((canvas_size, canvas_size), dtype=np.float32)
map_y = np.zeros((canvas_size, canvas_size), dtype=np.float32)

center_x = canvas_size // 2
center_y = canvas_size // 2
max_radius = canvas_size // 2

for y in range(canvas_size):
    dy = y - center_y
    for x in range(canvas_size):
        dx = x - center_x
        radius = np.sqrt(dx * dx + dy * dy)
        if radius > max_radius:
            map_x[y, x] = 0
            map_y[y, x] = 0
            continue

        angle = np.arctan2(dy, dx)
        if -np.pi / 2 <= angle <= np.pi / 2:
            norm_angle = (angle + (np.pi / 2)) / np.pi
            norm_radius = 1.0 - (radius / max_radius)

            src_x = norm_angle * (frame_size - 1)
            src_y = norm_radius * (frame_size - 1)

            map_x[y, x] = src_x
            map_y[y, x] = src_y
        else:
            map_x[y, x] = 0
            map_y[y, x] = 0

# === STEP 5: Warp the image ===
warped = cv2.remap(src_frame, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

# === STEP 6: Save result ===
cv2.imwrite(output_path, warped)
print(f"Saved warped image with background removed: {output_path}")
