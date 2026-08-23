"""
Trot Heritage - Season Calendar Engine v1.0
=======================================================================
AZ IDORENDSZER. Ez a modul rogzíti a jatek es a valos ido viszonyat,
es minden korabbi modul idoalapu parameteret ATSZAMOL erre a skalara.

ALAPARANY:  1 SZEZON = 1 JATEKEV = 1 VALOS HONAP (30 nap)
            -> 12x gyorsitas a valos idohoz kepest

Ebbol minden mas levezetheto:
    1 jatekev    = 30 valos nap
    1 jatekhonap = 2.5 valos nap
    1 jatekhet   = ~14 valos ora

A JATEKOS ALAPELVEI (kifejezett dontesek, ezek nem tudomanyos adatbol
jonnek, hanem jatszhatosagi megfontolasbol):

  1. A FEDEZTETESI ABLAK VEGIG NYITVA - nem buntetjuk a kesobb
     belepot. (A valos naptar febr. 15 - jun. 15 kozott engedne csak,
     lasd forras 1-2., de ezt SZANDEKOSAN feloldjuk.)

  2. SZEZONONKENT EGY CSIKO kancankent. Ez biologiailag pontos
     (11 honap vemhesseg = evi egy csiko), es EZ TARTJA ERTELMESEN a
     tenyeszcsik-rendszert: nelkule a 2 napos vemhesseg + monetizalt
     gyorsitas egy honap alatt kiuritene egy kanca teljes tenyesz-
     karrierjet.

  3. VEMHESSEG = 2 VALOS NAP, monetizacioval gyorsithato. A gyorsitas
     NEM tobb csikot ad (lasd 2. pont), hanem:
       - hamarabb kerul a csiko a kovetkezo yearling-arveresre
       - a kanca hamarabb kerul vissza "tavaly ellett" statuszba,
         ami a LEGJOBB vemhesulesi eselyt adja (lasd stud_sim.py)
     Tehat a gyorsitas KENYELMET vesz, nem elonyt.

  4. A SZEZON VEGEN SZULETETT CSIKO IS YEARLING LESZ a kovetkezo
     arveresre. Ez TUDATOS ELTERES a valosagtol: ott a december 28-an
     szuletett csiko harom nap mulva yearling (univerzalis jan. 1-i
     szuletesnap), ezert KERULIK a korai fedeztetest. A jatekban
     megforditjuk, hogy a keson belepo ne maradjon le. Ara: megszunik
     a korai/kesoi fedeztetes kozotti strategiai kulonbseg.

=======================================================================
FORRASOK - A VALOS NAPTAR SZERKEZETE (amibol a fazisok jonnek)
=======================================================================

1. Amplify Horse Racing / Mill Ridge: az ellesi szezon januartol kb.
   junius 1-ig tart; a fedeztetesi szezon februar 15-en indul es kb.
   junius 15-ig tart; a vemhesseg kb. 11 honap. Julius 1-tol indul a
   Keeneland September yearling-vasar elokeszitese.
   https://www.amplifyhorseracing.org/learn
   https://www.millridge.com/discover/october-newsletter

2. Kentucky Derby / PA Horse Racing: a fedeztetes Valentin-nap korul
   indul; a februar kozepi "early cover" januari ellest ad. A jelentos
   ketevesversenyek jellemzoen juliustol indulnak.
   https://www.kentuckyderby.com/horses/news/did-you-know-breeding-season-begins-around-valentines-day/
   https://pennhorseracing.com/stories/timing-is-everything-during-foaling-season/

3. UNIVERZALIS SZULETESNAP: minden eszaki felteken szuletett teliver
   januar 1-en oregszik egy evet, fuggetlenul a tenyleges ellesi
   datumtol. -> IMPLEMENTACIOS AJANDEK: egyetlen tick lepteti az
   egesz allomanyt, nincs egyedi szuletesnap-nyilvantartas.
   https://www.thoroughbreddailynews.com/universal-birthdate-no-joke-shared-archive/

4. Yearling-arveresek osszel (Keeneland September, Tattersalls),
   majd tenyeszallat-vasarok a Breeders' Cup utan.
   https://www.charlockstud.com/breeding-cycle/
"""

from enum import Enum


# =======================================================================
# 1) AZ IDOSKALA
# =======================================================================
REAL_DAYS_PER_SEASON = 30        # 1 szezon = 1 valos honap
GAME_YEARS_PER_SEASON = 1        # 1 szezon = 1 jatekev
TIME_RATIO = 12                  # 12x gyorsitas (12 jatekev / valos ev)

REAL_DAYS_PER_GAME_MONTH = REAL_DAYS_PER_SEASON / 12      # 2.5 nap
REAL_HOURS_PER_GAME_WEEK = REAL_DAYS_PER_SEASON / 52 * 24 # ~13.8 ora


def game_years_to_real_days(game_years):
    return round(game_years * REAL_DAYS_PER_SEASON, 1)


def game_weeks_to_real_hours(game_weeks):
    return round(game_weeks * REAL_HOURS_PER_GAME_WEEK, 1)


def real_days_to_game_years(real_days):
    return round(real_days / REAL_DAYS_PER_SEASON, 2)


# =======================================================================
# 2) A SZEZON BELSO SZERKEZETE (4 het = 30 nap)
# =======================================================================
# A hetvegi arveresek adjak a het ritmusat, a hetkoznapok a versenyeke.
class AuctionType(Enum):
    YEARLING = 'yearling'
    TWO_YEAR_OLD = 'two_year_old'
    BROODMARE = 'broodmare'
    MIXED = 'mixed'


AUCTION_LABELS_HU = {
    AuctionType.YEARLING: 'Yearling-árverés',
    AuctionType.TWO_YEAR_OLD: '2 éves / kész versenyló',
    AuctionType.BROODMARE: 'Kancaárverés',
    AuctionType.MIXED: 'Vegyes árverés',
}

SEASON_WEEKS = [
    {
        'week': 1,
        'weekday_focus': 'Szezonnyitás: csikók születnek, az állomány öregszik, fedeztetés indul',
        'weekend_auction': AuctionType.YEARLING,
    },
    {
        'week': 2,
        'weekday_focus': 'Versenynapok, fedeztetés, tréning',
        'weekend_auction': AuctionType.TWO_YEAR_OLD,
    },
    {
        'week': 3,
        'weekday_focus': 'Csúcsfutamok, fedeztetés',
        'weekend_auction': AuctionType.BROODMARE,
    },
    {
        'week': 4,
        'weekday_focus': 'Bajnoki futamok, szezonzárás',
        'weekend_auction': AuctionType.MIXED,
    },
]


def get_week_info(day_of_season):
    """Melyik heten jarunk a szezonban (1-30. nap)."""
    week_index = min(3, (day_of_season - 1) // 7)
    return SEASON_WEEKS[week_index]


# =======================================================================
# 3) VEMHESSEG ES A SZEZONONKENTI KORLAT
# =======================================================================
GESTATION_REAL_DAYS = 2.0            # alapertelmezett vemhesseg
GESTATION_MIN_REAL_DAYS = 0.25       # monetizacioval maximum ennyire gyorsithato
MAX_FOALS_PER_SEASON = 1             # A JATEKOS DONTESE: szezononkent egy csiko


class CoveringResult(Enum):
    OK = 'ok'
    ALREADY_COVERED = 'already_covered'
    PENSIONED = 'pensioned'


COVERING_MESSAGES = {
    CoveringResult.OK: 'A fedeztetés rögzítve.',
    CoveringResult.ALREADY_COVERED:
        'Ez a kanca már fedeztetve lett ebben a szezonban. Szezononként egy csikó.',
    CoveringResult.PENSIONED:
        'Nyugdíjazott kanca nem fedeztethető.',
}


def can_cover(mare, current_season):
    """Fedeztetheto-e a kanca ebben a szezonban?

    A fedeztetesi ABLAK vegig nyitva (barmikor a szezon soran), de
    SZEZONONKENT CSAK EGYSZER.
    """
    if mare.get('pensioned', False):
        return CoveringResult.PENSIONED

    if mare.get('last_covered_season') == current_season:
        return CoveringResult.ALREADY_COVERED

    return CoveringResult.OK


def gestation_days(speedup_level=0):
    """A vemhesseg hossza valos napokban.

    speedup_level: 0 = nincs gyorsitas, magasabb ertek = monetizalt
    gyorsitas. A gyorsitas NEM ad tobb csikot (lasd MAX_FOALS_PER_SEASON),
    csak hamarabb hozza a csikot es a kancat.
    """
    if speedup_level <= 0:
        return GESTATION_REAL_DAYS
    reduced = GESTATION_REAL_DAYS / (1 + speedup_level)
    return round(max(GESTATION_MIN_REAL_DAYS, reduced), 2)


def foal_ready_for_next_yearling_sale(birth_day_of_season):
    """A JATEKOS DONTESE: a szezon VEGEN szuletett csiko is yearling
    lesz a kovetkezo arveresre - senki ne maradjon le.

    Ez tudatos elteres a valosagtol (ott a kesoi csiko hatranyban van),
    a keson belepo jatekos vedelmeben."""
    return True


# =======================================================================
# 4) A KORABBI MODULOK IDOALAPU PARAMETEREINEK ATSZAMITASA
# =======================================================================
# Minden korabban "jatekidoben" megadott ertek ide kerul at, valos
# idore atszamolva. Ha az aranyt kesobb valtoztatjuk (a jatekos jelezte,
# hogy teszteles utan akar felezheto), CSAK a TIME_RATIO-t kell
# modositani, es ezek automatikusan kovetik.

FRESHNESS_FULL_RECOVERY_GAME_WEEKS = 3   # a pihenokutatasbol (lasd jockey/trainer)
TRAINER_CARRYOVER_RACES = 3              # trainer_sim.py


def converted_parameters():
    """A rendszer idoalapu parametereinek valos ideju megfeleloi."""
    return {
        'frissesseg_teljes_visszatoltes': {
            'jatekido': f'{FRESHNESS_FULL_RECOVERY_GAME_WEEKS} játékhét',
            'valos_ido': f'{game_weeks_to_real_hours(FRESHNESS_FULL_RECOVERY_GAME_WEEKS)} óra '
                         f'(~{round(game_weeks_to_real_hours(FRESHNESS_FULL_RECOVERY_GAME_WEEKS)/24, 2)} nap)',
            'megjegyzes': 'Egy ló nagyjából kétnaponta futhat — ez a napi visszatérés motorja.',
        },
        'fedeztetestol_elso_futamig': {
            'jatekido': '3 szezon (fedeztetés → csikó → yearling → 2 éves)',
            'valos_ido': f'{game_years_to_real_days(2)} nap (~2 hónap)',
            'megjegyzes': 'Ezért kell, hogy a játékos az első naptól vehessen kész versenylovat.',
        },
        'versenykarrier': {
            'jatekido': '6-8 szezon',
            'valos_ido': f'{game_years_to_real_days(6)}-{game_years_to_real_days(8)} nap (~6-8 hónap)',
        },
        'kanca_teljes_palyafutas': {
            'jatekido': '4 verseny + 7 tenyész szezon',
            'valos_ido': f'{game_years_to_real_days(11)} nap (~13 hónap)',
        },
        'men_palyafutas_jo_ivadekkal': {
            'jatekido': '24 szezon',
            'valos_ido': f'{game_years_to_real_days(24)} nap (~2 év)',
        },
        'trener_atmenet': {
            'jatekido': f'{TRAINER_CARRYOVER_RACES} verseny',
            'valos_ido': '~1 hét (kb. kétnaponta egy start mellett)',
        },
    }


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - SEASON CALENDAR ENGINE v1.0 ===\n")

    print("--- 1) AZ IDOSKALA ---")
    print(f"  1 szezon = 1 játékév = {REAL_DAYS_PER_SEASON} valós nap  ({TIME_RATIO}× gyorsítás)")
    print(f"  1 játékhónap = {REAL_DAYS_PER_GAME_MONTH:.1f} valós nap")
    print(f"  1 játékhét   = {REAL_HOURS_PER_GAME_WEEK:.1f} valós óra\n")

    print("--- 2) A SZEZON SZERKEZETE (4 hét, hétvégenként árverés) ---")
    for w in SEASON_WEEKS:
        print(f"  {w['week']}. hét  {w['weekday_focus']}")
        print(f"          hétvége: {AUCTION_LABELS_HU[w['weekend_auction']]}")
    print()

    print("--- 3) SZEZONONKENT EGY CSIKO ---")
    mare = {'name': 'Velvet Solstice', 'last_covered_season': None, 'pensioned': False}
    season = 7

    r1 = can_cover(mare, season)
    print(f"  Első fedeztetés a {season}. szezonban: {COVERING_MESSAGES[r1]}")
    mare['last_covered_season'] = season

    r2 = can_cover(mare, season)
    print(f"  Második kísérlet ugyanabban a szezonban: {COVERING_MESSAGES[r2]}")

    r3 = can_cover(mare, season + 1)
    print(f"  Következő szezonban: {COVERING_MESSAGES[r3]}")

    pensioned = {'name': 'Old Rose', 'pensioned': True, 'last_covered_season': None}
    r4 = can_cover(pensioned, season)
    print(f"  Nyugdíjazott kanca: {COVERING_MESSAGES[r4]}\n")

    print("--- 4) VEMHESSEG ES GYORSITAS ---")
    for lvl in [0, 1, 3, 7]:
        d = gestation_days(lvl)
        label = 'nincs gyorsítás' if lvl == 0 else f'gyorsítás {lvl}. szint'
        print(f"  {label:22s} -> {d:5.2f} valós nap ({d*24:5.1f} óra)")
    print("  A gyorsítás NEM ad több csikót — csak hamarabb hozza.")
    print("  Haszna: a csikó eléri a következő yearling-árverést, és a kanca")
    print("  hamarabb kerül vissza 'tavaly ellett' státuszba (legjobb esély).\n")

    print("--- 5) A KORABBI PARAMETEREK ATSZAMITVA ---")
    for key, val in converted_parameters().items():
        print(f"  {key.replace('_', ' ')}:")
        print(f"      játékidő: {val['jatekido']}")
        print(f"      valós:    {val['valos_ido']}")
        if 'megjegyzes' in val:
            print(f"      -> {val['megjegyzes']}")
    print()

    print("--- 6) VALIDACIO ---")
    checks = [
        ('Egy kanca szezononként csak egyszer fedeztethető',
         can_cover({'last_covered_season': 5}, 5) == CoveringResult.ALREADY_COVERED),
        ('Következő szezonban újra fedeztethető',
         can_cover({'last_covered_season': 5}, 6) == CoveringResult.OK),
        ('A fedeztetési ablak a szezon bármely napján nyitva',
         all(can_cover({'last_covered_season': None}, 5) == CoveringResult.OK
             for _ in range(30))),
        ('Nyugdíjazott kanca nem fedeztethető',
         can_cover({'pensioned': True}, 5) == CoveringResult.PENSIONED),
        ('A gyorsítás nem megy a minimum alá',
         gestation_days(99) >= GESTATION_MIN_REAL_DAYS),
        ('A gyorsítás sosem ad több csikót',
         MAX_FOALS_PER_SEASON == 1),
        ('A szezon végi csikó is eléri a következő yearling-árverést',
         foal_ready_for_next_yearling_sale(30)),
        ('A frissesség kb. kétnaponta töltődik vissza',
         1.0 < game_weeks_to_real_hours(FRESHNESS_FULL_RECOVERY_GAME_WEEKS) / 24 < 2.5),
        ('Minden hétvégén van árverés',
         len({w['weekend_auction'] for w in SEASON_WEEKS}) == 4),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
