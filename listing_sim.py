"""
Trot Heritage - Listing & Handover Engine v1.0
=======================================================================
Az ELADASI HIRDETES (katalogus-lap) es az ATADAS-ATVETEL rendszere.

A jatek barmelyik eletszakaszban engedi az eladast (yearling-arveres,
NPC- vagy jatekos-eladas), ezert a lo egy "atadasi dossziet" visz
magaval. A dosszie HAROM RETEGU - a valos teliver-arveresek
Repository-rendszere alapjan.

=======================================================================
FORRASOK - A HAROM RETEGU INFORMACIOS RENDSZER
=======================================================================

1. Keeneland Repository: az eladok ide helyezik a rontgeneket (36 felvetel
   mind a negy lab fobb izuleteirol, max 6 hettel a vasar elott keszitve,
   4 nappal a vasar elott be kell kerulnie), endoszkopos videokat,
   muteti jelenteseket. Kiváltó ok: ne kelljen minden erdeklodonek kulon
   vizsgalatot fizetnie ugyanazon a lovon.
   https://www.keeneland.com/sales/repository
   https://www.bloodhorse.com/horse-racing/articles/224066/repository-a-sales-staple

2. Az informaciokeres MAGA IS informacio: az elado megtekintheti azok
   listajat, akik megneztek az anyagait, a vevo nevevel egyutt.
   -> A jatekban: az elado lathatja, hany jatekos nezte meg a dossziet.
   https://www.bloodhorse.com/horse-racing/articles/224066/repository-a-sales-staple

3. Az informacio NEM garancia: a rontgenek ertelmezese bonyolult,
   jelentos tapasztalatot igenyel, es "altalaban nem olyan egyszeru,
   mint megfelelt vagy sem". -> A jatekban a vevo KOVETKEZTET, nem
   tudja meg. (Spec 21. pont: "a jatekos mint genetikai detektiv")
   https://thehorse.com/features/buying-a-racehorse-at-auction/

4. Aszimmetrikus informacio kozgazdasagtana: az allatorvosi informacio
   kozzetetele az informacios aszimmetria csokkentesere szolgal. Egy
   vizsgalat szerint a kozzetett egeszsegugyi informacio az ALACSONYABB
   aron kelo lovaknal befolyasolta az arat, a dragabbaknal kevesbe.
   -> A jatekban az allatorvosi felmeres a KOZEPES/OLCSO lovaknal
   valtoztat legtobbet az aron.
   https://www.sciencedirect.com/science/article/abs/pii/S0169515020300288

=======================================================================
FORRASOK - A BLACK TYPE KATALOGUS-HAGYOMANY (a "ne legyen szaraz" resz)
=======================================================================

5. A black type rendszer: vastag betus nev CSUPA NAGYBETUVEL =
   stakes-gyoztes; vegyes kis-/nagybetuvel = stakes-helyezett (2. vagy
   3. hely); normal betuvel = egyik sem. Fasig-Tipton 1952 ota,
   Keeneland 1960 ota hasznalja; az ICSC (1981) es SITA (1983)
   nemzetkozileg szabvanyositotta.
   https://washingtonthoroughbred.com/thoroughbred-terminology/
   https://www.bloodhorse.com/horse-racing/articles/213868/part-1-evolution-of-black-type

6. Miert jo ez jatekban: "kiugrik a lapról" - vizualis jelzes, nem
   tablazat. Es ritka: Eszak-Amerikaban az osszes futam kb. 3%-a
   graded stakes.
   https://www.aqha.com/-/what-is-black-type-
   https://www.gaylevanleer.com/ownership/catalog.htm

7. A katalogus-lap szerkezete: apa-bekezdes, 1. anya, 2. anya - minden
   behuzas egy generaciot jelent. A LEGFONTOSABB az 1. es 2. anya; a
   3-4. anya mar erosen "hig".
   https://boomerbloodstock.com.au/learning/buying-selling/how-to-read-a-catalogue-page/

8. A "detektiv-olvasat" beepitett: egy "9 csiko, 3 futott, 2 gyoztes"
   bejegyzes PIROS ZASZLO - vagy tehetsegtelenseget, vagy egeszsegi
   problemat (unsoundness) jelez.
   https://www.gaylevanleer.com/ownership/catalog.htm

9. VEVOTIPUS-KULONBSEG (dokumentalt): aki mas celra keres lovat, a
   black type KERULESEVEL talalhat jo vetelt - azaz a tenyesztesi es a
   futtatasi cel MAS ertekelest kivan.
   https://therrp.org/education/buying-selling/navigating-thoroughbred-sales/
"""

import random
from enum import Enum

random.seed(42)


# =======================================================================
# 1) BLACK TYPE - a katalogus-lap vizualis nyelve (forras 5., 6.)
# =======================================================================
class BlackType(Enum):
    """A valos katalogus-konvencio harom szintje."""
    STAKES_WINNER = 'stakes_winner'      # VASTAG NAGYBETU
    STAKES_PLACED = 'stakes_placed'      # Vastag vegyes betu
    PLAIN = 'plain'                      # normal betu


def render_black_type(name, black_type):
    """A nev megjelenitese a katalogus-konvencio szerint.
    A UI-ban ez vastagitassal jelenik meg; itt szoveges jelolessel
    demonstraljuk."""
    if black_type == BlackType.STAKES_WINNER:
        return name.upper()          # UI: vastag + nagybetu
    if black_type == BlackType.STAKES_PLACED:
        return name.title()          # UI: vastag, vegyes betu
    return name.lower().title()      # UI: normal


BLACK_TYPE_HINT = {
    BlackType.STAKES_WINNER: 'stakes-győztes',
    BlackType.STAKES_PLACED: 'stakes-helyezett',
    BlackType.PLAIN: '',
}


# =======================================================================
# 2) ELETSZAKASZOK ES A HOZZAJUK TARTOZO HIRDETES-TIPUS
# =======================================================================
class LifeStage(Enum):
    YEARLING = 'yearling'            # 1-2 ev, meg nem futott
    UNRACED_TWO = 'unraced_two'      # 2 ev, meg nem futott ("nyers ketéves")
    RACEHORSE = 'racehorse'          # aktiv versenylo
    BREEDING_STOCK = 'breeding'      # tenyeszallat (men vagy anyakanca)


STAGE_LABELS_HU = {
    LifeStage.YEARLING: 'Yearling',
    LifeStage.UNRACED_TWO: 'Nyers kétéves',
    LifeStage.RACEHORSE: 'Versenyló',
    LifeStage.BREEDING_STOCK: 'Tenyészállat',
}


# =======================================================================
# 2b) SZIN - a breeding_sim.py szingenetikai kimenetenek megjelenitese
# =======================================================================
# A valos teliver-katalogusokban a szin a lo azonosito soraban all
# (pl. "Bay Colt"). A Jockey Club het hivatalos szinkategoriat ismer el;
# a mi motorunk ezek kozul a genetikailag modellezetteket hasznalja.
COLOR_LABELS_HU = {
    'Bay': 'Pej',
    'Chestnut': 'Sárga',
    'Black': 'Fekete',
    'Gray': 'Szürke',
    'Palomino': 'Palomino',
}

# A ritkasagi fokozat a monetizacios reteg szamara keszult
# (breeding_sim.py COLOR_RARITY_TIER) - a hirdetesben csak a ritka es
# kulonleges szinek kapnak kiemelest, a gyakoriak nem.
RARITY_LABELS_HU = {
    'common': '',
    'uncommon': 'ritkább szín',
    'rare': 'ritka szín',
    'special': 'különleges szín',
}


# =======================================================================
# 3) EGYSEGES A-E SKALA - MINDEN ertekelesre ugyanaz
# =======================================================================
# EGYSEGESSEGI ELV: a jatekos MINDENHOL ugyanazt a 9 fokozatu skalat
# latja (A+ ... E) - a lo tenyesztesi indexenel, a trénernel, a
# zsokénal, a felneveles minosegenel es az allatorvosi felmeresnel is.
# Ez ugyanaz a fuggveny, mint a breeding_sim.py / trainer_sim.py /
# jockey_sim.py index_from_score()-a - szandekosan duplikalva, hogy a
# modul onalloan is futtathato legyen, de a hatarok BETUre azonosak.
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


# =======================================================================
# 4) FELNEVELES MINOSEGE - a lezart szakaszokbol, A-E skalan
# =======================================================================
# A feeding_sim.py szakasz-lezaras rendszerebol jon: a csikokor (max 9%)
# es a yearlingkor (max 6%) lezart erteke. A vevo NEM a nyers %-ot latja,
# hanem A-E minositest - ugyanazon a skalan, mint minden mas.
REARING_NOTES = {
    'A+': 'Kifogástalan takarmányozás végig.',
    'A':  'Kiemelkedő gondoskodás.',
    'A-': 'Következetesen jó nevelés.',
    'B+': 'Gondos nevelés, apró hiányokkal.',
    'B':  'Rendben tartott, átlag feletti.',
    'B-': 'Elfogadható, de nem kihasznált időszak.',
    'C':  'Átlagos nevelés, több kihagyott lehetőség.',
    'D':  'Hiányos ellátás a növekedés alatt.',
    'E':  'Elhanyagolt — a mulasztás már nem pótolható.',
}


def grade_rearing_quality(foal_stage_pct, yearling_stage_pct, stage):
    """A felneveles minosege A-E fokozatban (nyers % nelkul).

    A yearling meg nem zarta le a masodik szakaszt, ezert nala csak a
    csikokori resz szamit (max 9%), a kesobbi eletszakaszoknal a teljes
    lezart sav (max 15%)."""
    if stage == LifeStage.YEARLING:
        ratio = foal_stage_pct / 9.0
    else:
        ratio = (foal_stage_pct + yearling_stage_pct) / 15.0

    ratio = max(0.0, min(1.0, ratio))
    grade = index_from_score(ratio * 99)
    return {'grade': grade, 'note': REARING_NOTES[grade]}


# =======================================================================
# 5) ALLATORVOSI ALLAPOTFELMERES - az ELADO fizeti (forras 1., 4.)
# =======================================================================
# A valos Repository-logika: az elado sajat koltsegen keszittet
# vizsgalatot, es o donti el, hogy kozze teszi-e. Ha nem teszi kozze,
# az onmagaban is jelzes a vevo fele.
#
# Az eredmeny UGYANAZON az A-E skalan jelenik meg, mint minden mas.
VET_INSPECTION_COST = 1200   # jatekbeli valuta - jatektervezesi placeholder

VET_NOTES = {
    'A+': 'Az állatorvos nem talált semmilyen elváltozást.',
    'A':  'Kifogástalan felvételek, tiszta ízületek.',
    'A-': 'Lényegében tiszta, egy-két jelentéktelen jel.',
    'B+': 'Apró, versenykarriert nem befolyásoló jelek.',
    'B':  'Néhány enyhe elváltozás, kezelést nem igényel.',
    'B-': 'Több enyhe jel; rendszeres ellenőrzés javasolt.',
    'C':  'Elváltozások, amelyek körültekintő terhelést kívánnak.',
    'D':  'Ízületi jelek, amelyek terhelés mellett gondot okozhatnak.',
    'E':  'Több elváltozás; komoly kockázat versenykarrier esetén.',
}


def run_vet_inspection(soundness_value):
    """Allatorvosi felmeres a lo soundness ertekebol, A-E fokozatban.

    A jelentes NEM pontos szamot ad (forras 3.: "nem olyan egyszeru,
    mint megfelelt vagy sem"), es tartalmaz egy kis bizonytalansagot -
    ahogy a valos rontgen-ertelmezes sem binaris. Ezert a kapott
    fokozat kis mertekben elterhet a lo valodi soundness ertekétől."""
    noisy = soundness_value + random.gauss(0, 4)
    noisy = max(0, min(99, noisy))
    grade = index_from_score(noisy)
    return {'grade': grade, 'note': VET_NOTES[grade], 'cost': VET_INSPECTION_COST}


# =======================================================================
# 6) A HIRDETES OSSZEALLITASA - eletszakasz szerint bovulo retegekkel
# =======================================================================
def build_listing(horse, stage, vet_report=None, viewer_count=0):
    """Osszeallitja a lo eladasi hirdeteset (katalogus-lapjat).

    horse: dict a kovetkezo mezokkel:
        name, sire, dam, sire_black_type, dam_black_type,
        breeding_index, foal_stage_pct, yearling_stage_pct,
        previous_owner, soundness,
        (versenylonal:) race_record, current_trainer, current_jockey
        (tenyeszallatnal:) progeny

    A HAROM RETEG:
      A) MINDIG LATHATO
      B) AZ ELADO DONT ROLA (allatorvosi felmeres)
      C) SOSEM LATHATO (nyers toltottsegi %, valodi genetikai ertek)
    """
    listing = {
        'stage': stage,
        'stage_label': STAGE_LABELS_HU[stage],
        'name': horse['name'],
    }

    # --- A) MINDIG LATHATO RETEG ---
    listing['pedigree'] = {
        'sire': render_black_type(horse['sire'], horse['sire_black_type']),
        'sire_hint': BLACK_TYPE_HINT[horse['sire_black_type']],
        'dam': render_black_type(horse['dam'], horse['dam_black_type']),
        'dam_hint': BLACK_TYPE_HINT[horse['dam_black_type']],
    }
    listing['breeding_index'] = horse['breeding_index']
    listing['rearing'] = grade_rearing_quality(
        horse['foal_stage_pct'], horse.get('yearling_stage_pct', 0.0), stage
    )
    listing['previous_owner'] = horse['previous_owner']

    # --- SZIN: a valos katalogus-lapokon a lo azonosito soraban all ---
    # A breeding_sim.py color_phenotype() kimenete. A szurke lo SZINESEN
    # SZULETIK es fokozatosan oszul (Thiruvenkadan et al. 2008 / McCoy) -
    # ezert a yearlingnel meg latszhat az eredeti szin, es a hirdetes
    # jelzi, hogy a vegleges megjelenes mas lesz.
    color = horse['color']
    listing['color'] = {
        'displayed': color['displayed_color'],
        'displayed_hu': COLOR_LABELS_HU.get(color['displayed_color'], color['displayed_color']),
        'rarity': color['rarity_tier'],
        'rarity_hu': RARITY_LABELS_HU.get(color['rarity_tier'], color['rarity_tier']),
        'will_gray': color['will_gray_with_age'],
        'born_color': color['born_color'],
        'born_color_hu': COLOR_LABELS_HU.get(color['born_color'], color['born_color']),
    }

    # --- B) AZ ELADO DONTESE: allatorvosi felmeres ---
    if vet_report:
        listing['vet_report'] = vet_report
    else:
        # forras 2. logikaja: a hianyzo informacio maga is jelzes
        listing['vet_report'] = None
        listing['vet_note'] = 'Az eladó nem csatolt állatorvosi felmérést.'

    # --- ELETSZAKASZ-FUGGO BOVULES ---
    if stage == LifeStage.RACEHORSE:
        listing['race_record'] = horse.get('race_record', {})
        listing['current_trainer'] = horse.get('current_trainer')
        listing['current_jockey'] = horse.get('current_jockey')
        listing['race_db_link'] = f"/races?horse={horse['name']}"

    if stage == LifeStage.BREEDING_STOCK:
        listing['progeny'] = horse.get('progeny', [])
        listing['race_db_link'] = f"/races?progeny_of={horse['name']}"

    # --- forras 2.: az erdeklodes maga is adat, az ELADO latja ---
    listing['viewer_count_for_seller'] = viewer_count

    return listing


# =======================================================================
# 7) VEVOTIPUS-FUGGO ERTEKELES (forras 9.)
# =======================================================================
# Aki TENYESZTENI akar, mast ertekel, mint aki FUTTATNI. Ez dokumentalt
# valos jelenseg - a forras szerint mas celra keresve a black type
# kerulesevel lehet jo vetelt talalni.
#
# A sulyok JATEKTERVEZESI PLACEHOLDEREK (nincs publikalt numerikus
# adat arra, hogy egy tenyeszto pontosan hany szazalekban sulyoz egy
# pedigret) - de az IRANY dokumentalt.
BUYER_WEIGHTS = {
    'breeder': {
        'pedigree': 1.4,        # a vervonal a legfontosabb
        'breeding_index': 1.3,
        'race_record': 0.6,     # szamit, de nem donto
        'rearing': 0.7,
        'soundness': 1.1,       # reprodukcios szempontbol fontos
        'progeny': 1.5,         # ha mar van utod, az a legerosebb bizonyitek
    },
    'racer': {
        'pedigree': 0.8,
        'breeding_index': 0.9,
        'race_record': 1.5,     # a tenyleges forma a donto
        'rearing': 1.2,         # a felneveles minosege eroteljesen szamit
        'soundness': 1.4,       # egy serulekeny lo nem tud futni
        'progeny': 0.3,         # szinte lenyegtelen
    },
}


def describe_buyer_focus(buyer_type):
    """Mit nez elsosorban az adott vevotipus - a jatekos szamara
    megjelenitheto sugo szoveg."""
    if buyer_type == 'breeder':
        return ('Tenyésztőként a vérvonal, a tenyészérték és a már meglévő '
                'utódok eredményei számítanak leginkább.')
    return ('Futtatóként a versenyforma, a felnevelés minősége és az '
            'egészségi állapot a döntő.')


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
def _print_listing(listing):
    """Katalogus-lap stilusu megjelenites - a valos hagyomany szerint."""
    c = listing['color']
    rarity = f"  ({c['rarity_hu']})" if c['rarity_hu'] else ""
    print(f"  ┌─ {listing['name']}  ({listing['stage_label']})")
    if c['will_gray']:
        print(f"  │  Szín: {c['displayed_hu']}{rarity} — {c['born_color_hu']}ként született, őszül")
    else:
        print(f"  │  Szín: {c['displayed_hu']}{rarity}")
    ped = listing['pedigree']
    sire_line = ped['sire'] + (f"  [{ped['sire_hint']}]" if ped['sire_hint'] else "")
    dam_line = ped['dam'] + (f"  [{ped['dam_hint']}]" if ped['dam_hint'] else "")
    print(f"  │  apja:  {sire_line}")
    print(f"  │  anyja: {dam_line}")
    print(f"  │  Tenyésztési index: {listing['breeding_index']}")
    r = listing['rearing']
    print(f"  │  Felnevelés: {r['grade']:3s} — {r['note']}")
    print(f"  │  Előző tulajdonos: {listing['previous_owner']}")

    if listing.get('vet_report'):
        vr = listing['vet_report']
        print(f"  │  Állatorvosi felmérés: {vr['grade']:3s} — {vr['note']}")
    else:
        print(f"  │  Állatorvosi felmérés: — {listing['vet_note']}")

    if listing.get('race_record'):
        rr = listing['race_record']
        print(f"  │  Versenyforma: {rr['starts']} start, {rr['wins']} győzelem, "
              f"{rr['places']} helyezés")
        print(f"  │     → részletek a versenyadatbázisban: {listing['race_db_link']}")
    if listing.get('current_trainer'):
        print(f"  │  Jelenlegi tréner: {listing['current_trainer']}")
    if listing.get('current_jockey'):
        print(f"  │  Jelenlegi zsoké: {listing['current_jockey']}")

    if listing.get('progeny'):
        print(f"  │  Utódok:")
        for p in listing['progeny']:
            rendered = render_black_type(p['name'], p['black_type'])
            hint = BLACK_TYPE_HINT[p['black_type']]
            suffix = f"  [{hint}]" if hint else ""
            print(f"  │     {rendered}{suffix} — {p['summary']}")
        print(f"  │     → részletek a versenyadatbázisban: {listing['race_db_link']}")

    print(f"  └─ (eladónak látható: {listing['viewer_count_for_seller']} érdeklődő nézte meg)")
    print()


if __name__ == '__main__':
    print("=== TROT HERITAGE - LISTING & HANDOVER ENGINE v1.0 ===\n")

    print("--- 1) BLACK TYPE KONVENCIO (forras: Keeneland/Fasig-Tipton, ICSC 1981) ---")
    for bt in BlackType:
        print(f"  {bt.value:15s} -> {render_black_type('storm runner', bt):18s} "
              f"{('(' + BLACK_TYPE_HINT[bt] + ')') if BLACK_TYPE_HINT[bt] else '(nincs black type)'}")
    print()

    print("--- 2) YEARLING HIRDETES (allatorvosi felmeres NELKUL) ---")
    yearling = {
        'name': 'Sirdam142', 'sire': 'northwind cavalier', 'dam': 'velvet solstice',
        'sire_black_type': BlackType.STAKES_WINNER, 'dam_black_type': BlackType.STAKES_PLACED,
        'breeding_index': 'B+', 'foal_stage_pct': 8.1, 'yearling_stage_pct': 0.0,
        'previous_owner': 'Hollow Creek Farm', 'soundness': 74,
        'color': {'displayed_color': 'Bay', 'born_color': 'Bay',
                  'will_gray_with_age': False, 'rarity_tier': 'common'},
    }
    _print_listing(build_listing(yearling, LifeStage.YEARLING, viewer_count=17))

    print("--- 3) UGYANAZ A YEARLING, allatorvosi felmeressel (az ELADO fizette) ---")
    report = run_vet_inspection(yearling['soundness'])
    print(f"  (a felmeres koltsege az eladonak: {report['cost']} B$)")
    _print_listing(build_listing(yearling, LifeStage.YEARLING, vet_report=report, viewer_count=17))

    print("--- 4) NYERS KETEVES (a yearling szakasz is lezarult) ---")
    two_yo = dict(yearling)
    two_yo.update({'name': 'Quietfire', 'yearling_stage_pct': 5.4,
                   'previous_owner': 'Ashgrove Stud',
                   'color': {'displayed_color': 'Gray', 'born_color': 'Bay',
                             'will_gray_with_age': True, 'rarity_tier': 'rare'}})
    _print_listing(build_listing(two_yo, LifeStage.UNRACED_TWO,
                                 vet_report=run_vet_inspection(two_yo['soundness']),
                                 viewer_count=31))

    print("--- 5) VERSENYLO (kiegeszul versenyeredmennyel, trénerrel, zsokéval) ---")
    racer = dict(two_yo)
    racer.update({
        'name': 'Duskmeridian', 'breeding_index': 'A-',
        'race_record': {'starts': 11, 'wins': 3, 'places': 4},
        'current_trainer': 'B+ · Mérföld specialista',
        'current_jockey': 'A- · Középtáv / gyep',
        'previous_owner': 'Northgate Racing',
        'color': {'displayed_color': 'Chestnut', 'born_color': 'Chestnut',
                  'will_gray_with_age': False, 'rarity_tier': 'common'},
    })
    _print_listing(build_listing(racer, LifeStage.RACEHORSE,
                                 vet_report=run_vet_inspection(racer['soundness']),
                                 viewer_count=54))

    print("--- 6) TENYESZALLAT (kiegeszul az utodokkal es azok eredmenyevel) ---")
    breeding = dict(racer)
    breeding.update({
        'name': 'Velvet Solstice', 'breeding_index': 'A',
        'previous_owner': 'Northgate Racing',
        'color': {'displayed_color': 'Palomino', 'born_color': 'Palomino',
                  'will_gray_with_age': False, 'rarity_tier': 'special'},
        'progeny': [
            {'name': 'duskmeridian', 'black_type': BlackType.STAKES_WINNER,
             'summary': '11 start, 3 győzelem'},
            {'name': 'quietfire', 'black_type': BlackType.STAKES_PLACED,
             'summary': '8 start, 1 győzelem, 3 helyezés'},
            {'name': 'sirdam142', 'black_type': BlackType.PLAIN,
             'summary': 'még nem futott'},
        ],
    })
    _print_listing(build_listing(breeding, LifeStage.BREEDING_STOCK,
                                 vet_report=run_vet_inspection(breeding['soundness']),
                                 viewer_count=88))

    print("--- 7) VEVOTIPUS-FUGGO ERTEKELES (forras: RRP - mas celra mas ertek) ---")
    for buyer in ['breeder', 'racer']:
        print(f"  {buyer.upper()}: {describe_buyer_focus(buyer)}")
        w = BUYER_WEIGHTS[buyer]
        top = sorted(w.items(), key=lambda kv: -kv[1])[:3]
        print(f"    Legmagasabb sulyu tenyezok: " +
              ", ".join(f"{k} ({v})" for k, v in top))
        print()

    print("--- 8) VALIDACIO: a harom reteg elkulonitese ---")
    test_listing = build_listing(racer, LifeStage.RACEHORSE,
                                 vet_report=run_vet_inspection(racer['soundness']))
    forbidden_keys = ['fill_bar_pct', 'true_genetic_value', 'genetic_potential_score',
                      'trainer_overall_score', 'raw_soundness']
    leaked = [k for k in forbidden_keys if k in test_listing]
    print(f"  Nyers belso ertek NEM szivarog a hirdetesbe: "
          f"{'OK' if not leaked else 'HIBA - kiszivargott: ' + str(leaked)}")

    stage_keys = {
        LifeStage.YEARLING: (['race_record', 'progeny'], []),
        LifeStage.RACEHORSE: ([], ['race_record']),
        LifeStage.BREEDING_STOCK: ([], ['progeny']),
    }
    stage_ok = True
    for stage, (must_absent, must_present) in stage_keys.items():
        lst = build_listing(breeding if stage == LifeStage.BREEDING_STOCK else racer, stage)
        for k in must_absent:
            if k in lst:
                stage_ok = False
        for k in must_present:
            if k not in lst:
                stage_ok = False
    print(f"  Eletszakasz-fuggo retegek helyesen jelennek meg: {'OK' if stage_ok else 'HIBA'}")
    print()

    final = "MINDEN VALIDACIO OK" if (not leaked and stage_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== OSSZESITETT STATUS: {final} ===")
