import cv2
import numpy as np

# === CONFIG ===
input_path = 'IMG_8823.png'  # Replace with your image name
output_path = 'curved_horizontal_wrap.png'

# === STEP 1: Load image ===
img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
if img is None:
    raise ValueError("Couldn't load image. Check the filename!")

# Separate BGR and alpha
if img.shape[2] == 4:
    bgr = img[:, :, :3]
    alpha = img[:, :, 3]
else:
    bgr = img
    alpha = np.ones(bgr.shape[:2], dtype=np.uint8) * 255

# === STEP 2: Prepare canvas ===
h, w = bgr.shape[:2]
canvas_w = 2 * w
canvas_h = h
canvas_bgr = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
canvas_alpha = np.zeros((canvas_h, canvas_w), dtype=np.uint8)

# Center image on black canvas
x_offset = (canvas_w - w) // 2
canvas_bgr[:, x_offset:x_offset+w] = bgr
canvas_alpha[:, x_offset:x_offset+w] = alpha

# === STEP 3: Create horizontal warp (imaginary circle) ===
radius = canvas_w / 2.0
amplitude = h / 4.0  # how much it curves vertically (adjust as needed)

map_x = np.zeros((canvas_h, canvas_w), dtype=np.float32)
map_y = np.zeros((canvas_h, canvas_w), dtype=np.float32)

for y in range(canvas_h):
    for x in range(canvas_w):
        dx = (x - canvas_w / 2) / radius  # from -1 to 1
        angle = dx * np.pi / 2  # only bend 90° arc max
        offset = np.sin(angle) * amplitude
        map_x[y, x] = x
        map_y[y, x] = np.clip(y - offset, 0, canvas_h - 1)

# === STEP 4: Remap image ===
warped_bgr = cv2.remap(canvas_bgr, map_x, map_y, interpolation=cv2.INTER_LINEAR)
warped_alpha = cv2.remap(canvas_alpha, map_x, map_y, interpolation=cv2.INTER_LINEAR)

# === STEP 5: Combine BGR and alpha on black ===
final_img = np.zeros_like(warped_bgr)
mask = warped_alpha > 0
for c in range(3):
    final_img[:, :, c][mask] = warped_bgr[:, :, c][mask]

# === STEP 6: Save result ===
cv2.imwrite(output_path, final_img)
print(f"✅ Saved to: {output_path}")
