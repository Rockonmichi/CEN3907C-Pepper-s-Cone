import cv2
import numpy as np
import mediapipe as mp

# === CONFIG ===
frame_size = 300  # size of each frame
gap = 100         # size of black center gap
fps = 30

# === SETUP ===
cap = cv2.VideoCapture(0)  # <== Use webcam now
if not cap.isOpened():
    raise IOError("Could not open webcam.")

mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# Total canvas size
canvas_w = frame_size * 3
canvas_h = frame_size * 3
center_x = frame_size
center_y = frame_size

def tilt_image(image, angle_deg):
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    tilted = cv2.warpAffine(image, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    return tilted

print("🎥 Press 'q' to quit.")
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (frame_size, frame_size))
    #frame = tilt_image(frame, -22)

    # Background removal (optional)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = segmentor.process(rgb)
    mask = result.segmentation_mask > 0.5
    bg_removed = np.zeros_like(frame)
    bg_removed[mask] = frame[mask]
    frame = bg_removed

    # Create mirrored views
    top = cv2.flip(frame, 0)
    bottom = cv2.flip(frame, 90)
    left = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    right = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # Create canvas with black center
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    # Place views
    canvas[0:frame_size, center_x:center_x+frame_size] = bottom  # Top
    canvas[center_y:center_y+frame_size, 0:frame_size] = right   # Left
    canvas[center_y:center_y+frame_size, center_x+frame_size:canvas_w] = left  # Right
    canvas[center_y+frame_size:canvas_h, center_x:center_x+frame_size] = top   # Bottom

    # Show live output
    cv2.imshow('Live Hologram Preview', canvas)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
