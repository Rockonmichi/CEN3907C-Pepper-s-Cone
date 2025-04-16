import cv2
import mediapipe as mp
import numpy as np

# Load video
cap = cv2.VideoCapture('michelle.mov')  # Replace with your file
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# Output video writer
output_size = 800
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('cone_hologram.mp4', fourcc, 30, (output_size, output_size))

frame_buffer = []

# Step 1: Read and remove background from each frame
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (300, 300))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = segmentor.process(rgb)

    mask = result.segmentation_mask > 0.1
    bg_removed = np.zeros_like(frame)
    bg_removed[mask] = frame[mask]

    frame_buffer.append(bg_removed)

cap.release()

# Step 2: Arrange frames in a circular layout
center = output_size // 2
radius = 250
num_views = 36

for i in range(num_views):
    canvas = np.zeros((output_size, output_size, 3), dtype=np.uint8)

    index = i % len(frame_buffer)
    frame = frame_buffer[index]
    frame = cv2.resize(frame, (100, 100))

    angle = 2 * np.pi * i / num_views
    x = int(center + radius * np.cos(angle)) - 50
    y = int(center + radius * np.sin(angle)) - 50

    canvas[y:y+100, x:x+100] = frame
    out.write(canvas)

out.release()
cv2.destroyAllWindows()
