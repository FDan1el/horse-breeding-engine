"""
Breeder Tycoon - Farm & Infrastructure Engine v1.0
=======================================================================
A PENZ-EGETESI RETEG: epuletek, felujitas, terulet, ferohely-bovites.

A jatekos a NAGYBATYJATOL orokol egy leromlott allapotu vidéki farmot.
Minden epulet felujithato vagy bovitheto - ez adja a hosszu tavu
penznyelot, es kozben MECHANIKAI ELONYT is ad, nem csak diszit.

ALAPELV: minden epuletnek legyen VALODI hatasa. Ha csak kozmetika,
akkor az a monetizacios retegbe tartozik (lasd MONETIZATION jelolés),
nem a jatekmenet-gazdasagba.

=======================================================================
KONZISZTENCIA A SZEZON-SZIMULATORRAL
=======================================================================
A kezdo 12 istallohely EGYBEESIK a season.html-ben hasznalt ertekkel -
a korabbi gazdasagi merések tehat ervenyben maradnak. A teljes
felujitas 20 helyre visz, ami a novekedes fo penznyeloje.
"""

import random
from enum import Enum

random.seed(42)


# =======================================================================
# 1) EPULET-ALLAPOTOK
# =======================================================================
class Condition(Enum):
    DERELICT = 'derelict'      # leromlott - orokolt allapot
    BASIC = 'basic'            # felujitva, alapszinten
    GOOD = 'good'
    EXCELLENT = 'excellent'


CONDITION_LABELS = {
    Condition.DERELICT:  'Leromlott',
    Condition.BASIC:     'Felújított',
    Condition.GOOD:      'Jó állapotú',
    Condition.EXCELLENT: 'Kiváló',
}

CONDITION_ORDER = [Condition.DERELICT, Condition.BASIC, Condition.GOOD, Condition.EXCELLENT]


# =======================================================================
# 2) ISTALLO - FEROHELY-PROGRESSZIO
# =======================================================================
# A JATEKOS DONTESE: 12 hely kezdesnek, felujitassal 20-ig, kettesevel.
# Azon tul CSAK UJ EPULET ad tovabbi helyet.
STABLE_STEPS = [
    # (ferohely, koltseg, cimke)
    (12, 0,       'Örökölt állapot'),
    (14, 24000,   'Első felújítás'),
    (16, 45000,   'Bővítés'),
    (18, 78000,   'Bővítés'),
    (20, 125000,  'Teljes felújítás — az épület maximuma'),
]

NEW_STABLE_COST = 185000
NEW_STABLE_CAPACITY = 8


def stable_capacity(upgrade_level, extra_stables=0):
    """Az istallo ferohelye. upgrade_level: 0-4 (a STABLE_STEPS indexe)."""
    level = max(0, min(len(STABLE_STEPS) - 1, upgrade_level))
    return STABLE_STEPS[level][0] + extra_stables * NEW_STABLE_CAPACITY


def next_stable_upgrade(upgrade_level, extra_stables=0):
    """Mi a kovetkezo bovitesi lepes es mibe kerul?"""
    if upgrade_level < len(STABLE_STEPS) - 1:
        cap, cost, label = STABLE_STEPS[upgrade_level + 1]
        return {'type': 'upgrade', 'new_capacity': cap + extra_stables * NEW_STABLE_CAPACITY,
                'cost': cost, 'label': label}
    return {'type': 'new_building',
            'new_capacity': stable_capacity(upgrade_level, extra_stables) + NEW_STABLE_CAPACITY,
            'cost': NEW_STABLE_COST,
            'label': f'Új istálló (+{NEW_STABLE_CAPACITY} hely)'}


# =======================================================================
# 3) A FOEPULET - HAROM SZARNY
# =======================================================================
# A kozepso (lakoresz) rendben van, a masik ketto felujitando.
# Mindketto VALODI mechanikai elonyt ad, nem csak diszit.
MANOR_WINGS = {
    'central': {
        'name': 'Középső szárny (lakórész)',
        'starting_condition': Condition.GOOD,
        'renovation_cost': None,          # nem igenyel felujitast
        'effect': 'A birtok lakórésze. Nem igényel felújítást.',
        'mechanical': None,
    },
    'west': {
        'name': 'Nyugati szárny (iroda)',
        'starting_condition': Condition.DERELICT,
        'renovation_cost': 42000,
        'effect': 'Egyszerre két aukciós katalógust követhetsz, és korábban '
                  'látod a tételeket.',
        'mechanical': 'catalogue_slots',
    },
    'east': {
        'name': 'Keleti szárny (vendégszárny)',
        'starting_condition': Condition.DERELICT,
        'renovation_cost': 58000,
        'effect': 'Vevők látogathatják a farmot — az itt eladott lovak '
                  'magasabb árat érnek el.',
        'mechanical': 'sale_price_bonus',
    },
}

EAST_WING_SALE_BONUS = 0.08     # +8% eladasi ar


# =======================================================================
# 4) EGYEB EPULETEK
# =======================================================================
# MINDEGYIKNEK valodi hatasa van. Ami csak diszit, az a monetizacios
# retegbe tartozik (lasd 7. blokk).
BUILDINGS = {
    'round_pen': {
        'name': 'Körkarám',
        'cost': 0,                        # orokolt
        'inherited': True,
        'upkeep': 200,
        'effect': 'Alapszintű munka a fiatal lovakkal.',
        'mechanical': {'young_horse_dev': 0.02},
    },
    'feed_store': {
        'name': 'Takarmánytároló',
        'cost': 0,                        # orokolt, de bovitendo
        'inherited': True,
        'upkeep': 300,
        'effect': 'Meghatározza, hány lovat tudsz a választott minőségen etetni.',
        'mechanical': {'feed_capacity': 12},
    },
    'walker': {
        'name': 'Jártatógép',
        'cost': 34000,
        'inherited': False,
        'upkeep': 900,
        'effect': 'A frissesség gyorsabban töltődik vissza — sűrűbben futtathatsz.',
        'mechanical': {'freshness_rate': 1.28},
    },
    'training_track': {
        'name': 'Tréningpálya',
        'cost': 120000,
        'inherited': False,
        'upkeep': 2600,
        'effect': 'A tréner hatékonyabban dolgozik a lovaiddal.',
        'mechanical': {'trainer_effectiveness': 1.10},
    },
    'vet_room': {
        'name': 'Állatorvosi rendelő',
        'cost': 68000,
        'inherited': False,
        'upkeep': 1500,
        'effect': 'A sérülések enyhébbek, a lábadozás rövidebb.',
        'mechanical': {'injury_severity': 0.75, 'recovery_speed': 1.35},
    },
    'foaling_barn': {
        'name': 'Ellető istálló',
        'cost': 52000,
        'inherited': False,
        'upkeep': 1100,
        'effect': 'Az anyakanca-gondoskodás jobban érvényesül a csikón.',
        'mechanical': {'maternal_bonus': 1.20},
    },
}

# A takarmanytarolo bovitese: ha tul sok lo van, romlik az etetes minosege
FEED_STORE_STEPS = [
    (12, 0,      'Örökölt'),
    (18, 30000,  'Bővítés'),
    (28, 66000,  'Nagy tároló'),
    (40, 124000, 'Ipari tároló'),
]


def feed_capacity(level):
    level = max(0, min(len(FEED_STORE_STEPS) - 1, level))
    return FEED_STORE_STEPS[level][0]


def feed_quality_penalty(herd_size, feed_level):
    """Ha a letszam meghaladja a tarolo kapacitasat, romlik az etetes.

    Ez teszi KOTELEZOVE a takarmanytarolo fejleszteset a novekedessel -
    nem lehet csak istallot bovitgetni.
    """
    cap = feed_capacity(feed_level)
    if herd_size <= cap:
        return {'penalty': 0.0, 'ok': True, 'note': None}
    over = herd_size - cap
    penalty = min(0.45, over * 0.06)
    return {'penalty': round(penalty, 3), 'ok': False,
            'note': (f'{over} lóval túllépted a takarmánytároló kapacitását — '
                     f'az etetés hatékonysága {penalty*100:.0f}%-kal csökken.')}


# =======================================================================
# 5) TERULET - KARAM ES LEGELO
# =======================================================================
# A jatekos teruletet vasarolhat karamok epitesehez es legelonek.
# A legelo a nyugdijas/tenyeszallomanynak olcso tartast ad (lasd
# stabling_sim.py: 120 B$/szezon a 700 helyett).
LAND_PARCELS = [
    {'key': 'north',  'name': 'Északi dűlő',  'cost': 45000,  'pasture_slots': 6,
     'note': 'Közeli, jó minőségű legelő.'},
    {'key': 'brook',  'name': 'Patakparti rét', 'cost': 78000, 'pasture_slots': 10,
     'note': 'Természetes vízforrás — a csikók fejlődésének kedvez.'},
    {'key': 'upper',  'name': 'Felső legelő', 'cost': 132000, 'pasture_slots': 16,
     'note': 'Nagy kiterjedésű, dombos terület.'},
]

PADDOCK_COST = 12000
PADDOCK_UPKEEP = 250
PADDOCK_YOUNG_DEV = 0.015      # csikonkenti fejlodesi bonusz


def pasture_capacity(owned_parcels):
    return sum(p['pasture_slots'] for p in LAND_PARCELS if p['key'] in owned_parcels)


# =======================================================================
# 6) OSSZESITETT FARM-ALLAPOT
# =======================================================================
def new_farm():
    """A nagybatytol orokolt kiindulo allapot."""
    return {
        'stable_level': 0,
        'extra_stables': 0,
        'feed_level': 0,
        'manor': {k: v['starting_condition'] for k, v in MANOR_WINGS.items()},
        'buildings': [k for k, b in BUILDINGS.items() if b['inherited']],
        'paddocks': 0,
        'land': [],
    }


def farm_summary(farm):
    return {
        'stable_capacity': stable_capacity(farm['stable_level'], farm['extra_stables']),
        'pasture_capacity': pasture_capacity(farm['land']),
        'feed_capacity': feed_capacity(farm['feed_level']),
        'buildings': len(farm['buildings']),
        'paddocks': farm['paddocks'],
        'manor_renovated': sum(1 for k, c in farm['manor'].items()
                               if c != Condition.DERELICT),
    }


def total_upkeep(farm):
    """Szezonalis fenntartasi koltseg - a novekedes ARA."""
    up = sum(BUILDINGS[b]['upkeep'] for b in farm['buildings'])
    up += farm['paddocks'] * PADDOCK_UPKEEP
    up += len(farm['land']) * 400
    up += stable_capacity(farm['stable_level'], farm['extra_stables']) * 60
    return up


def apply_building_effects(farm):
    """Osszegyujti a mechanikai hatasokat - ezek kotnek be a tobbi
    motorba (trener, frissesseg, serules, anyai bonusz)."""
    eff = {'young_horse_dev': 0.0, 'freshness_rate': 1.0,
           'trainer_effectiveness': 1.0, 'injury_severity': 1.0,
           'recovery_speed': 1.0, 'maternal_bonus': 1.0, 'sale_price_bonus': 0.0}

    for b in farm['buildings']:
        for k, v in (BUILDINGS[b].get('mechanical') or {}).items():
            if k == 'feed_capacity':
                continue
            if k in ('young_horse_dev',):
                eff[k] += v
            else:
                eff[k] *= v

    eff['young_horse_dev'] += farm['paddocks'] * PADDOCK_YOUNG_DEV

    if farm['manor'].get('east') != Condition.DERELICT:
        eff['sale_price_bonus'] += EAST_WING_SALE_BONUS

    return {k: round(v, 4) for k, v in eff.items()}


# =======================================================================
# 7) MONETIZACIO
# =======================================================================
# A JATEKOS DONTESE: az epuletek DIZAJN-ELEMEI es NEHANY UJ EPULET
# kerul a monetizacios retegbe.
#
# ALAPELV: ami mechanikai elonyt ad, az jatekbeli penzert legyen
# elerheto. Ami CSAK KINEZET, az mehet valodi penzert. Igy nem lesz
# pay-to-win, de van mit venni.
COSMETIC_ITEMS = [
    {'key': 'stable_colours',  'name': 'Istálló-színsémák',      'type': 'cosmetic'},
    {'key': 'manor_facade',    'name': 'Kúria-homlokzatok',      'type': 'cosmetic'},
    {'key': 'fencing_styles',  'name': 'Kerítés-stílusok',       'type': 'cosmetic'},
    {'key': 'yard_decor',      'name': 'Udvari dísztárgyak',     'type': 'cosmetic'},
    {'key': 'silks_designer',  'name': 'Egyedi versenyszínek',   'type': 'cosmetic'},
]

PREMIUM_BUILDINGS = [
    {'key': 'clock_tower',   'name': 'Óratorony',
     'type': 'cosmetic_landmark',
     'note': 'Látványelem. Nincs mechanikai hatása.'},
    {'key': 'show_arena',    'name': 'Bemutatóaréna',
     'type': 'convenience',
     'note': 'A saját lovaid kiállíthatók a farmnézetben. Nincs statisztikai hatás.'},
]


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - FARM & INFRASTRUCTURE ENGINE v1.0 ===\n")

    print("--- 1) AZ OROKOLT FARM ---")
    farm = new_farm()
    print("  A nagybátyádtól örökölt birtok, leromlott állapotban:\n")
    for k, w in MANOR_WINGS.items():
        c = farm['manor'][k]
        cost = f"{w['renovation_cost']:,} B$".replace(',', ' ') if w['renovation_cost'] else '—'
        print(f"  {w['name']:34s} {CONDITION_LABELS[c]:12s} felújítás: {cost:>10s}")
    print()
    for b in farm['buildings']:
        print(f"  {BUILDINGS[b]['name']:34s} örökölt      fenntartás: {BUILDINGS[b]['upkeep']:>6,d} B$".replace(',', ' '))
    s = farm_summary(farm)
    print(f"\n  Istállóhely: {s['stable_capacity']}  ·  Takarmány-kapacitás: {s['feed_capacity']} ló")
    print(f"  Szezonális fenntartás: {total_upkeep(farm):,} B$\n".replace(',', ' '))

    print("--- 2) ISTALLO-BOVITES ---")
    print("  12 hely kezdésnek, felújítással 20-ig. Azon túl csak új épülettel.\n")
    print(f"  {'Szint':32s} {'Hely':>5s} {'Költség':>10s}")
    for cap, cost, label in STABLE_STEPS:
        cs = f"{cost:,}".replace(',', ' ') if cost else '—'
        print(f"  {label:32s} {cap:>5d} {cs:>10s}")
    print(f"  {'Új istálló':32s} {'+8':>5s} {NEW_STABLE_COST:>10,d}".replace(',', ' '))
    print()
    print("  A bővítési út egy játékos szemszögéből:")
    total = 0
    for lvl in range(len(STABLE_STEPS) - 1):
        nxt = next_stable_upgrade(lvl)
        total += nxt['cost']
        print(f"     {stable_capacity(lvl)} → {nxt['new_capacity']:>2d} hely   "
              f"{nxt['cost']:>7,d} B$   (halmozott: {total:>8,d})".replace(',', ' '))
    print()

    print("--- 3) A TAKARMANYTAROLO KENYSZERE ---")
    print("  Nem lehet csak istállót bővítgetni — a tároló is kell hozzá.\n")
    for herd in [12, 16, 20, 26]:
        r = feed_quality_penalty(herd, 0)
        mark = 'rendben' if r['ok'] else f"-{r['penalty']*100:.0f}% etetési hatékonyság"
        print(f"  {herd:>2d} ló, örökölt tároló (12 férőhely):  {mark}")
    print()
    print(f"  {'Szint':16s} {'Kapacitás':>10s} {'Költség':>10s}")
    for cap, cost, label in FEED_STORE_STEPS:
        cs = f"{cost:,}".replace(',', ' ') if cost else '—'
        print(f"  {label:16s} {cap:>10d} {cs:>10s}")
    print()

    print("--- 4) EPULETEK ES VALODI HATASUK ---")
    print("  Alapelv: minden épületnek legyen mechanikai hatása.")
    print("  Ami csak díszít, az a monetizációs rétegbe tartozik.\n")
    for k, b in BUILDINGS.items():
        if b['inherited']:
            continue
        print(f"  {b['name']:22s} {b['cost']:>7,d} B$  fenntartás {b['upkeep']:>5,d}/szezon".replace(',', ' '))
        print(f"     {b['effect']}")
    print()

    print("--- 5) A KURIA KET SZARNYA ---")
    for k in ['west', 'east']:
        w = MANOR_WINGS[k]
        print(f"  {w['name']:34s} {w['renovation_cost']:>7,d} B$".replace(',', ' '))
        print(f"     {w['effect']}")
    print()

    print("--- 6) TERULETVASARLAS ---")
    print(f"  {'Terület':20s} {'Költség':>9s} {'Legelőhely':>11s}")
    for p in LAND_PARCELS:
        print(f"  {p['name']:20s} {p['cost']:>9,d} {p['pasture_slots']:>11d}".replace(',', ' '))
        print(f"     {p['note']}")
    print(f"\n  Karám: {PADDOCK_COST:,} B$ + {PADDOCK_UPKEEP} B$/szezon, "
          f"csikónként +{PADDOCK_YOUNG_DEV*100:.1f}% fejlődés".replace(',', ' '))
    print()

    print("--- 7) EGY KIEPULT FARM ---")
    built = new_farm()
    built.update({'stable_level': 4, 'feed_level': 2, 'paddocks': 3,
                  'land': ['north', 'brook'],
                  'buildings': ['round_pen', 'feed_store', 'walker',
                                'training_track', 'vet_room', 'foaling_barn']})
    built['manor'] = {'central': Condition.GOOD, 'west': Condition.BASIC,
                      'east': Condition.BASIC}
    s = farm_summary(built)
    print(f"  Istállóhely {s['stable_capacity']}  ·  Legelő {s['pasture_capacity']}  ·  "
          f"Takarmány {s['feed_capacity']}  ·  Karám {s['paddocks']}")
    print(f"  Szezonális fenntartás: {total_upkeep(built):,} B$\n".replace(',', ' '))
    print("  Halmozott mechanikai hatások:")
    for k, v in apply_building_effects(built).items():
        print(f"     {k:24s} {v}")
    print()

    invest = (sum(c for _, c, _ in STABLE_STEPS)
              + sum(c for _, c, _ in FEED_STORE_STEPS[:3])
              + sum(BUILDINGS[b]['cost'] for b in built['buildings'])
              + MANOR_WINGS['west']['renovation_cost']
              + MANOR_WINGS['east']['renovation_cost']
              + sum(p['cost'] for p in LAND_PARCELS if p['key'] in built['land'])
              + built['paddocks'] * PADDOCK_COST)
    print(f"  Teljes beruházás idáig: {invest:,} B$".replace(',', ' '))
    print(f"  (a 12 szezonos kiegyensúlyozott stratégia ~225 000 B$ profitot hozott)\n")

    print("--- 8) MONETIZACIO ---")
    print("  Alapelv: ami mechanikai előnyt ad, játékbeli pénzért.")
    print("  Ami CSAK kinézet, az mehet valódi pénzért.\n")
    for c in COSMETIC_ITEMS:
        print(f"  {c['name']:26s} kozmetikai")
    for b in PREMIUM_BUILDINGS:
        print(f"  {b['name']:26s} {b['type']}")
        print(f"     {b['note']}")
    print()

    print("--- 9) VALIDACIO ---")
    checks = [
        ('Kezdő istállóhely 12 (egyezik a szezon-szimulátorral)',
         stable_capacity(0) == 12),
        ('Felújítással 14-re bővül', stable_capacity(1) == 14),
        ('Az épület maximuma 20', stable_capacity(4) == 20),
        ('20 felett csak új épület ad helyet',
         next_stable_upgrade(4)['type'] == 'new_building'),
        ('Új istálló +8 helyet ad',
         stable_capacity(4, 1) == 28),
        ('A takarmánytároló túllépése büntet',
         not feed_quality_penalty(16, 0)['ok']),
        ('Kapacitáson belül nincs büntetés',
         feed_quality_penalty(12, 0)['ok']),
        ('A tároló induló kapacitása egyezik az istállóéval',
         feed_capacity(0) == stable_capacity(0)),
        ('A büntetés korlátozott (max 45%)',
         feed_quality_penalty(100, 0)['penalty'] <= 0.45),
        ('A középső szárny nem igényel felújítást',
         MANOR_WINGS['central']['renovation_cost'] is None),
        ('A másik két szárny leromlott állapotban indul',
         all(MANOR_WINGS[k]['starting_condition'] == Condition.DERELICT
             for k in ['west', 'east'])),
        ('Minden nem-kozmetikai épületnek van mechanikai hatása',
         all(b.get('mechanical') for b in BUILDINGS.values())),
        ('A monetizált elemek nem adnak statisztikai előnyt',
         all(b['type'] in ('cosmetic_landmark', 'convenience')
             for b in PREMIUM_BUILDINGS)),
        ('A fenntartás nő a farm méretével',
         total_upkeep(built) > total_upkeep(new_farm())),
        ('A körkarám és a takarmánytároló örökölt',
         'round_pen' in new_farm()['buildings']
         and 'feed_store' in new_farm()['buildings']),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
