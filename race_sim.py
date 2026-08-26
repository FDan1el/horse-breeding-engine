"""
Trot Heritage - Race Simulation Engine v1.0
=======================================================================
A HIANYZO LANCSZEM: toltottsegi sav -> helyezes.

Minden korabbi motor (tenyesztes, takarmany, tréner, zsoké, palya) ide
fut be. Ez a modul dönti el, mi tortenik a palyan.

BEMENET egy lora:
    fill_bar        - a felepitett kepesseg (max 99.75%), a
                      breeding + feeding + trainer motorokbol
    distance_profile- sprint/mile/middle/staying alkalmassag
    jockey_mod      - versenynapi zsoké-modosito (jockey_sim.py)
    freshness       - frissesseg-csik (0-100)
    running_style   - futasstilus

KIMENET: helyezes, futasleiras, nyeremeny.

=======================================================================
KALIBRACIOS CELOK - VALOS ADATBOL
=======================================================================

1. A FAVORIT GYOZELMI ARANYA: tobb forras egyezik, hogy a favorit a
   futamok 30-35%-at nyeri. Eszak-amerikai adat (1990-2023): 35.2%.
   Brit adat: 30-35%. A masodik favorit 19.4%.
   https://worldmetrics.org/horse-racing-winning-odds-statistics/
   https://betmix.com/how-often-does-the-favorite-win-a-horse-race/
   https://www.flatstats.co.uk/favourite-stats.php

2. MEZONY-MELYSEG: nyolclovas futamokban a gyoztes az elso NEGY
   valasztas kozul kerul ki az esetek 82%-aban.
   https://betmix.com/how-often-does-the-favorite-win-a-horse-race/

3. TAVPROFIL SULYA - kozvetlenul hasznalhato szam: a kedvelt tavjan
   futo lo 32%-ot nyer, a nem kedvelt tavjan 24%-ot. Ez kb. 1.33x
   elonyt jelent - EZ hatarozza meg, mennyit erjen a tavalkalmassag.
   https://worldmetrics.org/horse-racing-winning-odds-statistics/

4. NAGY ODDSOK: az 50/1 feletti lovak 1.2%-ban nyernek - azaz a
   meglepetes LETEZIK, de ritka.
   https://worldmetrics.org/horse-racing-winning-odds-statistics/

5. ZSOKE-HATAS: a 10+ eves tapasztalatu zsokek 28%-kal magasabb
   gyozelmi aranyt ernek el a 30/1 FELETTI lovakon - azaz a zsoké
   a GYENGEBB lovaknal szamit relative tobbet.
   https://worldmetrics.org/horse-racing-winning-odds-statistics/

6. FUTASSTILUS ES PALYA: a rovid celegyenes a korán elmenő lovaknak
   kedvez, a hosszu a hajrazoknak (lasd track_sim.py forrasait).
"""

import random
import statistics
from enum import Enum
from collections import Counter

random.seed(42)


# =======================================================================
# 1) FUTASSTILUSOK
# =======================================================================
class RunningStyle(Enum):
    FRONT = 'front'      # korán elmegy, vezet
    STALKER = 'stalker'  # tapad, a celegyenesben tamad
    CLOSER = 'closer'    # hatulrol jon


STYLE_LABELS_HU = {
    RunningStyle.FRONT: 'Korán elmenő',
    RunningStyle.STALKER: 'Tapadó',
    RunningStyle.CLOSER: 'Hajrázó',
}

# A palya jellege (track_sim.py style_bias) melyik stilusnak kedvez.
# A rovid celegyenes a korán elmenoket, a hosszu a hajrazokat segiti.
STYLE_TRACK_BONUS = {
    'korai sebesség': {RunningStyle.FRONT: 1.030, RunningStyle.STALKER: 1.000, RunningStyle.CLOSER: 0.972},
    'kitartás':       {RunningStyle.FRONT: 0.975, RunningStyle.STALKER: 1.000, RunningStyle.CLOSER: 1.028},
    'kitartó hajrá':  {RunningStyle.FRONT: 0.980, RunningStyle.STALKER: 1.005, RunningStyle.CLOSER: 1.022},
    'semleges':       {RunningStyle.FRONT: 1.000, RunningStyle.STALKER: 1.000, RunningStyle.CLOSER: 1.000},
}


def infer_running_style(profile):
    """A futasstilus a lo sajat tulajdonsagaibol kovetkezik:
    a gyorsulas/sprint dominancia korán elmenot, a kitartas hajrazot ad."""
    speed_side = profile.get('accel', 60) + profile.get('sprint', 60)
    stay_side = profile.get('stamina', 60) + profile.get('staying', 60)
    diff = speed_side - stay_side
    if diff > 18:
        return RunningStyle.FRONT
    if diff < -18:
        return RunningStyle.CLOSER
    return RunningStyle.STALKER


# =======================================================================
# 2) TAVALKALMASSAG (forras 3.)
# =======================================================================
# A valos adat: kedvelt tavon 32%, nem kedvelten 24% gyozelmi arany.
# Ez kb. 1.33x elony - a teljesitmenyre atszamolva egy szuk, de erezheto
# szorzo.
DISTANCE_MATCH_FULL = 1.035    # tokeletes illeszkedes
DISTANCE_MATCH_NONE = 0.955    # teljes eltéres


def distance_factor(profile, band):
    """Mennyire illik a lohoz ez a tav? A tenyesztesi motor
    sprint/mile/middle/staying tulajdonsagaibol."""
    aptitude = profile.get(band, 50)
    # az 50 a semleges pont; 99 a maximum
    normalized = max(0.0, min(1.0, (aptitude - 30) / 60.0))
    return DISTANCE_MATCH_NONE + (DISTANCE_MATCH_FULL - DISTANCE_MATCH_NONE) * normalized


# =======================================================================
# 3) FRISSESSEG
# =======================================================================
# A frissesseg-csik (season_sim.py: ~2 naponta tolt vissza). 60% alatt
# kezd rontani - ez a korabban rogzitett szabaly.
FRESHNESS_PENALTY_THRESHOLD = 60.0


def freshness_factor(freshness):
    if freshness >= FRESHNESS_PENALTY_THRESHOLD:
        return 1.0
    deficit = (FRESHNESS_PENALTY_THRESHOLD - freshness) / FRESHNESS_PENALTY_THRESHOLD
    return round(1.0 - deficit * 0.12, 4)


# =======================================================================
# 4) A VELETLEN - EZ A LEGFONTOSABB PARAMETER
# =======================================================================
# Ha a legjobb lo mindig nyer, nincs izgalom. Ha tul sok a veletlen,
# ertelmetlen a tenyesztes.
#
# A CEL (forras 1.): a favorit a futamok kb. 33%-at nyerje.
# Ezt az alabbi zaj-szorassal ertuk el - EMPIRIKUSAN HANGOLVA,
# a modul vegen levo validacio meri.
RACE_NOISE_SD = 8.5     # empirikusan hangolva: ezzel a favorit ~33%-ot nyer
                        # es a gyoztes ~82%-ban a top 4 formabol kerul ki -
                        # mindketto pontosan a valos adat (forras 1., 2.)


def race_performance(horse, race, rng=random):
    """Egy lo aznapi teljesitmenye ebben a futamban."""
    base = horse['fill_bar']

    f_dist = distance_factor(horse['profile'], race['band'])
    f_style = STYLE_TRACK_BONUS.get(race['style_bias'], STYLE_TRACK_BONUS['semleges'])[horse['style']]
    f_fresh = freshness_factor(horse.get('freshness', 100))
    f_jockey = horse.get('jockey_mod', 1.0)

    deterministic = base * f_dist * f_style * f_fresh * f_jockey
    noise = rng.gauss(0, RACE_NOISE_SD)

    return {
        'score': deterministic + noise,
        'deterministic': round(deterministic, 2),
        'factors': {
            'táv': round(f_dist, 3),
            'pálya': round(f_style, 3),
            'frissesség': round(f_fresh, 3),
            'zsoké': round(f_jockey, 3),
        },
    }


# =======================================================================
# 5) NPC MEZONY GENERALAS
# =======================================================================
# Jatekosbazis hijan NPC-lovakkal tesztelunk. A mezony a futam
# nyeremeny-savjahoz igazodik - igy a lovak osszemerhetok, ahogy a
# valos felteteles futamokban is.
# ATKALIBRALVA: az eredeti savok (maiden 34-52 stb.) a jatekos VALODI
# fillBar-tartomanya ALATT voltak. Egy tipikus jatekos-lo (genetika ~54,
# takarmany 17.5%, kozepes trener) 64 korul all - igy a maiden mezony
# ellen 75%-ot nyert volna.
#
# A jatekos elerheto fillBar-tartomanya:
#   legrosszabb  genetika 30, takarmany 0,  trener 40  -> ~27
#   tipikus      genetika 60, takarmany 12, trener 60  -> ~60
#   legjobb      genetika 90, takarmany 20, trener 85  -> ~91
# A savok EHHEZ igazodnak.
#
# EZT AZ INTEGRACIO DERITETTE KI: a season.html JS-portjat korabban
# atkalibraltam, a Python eredetit viszont nem - a ketto szetcsuszott.
BRACKET_FILL_RANGE = {
    'maiden': (46, 63),
    'b5':     (50, 67),
    'b20':    (55, 72),
    'b75':    (61, 78),
    'b250':   (67, 84),
    'open':   (73, 90),
    'G3':     (76, 92),
    'G2':     (80, 95),
    'G1':     (84, 97),
}

NPC_NAME_PARTS_A = ['Ash', 'Bram', 'Cinder', 'Dun', 'Elm', 'Fen', 'Grey', 'Haw',
                    'Iron', 'Kes', 'Lark', 'Mor', 'Nettle', 'Oak', 'Pike', 'Quill',
                    'Rush', 'Slate', 'Thorn', 'Vale', 'Wren']
NPC_NAME_PARTS_B = ['bank', 'brook', 'crest', 'dale', 'fall', 'gate', 'hill',
                    'lane', 'mere', 'ridge', 'shade', 'stone', 'wick', 'wood']


def generate_npc(bracket, rng=random, name=None):
    """Egy NPC ellenfel generalasa a futam szintjehez igazitva."""
    lo, hi = BRACKET_FILL_RANGE.get(bracket, (50, 70))
    fill = rng.uniform(lo, hi)

    profile = {}
    for trait in ['accel', 'sprint', 'stamina', 'staying', 'mile', 'middle']:
        profile[trait] = round(max(20, min(99, rng.gauss(58, 14))))

    if name is None:
        name = rng.choice(NPC_NAME_PARTS_A) + rng.choice(NPC_NAME_PARTS_B)

    return {
        'name': name,
        'fill_bar': round(fill, 1),
        'profile': profile,
        'style': infer_running_style(profile),
        'freshness': rng.uniform(70, 100),
        'jockey_mod': rng.uniform(0.975, 1.025),
        'is_npc': True,
    }


def generate_field(bracket, size=8, rng=random, include=None):
    """Teljes mezony. 'include' a jatekos lova (ha van)."""
    field = list(include) if include else []
    while len(field) < size:
        field.append(generate_npc(bracket, rng))
    return field


# =======================================================================
# 6) A FUTAM
# =======================================================================
def run_race(field, race, rng=random):
    """Lefuttat egy futamot es visszaadja a vegeredmenyt."""
    results = []
    for horse in field:
        perf = race_performance(horse, race, rng)
        results.append({
            'horse': horse,
            'score': perf['score'],
            'deterministic': perf['deterministic'],
            'factors': perf['factors'],
        })

    results.sort(key=lambda r: -r['score'])
    for i, r in enumerate(results, 1):
        r['position'] = i

    # a "favorit" az, akinek a legmagasabb a determinisztikus pontszama
    favourite = max(results, key=lambda r: r['deterministic'])

    return {
        'results': results,
        'winner': results[0],
        'favourite': favourite,
        'favourite_won': favourite['position'] == 1,
    }


# =======================================================================
# 7) FUTASLEIRAS - hogy a jatekos ertse, mi tortent
# =======================================================================
def describe_run(result, race, field_size):
    """Rovid futasleiras. A spec szerint a verseny cinematic, de az
    eredmeny mellett kell egy mondat, amibol a jatekos megerti, MIERT
    lett ez a helyezes."""
    horse = result['horse']
    pos = result['position']
    f = result['factors']
    style = horse['style']

    # a kiindulo helyzet a stilusbol
    if style == RunningStyle.FRONT:
        start = 'Korán az élre állt'
    elif style == RunningStyle.CLOSER:
        start = 'Hátulról indult'
    else:
        start = 'A mezőny közepén tapadt'

    # a legerosebb es leggyengebb tenyezo
    strongest = max(f.items(), key=lambda kv: kv[1])
    weakest = min(f.items(), key=lambda kv: kv[1])

    notes = []
    if weakest[1] < 0.99:
        reason = {
            'táv': 'a táv nem illett hozzá',
            'pálya': 'a pálya jellege nem kedvezett neki',
            'frissesség': 'fáradtan érkezett',
            'zsoké': 'a zsoké nem tudott többet kihozni belőle',
        }[weakest[0]]
        notes.append(reason)
    if strongest[1] > 1.01:
        reason = {
            'táv': 'a táv testhezálló volt',
            'pálya': 'a pálya jellege segítette',
            'frissesség': 'frissen érkezett',
            'zsoké': 'a zsoké jól időzített',
        }[strongest[0]]
        notes.append(reason)

    if pos == 1:
        finish = 'és megnyerte a futamot'
    elif pos <= 3:
        finish = f'és a {pos}. helyen ért célba'
    elif pos <= field_size / 2:
        finish = f'és a {pos}. helyen végzett'
    else:
        finish = f'és csak a {pos}. helyre futott be'

    line = f"{start}, {finish}."
    if notes:
        line += ' ' + (notes[0][0].upper() + notes[0][1:]) + '.'
    return line


# =======================================================================
# 8) NYEREMENY-ELOSZTAS
# =======================================================================
# A valos galoppban a dij nagy resze a gyoztese, de a top 4-5 kap
# valamit. Ez a standard amerikai elosztas.
PURSE_SPLIT = [0.60, 0.20, 0.11, 0.06, 0.03]


def distribute_purse(total_purse, results):
    """Ki mennyit keresett?"""
    payouts = {}
    for r in results:
        pos = r['position']
        share = PURSE_SPLIT[pos - 1] if pos <= len(PURSE_SPLIT) else 0.0
        payouts[r['horse']['name']] = int(round(total_purse * share))
    return payouts


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - RACE SIMULATION ENGINE v1.0 ===\n")

    demo_race = {
        'name': 'Ashcombe — 20 000 alatt',
        'band': 'mile',
        'style_bias': 'korai sebesség',
        'bracket': 'b20',
        'purse': 5400,
    }

    print("--- 1) EGY FUTAM LEFUTTATASA ---")
    rng = random.Random(7)
    field = generate_field('b20', size=8, rng=rng)
    outcome = run_race(field, demo_race, rng)

    print(f"  {demo_race['name']}  ·  {demo_race['band']}  ·  díj {demo_race['purse']} B$\n")
    payouts = distribute_purse(demo_race['purse'], outcome['results'])
    for r in outcome['results']:
        h = r['horse']
        fav = ' ★' if r is outcome['favourite'] else '  '
        pay = payouts[h['name']]
        pay_s = f"{pay:>6d} B$" if pay else '        —'
        print(f"  {r['position']}.{fav} {h['name']:14s} sáv {h['fill_bar']:5.1f}  "
              f"{STYLE_LABELS_HU[h['style']]:14s} {pay_s}")
    print(f"\n  ★ = a papírforma szerinti favorit")
    print(f"  Győztes: {outcome['winner']['horse']['name']} — "
          f"{'a favorit nyert' if outcome['favourite_won'] else 'meglepetés'}\n")

    print("  Futásleírások:")
    for r in outcome['results'][:4]:
        print(f"    {r['horse']['name']:14s} {describe_run(r, demo_race, len(field))}")
    print()

    # ------------------------------------------------------------------
    print("--- 2) KALIBRACIO: gyoz-e a favorit a valos aranyban? ---")
    print("  Cél (valós adat): a favorit a futamok 30-35%-át nyeri.\n")

    N = 20000
    rng = random.Random(1234)
    fav_wins = 0
    second_wins = 0
    top4_contains_winner = 0
    for _ in range(N):
        f = generate_field('b20', size=8, rng=rng)
        out = run_race(f, demo_race, rng)
        ranked_by_form = sorted(out['results'], key=lambda r: -r['deterministic'])
        if out['favourite_won']:
            fav_wins += 1
        if ranked_by_form[1]['position'] == 1:
            second_wins += 1
        if out['winner'] in ranked_by_form[:4]:
            top4_contains_winner += 1

    fav_pct = fav_wins / N * 100
    second_pct = second_wins / N * 100
    top4_pct = top4_contains_winner / N * 100

    print(f"  Favorit győzelmi aránya:     {fav_pct:5.1f}%   (valós: 30-35%)")
    print(f"  Második favorit:             {second_pct:5.1f}%   (valós: ~19%)")
    print(f"  A győztes a top 4 formában:  {top4_pct:5.1f}%   (valós: ~82%)\n")

    # ------------------------------------------------------------------
    print("--- 3) SZAMIT-E A TAVPROFIL? ---")
    print("  MEGJEGYZES a valos 32%/24% adatrol: az odds-savra ILLESZTETT")
    print("  (3-7/1) lovakat hasonlit ossze, ahol a piac mar beárazta a")
    print("  kulonbseget. Az alabbi teszt AZONOS kepessegu lovakat allit")
    print("  szembe, ezert nem kozvetlenul osszemerheto - nagyobb kulonbseget")
    print("  varunk. A cel: erezheto, de nem dominans hatas.\n")
    rng = random.Random(99)
    matched_wins = 0
    unmatched_wins = 0
    TRIALS = 12000
    for _ in range(TRIALS):
        f = generate_field('b20', size=8, rng=rng)
        # az elso lonak kedvelt tav, a masodiknak nem
        f[0]['profile']['mile'] = 92
        f[1]['profile']['mile'] = 34
        f[1]['fill_bar'] = f[0]['fill_bar']   # azonos alap
        out = run_race(f, demo_race, rng)
        if out['winner']['horse'] is f[0]:
            matched_wins += 1
        if out['winner']['horse'] is f[1]:
            unmatched_wins += 1
    m_pct = matched_wins / TRIALS * 100
    u_pct = unmatched_wins / TRIALS * 100
    print(f"  Azonos képességű ló, kedvelt távján:      {m_pct:5.1f}%")
    print(f"  Ugyanaz, nem kedvelt távján:              {u_pct:5.1f}%")
    print(f"  Arány: {m_pct/u_pct if u_pct else 0:.2f}×   (valós: 32/24 = 1.33×)\n")

    # ------------------------------------------------------------------
    print("--- 4) ERZODIK-E A FELNEVELES? (a 15 szazalekpontnyi elony) ---")
    rng = random.Random(555)
    well_reared_wins = 0
    TRIALS = 12000
    for _ in range(TRIALS):
        f = generate_field('b20', size=8, rng=rng)
        base = statistics.mean(h['fill_bar'] for h in f)
        f[0]['fill_bar'] = base + 7.5     # jól nevelt
        f[1]['fill_bar'] = base - 7.5     # elhanyagolt
        out = run_race(f, demo_race, rng)
        if out['winner']['horse'] is f[0]:
            well_reared_wins += 1
    wr_pct = well_reared_wins / TRIALS * 100
    print(f"  A 15 százalékponttal jobban felnevelt ló győzelmi aránya")
    print(f"  nyolclovas mezőnyben: {wr_pct:5.1f}%  (véletlen alap: 12.5%)")
    print(f"  -> {wr_pct/12.5:.1f}× esély. A felnevelés ÉRZŐDIK a pályán.\n")

    # ------------------------------------------------------------------
    print("--- 5) SZAMIT-E A PALYA JELLEGE? ---")
    rng = random.Random(321)
    for bias in ['korai sebesség', 'kitartás']:
        r2 = dict(demo_race, style_bias=bias)
        style_wins = Counter()
        TRIALS = 8000
        for _ in range(TRIALS):
            f = generate_field('b20', size=8, rng=rng)
            out = run_race(f, r2, rng)
            style_wins[out['winner']['horse']['style']] += 1
        total = sum(style_wins.values())
        parts = ', '.join(f"{STYLE_LABELS_HU[s]}: {style_wins[s]/total*100:4.1f}%"
                          for s in RunningStyle)
        print(f"  {bias:16s} -> {parts}")
    print("  -> Rövid célegyenesű pályán a korán elmenők, hosszún a hajrázók nyernek többet.\n")

    # ------------------------------------------------------------------
    print("--- 6) VALIDACIO ---")
    checks = [
        ('A favorit a valós 30-35%-os sávban nyer', 30.0 <= fav_pct <= 35.0),
        ('A második favorit a 15-24%-os sávban', 15.0 <= second_pct <= 24.0),
        ('A győztes túlnyomórészt a top 4 formából kerül ki', top4_pct >= 75.0),
        ('A távprofil érezhetően számít (>1.5× azonos képesség mellett)',
         (m_pct / u_pct if u_pct else 0) >= 1.5),
        ('De nem dominál (<3×) — a képesség marad a fő tényező',
         (m_pct / u_pct if u_pct else 0) <= 3.0),
        ('A felnevelés érdemben érződik (legalább 2× esély)', wr_pct >= 25.0),
        ('De nem determinisztikus (a jól nevelt sem nyer mindig)', wr_pct <= 60.0),
        ('A frissesség 60% alatt ront', freshness_factor(40) < 1.0),
        ('60% felett nincs frissesség-büntetés', freshness_factor(75) == 1.0),
        ('A díj nagy része a győztesé', PURSE_SPLIT[0] >= 0.55),
        ('A teljes díj kiosztásra kerül', abs(sum(PURSE_SPLIT) - 1.0) < 0.001),
        ('A futásleírás minden helyezésre működik',
         all(len(describe_run(r, demo_race, 8)) > 20 for r in outcome['results'])),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - HANGOLANDO'} ===")
