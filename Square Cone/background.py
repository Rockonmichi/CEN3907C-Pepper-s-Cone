import cv2
import numpy as np
import mediapipe as mp

# === CONFIG ===
input_path = "try.mp4"
output_path = "try_no_background.mp4"

# Open video
cap = cv2.VideoCapture(input_path)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

# Output writer
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

# Mediapipe segmentation
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # === STEP 1: Segmentation mask (to find the subject) ===
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = segmentor.process(rgb)
    seg_mask = (result.segmentation_mask > 0.3).astype(np.uint8) * 255

    # === STEP 2: Green mask (detect green pixels) ===
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_green = np.array([30, 30, 30])  # expanded range
    upper_green = np.array([95, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    green_mask = cv2.GaussianBlur(green_mask, (9, 9), 0)

    # === STEP 3: Combine masks to remove green from segmented person ===
    combined_mask = cv2.bitwise_and(seg_mask, cv2.bitwise_not(green_mask))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
    combined_mask = cv2.GaussianBlur(combined_mask, (15, 15), 0)

    # === STEP 4: Apply final mask ===
    foreground = cv2.bitwise_and(frame, frame, mask=combined_mask)
    background = np.zeros_like(frame)
    final = np.where(combined_mask[..., None] > 0, foreground, background)

    # === STEP 5: Green spill suppression ===
    final_float = final.astype(np.float32) / 255.0
    r = final_float[:, :, 2]
    g = final_float[:, :, 1]
    b = final_float[:, :, 0]

    # Suppress green halo by reducing excess green
    green_excess = np.maximum(0, g - np.maximum(r, b))
    final_float[:, :, 1] = g - 0.6 * green_excess  # reduce green

    # Convert back to uint8
    final_cleaned = (np.clip(final_float, 0, 1) * 255).astype(np.uint8)

    out.write(final_cleaned)

cap.release()
out.release()
print(f"✅ Background removed and green cleaned. Output saved to '{output_path}'")
