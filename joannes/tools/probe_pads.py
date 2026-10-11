"""JOANNES-MOD, notitie 01 §7: welke toets + pad is vrij voor *generate*?

Draait de echte code van het officiële MAIN OS 1.13 (Unicorn), stock, zonder enige wijziging:

1. De drie pad-afnemers van het OS met elke toets (code 1..31) ingedrukt:
   PadsView (0x4001d180, hergebruikt de opstelling van upstream probe_chord_pads.py),
   PatternAndBankSelectView (0x40020060) en QuickMuteMenuView (0x4002350a).
2. De echte toetsinterruptie en toetsklok (opstelling van upstream test_trig_hold.py) met BACK kort en lang
   ingedrukt: welke KeyEvents het OS maakt, en wat PatternGridView (0x40022382) ermee doet.
3. Dezelfde KeyEvents door MainScreenView::consumeKeyEvent (0x4001c0d2), de vaste vertakking per toets.

    python3 joannes/tools/probe_pads.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import struct
import sys

from unicorn import UC_HOOK_CODE

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emu"))
sys.path.insert(0, str(ROOT / "tools"))

import probe_chord_pads as P        # noqa: E402
import test_trig_hold as H          # noqa: E402

NAMES = {0: "geen", 1: "FUNC", 2: "TRACK", 3: "PATTERN", 4: "RETRIG", 5: "MACHINES", 6: "PUNCH", 7: "GATE",
         8: "LFO", 9: "RECORD", 10: "PLAY", 11: "STOP", 12: "BACK", 13: "SETTINGS", 14: "TEMPO", 15: "PAGE"}
NAMES.update({15 + n: f"TRIG {n}" for n in range(1, 17)})
BACK = 12
PBS_PAD, QM_PAD = 0x40020060, 0x4002350a
MSV_KEY, MSV_TABLE = 0x4001c0d2, 0x4001c100
KEY_CTOR, BASE_KEY, CLOSE_ALL = 0x4007238c, 0x40075f3c, 0x40076afe
OBJ, KEYEV, CTRL = 0x93005000, 0x93006000, 0x93007000
FAIL = []


def check(ok, msg):
    print(("  ok    " if ok else "  FOUT  ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)


class PadRig(P.Rig):
    """PadsView-opstelling van upstream, plus de pad-afnemers van PATTERN en QuickMute op een nep-object."""

    def __init__(self, image):
        super().__init__(image)
        for addr, fn in {0x400cf9a8: lambda a: 0x93105000,           # UIStates
                         0x4006bbb0: self._capture("bank", 2),        # bank kiezen
                         0x4006bb22: lambda a: 0,
                         0x40013904: self._capture("mute", 3)}.items():
            self.uc.hook_add(UC_HOOK_CODE, self._stub(fn), begin=addr, end=addr)

    def other(self, consumer, pad, down):
        self.uc.mem_write(OBJ, bytes(0x100))
        self.calls.clear()
        self.call(P.PAD_CTOR, P.EVENT, pad, int(down), 90, 123, 0)
        return self.call(consumer, OBJ, P.EVENT) & 0xff, self.calls[:]


def pads(image):
    print("1. Pad-afnemers met een toets ingedrukt (T3 indrukken en loslaten)")
    rig = PadRig(image)
    seen = {}
    for key in range(0, 32):
        rig.pressed = {key} if key else set()
        pv = [(rig.event(3, d, 90) & 0xff, rig.calls[:]) for d in (True, False)]
        pbs = rig.other(PBS_PAD, 3, True)
        seen[key] = (pv, pbs)
    base = seen[0]
    special = [k for k in seen if seen[k] != base]
    for k in range(32):
        pv, pbs = seen[k]
        tag = "zoals zonder toets" if seen[k] == base else f"PadsView {pv[0][1]}, PATTERN-afnemer {pbs}"
        print(f"     {NAMES[k]:9s} + T3: {tag}")
    check(base[0][0][1] == [("select", (2,)), ("on", (2, 62, 90, 64, 0, 0xFFFFFFFF, 0xFFFFFFFF))],
          "zonder toets: T3 kiest track 3 en speelt hem")
    check(base[1] == (0, []), "zonder toets: de PATTERN-afnemer laat de pad door")
    check(seen[2][0][0][1] == [("select", (2,))], "TRACK + T3: alleen track kiezen, geen noot")
    check(seen[3][1] == (1, [("bank", (0x93105000, 2))]), "PATTERN + T3: bank C kiezen, pad afgevangen")
    check(seen[4][0][0][1][1][1][-1] == rig.rate, "RETRIG + T3: noot met retrig-snelheid")
    check(set(special) == {2, 3, 4}, f"alleen TRACK, PATTERN en RETRIG veranderen de pad in deze afnemers "
                                    f"(gevonden: {[NAMES[k] for k in special]})")
    check(seen[BACK] == base, "BACK + T3: precies hetzelfde als T3 alleen (BACK wordt door geen pad-afnemer gelezen)")
    rig.pressed = set()
    qm = rig.other(QM_PAD, 3, True)
    check(qm == (1, [("mute", (0x93101000, 2, 1))]),
          "QuickMuteMenuView: elke pad wordt een mute (alleen actief na FUNC, zie §7)")
    check(not rig.bad, "pads: geen geheugentoegang buiten de opstelling")


def key_events(image):
    print("\n2. Echte toetsinterruptie en toetsklok: BACK kort (150 ms) en lang (1500 ms) ingedrukt")
    out = {}
    for name, dur in (("kort", 150), ("lang", 1500)):
        rig = H.Rig(image)
        log = rig.run({10: [(BACK, True)], 10 + dur: [(BACK, False)]}, dur + 200)
        evs = [(t, kind, code, flags) for t, kind, code, flags in log if kind in ("appui", "maintien", "relâché")]
        trigs = [x for x in log if x[1] == "trig"]
        print(f"     {name}: " + ", ".join(f"{t} ms {kind} (vlaggen {flags:#04x})" for t, kind, code, flags in evs))
        check(all(c == BACK for _, _, c, _ in evs) and evs, f"BACK {name}: alleen KeyEvents met code 12")
        check(not trigs and not rig.bad, f"BACK {name}: PatternGridView plaatst of wist geen trig")
        out[name] = [f for *_, f in evs]
    return out


def main_screen(image, flags_by_case):
    print("\n3. MainScreenView::consumeKeyEvent (0x4001c0d2) met dezelfde KeyEvents van BACK")
    d = image
    entry = lambda code: MSV_TABLE + struct.unpack(">h", d[MSV_TABLE - P.BASE + 2 * (code - 1):][:2])[0]
    check(entry(BACK) == 0x4001c1a6, "sprongtabel: BACK (code 12) gaat naar 0x4001c1a6")
    check(entry(1) == 0x4001c5f2 and d[0x4001c600 - P.BASE:][:4] == bytes.fromhex("4aaa00ec"),
          "sprongtabel: FUNC (code 1) test MainScreenView+236 (de QuickMuteMenuView, gemaakt in 0x4001bd48)")
    rig = P.Rig(image)
    hits = []
    for addr, name in ((BASE_KEY, "basis"), (CLOSE_ALL, "alles-sluiten")):
        rig.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, u, n=name: hits.append(n), begin=addr, end=addr)
    rig.uc.hook_add(UC_HOOK_CODE, rig._stub(lambda a: 0), begin=CLOSE_ALL, end=CLOSE_ALL)
    for case, flist in flags_by_case.items():
        for flags in dict.fromkeys(flist):                  # elke soort event één keer
            rig.uc.mem_write(OBJ, bytes(0x200))
            rig.w32(OBJ + 44, CTRL)
            hits.clear()
            rig.call(KEY_CTOR, KEYEV, BACK, flags, 123, 0x7f)
            consumed = rig.call(MSV_KEY, OBJ, KEYEV) & 0xff
            print(f"     BACK {case}, vlaggen {flags:#04x}: afgevangen={consumed}, bereikt {hits}")
            if flags & 0x20:
                check(hits == ["alles-sluiten"], f"BACK lang ({flags:#04x}): alleen 'open menu's sluiten' (0x40076afe)")
            else:
                check(hits == ["basis"] and consumed == 0,
                      f"BACK {case} ({flags:#04x}): niets, het event gaat onaangeroerd verder")
    check(not rig.bad, "MainScreenView: geen geheugentoegang buiten de opstelling")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    a = ap.parse_args()
    image = P.official_image(a.cycles)
    pads(image)
    flags = key_events(image)
    main_screen(image, flags)
    print("\nALLES OK" if not FAIL else f"\n{len(FAIL)} FOUT(EN)")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
