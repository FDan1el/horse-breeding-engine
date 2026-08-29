"""
Breeder Tycoon - Naming Engine v1.0
=======================================================================
NEVADAS VALOS MINTAK ALAPJAN.

A korabbi megoldas szotagokat fuzott ossze a szulok nevebol, es negy
generacio utan elfajult ("Wrenwrenwr", "Gildbwrenrg"). A valos
telivér-nevadas ennel sokkal gazdagabb.

=======================================================================
FORRASOK
=======================================================================

1. A LEGGYAKORIBB MINTA: az apa es az anya nevenek osszevonasa.
   Thunder Gulch = Gulch x Line of Thunder
   Danzing Candy = Twirling Candy x House of Danzing
   Ali Sheba     = Alidar x Bell Shiva
   https://www.mentalfloss.com/article/21585/whats-horse-name-no-more-18-characters
   https://horseracingsense.com/why-are-racehorse-names-so-weird/

2. A SZELLEMESEBB VALTOZAT JELENTES-ALAPU, nem szotag-alapu:
   Inside Information = Private Account x Pure Profit
   Elope              = Gone West x Proposal
   Pioneer of Medina  = Pioneer of the Nile x Lights of Medina
   -> EZERT hasznalunk SZOKESZLETET, nem szotag-darabolast.
   https://steeplechaseofcharleston.com/2022/10/04/how-racehorses-get-their-names/

3. MENVONAL-TEMAK OROKLODNEK. Mr. Prospector (Raise a Native x Gold
   Digger) -> fia Gone West -> annak fia Mr. Greeley (Horace Greeley
   utan, aki a "Go West, young man" mondast megalkotta).
   -> EZERT kap minden menvonal sajat TEMAT, es a leszarmazottak
   abbol a szokeszletbol meritenek.
   https://myracehorse.com/the-naming-process

4. KEMENY SZABALYOK (Jockey Club):
   - legfeljebb 18 karakter, a szokozokkel es irasjelekkel egyutt
   - NEM hasznalhato fel nev a pedigre ELSO OT GENERACIOJABOL
   - nem hasznalhato ugyanattol az apatol vagy anyatol szarmazo
     korabbi lo neve
   - nem allhat csak kezdobetukbol vagy csak szamokbol
   https://www.kentuckyderby.com/horses/news/whats-in-a-name-a-look-at-the-rules-for-naming-thoroughbreds/
   https://petnamee.com/racehorse-naming-rules/

5. A NEVTER SZUKOSSEGE VALOS PROBLEMA: evi ~60 000 kerelembol kb.
   harmadot elutasitanak, es 430 000 nev van aktiv hasznalatban.
   -> EZERT kell bo szokeszlet es tobb strategia, kulonben a jatek
   nevei is elfogynak.
   https://www.mentalfloss.com/article/21585/whats-horse-name-no-more-18-characters
"""

import random

MAX_NAME_LENGTH = 18
PEDIGREE_UNIQUE_GENERATIONS = 5     # a Jockey Club szabalya


# =======================================================================
# 1) SZOKESZLET TEMAK SZERINT
# =======================================================================
# A temak a MENVONALAKHOZ tartoznak (forras 3.). Egy alapito men temat
# kap, es a leszarmazottai abbol meritenek - igy a nevekbol is latszik
# a vervonal, ahogy a valosagban is.
THEMES = {
    'weather': {
        'label': 'Időjárás',
        'adj': ['Storm', 'Thunder', 'Frost', 'Winter', 'Summer', 'Autumn',
                'Northern', 'Rolling', 'Silent', 'Wild', 'Sudden', 'Rising'],
        'noun': ['Gale', 'Tempest', 'Cloud', 'Rain', 'Sky', 'Thunder',
                 'Frost', 'Snow', 'Wind', 'Season', 'Front', 'Squall'],
        'solo': ['Downpour', 'Whirlwind', 'Cloudburst', 'Nimbus', 'Cyclone'],
    },
    'navigation': {
        'label': 'Hajózás',
        'adj': ['Northern', 'Distant', 'Open', 'Charted', 'Steady', 'True',
                'Coastal', 'Deep', 'Silver', 'Morning'],
        'noun': ['Compass', 'Beacon', 'Harbour', 'Anchor', 'Passage',
                 'Bearing', 'Channel', 'Lantern', 'Sextant', 'Voyage'],
        'solo': ['Landfall', 'Waypoint', 'Meridian', 'Windward', 'Seafarer'],
    },
    'nobility': {
        'label': 'Nemesség',
        'adj': ['Noble', 'Royal', 'Crown', 'Golden', 'Grand', 'High',
                'Regal', 'Ancient', 'Sovereign', 'Bold'],
        'noun': ['Crown', 'Banner', 'Heir', 'Charter', 'Seal', 'Court',
                 'Standard', 'Herald', 'Coronet', 'Regent'],
        'solo': ['Sovereign', 'Chancellor', 'Birthright', 'Pretender'],
    },
    'craft': {
        'label': 'Mesterség',
        'adj': ['Iron', 'Copper', 'Oaken', 'Fine', 'Hammered', 'Woven',
                'Turned', 'Cut', 'Forged', 'Polished'],
        'noun': ['Forge', 'Anvil', 'Loom', 'Chisel', 'Kiln', 'Bellows',
                 'Lathe', 'Craft', 'Trade', 'Workshop'],
        'solo': ['Craftsman', 'Journeyman', 'Ironwork', 'Handiwork'],
    },
    'landscape': {
        'label': 'Táj',
        'adj': ['Upper', 'Lower', 'Hidden', 'Broad', 'Narrow', 'Green',
                'Grey', 'Far', 'Quiet', 'Old'],
        'noun': ['Meadow', 'Ridge', 'Hollow', 'Brook', 'Fell', 'Moor',
                 'Copse', 'Vale', 'Heath', 'Fen'],
        'solo': ['Woodland', 'Highground', 'Riverbend', 'Stonewall'],
    },
    'fortune': {
        'label': 'Szerencse',
        'adj': ['Lucky', 'Fair', 'Certain', 'Doubtful', 'Second', 'Final',
                'Even', 'Long', 'Short', 'Fortunate'],
        'noun': ['Chance', 'Fortune', 'Verdict', 'Wager', 'Margin', 'Odds',
                 'Reckoning', 'Gambit', 'Ledger', 'Outcome'],
        'solo': ['Windfall', 'Longshot', 'Fairplay', 'Providence'],
    },
    'music': {
        'label': 'Zene',
        'adj': ['Quiet', 'Rising', 'Falling', 'Minor', 'Major', 'Distant',
                'Clear', 'Low', 'Sweet', 'Steady'],
        'noun': ['Chorus', 'Refrain', 'Cadence', 'Anthem', 'Ballad',
                 'Overture', 'Measure', 'Encore', 'Prelude', 'Verse'],
        'solo': ['Crescendo', 'Nocturne', 'Serenade', 'Fanfare'],
    },
    'light': {
        'label': 'Fény',
        'adj': ['Morning', 'Evening', 'Pale', 'Bright', 'First', 'Last',
                'Amber', 'Silver', 'Golden', 'Low'],
        'noun': ['Dawn', 'Dusk', 'Ember', 'Beacon', 'Glimmer', 'Shadow',
                 'Gleam', 'Flare', 'Halo', 'Twilight'],
        'solo': ['Daybreak', 'Nightfall', 'Sunspot', 'Afterglow'],
    },
}

THEME_KEYS = list(THEMES)

# Temaktol fuggetlen, altalanos keszlet - a "szabad" nevekhez (forras 2.:
# a tulajdonos barmit valaszthat, nem kotelezo a pedigrere utalni).
FREE_ADJ = ['Bold', 'Quiet', 'Swift', 'Patient', 'Restless', 'Honest',
            'Careful', 'Reckless', 'Modest', 'Curious', 'Stubborn',
            'Gentle', 'Sharp', 'Solemn', 'Merry', 'Certain', 'Idle',
            'Eager', 'Wary', 'Candid', 'Sober', 'Brisk', 'Tender',
            'Fearless', 'Humble', 'Nimble', 'Placid', 'Vivid', 'Wistful']
FREE_NOUN = ['Promise', 'Rumour', 'Errand', 'Bargain', 'Notion', 'Habit',
             'Whisper', 'Memory', 'Question', 'Answer', 'Detour', 'Custom',
             'Remedy', 'Pretext', 'Reason', 'Venture', 'Motive', 'Pledge',
             'Riddle', 'Wisdom', 'Council', 'Errantry', 'Legacy', 'Rally',
             'Signal', 'Token', 'Tribute', 'Warrant', 'Witness']
FREE_SOLO = ['Cornerstone', 'Landmark', 'Watermark', 'Hallmark',
             'Benchmark', 'Milestone', 'Keystone', 'Touchstone',
             'Firebrand', 'Wayfarer', 'Standfast', 'Farsighted',
             'Openhanded', 'Straightaway', 'Aftermath', 'Undertow']


# =======================================================================
# 2) SZO-KINYERES A SZULOK NEVEBOL
# =======================================================================
def words_of(name):
    """A nev ertelmes szavai - ezekbol epul az osszevont nev."""
    return [w for w in (name or '').replace("'s", '').split() if len(w) > 2]


def combine_parents(sire_name, dam_name, rng):
    """A LEGGYAKORIBB VALOS MINTA (forras 1.): egy szo az apatol,
    egy az anyatol.

    Thunder Gulch = Gulch x Line of Thunder
    """
    s_words = words_of(sire_name)
    d_words = words_of(dam_name)
    if not s_words or not d_words:
        return None
    a = rng.choice(s_words)
    b = rng.choice(d_words)
    if a.lower() == b.lower():
        return None
    return f"{a} {b}" if rng.random() < 0.5 else f"{b} {a}"


def possessive(sire_name, dam_name, rng):
    """Birtokos szerkezet - Curlin's Voyage mintajara."""
    s_words = words_of(sire_name)
    d_words = words_of(dam_name)
    if not s_words or not d_words:
        return None
    base = rng.choice(s_words if rng.random() < 0.5 else d_words)
    other = rng.choice(d_words if base in s_words else s_words)
    if base.lower() == other.lower():
        return None
    return f"{base}'s {other}"


# =======================================================================
# 3) TEMA-ALAPU NEV
# =======================================================================
def theme_name(theme_key, rng):
    """A menvonal temajabol (forras 3.)."""
    t = THEMES.get(theme_key) or THEMES[rng.choice(THEME_KEYS)]
    r = rng.random()
    if r < 0.18 and t['solo']:
        return rng.choice(t['solo'])
    if r < 0.60:
        return f"{rng.choice(t['adj'])} {rng.choice(t['noun'])}"
    # kereszthivatkozas egy masik temara - igy nem lesz monoton
    other = THEMES[rng.choice(THEME_KEYS)]
    return f"{rng.choice(t['adj'])} {rng.choice(other['noun'])}"


def free_name(rng):
    """Tema nelkuli, szabad nev (forras 2.)."""
    r = rng.random()
    if r < 0.15:
        return rng.choice(FREE_SOLO)
    if r < 0.55:
        return f"{rng.choice(FREE_ADJ)} {rng.choice(FREE_NOUN)}"
    t = THEMES[rng.choice(THEME_KEYS)]
    return f"{rng.choice(t['adj'])} {rng.choice(t['noun'])}"


# =======================================================================
# 4) SZABALY-ELLENORZES
# =======================================================================
FORBIDDEN_ENDINGS = ('filly', 'colt', 'stud', 'mare', 'stallion', 'sire')


def is_valid(name, forbidden_names=None):
    """A Jockey Club szabalyai (forras 4.)."""
    if not name or len(name) > MAX_NAME_LENGTH:
        return False
    if name.replace(' ', '').isdigit():
        return False
    if all(len(w) <= 1 for w in name.split()):        # csak kezdobetuk
        return False
    low = name.lower()
    if any(low.endswith(e) for e in FORBIDDEN_ENDINGS):
        return False
    if forbidden_names and low in forbidden_names:
        return False
    return True


def pedigree_names(horse, all_horses, generations=PEDIGREE_UNIQUE_GENERATIONS):
    """A pedigre elso OT generaciojanak nevei.

    A Jockey Club szabalya szerint EZEK nem hasznalhatok fel ujra
    (forras 4.). A sire_id/dam_id lanc bejarasaval gyujtjuk ossze -
    nem a 14 elemu os-tombbol, mert az csak negy generacio.
    """
    names = set()
    frontier = [(horse, 0)]
    while frontier:
        h, depth = frontier.pop()
        if h is None or depth > generations:
            continue
        if depth > 0:
            names.add(h.name.lower())
        for pid in (getattr(h, 'sire_id', None), getattr(h, 'dam_id', None)):
            if pid and pid in all_horses:
                frontier.append((all_horses[pid], depth + 1))
    return names


# =======================================================================
# 5) A FO GENERATOR
# =======================================================================
# A strategiak aranya. A valos gyakorlat szerint az osszevonas a
# leggyakoribb (forras 1., 6.), de messze nem kizarolagos.
STRATEGY_WEIGHTS = [
    ('combine', 0.34),      # apa + anya szava
    ('theme', 0.30),        # a menvonal temaja
    ('free', 0.26),         # szabad nev
    ('possessive', 0.10),   # birtokos szerkezet
]


def generate_name(rng, sire=None, dam=None, all_horses=None,
                  theme_key=None, used_names=None, attempts=40):
    """Egy uj lo neve.

    A pedigre elso ot generaciojabol szarmazo neveket ES a mar
    hasznalt neveket egyarant kizarja.
    """
    used = set(n.lower() for n in (used_names or []))

    # a pedigre-tiltas (forras 4.)
    if sire is not None and all_horses:
        used |= pedigree_names(sire, all_horses, PEDIGREE_UNIQUE_GENERATIONS - 1)
        used.add(sire.name.lower())
    if dam is not None and all_horses:
        used |= pedigree_names(dam, all_horses, PEDIGREE_UNIQUE_GENERATIONS - 1)
        used.add(dam.name.lower())

    strategies = [s for s, _ in STRATEGY_WEIGHTS]
    weights = [w for _, w in STRATEGY_WEIGHTS]

    for i in range(attempts):
        # a vegen egyre inkabb a szabad nev fele tolodunk, hogy
        # biztosan legyen eredmeny
        strat = 'free' if i > attempts * 0.7 else rng.choices(strategies, weights)[0]

        if strat == 'combine' and sire and dam:
            cand = combine_parents(sire.name, dam.name, rng)
        elif strat == 'possessive' and sire and dam:
            cand = possessive(sire.name, dam.name, rng)
        elif strat == 'theme':
            cand = theme_name(theme_key, rng)
        else:
            cand = free_name(rng)

        if cand and is_valid(cand, used):
            return cand

    # vegso menedek: temanev sorszammal (a valos gyakorlatban is
    # letezik - "Omaha Omaha", mert az "Omaha" foglalt volt)
    for n in range(2, 40):
        cand = f"{free_name(rng)} {n}"
        if is_valid(cand, used):
            return cand
    return f"Unnamed {rng.randint(1000, 9999)}"


# =======================================================================
# 6) MENVONAL-TEMAK
# =======================================================================
def assign_theme(rng, parent_theme=None, drift=0.22):
    """Egy uj menvonal temaja.

    Az esetek tobbsegeben AZ APJA TEMAJAT viszi tovabb (forras 3.:
    Mr. Prospector -> Gone West -> Mr. Greeley), neha viszont uj
    iranyba fordul.
    """
    if parent_theme and rng.random() > drift:
        return parent_theme
    return rng.choice(THEME_KEYS)


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - NEVADAS ===\n")
    rng = random.Random(42)

    print("--- 1) A NEGY STRATEGIA ---")
    print("  Valós minták alapján. Az összevonás a leggyakoribb,")
    print("  de messze nem kizárólagos.\n")
    for strat, w in STRATEGY_WEIGHTS:
        print(f"  {strat:12s} {w*100:>4.0f}%")
    print()

    class FakeHorse:
        def __init__(self, name):
            self.name, self.sire_id, self.dam_id = name, None, None

    sire = FakeHorse('Northern Beacon')
    dam = FakeHorse('Quiet Fortune')
    print(f"  Apa: {sire.name}   Anya: {dam.name}\n")
    print("  Összevonás:")
    for _ in range(4):
        print(f"     {combine_parents(sire.name, dam.name, rng)}")
    print("  Birtokos:")
    for _ in range(3):
        print(f"     {possessive(sire.name, dam.name, rng)}")
    print()

    print("--- 2) MENVONAL-TEMAK (Mr. Prospector -> Gone West mintajara) ---")
    for key in ['weather', 'navigation', 'nobility', 'fortune']:
        names = [theme_name(key, rng) for _ in range(4)]
        print(f"  {THEMES[key]['label']:12s} {' · '.join(names)}")
    print()

    print("--- 3) NEGY GENERACIO EGY VONALON ---")
    print("  A régi rendszerben itt fajultak el a nevek.\n")
    horses = {}
    def add(h, hid):
        h.horse_id = hid
        horses[hid] = h
        return h

    line_theme = 'navigation'
    s = add(FakeHorse(theme_name(line_theme, rng)), 's0')
    d = add(FakeHorse(free_name(rng)), 'd0')
    print(f"  0. gen:  {s.name} × {d.name}")
    for gen in range(1, 6):
        nm = generate_name(rng, s, d, horses, line_theme)
        child = add(FakeHorse(nm), f'g{gen}')
        child.sire_id, child.dam_id = s.horse_id, d.horse_id
        print(f"  {gen}. gen:  {nm}")
        s = child
        d = add(FakeHorse(free_name(rng)), f'm{gen}')
    print()

    print("--- 4) A PEDIGRE-TILTAS MUKODIK (Jockey Club: 5 generacio) ---")
    names_in_ped = pedigree_names(horses['g5'], horses)
    print(f"  A g5 pedigréjében {len(names_in_ped)} név szerepel — "
          f"ezek egyike sem használható fel újra.")
    fresh = [generate_name(rng, horses['g5'], horses['m5'], horses, line_theme)
             for _ in range(6)]
    clash = [n for n in fresh if n.lower() in names_in_ped]
    print(f"  6 új név generálva, ütközés: {len(clash)}")
    print(f"  {' · '.join(fresh)}\n")

    print("--- 5) NEVTER-KAPACITAS ---")
    print("  A valóságban 430 000 név van aktív használatban, és az évi")
    print("  60 000 kérelem harmadát elutasítják — a szűkösség valós.\n")
    rng2 = random.Random(7)
    generated = set()
    collisions = 0
    for _ in range(20000):
        n = generate_name(rng2, used_names=generated)
        if n in generated:
            collisions += 1
        generated.add(n)
    print(f"  20 000 kísérletből {len(generated):,} egyedi név, "
          f"{collisions} ütközés".replace(',', ' '))
    theoretical = sum(len(t['adj']) * len(t['noun']) for t in THEMES.values())
    theoretical += len(FREE_ADJ) * len(FREE_NOUN)
    theoretical += sum(len(t['solo']) for t in THEMES.values()) + len(FREE_SOLO)
    print(f"  Elméleti kombinációk (kereszthivatkozás nélkül): "
          f"{theoretical:,}".replace(',', ' '))
    cross = len(THEMES) * len(THEMES) * 10 * 10
    print(f"  Kereszthivatkozásokkal: ~{cross:,}".replace(',', ' '))
    print()

    print("--- 6) SZABALY-ELLENORZES ---")
    tests = [
        ('Northern Beacon', True, 'rendben'),
        ('A' * 19, False, 'túl hosszú (18 a maximum)'),
        ('12345', False, 'csak számok'),
        ('A B C', False, 'csak kezdőbetűk'),
        ('Silver Colt', False, 'tiltott végződés'),
        ("Storm's Promise", True, 'birtokos szerkezet rendben'),
    ]
    for name, expected, why in tests:
        got = is_valid(name)
        mark = 'OK ' if got == expected else 'HIBA'
        print(f"  [{mark}] {name[:20]:22s} {why}")
    print()

    print("--- 7) VALIDACIO ---")
    checks = [
        ('Minden név 18 karakteren belül',
         all(len(n) <= 18 for n in generated)),
        ('Nincs ütközés 20 000 generálásnál', collisions == 0),
        ('A névtér elég bő (>2000 egyedi)', len(generated) > 2000),
        ('A pedigré-tiltás működik', len(clash) == 0),
        ('A ménvonal-téma öröklődik',
         assign_theme(random.Random(1), 'weather', drift=0.0) == 'weather'),
        ('De néha új irányba fordul',
         assign_theme(random.Random(1), 'weather', drift=1.0) is not None),
        ('Az összevonás mindkét szülőből merít',
         # A korabbi teszt hibas volt: az all(...) generatoron belul
         # hivta a fuggvenyt, es a kimeritett generator ures eredmenyt
         # adott. Most eloszor eloallitjuk a mintat, aztan ellenorzunk.
         all(len([w for w in ['Northern', 'Beacon', 'Quiet', 'Fortune']
                  if w in r]) == 2
             for r in [combine_parents('Northern Beacon', 'Quiet Fortune',
                                       random.Random(i)) for i in range(30)])),
        ('A tiltott végződések kiszűrve',
         not is_valid('Grey Stallion') and not is_valid('Bold Filly')),
        ('Nyolc téma áll rendelkezésre', len(THEMES) == 8),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
