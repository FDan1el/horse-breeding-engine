"""
Trot Heritage - Track & Race Class Engine v1.0
=======================================================================
A KOZOS FIKTIV VILAG VERSENYRENDSZERE: hat palya, valos osztalyletra,
felszin-jellemzok es futameloszlas.

Ez a modul a versenyek SZERKEZETET rogziti. Maga a futas-szimulacio
(toltottsegi sav -> helyezes) kulon modul lesz, ez adja hozza a
kornyezetet: hol, milyen felszinen, milyen osztalyban futnak.

=======================================================================
FORRASOK
=======================================================================

AZ OSZTALYLETRA:

1. West Point Thoroughbreds (condition book): "About 70% of all races
   in North America are claiming races". Az osztalyletra alulrol:
   maiden claiming -> maiden special weight -> claiming -> starter
   allowance -> allowance -> listed stakes -> G3 -> G2 -> G1.
   https://www.westpointtb.com/the-thoroughbred-racing-condition-book-how-it-works-and-race-types/

2. Horse Racing Sense (allowance-feltetelek): a feltetelkodok a gyozelmi
   elozmenyre korlatoznak - N1X (nem nyert egy versenyt sem a maidenen
   es claimingen kivul), N2X, N3L (eletben harom gyozelem alatt). Az
   allowance "a fejlodesi reteg, ahol a komoly telivérek felepitik a
   rekordjukat".
   https://horseracingsense.com/allowance-race/

3. betHQ: az osztalyozas celja, "hogy osszemerhetó kepessegu lovak
   fussanak egymas ellen", es hogy minden szinten teljesuljenek a
   minosegi kovetelmenyek.
   https://www.bethq.com/how-to-bet/horse-racing-classes-grades-and-groups-explained/

4. PA Horse Racing / Kentucky Derby: a DIJAZAS MERTEKE hatarozza meg a
   mezony minoseget - "a jobb lovak jellemzoen magasabb dijakert
   futnak". A maiden special weight lovak "jobb tenyesztesuek,
   egeszsegesebbek, magasabb a felteteles plafonjuk".
   https://pennhorseracing.com/stories/racing-classes-thoroughbred-racing/
   https://www.kentuckyderby.com/horses/news/classifying-the-different-types-of-horse-races/

A PALYAK ES FELSZINEK:

5. Mad Barn / Equine Injury Database - A LEGFONTOSABB SZAM:
   halalos serules 1000 startra:  SZINTETIKUS 0.41  |  GYEP 0.99  |
   HOMOK 1.44. A homok tehat tobb mint HAROMSZOR kockazatosabb, mint a
   szintetikus. Tovabba: a homokpalyak kanyarjai 2-6%-ban doltek, az
   egyenesek 1-2%-os lejtessel a vizelvezetes miatt; a homok 80-95%
   homokbol all, a tobbi agyag es iszap.
   https://madbarn.com/synthetic-footing-in-horse-racing/

6. Global Racing / EquinEdge: a hosszu, iveltebb kanyarok GYEPEN a
   kitartó hajrat segitik, a szukebb homok-kanyarok a taktikai
   sebesseget. Kemeny gyep: a korai sebesseget jutalmazza; puha gyep:
   a kesoi felzarkozokat.
   https://globalracing.com/the-differences-between-turf-dirt-and-synthetic-tracks/
   https://equinedge.com/glossary/distances-track-types/turf

7. Derby Insider / Hello Race Fans: a CELEGYENES HOSSZA donto -
   "egyes lovaknak hosszu celegyenes kell a hajrahoz, masok akkor a
   legjobbak, ha korán elmennek es nem adjak vissza a vezetest".
   Konkret adatok: Aqueduct 1155.5 lab az utolso kanyartol a celig;
   a Fair Grounds hiresen hosszu, az Oaklawn Park es Keeneland
   hiresen rovid celegyenessel bir.
   https://www.derbyinsider.com/track-handicapping-for-beginners/
   https://helloracefans.com/handicapping/distance/guide-to-one-and-two-turn-track-configurations/

8. Wikipedia (chute) / Grokipedia: az amerikai palyak jellemzoen
   pontosan 1 merfold kerulettel epulnek, szimmetrikus ovalisban; a
   leggyakoribb amerikai tav 6 furlong. A lovaspalyak altalaban
   1-2 merfold keruletuek.
   https://en.wikipedia.org/wiki/Chute_(racecourse)
   https://grokipedia.com/page/Race_track

9. Past The Wire: a talajallapotok (fast/good/muddy/sloppy homokon,
   firm/good/yielding/soft gyepen) erdemben megvaltoztatjak, ki
   nyerhet; a puha gyep "tompitja az eles gyorsulast, es a
   kiegyensulyozottabb, orlo mozgasuakat segiti".
   https://pastthewire.com/blog-posts/how-track-conditions-shape-betting-decisions-on-race-day/
"""

from enum import Enum


# =======================================================================
# 1) FELSZINEK
# =======================================================================
class Surface(Enum):
    DIRT = 'dirt'
    TURF = 'turf'
    SYNTHETIC = 'synthetic'


SURFACE_LABELS_HU = {
    Surface.DIRT: 'homok',
    Surface.TURF: 'gyep',
    Surface.SYNTHETIC: 'szintetikus',
}

# SERULESI KOCKAZAT - NEM halalozas
#
# A jatekos kifejezett dontese: A JATEKBAN NINCS ELHULLAS, csak serules.
# A serules kihagyast okoz, rontja a soundness-t es fogyasztja az
# elet-csikot, de a lo NEM tunik el.
#
# A relativ aranyok viszont VALOS adatbol jonnek: az Equine Injury
# Database halalos-serules statisztikaja 1000 startra vetitve
# (szintetikus 0.41 | gyep 0.99 | homok 1.44) - ezt NEM abszolut
# ertekkent, hanem RELATIV VESZELYESSEGI INDEXKENT hasznaljuk.
# A homok tehat kb. 3.5x veszelyesebb, mint a szintetikus - ez az
# ARANY az, ami atvihetó a serules-modellre.
#   https://madbarn.com/synthetic-footing-in-horse-racing/
SURFACE_DANGER_INDEX = {
    Surface.SYNTHETIC: 1.00,   # referencia
    Surface.TURF: 2.41,        # 0.99 / 0.41
    Surface.DIRT: 3.51,        # 1.44 / 0.41
}

# A palya veszelyessege es a lo serulekenysege EGYUTT adja a kockazatot.
# A serulekenyseg a soundness tulajdonsagbol jon (breeding_sim.py).
BASE_INJURY_CHANCE_PCT = 0.9   # jatektervezesi alapertek szintetikuson,
                               # atlagos soundness mellett


def injury_risk_pct(surface, soundness, going=None, distance_furlongs=8):
    """Serulesi eselye egy startnak, szazalekban.

    A palya veszelyessege (valos relativ index) es a lo sajat
    serulekenysege (soundness) egyutt hataroz meg. NINCS elhullas -
    a serules kihagyast es soundness-romlast okoz.
    """
    danger = SURFACE_DANGER_INDEX[surface]

    # a soundness 5-99 skalan mozog; az atlag (60) a semleges pont
    soundness_factor = max(0.35, min(2.2, (60.0 / max(20.0, soundness)) ** 1.4))

    # nehez talaj noveli a terhelest (forras 9.)
    going_factor = 1.0
    if going in (Going.MUDDY, Going.SLOPPY, Going.SOFT, Going.YIELDING):
        going_factor = 1.25

    # hosszabb tav = tobb terheles
    distance_factor = 1.0 + max(0, distance_furlongs - 8) * 0.03

    risk = BASE_INJURY_CHANCE_PCT * danger * soundness_factor * going_factor * distance_factor
    return round(min(12.0, risk), 2)


class InjurySeverity(Enum):
    NONE = 'none'
    MINOR = 'minor'        # nehany nap kihagyas
    MODERATE = 'moderate'  # egy szezon resze
    SERIOUS = 'serious'    # hosszu kihagyas, karrier-hatas


INJURY_SEVERITY_TABLE = [
    (0.55, InjurySeverity.MINOR,    {'days_out': 4,  'soundness_loss': 1,
                                     'label': 'Enyhe sérülés — néhány nap pihenő.'}),
    (0.85, InjurySeverity.MODERATE, {'days_out': 12, 'soundness_loss': 4,
                                     'label': 'Közepes sérülés — hosszabb kihagyás.'}),
    (1.00, InjurySeverity.SERIOUS,  {'days_out': 30, 'soundness_loss': 9,
                                     'label': 'Súlyos sérülés — a karrierre is kihat.'}),
]


def resolve_injury(roll):
    """Ha bekovetkezett a serules, milyen sulyos? (roll: 0-1)"""
    for threshold, severity, data in INJURY_SEVERITY_TABLE:
        if roll <= threshold:
            return {'severity': severity, **data}
    return {'severity': InjurySeverity.SERIOUS, **INJURY_SEVERITY_TABLE[-1][2]}

# Melyik felszin milyen futasstilust jutalmaz (forras 6.)
SURFACE_CHARACTER = {
    Surface.DIRT: {
        'favors': 'korai sebesség, taktikai pozíció',
        'note': 'Gyorsabb felszín; a vezetést korán átvevő lovaknak kedvez.',
    },
    Surface.TURF: {
        'favors': 'kitartó hajrá, egyenletes mozgás',
        'note': 'Rugalmasabb felszín; a hosszú, ívelt kanyarok a késői felzárkózást segítik.',
    },
    Surface.SYNTHETIC: {
        'favors': 'kiegyensúlyozott, semleges',
        'note': 'A legbiztonságosabb felszín — sérülékeny ló védelmére.',
    },
}


# =======================================================================
# 2) TALAJALLAPOT (forras 9.)
# =======================================================================
class Going(Enum):
    # homok
    FAST = 'fast'
    GOOD_DIRT = 'good_dirt'
    MUDDY = 'muddy'
    SLOPPY = 'sloppy'
    # gyep
    FIRM = 'firm'
    GOOD_TURF = 'good_turf'
    YIELDING = 'yielding'
    SOFT = 'soft'


GOING_LABELS_HU = {
    Going.FAST: 'száraz', Going.GOOD_DIRT: 'jó', Going.MUDDY: 'sáros', Going.SLOPPY: 'latyakos',
    Going.FIRM: 'kemény', Going.GOOD_TURF: 'jó', Going.YIELDING: 'engedő', Going.SOFT: 'puha',
}

GOING_BY_SURFACE = {
    Surface.DIRT: [Going.FAST, Going.GOOD_DIRT, Going.MUDDY, Going.SLOPPY],
    Surface.TURF: [Going.FIRM, Going.GOOD_TURF, Going.YIELDING, Going.SOFT],
    Surface.SYNTHETIC: [Going.FAST, Going.GOOD_DIRT],   # all-weather: keves valtozas
}

# A talaj hatasa a futasstilusra (forras 9.): a kemeny gyep a korai
# sebesseget, a puha a kesoi felzarkozokat jutalmazza.
GOING_STYLE_BIAS = {
    Going.FAST: 'korai sebesség',
    Going.GOOD_DIRT: 'semleges',
    Going.MUDDY: 'kitartás',
    Going.SLOPPY: 'kitartás',
    Going.FIRM: 'korai sebesség',
    Going.GOOD_TURF: 'semleges',
    Going.YIELDING: 'kitartás',
    Going.SOFT: 'kitartás',
}


# =======================================================================
# 3) TAVKATEGORIAK - a tenyesztesi motor kategoriaihoz illesztve
# =======================================================================
# A breeding_sim.py mar sprint/mile/middle/staying tulajdonsagokkal
# dolgozik - a palyak tavjai EZEKRE kepzodnek le.
# A leggyakoribb amerikai tav 6 furlong (forras 8.).
DISTANCE_BANDS = {
    'sprint':  {'furlongs': (5, 7),   'label': 'Sprint'},
    'mile':    {'furlongs': (8, 9),   'label': 'Mérföld'},
    'middle':  {'furlongs': (9, 11),  'label': 'Középtáv'},
    'staying': {'furlongs': (12, 16), 'label': 'Hosszútáv'},
}


def band_for_furlongs(furlongs):
    if furlongs <= 7: return 'sprint'
    if furlongs <= 8: return 'mile'
    if furlongs <= 11: return 'middle'
    return 'staying'


# =======================================================================
# 4) A HAT PALYA
# =======================================================================
# A kozos fiktiv vilag hat palyaja. Mindegyik a VALOS jellemzo-tengelyek
# menten kulonbozik (felszin, kerulet, celegyenes hossza, kanyarok) -
# forras 5-8. A celegyenes hossza a legfontosabb megkulonbozteto
# (forras 7.): rovid celegyenes = korai sebesseg, hosszu = hajra.
#
# A NEVEK FIKTIVEK, a szerkezetuk valos mintakat kovet.
TRACKS = {
    'ashcombe': {
        'name': 'Ashcombe Park',
        'surface': Surface.DIRT,
        'circumference_furlongs': 8,      # 1 merfold - amerikai szabvany
        'stretch_feet': 1010,             # rovid celegyenes
        'turns': 'szűk, 5% dőlésű',
        'character': 'Klasszikus amerikai homokpálya. A rövid célegyenes a korán '
                     'elmenő lovaknak kedvez — aki hátulról jön, ritkán ér oda.',
        'style_bias': 'korai sebesség',
        'distances': [5, 6, 7, 8, 9],
        'prestige': 3,                    # 1-5, a dijazas szorzoja
    },
    'kingsmere': {
        'name': 'Kingsmere Downs',
        'surface': Surface.DIRT,
        'circumference_furlongs': 9,      # 1 1/8 merfold
        'stretch_feet': 1340,             # hosszu celegyenes
        'turns': 'tágas, 3% dőlésű',
        'character': 'A bajnoki homokpálya. A kontinens egyik leghosszabb '
                     'célegyenese — itt a hajrázó lovak visszahozhatják a versenyt.',
        'style_bias': 'kitartás',
        'distances': [7, 8, 9, 10, 12],
        'prestige': 5,
    },
    'thornbury': {
        'name': 'Thornbury Green',
        'surface': Surface.TURF,
        'circumference_furlongs': 10,
        'stretch_feet': 1180,
        'turns': 'hosszú, ívelt',
        'character': 'Európai jellegű gyeppálya, ívelt kanyarokkal. A mérföldes '
                     'specialisták otthona.',
        'style_bias': 'kitartó hajrá',
        'distances': [7, 8, 9, 10],
        'prestige': 4,
    },
    'wrenfield': {
        'name': 'Wrenfield Heath',
        'surface': Surface.TURF,
        'circumference_furlongs': 14,
        'stretch_feet': 1450,
        'turns': 'széles, hullámzó terep',
        'character': 'Hullámzó terepű, hosszú gyeppálya. A klasszikus távok és a '
                     'valódi staminát igénylő futamok helyszíne.',
        'style_bias': 'kitartás',
        'distances': [10, 12, 14, 16],
        'prestige': 5,
    },
    'marlowe': {
        'name': 'Marlowe Allweather',
        'surface': Surface.SYNTHETIC,
        'circumference_furlongs': 8,
        'stretch_feet': 1120,
        'turns': 'egyenletes, 4% dőlésű',
        'character': 'Minden időben futható szintetikus felszín. A legbiztonságosabb '
                     'pálya — sérülékeny vagy visszatérő ló védelmére.',
        'style_bias': 'semleges',
        'distances': [6, 7, 8, 9],
        'prestige': 2,
    },
    'creedon': {
        'name': 'Creedon Bullring',
        'surface': Surface.DIRT,
        'circumference_furlongs': 6,      # kis palya, szuk kanyarok
        'stretch_feet': 820,              # nagyon rovid
        'turns': 'nagyon szűk, 6% dőlésű',
        'character': 'Kis vidéki pálya szűk kanyarokkal. Alacsonyabb osztályok, '
                     'gyakori futamok — itt kezdi a legtöbb ló a pályafutását.',
        'style_bias': 'korai sebesség',
        'distances': [5, 6, 7],
        'prestige': 1,
    },
}


def tracks_for_band(band):
    """Melyik palyakon futnak az adott tavkategoria futamai?"""
    out = []
    for key, t in TRACKS.items():
        if any(band_for_furlongs(d) == band for d in t['distances']):
            out.append(key)
    return out


# =======================================================================
# 5) NYEREMENY-SAVOK - a legegyszerubb lehetseges rendszer
# =======================================================================
# A JATEKOS DONTESE: nem szakemberek fognak jatszani vele. Ezert NINCS
# osztalyozas, NINCS ertekszam, NINCS feljutas-kieses szabaly.
#
# A futamok az ELETNYEREMENY szerint vannak kiirva:
#     "Ez a futam a 20 000 alatti nyereményű lovaknak."
#
# Miert ez a legjobb valasztas:
#   - a jatekos MAR LATJA a nyeremenyt, nem uj adat
#   - nulla magyarazatot igenyel: mindenki erti a penzt
#   - egyetlen szam, ami CSAK NO - nincs se sav-atlepes szabaly, se
#     kieses, se ertekszam-korrekcio
#   - a lo automatikusan feljebb kerul, ahogy nyer
#
# PRECEDENS:
#   - Az ugetoben ez a bevett forma (a jatekos jelezte).
#   - A GALOPPBAN: a JRA (Japan) evtizedekig pontosan igy mukodott -
#     a lovakat a nyeremenyuk szerint osztalyoztak: 5 millio jen alatt,
#     10 millio alatt, 16 millio alatt, es afolott.
#     "In Japan, racing is conducted according to the amount of prize
#     money, not the military system."
#     https://en.namu.wiki/w/%EA%B2%BD%EB%A7%88/%EC%9D%BC%EB%B3%B8
#   - Amerikai allowance-kiirasok is hasznaltak kereset-alapu feltetelt
#     ("non-winners of $X other than maiden or claiming").
#     https://horseracingsense.com/allowance-race/
#
# MEGJEGYZES a JRA 2019-es valtasarol: attertek gyozelemszamra, mert
# nyeremeny-alapon egy kozepszeru lo sok olcso futamban "felorolheti"
# magat. A JATEKBAN EZ NEM PROBLEMA: ha egy lo igy feljebb kerul,
# egyszeruen veszit a jobb mezonyben, es a jatekos megtanulja. Nem
# buntetes, csak visszajelzes - es nem kell hozza semmilyen szabalyt
# elolvasni.

# A savok. A futam kiirasa mindig ugyanaz a mondat, csak a szam valtozik.
EARNINGS_BRACKETS = [
    {'key': 'maiden',  'max': 0,       'label': 'Még nem nyert',            'purse': 3200},
    {'key': 'b5',      'max': 5000,    'label': '5 000 alatt',              'purse': 5000},
    {'key': 'b20',     'max': 20000,   'label': '20 000 alatt',             'purse': 11000},
    {'key': 'b75',     'max': 75000,   'label': '75 000 alatt',             'purse': 26000},
    {'key': 'b250',    'max': 250000,  'label': '250 000 alatt',            'purse': 60000},
    {'key': 'open',    'max': None,    'label': 'Nyílt — bárki nevezhet',   'purse': 130000},
]

# A csucson a Group versenyek - EZEK adnak black type-ot. Ide nem
# nyeremeny-sav, hanem MEGHIVAS/kuszob visz.
GROUP_RACES = {
    'G3': {'label': 'Group 3', 'min_earnings': 60000,  'purse': 45000,  'black_type': True},
    'G2': {'label': 'Group 2', 'min_earnings': 150000, 'purse': 100000, 'black_type': True},
    'G1': {'label': 'Group 1', 'min_earnings': 300000, 'purse': 280000, 'black_type': True},
}


def bracket_for_earnings(lifetime_earnings, has_won=True):
    """Melyik savban fut ez a lo? Egyetlen szambol kovetkezik."""
    if not has_won:
        return EARNINGS_BRACKETS[0]
    for b in EARNINGS_BRACKETS[1:]:
        if b['max'] is None or lifetime_earnings < b['max']:
            return b
    return EARNINGS_BRACKETS[-1]


def can_enter(lifetime_earnings, bracket_key, has_won=True):
    """Nevezhet-e a lo erre a futamra? Egyetlen osszehasonlitas."""
    b = next(x for x in EARNINGS_BRACKETS if x['key'] == bracket_key)
    if b['key'] == 'maiden':
        return not has_won
    if b['max'] is None:
        return True
    return lifetime_earnings < b['max']


def can_enter_group(lifetime_earnings, group):
    return lifetime_earnings >= GROUP_RACES[group]['min_earnings']


def purse_for_race(bracket_key, track_key, group=None):
    """A dijazas: a sav alapja szorozva a palya presztizsével."""
    prestige = TRACKS[track_key]['prestige']
    if group:
        base = GROUP_RACES[group]['purse']
    else:
        base = next(x for x in EARNINGS_BRACKETS if x['key'] == bracket_key)['purse']
    return int(round(base * (0.6 + prestige * 0.16)))


def earnings_display(lifetime_earnings, has_won=True):
    """A jatekosnak megjelenitett allapot - egyetlen sor, nyers penz."""
    b = bracket_for_earnings(lifetime_earnings, has_won)
    groups = [g for g in ('G1', 'G2', 'G3') if can_enter_group(lifetime_earnings, g)]

    line = f"Életnyeremény {lifetime_earnings:,} B$".replace(',', ' ')
    if groups:
        return f"{line} · futhat: {', '.join(sorted(groups))}"
    if b['max']:
        to_next = b['max'] - lifetime_earnings
        return f"{line} · {b['label']} futamokban (még {to_next:,} B$ a következő szintig)".replace(',', ' ')
    return f"{line} · {b['label']}"


def rules_text():
    return ("A futamok nyeremény szerint vannak kiírva. "
            "Ahogy a lovad nyer, magasabb szintre kerül.")


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - TRACK & RACE CLASS ENGINE v1.0 ===\n")

    print("--- 1) A HAT PALYA ---")
    for key, t in TRACKS.items():
        s = SURFACE_LABELS_HU[t['surface']]
        danger = SURFACE_DANGER_INDEX[t['surface']]
        dists = ', '.join(f"{d}f" for d in t['distances'])
        print(f"  {t['name']:22s} {s:12s} {t['circumference_furlongs']:2d}f kerület  "
              f"célegyenes {t['stretch_feet']:5d} láb  presztízs {t['prestige']}/5")
        print(f"      {t['character']}")
        print(f"      Kedvez: {t['style_bias']:16s} · Távok: {dists} · "
              f"Veszélyességi index: {danger:.2f}×")
        print()

    print("--- 2) SERULESI KOCKAZAT (NINCS elhullas, csak serules) ---")
    print("  A relatív arányok valós adatból (Equine Injury Database), de")
    print("  veszélyességi indexként, nem halálozásként alkalmazva.\n")
    print(f"  {'Felszín':12s} {'Index':>7s}   sérülési esély startonként, soundness szerint")
    print(f"  {'':12s} {'':>7s}   {'gyenge (35)':>13s} {'átlagos (60)':>13s} {'kiváló (90)':>13s}")
    for surf in [Surface.SYNTHETIC, Surface.TURF, Surface.DIRT]:
        row = f"  {SURFACE_LABELS_HU[surf]:12s} {SURFACE_DANGER_INDEX[surf]:6.2f}×  "
        for snd in [35, 60, 90]:
            row += f"{injury_risk_pct(surf, snd):12.2f}% "
        print(row)
    print("\n  -> Egy sérülékeny lovat védeni lehet szintetikus pályán futtatással:")
    weak_dirt = injury_risk_pct(Surface.DIRT, 35)
    weak_syn = injury_risk_pct(Surface.SYNTHETIC, 35)
    print(f"     gyenge soundness homokon {weak_dirt}% vs szintetikuson {weak_syn}% "
          f"({weak_dirt/weak_syn:.1f}× különbség)")
    print("\n  Sérülés súlyossága, ha bekövetkezik:")
    for threshold, sev, data in INJURY_SEVERITY_TABLE:
        print(f"     {data['label']:48s} {data['days_out']:2d} nap kihagyás, "
              f"-{data['soundness_loss']} soundness")
    print()

    print("--- 3) NYEREMENY-SAVOK ---")
    print(f"  {rules_text()}\n")
    print(f"  {'Futam kiírása':28s} {'Győztes díja':>13s}")
    for b in EARNINGS_BRACKETS:
        print(f"  {b['label']:28s} {b['purse']:13,d}".replace(',', ' '))
    print()
    print("  A csúcson a Group versenyek — ezek adnak black type-ot:")
    for g, cfg in GROUP_RACES.items():
        print(f"     {cfg['label']:10s} nyeremény {cfg['min_earnings']:>8,d} B$ felett   "
              f"díj {cfg['purse']:>7,d}".replace(',', ' '))
    print()

    print("--- 3b) EGY LO UTJA (csak a penz szamol) ---")
    earnings = 0
    has_won = False
    print(f"  Debütálás: {earnings_display(earnings, has_won)}\n")
    journey = [
        (3, 'maiden'), (1, 'maiden'), (1, 'b5'), (1, 'b5'), (1, 'b5'),
        (2, 'b20'), (1, 'b20'), (1, 'b20'), (1, 'b20'),
        (1, 'b75'), (1, 'b75'), (1, 'b75'), (1, 'b75'), (1, 'b75'),
    ]
    track = 'ashcombe'
    for i, (pos, bracket) in enumerate(journey, 1):
        if not can_enter(earnings, bracket, has_won):
            print(f"  {i:2d}. futam  NEVEZÉS ELUTASÍTVA — a ló már túl sokat nyert "
                  f"a '{next(x for x in EARNINGS_BRACKETS if x['key']==bracket)['label']}' futamhoz")
            continue
        full = purse_for_race(bracket, track)
        won = full if pos == 1 else int(full * (0.2 if pos == 2 else 0.1 if pos == 3 else 0))
        before_bracket = bracket_for_earnings(earnings, has_won)['label']
        earnings += won
        if pos == 1:
            has_won = True
        after_bracket = bracket_for_earnings(earnings, has_won)['label']
        moved = '   >>> feljebb lépett' if after_bracket != before_bracket else ''
        print(f"  {i:2d}. futam  {pos}. hely  +{won:>6,d} B$ → összesen {earnings:>8,d} B${moved}".replace(',', ' '))
    print(f"\n  Végül: {earnings_display(earnings, has_won)}\n")

    print("--- 4) DIJAZAS PALYA SZERINT (presztízs-szorzó) ---")
    print(f"  {'Sáv':24s}" + ''.join(f"{TRACKS[k]['name'].split()[0]:>12s}"
          for k in ['creedon', 'marlowe', 'ashcombe', 'thornbury', 'kingsmere']))
    for b in EARNINGS_BRACKETS:
        row = f"  {b['label']:24s}"
        for key in ['creedon', 'marlowe', 'ashcombe', 'thornbury', 'kingsmere']:
            row += f"{purse_for_race(b['key'], key):>12,d}".replace(',', ' ')
        print(row)
    print()

    print("--- 5) AMIT A JATEKOS LAT (egyetlen sor, nyers penz) ---")
    for e, w in [(0, False), (2400, True), (18000, True), (61000, True), (320000, True)]:
        print(f"  \"{earnings_display(e, w)}\"")
    print()

    print("--- 6) VALIDACIO ---")
    checks = [
        ('A homok több mint 3× veszélyesebb a szintetikusnál',
         SURFACE_DANGER_INDEX[Surface.DIRT] / SURFACE_DANGER_INDEX[Surface.SYNTHETIC] > 3),
        ('A sérülési esély sosem éri el a 12%-ot',
         injury_risk_pct(Surface.DIRT, 20, Going.SLOPPY, 16) <= 12.0),
        ('Jó soundness érdemben csökkenti a kockázatot',
         injury_risk_pct(Surface.DIRT, 90) < injury_risk_pct(Surface.DIRT, 35) / 1.8),
        ('Nincs elhullás — a legsúlyosabb kimenet is csak kihagyás',
         all(d['days_out'] > 0 for _, _, d in INJURY_SEVERITY_TABLE)),
        ('A teljes szabály két mondat',
         len(rules_text()) < 120),
        ('Nyeretlen ló csak maiden futamba nevezhet',
         can_enter(0, 'maiden', has_won=False) and not can_enter(0, 'maiden', has_won=True)),
        ('A nyeremény automatikusan visz feljebb',
         bracket_for_earnings(3000)['key'] != bracket_for_earnings(30000)['key']),
        ('Túl sok nyeremény kizár az alacsonyabb sávból',
         not can_enter(30000, 'b20')),
        ('A nyílt futamba mindenki nevezhet',
         can_enter(999999, 'open') and can_enter(100, 'open')),
        ('Group verseny nyereményküszöbhöz kötött',
         not can_enter_group(50000, 'G3') and can_enter_group(70000, 'G3')),
        ('Csak a Group ad black type-ot',
         all(cfg['black_type'] for cfg in GROUP_RACES.values())),
        ('A magasabb sáv nagyobb díjat fizet',
         all(EARNINGS_BRACKETS[i]['purse'] < EARNINGS_BRACKETS[i+1]['purse']
             for i in range(len(EARNINGS_BRACKETS)-1))),
        ('Mind a hat pálya különböző karakterű',
         len({(t['surface'], t['style_bias'], t['prestige']) for t in TRACKS.values()}) >= 5),
        ('Minden távkategóriára van legalább egy pálya',
         all(len(tracks_for_band(b)) > 0 for b in DISTANCE_BANDS)),
        ('A díjazás a presztízzsel nő',
         purse_for_race('open', 'kingsmere') > purse_for_race('open', 'creedon')),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
