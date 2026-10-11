# 01 · Het pattern-geheugen van de Model:Cycles

Eerste onderzoek voor de **random generators per track** van de JOANNES-MOD. Doel: weten waar een pattern-track in
het geheugen staat, welk veld wat is, en hoe je er veilig in schrijft.

Bron: desassemblage van het officiële MAIN OS 1.13 (`m68k-linux-gnu-objdump`, ColdFire V4e, basisadres
`0x40000400`), aangevuld met upstream notitie [32 (arpeggiator)](../../notes/32-arpegiateur.md). Alle adressen zijn
virtuele adressen van OS 1.13.

> **Conventie** (zoals upstream): **`[FEIT]`** = gelezen in de code, op de byte nauwkeurig.
> **`[HYP]`** = hypothese, nog te bevestigen in de emulator.

## 1. Waar een track staat

- `[FEIT]` (upstream 32 §4) Een pattern-track bestaat in twee vormen van 722 bytes: in het geheugen (**B**) en in
  het bestand (**A**). De sequencer-bank: `0x406fa040 + pattern × 30710 + track × 722`.
- `[FEIT]` `0x4005b4ec` kopieert **A → B** bij het laden, `0x4005b642` **B → A** bij het opslaan, veld voor veld.
- `[FEIT]` (upstream 32 §10) De interface houdt een **eigen kopie** bij. Bij de arpeggiator las de audiokant de
  sequencer-bank, terwijl het menu in de interface-kopie schreef; de audiokant zag daardoor altijd 0. Les: **niet
  rechtstreeks in de bank schrijven.**

## 2. Indeling van een track (vorm B)

Uit de laad-routine `0x4005b4ec`: een lus van 64 stappen kopieert één 16-bits woord en acht losse bytes per stap.

| Offset in B | Grootte | Inhoud | Bron |
|---|---|---|---|
| +0 | 64 × woord | stapwoord: vlaggen per stap (bit 0 = trig aan, `0x8000` = retrig) | `[FEIT]` bit 0: `0x40017aee`; `0x8000`: upstream 32 |
| +128 | 64 × byte | **velocity** 0…127; −1 = standaardvelocity van de track (setter `0x400166c2`) | `[FEIT]` live-opname: bericht +17 → deze setter (§2b); emulatie |
| +192 | 64 × byte | trig-lengte (setter `0x40016742`) | `[FEIT]` upstream 32 §11 noemt deze setter de lengte |
| +256 | 64 × byte | **micro-timing** −23…+23; de setter krijgt waarde + 64 (setter `0x400167bc`) | `[FEIT]` emulatie; live-opname telt 64 op |
| +320 | 64 × byte | begrensd op 0…127 (setter `0x400168da`) | `[FEIT]` retrig-lengte (upstream 32 §11) |
| +384 | 64 × byte | begrensd op 0…16 (setter `0x40016850`) | `[FEIT]` retrig-snelheid |
| +448 | 64 × byte | 0…127 bovengrens, negatief ongemoeid (setter `0x40016964`) | `[HYP]` retrig-velocitycurve |
| +512 | 4 bytes | +512 vrij voor mods (bits 0–4 arpeggiator); +513 retrig `Len`, +514 `Rte`, +515 heeft eigen accessors (betekenis `[HYP]`, vermoedelijk retrig-velocity) | `[FEIT]` upstream 32 §4; accessors van 513–515 gevonden |
| +516 | 64 × byte | −1 of waarde (setter `0x40016010`); deze setter kijkt **niet** naar de tracklengte | `[FEIT]` gedrag (emulatie); betekenis `[HYP]` trig-conditie |
| +580 | 64 × byte | **noot** 0…127; −1 = standaardnoot van de track (setter `0x40016642`) | `[FEIT]` live-opname: bericht +16 → deze setter (§2b); emulatie |
| +644 | 64 × byte | 0…127, daarbuiten wordt niets geschreven (setter `0x4001653e`) | `[HYP]` betekenis onbekend; generator laat dit veld op de standaard |
| +708 … | losse bytes | track-parameters | `[FEIT]` gekopieerd met grenscontroles |
| +713 | woord | tracklengte, 2…64, anders 16 | `[FEIT]` `0x4005b58c`, gelezen door `0x40016402` |

### 2b. Hoe noot en velocity zijn vastgesteld

`[FEIT]` Live-opname: `0x40007266` roept `0x40012158` aan met (…, track = bericht +8, **noot = bericht +16**,
**velocity = bericht +17**, …, stap = +28, micro = +30). In `0x40012158` gaat het 3e argument (noot) naar de setter
van +580 (`0x400121fc`) en het 4e (velocity) naar die van +128 (`0x4001225a`); de micro-timing gaat met + 64 naar
`0x400167bc`.

`[FEIT]` Nieuwe trig (`0x400169f0`, emulatie): velocity, noot, lengte, +516 en +644 op −1 (standaard van de track),
retrig-lengte 46, retrig-snelheid 9.

Alles hierboven met *emulatie* is gecontroleerd door `joannes/tools/probe_steps.py`, die de echte setters van het
officiële OS 1.13 draait op een nep-track (13 controles, alle groen).

## 3. Veilig schrijven: de setters van het OS

`[FEIT]` Elk veld heeft een eigen setter met dezelfde vorm, `setter(track-object, stap, waarde)`:

1. stap begrenzen op 0…63;
2. controleren dat de stap binnen de tracklengte valt (`0x40016402`);
3. de data-pointer van de track ophalen (`vtable[40]`) en de waarde schrijven;
4. een **wijzigingsmelding** sturen (`vtable[16]`, bericht `0x400ff59c`).

Stap 4 houdt de kopie van de sequencer gelijk aan die van de interface: precies wat bij de arpeggiator misging.
`[FEIT]` `0x400179ce` (een trig plaatsen bij live-opname) gebruikt dezelfde setters en zet bij een nieuwe trig eerst
de standaardwaarden (`0x400169f0`, `0x400164f2`, `0x400165d6`).

**Ontwerpbesluit:** de generator schrijft **uitsluitend via deze OS-setters**, nooit rechtstreeks in de bank. Dan
gedraagt een gegenereerd patroon zich voor het OS exact als een met de hand ingevoerd patroon: dezelfde controles,
dezelfde meldingen, en opslaan via de normale weg.

## 4. Gevolgen voor de generator

- **Projecten blijven compatibel:** de generator schrijft alleen bestaande velden. Een gegenereerd patroon is gewone
  Cycles-data en opent ook op het officiële OS.
- **Ruimte voor instellingen** (genre, locks). `[FEIT]` Bytes 513–515 zijn **niet** vrij: het OS heeft er
  getters en setters voor (513: `0x4001613e`/`0x40016188`, 515: `0x400161d2`/`0x4001621e`); 513 en 514 zijn de retrig-
  instellingen. Wat overblijft:
  - per track: bits 5–7 van byte +512 (de arpeggiator gebruikt 0–4); upstream 42 vond dat te weinig voor zijn doel;
  - per pattern: de kop van 64 bytes (`B+30642`). Het OS leest daar velden 0–28 en 38 en bewaart de rest; het
    akkoordenklavier (upstream 42) neemt 32–35 (handtekening) en 40–63. Vrij lijken 29–31, 36, 37 en 39 `[HYP]`,
    nog na te lopen in de emulator.
  - **Advies voor versie 1: niets opslaan.** De generator-instellingen leven alleen in het werkgeheugen (na
    aanzetten terug naar de standaard). Dan verandert er niets aan wat er wordt opgeslagen, en is botsen met andere
    mods uitgesloten. Toonladder: overnemen van het akkoordenklavier als dat in het pattern staat.
- **Niet automatisch opslaan:** de generator roept nooit de opslag-routine aan.

## 5. Volgende stappen

1. ~~Noot en velocity vastleggen~~ gedaan (§2b).
2. ~~Vrije byte zoeken~~ gedaan (§4): advies versie 1 zonder opslag.
3. Uitzoeken hoe het track-object voor een gegeven track wordt opgehaald (upstream 32: `0x4000cfcc(0x4000f208(…), track)`).
4. ~~Een vrije knoppencombinatie kiezen voor *generate*~~ gedaan (§7): **BACK + pad**, wacht op bevestiging door
   Niels op de machine.
5. De hook in PadsView ontwerpen (§7d) en de generator zelf (genres, kansen per stap).

## 6. Knoppencombinatie: TRK + RETRIG is niet vrij

Voorstel van Niels (11/10/2026): TRK + RETRIG voor *generate*.

- `[FEIT]` Toetscodes voor `0x4007faf4(code)` (= is de toets ingedrukt): FUNC 1, TRK 2, RETRIG 4, MACHINES 5,
  PAGE 15 (upstream 32, 44, 47, 53).
- `[FEIT]` `0x4001d506`, gebeurtenis-afhandeling van het OS zelf: bij **loslaten van RETRIG** wordt byte +112 van
  het interface-object `TRK ingedrukt`; bij **loslaten van TRK** wordt het `RETRIG niet ingedrukt`.
- `[FEIT]` Die byte wordt gelezen in de afhandeling van gespeelde noten met retrig (`0x4001d35a`/`0x4001d360`,
  daarna `0x4001d05e`): ze bepaalt of een retrig na het loslaten doorloopt.
- `[HYP]` Het originele OS gebruikt TRK tijdens RETRIG dus om een **retrig vast te zetten** (latch). Te controleren
  op de machine: noot + RETRIG vasthouden, TRK indrukken, RETRIG loslaten: blijft de roffel doorlopen?
- **Gevolg:** *generate* op TRK + RETRIG zou afgaan op hetzelfde moment dat iemand een roffel vastzet. Niet
  gebruiken. Andere combinatie zoeken en op dezelfde manier controleren.

### 6b. Waar de trackkeuze zit

- `[FEIT]` Huidige track: `0x40012412(project)` geeft veld +4 van de projectdata (via `vtable[40]`); het project
  komt van `0x4000eb90(0x400cf866())`.
- `[FEIT]` Track kiezen: `0x40023c90(track)` begrenst op 0…5, doet niets als het al de huidige track is, en roept
  `0x40013aca` en de eigenlijke setter `0x40013a4a` (schrijft veld +4) aan; daarna wordt het scherm bijgewerkt.
- `[FEIT]` De enige directe aanroeper van `0x40023c90` is `0x4001d36a`, in de afhandeling van de **pads** (dezelfde
  functie die de RETRIG/TRK-vlag van §6 leest). Trackkeuze = TRK + pad; de stap-toetsen (TRIG 1–16) doen dat niet.
- `[FEIT]` `probe_keys.py`: in de patroonweergave plaatst TRK + TRIG *n* gewoon een trig op stap *n*, net als
  zonder TRK. Die opstelling draait niet de pad-afhandeling; voor een uitspraak over vrije combinaties moet de
  probe naar `0x4001d3de` en omgeving worden uitgebreid.
- Gevolg voor *generate*: de natuurlijke plek is ook de pad-afhandeling (welke track = welke pad). Kandidaat om te
  controleren: een combinatie met een pad die het OS nu negeert.

## 7. Vrije combinatie voor *generate*: BACK + pad

Onderzoek van 11/10/2026. Bewijs: `python3 joannes/tools/probe_pads.py --cycles firmware/model-cycles_OS1.13.syx`
(echte OS-code, stock, alle controles groen).

### 7a. Toetscodes

`[FEIT]` De testvolgorde van de fabriekstest (`0x4010a9e0`, codes) naast de namenlijst (`0x4010a870`) en de
handleiding geven de logische codes van `0x4007faf4` en `KeyEvent+12`:

| Code | Toets | Code | Toets | Code | Toets |
|---|---|---|---|---|---|
| 1 | FUNC | 6 | PUNCH | 11 | STOP |
| 2 | TRACK | 7 | GATE | 12 | **BACK** |
| 3 | PATTERN | 8 | LFO | 13 | SETTINGS |
| 4 | RETRIG | 9 | RECORD | 14 | TEMPO |
| 5 | MACHINES | 10 | PLAY | 15 | PAGE |

16…31 zijn TRIG 1…16. (De fabriekstest gebruikt namen van de Model:Samples: WAVE = MACHINES, LOOP = PUNCH,
FLIP = GATE; code 5 = MACHINES klopt met upstream 47.)

### 7b. Wie leest een pad?

`[FEIT]` De enige code die de pad-velden van een PadEvent leest (`0x400740ca`, `0x400740d4`, `0x400740e4`, `0x400740f2`):
PadsView `0x4001d180`, PatternAndBankSelectView `0x40020060`, QuickMuteMenuView `0x4002350a`, BankSelectMenuView en
VolumeControllerView (`0x40024948`, menu), AudioSettingsMenuView (menu) en twee fabriekstests. Alle views worden één
keer gemaakt bij het opstarten (MainScreenView, `0x4001ba7e`…).

`[FEIT]` (probe, deel 1) Elke toets 1…31 ingedrukt + T3:

- TRACK: alleen track kiezen, geen noot; PATTERN: bank kiezen, pad afgevangen; RETRIG: noot met retrig-snelheid;
- FUNC: QuickMuteMenuView maakt van elke pad een mute; die view komt pas in beeld na een FUNC-druk
  (sprongtabel van MainScreenView, code 1 → `0x4001c5f2` test MainScreenView+236 = de QuickMute-view);
- **alle andere toetsen, ook BACK: precies hetzelfde als de pad alleen** (track kiezen en spelen).

`[FEIT]` (forum, Model:Cycles tips) Een TRIG-toets vasthouden + pad = velocity van die stap invoeren. Dat loopt niet
via deze afnemers (`[HYP]` via de live-opname); TRIG + pad is dus bezet.

### 7c. Wat doet de toets zelf?

`[FEIT]` MainScreenView::consumeKeyEvent (`0x4001c0d2`) springt per code via een tabel (`0x4001c100`). Vlaggen van
`KeyEvent+16` (upstream 33): bit 0 appui, 1 FUNC, 2 dubbel, 3 maintien, 4 relâché, 5 lang.

| Toets | Op het hoofdscherm | Bruikbaar? |
|---|---|---|
| MACHINES, LFO, TEMPO | opent het menu bij het indrukken | nee: pads werken daar anders (bv. preset beluisteren) |
| PUNCH | zet punch aan/uit bij het indrukken | nee: hoorbaar |
| GATE | bij loslaten (met FUNC: CLICK-menu) | alleen als we het loslaten onderdrukken |
| SETTINGS | loslaten opent CONFIG; lang vasthouden `0x40039570` | alleen met onderdrukken |
| PAGE | pagina kiezen, vasthouden = FILL | nee: hoorbaar |
| RECORD, PLAY, STOP | transport (basis `0x40075f3c`; met FUNC kopiëren/wissen/plakken) | nee |
| **BACK** | **niets**; alleen na ~0,5 s vasthouden (bit 5) `0x40076afe` = open menu's sluiten | **ja** |

`[FEIT]` (probe, deel 2 en 3) Met de echte toetsinterruptie en toetsklok: BACK kort geeft *appui* (0x01) en
*relâché* (0x10); BACK lang geeft daarna elke ~67 ms *maintien* (0x09) en na ~530 ms één keer 0x29. MainScreenView
laat elk van die events onaangeroerd door (basis-afhandeling, niet afgevangen), behalve 0x29: open menu's sluiten,
wat op het hoofdscherm niets doet. PatternGridView plaatst of wist niets.

`[FEIT]` Code 12 wordt verder alleen gelezen door menu's, pop-ups en vensters (o.a. BankSelectMenuView,
NoteVelocityView, TempoMenuView, SwingMenuView, alle VerticalMenu-afgeleiden, VolumeControllerView/PopupWindow,
DrumSelect): daar betekent BACK "terug". Op het hoofdscherm zonder open menu is BACK dus vrij.

### 7d. Besluit en gevolgen voor de hook

**Voorstel: BACK vasthouden + pad = *generate* voor de track van die pad.** In het originele OS speelt die pad dan
gewoon (de gebruiker merkt niets van BACK); met de mod vangt de hook de pad af: patroon maken, track kiezen, geen
noot.

- Plek: de pad-afhandeling van PadsView. Bij het indrukken `0x4007faf4(12)`: zo ja, *generate* (track = pad − 1) en
  1 teruggeven; anders de stock-afnemer. Het loslaten van die pad gaat naar stock (de nootcel staat op −1, upstream
  probe: dan geen noot-uit).
- Upstream deed dit bij een eerdere versie van het akkoordenklavier met de twee pointers `0x4010025c` en
  `0x401002b0` (thunk −16; alleen de eerste omleiden is niet genoeg, upstream 42 §2). `[FEIT]` Geen enkele tweak in
  `tweaks/model-cycles_OS1.13/` schrijft nu in die pointers, in de thunk `0x4001d3d4` of in `0x4001d180` (scan
  11/10/2026). `check_overlaps.py` controleert het opnieuw als de tweak er is.
- In de vastgezette mute-modus (tweak `latching-mute`) vangt QuickMute de pads eerst af: daar werkt *generate* niet,
  en dat is goed zo.
- BACK + pad in een open menu: BACK sluit eerst het menu (stock), daarna geldt het hoofdscherm. Geen probleem.
- **Op de machine te controleren door Niels** (stock OS): BACK vasthouden en T3 indrukken. Verwacht: T3 klinkt en
  wordt geselecteerd, verder gebeurt er niets. Daarna BACK ~1 s vasthouden op het hoofdscherm: er gebeurt niets.
