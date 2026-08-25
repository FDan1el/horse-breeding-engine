"""
Breeder Tycoon - Data Architecture v1.0
=======================================================================
HAROM RETEG, NEM KETTO.

A jatekos ket adatbazist kert: PEDIGRE es VERSENY. Ezek valoban kulon
kezelendok - de a legfontosabb kerdesek MINDKETTOT erintik:

  "Hany black type utodja van ennek a kancanak?"
     -> pedigre: keresd ki az utodait
     -> verseny: nezd meg az eredmenyeiket

Ezt kataloguslaponkent eloben lekerdezni DRAGA. Ezert kell egy
HARMADIK reteg: az AGGREGATUM, ami a ket adatbazis kozott all, es
irasnal frissul, nem olvasasnal szamolodik.

    +-------------+      +-------------+
    |  PEDIGRE    |      |   VERSENY   |
    |  lassan     |      |  append-only|
    |  valtozik   |      |  esemenynap |
    +------+------+      +------+------+
           |                    |
           +--------+-----------+
                    |
            +-------v--------+
            |   AGGREGATUM   |  <- irasnal frissul
            |  osszesitesek  |     olvasasnal csak lekerdezes
            +----------------+

=======================================================================
KET KULCS-DONTES, AMI SOK KESOBBI FAJDALMAT MEGSPOROL
=======================================================================

1. NOI CSALAD: NE rekurzivan szamold. Minden csiko SZULETESKOR
   megorokli az anyja family_id-jat. Igy a csalad-lekerdezes egyetlen
   indexelt kereses, nem generaciokon atnyulo rekurziv jaras.

2. PEDIGRE-MELYSEG: a kataloguslap 3-4 generaciot mutat, es ez a
   LEGGYAKORIBB OLVASASI UT. Ezert a lo sorába DENORMALIZALVA
   beletesszuk a 4 generacionyi ost (14 hely). Cserebe:
     - a kataloguslap egyetlen sorbol felepitheto
     - az inbreeding-szamitas halmazmetszet lesz, nem faseta
"""

from enum import Enum
from collections import defaultdict


# =======================================================================
# 1) PEDIGRE ADATBAZIS
# =======================================================================
# Lassan valtozik. Egy lo egyszer kerul be (szuletes vagy alapito
# generalas), es utana csak nehany mezoje modosul (tulajdonos, csikok).
PEDIGREE_SCHEMA = {
    'horse_id':        'uuid, elsodleges kulcs',
    'name':            'szoveg, egyedi (nevadasi szabaly: listing_sim.py)',
    'sex':             'colt | filly',
    'birth_season':    'egesz - melyik szezonban szuletett',

    # --- szarmazas ---
    'sire_id':         'uuid vagy null (alapito lo)',
    'dam_id':          'uuid vagy null',
    'family_id':       'uuid - a NOI VONAL azonositoja. A csiko az '
                       'ANYJATOL orokli. EZ A KULCS-DONTES: igy a '
                       'csalad-lekerdezes indexelt kereses, nem rekurzio.',

    # --- denormalizalt pedigre (a katalogus-olvasas gyorsitasa) ---
    'ancestors':       'tomb[14] - 2., 3., 4. generacio osei. '
                       'Redundans, de a kataloguslap igy EGYETLEN '
                       'sorbol felepitheto, es az inbreeding halmaz-'
                       'metszet lesz.',

    # --- rejtett genetika (a jatekos SOSEM latja) ---
    'genetics':        'jsonb - a 10 tulajdonsag valodi erteke (TGV)',
    'colour_genotype': 'jsonb - E/A/G/Cr lokusz',

    # --- lathato szarmaztatott ertekek ---
    'colour':          'szoveg - a genotipusbol szamitva',
    'rarity_tier':     'common | uncommon | rare | special',

    # --- tulajdon es tenyesztes ---
    'breeder_id':      'uuid - A TENYESZTOI PREMIUM CIMZETTJE. '
                       'SOHA nem valtozik, akkor sem, ha a lo gazdat cserel.',
    'owner_id':        'uuid - valtozik eladaskor',

    # --- eletciklus (lifecycle_sim.py) ---
    'life_bar':        'valos 0-100',
    'career_bar':      'valos 0-100',
    'breeding_bar':    'valos 0-100 vagy null (mennel null)',
    'freshness':       'valos 0-100',
    'stage':           'foal | yearling | racer | breeding | pensioned | retired_out',
}


# =======================================================================
# 2) VERSENY ADATBAZIS
# =======================================================================
# APPEND-ONLY esemenynaplo. Sosem modositunk, csak beszurunk. Ez teszi
# auditalhatova (csalasvedelem: integrity_sim.py) es visszajatszhatova.
RACE_SCHEMA = {
    'race_id':      'uuid',
    'season':       'egesz',
    'day':          'egesz 1-30',
    'time_utc':     'ido - a session-idopont (schedule_model.py)',
    'track_id':     'szoveg',
    'distance_f':   'egesz - furlong',
    'surface':      'dirt | turf | synthetic',
    'going':        'talajallapot',
    'bracket':      'nyeremenysav (track_sim.py)',
    'classic':      'null vagy a klasszikus azonositoja',
    'purse':        'egesz',
    'field_size':   'egesz 8-14',
}

RESULT_SCHEMA = {
    'race_id':      'uuid - idegen kulcs',
    'horse_id':     'uuid - idegen kulcs a PEDIGRE-be',
    'position':     'egesz',
    'earnings':     'egesz - a lo reszesedese',
    'jockey_id':    'uuid',
    'trainer_id':   'uuid',
    'injury':       'null | minor | moderate | serious',
    # a black type NEM itt tarolodik szarmaztatottkent, hanem az
    # aggregatum retegben osszesitve
}


# =======================================================================
# 3) AGGREGATUM RETEG - EZ KOTI OSSZE A KETTOT
# =======================================================================
# Minden ertek IRASNAL frissul (amikor egy futam eredmenye beerkezik),
# es olvasasnal csak lekerdezzuk. Igy a kataloguslap, a Hall of Fame es
# a men-kereslet mind egyetlen indexelt olvasas.
HORSE_STATS_SCHEMA = {
    'horse_id':          'uuid, elsodleges kulcs',
    # sajat versenyzes
    'starts':            'egesz',
    'wins':              'egesz',
    'places':            'egesz',
    'career_earnings':   'egesz',
    'black_type_wins':   'egesz',
    'classic_wins':      'egesz',
    'best_bracket':      'szoveg',
    # SZULOKENT - ezt a gyerekek futasa frissiti
    'progeny_count':     'egesz',
    'progeny_runners':   'egesz',
    'progeny_winners':   'egesz',
    'progeny_black_type':'egesz',
    'progeny_classic':   'egesz',
    'progeny_earnings':  'egesz',
}

FAMILY_STATS_SCHEMA = {
    'family_id':          'uuid',
    'generation_depth':   'egesz',
    'total_offspring':    'egesz',
    'black_type_count':   'egesz',
    'classic_count':      'egesz',
    'family_grade':       'A+ ... E (family_sim.py)',
    'is_blue_hen_line':   'logikai',
}

STUD_STATS_SCHEMA = {
    'stud_id':            'uuid',
    'seasons_at_stud':    'egesz',
    'mares_covered_total':'egesz',
    'mares_this_season':  'egesz - a 140-es konyv szamlaloja',
    'progeny_performance':'valos 0-100 - a kereslet-modell bemenete',
    'commercial_appeal':  'valos 0-100 - szamitott (stud_sim.py)',
    'globally_listed':    'logikai - black type + B+ index kell hozza',
}


# =======================================================================
# 4) A PROPAGACIO - MI TORTENIK EGY FUTAM UTAN
# =======================================================================
# EZ A LENYEG. Egy eredmeny beerkezese KEVES sort erint, ezert olcso.
class BlackTypeLevel(Enum):
    NONE = 'none'
    PLACED = 'placed'
    WINNER = 'winner'
    CLASSIC = 'classic'


def propagate_result(result, horse, race):
    """Milyen sorokat kell frissiteni egy futam eredmenye utan?

    Visszaadja a MUVELETI LISTAT - ebbol latszik, hogy a propagacio
    KORLATOZOTT: legfeljebb ~8 sort erint, fuggetlenul attol, mekkora
    a vilag.
    """
    ops = []
    pos = result['position']
    is_win = pos == 1
    bt = BlackTypeLevel.NONE
    if is_win and race.get('classic'):
        bt = BlackTypeLevel.CLASSIC
    elif is_win and race.get('black_type'):
        bt = BlackTypeLevel.WINNER
    elif pos <= 3 and race.get('black_type'):
        bt = BlackTypeLevel.PLACED

    # 1. a lo sajat statisztikaja
    ops.append({'table': 'horse_stats', 'key': horse['horse_id'],
                'change': f"starts +1, earnings +{result['earnings']}"
                          + (", wins +1" if is_win else "")
                          + (f", {bt.value} +1" if bt != BlackTypeLevel.NONE else "")})

    # 2-3. a KET SZULO ivadek-statisztikaja
    for parent_key in ('sire_id', 'dam_id'):
        pid = horse.get(parent_key)
        if pid:
            ops.append({'table': 'horse_stats', 'key': pid,
                        'change': f"progeny_earnings +{result['earnings']}"
                                  + (", progeny_winners +1" if is_win else "")
                                  + (f", progeny_{bt.value} +1"
                                     if bt in (BlackTypeLevel.WINNER, BlackTypeLevel.CLASSIC)
                                     else "")})

    # 4. a NOI CSALAD - EGYETLEN sor, mert a family_id oroklodik
    if bt != BlackTypeLevel.NONE and horse.get('family_id'):
        ops.append({'table': 'family_stats', 'key': horse['family_id'],
                    'change': f"{bt.value}_count +1, ujraszamolt family_grade"})

    # 5. a MEN kereslet-bemenete
    if horse.get('sire_id'):
        ops.append({'table': 'stud_stats', 'key': horse['sire_id'],
                    'change': "progeny_performance ujraszamolva"})

    # 6. TENYESZTOI PREMIUM - a tenyesztonek, nem a tulajdonosnak
    if result['earnings'] > 0 and horse.get('breeder_id'):
        premium = round(result['earnings'] * 0.15)
        ops.append({'table': 'accounts', 'key': horse['breeder_id'],
                    'change': f"balance +{premium} (tenyésztői prémium 15%)"})

    # 7. eletciklus-csikok
    ops.append({'table': 'pedigree', 'key': horse['horse_id'],
                'change': "career_bar -, freshness -, life_bar -"})

    # 8. serules eseten
    if result.get('injury'):
        ops.append({'table': 'pedigree', 'key': horse['horse_id'],
                    'change': f"soundness -, kihagyas ({result['injury']})"})

    return ops


# =======================================================================
# 5) UJ CSIKO BESZURASA
# =======================================================================
def insert_foal(sire, dam, breeder_id, season):
    """Mi tortenik, amikor megszuletik egy csiko?

    A KULCS: a family_id az ANYJATOL oroklodik, es a 4 generacionyi
    os DENORMALIZALVA belekerul a sorba.
    """
    # a 14 os-hely: 2 szulo + 4 nagyszulo + 8 dedszulo
    ancestors = (
        [sire['horse_id'], dam['horse_id']]
        + sire.get('ancestors', [None] * 6)[:6]
        + dam.get('ancestors', [None] * 6)[:6]
    )[:14]

    ops = [
        {'table': 'pedigree', 'op': 'INSERT',
         'detail': f"uj lo, sire={sire['name']}, dam={dam['name']}, "
                   f"family_id={dam.get('family_id')} (az ANYJATOL orokolt), "
                   f"breeder_id={breeder_id} (SOSEM valtozik)"},
        {'table': 'horse_stats', 'op': 'INSERT',
         'detail': 'ures statisztika-sor'},
        {'table': 'horse_stats', 'op': 'UPDATE', 'key': dam['horse_id'],
         'detail': 'progeny_count +1'},
        {'table': 'horse_stats', 'op': 'UPDATE', 'key': sire['horse_id'],
         'detail': 'progeny_count +1'},
        {'table': 'family_stats', 'op': 'UPDATE', 'key': dam.get('family_id'),
         'detail': 'total_offspring +1'},
        {'table': 'pedigree', 'op': 'UPDATE', 'key': dam['horse_id'],
         'detail': 'breeding_bar - (lifecycle_sim.py)'},
        {'table': 'stud_stats', 'op': 'UPDATE', 'key': sire['horse_id'],
         'detail': 'mares_this_season +1 (a 140-es konyv szamlaloja)'},
    ]
    return {'ancestors': ancestors, 'ops': ops}


# =======================================================================
# 6) INBREEDING - HALMAZMETSZET, NEM FASETA
# =======================================================================
def inbreeding_from_ancestors(sire, dam):
    """A denormalizalt os-tomb miatt ez EGYETLEN halmazmetszet.

    Rekurziv faseta nelkul, konstans idoben.
    """
    a = set(x for x in sire.get('ancestors', []) if x)
    b = set(x for x in dam.get('ancestors', []) if x)
    shared = a & b
    return {'shared_count': len(shared), 'shared': shared,
            'coefficient': min(len(shared) * 0.0625, 0.25)}


# =======================================================================
# 7) OLVASASI UTAK - MIT KERDEZ A JATEK?
# =======================================================================
READ_PATHS = [
    {'query': 'Katalóguslap egy lóra',
     'tables': ['pedigree (1 sor)', 'horse_stats (1 sor)', 'family_stats (1 sor)'],
     'cost': 'három indexelt olvasás — a 4 generációnyi ős a sorban van'},
    {'query': 'Egy kanca utódai és eredményeik',
     'tables': ['horse_stats (1 sor)'],
     'cost': 'EGYETLEN olvasás — az aggregátum már összesítve tárolja'},
    {'query': 'Női család erőssége',
     'tables': ['family_stats (1 sor)'],
     'cost': 'egyetlen indexelt olvasás a family_id-ra'},
    {'query': 'Mén kereslete és könyve',
     'tables': ['stud_stats (1 sor)'],
     'cost': 'egyetlen olvasás'},
    {'query': 'Hall of Fame rangsor',
     'tables': ['horse_stats (rendezett, top 100)'],
     'cost': 'indexelt rendezés, gyorsítótárazható'},
    {'query': 'Egy futam részletes eredménye',
     'tables': ['races (1 sor)', 'results (8-14 sor)'],
     'cost': 'a versenyadatbázis közvetlen lekérdezése'},
    {'query': 'Inbreeding két ló között',
     'tables': ['pedigree (2 sor)'],
     'cost': 'halmazmetszet a denormalizált ős-tömbön'},
]


# =======================================================================
# DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - ADATARCHITEKTURA ===\n")

    print("--- 1) HAROM RETEG ---")
    print("""
    +-------------+      +-------------+
    |  PEDIGRÉ    |      |   VERSENY   |
    |  lassan     |      |  append-only|
    |  változik   |      |  eseménynap |
    +------+------+      +------+------+
           |                    |
           +--------+-----------+
                    |
            +-------v--------+
            |   AGGREGÁTUM   |  <- íráskor frissül
            |  összesítések  |     olvasáskor csak lekérdezés
            +----------------+
    """)

    print("--- 2) A KET KULCS-DONTES ---")
    print("  a) NŐI CSALÁD: a csikó SZÜLETÉSKOR örökli az anyja family_id-ját.")
    print("     Így a család-lekérdezés indexelt keresés, nem rekurzió.\n")
    print("  b) PEDIGRÉ-MÉLYSÉG: 4 generációnyi ős DENORMALIZÁLVA a sorban.")
    print("     A katalóguslap egyetlen sorból felépíthető, és az")
    print("     inbreeding halmazmetszet lesz, nem fasétta.\n")

    print("--- 3) MI TORTENIK EGY FUTAM UTAN ---")
    horse = {'horse_id': 'h-042', 'name': 'Ashridge', 'sire_id': 's-011',
             'dam_id': 'd-007', 'family_id': 'f-003', 'breeder_id': 'p-100'}
    race = {'race_id': 'r-9001', 'black_type': True, 'classic': None,
            'purse': 45000}
    result = {'position': 1, 'earnings': 27000, 'injury': None}

    ops = propagate_result(result, horse, race)
    print(f"  {horse['name']} megnyert egy black type futamot (27 000 B$):\n")
    for i, op in enumerate(ops, 1):
        print(f"  {i}. {op['table']:14s} [{op['key']:8s}]  {op['change']}")
    print(f"\n  -> {len(ops)} sor érintve. Ez FÜGGETLEN attól, mekkora a világ.\n")

    print("--- 4) UJ CSIKO SZULETESE ---")
    sire = {'horse_id': 's-011', 'name': 'Thornmere',
            'ancestors': ['a1','a2','a3','a4','a5','a6']}
    dam = {'horse_id': 'd-007', 'name': 'Winvale', 'family_id': 'f-003',
           'ancestors': ['b1','b2','a3','b4','b5','b6']}
    foal = insert_foal(sire, dam, breeder_id='p-100', season=8)
    for i, op in enumerate(foal['ops'], 1):
        key = f" [{op.get('key','')}]" if op.get('key') else ''
        print(f"  {i}. {op['op']:6s} {op['table']:14s}{key}  {op['detail']}")
    print(f"\n  Ős-tömb (14 hely): {foal['ancestors'][:8]} ...\n")

    print("--- 5) INBREEDING: HALMAZMETSZET ---")
    ib = inbreeding_from_ancestors(sire, dam)
    print(f"  Közös ős: {ib['shared']}  ->  koefficiens {ib['coefficient']*100:.2f}%")
    print("  Rekurzív faséta nélkül, konstans időben.\n")

    print("--- 6) OLVASASI UTAK ---")
    for r in READ_PATHS:
        print(f"  {r['query']}")
        print(f"     {' + '.join(r['tables'])}")
        print(f"     -> {r['cost']}")
    print()

    print("--- 7) MIERT KELL A HARMADIK RETEG ---")
    print("  Aggregátum NÉLKÜL egy katalóguslap:")
    print("     1. pedigré: keresd ki a kanca összes utódját")
    print("     2. verseny: kérdezd le MINDEGYIK eredményeit")
    print("     3. számold össze a black type-okat")
    print("     4. ismételd meg a nagyanyára, dédanyára...")
    print("     -> több tucat lekérdezés EGYETLEN katalóguslapért\n")
    print("  Aggregátummal: 3 indexelt olvasás.\n")
    print("  A költség áttolódik az ÍRÁSRA — ami ritkább és kiszámítható:")
    print("     20 000 játékosnál ~2 959 futam/nap = kb. 34 másodpercenként egy")
    print("     futam, futamonként ~8 sor frissítés. Elhanyagolható terhelés.")
