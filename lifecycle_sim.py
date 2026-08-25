"""
Breeder Tycoon - Lifecycle Engine v1.0
=======================================================================
AZ ELETCIKLUS-CSIKOK. Ezek hatarozzak meg, meddig el egy lo a
jatekban, es meddig hasznalhato.

NEGY CSIK, kulonbozo termeszettel:

  1. ELET-CSIK      - a mesteróra. Minden mas alatta fut. Fogy, nem
                      tolthető vissza.
  2. VERSENYKARRIER - a versenylo hatralevo palyafutasa. A tenyesztesre
                      valtaskor ELVESZIK.
  3. FRISSESSEG     - az EGYETLEN visszatoltodo csik. Ez gatolja a
                      pihentetes nelkuli futtatast.
  4. TENYESZCSIK    - a tenyeszallat hatralevo utodszama. A verseny-
                      karrier hosszabol szarmazik.

A JATEKOS ALAPELVEI:
  - NINCS ELHULLAS. A csik kifutasa nyugdijazast jelent, nem halalt.
  - A kedves lo ne essen ki hamar: a nyugdijazott lo a jatekban marad,
    pedigrekben es utodlistakon szerepel (stabling_sim.py).
  - A tenyeszcsik SOSEM lehet 100%-os a versenykarrier utan.

=======================================================================
IDOSKALA (season_sim.py: 1 szezon = 1 jatekev = 1 valos honap)
=======================================================================
  Versenykarrier 6-8 szezon   ->  6-8 valos honap
  Kanca teljes palyafutasa    ->  ~13 valos honap
  Men (jo ivadekkal)          ->  ~2 valos ev

=======================================================================
FORRASOK
=======================================================================

1. Atlagos versenylo-karrier: 4.5 ev.
   https://www.equineinfoexchange.com/racing/the-life-of-a-race-horse

2. Anyakanca: atlagosan 4-10 csiko egy elet alatt, leggyakrabban ot
   vagy hat. A produktiv anyakanca inkabb tizenharom korul, ot es
   tizenhet kozott.
   https://www.horseforum.com/threads/how-many-foals-can-a-mare-have.786698/

3. A kor a legerosebb elorejelzo: a 10 evesnel fiatalabb kancak
   csaknem HAROMSZOR nagyobb esellyel hoztak elo csikot. A termekenyseg
   kb. 15 eves kortol hanyatlik.
   https://ker.com/equinews/mare-age-biggest-predictor-of-foaling-success/

4. "Use it or lose it": azok a kancak, akik a kesoi tinedzser eveikben
   tobb szabadevet kapnak, nagyon nehezen hozhatok vissza vemhesbe.
   https://thehorse.com/features/broodmare-management-older-mares/

5. Pihenes ket start kozott: a hosszabb piheno kb. 3 hetig javitja az
   eredmenyt, utana romlik - azaz van egy OPTIMALIS SAV.
   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8614314/

6. Serules-hatas: a soundness-romlas gyorsitja az elet-csik fogyasat
   (Oki et al. 2008, Welsh et al. 2013 - lasd breeding_sim.py).
"""

import math
from enum import Enum


# =======================================================================
# 1) ELET-CSIK
# =======================================================================
# A mesteróra. Osszetetele a korabbi dontés szerint:
#   genetika 50% + egeszsegi esemenyek 30% + tartasi korulmenyek 20%
# Ezek NEM a csik hosszat adjak, hanem a FOGYAS SEBESSEGET moditjak.
LIFE_BAR_MAX = 100.0
BASE_LIFE_SEASONS = 22          # atlagos teljes elettartam szezonban
                                # (a valos 25-30 ev, de a jatekban a
                                # hasznos eletszakasz a lenyeges)

LIFE_DECAY_WEIGHTS = {
    'genetics': 0.50,           # soundness alapu
    'health_events': 0.30,      # serulesek, betegsegek
    'husbandry': 0.20,          # tartas, takarmanyozas minosege
}


def life_decay_per_season(soundness, injuries_total=0, husbandry_quality=0.6):
    """Mennyit fogy az elet-csik egy szezonban?

    soundness:  5-99 (breeding_sim.py)
    injuries_total: az eddigi serulesek szama
    husbandry_quality: 0-1, a tartas/takarmanyozas minosege
    """
    base = LIFE_BAR_MAX / BASE_LIFE_SEASONS      # ~4.55 / szezon

    # genetika: a gyenge soundness gyorsitja
    g = (60.0 / max(20.0, soundness)) ** 0.9

    # egeszsegi esemenyek: minden serules tartos nyomot hagy
    h = 1.0 + injuries_total * 0.06

    # tartas: a jo korulmenyek lassitjak
    k = 1.25 - husbandry_quality * 0.45

    modifier = (g * LIFE_DECAY_WEIGHTS['genetics']
                + h * LIFE_DECAY_WEIGHTS['health_events']
                + k * LIFE_DECAY_WEIGHTS['husbandry'])

    return round(base * modifier, 3)


def life_expectancy(soundness, injuries_total=0, husbandry_quality=0.6):
    """Hany szezont el meg a lo a jelenlegi korulmenyek mellett?"""
    d = life_decay_per_season(soundness, injuries_total, husbandry_quality)
    return round(LIFE_BAR_MAX / d, 1)


# =======================================================================
# 2) VERSENYKARRIER-CSIK
# =======================================================================
# 100% = kb. 6 szezon versenyzes. A valos atlag 4.5 ev (forras 1.),
# a jatekban ennel bovebbre szabva, hogy legyen ter a dontesekre.
CAREER_BAR_MAX = 100.0
CAREER_SEASONS_AT_FULL = 6.5
STARTS_PER_SEASON_REFERENCE = 5


def career_cost_per_start(race_class_weight=1.0, going_hard=False, distance_f=8):
    """Mennyit fogyaszt egy start a versenykarrier-csikbol?

    A nehezebb futam es a nehez talaj tobbet visz.
    """
    base = CAREER_BAR_MAX / (CAREER_SEASONS_AT_FULL * STARTS_PER_SEASON_REFERENCE)
    mult = race_class_weight
    if going_hard:
        mult *= 1.15
    mult *= 1.0 + max(0, distance_f - 8) * 0.02
    return round(base * mult, 3)


def career_remaining_seasons(career_bar, starts_per_season=STARTS_PER_SEASON_REFERENCE):
    per_start = career_cost_per_start()
    return round(career_bar / (per_start * starts_per_season), 1)


# =======================================================================
# 3) FRISSESSEG-CSIK - az EGYETLEN visszatoltodo
# =======================================================================
# season_sim.py: teljes visszatoltodes ~3 jatekhet = ~41 valos ora.
# 60% alatt kezd rontani (race_sim.py freshness_factor).
FRESHNESS_MAX = 100.0
FRESHNESS_PENALTY_THRESHOLD = 60.0
FRESHNESS_COST_PER_START = 35.0
FRESHNESS_RECOVERY_PER_DAY = 100.0 / 1.75      # ~2 nap alatt teljes


def freshness_after_start(current):
    return round(max(0.0, current - FRESHNESS_COST_PER_START), 1)


def freshness_recover(current, real_days, walker_bonus=1.0):
    """A jartatogep (farm_sim.py) gyorsitja a visszatoltodest."""
    gain = FRESHNESS_RECOVERY_PER_DAY * real_days * walker_bonus
    return round(min(FRESHNESS_MAX, current + gain), 1)


def days_to_full(current, walker_bonus=1.0):
    if current >= FRESHNESS_MAX:
        return 0.0
    return round((FRESHNESS_MAX - current) /
                 (FRESHNESS_RECOVERY_PER_DAY * walker_bonus), 2)


def freshness_ready(current):
    """Futtathato-e a lo buntetes nelkul?"""
    return current >= FRESHNESS_PENALTY_THRESHOLD


# =======================================================================
# 4) TENYESZCSIK
# =======================================================================
# A JATEKOS DONTESE: a versenykarrier utan kapott tenyeszcsik SOSEM
# lehet 100%-os. Minel tovabb futott a lo, annal kevesebb marad.
#
# A valos adat (forras 2.): 4-10 csiko egy elet alatt, leggyakrabban
# ot vagy hat. A 100%-os csik ~10 csikonak felel meg, es az atlagos
# karrier utani ~65% pontosan az 6-7 csikot ad - egyezik a valossal.
BREEDING_BAR_MAX = 100.0
FOALS_AT_FULL_BAR = 10

CAREER_TO_BREEDING = [
    # (elhasznalt versenykarrier %, kapott tenyeszcsik %)
    (0,   90),      # sosem futott
    (20,  80),      # 1-2 szezon
    (50,  65),      # 3-4 szezon - a valos atlag
    (75,  50),      # 5-6 szezon
    (100, 35),      # teljes karrier
]


def breeding_bar_from_career(career_used_pct):
    """Mennyi tenyeszcsikot kap a lo a versenykarrier utan?"""
    pts = CAREER_TO_BREEDING
    if career_used_pct <= pts[0][0]:
        return float(pts[0][1])
    if career_used_pct >= pts[-1][0]:
        return float(pts[-1][1])
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= career_used_pct <= x1:
            t = (career_used_pct - x0) / (x1 - x0)
            return round(y0 + (y1 - y0) * t, 1)
    return float(pts[-1][1])


def foals_remaining(breeding_bar):
    return round(breeding_bar / BREEDING_BAR_MAX * FOALS_AT_FULL_BAR, 1)


BREEDING_COST_PER_FOAL = BREEDING_BAR_MAX / FOALS_AT_FULL_BAR   # 10


def breeding_cost(mare_age, rested_last_season=False):
    """Egy csiko mennyit fogyaszt a tenyeszcsikbol?

    Az idosebb kanca tobbet - a termekenyseg hanyatlik (forras 3.).
    A "use it or lose it" (forras 4.): a kihagyott szezon extra
    fogyast okoz.
    """
    cost = BREEDING_COST_PER_FOAL
    if mare_age >= 15:
        cost *= 1.30
    elif mare_age >= 11:
        cost *= 1.12
    if rested_last_season and mare_age >= 14:
        cost *= 1.25       # use it or lose it
    return round(cost, 2)


# =======================================================================
# 5) ALLAPOTOK ES ATMENETEK
# =======================================================================
class Stage(Enum):
    FOAL = 'foal'
    YEARLING = 'yearling'
    RACER = 'racer'
    BREEDING = 'breeding'
    PENSIONED = 'pensioned'


STAGE_LABELS = {
    Stage.FOAL: 'Csikó', Stage.YEARLING: 'Yearling', Stage.RACER: 'Versenyló',
    Stage.BREEDING: 'Tenyészállat', Stage.PENSIONED: 'Nyugdíjas',
}


def new_horse_bars(genetics_score=60):
    return {
        'life': LIFE_BAR_MAX,
        'career': CAREER_BAR_MAX,
        'freshness': FRESHNESS_MAX,
        'breeding': None,           # csak a valtaskor keletkezik
        'stage': Stage.FOAL,
        'career_used': 0.0,
    }


def retire_to_breeding(bars):
    """Versenylobol tenyeszallat: a VERSENYKARRIER-CSIK ELVESZIK,
    helyette tenyeszcsikot kap - de sosem 100%-osat."""
    used = bars['career_used']
    return {
        **bars,
        'career': 0.0,
        'breeding': breeding_bar_from_career(used),
        'stage': Stage.BREEDING,
        'note': (f'A versenykarrier lezárult ({used:.0f}% elhasználva). '
                 f'Tenyészcsík: {breeding_bar_from_career(used):.0f}% '
                 f'(~{foals_remaining(breeding_bar_from_career(used)):.0f} csikó).'),
    }


def check_retirement(bars):
    """Kifutott-e valamelyik csik? NINCS elhullas - nyugdijazas van."""
    if bars['life'] <= 0:
        return {'retire': True, 'reason': 'Az élet-csík kifutott — nyugdíjba vonul.'}
    if bars['stage'] == Stage.RACER and bars['career'] <= 0:
        return {'retire': True, 'reason': 'A versenykarrier véget ért.'}
    if bars['stage'] == Stage.BREEDING and (bars['breeding'] or 0) <= 0:
        return {'retire': True, 'reason': 'A tenyészcsík kifutott — nyugdíjba vonul.'}
    return {'retire': False, 'reason': None}


# =======================================================================
# 6) AMIT A JATEKOS LAT
# =======================================================================
def bar_label(value, maximum=100.0):
    pct = value / maximum * 100
    if pct >= 80: return 'Kiváló'
    if pct >= 60: return 'Jó'
    if pct >= 40: return 'Közepes'
    if pct >= 20: return 'Fogyóban'
    return 'Kifutóban'


def describe_bars(bars):
    """A jatekosnak megjelenitett allapot. NYERS szazalek helyett savok -
    ugyanaz az elv, mint az A-E indexnel."""
    out = [f"Élet: {bar_label(bars['life'])}"]
    if bars['stage'] == Stage.RACER:
        out.append(f"Karrier: {bar_label(bars['career'])}")
        out.append(f"Frissesség: {bar_label(bars['freshness'])}"
                   + ('' if freshness_ready(bars['freshness']) else ' — pihenőre szorul'))
    if bars['stage'] == Stage.BREEDING and bars['breeding'] is not None:
        out.append(f"Tenyészcsík: {bar_label(bars['breeding'])} "
                   f"(~{foals_remaining(bars['breeding']):.0f} csikó)")
    return ' · '.join(out)


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - LIFECYCLE ENGINE v1.0 ===\n")

    print("--- 1) ELET-CSIK: genetika 50% + egészség 30% + tartás 20% ---")
    print("  Nem a csík hosszát adják, hanem a FOGYÁS SEBESSÉGÉT.\n")
    print(f"  {'Soundness':>10s} {'Sérülés':>8s} {'Tartás':>8s} "
          f"{'Fogyás/szezon':>14s} {'Várható élettartam':>19s}")
    for snd, inj, hus in [(90, 0, 0.9), (60, 0, 0.6), (60, 3, 0.6),
                          (35, 0, 0.6), (35, 4, 0.3)]:
        d = life_decay_per_season(snd, inj, hus)
        e = life_expectancy(snd, inj, hus)
        print(f"  {snd:>10d} {inj:>8d} {hus:>8.1f} {d:>14.2f} "
              f"{e:>16.1f} szezon")
    print()

    print("--- 2) VERSENYKARRIER ---")
    print(f"  100% ≈ {CAREER_SEASONS_AT_FULL} szezon "
          f"({STARTS_PER_SEASON_REFERENCE} start/szezon mellett)")
    print(f"  Valós referencia: az átlagos versenyló-karrier 4,5 év.\n")
    print(f"  {'Futam típusa':28s} {'Karrier-fogyás':>15s}")
    for label, w, hard, dist in [('Sima futam, jó talaj', 1.0, False, 8),
                                 ('Nehéz talaj', 1.0, True, 8),
                                 ('Hosszútáv (14f)', 1.0, False, 14),
                                 ('Nagyverseny, nehéz talaj', 1.4, True, 12)]:
        print(f"  {label:28s} {career_cost_per_start(w, hard, dist):>15.2f}")
    print()

    print("--- 3) FRISSESSEG: az egyetlen visszatoltodo csik ---")
    f = FRESHNESS_MAX
    print(f"  Kiindulás: {f:.0f}%\n")
    for i in range(1, 4):
        f = freshness_after_start(f)
        ready = 'futtatható' if freshness_ready(f) else 'PIHENŐRE SZORUL'
        print(f"  {i}. start után: {f:>5.1f}%  ({ready})  "
              f"teljes visszatöltés: {days_to_full(f)} nap")
    print(f"\n  Jártatógéppel (farm_sim.py, 1,28×): "
          f"{days_to_full(f, 1.28)} nap\n")

    print("--- 4) TENYESZCSIK: a versenykarrier hosszabol ---")
    print("  A tenyészcsík SOSEM 100%-os. Minél tovább futott, annál kevesebb.\n")
    print(f"  {'Versenykarrier':>16s} {'Tenyészcsík':>13s} {'≈ Csikó':>9s}")
    for used, label in [(0, 'sosem futott'), (20, '1-2 szezon'),
                        (50, '3-4 szezon'), (75, '5-6 szezon'),
                        (100, 'teljes karrier')]:
        b = breeding_bar_from_career(used)
        print(f"  {label:>16s} {b:>12.0f}% {foals_remaining(b):>9.1f}")
    print(f"\n  Valós referencia: 4-10 csikó egy élet alatt, leggyakrabban 5-6.")
    print(f"  A modell átlagos karrier után 6,5 csikót ad — egyezik.\n")

    print("--- 5) A KOR ES A KIHAGYOTT SZEZON HATASA ---")
    print(f"  {'Kanca kora':>11s} {'Pihentetett':>12s} {'Csikó-költség':>15s} "
          f"{'≈ Hátralévő csikó 65%-ból':>26s}")
    for age, rested in [(6, False), (12, False), (16, False), (16, True)]:
        c = breeding_cost(age, rested)
        rem = round(65 / c, 1)
        r = 'igen' if rested else 'nem'
        print(f"  {age:>11d} {r:>12s} {c:>15.2f} {rem:>24.1f}")
    print("\n  A 'use it or lose it' hatás: a kihagyott szezon idős kancánál")
    print("  extra fogyást okoz — a pihentetés véglegesen csökkenti a csíkot.\n")

    print("--- 6) EGY LO TELJES ELETUTJA ---")
    bars = new_horse_bars()
    bars['stage'] = Stage.RACER
    print(f"  Versenybe állás: {describe_bars(bars)}\n")

    season = 0
    while bars['career'] > 0 and season < 10:
        season += 1
        for _ in range(STARTS_PER_SEASON_REFERENCE):
            cost = career_cost_per_start()
            bars['career'] = max(0, bars['career'] - cost)
            bars['career_used'] = CAREER_BAR_MAX - bars['career']
        bars['life'] -= life_decay_per_season(65, season // 3, 0.7)
        if season in (2, 4, 6):
            print(f"  {season}. szezon után: {describe_bars(bars)}")
        if bars['career'] <= 0:
            break

    print(f"\n  A versenykarrier a {season}. szezonban ért véget.")
    bred = retire_to_breeding(bars)
    print(f"  {bred['note']}")
    print(f"  Új állapot: {describe_bars(bred)}\n")

    foals = 0
    age = 4 + season
    while (bred['breeding'] or 0) > 0 and bred['life'] > 0:
        cost = breeding_cost(age)
        bred['breeding'] -= cost
        bred['life'] -= life_decay_per_season(65, 3, 0.7)
        age += 1
        foals += 1
        if foals > 20:
            break
    print(f"  Tenyésztésben {foals} csikót adott, {age} éves koráig.")
    ret = check_retirement(bred)
    print(f"  {ret['reason']}")
    print(f"  A ló NEM tűnik el — a pedigrékben és az utódlistákon marad.\n")

    print("--- 7) VALIDACIO ---")
    checks = [
        ('A jó soundness érdemben hosszabb életet ad',
         life_expectancy(90, 0, 0.9) > life_expectancy(35, 0, 0.6) * 1.3),
        ('A sérülések gyorsítják az élet-csík fogyását',
         life_decay_per_season(60, 4) > life_decay_per_season(60, 0)),
        ('A jó tartás lassítja a fogyást',
         life_decay_per_season(60, 0, 0.9) < life_decay_per_season(60, 0, 0.3)),
        ('A teljes versenykarrier kb. 6-7 szezon',
         6.0 <= career_remaining_seasons(CAREER_BAR_MAX) <= 7.5),
        ('A nehezebb futam többet visz a karrierből',
         career_cost_per_start(1.4, True, 12) > career_cost_per_start(1.0, False, 8)),
        ('A frissesség 3 start után büntetéses sávba kerül',
         not freshness_ready(freshness_after_start(
             freshness_after_start(freshness_after_start(100.0))))),
        ('A frissesség kb. 2 nap alatt töltődik vissza',
         1.5 <= days_to_full(0) <= 2.0),
        ('A jártatógép gyorsítja a visszatöltődést',
         days_to_full(50, 1.28) < days_to_full(50, 1.0)),
        ('A tenyészcsík SOSEM 100%-os',
         all(breeding_bar_from_career(u) < 100 for u in range(0, 101, 10))),
        ('Sosem futott ló kapja a legtöbbet (90%)',
         breeding_bar_from_career(0) == 90),
        ('Teljes karrier után a legkevesebbet (35%)',
         breeding_bar_from_career(100) == 35),
        ('Az átlagos karrier ~6-7 csikót ad (valós: 5-6)',
         6.0 <= foals_remaining(breeding_bar_from_career(50)) <= 7.0),
        ('Az idős kanca több csíkot fogyaszt csikónként',
         breeding_cost(16) > breeding_cost(6)),
        ('A kihagyott szezon idős kancánál extra fogyás',
         breeding_cost(16, True) > breeding_cost(16, False)),
        ('A csík kifutása nyugdíjazás, nem elhullás',
         'nyugdíj' in check_retirement(
             {'life': 0, 'stage': Stage.BREEDING, 'career': 0, 'breeding': 0})['reason'].lower()),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
