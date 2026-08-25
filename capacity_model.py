"""
Breeder Tycoon - Capacity Model v1.0
=======================================================================
KAPACITASTERVEZES: 20 000 aktiv jatekos, 8. szezon.

Hany futamot kell kiirni es hany aukciot inditani, hogy a kereslet es
a kinalat kiegyensulyozott legyen?

Ez NEM jatekmenet-modul, hanem UZEMELTETESI szamitas. A kimenete azt
mutatja meg, hol torik el a jelenlegi terv (6 palya, 4 aukcios haz,
max 12 session/nap).

BEMENETEK - a korabbi modulokbol:
  - Istallo-kapacitas 12 (farm_sim.py)
  - Kanca max 6 (stabling_sim.py)
  - Szezononkent egy csiko kancankent (season_sim.py)
  - ~7 start szezononkent lovankent (season.html, frissesseg-ciklus)
  - 8 lo egy futamban (race_sim.py)
  - 80-100 tetel egy aukcios sessionben (auction_sim.py)
  - Max 12 session/nap/haz (auction_sim.py)
  - 1 szezon = 30 nap (season_sim.py)
"""

import math

# =======================================================================
# 1) BEMENETI PARAMETEREK
# =======================================================================
ACTIVE_PLAYERS = 20000
SEASON = 8

SEASON_DAYS = 30
STABLE_CAPACITY = 12
MAX_MARES = 6
STARTS_PER_HORSE_PER_SEASON = 7
FIELD_SIZE = 8
LOTS_PER_SESSION = 90
MAX_SESSIONS_PER_DAY = 12
AUCTION_HOUSES = 4
CURRENT_TRACKS = 6

# A jatekosok NEM egyformak. A season.html meresei alapjan hasznalt
# strategia-mix - ez hatarozza meg, hany versenylovat es hany eladasra
# szant lovat tart egy atlagos jatekos.
STRATEGY_MIX = [
    # (arany, cimke, versenylo, kanca, fiatal, eladasra szant/szezon)
    (0.30, 'Kereskedő',        2.5, 4.0, 3.0, 2.6),
    (0.22, 'Kiegyensúlyozott', 5.0, 4.0, 2.5, 1.2),
    (0.18, 'Csak futtató',     6.5, 2.0, 1.5, 1.6),
    (0.15, 'Tiszta tenyésztő', 1.0, 6.0, 4.0, 3.2),
    (0.10, 'Kancabefektető',   3.0, 6.0, 3.0, 2.4),
    (0.05, 'Elit tenyésztő',   5.5, 5.0, 3.0, 1.0),
]

# Nem minden jatekos aktiv minden nap. A "aktiv jatekos" definicioja
# jellemzoen havi aktivitas - a napi aktiv arany ennek toredeke.
DAILY_ACTIVE_RATIO = 0.35        # DAU/MAU, tipikus mobil menedzserjatek


# =======================================================================
# 2) LOALLOMANY
# =======================================================================
def population():
    racers = mares = young = for_sale = 0.0
    for share, _, r, m, y, s in STRATEGY_MIX:
        racers += share * r
        mares += share * m
        young += share * y
        for_sale += share * s
    total = racers + mares + young

    return {
        'per_player': {'racers': racers, 'mares': mares, 'young': young,
                       'total': total, 'for_sale_per_season': for_sale},
        'world': {
            'racers': round(racers * ACTIVE_PLAYERS),
            'mares': round(mares * ACTIVE_PLAYERS),
            'young': round(young * ACTIVE_PLAYERS),
            'total': round(total * ACTIVE_PLAYERS),
            'for_sale_per_season': round(for_sale * ACTIVE_PLAYERS),
        },
        'stable_utilisation': round(total / STABLE_CAPACITY * 100, 1),
    }


# =======================================================================
# 3) VERSENY-KAPACITAS
# =======================================================================
def race_demand(pop, field_size=FIELD_SIZE, starts=STARTS_PER_HORSE_PER_SEASON):
    racers = pop['world']['racers']
    total_starts = racers * starts
    races_per_season = math.ceil(total_starts / field_size)
    return {
        'racers': racers,
        'total_starts': total_starts,
        'races_per_season': races_per_season,
        'races_per_day': round(races_per_season / SEASON_DAYS),
        'races_per_track_per_day': round(races_per_season / SEASON_DAYS / CURRENT_TRACKS),
    }


# A valos referencia: az USA-ban evente kb. 30-40 ezer futam van
# osszesen, minden palyan. Egy nagy palyan napi 8-12 futam.
REAL_RACES_PER_TRACK_PER_DAY = 10
REAL_US_RACES_PER_YEAR = 35000


def tracks_needed(races_per_day, per_track=REAL_RACES_PER_TRACK_PER_DAY):
    return math.ceil(races_per_day / per_track)


# =======================================================================
# 4) AUKCIO-KAPACITAS
# =======================================================================
def auction_demand(pop):
    lots_per_season = pop['world']['for_sale_per_season']
    lots_per_week = lots_per_season / 4          # 4 het egy szezonban

    # a hazak beosztasa (auction_sim.py):
    #   3 kategoriahaz hetvegen (pentek-szombat) = 2 nap
    #   1 vegyes haz hetfotol csutortokig = 4 nap
    weekend_days = 2
    weekday_days = 4

    # a kinalat megoszlasa: a kategoriahazak viszik a tobbseget
    weekend_lots = lots_per_week * 0.72
    weekday_lots = lots_per_week * 0.28

    weekend_sessions = math.ceil(weekend_lots / LOTS_PER_SESSION)
    weekday_sessions = math.ceil(weekday_lots / LOTS_PER_SESSION)

    # kapacitas a jelenlegi terv szerint
    weekend_capacity = 3 * weekend_days * MAX_SESSIONS_PER_DAY
    weekday_capacity = 1 * weekday_days * MAX_SESSIONS_PER_DAY

    return {
        'lots_per_season': lots_per_season,
        'lots_per_week': round(lots_per_week),
        'weekend': {'lots': round(weekend_lots), 'sessions_needed': weekend_sessions,
                    'capacity': weekend_capacity,
                    'sessions_per_house_per_day': math.ceil(weekend_sessions / (3 * weekend_days))},
        'weekday': {'lots': round(weekday_lots), 'sessions_needed': weekday_sessions,
                    'capacity': weekday_capacity,
                    'sessions_per_house_per_day': math.ceil(weekday_sessions / weekday_days)},
    }


# =======================================================================
# 4b) AZ ELADATLAN LOVAK SORSA
# =======================================================================
# A JATEKOS ERVELESE: nem kell minden lonak elkelnie. A tulajdonos
# donti el, mi legyen:
#   - megtartja es kesobb ujra probalkozik
#   - villamaron eladja (2 500)
#   - vagy az NPC felvasarolja
#
# A nagyon gyenge lovak lemorzsolodasa NEM PROBLEMA: a tenyesztes
# folyamatosan termeli az utanpotlast, es a gyenge lo ugysem termel
# erdemi tenyesztoi premiumot vagy versenynyeremenyt.
UNSOLD_RATE = 0.17               # auction_sim.py meresebol

UNSOLD_DISPOSITION = {
    'npc_buyout': 0.50,          # az NPC felvasarolja
    'keep_retry': 0.32,          # a jatekos megtartja, kesobb ujra probal
    'quick_sale': 0.18,          # villamar 2 500 -> kikerul a jatekbol
}


def unsold_flow(pop):
    """Mi tortenik az eladatlan lovakkal?"""
    listed = pop['world']['for_sale_per_season']
    unsold = round(listed * UNSOLD_RATE)
    return {
        'listed': listed,
        'sold': listed - unsold,
        'unsold': unsold,
        **{k: round(unsold * v) for k, v in UNSOLD_DISPOSITION.items()},
    }


# =======================================================================
# 4c) AZ NPC-ALLOMANY - EZEK IS FUTTATNAK
# =======================================================================
# EZT AZ ELSO MODELL NEM SZAMOLTA. Az NPC-k nemcsak vasarolnak, hanem
# futtatjak is a lovakat - ez erdemben noveli a verseny-keresletet.
#
# DE: az NPC-lovak nem kulon futamokat igenyelnek, hanem KITOLTIK a
# jatekos-futamok mezonyet. Ez koherensebb vilag, mint szintetikus
# ellenfeleket generalni: a lo, amit az NPC megvett, tenylegesen ott
# fut a mezonyben.
NPC_RACING_SEASONS = 4           # atlagosan ennyi szezont futnak meg
NPC_STARTS_PER_SEASON = 4        # kevesebbet, mint a jatekos lovai


def npc_population(pop):
    """Az NPC-k kezeben levo versenylo-allomany egyensulyi allapotban."""
    bought = round(pop['world']['for_sale_per_season'] * UNSOLD_RATE
                   * UNSOLD_DISPOSITION['npc_buyout'])
    # az elado piacrol is vesznek (nem csak az eladatlanokat)
    mb_gap = max(0, pop['world']['for_sale_per_season'] - _player_demand())
    bought += mb_gap
    steady = bought * NPC_RACING_SEASONS
    return {
        'bought_per_season': bought,
        'steady_population': steady,
        'starts_per_season': steady * NPC_STARTS_PER_SEASON,
    }


def _player_demand():
    net_growth_per_player = 0.6
    replacement_per_player = 1.1
    return round((net_growth_per_player + replacement_per_player) * ACTIVE_PLAYERS)


def combined_race_demand(pop):
    """A TELJES verseny-kereslet: jatekos + NPC lovak egyutt."""
    npc = npc_population(pop)
    player_starts = pop['world']['racers'] * STARTS_PER_HORSE_PER_SEASON
    npc_starts = npc['starts_per_season']
    total = player_starts + npc_starts
    return {
        'player_starts': player_starts,
        'npc_starts': npc_starts,
        'total_starts': total,
        'npc_share_pct': round(npc_starts / total * 100, 1),
        'races_per_season': math.ceil(total / FIELD_SIZE),
        'races_per_day': round(total / FIELD_SIZE / SEASON_DAYS),
    }


# =======================================================================
# 5) KERESLET-KINALAT EGYENSULY
# =======================================================================
# A kritikus kerdes nem a KAPACITAS, hanem hogy van-e ELEG VEVO.
# Ha 20 000 jatekos evente 50 000 lovat ad el, de csak 20 000-et vesz,
# a tobbi az NPC-re marad - es akkor a piac nem valodi.
def market_balance(pop):
    sellers_lots = pop['world']['for_sale_per_season']

    # hany lovat VESZ egy jatekos szezononkent?
    # A ferohely korlatoz: ha tele van az istallo, csak akkor vesz,
    # ha kozben eladott. A nettó novekedes szezononkent keves.
    net_growth_per_player = 0.6      # ennyivel no az allomany szezononkent
    replacement_per_player = 1.1     # ennyit cserel le (elado + vesz)
    buys_per_player = net_growth_per_player + replacement_per_player

    player_demand = round(buys_per_player * ACTIVE_PLAYERS)
    gap = sellers_lots - player_demand

    return {
        'supply': sellers_lots,
        'player_demand': player_demand,
        'gap': gap,
        'npc_absorption_needed': max(0, gap),
        'npc_share_pct': round(max(0, gap) / sellers_lots * 100, 1) if sellers_lots else 0,
    }


# =======================================================================
# JELENTES
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - KAPACITASMODELL ===")
    print(f"    {ACTIVE_PLAYERS:,} aktív játékos · {SEASON}. szezon\n".replace(',', ' '))

    pop = population()
    pp = pop['per_player']
    w = pop['world']

    print("--- 1) LOALLOMANY ---")
    print(f"  Egy átlagos játékosnál (stratégia-mix szerint):")
    print(f"     versenyló {pp['racers']:.1f} · kanca {pp['mares']:.1f} · "
          f"fiatal {pp['young']:.1f}  = {pp['total']:.1f} ló")
    print(f"     istálló-kihasználtság: {pop['stable_utilisation']}% "
          f"({STABLE_CAPACITY} férőhelyből)\n")
    print(f"  A világban összesen:")
    print(f"     versenyló  {w['racers']:>9,d}".replace(',', ' '))
    print(f"     kanca      {w['mares']:>9,d}".replace(',', ' '))
    print(f"     fiatal     {w['young']:>9,d}".replace(',', ' '))
    print(f"     ÖSSZESEN   {w['total']:>9,d} ló\n".replace(',', ' '))

    print("--- 2) VERSENY-KERESLET ---")
    rd = race_demand(pop)
    print(f"  {rd['racers']:,} versenyló × {STARTS_PER_HORSE_PER_SEASON} start "
          f"= {rd['total_starts']:,} start/szezon".replace(',', ' '))
    print(f"  {FIELD_SIZE} lovas mezőnyökkel: "
          f"{rd['races_per_season']:,} futam/szezon".replace(',', ' '))
    print(f"  Naponta: {rd['races_per_day']:,} futam".replace(',', ' '))
    print(f"  A jelenlegi {CURRENT_TRACKS} pályán: "
          f"{rd['races_per_track_per_day']:,} futam/pálya/nap".replace(',', ' '))
    print(f"\n  VALOS REFERENCIA: egy nagy pályán napi {REAL_RACES_PER_TRACK_PER_DAY} futam.")
    print(f"  Az USA-ban évente összesen kb. {REAL_US_RACES_PER_YEAR:,} futam.".replace(',', ' '))
    need = tracks_needed(rd['races_per_day'])
    print(f"\n  -> {need:,} PALYA kellene, ha valósághű napi programot akarunk.".replace(',', ' '))
    print(f"     A jelenlegi terv {CURRENT_TRACKS} pályával számol — "
          f"{need/CURRENT_TRACKS:.0f}× kevés.\n")

    print("--- 3) MEGOLDASI IRANYOK A VERSENYEKRE ---")
    print(f"  {'Megoldás':38s} {'Futam/nap':>10s} {'Pálya kell':>11s}")
    options = [
        ('Jelenlegi terv (8 lovas, 7 start)', FIELD_SIZE, STARTS_PER_HORSE_PER_SEASON),
        ('Nagyobb mezőny (14 lovas)', 14, STARTS_PER_HORSE_PER_SEASON),
        ('Kevesebb start (4/szezon)', FIELD_SIZE, 4),
        ('Mindkettő (14 lovas, 4 start)', 14, 4),
        ('Nagyobb mezőny (20 lovas, 4 start)', 20, 4),
    ]
    for label, fs, st in options:
        r = race_demand(pop, fs, st)
        t = tracks_needed(r['races_per_day'])
        print(f"  {label:38s} {r['races_per_day']:>10,d} {t:>11,d}".replace(',', ' '))
    print()

    print("--- 4) AUKCIO-KERESLET ---")
    ad = auction_demand(pop)
    print(f"  Eladásra szánt ló: {ad['lots_per_season']:,}/szezon "
          f"= {ad['lots_per_week']:,}/hét\n".replace(',', ' '))
    for key, label, houses, days in [('weekend', 'Hétvége (3 kategóriaház)', 3, 2),
                                      ('weekday', 'Hétköznap (vegyes ház)', 1, 4)]:
        d = ad[key]
        over = d['sessions_needed'] > d['capacity']
        print(f"  {label}")
        print(f"     tétel: {d['lots']:,}  ·  szükséges session: {d['sessions_needed']:,}"
              .replace(',', ' '))
        print(f"     jelenlegi kapacitás: {d['capacity']} session "
              f"({houses} ház × {days} nap × {MAX_SESSIONS_PER_DAY})")
        print(f"     -> {d['sessions_per_house_per_day']:,} session/ház/nap kellene"
              .replace(',', ' ')
              + ("   TULLEPES" if over else "   rendben"))
        print()

    print("--- 5) A VALODI KERDES: VAN-E ELEG VEVO? ---")
    mb = market_balance(pop)
    print(f"  Kínálat (eladásra szánt ló):  {mb['supply']:>9,d}/szezon".replace(',', ' '))
    print(f"  Játékosi kereslet:            {mb['player_demand']:>9,d}/szezon".replace(',', ' '))
    print(f"  Rés:                          {mb['gap']:>9,d}".replace(',', ' '))
    print(f"\n  Az NPC-nek a kínálat {mb['npc_share_pct']}%-át kell felszívnia.")
    if mb['npc_share_pct'] > 40:
        print("  -> EZ SOK. A piac tulnyomoreszt NPC-vel szemben mukodne,")
        print("     ami a 'valodi jatekospiac' erzetet elrontja.")
    print()

    print("--- 5b) AZ ELADATLAN LOVAK SORSA ---")
    uf = unsold_flow(pop)
    print(f"  Meghirdetve: {uf['listed']:,}  ·  eladva: {uf['sold']:,}  ·  "
          f"eladatlan: {uf['unsold']:,} ({UNSOLD_RATE*100:.0f}%)".replace(',', ' '))
    print(f"\n  Az eladatlanokkal:")
    labels = {'npc_buyout': 'NPC felvásárolja', 'keep_retry': 'A játékos megtartja, később újra próbál',
              'quick_sale': 'Villámár (2 500) — kikerül a játékból'}
    for k, lab in labels.items():
        print(f"     {lab:44s} {uf[k]:>7,d}".replace(',', ' '))
    print("\n  A gyenge lovak lemorzsolódása nem probléma: a tenyésztés")
    print("  folyamatosan termeli az utánpótlást.\n")

    print("--- 5c) AZ NPC-ALLOMANY ES A VERSENY-KERESLET ---")
    print("  EZT AZ ELSO MODELL NEM SZAMOLTA: az NPC-k futtatnak is.\n")
    npc = npc_population(pop)
    print(f"  NPC vásárlás:            {npc['bought_per_season']:>9,d} ló/szezon".replace(',', ' '))
    print(f"  NPC versenyló-állomány:  {npc['steady_population']:>9,d} (egyensúlyi)".replace(',', ' '))
    print(f"  NPC start/szezon:        {npc['starts_per_season']:>9,d} "
          f"({NPC_STARTS_PER_SEASON} start/ló)".replace(',', ' '))
    print()
    cd = combined_race_demand(pop)
    print(f"  Játékos start:  {cd['player_starts']:>9,d}".replace(',', ' '))
    print(f"  NPC start:      {cd['npc_starts']:>9,d}  ({cd['npc_share_pct']}%)".replace(',', ' '))
    print(f"  ÖSSZESEN:       {cd['total_starts']:>9,d} start/szezon".replace(',', ' '))
    print(f"\n  Futam/nap: {cd['races_per_day']:,} "
          f"(a csak-játékos {rd['races_per_day']:,} helyett)".replace(',', ' '))
    print(f"  Növekedés: +{(cd['races_per_day']/rd['races_per_day']-1)*100:.0f}%\n")
    print("  -> DE: az NPC-lovak nem külön futamokat igényelnek, hanem")
    print("     KITOLTIK a játékos-futamok mezőnyét. Egy tipikus mezőnyben")
    print(f"     {100-cd['npc_share_pct']:.0f}% játékos-ló és {cd['npc_share_pct']}% NPC-ló fut.")
    print("     Ez koherensebb, mint szintetikus ellenfeleket generálni:")
    print("     a ló, amit az NPC megvett, tényleg ott fut a mezőnyben.\n")

    print("--- 6) KOVETKEZTETESEK ---")
    print("  a) A 6 pálya nagyságrendekkel kevés. Vagy sokkal több pálya kell,")
    print("     vagy a futamokat el kell szakítani a fizikai pálya-slottól")
    print("     (párhuzamos futamok ugyanazon a pályán, időzónánként).")
    print()
    print("  b) A mezőnyméret növelése a leghatékonyabb eszköz: 8-ról 14-re")
    print("     emelve a futamszám 43%-kal csökken. A valóságban is gyakori")
    print("     a 12-14 lovas mezőny.")
    print()
    print("  c) Az aukciós kapacitás a session-limit emelésével megoldható,")
    print("     de a KERESLET a szűk keresztmetszet, nem a kapacitás.")
    print()
    print("  d) Az NPC-felszívás NEM probléma: az NPC-lovak kitöltik a")
    print("     mezőnyöket, így a világ koherensebb lesz, nem szegényebb.")
    print()
    print("  e) Az eladatlan lovak sorsáról a játékos dönt (megtart / villámár),")
    print("     a nagyon gyengék lemorzsolódása pedig kívánatos — a tenyésztés")
    print("     termeli az utánpótlást.")
    print()

    print("--- 7) JAVASLAT: MI KELL 20 000 JATEKOSHOZ ---")
    r14 = race_demand(pop, 14, 5)
    print(f"  Mezőnyméret:        14 ló (8 helyett)")
    print(f"  Start/szezon:       5 (7 helyett)")
    print(f"  Futam/nap:          {r14['races_per_day']:,}".replace(',', ' '))
    print(f"  Pálya:              {tracks_needed(r14['races_per_day'])} "
          f"(vagy 6 pálya párhuzamos futamokkal)")
    print(f"  Aukciós session:    {ad['weekend']['sessions_per_house_per_day']} /ház/nap hétvégén")
    print(f"  Session-limit:      emelendő {MAX_SESSIONS_PER_DAY}-ről")
    print(f"  NPC-felszívás:      {mb['npc_share_pct']}% — csökkentendő a férőhely")
    print(f"                      bővítésével (20-ra) vagy a kínálat mérséklésével")
