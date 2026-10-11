# JOANNES-MOD

Eigen mods voor de **Elektron Model:Cycles (OS 1.13)** van Niels Schilder / De Robotfabriek, gebouwd als fork van
[Modded-Cycles](https://github.com/18nelli18/Modded-Cycles) (MIT, Maxime / 18nelli18).

Alles van de JOANNES-MOD staat in deze map `joannes/`. De rest van de repository blijft gelijk aan upstream, zodat
we nieuwe upstream-versies zonder conflicten kunnen binnenhalen. Onze tweaks volgen dezelfde regels als upstream
(zie `../AGENTS.md`).

## Functies

| Functie | Status |
|---|---|
| Terug naar origineel (officiële OS ongewijzigd terugsturen) | bestaat al in de flasher van upstream (tab *Official firmware*); wordt bewaakt en prominenter gemaakt |
| Random generators per track (JOANNES-stijl) | onderzoek: pattern-geheugen ([notitie 01](notes/01-pattern-geheugen.md)) |
| 909-machine (gesynthetiseerd) | gepland, fase 3 |
| Rave-stab engine | gepland, fase 3 |
| Master-bus (compressor, EQ, widener) | bewust buiten scope |

## Vaste regels

- Alleen het MAIN OS (sectie 3) wordt aangepast; bootloader en updater blijven die van Elektron, zodat het
  herstelmenu (FUNC + aanzetten, TRIG 4, via MIDI IN) altijd werkt.
- Geen enkele JOANNES-tweak raakt de update-routes van het OS aan (Transfer-protocol, SysEx-ontvangst, verificatie),
  zodat terugzetten naar het officiële OS altijd via USB kan.
- Elke functie is een losse tweak, eerst bewezen in de emulator, daarna getest door Niels op zijn eigen Model:Cycles.
- Projectformaat blijft ongewijzigd.
- Nooit firmware van Elektron in de repository (`firmware/` is uitgesloten via `.gitignore`).

## Installeren moet simpel zijn

Vaste regel (Niels, 11/10/2026): de bestaande manieren om mods te installeren zijn te ingewikkeld. De JOANNES-MOD
installeer je zo:

- één webpagina, die je Model:Cycles via USB zelf herkent;
- twee knoppen: **JOANNES-MOD installeren** en **Terug naar origineel**; geen lijst met vinkjes;
- het officiële OS-bestand hoef je maar één keer te kiezen: de pagina onthoudt het in je browser, dus een update is
  daarna één klik;
- de snelle USB-route (geen menu op de Cycles nodig; alleen bevestigen op het scherm);
- alle uitleg in gewone taal, zonder technische termen.

## Documenten

- [Ontwerp v0.1 (PDF)](docs/JOANNES-MOD%20ontwerp%20v0.1.pdf)
- [Notitie 01: pattern-geheugen](notes/01-pattern-geheugen.md), bewijs: `python3 joannes/tools/probe_steps.py --cycles firmware/model-cycles_OS1.13.syx`
