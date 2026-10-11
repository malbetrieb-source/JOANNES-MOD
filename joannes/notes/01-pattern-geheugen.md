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
4. Een vrije knoppencombinatie kiezen voor *generate* (§6).

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
