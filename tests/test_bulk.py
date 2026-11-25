"""Adding many pictures at once: names from file names, order, the queue, and the two-step discard.   python tests/test_bulk.py"""
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

import bulk_add  # noqa: E402


def test_names_come_from_file_names_but_not_from_camera_names():
    assert bulk_add.guess_name("incline_row.gif") == "Incline row"
    assert bulk_add.guess_name("step-1.jpg") == "Step 1"
    assert bulk_add.guess_name("Total Gym Squat.PNG") == "Total Gym Squat"
    for junk in ("IMG_2041.jpg", "image.png", "Screenshot 2026-11-25 at 1.54.51 PM.png", "pasted image.png", "DSC00012.JPG", ""):
        assert bulk_add.guess_name(junk) == "", junk


def test_natural_order_puts_step_2_before_step_10():
    names = ["step10.png", "step2.png", "step1.png"]
    assert sorted(names, key=bulk_add.natural_key) == ["step1.png", "step2.png", "step10.png"]


def _png(color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color).save(buf, "PNG")
    return buf.getvalue()


def _gif(frames=6):
    buf = io.BytesIO()
    imgs = [Image.new("RGB", (300, 200), (40 * i, 80, 255 - 40 * i)) for i in range(frames)]
    imgs[0].save(buf, "GIF", save_all=True, append_images=imgs[1:], duration=120, loop=0)
    return buf.getvalue()


def test_prepare_makes_a_queue_item():
    still = bulk_add.prepare("row.png", _png())
    assert still["name"] == "Row" and not still["animated"] and still["preview"].startswith("data:image/jpeg;base64,")
    moving = bulk_add.prepare("curl.gif", _gif())
    assert moving["animated"] and moving["preview"].startswith("data:image/webp;base64,")
    assert still["uid"] != moving["uid"]
    try:
        bulk_add.prepare("notes.png", b"this is not a picture")
        raise AssertionError("a non-picture should be refused")
    except OSError:
        pass


def test_a_huge_gif_falls_back_to_its_first_picture():
    big = io.BytesIO()
    noisy = [Image.frombytes("RGB", (360, 360), os.urandom(360 * 360 * 3)) for _ in range(30)]
    noisy[0].save(big, "GIF", save_all=True, append_images=noisy[1:], duration=100, loop=0)
    item = bulk_add.prepare("huge.gif", big.getvalue())
    assert not item["animated"] and "too big" in item["note"]
    Image.open(io.BytesIO(item["bytes"])).verify()  # what gets saved is a normal picture


def test_discard_needs_two_taps_and_discard_all_asks_first():
    ss = bulk_add.st.session_state
    ss.clear()
    key = "t"
    ss[f"{key}_bq"] = [{"uid": str(i)} for i in range(3)]
    bulk_add._discard(key)
    assert len(ss[f"{key}_bq"]) == 3 and ss[f"{key}_bdisc"], "the first tap only asks"
    bulk_add._discard(key)
    assert len(ss[f"{key}_bq"]) == 2 and not ss[f"{key}_bdisc"], "the second tap discards one"

    bulk_add._ask_all(key)
    assert ss[f"{key}_brest"] and len(ss[f"{key}_bq"]) == 2, "asking to discard all removes nothing yet"
    bulk_add._keep(key)
    assert not ss[f"{key}_brest"] and len(ss[f"{key}_bq"]) == 2
    bulk_add._ask_all(key)
    bulk_add._drop_all(key)
    assert ss[f"{key}_bq"] == [] and not ss[f"{key}_brest"]

    bulk_add.start("u")
    assert ss["u_bulk"] and "u_bq" not in ss, "starting clears an old queue"
    ss["u_bq"] = [{"uid": "x"}]
    bulk_add.close("u")
    assert not ss["u_bulk"] and "u_bq" not in ss, "closing (the Back button) leaves nothing behind"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("all passed")
