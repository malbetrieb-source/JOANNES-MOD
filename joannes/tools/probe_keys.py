"""JOANNES-MOD, notitie 01 §6: wat doet het originele OS met TRK + TRIG n (n = 1..16) in de patroonweergave?

Hergebruikt de testopstelling van upstream test_trig_hold.py (notitie 33): de echte toetsinterruptie, de echte
toetsklok en de echte PatternGridView::consumeKeyEvent (0x40022382) van het officiële MAIN OS 1.13. Per combinatie
noteren we de uitgevoerde codeblokken in het OS, de getroffen trigs en wat er naar de boîte aux lettres gaat.

    python3 joannes/tools/probe_keys.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import sys

from unicorn import UC_HOOK_BLOCK

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emu"))
sys.path.insert(0, str(ROOT / "tools"))

import test_sdvintage as T          # noqa: E402
import test_trig_hold as H          # noqa: E402

TRK, RETRIG, FUNC = 2, 4, 1


class LiveBase(H.Rig):
    """Zoals upstream, maar de basis-afhandeling van toetsen (0x40075f3c) draait echt in plaats van een stub:
    daar landen de algemene combinaties. Onbekende aanroepen buiten het geheugen worden genoteerd."""

    def __init__(self, img):
        from unicorn import Uc
        orig = Uc.hook_add

        def hook_add(uc, htype, cb, user_data=None, begin=1, end=0, *a):
            if begin == 0x40075f3c and end == 0x40075f3c:
                return None
            return orig(uc, htype, cb, user_data, begin, end, *a)
        Uc.hook_add = hook_add
        try:
            super().__init__(img)
        finally:
            Uc.hook_add = orig


def trace(img, events, until, live=False):
    """Draai de rig; rend (log, set van uitgevoerde blokadressen tijdens de toets-afhandeling)."""
    rig = LiveBase(img) if live else H.Rig(img)
    blocks = set()
    on = {"v": False}
    orig_call = rig.call

    def call(fn, *args):
        if fn == H.GRID_KEY:
            on["v"] = True
            try:
                return orig_call(fn, *args)
            finally:
                on["v"] = False
        return orig_call(fn, *args)

    rig.call = call
    rig.uc.hook_add(UC_HOOK_BLOCK, lambda uc, a, s, d: on["v"] and blocks.add(a), begin=0x40000400, end=0x40100000)
    log = rig.run(events, until)
    return rig, log, blocks


def combo(img, mod, n, dur=120, live=False):
    """mod ingedrukt, dan TRIG n kort, dan mod los."""
    code = 15 + n
    ev = {0: [(mod, True)], 40: [(code, True)], 40 + dur: [(code, False)], 80 + dur: [(mod, False)]}
    return trace(img, ev, dur + 400, live)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--live", action="store_true", help="basis-afhandeling 0x40075f3c echt laten draaien")
    a = ap.parse_args()
    img = T.main_os_from_syx(a.cycles)
    live = "--live" in sys.argv
    _, _, base = trace(img, {0: [(TRK, True)], 200: [(TRK, False)]}, 500, live)
    print(f"Alleen TRK indrukken en loslaten: {len(base)} codeblokken in de toets-afhandeling\n")
    rows = []
    for n in range(1, 17):
        rig, log, blocks = combo(img, TRK, n, live=live)
        if rig.bad:
            print(f"   (buiten geheugen: {[hex(x) for x in rig.bad[:3]]})")
        extra = sorted(blocks - base)
        trigs = [x for x in log if x[1] == "trig"]
        rows.append((n, len(extra), extra, trigs))
        print(f"TRK + TRIG {n:2d}: {len(extra):3d} extra blokken, trig-wijzigingen {trigs}")
    sig = {}
    for n, k, extra, _ in rows:
        sig.setdefault(tuple(extra), []).append(n)
    print("\nGroepen TRIG-toetsen met precies hetzelfde codepad onder TRK:")
    for path, ns in sig.items():
        print(f"  TRIG {ns}: {len(path)} extra blokken" + (f", o.a. {[hex(x) for x in path[:6]]}" if path else ""))


if __name__ == "__main__":
    main()
