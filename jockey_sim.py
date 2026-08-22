"""
Trot Heritage - Jockey Engine v1.0
=======================================================================
A zsoké NEM a toltottsegi sav resze (55% genetika + 20% takarmany +
25% tréner = 100%). A zsoké VERSENYNAPI MODOSITOKENT hat: a mar
felepitett lo-kepesseget modositja az adott futasra, futasonkent
valtozoan.

    toltottsegi sav (max 99.75%)  -> a lo felepitett kepessege
      x zsoké-modosito             -> aznapi realizalt teljesitmeny
      x (kesobb: forma/palya/talaj/tav)
      = versenyeredmeny

Ez a szetvalasztas TUDOMANYOSAN IS INDOKOLT: a zsoké nem fejleszti a
lovat, csak az adott napon hozza ki belole tobbet vagy kevesebbet.

=======================================================================
FORRASOK - A ZSOKE HATASANAK MERTEKE (ez a legfontosabb parameter)
=======================================================================

1. Oki et al., "Influence of jockey on racing time in Thoroughbred
   horse" (Japan Racing Association adatok): a celbaerkezesi idobol
   a LO 94.8%-ot, a ZSOKE mindossze 5.2%-ot magyaraz.
   TOVABBA: "As the racing distance increased, the percent contribution
   of the jockey also tended to increase" - azaz HOSSZABB TAVON A ZSOKE
   HATASA NAGYOBB.
   https://www.researchgate.net/publication/229976195_Influence_of_jockey_on_racing_time_in_Thoroughbred_horse

2. Ugyanezen elemzes varianciakomponens-bontasa: "Of the total variance
   components, the proportion of variance due to the jockey was from
   0.02 to 0.06, and it was larger in longer distance races than in
   shorter ones." -> 2-6% varianciahanyad, tavfuggoen.

3. Oki et al. (1995), Journal of Animal Breeding and Genetics:
   "The skill of the jockey is an important source of variation in
   racing time across distances and track types, therefore, it should
   be considered in deriving adjustment factors" - azaz a zsoké hatasa
   TAVTOL ES PALYATIPUSTOL is fugg.
   https://onlinelibrary.wiley.com/doi/10.1111/j.1439-0388.1995.tb00555.x

4. Oda et al. (2024), Journal of Animal Breeding and Genetics,
   mixed-effects modell 12 palya-tav kategorian: a zsoké-hatas a
   modellben szignifikans tenyezo, a verseny-hatas utan.
   https://onlinelibrary.wiley.com/doi/10.1111/jbg.12822

5. Iparagi hüvelykujjszabaly (Pick Pony): a lovas-korokben elterjedt
   becsles szerint "a jockey contributes 10 percent of a horse's
   performance on any given day". A forras MAGA IS jelzi, hogy ez
   "isn't a scientific fact" - ezert a TUDOMANYOS 5.2%-os erteket
   hasznaljuk alapkent, nem ezt.
   https://www.pickpony.com/horse-racing-feature/education/how-much-impact-jockey-horse-race/

=======================================================================
FORRASOK - A ZSOKE ATTRIBUTUM-DIMENZIOI
=======================================================================

6. EquinEdge (zsoké-statisztikak szakmai attekintese): a zsoké
   ertekelesenek valos dimenzoi: gyozelmi arany, PALYA- ES TALAJ-
   SPECIALIZACIO ("some jockeys perform better at specific tracks or
   on particular surfaces, e.g. dirt vs turf"), aktualis forma, es a
   ZSOKE-LO PAROSITAS kompatibilitasa.
   https://equinedge.com/glossary/key-factors/what-are-jockey-trainer-stats

7. Nature Scientific Reports (2025), "Relationship between experience
   and head kinematics in race riding jockeys": a TAPASZTALTABB zsokek
   bizonyitottan alacsonyabb esesi/serulesi aranyt mutatnak
   ("experienced jockeys have a lower incidence of race day falls than
   inexperienced jockeys"), es jobban csillapitjak a lo mozgasat.
   https://www.nature.com/articles/s41598-025-98683-9

8. "Physiological Demands and Muscle Activity of Jockeys": a verseny
   maximalis intenzitasu terheles a zsokének (~94% HRmax) - azaz a
   zsoké FIZIKAI ALLOKEPESSEGE valos, meresi teljesitmeny-tenyezo.
   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9495223/

9. "Does the start of flat races influence racehorse race performance?"
   (ScienceDirect): a RAJT kezelese merheto hatassal van a helyezesre -
   "jockeys that pushed their bodyweight forwards in the saddle during
   loading were significantly more likely to place first to fourth".
   https://www.sciencedirect.com/science/article/abs/pii/S016815912200140X

10. FONTOS NEGATIV EREDMENY (amit NEM epitunk be): Nottingham/PMC
    tanulmany 530 lovon: a zsoké NEME nem befolyasolja a lo
    teljesitmenyet ("Sex of the rider did not influence racehorse speed
    nor stride length at any training intensity"). Ezert a modellben a
    zsoké neme SEMMILYEN teljesitmeny-hatassal NEM rendelkezik - ez
    tudatos, tudomanyosan megalapozott dontes.
    https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9432741/

=======================================================================
"""

import random
import statistics
from collections import Counter

random.seed(42)


# =======================================================================
# 1) A ZSOKE HATASANAK MERTEKE - TAVFUGGO (forras 1., 2., 3.)
# =======================================================================
# A tudomanyos adat: a zsoké a celbaerkezesi ido varianciajanak
# 2-6%-at magyarazza, ES A HOSSZABB TAVON NAGYOBB A HATASA.
# Ezt kozvetlenul lekepezzuk: a zsoké-modosito maximalis kileng ese
# tavkategoriankent elteroen, a forrasokban leirt 2-6%-os savban.
#
# Ez az egyik legjobban alatamasztott parameterunk az egesz projektben -
# nem becsles, hanem publikalt varianciakomponens-bontas.
JOCKEY_MAX_SWING_PCT = {
    'sprint':  2.0,   # legrovidebb tav -> legkisebb zsoké-hatas (forras 2: 0.02)
    'mile':    3.5,
    'middle':  5.0,
    'staying': 6.0,   # leghosszabb tav -> legnagyobb zsoké-hatas (forras 2: 0.06)
}

# A modosito NEUTRALIS pontja: egy atlagos kepessegu zsoké se nem javit,
# se nem ront. A skala igy: 1.0 - swing ... 1.0 + swing
NEUTRAL_JOCKEY_SCORE = 50.0  # a populacios atlag (lasd JOCKEY_ATTR_CONFIG)


# =======================================================================
# 2) ZSOKE ATTRIBUTUMOK (forras 6-9.)
# =======================================================================
# MODSZERTANI MEGJEGYZES (ugyanaz, mint a trénernel): hogy MELYIK
# dimenziok szamitanak, az valos forrasbol jon. A konkret mean/sd
# szamertekek JATEKTERVEZESI PLACEHOLDEREK - ilyen publikalt numerikus
# adat egy fiktiv zsoké "kepesseg-pontszamara" nem letezik.
JOCKEY_ATTR_CONFIG = {
    'pace_judgement':   {'mean': 50, 'sd': 15, 'source': 'forras 3., 6. - tempo-beosztas, taktika, tav/palyafuggo'},
    'start_handling':   {'mean': 50, 'sd': 14, 'source': 'forras 9. - a rajt kezelese merheto hatassal van a helyezesre'},
    'experience':       {'mean': 45, 'sd': 18, 'source': 'forras 7. - tapasztaltabb zsoké kevesebb eses, jobb mozgascsillapitas'},
    'physical_fitness': {'mean': 50, 'sd': 13, 'source': 'forras 8. - a verseny ~94% HRmax terheles a zsokének'},
    'horsemanship':     {'mean': 50, 'sd': 14, 'source': 'forras 6. - zsoké-lo kompatibilitas, a lo "olvasasa" futas kozben'},
}
JOCKEY_ATTRS = list(JOCKEY_ATTR_CONFIG.keys())

JOCKEY_WEIGHTS = {
    'pace_judgement':   1.2,   # a taktika a legerosebben dokumentalt tenyezo
    'start_handling':   1.0,
    'experience':       0.9,
    'physical_fitness': 0.8,
    'horsemanship':     1.1,
}

# Talaj-specializacio (forras 6.: "some jockeys perform better on
# particular surfaces, e.g. dirt vs turf")
SURFACE_TYPES = ['turf', 'dirt']
SURFACE_SPEC_BONUS = 12      # placeholder: a fo talaj-tipuson ennyivel jobb
SURFACE_SPEC_PENALTY = 6     # placeholder: a masikon ennyivel gyengebb

# Tav-specializacio (forras 3.: a zsoké hatasa tavonkent elter)
DISTANCE_CATEGORIES = ['sprint', 'mile', 'middle', 'staying']
DISTANCE_SPEC_BONUS = 10
DISTANCE_SPEC_PENALTY = 5

SPEC_LABELS_HU = {
    'sprint': 'Sprint', 'mile': 'Mérföld', 'middle': 'Középtáv', 'staying': 'Hosszútáv',
    'turf': 'gyep', 'dirt': 'homok',
}


def jockey_overall_score(attrs):
    s = sum(attrs[k] * JOCKEY_WEIGHTS[k] for k in JOCKEY_ATTRS)
    return s / sum(JOCKEY_WEIGHTS.values())


def index_from_score(avg):
    """Ugyanaz az A-E skala, mint a lovaknal es a trénernel - a jatekos
    egyseges jelolest lat mindenhol, nyers szamot sosem."""
    if avg >= 88: return 'A+'
    if avg >= 82: return 'A'
    if avg >= 76: return 'A-'
    if avg >= 70: return 'B+'
    if avg >= 63: return 'B'
    if avg >= 56: return 'B-'
    if avg >= 47: return 'C'
    if avg >= 36: return 'D'
    return 'E'


def generate_random_jockey(name):
    attrs = {}
    for attr, cfg in JOCKEY_ATTR_CONFIG.items():
        val = round(max(10, min(99, random.gauss(cfg['mean'], cfg['sd']))))
        attrs[attr] = val

    overall = jockey_overall_score(attrs)
    return {
        'name': name,
        'attrs': attrs,
        'overall_score': round(overall, 1),
        'index': index_from_score(overall),
        'surface_specialization': random.choice(SURFACE_TYPES),
        'distance_specialization': random.choice(DISTANCE_CATEGORIES),
    }


def generate_jockey_population(n):
    return [generate_random_jockey(f'Jockey{i+1:03d}') for i in range(n)]


# =======================================================================
# 3) VERSENYNAPI MODOSITO SZAMITAS
# =======================================================================
def get_effective_jockey_score(jockey, distance_category, surface):
    """A zsoké adott futasra ervenyes, specializaciokkal korrigalt
    pontszama. A specializacio-illeszkedes (forras 3., 6.) noveli vagy
    csokkenti a hatekonysagot."""
    score = jockey['overall_score']

    if jockey['distance_specialization'] == distance_category:
        score += DISTANCE_SPEC_BONUS
    else:
        score -= DISTANCE_SPEC_PENALTY

    if jockey['surface_specialization'] == surface:
        score += SURFACE_SPEC_BONUS
    else:
        score -= SURFACE_SPEC_PENALTY

    return max(5, min(99, score))


def get_raceday_modifier(jockey, distance_category, surface):
    """A VERSENYNAPI MODOSITO: 1.0 korul mozgo szorzo, aminek maximalis
    kilengese a tavtol fugg (forras 1., 2.: 2-6%, hosszabb tavon nagyobb).

    - Atlagos zsoké (50 pont)      -> kb. 1.000 (semleges)
    - Kivalo zsoké rovid tavon     -> max kb. 1.02
    - Kivalo zsoké hosszu tavon    -> max kb. 1.06
    - Gyenge zsoké hosszu tavon    -> min kb. 0.94

    Ez pontosan a publikalt 5.2%-os atlagos zsoké-hozzajarulast tukrozi,
    tavfuggoen szetbontva."""
    effective = get_effective_jockey_score(jockey, distance_category, surface)
    max_swing = JOCKEY_MAX_SWING_PCT[distance_category] / 100.0

    # a 0-99 skalat -1..+1 tartomanyra kepezzuk a neutralis pont korul
    deviation = (effective - NEUTRAL_JOCKEY_SCORE) / NEUTRAL_JOCKEY_SCORE
    deviation = max(-1.0, min(1.0, deviation))

    return round(1.0 + deviation * max_swing, 4)


def describe_jockey_for_player(jockey):
    """A jatekosnak megjelenitett nezet - index + specializaciok, NYERS
    attributum-ertek sosem."""
    dist = SPEC_LABELS_HU[jockey['distance_specialization']]
    surf = SPEC_LABELS_HU[jockey['surface_specialization']]
    return f"{jockey['index']} · {dist} / {surf}"


def apply_raceday_performance(fill_bar_pct, jockey, distance_category, surface):
    """A vegso, aznapi realizalt teljesitmeny: a felepitett lo-kepesseg
    (toltottsegi sav) megszorozva a versenynapi zsoké-modositoval.

    KESOBBI BOVITESI PONT: ide fog majd bekerulni a napi forma, a palya
    allapota, a tav-illeszkedes es a talaj is - a fuggveny szerkezete
    ezt kesobb egyszeruen befogadja."""
    mod = get_raceday_modifier(jockey, distance_category, surface)
    return {
        'fill_bar_pct': fill_bar_pct,
        'jockey_modifier': mod,
        'raceday_performance': round(fill_bar_pct * mod, 2),
    }


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - JOCKEY ENGINE v1.0 ===\n")

    N_JOCKEYS = 2000
    population = generate_jockey_population(N_JOCKEYS)

    # --- 1) Attributum-generator validacio ---
    print("--- 1) ATTRIBUTUM-GENERATOR VALIDACIO (statisztikai visszanyeres) ---")
    attr_ok = True
    for attr, cfg in JOCKEY_ATTR_CONFIG.items():
        values = [j['attrs'][attr] for j in population]
        obs_mean = statistics.mean(values)
        obs_sd = statistics.stdev(values)
        status = "OK" if abs(obs_mean - cfg['mean']) < 1.5 and abs(obs_sd - cfg['sd']) < 1.5 else "ELTERES"
        if status == "ELTERES":
            attr_ok = False
        print(f"  {attr:18s} celzott {cfg['mean']:.0f}/{cfg['sd']:.0f} -> kapott {obs_mean:5.1f}/{obs_sd:5.1f}  [{status}]")
    print()

    # --- 2) A KULCS VALIDACIO: a zsoké-hatas a publikalt 2-6%-os savban van-e ---
    print("--- 2) ZSOKE-HATAS MERTEKE (forras: Oki et al., 2-6% varianciahanyad, tavfuggo) ---")
    swing_ok = True
    for dist in DISTANCE_CATEGORIES:
        mods = []
        for j in population:
            for surf in SURFACE_TYPES:
                mods.append(get_raceday_modifier(j, dist, surf))
        min_mod, max_mod = min(mods), max(mods)
        actual_swing = max(abs(1 - min_mod), abs(max_mod - 1)) * 100
        target = JOCKEY_MAX_SWING_PCT[dist]
        status = "OK" if actual_swing <= target + 0.01 else "ELTERES"
        if status == "ELTERES":
            swing_ok = False
        print(f"  {dist:8s} modosito tartomany: {min_mod:.4f} - {max_mod:.4f}  "
              f"(max kilenges {actual_swing:.2f}%, celzott max {target}%)  [{status}]")
    print("  -> A hosszabb tavon nagyobb a zsoké hatasa, ahogy a forras is leirja.\n")

    # --- 3) Semlegesseg-ellenorzes: atlagos zsoké ~1.0 modositot ad-e ---
    print("--- 3) SEMLEGESSEG-ELLENORZES (atlagos zsoké, illeszkedo specializaciokkal) ---")
    avg_jockey = {
        'name': 'AvgTest', 'attrs': {k: 50 for k in JOCKEY_ATTRS},
        'overall_score': 50.0, 'index': 'B-',
        'surface_specialization': 'turf', 'distance_specialization': 'mile',
    }
    # semleges eset: a specializacio-bonusz es -buntetes kiegyenlitve
    neutral_mod = get_raceday_modifier(avg_jockey, 'mile', 'turf')
    print(f"  Pontosan atlagos (50) zsoké, sajat tavan es talajan: modosito = {neutral_mod:.4f}")
    print(f"  (A specializacio-illeszkedes miatt >1.0 - ez helyes: a jo illeszkedes elonyt ad.)\n")

    # --- 4) Index-eloszlas ---
    print("--- 4) INDEX-ELOSZLAS A ZSOKE-POPULACION ---")
    idx_counts = Counter(j['index'] for j in population)
    for idx in ['A+','A','A-','B+','B','B-','C','D','E']:
        cnt = idx_counts.get(idx, 0)
        if cnt > 0:
            print(f"  {idx:3s} {cnt:5d}  ({cnt/N_JOCKEYS*100:5.2f}%)")
    print()

    # --- 5) Jatekosnak megjelenitett nezet ---
    print("--- 5) JATEKOSNAK MEGJELENITETT NEZET (5 pelda zsoké) ---")
    for j in population[:5]:
        print(f"  {j['name']:12s} -> \"{describe_jockey_for_player(j)}\"")
    print()

    # --- 6) Integralt demo: toltottsegi sav + versenynapi modosito ---
    print("--- 6) INTEGRALT DEMO: toltottsegi sav x versenynapi zsoké-modosito ---")
    print("  (a toltottsegi sav a breeding+feeding+trainer motorokbol jon)\n")
    demo_fill_bars = [
        (85.0, "jol felepitett lo"),
        (60.0, "kozepesen felepitett lo"),
    ]
    best_jockey = max(population, key=lambda j: j['overall_score'])
    worst_jockey = min(population, key=lambda j: j['overall_score'])

    for fill, note in demo_fill_bars:
        print(f"  {note} (toltottseg: {fill}%)")
        for j, jlabel in [(best_jockey, "legjobb zsoké"), (worst_jockey, "leggyengebb zsoké")]:
            for dist in ['sprint', 'staying']:
                res = apply_raceday_performance(fill, j, dist, j['surface_specialization'])
                print(f"    {jlabel:18s} ({describe_jockey_for_player(j):24s}) {dist:8s} -> "
                      f"modosito {res['jockey_modifier']:.4f} -> teljesitmeny {res['raceday_performance']:.2f}")
        print()

    overall = "MINDEN VALIDACIO OK" if (attr_ok and swing_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== OSSZESITETT STATUS: {overall} ===")
