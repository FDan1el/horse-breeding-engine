"""
Trot Heritage - Female Family (Bloodline) Engine v1.0
=======================================================================
A NOI CSALAD (female family / damline) kulon kezelese es A-E
besorolasa - a lo SAJAT tenyeszindexetol FUGGETLENUL.

A JATEKOS ALAPELVE: "A sajat genetikat nem akarjuk elhomalyositani a
kancacsaladok erejevel - az csak egy PLUSZ."

Ezert a csalad NEM az atlagot tolja el, hanem a KIUGRO UTOD ESELYET
noveli. Egy szereny kepessegu kanca egy nagy csaladbol nem ad
rendszeresen jobb csikot - de nagyobb esellyel ad egy klasszist.

=======================================================================
FORRASOK
=======================================================================

A BIZONYITO ESET (miert kell egyaltalan a csalad):

1. Win Approval (1992-2021): "had an unremarkable racing career", majd
   kivetelezes anyakancava valt - tiz csikobol NEGY graded stakes
   gyoztest hozott, az utodai 8 936 808 dollart kerestek. TOBA
   Broodmare of the Year (2017).
   -> Pontosan a jatekos altal leirt eset: a gyenge sajat genetika
   nem jelenti, hogy a kancat le kell irni.
   https://en.wikipedia.org/wiki/Win_Approval

2. Fall Aspen (blue hen, G1-gyoztes): olyan noi vonalat alapitott,
   amely csaknem 30 Group/Graded gyoztesert felelos, koztuk a Dubai
   Millennium. Just The Judge 4.5m guineaert kelt el, mig az anyja het
   evvel korabban mindossze 26 000 euroert.
   https://theownerbreeder.com/columns/broodmares-buying-guide/

3. A "blue hen" definicioja: olyan kanca, aki tartos, tobbgeneracios
   hatast gyakorolt a fajtara - jellemzoen him ES noi leszarmazottakon
   keresztul egyarant.
   https://www.aqha.com/-/horse-breeding-lingo

4. Alidiva (1997): az egyetlen kanca, akinek EGY szezonban harom utoda
   nyert grade/group I versenyt - Broodmare of the Year Irorszagban es
   Olaszorszagban is.
   https://www.bloodhorse.com/horse-racing/articles/177641/blue-hens

A KRITIKUS ELLENADAT (miert csak PLUSZ, es nem fokomponens):

5. Thoroughbred Review, "The Myth Of The Female Family" - a
   Blood-Horse 65 000+ kanca produce-rekordjainak elemzese alapjan:
     - a VERSENYKEPESSEGGEL rendelkezo kancak OTSZOR annyi graded
       stakes gyoztest hoznak, mint az atlagos teliver kanca
     - az EROS NOI CSALADDAL rendelkezok csak valamivel TOBB MINT
       KETSZER annyit
     - a versenyosztallyal biro kancaktol szarmazo csikok atlagosan
       40 271 dollarral tobbet kerestek, mint azok, akiknek csak eros
       csaladjuk volt
     - "relatively small gap between the breed average and mares with
       strong families"
   -> EZERT a csalad a modellben kb. FELE akkora sullyal szerepel,
   mint a sajat kepesseg. Ez nem onkenyes dontes: a 2x vs 5x arany
   kozvetlenul ebbol az elemzesbol jon.
   https://thoroughbredreview.com/the-myth-of-the-female-family/

A CSALADFOKOZAT FELEPITESE:

6. Elit kanca-minositesek valos registerekben (pl. KWPN Preferent,
   Keur): a kancak a SAJAT teljesitmenyuk ES az UTODAIK sikere alapjan
   kapjak. Ha egy vonalon belul tobb generacio is visel ilyen cimet,
   az emeli a csalad genetikai hitelet es kereskedelmi erteket.
   https://faunadiscovery.com/damline-explained/

7. A katalogus-hagyomany: a legfontosabb az 1. es 2. anya; a 3-4.
   anyanal a rokonsag mar erosen "hig". Ezert a pontok GENERACIONKENT
   CSOKKENO sullyal szamitanak.
   https://www.gaylevanleer.com/ownership/catalog.htm
   https://boomerbloodstock.com.au/learning/buying-selling/how-to-read-a-catalogue-page/

8. A noi vonal kulon kezelese genetikailag is indokolt: a mitokondrialis
   DNS kizarolag az anyai agon oroklodik. (Korabbi forrasunk: 675
   teliver anyai vonal, anya-csiko r=0.141 vs apa-csiko r=0.035.)
   https://pubmed.ncbi.nlm.nih.gov/25940872/
"""

from enum import Enum


# =======================================================================
# 1) EGYSEGES A-E SKALA (azonos a tobbi modullal)
# =======================================================================
GRADE_ORDER = ['E', 'D', 'C', 'B-', 'B', 'B+', 'A-', 'A', 'A+']


def index_from_score(avg):
    if avg >= 88: return 'A+'
    if avg >= 82: return 'A'
    if avg >= 76: return 'A-'
    if avg >= 70: return 'B+'
    if avg >= 63: return 'B'
    if avg >= 56: return 'B-'
    if avg >= 47: return 'C'
    if avg >= 36: return 'D'
    return 'E'


# A blue hen cim TARTOSAN emeli a vonal fokozatat - ez a vervonal-epites
# hosszu tavu jutalma. (A cim feltetelei a 3. blokkban.)
BLUE_HEN_FAMILY_BONUS = 12.0   # pont, a nyers csaladpontszamhoz


# =======================================================================
# 2) CSALAD-PONTOK: mi er mennyit
# =======================================================================
# Az eredmenyek generacionkent CSOKKENO sullyal szamitanak (forras 7.):
# az 1. es 2. anya a donto, a tavolabbi generaciok mar "higak".
GENERATION_WEIGHT = {
    1: 1.00,   # maga a kanca / 1. anya
    2: 0.65,   # nagyanya
    3: 0.35,   # dedanya
    4: 0.15,   # ukanya - innen mar alig szamit
}
MAX_TRACKED_GENERATIONS = 4

# Egy-egy eredmeny nyers pontertek. Jatektervezesi kalibracio, de az
# ARANYOK a valos katalogus-logikat kovetik: a graded gyozelem
# nagysagrendekkel tobbet er, mint egy sima gyozelem.
ACHIEVEMENT_POINTS = {
    'graded_winner': 30,    # graded/group stakes gyoztes
    'stakes_winner': 18,    # black type gyoztes
    'stakes_placed': 9,     # black type helyezett
    'winner': 3,            # sima gyoztes
    'unraced': 0,
}

# A csalad meretere normalizalunk: egy nagy csalad ne csak azert legyen
# jobb, mert tobb lova van. A valos katalogusolvasas is ezt nezi:
# "9 csiko, 3 futott, 2 gyoztes" PIROS ZASZLO - az ARANY szamit.
#
# A REFERENCIA-ERTEK VALOS ESETEKBOL KALIBRALVA (nem onkenyes):
#   - Win Approval: 4 graded gyoztes 10 csikobol + 2 sima gyoztes
#     = (4*30 + 2*3) / 10 = 12.6 pont/fo  -> ez a CSUCS (A+)
#     https://en.wikipedia.org/wiki/Win_Approval
#   - Van Leer "nagyon jo rekord" pelda: 6 versenykorbeli csikobol
#     1 graded gyoztes, 2 stakes-helyezett gyoztes, 1 gyoztes
#     = (30 + 2*9 + 3) / 6 = 8.5 pont/fo  -> ez legyen kb. A-
#     https://www.gaylevanleer.com/ownership/catalog.htm
# Ezert a referencia 11 pont/fo: igy Win Approval A+, a "nagyon jo"
# rekord A-, az atlagos csalad pedig C korul landol.
POINTS_PER_HEAD_REFERENCE = 11.0


def calculate_family_score(generations, is_blue_hen=False):
    """A noi csalad nyers pontszama (0-99).

    generations: dict, kulcs = generacio szama (1-4), ertek = lista
      az adott generacio noi vonalanak utodairol, pl.
        {1: ['graded_winner', 'stakes_placed', 'winner', 'unraced'],
         2: ['stakes_winner', 'winner'], ...}
    is_blue_hen: a blue hen cim TARTOSAN emeli a vonal fokozatat
    """
    weighted_points = 0.0
    weighted_count = 0.0

    for gen in range(1, MAX_TRACKED_GENERATIONS + 1):
        offspring = generations.get(gen, [])
        if not offspring:
            continue
        w = GENERATION_WEIGHT[gen]
        gen_points = sum(ACHIEVEMENT_POINTS.get(o, 0) for o in offspring)
        weighted_points += gen_points * w
        weighted_count += len(offspring) * w

    if weighted_count == 0:
        return 0.0

    # aranyra normalizalunk: az ARANY szamit, nem a csalad merete
    per_head = weighted_points / weighted_count
    score = per_head / POINTS_PER_HEAD_REFERENCE * 99.0

    if is_blue_hen:
        score += BLUE_HEN_FAMILY_BONUS

    return round(min(99.0, max(0.0, score)), 1)


def family_grade(generations, is_blue_hen=False):
    """A noi csalad A-E besorolasa."""
    return index_from_score(calculate_family_score(generations, is_blue_hen))


# =======================================================================
# 3) BLUE HEN CIM
# =======================================================================
# A JATEKOS DONTESE: harom black type utod a kuszob.
# Valos alap: a blue hen olyan kanca, aki TARTOS, TOBBGENERACIOS hatast
# gyakorol (forras 3.). Win Approval tizbol negy graded gyoztest adott
# (forras 1.) - ez kivetelezes, ezert a harom reális jatekbeli kuszob.
BLUE_HEN_THRESHOLD = 3
BLUE_HEN_QUALIFYING = {'graded_winner', 'stakes_winner'}


def check_blue_hen(offspring):
    """Elnyeri-e a kanca a blue hen cimet?"""
    qualifying = [o for o in offspring if o in BLUE_HEN_QUALIFYING]
    count = len(qualifying)
    return {
        'is_blue_hen': count >= BLUE_HEN_THRESHOLD,
        'qualifying_count': count,
        'needed': max(0, BLUE_HEN_THRESHOLD - count),
    }


# =======================================================================
# 4) A CSALAD HATASA: a felso szel, NEM az atlag
# =======================================================================
# EZ A MODUL LEGFONTOSABB DONTESE, es kozvetlenul a forras 5. adatabol
# kovetkezik.
#
# Win Approval nem azert volt kulonleges, mert MINDEN csikoja jo lett -
# tizbol negy. A csalad tehat NEM a varhato erteket tolja el, hanem
# megnoveli a KIUGRO utod eselyet.
#
# A szamok a valos aranyokat kovetik: a csalad kb. 2x szorzo a kiugro
# eredmenyre, a sajat kepesseg 5x (forras 5.) - igy a csalad nagyjabol
# FELE akkora sullyal hat, es nem homalyositja el a sajat genetikat.
FAMILY_EFFECT = {
    'A+': {'mean_shift': 1.5, 'upside_mult': 2.2, 'label': 'Blue hen vonal'},
    'A':  {'mean_shift': 1.2, 'upside_mult': 1.9, 'label': 'Kivételes család'},
    'A-': {'mean_shift': 1.0, 'upside_mult': 1.8, 'label': 'Erős család'},
    'B+': {'mean_shift': 0.7, 'upside_mult': 1.5, 'label': 'Jó család'},
    'B':  {'mean_shift': 0.5, 'upside_mult': 1.4, 'label': 'Rendezett család'},
    'B-': {'mean_shift': 0.3, 'upside_mult': 1.2, 'label': 'Átlag feletti család'},
    'C':  {'mean_shift': 0.0, 'upside_mult': 1.0, 'label': 'Átlagos család'},
    'D':  {'mean_shift': -0.3, 'upside_mult': 0.9, 'label': 'Gyenge család'},
    'E':  {'mean_shift': -0.5, 'upside_mult': 0.8, 'label': 'Nyomtalan család'},
}


def get_family_effect(grade):
    """A csalad hatasa a csiko genetikai eloszlasara.

    mean_shift:   mennyivel tolodik a KOZEPERTEK (szandekosan CSEKELY)
    upside_mult:  hanyszorosara no a KIUGRO utod eselye (ez a lenyeg)
    """
    return FAMILY_EFFECT.get(grade, FAMILY_EFFECT['C'])


def apply_family_to_foal(base_tgv, family_grade_letter, roll):
    """A csalad hatasanak alkalmazasa egy csiko genetikai ertekere.

    base_tgv: a breeding_sim.py Mendeli modelljebol jovo alapertek
    roll:     0-1 kozotti veletlen szam (a kiugras "dobasa")

    A csalad ket dolgot csinal:
      1. minimalis kozepertek-eltolas (mean_shift)
      2. ha a dobas a felso savba esik, a csalad MEGERSITI a kiugrast
    """
    effect = get_family_effect(family_grade_letter)
    tgv = base_tgv + effect['mean_shift']

    # a felso 8% a "kiugro" sav; a csalad ezt a kuszobot tagitja
    upside_threshold = 1.0 - (0.08 * effect['upside_mult'])
    exceptional = roll >= upside_threshold

    if exceptional:
        # a kiugras merteke is fugg a csaladtol, de korlatozottan
        tgv += 6.0 * effect['upside_mult']

    return {
        'tgv': round(min(99.0, tgv), 1),
        'exceptional': exceptional,
        'upside_chance_pct': round(0.08 * effect['upside_mult'] * 100, 1),
    }


# =======================================================================
# 5) MEGJELENITES A KATALOGUSLAPON
# =======================================================================
# A JATEKOS DONTESE: a csalad LATSZODJON - a vervonal-epites fontos.
def describe_family_for_player(grade, generations, is_blue_hen=False):
    """A katalogus-lapon megjeleno csalad-sor."""
    effect = get_family_effect(grade)

    graded = sum(1 for gen in generations.values()
                 for o in gen if o == 'graded_winner')
    black_type = sum(1 for gen in generations.values()
                     for o in gen if o in ('graded_winner', 'stakes_winner', 'stakes_placed'))

    parts = [f"{grade} · {effect['label']}"]
    if is_blue_hen:
        parts[0] = f"{grade} · Blue hen vonal"
    if graded:
        parts.append(f"{graded} graded győztes a vonalban")
    elif black_type:
        parts.append(f"{black_type} black type a vonalban")

    return ' — '.join(parts)


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - FEMALE FAMILY (BLOODLINE) ENGINE v1.0 ===\n")

    print("--- 1) A CSALAD SULYA A SAJAT KEPESSEGHEZ KEPEST ---")
    print("  Valos adat (Blood-Horse 65 000+ kanca elemzese):")
    print("    versenyképes kanca      -> 5×  graded stakes győztes az átlaghoz képest")
    print("    erős női család         -> 2×  graded stakes győztes az átlaghoz képest")
    print("  -> A család kb. FELE akkora súllyal hat. Ezt a modell közvetlenül tükrözi:\n")
    for g in ['A+', 'A-', 'B', 'C', 'E']:
        e = get_family_effect(g)
        print(f"    {g:3s} {e['label']:24s} középérték {e['mean_shift']:+.1f}  "
              f"kiugrás esélye ×{e['upside_mult']:.1f}")
    print()

    print("--- 2) CSALADPONTSZAM ES BESOROLAS ---")
    families = {
        'Fall Aspen-szerű vonal': {
            1: ['graded_winner', 'graded_winner', 'stakes_winner', 'winner'],
            2: ['graded_winner', 'stakes_winner', 'winner'],
            3: ['stakes_winner', 'winner', 'unraced'],
        },
        'Win Approval-szerű': {
            1: ['graded_winner', 'graded_winner', 'graded_winner', 'graded_winner',
                'winner', 'winner', 'unraced', 'unraced', 'unraced', 'unraced'],
            2: ['winner', 'unraced'],
        },
        'Szolid, rendezett': {
            1: ['stakes_placed', 'winner', 'winner'],
            2: ['stakes_winner', 'winner'],
        },
        'Nyomtalan vonal': {
            1: ['unraced', 'winner', 'unraced'],
            2: ['unraced', 'unraced'],
        },
    }
    for name, gens in families.items():
        bh = check_blue_hen(gens.get(1, []))['is_blue_hen']
        score = calculate_family_score(gens, bh)
        grade = family_grade(gens, bh)
        tag = " [blue hen]" if bh else ""
        print(f"  {name:24s} pontszám: {score:5.1f}  ->  {grade}{tag}")
    print()

    print("--- 3) BLUE HEN CIM (küszöb: 3 black type győztes) ---")
    cases = [
        ('Win Approval', ['graded_winner', 'graded_winner', 'graded_winner',
                          'graded_winner', 'winner', 'unraced']),
        ('Két győztes',  ['stakes_winner', 'graded_winner', 'winner', 'unraced']),
        ('Egy győztes',  ['stakes_winner', 'winner', 'winner']),
    ]
    for name, offspring in cases:
        r = check_blue_hen(offspring)
        status = "BLUE HEN" if r['is_blue_hen'] else f"még {r['needed']} kell"
        print(f"  {name:14s} {r['qualifying_count']} minősülő utód -> {status}")
    print()

    print("--- 4) A LENYEG: a csalad a FELSO SZELET nyujtja, nem az atlagot ---")
    print("  Ugyanaz a 62-es alap genetikai ertek, kulonbozo csaladokkal,")
    print("  1000 szimulalt csiko:\n")
    import random
    random.seed(11)
    for g in ['E', 'C', 'A-', 'A+']:
        tgvs = []
        exceptional_count = 0
        for _ in range(1000):
            r = apply_family_to_foal(62.0, g, random.random())
            tgvs.append(r['tgv'])
            if r['exceptional']:
                exceptional_count += 1
        avg = sum(tgvs) / len(tgvs)
        top = max(tgvs)
        e = get_family_effect(g)
        print(f"  {g:3s} átlag: {avg:5.2f}  legjobb: {top:5.1f}  "
              f"kiugró csikó: {exceptional_count/10:.1f}%  ({e['label']})")
    print()
    print("  -> Az ÁTLAG alig mozdul (a saját genetika marad a döntő),")
    print("     de a kiugró csikó esélye A+ családnál közel háromszoros.\n")

    print("--- 5) MEGJELENITES A KATALOGUSLAPON ---")
    for name, gens in families.items():
        bh = check_blue_hen(gens.get(1, []))['is_blue_hen']
        grade = family_grade(gens, bh)
        print(f"  {name:24s} \"Család: {describe_family_for_player(grade, gens, bh)}\"")
    print()

    print("--- 6) VALIDACIO ---")
    # a csalad-hatas atlagra gyakorolt hatasa maradjon CSEKELY
    random.seed(99)
    avg_by_grade = {}
    for g in ['E', 'C', 'A+']:
        tgvs = [apply_family_to_foal(62.0, g, random.random())['tgv'] for _ in range(4000)]
        avg_by_grade[g] = sum(tgvs) / len(tgvs)

    spread = avg_by_grade['A+'] - avg_by_grade['E']

    checks = [
        ('A család átlagra gyakorolt hatása korlátozott (< 6 pont)',
         spread < 6.0),
        ('A kiugrás esélye A+ családnál legalább kétszeres a C-hez képest',
         get_family_effect('A+')['upside_mult'] / get_family_effect('C')['upside_mult'] >= 2.0),
        ('A saját genetika marad a domináns (a 62-es alap dominál)',
         all(55 < v < 70 for v in avg_by_grade.values())),
        ('Win Approval-szerű vonal blue hen',
         check_blue_hen(families['Win Approval-szerű'][1])['is_blue_hen']),
        ('Két black type győztes még nem blue hen',
         not check_blue_hen(['stakes_winner', 'graded_winner', 'winner'])['is_blue_hen']),
        ('A nyomtalan vonal E vagy D besorolást kap',
         family_grade(families['Nyomtalan vonal']) in ('E', 'D')),
        ('A Win Approval-szerű blue hen vonal A sávba kerül',
         family_grade(families['Win Approval-szerű'], True) in ('A+', 'A', 'A-')),
        ('A blue hen cím érdemben emeli a vonal pontszámát',
         # kozepmezonyos vonal, ami EPP most lepett at blue hen statuszba -
         # a Win Approval-szeru csucs mar a bonusz nelkul is 99-en van,
         # ott a bonusz lathatatlan. A cim akkor szamit igazan, amikor
         # egy vonal ATLEPI a kuszobot.
         calculate_family_score({1: ['stakes_winner', 'stakes_winner',
                                     'stakes_winner', 'unraced', 'unraced', 'unraced']}, True)
         > calculate_family_score({1: ['stakes_winner', 'stakes_winner',
                                       'stakes_winner', 'unraced', 'unraced', 'unraced']}, False)),
        ('A "nagyon jó rekord" referencia (Van Leer) A- körül landol',
         family_grade({1: ['graded_winner', 'stakes_placed', 'stakes_placed',
                           'winner', 'unraced', 'unraced']}) in ('A-', 'B+', 'A')),
        ('A távolabbi generációk kisebb súllyal számítanak',
         GENERATION_WEIGHT[1] > GENERATION_WEIGHT[2] > GENERATION_WEIGHT[3] > GENERATION_WEIGHT[4]),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print(f"\n  (A+ és E család közötti átlagkülönbség: {spread:.2f} pont)")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
