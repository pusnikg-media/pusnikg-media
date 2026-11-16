"""Clipfabrik-Regression: Layouts rendern, Bild/Ton laufen synchron, und auf bekanntem ffmpeg-Build sind die Hashes unveraendert.
Skript: tests/clip_regression.py (save/compare fuer Vorher/Nachher bei Aenderungen an clipfabrik.py)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import clip_regression as cr


def test_layout_hashes_and_sync():
    m = cr.measure()
    assert not cr.structural_problems(m), cr.structural_problems(m)
    gold = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "clip_hashes.json")))
    key = m["_ffmpeg"]
    if key not in gold:  # anderer ffmpeg-Build (z. B. Runner): Struktur gepruefte, Hashes nicht vergleichbar
        print("kein Golden fuer", key); return
    assert not cr.diff(gold[key], m), cr.diff(gold[key], m)
