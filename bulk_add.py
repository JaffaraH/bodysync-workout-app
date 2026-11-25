"""Add many pictures or GIFs at once.

* Exercises: every picture or GIF becomes its own exercise. One card at a time: name it, pick the muscle and
  equipment, then "Save and next" and the next one comes up. "Discard this one" needs a second tap, so it can't
  happen by accident, and "Discard all" asks first.
* Skills: every picture or GIF becomes a step, in file-name order (see skills._steps_from_pictures).

Pictures stay in the person's own storage (their Drive, or this computer); they are never uploaded anywhere else.
The queue lives in st.session_state under "<key>_b..." names, where key is the picker's prefix ("ex", "yc", "pk", "pa"),
so the same flow works the same everywhere "Create your own exercise" does.
"""
import base64
import io
import re
import uuid

import streamlit as st
from PIL import Image

import session_data

TYPES = ["jpg", "jpeg", "png", "webp", "gif"]
MAX_FILES = 20
_GENERIC = {"img", "image", "images", "photo", "pic", "picture", "screenshot", "screen", "shot", "pasted", "untitled",
            "unnamed", "dsc", "pxl", "mvimg", "download", "file", "copy", "at", "pm", "am"}


# --- small pure helpers (tested in tests/test_bulk.py) -------------------------------------------------
def guess_name(filename):
    """A readable name from a file name ('incline_row.gif' -> 'Incline row'), or '' for camera and paste names such as
    IMG_2041.jpg or 'Screenshot 2026-11-25 at 1.54.51 PM.png', so the person types a real one."""
    stem = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", filename or "")
    text = re.sub(r"\s+", " ", re.sub(r"[_\-.]+", " ", stem)).strip()
    words = re.findall(r"[a-z]+|\d+", text.lower())
    if not words or all(w.isdigit() or w in _GENERIC for w in words):
        return ""
    return text[:1].upper() + text[1:]


def natural_key(name):
    """Sort 'step2' before 'step10'."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name or "")]


def prepare(filename, data):
    """One uploaded file as a queue item: its bytes, a small preview and a guessed name. An animated GIF stays animated;
    if it is too big to save, its first picture is used and a note says so. Raises OSError for a file that isn't a picture."""
    import exercise_data

    note, demo = "", None
    try:
        demo = exercise_data._gif_demo(io.BytesIO(data))
    except ValueError:
        note = "This GIF is too big to save, so only its first picture is used."
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if note:  # keep just the first picture
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        data = buf.getvalue()
    if demo:
        preview = "data:image/webp;base64," + demo
    else:
        im.thumbnail((480, 480))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72)
        preview = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"uid": uuid.uuid4().hex[:8], "bytes": data, "name": guess_name(filename), "preview": preview,
            "animated": bool(demo), "note": note}


# --- the exercise flow ---------------------------------------------------------------------------------
_STATE = ("bq", "bsaved", "btotal", "bdisc", "brest", "berr")


def start(key):
    for s in _STATE:
        st.session_state.pop(f"{key}_{s}", None)
    st.session_state[f"{key}_bulk"] = True
    st.session_state[f"{key}_new"] = False
    st.session_state[f"{key}_editing"] = None


def close(key):
    for s in _STATE:
        st.session_state.pop(f"{key}_{s}", None)
    st.session_state[f"{key}_bulk"] = False


def flow(username, key, exercises):
    """Draw the many-at-once flow (called by exercise_picker.create_form while it is open)."""
    ss = st.session_state
    st.markdown("**Add many exercises**")
    q = ss.get(f"{key}_bq")
    if q is None:
        _pick(key)
        return
    if not q:  # the last one was saved or discarded
        saved = ss.get(f"{key}_bsaved", 0)
        close(key)
        if saved:
            st.toast(f"Saved {saved} exercise{'s' if saved != 1 else ''}. Find them under Yours.",
                     icon=":material/check_circle:")
        st.rerun()
    _card(username, key, exercises, q)


def _pick(key):
    n = st.session_state.get(f"{key}_bn", 0)
    files = st.file_uploader("Pictures or GIFs", type=TYPES, accept_multiple_files=True, key=f"{key}_bfiles{n}",
                             label_visibility="collapsed")
    st.caption(f"Pick several pictures or GIFs. Each one becomes its own exercise: you name it and choose the muscle, "
               f"one at a time. Up to {MAX_FILES} at once.")
    err = st.session_state.get(f"{key}_berr")
    if err:
        st.error(err)
    a, b = st.columns(2)
    a.button("Cancel", key=f"{key}_bcancel", width="stretch", on_click=close, args=(key,))
    b.button(f"Continue ({len(files)})" if files else "Continue", type="primary", key=f"{key}_bgo", width="stretch",
             disabled=not files, on_click=_load, args=(key, f"{key}_bfiles{n}"))


def _load(key, upload_key):
    ss = st.session_state
    files = sorted(ss.get(upload_key) or [], key=lambda f: natural_key(f.name))[:MAX_FILES]
    items, skipped = [], 0
    for f in files:
        try:
            items.append(prepare(f.name, f.getvalue()))
        except OSError:
            skipped += 1
    ss.pop(f"{key}_berr", None)
    if not items:
        ss[f"{key}_berr"] = "None of those files could be read as pictures. Try JPG, PNG, WEBP or GIF."
        return
    if skipped:
        ss[f"{key}_berr"] = f"{skipped} file{'s' if skipped != 1 else ''} couldn't be read and {'were' if skipped != 1 else 'was'} skipped."
    ss[f"{key}_bq"], ss[f"{key}_btotal"], ss[f"{key}_bsaved"] = items, len(items), 0
    ss[f"{key}_bn"] = ss.get(f"{key}_bn", 0) + 1  # a fresh, empty uploader next time


def _card(username, key, exercises, q):
    import exercise_picker as ep
    import ui

    ss = st.session_state
    cur = q[0]
    uid = cur["uid"]
    total = ss.get(f"{key}_btotal", len(q))
    st.caption(f"Exercise {total - len(q) + 1} of {total}")
    ui.demo(cur["preview"], max_h="32vh")
    if cur["note"]:
        st.caption(cur["note"])
    muscles = ep._options([e for e in exercises if not e.get("custom")], "primaryMuscles")
    equip = ep._options([e for e in exercises if not e.get("custom")], "equipment")
    ss.setdefault(f"{key}_bnm_{uid}", cur["name"])
    st.text_input("Name", key=f"{key}_bnm_{uid}", max_chars=50, placeholder="e.g. Total Gym incline row")
    c1, c2 = st.columns(2)
    # muscle, equipment and "counted in" stay as you left them, so a run of similar moves is quick
    first = {} if f"{key}_bmus" in ss else {"index": None}
    c1.selectbox("Main muscle", muscles, key=f"{key}_bmus", format_func=ep._label, placeholder="Pick one", **first)
    first = {} if f"{key}_beq" in ss else {"index": equip.index("body only") if "body only" in equip else 0}
    c2.selectbox("Equipment", equip, key=f"{key}_beq", format_func=ep._label, **first)
    first = {} if f"{key}_bkind" in ss else {"default": "Reps"}
    st.segmented_control("Counted in", ["Reps", "Seconds"], key=f"{key}_bkind", **first)
    with st.expander("Add steps (optional)"):
        st.text_area("How to do it (one step per line)", key=f"{key}_bst_{uid}", height=90, label_visibility="collapsed",
                     placeholder="Sit facing the machine...\nPull the handles to your chest...\nLower slowly.")
    err = ss.get(f"{key}_berr")
    if err:
        st.error(err)
    st.button("Save and next" if len(q) > 1 else "Save", type="primary", key=f"{key}_bsave", width="stretch",
              icon=":material/check:", on_click=_save_one, args=(username, key))
    pending = ss.get(f"{key}_bdisc")
    d1, d2 = st.columns(2)
    d1.button("Tap again to discard" if pending else "Discard this one", key=f"{key}_bdiscard", width="stretch",
              type="primary" if pending else "secondary", on_click=_discard, args=(key,))
    if len(q) > 1:
        d2.button(f"Discard all {len(q)}", key=f"{key}_bask", width="stretch", on_click=_ask_all, args=(key,))
    if ss.get(f"{key}_brest"):
        with st.container(border=True):
            st.markdown(f"Discard all {len(q)} pictures that are left? This can't be undone.")
            y, n = st.columns(2)
            y.button("Yes, discard", type="primary", key=f"{key}_byes", width="stretch", on_click=_drop_all, args=(key,))
            n.button("Keep them", key=f"{key}_bkeep", width="stretch", on_click=_keep, args=(key,))


def _save_one(username, key):
    import exercise_data as ed

    ss = st.session_state
    q = ss[f"{key}_bq"]
    cur = q[0]
    ss[f"{key}_bdisc"] = False
    name = (ss.get(f"{key}_bnm_{cur['uid']}") or "").strip()
    if not name:
        ss[f"{key}_berr"] = "Give this exercise a name."
        return
    taken = ed.find_exercise(name)
    if taken:
        ss[f"{key}_berr"] = (f"You already have an exercise called {name}." if taken.get("custom")
                             else f"{name} is already in the library.") + " Use a different name."
        return
    try:
        ex = ed.make_custom(name, ss.get(f"{key}_bmus"), ss.get(f"{key}_beq"), ss.get(f"{key}_bkind") == "Seconds",
                            ss.get(f"{key}_bst_{cur['uid']}") or "", [io.BytesIO(cur["bytes"])])
    except ValueError as e:  # a GIF that is too big
        ss[f"{key}_berr"] = str(e)
        return
    except OSError:
        ss[f"{key}_berr"] = "That picture couldn't be read."
        return
    items = [e for e in ed.custom_list() if e["name"] != name] + [ex]
    session_data.save_settings(username, custom_exercises=items)
    ed.set_custom(items)
    ss.pop("_custom_media", None)  # rebuild its demo from the new picture
    ss.pop(f"{key}_berr", None)
    ss[f"{key}_bsaved"] = ss.get(f"{key}_bsaved", 0) + 1
    q.pop(0)


def _discard(key):
    ss = st.session_state
    ss.pop(f"{key}_berr", None)
    if not ss.get(f"{key}_bdisc"):  # the first tap only asks; the second one discards
        ss[f"{key}_bdisc"] = True
        return
    ss[f"{key}_bdisc"] = False
    ss[f"{key}_bq"].pop(0)


def _ask_all(key):
    st.session_state[f"{key}_brest"] = True
    st.session_state[f"{key}_bdisc"] = False


def _keep(key):
    st.session_state[f"{key}_brest"] = False


def _drop_all(key):
    st.session_state[f"{key}_bq"] = []
    st.session_state[f"{key}_brest"] = False
