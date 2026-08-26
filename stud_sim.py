"""
Trot Heritage - Stud Book Engine v1.0
=======================================================================
A MEN-OLDAL: szezononkenti fedeztetesi konyv, kanca-jogosultsag,
globalis menlista es a kereslet valtozasa az ivadekteljesitmeny
alapjan.

ALAPELVEK (a jatekos dontesei):
  - A men ELETE VEGEIG fedezhet; a kora NEM jelenik meg markansan az
    utod genetikai osszetetelében (ellentetben a kancaval, ahol a
    tenyeszcsik fogy).
  - Szezononkent viszont KORLATOZOTT a konyv merete.
  - A mentulajdonos KOVETELMENYT tamaszthat: milyen kanca johet.
  - A jatekos menjenek meg kell ugrania egy kuszobot, hogy a GLOBALIS
    menlistara kerulhessen -> ez zarja ki a tobb-accountos csalast.
  - SAJAT men x SAJAT kanca: korlatlan, semmilyen megkotes nelkul.
  - A regi menek nem a koruk miatt esnek ki, hanem mert az uj menek
    megjelenesevel elvesztik a KERESLETET - kiveve azt az egy-ket
    ment, akinek az ivadekai bizonyitanak.

=======================================================================
FORRASOK
=======================================================================

1. The Jockey Club, Rule 14C (American Stud Book), 2020. majus 7.:
   a 2020-ban vagy kesobb szuletett menek legfeljebb 140 kancat
   fedezhetnek naptari evente. Indok: "a declining and concerning
   degree of diversity within the Thoroughbred gene pool".
   -> A jatek 140-es felso plafonja ONNAN szarmazik.
   https://paulickreport.com/news/bloodstock/the-jockey-club-rescinds-stud-book-cap-rule/
   https://www.bloodhorse.com/horse-racing/articles/246336/farms-file-lawsuit-challenging-cap-on-mares-bred

2. A diverzitas-romlas adatai (a Jockey Club "mares bred" jelenteseibol,
   a TrueNicks/BloodHorse osszefoglaloja szerint):
     - 1991: mindossze EGY men (Alydar) fedezett 100+ kancat
     - 1996: mar 14 ilyen men
     - 2007: 5 894 kanca (a teljes allomany 9.5%-a) 140+ konyvu mentol
     - 2019: 7 415 kanca (27%) - HAROMSZOROS novekedes
   -> EZ a fo indok, amiert egy KOZOS ONLINE ADATBAZISBAN is kell a
   korlat: nelkule nehany elit men elnyelne a teljes genallomanyt.
   https://www.truenicks.com/articles/246953/the-jockey-club-requests-dismissal-of-stallion-cap-suit

3. A szabaly sorsa (a teljesseg kedveert): harom nagy menes
   (Spendthrift, Ashford/Coolmore, Three Chimneys) beperelte a Jockey
   Clubot; a szabalyt 2022. februar 17-en visszavontak, majd Kentucky
   torvenyben tiltotta meg a konyv-limitet. A JATEKBAN ez nem korlat -
   ott nincs kartelljog -, de a szam VALOS iparagi kalibraciobol jon.
   https://www.thoroughbreddailynews.com/jockey-club-rescinds-140-mare-cap-rule/

4. A BLACK TYPE mint menjelolt-kuszob: a valos iparagban egy men attol
   lesz menjelolt, hogy NYERT - a stakes-gyozelem/helyezes a belepo.
   (lasd listing_sim.py forrasait: Keeneland/Fasig-Tipton black type
   konvencio, ICSC 1981.)
   -> Ezert a globalis menlista kapuja a black type: egy masodik
   fiokkal tenyesztett lo nem lesz men attol, hogy letezik - ki kell
   vinni a palyara es meg kell vernie a valodi mezonyt.
"""

from enum import Enum


# =======================================================================
# 1) EGYSEGES A-E SKALA (azonos a tobbi modullal)
# =======================================================================
GRADE_ORDER = ['E', 'D', 'C', 'B-', 'B', 'B+', 'A-', 'A', 'A+']


def grade_rank(grade):
    """A fokozat szamszerusitve az osszehasonlitashoz (E=0 ... A+=8)."""
    return GRADE_ORDER.index(grade) if grade in GRADE_ORDER else 0


def meets_grade(actual, required):
    """Eleri-e az 'actual' fokozat a 'required' szintet?"""
    if required is None:
        return True
    return grade_rank(actual) >= grade_rank(required)


# =======================================================================
# 2) SZEZON-KONYV ES KANCA-KOVETELMENY A MEN INDEXE SZERINT
# =======================================================================
# A felso plafon 140 - a Jockey Club Rule 14C valos szamabol (forras 1.).
#
# A KANCA-KOVETELMENY MAGA A DIVERZITAS-FEK: egy A+ men 140-es konyve
# onmagaban veszelyes lenne (forras 2.), de ha csak A- kancat fogad,
# a jatekosok tobbsege eleve nem fer hozza - igy a genallomany
# szetterul anelkul, hogy mesterseges korlatot kellene bevezetni.
STUD_TIERS = {
    'A+': {'book': 140, 'min_mare_index': 'A-', 'min_mare_health': 'B'},
    'A':  {'book': 140, 'min_mare_index': 'B+', 'min_mare_health': 'B-'},
    'A-': {'book': 130, 'min_mare_index': 'B',  'min_mare_health': 'B-'},
    'B+': {'book': 110, 'min_mare_index': 'B-', 'min_mare_health': 'C'},
    'B':  {'book':  90, 'min_mare_index': 'C',  'min_mare_health': 'C'},
    'B-': {'book':  70, 'min_mare_index': None, 'min_mare_health': None},
    'C':  {'book':  70, 'min_mare_index': None, 'min_mare_health': None},
    'D':  {'book':  50, 'min_mare_index': None, 'min_mare_health': None},
    'E':  {'book':  50, 'min_mare_index': None, 'min_mare_health': None},
}

# NINCS KOR-ALAPU KONYVCSOKKENES.
#
# A JATEKOS DONTESE: a konyvcsokkenest a PIAC generalja, nem a szabaly.
# Egy kulonleges szinu, jo orokito men akar az eletciklusa vegen is
# maximumon fedezhet, ha van ra kereslet. Fordítva: egy gyenge ivadeku
# men mar 8 evesen kiszorul - nem a kora, hanem az ivadekteljesitmenye
# miatt (lasd a kereslet-modellt lentebb).
#
# Egy korabbi valtozatban volt egy kor-alapu taper (18 evtol 85%, stb.) -
# ez KIKERULT, mert ketszeresen buntetett volna ugyanazert.
def get_season_book(stud_index, age=None):
    """A men adott szezonban elerheto MAXIMALIS konyvmeretet adja.
    A tenyleges kihasznaltsagot a KERESLET donti el (lasd 7. blokk).

    Az 'age' parameter megmaradt a hivasok kompatibilitasa miatt, de
    NEM befolyasol semmit."""
    return STUD_TIERS[stud_index]['book']


# =======================================================================
# 2b) MENTULAJDONOSI POLITIKA: valogatos vagy nyitott
# =======================================================================
# A JATEKOS DONTESE: ne legyen MINDEN mennel megkotes. Ket fele
# mentulajdonos van, es ez ketfele UTAT ad a jatekosnak ugyanahhoz az
# elit vervonalhoz:
#
#   VALOGATOS (selective): elvarja a jo kancat, cserebe a fedeztetesi
#     dij merskeltebb. Az "arat" a kanca minosegevel fizeted meg.
#     -> Az epitkezo jatekos utja: hozd fel a kancavonaladat.
#
#   NYITOTT (open): barmilyen kancat fogad, de a dij jelentosen magasabb.
#     -> A tokeeros jatekos utja: fizesd meg a hozzaferest.
#
# Igy senki nem akad el: aki meg nem tud jo kancat felmutatni, az
# penzzel is elorejuthat, es forditva.
#
# Ez valos iparagi mintat is kovet: az elit menek a gyakorlatban
# valogatnak (megtehetik), mig egyes kereskedelmi menesek mindenkit
# fogadnak - magasabb dijert.
STUD_POLICY_SELECTIVE = 'selective'
STUD_POLICY_OPEN = 'open'

# A nyitott men ennyiszeres dijat ker ugyanazert a genetikai minosegert
OPEN_POLICY_FEE_MULTIPLIER = 2.0


# =======================================================================
# 3) KANCA-JOGOSULTSAG: csak VALOGATOS mennel van megkotes
# =======================================================================
# A kovetelmeny KET dolgot ved:
#   - a tenyeszindex a men vervonalanak minoseget (kuratori dontes)
#   - az egeszseg a men SZUKOS FEROHELYET a karba veszett fedeztetestol
#     (lasd az 6. blokk vemhesulesi modelljet: egy meddon maradt
#     fedeztetes elpazarol egyet a 140-bol)
#
# FONTOS: a szelektiv tenyesztes NEM visszaeles, hanem MAGA A JATEK.
# Aki generaciokon at felhozza a kancavonalat C-rol A-ra, az jol
# jatszik. A kovetelmeny nem ez ellen ved, hanem a feroely-pazarlas
# ellen.
class Rejection(Enum):
    INDEX_TOO_LOW = 'A kanca tenyészindexe nem éri el a mén elvárását.'
    HEALTH_TOO_LOW = 'A kanca egészségi állapota nem éri el a mén elvárását.'
    NO_HEALTH_REPORT = 'A mén tulajdonosa állatorvosi felmérést vár el a kancáról.'
    BOOK_FULL = 'A mén szezonkönyve betelt.'
    NOT_LISTED = 'Ez a mén nem szerepel a globális ménlistán.'


def check_mare_eligibility(stud, mare, bookings_this_season, same_owner=False):
    """Fedeztethető-e ez a kanca ezzel a ménnel?

    same_owner=True eseten (SAJAT men x SAJAT kanca) NINCS semmilyen
    megkotes - sem index, sem egeszseg, sem konyvmeret, sem listazas."""
    if same_owner:
        return {'allowed': True, 'reasons': [], 'note': 'Saját mén × saját kanca — korlátozás nélkül.'}

    reasons = []

    if not stud.get('globally_listed', False):
        reasons.append(Rejection.NOT_LISTED)

    # A NYITOTT men nem tamaszt kanca-kovetelmenyt - csak a konyvmeret
    # es a listazas korlatoz.
    if stud.get('policy', STUD_POLICY_SELECTIVE) == STUD_POLICY_SELECTIVE:
        tier = STUD_TIERS[stud['index']]

        if not meets_grade(mare['breeding_index'], tier['min_mare_index']):
            reasons.append(Rejection.INDEX_TOO_LOW)

        if tier['min_mare_health'] is not None:
            if mare.get('health_grade') is None:
                reasons.append(Rejection.NO_HEALTH_REPORT)
            elif not meets_grade(mare['health_grade'], tier['min_mare_health']):
                reasons.append(Rejection.HEALTH_TOO_LOW)

    if bookings_this_season >= get_season_book(stud['index'], stud['age']):
        reasons.append(Rejection.BOOK_FULL)

    return {'allowed': len(reasons) == 0, 'reasons': reasons, 'note': None}


def get_stud_fee(stud, base_fee):
    """A fedeztetesi dij: a nyitott men ugyanazert a genetikai minosegert
    lenyegesen tobbet ker, mert nem tamaszt kanca-kovetelmenyt."""
    if stud.get('policy', STUD_POLICY_SELECTIVE) == STUD_POLICY_OPEN:
        return int(round(base_fee * OPEN_POLICY_FEE_MULTIPLIER))
    return base_fee


def describe_stud_requirements(stud):
    """A mentulajdonos elvarasai, jatekosnak megjelenitheto formaban."""
    if stud.get('policy', STUD_POLICY_SELECTIVE) == STUD_POLICY_OPEN:
        return 'Nyitott: bármilyen kancát fogad — magasabb fedeztetési díjért.'
    tier = STUD_TIERS[stud['index']]
    if tier['min_mare_index'] is None:
        return 'Nincs elvárás a kancával szemben.'
    return (f"Válogatós: legalább {tier['min_mare_index']} tenyészindex "
            f"és {tier['min_mare_health']} egészségi állapot.")


# =======================================================================
# 4) GLOBALIS MENLISTA - a tobb-accountos csalas kapuja
# =======================================================================
# A KUSZOB: black type (stakes-gyozelem VAGY -helyezes) ES legalabb
# B+ tenyeszindex.
#
# Miert ez zarja ki a csalast: egy masodik fiokkal tenyesztett lo nem
# lesz attol men, hogy letezik - ki kell vinni a palyara es meg kell
# vernie a VALODI mezonyt. Ez nem hamisithato meg sajat fiokok kozott.
#
# Aki nem eri el a kuszobot, tovabbra is fedezhet - de CSAK sajat
# kancat, korlatlanul (lasd same_owner). Igy senki nem veszti el a
# sajat lovat, csak a globalis piacra nem kerul be.
GLOBAL_LIST_MIN_INDEX = 'B+'


def check_global_listing(horse):
    """Bekerulhet-e ez a men a globalis menlistara?"""
    reasons = []
    has_black_type = horse.get('black_type') in ('stakes_winner', 'stakes_placed')

    if not has_black_type:
        reasons.append('Nincs black type — a ménnek stakes-győzelem vagy -helyezés kell.')
    if not meets_grade(horse['breeding_index'], GLOBAL_LIST_MIN_INDEX):
        reasons.append(f"A tenyészindex nem éri el a {GLOBAL_LIST_MIN_INDEX} szintet.")

    return {
        'listed': len(reasons) == 0,
        'reasons': reasons,
        'private_breeding_note': 'Saját kancákkal továbbra is korlátlanul fedeztethető.',
    }


# =======================================================================
# 6) VEMHESULES - valoszinuseg, nem kapu
# =======================================================================
# Az egeszseg NEM azert szamit, mert manipulalhatatlan - hanem mert a
# fedeztetes egyszeruen NEM SIKERUL. Egy meddon maradt fedeztetes
# elpazarol egyet a men 140 feroelyebol; EZERT tamaszt elvarast a
# valogatos mentulajdonos.
#
# VALOS ADATOK (amikre a modell epul):
#   - A teliver termekenysegi aranya kb. 60%; egy tenyeszfarmon a 65%-os
#     vemhesulesi arany szamit atlagosnak.
#     https://www.myhorseuniversity.com/single-post/2017/09/25/breeding-the-mare-factors-that-can-influence-conception-rates
#   - Egy felmeresben a kancak 83%-a lett valamikor vemhes, es a
#     vemhesek 80%-a hozott elo csikot (~66% vegeredmeny).
#     https://pubmed.ncbi.nlm.nih.gov/15338910/
#   - A KOR a legerosebb elorejelzo: a 10 evesnel fiatalabb kancak
#     csaknem HAROMSZOR nagyobb esellyel hoztak elo csikot.
#     https://ker.com/equinews/mare-age-biggest-predictor-of-foaling-success/
#   - Fiatal, egeszseges kanca: 50-60% ciklusonkent; idosebb: 30-40%
#     vagy kevesebb. A termekenyseg kb. 15 eves kortol hanyatlik.
#     https://nexgenvetrx.com/blog/equine/breedingproducts/when-is-a-mare-too-old-to-breed/
#   - ALLAPOT szerinti elso fedeztetesi aranyok: 54% csikos, 44% maiden,
#     40% meddo. Ot ciklus utan kumulaltan 84 / 84 / 74%.
#     https://pubmed.ncbi.nlm.nih.gov/1060797/
#   - Az idos maiden kancakat kozismerten nehez vemhesbe hozni
#     ("use it or lose it").
#
# JATEKTERVEZESI ELTERES - TUDATOSAN MEGENGEDOBB:
# A valos ~60-65%-os atlag egy jatekban tul buntetoe lenne (minden
# harmadik fedeztetes eredmenytelen). A jatekos kifejezett kerese
# alapjan az alaprataakat FELJEBB kalibraltuk, es a modositokat
# LAGYABBRA vettuk. Igy a tipikus eset kb. 78-85% kozott mozog, es a
# valodi kockazat csak a szelsosegeknel (nagyon idos, gyenge egeszsegu,
# meddo kanca) jelenik meg. Az ARANYOK a valos adatokat kovetik, csak
# a szintjuk emelt - ez dokumentalt jatektervezesi dontes.
CONCEPTION_BASE = {
    'foaling':  78.0,   # elozo evben ellett - a valosagban is a legjobb
    'maiden':   70.0,   # meg nem ellett
    'barren':   65.0,   # tavaly nem fogant
    'rested':   58.0,   # kihagyott szezon - "use it or lose it"
}

CONCEPTION_AGE_MULT = [
    (18, 0.70),   # 18+ ev
    (15, 0.85),   # 15-17 ev - itt kezdodik a valos hanyatlas
    (11, 1.00),   # 11-14 ev
    (0,  1.10),   # 10 ev alatt - a valos adat szerint a legjobb
]

OLD_MAIDEN_AGE = 15
OLD_MAIDEN_MULT = 0.75   # idos maiden kanca - lagyitva a valos "notorious"-hoz kepest

CONCEPTION_HEALTH_MULT = {
    'A+': 1.08, 'A': 1.08, 'A-': 1.08,
    'B+': 1.00, 'B': 1.00, 'B-': 1.00,
    'C': 0.85, 'D': 0.85, 'E': 0.85,
}
CONCEPTION_NO_REPORT_MULT = 0.95   # nincs felmeres: enyhe bizonytalansag


def _age_multiplier(age):
    for threshold, mult in CONCEPTION_AGE_MULT:
        if age >= threshold:
            return mult
    return 1.0


def conception_probability(mare):
    """Mekkora esellyel fogan meg a kanca ebben a szezonban?

    mare mezoi: age, status ('foaling'|'maiden'|'barren'|'rested'),
                health_grade (vagy None)
    """
    base = CONCEPTION_BASE.get(mare.get('status', 'maiden'), 65.0)
    p = base * _age_multiplier(mare['age'])

    if mare.get('status') == 'maiden' and mare['age'] >= OLD_MAIDEN_AGE:
        p *= OLD_MAIDEN_MULT

    hg = mare.get('health_grade')
    p *= CONCEPTION_HEALTH_MULT.get(hg, CONCEPTION_NO_REPORT_MULT) if hg else CONCEPTION_NO_REPORT_MULT

    return round(max(5.0, min(95.0, p)), 1)


def describe_conception_for_player(mare):
    """A jatekosnak megjelenitett becsles - szandekosan SAVOKBAN, nem
    pontos szazalekban (ugyanaz az elv, mint az A-E indexnel: a
    jatekos kovetkeztet, nem tudja meg pontosan)."""
    p = conception_probability(mare)
    if p >= 80: return 'Kiváló esély'
    if p >= 68: return 'Jó esély'
    if p >= 55: return 'Mérsékelt esély'
    if p >= 40: return 'Bizonytalan'
    return 'Csekély esély'


# =======================================================================
# 7) KERESLET - az ivadekteljesitmeny, nem a kor
# =======================================================================
# A JATEKOS MEGFIGYELESE: "az uj menek bekerulesevel egy-ket kivetellel
# a regiek elvesztik az erdeklodest". Ez valos jelenseg - es a
# differencial NEM a kor, hanem az IVADEKTELJESITMENY: akinek az elso
# ivadekai jol futnak, evtizedekig tartja a konyvet; akie nem, kiesik.
#
# Idozites: a men 4 evesen kerul mének koze, az elso ivadekai 3 evvel
# kesobb futnak eloszor -> a "pillanat igazsag" kb. 7-8 eves korban jon.
UNPROVEN_SEASONS = 3          # ennyi szezonig meg nincs futo ivadek
APPEAL_DECAY_UNPROVEN = 4     # szezononkenti lemorzsolodas, amig nincs bizonyitek
APPEAL_PULL_TO_PROGENY = 0.75 # ennyire erosen huzza az ivadek-eredmeny a keresletet

# AZ UJ MENEK FOLYAMATOS NYOMASA: evrol evre erkeznek frissebb menek, ezert
# a bizonyitott fazisban is van egy szezononkenti eroziо - DE ezt a jo
# ivadekteljesitmeny teljesen semlegesiti. Ez adja a jatekos altal leirt
# kepet: "egy-ket kivetellel a regiek elvesztik az erdeklodest".
PROGENY_HOLD_THRESHOLD = 75   # e folott a men "beerkezett", nem kopik tovabb
APPEAL_EROSION = [
    (75, 0.0),   # kivalo ivadek -> tartja a konyvet evtizedekig
    (55, 1.0),   # kozepes ivadek -> lassan kopik
    (0,  2.5),   # gyenge ivadek -> gyorsan kiszorul
]


def _erosion_rate(progeny_performance):
    for threshold, rate in APPEAL_EROSION:
        if progeny_performance >= threshold:
            return rate
    return APPEAL_EROSION[-1][1]


def calculate_commercial_appeal(stud):
    """A men KERESLETE 0-100 kozott. Ez donti el, hogy a szezonkonyve
    mennyire telik meg - nem a plafon merete.

    stud mezoi:
      index, age, seasons_at_stud, progeny_performance (None vagy 0-100)
    """
    base = grade_rank(stud['index']) / 8 * 100   # induloertek a sajat indexebol
    seasons = stud.get('seasons_at_stud', 0)
    progeny = stud.get('progeny_performance')

    if progeny is None or seasons < UNPROVEN_SEASONS:
        # meg nincs bizonyitek: a kezdeti lelkesedes evrol evre kopik,
        # ahogy ujabb, frissebb menek erkeznek
        appeal = base - APPEAL_DECAY_UNPROVEN * seasons
    else:
        # megjottek az elso ivadekok: a kereslet erosen ATALL rajuk
        appeal = base * (1 - APPEAL_PULL_TO_PROGENY) + progeny * APPEAL_PULL_TO_PROGENY
        # majd az uj menek nyomasa alatt tovabb kopik - kiveve, ha az
        # ivadekteljesitmeny tartosan kivalo
        proven_seasons = seasons - UNPROVEN_SEASONS
        appeal -= _erosion_rate(progeny) * proven_seasons

    return max(0, min(100, round(appeal, 1)))


def project_bookings(stud):
    """Hany kanca jon ossze ténylegesen a szezonban: a plafon es a
    kereslet szorzata."""
    cap = get_season_book(stud['index'], stud['age'])
    appeal = calculate_commercial_appeal(stud)
    return {
        'cap': cap,
        'appeal': appeal,
        'expected_bookings': int(round(cap * appeal / 100)),
    }


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - STUD BOOK ENGINE v1.0 ===\n")

    print("--- 1) SZEZON-KONYV ES KANCA-KOVETELMENY (plafon: 140, Jockey Club Rule 14C) ---")
    print(f"  {'Index':6s} {'Könyv':>6s}  {'Kanca-elvárás':38s}")
    for idx in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C', 'D', 'E']:
        t = STUD_TIERS[idx]
        req = (f"min. {t['min_mare_index']} index + {t['min_mare_health']} egészség"
               if t['min_mare_index'] else "nincs elvárás")
        print(f"  {idx:6s} {t['book']:6d}  {req:38s}")
    print("\n  A követelmény maga a diverzitás-fék: egy A+ mén 140-es könyve")
    print("  önmagában veszélyes lenne, de A- kanca-elvárással a játékosok")
    print("  többsége eleve nem fér hozzá.\n")

    print("--- 2) A KOR NEM CSOKKENTI A KONYVET ---")
    for age in [4, 10, 18, 24]:
        print(f"  A+ mén, {age:2d} éves -> könyv: {get_season_book('A+', age):3d}")
    print("  A könyvcsökkenést a PIAC generálja, nem a szabály.")
    print("  Egy különleges színű, jó örökítő mén az életciklusa végén is")
    print("  maximumon fedezhet — ha van rá kereslet.\n")

    print("--- 3) KANCA-JOGOSULTSAG ELLENORZES ---")
    elite_stud = {'name': 'Ironvale', 'index': 'A+', 'age': 7, 'globally_listed': True,
                  'policy': STUD_POLICY_SELECTIVE}
    open_elite = {'name': 'Goldmarket', 'index': 'A+', 'age': 8, 'globally_listed': True,
                  'policy': STUD_POLICY_OPEN}
    mid_stud = {'name': 'Redbarn', 'index': 'B', 'age': 9, 'globally_listed': True,
                'policy': STUD_POLICY_SELECTIVE}
    unlisted = {'name': 'Homefield', 'index': 'A-', 'age': 6, 'globally_listed': False,
                'policy': STUD_POLICY_SELECTIVE}

    mares = [
        {'name': 'Amber Thistledown', 'breeding_index': 'A',  'health_grade': 'A-'},
        {'name': 'Quiet Meridian',    'breeding_index': 'B+', 'health_grade': 'B'},
        {'name': 'Frostbramble',      'breeding_index': 'C',  'health_grade': None},
    ]

    for stud in [elite_stud, open_elite, mid_stud, unlisted]:
        print(f"  {stud['name']} ({stud['index']}) — {describe_stud_requirements(stud)}")
        for m in mares:
            r = check_mare_eligibility(stud, m, bookings_this_season=0)
            mark = "IGEN" if r['allowed'] else "NEM "
            why = "" if r['allowed'] else "  · " + " ".join(x.value for x in r['reasons'])
            print(f"     [{mark}] {m['name']:20s} ({m['breeding_index']}/{m['health_grade']}){why}")
        print()

    print("--- 4) SAJAT MEN x SAJAT KANCA: korlatozas nelkul ---")
    r = check_mare_eligibility(elite_stud, mares[2], bookings_this_season=999, same_owner=True)
    print(f"  Ironvale (A+) × Frostbramble (C/nincs felmérés), betelt könyv mellett:")
    print(f"     [{'IGEN' if r['allowed'] else 'NEM'}] {r['note']}\n")

    print("--- 4b) KET UT UGYANAHHOZ A GENETIKAI MINOSEGHEZ ---")
    BASE_FEE = 9000
    for stud in [elite_stud, open_elite]:
        pol = 'VÁLOGATÓS' if stud['policy'] == STUD_POLICY_SELECTIVE else 'NYITOTT'
        print(f"  {stud['name']:12s} (A+, {pol:10s}) díj: {get_stud_fee(stud, BASE_FEE):6d} B$")
        print(f"     {describe_stud_requirements(stud)}")
    print("  -> Ugyanaz a genetikai minőség: vagy felhozod a kancádat, vagy megfizeted.\n")

    print("--- 4c) VEMHESULESI ESELY (valoszinuseg, nem kapu) ---")
    demo_mares = [
        {'name': 'fiatal csikós, A egészség', 'age': 8,  'status': 'foaling', 'health_grade': 'A'},
        {'name': 'átlagos, B egészség',       'age': 12, 'status': 'foaling', 'health_grade': 'B'},
        {'name': 'maiden, felmérés nélkül',   'age': 6,  'status': 'maiden',  'health_grade': None},
        {'name': 'meddő, C egészség',         'age': 16, 'status': 'barren',  'health_grade': 'C'},
        {'name': 'pihentetett, 19 éves',      'age': 19, 'status': 'rested',  'health_grade': 'B'},
        {'name': 'idős maiden (17)',          'age': 17, 'status': 'maiden',  'health_grade': 'B'},
    ]
    for m in demo_mares:
        p = conception_probability(m)
        print(f"  {m['name']:28s} {p:5.1f}%  → \"{describe_conception_for_player(m)}\"")
    avg = sum(conception_probability(m) for m in demo_mares) / len(demo_mares)
    print(f"  (a hat példa átlaga: {avg:.1f}% — a tipikus eset jóval e fölött van)\n")

    print("--- 5) GLOBALIS MENLISTA - a tobb-accountos csalas kapuja ---")
    candidates = [
        {'name': 'Ironvale',   'breeding_index': 'A',  'black_type': 'stakes_winner'},
        {'name': 'Hollowmere', 'breeding_index': 'A-', 'black_type': 'stakes_placed'},
        {'name': 'Paperclip',  'breeding_index': 'A+', 'black_type': None},
        {'name': 'Dustlane',   'breeding_index': 'B',  'black_type': 'stakes_winner'},
    ]
    for c in candidates:
        res = check_global_listing(c)
        mark = "LISTÁZVA" if res['listed'] else "ELUTASÍTVA"
        bt = c['black_type'] or 'nincs'
        print(f"  [{mark:10s}] {c['name']:12s} index={c['breeding_index']:3s} black type={bt}")
        for rr in res['reasons']:
            print(f"       · {rr}")
        if not res['listed']:
            print(f"       · {res['private_breeding_note']}")
    print()

    print("--- 6) KERESLET AZ IVADEKTELJESITMENY ALAPJAN (nem a kor alapjan) ---")
    print("  Ket azonos indexu men, elteroe ivadekokkal:\n")
    for label, progeny in [("ivadékai kiválóan futnak", 88), ("ivadékai gyengén futnak", 34)]:
        print(f"  A mén {label}:")
        for season in [0, 2, 4, 8, 14, 20]:
            s = {'index': 'A', 'age': 4 + season, 'seasons_at_stud': season,
                 'progeny_performance': None if season < UNPROVEN_SEASONS else progeny}
            p = project_bookings(s)
            phase = "még bizonyítatlan" if season < UNPROVEN_SEASONS else "ivadékai futnak"
            print(f"    {4+season:2d} éves, {season:2d}. szezon ({phase:16s}) "
                  f"kereslet={p['appeal']:5.1f}  plafon={p['cap']:3d}  "
                  f"várható fedeztetés={p['expected_bookings']:3d}")
        print()

    print("  -> A gyenge ivadékú mén 20 év alatt sem esik ki 'kor' miatt,")
    print("     hanem mert a kereslet elhagyja. A jó ivadékú tartja a könyvét.\n")

    print("--- 7) VALIDACIO ---")
    checks = []
    checks.append(('A felső plafon 140 (Jockey Club Rule 14C)',
                   max(t['book'] for t in STUD_TIERS.values()) == 140))
    checks.append(('Saját mén × saját kanca mindig engedélyezett',
                   check_mare_eligibility(elite_stud, mares[2], 999, same_owner=True)['allowed']))
    checks.append(('Black type nélkül nincs globális listázás',
                   not check_global_listing(candidates[2])['listed']))
    checks.append(('B index + black type sem elég (B+ kell)',
                   not check_global_listing(candidates[3])['listed']))
    checks.append(('Nem listázott mén idegen kancát nem fogad',
                   not check_mare_eligibility(unlisted, mares[0], 0)['allowed']))
    checks.append(('A válogatós elit mén elutasítja a gyenge kancát',
                   not check_mare_eligibility(elite_stud, mares[2], 0)['allowed']))
    checks.append(('A NYITOTT elit mén ugyanazt a kancát elfogadja',
                   check_mare_eligibility(open_elite, mares[2], 0)['allowed']))
    checks.append(('A nyitott mén díja magasabb',
                   get_stud_fee(open_elite, 9000) > get_stud_fee(elite_stud, 9000)))
    checks.append(('Tipikus kanca vemhesülési esélye 75% felett',
                   conception_probability({'age': 10, 'status': 'foaling', 'health_grade': 'B'}) > 75))
    checks.append(('Szélsőséges eset érdemi kockázat (60% alatt)',
                   conception_probability({'age': 19, 'status': 'barren', 'health_grade': 'C'}) < 60))
    checks.append(('Jó ivadékú mén 20 szezon után is keresett',
                   project_bookings({'index': 'A', 'age': 24, 'seasons_at_stud': 20,
                                     'progeny_performance': 88})['appeal'] > 60))
    checks.append(('Gyenge ivadékú mén kiszorul (8. szezonra kereslet < 40)',
                   project_bookings({'index': 'A', 'age': 12, 'seasons_at_stud': 8,
                                     'progeny_performance': 34})['appeal'] < 40))
    checks.append(('Gyenge ivadékú mén 20 szezonra gyakorlatilag eltűnik',
                   project_bookings({'index': 'A', 'age': 24, 'seasons_at_stud': 20,
                                     'progeny_performance': 34})['expected_bookings'] < 15))

    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: {'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
