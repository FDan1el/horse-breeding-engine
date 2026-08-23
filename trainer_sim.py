"""
Trot Heritage - Trainer Engine v1.0
=======================================================================
A tenyesztesi motorral (breeding_sim.py) azonos filozofiaval epul fel:

  - A jatekos csak egy A-E indexet + egy specializacios cimket lat
    (pl. "B+ - Sprint specialista"), a nyers attributumokat SOHA.
  - A hatterben reszletes, tobb-dimenzios attributum-rendszer fut.
  - Nagy skalaju, veletlenszeru "tréner-populacio" generalasa, ugyanugy
    skalazhato letszammal, mint a lovaknal.
  - Minden generator-fuggveny STATISZTIKAILAG VALIDALVA a fajl vegen.

FONTOS METODOLOGIAI KULONBSEG A TENYESZTESI MOTORHOZ KEPEST:
A lo teljesitmeny-genetikajahoz (h2 ertekek) letezik publikalt, valos
tudomanyos adat (Sharman et al. 2023, Oki et al. 2008, stb.). A tréner
KEPESSEGEIRE (pl. "Kondicionalas: 72/100") NINCS es NEM IS LETEZHET
ilyen publikalt numerikus adat - ez a termeszetenel fogva jatektervezesi
konstrukcio. AMI VISZONT VALOS TUDOMANYOS ALAPRA EPUL: hogy MELYIK
DIMENZIOK szamitanak egy tréner munkajaban, es hogy ezek MILYEN IRANYBAN
hatnak a lo teljesitmenyere/serulesrizikojara - ez mar dokumentalt.

FORRASOK (a tréner-DIMENZIOK kivalasztasahoz, nem a szamertekekhez):

1. "Objectives, Principles, and Methods of Strength Training for Horses",
   ScienceDirect: het tudomanyos tréning-alapelv - serulesmegelozes,
   overcompensation, periodizacio, fokozatos terhelesnoveles, egyediseg,
   specifikussag, egyseg.
   https://www.sciencedirect.com/science/article/abs/pii/S0737080616307158

2. Morrice-West et al., "Association between Thoroughbred racehorse
   training practices and musculoskeletal injuries in Victoria,
   Australia" (66 tréner felmeres, valos adat): a gyakoribb, rovidebb
   pihenoidok ES a mersekelt (nem tul magas, nem tul alacsony) vagta-
   mennyiseg alacsonyabb serulesrizikoval jart egyutt.
   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10628463/

3. "Association of Thoroughbred Racehorse Workloads and Rest Practices
   with Trainer Success": a rajtok kozotti hosszabb (kb. 3 hetig tarto)
   pihenoido jobb eredmenyekkel jart, utana mar romlott a teljesitmeny -
   azaz van egy optimalis sav, nem "minel tobb piheno, annal jobb".
   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8614314/

4. Tobb forras (Mad Barn, Equiniction, AQHA, eXtension, RaceShare):
   a tréning tav-specifikus (sprint vs. hosszutav felkeszites elteroen
   epul fel), es a psziches felkeszites (magabiztossag, verseny-
   kornyezethez szoktatas) kulon, dokumentalt terulet a fizikai
   kondicionalas mellett.
   https://madbarn.com/athletic-performance-in-horses/
   https://raceshare.com/news/beginners-guide-to-the-training-of-racehorses

EZERT A MODELL 5+1 dimenziot hasznal, MINDEGYIK KOZVETLENUL A MEGLEVO
LO-TULAJDONSAGOKHOZ KAPCSOLVA (nem legbol kapott dimenziok):
  - Kondicionalas       -> Stamina kihasznalasa
  - Sebessegfejlesztes   -> Speed, Acceleration, Sprint Aptitude kihasznalasa
  - Tav-specializacio    -> melyik tavkategoriaban (Sprint/Mile/Middle/
                            Staying) a legerosebb - forras 4.
  - Terheles-kezeles     -> Soundness kihasznalasa / serulesriziko - forras 2, 3.
  - Psziches felkeszites -> Temperament, Trainability kihasznalasa - forras 4.
  - Tapasztalat/hirnev   -> meta-stat, csokkenti az eredmenyek szorasat
                            (megbizhatobb, kiszamithatobb teljesitmeny)
"""

import random
import statistics
import math
from collections import Counter

random.seed(42)


# =======================================================================
# 1) TRENER ATTRIBUTUMOK - JATEKTERVEZESI ERTEKKESZLET
# =======================================================================
# EXPLICIT MEGJEGYZES: az itt szereplo mean/sd ertekek NEM tudomanyos
# adatok (mert ilyen nem letezik trénerek "kepesseg-pontszamara"), hanem
# jatektervezesi kalibracios parameterek, ugyanugy jelolve, mint a
# breeding_sim.py-ban minden hasonlo eset (pl. POPULATION_TRAIT_MEAN).
TRAINER_ATTR_CONFIG = {
    'conditioning':               {'mean': 60, 'sd': 13, 'affects': 'Stamina'},
    'speed_development':          {'mean': 60, 'sd': 13, 'affects': 'Speed, Acceleration, Sprint Aptitude'},
    'injury_prevention':          {'mean': 60, 'sd': 14, 'affects': 'Soundness'},
    'psychological_conditioning': {'mean': 60, 'sd': 12, 'affects': 'Temperament, Trainability'},
    'experience':                 {'mean': 50, 'sd': 18, 'affects': 'megbizhatosag / eredmeny-szoras'},
}
TRAINER_ATTRS = list(TRAINER_ATTR_CONFIG.keys())

# Osszesitett index sulyozasa - a terheles-kezeles (serulesriziko miatt)
# es a sebessegfejlesztes kapja a legnagyobb sulyt, az elmelet szerint
# (forras 1-3.) ezek a legkritikusabb tenyezok a tréner munkajaban.
TRAINER_WEIGHTS = {
    'conditioning': 1.0,
    'speed_development': 1.1,
    'injury_prevention': 1.15,
    'psychological_conditioning': 0.85,
    'experience': 0.6,
}

DISTANCE_CATEGORIES = ['sprint', 'mile', 'middle', 'staying']
SPECIALIZATION_BONUS_MEAN = 15   # placeholder: a fo specializacio hany ponttal jobb
SPECIALIZATION_BONUS_SD = 5
SPECIALIZATION_PENALTY_FRACTION = 0.4  # a nem-specializalt tavkategoriak ennyivel gyengebbek


def trainer_overall_score(attrs):
    s = sum(attrs[k] * TRAINER_WEIGHTS[k] for k in TRAINER_ATTRS)
    return s / sum(TRAINER_WEIGHTS.values())

def index_from_score(avg):
    """Ugyanaz a skala, mint a lovaknal (breeding_sim.py) - konzisztencia
    kedveert, hogy a jatekos egyseges A-E logikat lasson mindenhol."""
    if avg >= 88: return 'A+'
    if avg >= 82: return 'A'
    if avg >= 76: return 'A-'
    if avg >= 70: return 'B+'
    if avg >= 63: return 'B'
    if avg >= 56: return 'B-'
    if avg >= 47: return 'C'
    if avg >= 36: return 'D'
    return 'E'


# =======================================================================
# 2) VELETLENSZERU TRENER-POPULACIO GENERALASA
# =======================================================================
def generate_random_trainer(name):
    """Egy fuggetlen tréner generalasa a populacios eloszlasokbol."""
    attrs = {}
    for attr, cfg in TRAINER_ATTR_CONFIG.items():
        val = round(max(15, min(99, random.gauss(cfg['mean'], cfg['sd']))))
        attrs[attr] = val

    overall = trainer_overall_score(attrs)
    index_letter = index_from_score(overall)

    # tav-specializacio: egy fo iranyt kap a tréner, abban jobb, masban
    # gyengebb - ez adja a strategiai valasztast a jatekosnak (forras 4.)
    primary_specialization = random.choice(DISTANCE_CATEGORIES)
    bonus = max(2, random.gauss(SPECIALIZATION_BONUS_MEAN, SPECIALIZATION_BONUS_SD))
    base_distance_skill = (attrs['conditioning'] + attrs['speed_development']) / 2

    distance_skill = {}
    for cat in DISTANCE_CATEGORIES:
        if cat == primary_specialization:
            val = base_distance_skill + bonus
        else:
            val = base_distance_skill - bonus * SPECIALIZATION_PENALTY_FRACTION
        distance_skill[cat] = round(max(15, min(99, val)))

    return {
        'name': name,
        'attrs': attrs,
        'overall_score': round(overall, 1),
        'index': index_letter,
        'primary_specialization': primary_specialization,
        'distance_skill': distance_skill,
    }

def generate_trainer_population(n):
    return [generate_random_trainer(f'Trainer{i+1:03d}') for i in range(n)]


# =======================================================================
# 3) JATEKOSNAK MEGJELENITETT INFORMACIO (csak index + cimke, SOHA nyers szam)
# =======================================================================
SPECIALIZATION_LABELS_HU = {
    'sprint': 'Sprint specialista',
    'mile': 'Mérföld specialista',
    'middle': 'Középtáv specialista',
    'staying': 'Hosszútáv specialista',
}

def describe_trainer_for_player(trainer):
    """EZ az egyetlen fuggveny, aminek a kimenetet a jatekos lathatja.
    Nyers attributum-ertek innen sosem kerulhet ki."""
    label = SPECIALIZATION_LABELS_HU[trainer['primary_specialization']]
    return f"{trainer['index']} · {label}"


# =======================================================================
# 4) TRENING-HATEKONYSAG LEKERDEZES (jovobeli integracios pont)
# =======================================================================
def get_training_effectiveness(trainer, distance_category):
    """0-1 kozotti hatekonysagi ertek egy adott tavkategoriara - ez lesz
    a bemenete a kesobbi, MEG NEM VEGLEGESITETT fenotipus-kepletnek
    (genetika + felneveles + tréning egyesitese). A fuggveny szandekosan
    csak egy tiszta 0-1 erteket ad vissza, a vegleges kombinacios keplet
    kesobb, kulon dontes alapjan epul ra."""
    skill = trainer['distance_skill'][distance_category]
    return round(skill / 99, 3)


# =======================================================================
# 5) TRENERVALTAS - ATMENETI IDOSZAK (CARRYOVER)
# =======================================================================
# A JATEKOS KONCEPCIOJA: a jatekos lotenyeszto farmot vezet, NEM sajat
# versenyistallot - a lovat ATADJA egy trénernek, aki treningezi es
# futtatja. Egy kesz versenylo eladasakor a vevo MARADHAT az eddigi
# trénernel. Ha viszont valt, az elozo tréner munkaja MEG 3 VERSENY
# EREJEIG a loban marad, utana veszi at teljesen az uj tréner.
#
# EZ A MECHANIKA VALOS ELETTANI ALAPON ALL - nem onkenyes szam:
#
# 1. Mukai et al. (2006), Equine Veterinary Journal: 6 teliver yearling
#    6 honapos treningje utan a leepitesi (detraining) idoszakot
#    vizsgaltak. Eredmeny: "Aerobic and cardiovascular fitness may be
#    maintained in young Thoroughbred horses during at least 10 weeks
#    of detraining by maintaining modest spontaneous exercise activity."
#    -> Azaz ha a lo TOVABBRA IS aktiv marad (mint egy trénervaltasnal,
#    ahol nem all le, csak mas edzi), a korabbi adaptaciok LEGALABB
#    10 HETIG megmaradnak.
#    https://pubmed.ncbi.nlm.nih.gov/17402420/
#    https://beva.onlinelibrary.wiley.com/doi/10.1111/j.2042-3306.2006.tb05541.x
#
# 2. eXtension (land-grant egyetemek), "Basic Conditioning of the
#    Equine Athlete": az izomzatban 2-4 het alatt kovetkeznek be a
#    valtozasok, ezt kovetik a kardiovaszkularis es csontvaltozasok;
#    az oxigenfelvetel es ventillacios kapacitas 3 heten belul csokken.
#    -> A leepules FOKOZATOS, nem egyik naprol a masikra tortenik.
#    https://articles.extension.org/pages/11280/basic-conditioning-of-the-equine-athlete
#
# 3. Mujika & Padilla (2000), Sports Medicine: hosszu tavu detraining
#    eseten a jol edzett egyedek VO2max-a jelentosen csokken, DE
#    VEGIG A KIINDULASI SZINT FELETT MARAD - a REGEN szerzett
#    adaptaciok vesznek el eloszor.
#    https://link.springer.com/article/10.2165/00007256-200030030-00001
#
# 4. Idozites-szamitas: a versenyek kozti tipikus piheno 3-5 het
#    (korabbi forrasunk: a rajtok kozti hosszabb piheno kb. 3 hetig
#    javitja az eredmenyt). HAROM VERSENY tehat kb. 9-15 HET - ami
#    szinte pontosan egybeesik a Mukai-tanulmany 10 hetes ablakaval.
#    https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8614314/
#
# ATMENETI SULYOK (linearis kifutas, 3 verseny alatt):
#   1. verseny valtas utan: 75% regi tréner / 25% uj
#   2. verseny:             50% / 50%
#   3. verseny:             25% / 75%
#   4. verseny-tol:          0% / 100%  (teljes atvetel)
TRAINER_CARRYOVER_RACES = 3

CARRYOVER_WEIGHTS = {
    1: 0.75,   # az elso verseny utan meg 75%-ban a regi tréner munkaja hat
    2: 0.50,
    3: 0.25,
    # 4-tol: 0.0 (teljes atvetel)
}


def get_carryover_weight(races_since_change):
    """Milyen sullyal hat meg a REGI tréner munkaja, N versennyel a
    valtas utan. 0 = meg egy verseny sem volt a valtas ota."""
    if races_since_change <= 0:
        return 1.0   # a valtas pillanataban meg teljesen a regi tréner hatasa el
    return CARRYOVER_WEIGHTS.get(races_since_change, 0.0)


def get_effective_trainer_score(old_trainer, new_trainer, races_since_change):
    """A lora ADOTT PILLANATBAN ervenyes, effektiv tréner-pontszam a
    valtas utani atmeneti idoszakban.

    old_trainer: az elozo tréner (None, ha nem volt valtas)
    new_trainer: a jelenlegi tréner
    races_since_change: hany verseny telt el a valtas ota
    """
    if old_trainer is None:
        return new_trainer['overall_score']

    w_old = get_carryover_weight(races_since_change)
    w_new = 1.0 - w_old
    return round(old_trainer['overall_score'] * w_old + new_trainer['overall_score'] * w_new, 2)


def describe_transition_for_player(old_trainer, new_trainer, races_since_change):
    """A jatekosnak megjelenitett atmeneti allapot - NYERS pontszam
    nelkul, csak allapot-jelzes."""
    if old_trainer is None:
        return f"Tréner: {describe_trainer_for_player(new_trainer)}"

    w_old = get_carryover_weight(races_since_change)
    if w_old <= 0.0:
        return f"Tréner: {describe_trainer_for_player(new_trainer)} (teljes átvétel megtörtént)"

    remaining = TRAINER_CARRYOVER_RACES - races_since_change
    return (f"Tréner: {describe_trainer_for_player(new_trainer)} "
            f"— átmeneti időszak, még {remaining} verseny az előző tréner hatása alatt")


# =======================================================================
# 6) VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - TRAINER ENGINE v1.0 ===\n")

    N_TRAINERS = 2000
    population = generate_trainer_population(N_TRAINERS)

    # --- 1) Attributum-eloszlas validacio: a generalt populacio
    #     statisztikai jellemzoi visszaadjak-e a beallitott celertekeket ---
    print("--- 1) ATTRIBUTUM-GENERATOR VALIDACIO (statisztikai visszanyeres) ---")
    all_ok = True
    for attr, cfg in TRAINER_ATTR_CONFIG.items():
        values = [t['attrs'][attr] for t in population]
        obs_mean = statistics.mean(values)
        obs_sd = statistics.stdev(values)
        mean_diff = abs(obs_mean - cfg['mean'])
        sd_diff = abs(obs_sd - cfg['sd'])
        status = "OK" if mean_diff < 1.5 and sd_diff < 1.5 else "ELTERES"
        if status == "ELTERES":
            all_ok = False
        print(f"  {attr:28s} celzott atlag={cfg['mean']:.0f} (kapott {obs_mean:5.1f})  "
              f"celzott szoras={cfg['sd']:.0f} (kapott {obs_sd:5.1f})  [{status}]")
    print()

    # --- 2) Specializacio-eloszlas validacio: kb. egyenletes eloszlas
    #     a negy tavkategoria kozott ---
    print("--- 2) SPECIALIZACIO-ELOSZLAS VALIDACIO (kb. 25%-25%-25%-25% elvart) ---")
    spec_counts = Counter(t['primary_specialization'] for t in population)
    for cat in DISTANCE_CATEGORIES:
        pct = spec_counts.get(cat, 0) / N_TRAINERS * 100
        status = "OK" if abs(pct - 25.0) < 3.0 else "ELTERES"
        print(f"  {cat:10s} {pct:5.1f}%  [{status}]")
    print()

    # --- 3) Index-eloszlas: legyen ertelmes szoras A-E kozott ---
    print("--- 3) INDEX-ELOSZLAS (a teljes trener-populacion) ---")
    index_counts = Counter(t['index'] for t in population)
    for idx in ['A+','A','A-','B+','B','B-','C','D','E']:
        cnt = index_counts.get(idx, 0)
        if cnt > 0:
            print(f"  {idx:3s} {cnt:5d}  ({cnt/N_TRAINERS*100:5.2f}%)")
    print()

    # --- 4) Jatekosnak megjelenitett nezet demonstracioja ---
    print("--- 4) JATEKOSNAK MEGJELENITETT NEZET (5 pelda tréner) ---")
    for t in population[:5]:
        print(f"  {t['name']:12s} -> \"{describe_trainer_for_player(t)}\"")
    print()

    # --- 5) Trening-hatekonysag lekerdezes demonstracioja ---
    print("--- 5) TRENING-HATEKONYSAG LEKERDEZES DEMO (egy sprint-specialista trénerre) ---")
    sprint_trainer = next(t for t in population if t['primary_specialization'] == 'sprint')
    print(f"  Pelda tréner: {describe_trainer_for_player(sprint_trainer)}")
    for cat in DISTANCE_CATEGORIES:
        eff = get_training_effectiveness(sprint_trainer, cat)
        print(f"    {cat:10s} hatekonysag: {eff*100:5.1f}%")
    print()

    overall_status = "MINDEN VALIDACIO OK" if all_ok else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== OSSZESITETT STATUS (1-5. blokk): {overall_status} ===\n")

    # --- 6) Trenervaltas atmeneti idoszak validacio ---
    print("--- 6) TRENERVALTAS - ATMENETI IDOSZAK (3 verseny carryover) ---")
    print("  Tudomanyos alap: Mukai et al. 2006 - a kardiovaszkularis fittseg")
    print("  legalabb 10 hetig fennmarad, ha a lo aktiv marad. 3 verseny ~ 9-15 het.\n")

    # ket erosen elteroe trener a demonstraciohoz
    strong_trainer = max(population, key=lambda t: t['overall_score'])
    weak_trainer = min(population, key=lambda t: t['overall_score'])

    print(f"  Regi tréner:  {describe_trainer_for_player(strong_trainer):32s} (belso pontszam: {strong_trainer['overall_score']})")
    print(f"  Uj tréner:    {describe_trainer_for_player(weak_trainer):32s} (belso pontszam: {weak_trainer['overall_score']})")
    print()
    print("  ESET A: eros trénertol gyenge trénerhez valt a vevo (romlas, de fokozatos)")
    transition_ok = True
    expected_weights = [1.0, 0.75, 0.50, 0.25, 0.0, 0.0]
    for races in range(0, 6):
        eff = get_effective_trainer_score(strong_trainer, weak_trainer, races)
        w = get_carryover_weight(races)
        status = "OK" if abs(w - expected_weights[races]) < 0.001 else "ELTERES"
        if status == "ELTERES":
            transition_ok = False
        label = "valtas pillanata" if races == 0 else f"{races}. verseny utan"
        print(f"    {label:20s} regi tréner sulya: {w*100:5.1f}%  -> effektiv pontszam: {eff:5.2f}  [{status}]")
    print()

    print("  ESET B: gyenge trénertol eros trénerhez valt (javulas, de nem azonnal)")
    for races in range(0, 6):
        eff = get_effective_trainer_score(weak_trainer, strong_trainer, races)
        w = get_carryover_weight(races)
        label = "valtas pillanata" if races == 0 else f"{races}. verseny utan"
        print(f"    {label:20s} regi tréner sulya: {w*100:5.1f}%  -> effektiv pontszam: {eff:5.2f}")
    print()

    print("  ESET C: a vevo MEGTARTJA az eddigi trénert (nincs valtas, nincs atmenet)")
    eff_no_change = get_effective_trainer_score(None, strong_trainer, 0)
    print(f"    effektiv pontszam azonnal: {eff_no_change} (valtozatlan)")
    print()

    print("  JATEKOSNAK MEGJELENITETT NEZET az atmenet alatt:")
    for races in [0, 1, 2, 3, 4]:
        print(f"    {races} verseny: \"{describe_transition_for_player(strong_trainer, weak_trainer, races)}\"")
    print()

    final_status = "MINDEN VALIDACIO OK" if (all_ok and transition_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== TELJES OSSZESITETT STATUS: {final_status} ===")
