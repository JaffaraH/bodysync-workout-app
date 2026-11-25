"""Exercises people create: same shape as the database's, holds counted in seconds, photos become a demo."""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

import exercise_data  # noqa: E402
import training  # noqa: E402


def _photo(color):
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), color).save(buf, "PNG")
    buf.seek(0)
    return buf


ex = exercise_data.make_custom("Total Gym Row", "lats", "machine", False, "Sit facing in.\nPull.\n\nLower.",
                               [_photo("red"), _photo("blue")])
assert ex["custom"] and ex["id"] == "custom-total-gym-row" and ex["primaryMuscles"] == ["lats"]
assert ex["instructions"] == ["Sit facing in.", "Pull.", "Lower."]  # blank lines dropped
assert len(ex["photos"]) == 2 and all(isinstance(p, str) for p in ex["photos"])  # stored as text (base64)

hold = exercise_data.make_custom("Wall Sit", "quadriceps", None, True, "", [])
assert hold["hold"] and hold["equipment"] == "body only" and hold["photos"] == []

# the hold hook: training can't see the session, exercise_data plugs a function in
training.EXTRA_HOLDS = lambda: {"Wall Sit"}
assert training.kind_of("Wall Sit") == "hold" and training.kind_of("Total Gym Row") == "reps"
# an animated GIF becomes the whole demo (a small animated WebP); its first frame is the still picture
def _gif(frames=6, size=(300, 200), name="move.gif"):
    buf = io.BytesIO()
    imgs = [Image.new("RGB", size, (40 * i, 80, 255 - 40 * i)) for i in range(frames)]
    imgs[0].save(buf, "GIF", save_all=True, append_images=imgs[1:], duration=120, loop=0)
    buf.seek(0)
    buf.name = name
    return buf


g = exercise_data.make_custom("GIF Row", "lats", "machine", False, "", [_gif()])
assert g.get("demo") and len(g["photos"]) == 1, "one GIF: a demo plus one still picture"
exercise_data.st.session_state.clear()
assert exercise_data._custom_media(g).startswith("data:image/webp;base64,"), "big view plays the GIF"
assert exercise_data._custom_media(g, size=96).startswith("data:image/webp;base64,"), "small view uses the still"

# a still GIF (one frame) is just a photo; editing without new pictures keeps the demo; new photos replace it
still = exercise_data.make_custom("Still", None, None, False, "", [_gif(frames=1)])
assert "demo" not in still and len(still["photos"]) == 1
kept = exercise_data.make_custom("GIF Row", "lats", "machine", False, "", g["photos"], keep_demo=g["demo"])
assert kept.get("demo") == g["demo"]
replaced = exercise_data.make_custom("GIF Row", "lats", "machine", False, "", [_photo("red"), _photo("blue")], keep_demo=g["demo"])
assert "demo" not in replaced and len(replaced["photos"]) == 2

# a huge GIF is refused with a clear message instead of filling the person's storage
import os  # noqa: E402
big = io.BytesIO()
noisy = [Image.frombytes("RGB", (360, 360), os.urandom(360 * 360 * 3)) for _ in range(30)]
noisy[0].save(big, "GIF", save_all=True, append_images=noisy[1:], duration=100, loop=0)
big.seek(0)
try:
    exercise_data.make_custom("Huge", None, None, False, "", [big])
    raise AssertionError("a huge GIF should have been refused")
except ValueError as e:
    assert "too big" in str(e)

print("all passed")
