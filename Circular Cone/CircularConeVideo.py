import cv2
import numpy as np
import mediapipe as mp

# === CONFIG ===
frame_size = 300           # Input webcam frame size (square)
canvas_size = 600          # Output display size
warp_map_path = '45_cone_stereo_pixel_to_ray_map_left.png'  # Make sure this is in the same folder
rotation_angle = 0         # Default rotation angle (can be adjusted)
power = 1.0                # Brightness power (matches Unity WarpBase)
alpha = 1.0                # Brightness alpha (matches Unity WarpBase)

# === SETUP VIDEO ===
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("Could not open webcam.")

mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# === LOAD WARP MAP ===
encoded_map = cv2.imread(warp_map_path, cv2.IMREAD_UNCHANGED)
if encoded_map is None or encoded_map.shape[2] != 4:
    raise ValueError("Warp map must be a valid 4-channel RGBA image.")

height, width = encoded_map.shape[:2]
mapDiv = 4095.0  # Same as in Unity WarpBase

# Decode warp map using the same method as WarpBase.ConvertRGBATexture2Map
r = encoded_map[:, :, 0].astype(np.float32)
g = encoded_map[:, :, 1].astype(np.float32)
b = encoded_map[:, :, 2].astype(np.float32)
a = encoded_map[:, :, 3].astype(np.float32)

# Match the precise bit-shifting logic from WarpBase
LOAD_TEX_COLOR_BIT_DEPTH = 8
map_x = ((r * (1 << LOAD_TEX_COLOR_BIT_DEPTH) + g) / mapDiv) * frame_size
map_y = ((b * (1 << LOAD_TEX_COLOR_BIT_DEPTH) + a) / mapDiv) * frame_size

# Handle flip_texture like in WarpBase
flip_texture = True
if flip_texture:
    map_y = frame_size - map_y

# Clip to valid range (required for OpenCV remap)
map_x = np.clip(map_x, 0, frame_size - 1)
map_y = np.clip(map_y, 0, frame_size - 1)

# Create rotation matrix function (similar to WarpBase.LateUpdate)
def get_rotation_matrix(angle_degrees):
    """Create rotation matrix for texture coordinates similar to WarpBase"""
    # Convert to radians
    angle_rad = np.radians(angle_degrees)
    # Create rotation matrix
    cos_val = np.cos(angle_rad)
    sin_val = np.sin(angle_rad)
    # Tablet aspect ratio (4:3) matching Unity tabletScreenScale
    tablet_scale = np.array([4.0, 3.0])
    
    # Create rotation matrix similar to Unity's computation
    m00 = cos_val / tablet_scale[0]
    m01 = -sin_val / tablet_scale[0]
    m10 = sin_val / tablet_scale[1]
    m11 = cos_val / tablet_scale[1]
    
    return np.array([[m00, m01], [m10, m11]])

# === LOOP ===
print("🎥 Press 'q' to quit, 'r'/'t' to rotate, '+'/'-' to adjust brightness.")
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Resize to square format
    frame = cv2.resize(frame, (frame_size, frame_size))

    # === BACKGROUND REMOVAL ===
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = segmentor.process(rgb)
    mask = result.segmentation_mask > 0.5
    bg_removed = np.zeros_like(frame)
    bg_removed[mask] = frame[mask]

    # === CENTER SUBJECT WITH PADDING (like the tiger example) ===
    padded = np.zeros_like(bg_removed)
    scaled = cv2.resize(bg_removed, (0, 0), fx=0.6, fy=0.6)

    y_offset = (frame_size - scaled.shape[0]) // 2
    x_offset = (frame_size - scaled.shape[1]) // 2
    padded[y_offset:y_offset+scaled.shape[0], x_offset:x_offset+scaled.shape[1]] = scaled

    frame = padded

    # === GET ROTATION MATRIX (matching WarpBase behavior) ===
    rot_matrix = get_rotation_matrix(-rotation_angle)  # Negative like in WarpBase
    
    # === APPLY ROTATION TO WARP MAP ===
    # Create meshgrid of coordinates
    y, x = np.mgrid[0:height, 0:width]
    # Normalize to 0-1 range
    x_norm = x / width
    y_norm = y / height
    
    # Center coordinates at 0.5, 0.5
    x_centered = x_norm - 0.5
    y_centered = y_norm - 0.5
    
    # Apply rotation
    x_rotated = rot_matrix[0, 0] * x_centered + rot_matrix[0, 1] * y_centered + 0.5
    y_rotated = rot_matrix[1, 0] * x_centered + rot_matrix[1, 1] * y_centered + 0.5
    
    # Convert back to image coordinates
    x_rotated = x_rotated * width
    y_rotated = y_rotated * height
    
    # Use these rotated coordinates for lookup
    rot_map_x = cv2.remap(map_x, x_rotated.astype(np.float32), y_rotated.astype(np.float32), 
                          interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    rot_map_y = cv2.remap(map_y, x_rotated.astype(np.float32), y_rotated.astype(np.float32), 
                          interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # === APPLY BRIGHTNESS ADJUSTMENT (matching WarpBase power and alpha) ===
    frame_float = frame.astype(np.float32) / 255.0
    frame_adjusted = alpha * np.power(frame_float, power) * 255.0
    frame_adjusted = np.clip(frame_adjusted, 0, 255).astype(np.uint8)

    # === APPLY WARP MAP ===
    warped = cv2.remap(frame_adjusted, rot_map_x, rot_map_y, 
                       interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    # === SHOW AS SQUARE OUTPUT ===
    warped_resized = cv2.resize(warped, (canvas_size, canvas_size))
    cv2.imshow("Pepper's Cone Warped Feed", warped_resized)

    # === KEYBOARD CONTROLS ===
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        rotation_angle -= 5  # Rotate counterclockwise
        print(f"Rotation angle: {rotation_angle}°")
    elif key == ord('t'):
        rotation_angle += 5  # Rotate clockwise
        print(f"Rotation angle: {rotation_angle}°")
    elif key == ord('+') or key == ord('='):
        alpha = min(alpha + 0.1, 3.0)
        print(f"Brightness alpha: {alpha:.1f}")
    elif key == ord('-'):
        alpha = max(alpha - 0.1, 0.1)
        print(f"Brightness alpha: {alpha:.1f}")
    elif key == ord('['):
        power = max(power - 0.1, 0.1)
        print(f"Brightness power: {power:.1f}")
    elif key == ord(']'):
        power = min(power + 0.1, 3.0)
        print(f"Brightness power: {power:.1f}")

cap.release()
cv2.destroyAllWindows()
