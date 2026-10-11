"""JOANNES-MOD, notitie 01: welke byte van een pattern-track schrijft elke stap-setter van het OS?

Draait de echte functies van het officiële MAIN OS 1.13 (Unicorn), op een nep-track-object zoals upstream
test_arp.py: vtable[40] geeft de 722 bytes van de track terug, vtable[16] is de wijzigingsmelding (genoteerd).

    python3 joannes/tools/probe_steps.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import struct
import sys

from unicorn import UC_HOOK_CODE
from unicorn import m68k_const as mk

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emu"))
sys.path.insert(0, str(ROOT / "tools"))

import test_sdvintage as T          # noqa: E402
import test_sdvintage_7th as t7     # noqa: E402

OBJ = 0x93400000
FIELDS = {0: "stapwoord", 128: "+128", 192: "+192", 256: "+256", 320: "+320", 384: "+384", 448: "+448",
          516: "+516", 580: "+580", 644: "+644"}
FAIL = []


def check(ok, msg):
    print(("  ok    " if ok else "  FOUT  ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)


class Emu(t7.UI):
    def __init__(self, img):
        super().__init__(img)
        self.uc.reg_write(mk.UC_M68K_REG_SR, 0x2700)
        self.notes = 0
        self.vt, self.f10, self.f4, self.fx, self.data = OBJ + 0x100, OBJ + 0x200, OBJ + 0x210, OBJ + 0x220, OBJ + 0x1000
        self.w32(OBJ, self.vt)
        for slot in range(0, 0x100, 4):               # elke onbekende methode: rts met d0 = 0
            self.w32(self.vt + slot, self.fx)
        self.w32(self.vt + 40, self.f10)
        self.w32(self.vt + 16, self.f4)
        self.uc.mem_write(self.f10, b"\x20\x3c" + struct.pack(">I", self.data) + b"\x4e\x75")   # move.l #data,d0 ; rts
        self.uc.mem_write(self.f4, b"\x4e\x75")
        self.uc.mem_write(self.fx, b"\x70\x00\x4e\x75")                                        # moveq #0,d0 ; rts
        self.uc.hook_add(UC_HOOK_CODE, self._notify, begin=self.f4, end=self.f4)
        self.methods = []
        self.uc.hook_add(UC_HOOK_CODE, self._other, begin=self.fx, end=self.fx)

    def _notify(self, uc, addr, size, ud):
        self.notes += 1

    def _other(self, uc, addr, size, ud):
        self.methods.append(addr)

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))

    def reset(self, length=64, fill=0):
        buf = bytearray([fill]) * 722
        struct.pack_into(">H", buf, 713, length)
        self.uc.mem_write(self.data, bytes(buf))
        self.notes = 0

    def track(self):
        return bytes(self.uc.mem_read(self.data, 722))


def diff(a, b):
    """Gewijzigde bytes als lijst van (veldnaam, stap, oud, nieuw)."""
    out = []
    for i in range(722):
        if a[i] != b[i]:
            if i < 128:
                out.append(("stapwoord", i // 2, a[i], b[i]))
            else:
                base = max(k for k in FIELDS if k <= i)
                step = i - base
                out.append((FIELDS[base] if step < 64 else f"+{i}", step if step < 64 else None, a[i], b[i]))
    return out


SETTERS = [
    (0x400166c2, "+128-setter"), (0x40016742, "lengte"), (0x400167bc, "micro-timing?"),
    (0x400168da, "retrig-lengte"), (0x40016850, "retrig-snelheid"), (0x40016964, "+448-setter"),
    (0x40016010, "+516-setter"), (0x40016642, "+580-setter"), (0x4001653e, "+644-setter"),
]


def setter_tests(e):
    print("\n1. Elke setter(track, stap 5, waarde): welke byte, welke begrenzing, wordt er gemeld?")
    for fn, name in SETTERS:
        for val in (42, 7, -40, 200):
            e.reset()
            before = e.track()
            e.call(fn, OBJ, 5, val)
            d = diff(before, e.track())
            print(f"     0x{fn:08x} {name:16s} waarde {val:5d} -> {[(f, s, n if n < 128 else n - 256) for f, s, _, n in d]}"
                  f"  meldingen {e.notes}")
        e.reset(length=4)
        before = e.track()
        e.call(fn, OBJ, 5, 42)
        if fn == 0x40016010:        # +516: deze setter kijkt niet naar de tracklengte (gedrag van het OS zelf)
            check(e.track() != before, f"{name}: schrijft ook buiten de tracklengte (zoals het OS doet)")
        else:
            check(e.track() == before, f"{name}: stap 5 buiten tracklengte 4 schrijft niets")


def one(e, fn, val, off, step=5):
    e.reset()
    e.call(fn, OBJ, step, val)
    v = e.track()[off + step]
    return v - 256 if v > 127 else v


def semantic_tests(e):
    print("\n3. Betekenis (bron: live-opname 0x40007266 -> 0x40012158: bericht +16 noot, +17 velocity)")
    check([one(e, 0x40016642, v, 580) for v in (0, 60, 127, 128, -5)] == [0, 60, 127, -1, -1],
          "noot (+580, setter 0x40016642): 0..127, daarbuiten -1 = standaardnoot van de track")
    check([one(e, 0x400166c2, v, 128) for v in (1, 100, 127, 128)] == [1, 100, 127, -1],
          "velocity (+128, setter 0x400166c2): 0..127, daarbuiten -1 = standaardvelocity van de track")
    check([one(e, 0x400167bc, v, 256) for v in (64, 65, 87, 41, 100, 0)] == [0, 1, 23, -23, 23, -23],
          "micro-timing (+256, setter 0x400167bc): waarde - 64, begrensd op -23..+23")
    check(one(e, 0x40016850, 9, 384) == 9 and one(e, 0x40016850, 30, 384) == 16,
          "retrig-snelheid (+384): 0..16")


def default_tests(e):
    print("\n2. Nieuwe trig (0x400169f0, 0x400164f2, 0x400165d6 met (track, stap)): welke standaardwaarden?")
    for fn in (0x400169f0, 0x400164f2, 0x400165d6):
        e.reset()
        before = e.track()
        e.call(fn, OBJ, 9)
        d = diff(before, e.track())
        print(f"     0x{fn:08x} -> {[(f, s, n) for f, s, _, n in d]}  meldingen {e.notes}  onbekend geheugen {e.bad[:3]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    a = ap.parse_args()
    img = T.main_os_from_syx(a.cycles)
    e = Emu(img)
    setter_tests(e)
    default_tests(e)
    semantic_tests(e)
    print("\nALLES OK" if not FAIL else f"\n{len(FAIL)} FOUT(EN)")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
