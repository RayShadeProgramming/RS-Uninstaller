#!/usr/bin/env python3
"""Generate a simple application icon (ICO, 64x64, 32bpp) for RS-Uninstaller."""
import struct
import os

W = H = 64


def rounded_rect_inside(x, y, w, h, r):
    if x < 0 or y < 0 or x >= w or y >= h:
        return False
    cx = min(max(x, r), w - 1 - r)
    cy = min(max(y, r), h - 1 - r)
    dx = x - cx
    dy = y - cy
    return dx * dx + dy * dy <= r * r


def lerp(a, b, t):
    return int(round(a + (b - a) * t))


px = bytearray(W * H * 4)

# background gradient (top -> bottom)
top = (37, 99, 235)     # #2563EB
bot = (29, 78, 216)     # #1D4ED8

for y in range(H):
    for x in range(W):
        i = (y * W + x) * 4
        if rounded_rect_inside(x, y, W, H, 15):
            t = y / (H - 1)
            r = lerp(top[0], bot[0], t)
            g = lerp(top[1], bot[1], t)
            b = lerp(top[2], bot[2], t)
            px[i] = b
            px[i + 1] = g
            px[i + 2] = r
            px[i + 3] = 255
        else:
            px[i + 3] = 0

WHITE = (255, 255, 255)
LIGHT = (219, 234, 254)

def set_px(x, y, rgb):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 4
        px[i] = rgb[2]
        px[i + 1] = rgb[1]
        px[i + 2] = rgb[0]
        px[i + 3] = 255

# handle
for y in range(13, 18):
    for x in range(26, 38):
        set_px(x, y, LIGHT)
# lid
for y in range(18, 23):
    for x in range(15, 49):
        set_px(x, y, WHITE)
# lid highlight line
for y in range(19, 21):
    for x in range(17, 47):
        set_px(x, y, LIGHT)
# body (trapezoid)
for y in range(24, 51):
    t = (y - 24) / 26.0
    left = 18 + 3 * t
    right = 46 - 3 * t
    for x in range(int(left), int(right) + 1):
        set_px(x, y, WHITE)
# slots (cut out to background color)
bg = (37, 99, 235)
for cx in (27, 32, 37):
    for y in range(28, 47):
        for x in range(cx - 1, cx + 2):
            set_px(x, y, bg)

# convert to bottom-up BGRA
rows = []
for y in range(H - 1, -1, -1):
    rows.append(bytes(px[y * W * 4:(y + 1) * W * 4]))
xor_data = b"".join(rows)

# AND mask: all zero, rows padded to 4 bytes
mask_row = ((W + 31) // 32) * 4
and_data = b"\x00" * (mask_row * H)

bi = struct.pack("<IiiHHIIiiII",
                 40, W, H * 2, 1, 32, 0, len(xor_data) + len(and_data),
                 0, 0, 0, 0)
image = bi + xor_data + and_data

ico = struct.pack("<HHH", 0, 1, 1)
ico += struct.pack("<BBBBHHII", W, H, 0, 0, 1, 32, len(image), 6 + 16)
ico += image

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "res", "icon.ico")
with open(out, "wb") as f:
    f.write(ico)
print("wrote", os.path.abspath(out), len(ico), "bytes")
