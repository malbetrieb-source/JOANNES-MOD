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
| +128 | 64 × byte | veld met standaardwaarde −1 (setter `0x400166c2`) | `[HYP]` noot of velocity, −1 = standaard van de track |
| +192 | 64 × byte | trig-lengte (setter `0x40016742`) | `[FEIT]` upstream 32 §11 noemt deze setter de lengte |
| +256 | 64 × byte | begrensd op −23…+23 (setter `0x400167bc`) | `[HYP]` micro-timing (Elektron: ±23) |
| +320 | 64 × byte | begrensd op 0…127 (setter `0x400168da`) | `[FEIT]` retrig-lengte (upstream 32 §11) |
| +384 | 64 × byte | begrensd op 0…16 (setter `0x40016850`) | `[FEIT]` retrig-snelheid |
| +448 | 64 × byte | begrensd op 0…127 (setter `0x40016964`) | `[HYP]` retrig-velocitycurve |
| +512 | 4 bytes | track-instellingen; +512 = arpeggiator, +514 = `Rte` | `[FEIT]` upstream 32 §4 |
| +516 | 64 × byte | waarde −1 of 63 (setter `0x40016010`) | `[HYP]` trig-conditie |
| +580 | 64 × byte | standaardwaarde −1 (setter `0x40016642`) | `[HYP]` noot of velocity |
| +644 | 64 × byte | begrensd op 0…127 (setter `0x4001653e`, ook `0x400165d6`) | `[HYP]` noot of velocity |
| +708 … | losse bytes | track-parameters | `[FEIT]` gekopieerd met grenscontroles |
| +713 | woord | tracklengte, 2…64, anders 16 | `[FEIT]` `0x4005b58c`, gelezen door `0x40016402` |

De drie kandidaten voor noot en velocity (+128, +580, +644) moeten in de emulator worden vastgesteld: een trig
schrijven met een bekende noot en velocity en kijken welke bytes veranderen.

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
- **Ruimte voor instellingen** (genre, locks): byte +512 is bezet door de arpeggiator. Nog te zoeken: een andere
  byte die wel wordt opgeslagen maar niet gebruikt. Bytes 513 en 515 (gekopieerd in `0x4005b55a…`) zijn kandidaten
  `[HYP]`.
- **Niet automatisch opslaan:** de generator roept nooit de opslag-routine aan.

## 5. Volgende stappen

1. Emulatietest: via `0x400179ce` en de losse setters een trig met bekende waarden schrijven, de 722 bytes vóór en
   na vergelijken, en zo de drie `[HYP]`-velden vastleggen.
2. Nagaan welke van de bytes 513 en 515 vrij zijn (welke code ze leest).
3. Uitzoeken hoe het track-object voor een gegeven track wordt opgehaald (upstream 32: `0x4000cfcc(0x4000f208(…), track)`).
4. Een vrije knoppencombinatie kiezen voor *generate*.
