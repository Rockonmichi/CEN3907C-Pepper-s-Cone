import cv2
import numpy as np
import mediapipe as mp

# === CONFIG ===
input_video = "try_no_background.mp4"  # Replace with your file
output_video = "pyramid_hologram_final.mp4"
frame_size = 300  # size of each frame
gap = 100         # size of black center gap
fps = 30

# === SETUP ===
cap = cv2.VideoCapture(input_video)
if not cap.isOpened():
    raise IOError("Could not open video.")

mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# Total canvas size
canvas_w = frame_size * 3
canvas_h = frame_size * 3
center_x = frame_size
center_y = frame_size

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_video, fourcc, fps, (canvas_w, canvas_h))

def tilt_image(image, angle_deg):
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    tilted = cv2.warpAffine(image, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    return tilted

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Resize and background removal
    frame = cv2.resize(frame, (frame_size, frame_size))
    frame = tilt_image(frame, -22)  # Tilt by -22 degrees


    # Create mirrored views
    top = cv2.flip(frame, 0)
    bottom = cv2.flip(frame, 90)
    left = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    right = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # Create canvas with black center
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    # Positions (around a black center square)
    canvas[0:frame_size, center_x:center_x+frame_size] = bottom #left                      # Top
    canvas[center_y:center_y+frame_size, 0:frame_size] = right #top                    # Left
    canvas[center_y:center_y+frame_size, center_x+frame_size:canvas_w] = left #bottom   # Right
    canvas[center_y+frame_size:canvas_h, center_x:center_x+frame_size] = top #right  # Bottom

    out.write(canvas)

cap.release()
out.release()
print(f"✅ Final hologram video saved as: {output_video}")
