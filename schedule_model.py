"""
Breeder Tycoon - Race Schedule Model v2.0
=======================================================================
24 ORAS VERSENYNAPTAR IDOZONAK SZERINT.

A JATEKOS DONTESEI:
  - Rugalmas mezony: 8-14 lo
  - Minden palyan, a het minden napjan, 15 PERCENKENT futam
  - Nevezes 24 oraval a futam elott zarul - aki nem fer be, igy jart
  - A Group 1-2 es nagyversenyek NAP VEGEN surusodnek, IDOZONANKENT
  - Ha a jatekos nem talal futamot a sajat csucsidejeben, beirhatja
    egy masik idozona vagy egy uresebb sav futamaba - nem biztos, hogy
    elohen latja, de FELVETELROL visszanezheti, es a lo tud futni

  - PARHUZAMOS FUTAMOK: ugyanazon a palyan, ugyanabban az idopontban
    tobb futam is mehet. Igy nem kell tobb palya.
  - A jatekos a futam elott 24 oraval EGY LISTABOL valaszt futamot a
    lovanak. A lista NYEREMENY-SZUROVEL szukitheto.
  - Nevezes utan a jatekos MAR CSAK azokat a futamokat latja, ahova
    beirta a lovat - nem vesz el az informaciotomegben.

EZ AZ ELOZO KAPACITASMODELL VALASZA: a 15 perces suruseg + a
parhuzamossag egy jatekbeli palyat gyakorlatilag korlatlan
kapacitasuva tesz.

A PARHUZAMOSSAGNAK VALOS MEGFELELOJE VAN: ha egy futam tuljelentkezik,
a valosagban DIVIZIOKRA bontjak. Nalunk a parhuzamos futamok a
kulonbozo NYEREMENYSAVOK - igy a parhuzamossag egyben a mezony
osszemerhetoseget is biztositja.
"""

import math
from collections import Counter

# =======================================================================
# 1) A NAPTAR SZERKEZETE
# =======================================================================
RACE_INTERVAL_MIN = 15
SLOTS_PER_DAY_PER_TRACK = 24 * 60 // RACE_INTERVAL_MIN     # 96
FIELD_MIN = 8
FIELD_MAX = 14
FIELD_AVG = (FIELD_MIN + FIELD_MAX) / 2                     # 11

ENTRY_CLOSES_HOURS_BEFORE = 24

# Valos referencia osszevetesul: egy nagy palyan napi kb. 10 futam.
REAL_RACES_PER_TRACK_PER_DAY = 10


def track_capacity(n_tracks, days=30):
    slots = n_tracks * SLOTS_PER_DAY_PER_TRACK * days
    return {
        'races_per_day_per_track': SLOTS_PER_DAY_PER_TRACK,
        'races_per_day': n_tracks * SLOTS_PER_DAY_PER_TRACK,
        'races_per_season': slots,
        'starts_min': slots * FIELD_MIN,
        'starts_avg': round(slots * FIELD_AVG),
        'starts_max': slots * FIELD_MAX,
        'vs_real': round(SLOTS_PER_DAY_PER_TRACK / REAL_RACES_PER_TRACK_PER_DAY, 1),
    }


def tracks_for_starts(total_starts, days=30, field=FIELD_AVG):
    """Hany palya kell ennyi starthoz?"""
    races = total_starts / field
    return math.ceil(races / (SLOTS_PER_DAY_PER_TRACK * days))


# =======================================================================
# 1b) NYEREMENYSAVOK ES PARHUZAMOSSAG
# =======================================================================
# A track_sim.py sávjai. A parhuzamos futamok EZEK szerint bomlanak -
# igy egy idopontban tobb futam megy, de mindegyikben osszemerheto
# lovak indulnak.
#
# A LOALLOMANY ELOSZLASA a savok kozott: a tobbseg alul van. Ez a
# valos versenyzest is tukrozi (a futamok ~70%-a claiming szintu).
EARNINGS_BRACKETS = [
    {'key': 'maiden', 'label': 'Még nem nyert',  'share': 0.26},
    {'key': 'b5',     'label': '5 000 alatt',    'share': 0.24},
    {'key': 'b20',    'label': '20 000 alatt',   'share': 0.21},
    {'key': 'b75',    'label': '75 000 alatt',   'share': 0.16},
    {'key': 'b250',   'label': '250 000 alatt',  'share': 0.09},
    {'key': 'open',   'label': 'Nyílt',          'share': 0.04},
]

MAX_PARALLEL_PER_SLOT = 6      # savonkent legfeljebb egy futam


def bracket_schedule(starts_in_hour, n_tracks):
    """Savonkent: hany futam megy oranként, es milyen surun?

    NEM minden sav indul minden idopontban - ez lenne a hiba. A savok
    ROTALODNAK a slotok kozott: egy adott sav orankent nehany futamot
    kap, a kozottuk levo varakozas percekben merheto.

    Ez a valos versenynap szerkezete is: a program kulonbozo tipusu
    futamokat valtogat, nem ugyanazt ismetli.
    """
    slots_per_hour = n_tracks * (60 // RACE_INTERVAL_MIN)
    out = []
    used_slots = 0
    for b in EARNINGS_BRACKETS:
        starts = starts_in_hour * b['share']
        races = starts / FIELD_AVG
        if races < 0.5:
            out.append({'bracket': b['label'], 'races_per_hour': 0,
                        'gap_min': None, 'field': round(starts), 'runs': False})
            continue
        races = max(1, round(races))
        used_slots += races
        out.append({
            'bracket': b['label'],
            'races_per_hour': races,
            'gap_min': round(60 / races),
            'field': min(FIELD_MAX, max(FIELD_MIN, round(starts / races))),
            'runs': True,
        })
    return {'brackets': out, 'slots_used': used_slots,
            'slots_available': slots_per_hour,
            'parallel_per_slot': round(used_slots / slots_per_hour, 1)}


# =======================================================================
# 2) IDOZONAK ES CSUCSIDOK
# =======================================================================
# Egy mobil menedzserjatek tipikus jatekos-megoszlasa. Minden regionak
# sajat esti csucsa van - ez hatarozza meg, mikor akarnak versenyt nezni.
TIMEZONES = [
    {'key': 'europe',  'name': 'Európa',        'share': 0.35, 'utc_offset': 1},
    {'key': 'americas','name': 'Amerika',       'share': 0.30, 'utc_offset': -6},
    {'key': 'asia',    'name': 'Ázsia',         'share': 0.25, 'utc_offset': 8},
    {'key': 'oceania', 'name': 'Óceánia/egyéb', 'share': 0.10, 'utc_offset': 11},
]

# A napon beluli aktivitas gorbeje (helyi ido szerint, 0-23 ora).
# Esti csucs, hajnali melypont - ez a mobil jatekok jellemzo mintaja.
LOCAL_ACTIVITY = [
    0.15, 0.08, 0.05, 0.04, 0.04, 0.06,   # 00-05
    0.12, 0.25, 0.35, 0.40, 0.42, 0.45,   # 06-11
    0.50, 0.48, 0.45, 0.48, 0.55, 0.70,   # 12-17
    0.90, 1.00, 0.98, 0.85, 0.60, 0.32,   # 18-23
]


def utc_demand_curve():
    """A vilag ossz-kereslete UTC oraban. Az idozonak esti csucsai
    ELTOLODNAK egymashoz kepest - ettol lesz a nap folyamatosan
    terhelt, csucsok es volgyek valtakozasaval."""
    curve = [0.0] * 24
    for tz in TIMEZONES:
        for local_h in range(24):
            utc_h = (local_h - tz['utc_offset']) % 24
            curve[utc_h] += LOCAL_ACTIVITY[local_h] * tz['share']
    total = sum(curve)
    return [c / total for c in curve]      # normalizalva


def peak_analysis():
    curve = utc_demand_curve()
    avg = sum(curve) / 24
    peak = max(curve)
    trough = min(curve)
    peak_hours = [h for h, c in enumerate(curve) if c > avg * 1.15]
    quiet_hours = [h for h, c in enumerate(curve) if c < avg * 0.85]
    return {'curve': curve, 'avg': avg, 'peak': peak, 'trough': trough,
            'peak_ratio': round(peak / trough, 2),
            'peak_hours': peak_hours, 'quiet_hours': quiet_hours}


# =======================================================================
# 3) NAGYVERSENYEK - IDOZONANKENT A NAP VEGEN
# =======================================================================
# A JATEKOS DONTESE: a Group 1-2 es mas nagyversenyek minden idozona
# esti csucsara esnek. Igy mindenki a sajat estejeben lat nagy futamot.
BIG_RACE_LOCAL_HOURS = [19, 20, 21]     # helyi ido szerint


def big_race_schedule():
    """Mikor mennek a nagyversenyek UTC szerint?"""
    slots = []
    for tz in TIMEZONES:
        for local_h in BIG_RACE_LOCAL_HOURS:
            utc_h = (local_h - tz['utc_offset']) % 24
            slots.append({'utc_hour': utc_h, 'region': tz['name'],
                          'local_hour': local_h, 'share': tz['share']})
    return sorted(slots, key=lambda s: s['utc_hour'])


# =======================================================================
# 4) NEVEZES ES TULJELENTKEZES
# =======================================================================
# A nevezes 24 oraval korabban zarul, ELSO JON - ELSO KAPJA alapon.
# Aki nem fer be a csucsido futamaba, atteheto egy uresebb savba.
def slot_utilisation(n_tracks, total_starts_per_day):
    """Oralebontasban: hol telik meg, hol marad ures hely?"""
    curve = utc_demand_curve()
    slots_per_hour = n_tracks * (60 // RACE_INTERVAL_MIN)
    capacity_per_hour = slots_per_hour * FIELD_MAX

    rows = []
    overflow_total = 0
    for h in range(24):
        demand = total_starts_per_day * curve[h]
        used = min(demand, capacity_per_hour)
        overflow = max(0, demand - capacity_per_hour)
        overflow_total += overflow
        rows.append({
            'hour': h,
            'demand': round(demand),
            'capacity': capacity_per_hour,
            'utilisation': round(used / capacity_per_hour * 100, 1),
            'overflow': round(overflow),
            'avg_field': round(min(FIELD_MAX, max(0, demand / slots_per_hour)), 1),
        })
    return {'rows': rows, 'overflow_per_day': round(overflow_total),
            'overflow_pct': round(overflow_total / total_starts_per_day * 100, 1)}


def absorb_overflow(util):
    """A tuljelentkezest a uresebb savok felszivjak. Mennyi fer el?"""
    free = sum(max(0, r['capacity'] - r['demand']) for r in util['rows'])
    over = util['overflow_per_day']
    return {'free_capacity': round(free), 'overflow': over,
            'absorbed': min(free, over), 'unplaced': max(0, over - free),
            'can_absorb': free >= over}


# =======================================================================
# JELENTES
# =======================================================================
if __name__ == '__main__':
    # az elozo modell szamai
    RACERS = 74900
    print("=== BREEDER TYCOON - VERSENYNAPTAR MODELL ===")
    print(f"    {RACERS:,} versenyló · rugalmas mezőny {FIELD_MIN}-{FIELD_MAX} ló\n"
          .replace(',', ' '))

    print("--- 1) MIT AD A 15 PERCES SURUSEG ---")
    for n in [6, 10, 14]:
        c = track_capacity(n)
        print(f"  {n:>2d} pálya: {c['races_per_day']:>5,d} futam/nap  ·  "
              f"{c['starts_avg']:>9,d} start/szezon".replace(',', ' '))
    c6 = track_capacity(6)
    print(f"\n  Egy pálya napi {c6['races_per_day_per_track']} futamot bír "
          f"— a valós {REAL_RACES_PER_TRACK_PER_DAY} helyett ({c6['vs_real']}×).\n")

    print("--- 2) HANY PALYA KELL? ---")
    print(f"  {'Start/ló/szezon':>17s} {'Össz start':>12s} {'Pálya':>7s} {'Futam/nap':>11s}")
    for starts in [3, 4, 5, 6, 7]:
        total = RACERS * starts
        n = tracks_for_starts(total)
        rpd = math.ceil(total / FIELD_AVG / 30)
        print(f"  {starts:>17d} {total:>12,d} {n:>7d} {rpd:>11,d}".replace(',', ' '))
    print()

    print("--- 3) A NAP TERHELESE UTC SZERINT ---")
    pa = peak_analysis()
    print(f"  Csúcs/völgy arány: {pa['peak_ratio']}×")
    print(f"  Csúcsórák (UTC): {', '.join(str(h)+'h' for h in pa['peak_hours'])}")
    print(f"  Csendes órák:    {', '.join(str(h)+'h' for h in pa['quiet_hours'])}\n")
    for h in range(24):
        v = pa['curve'][h]
        bar = '#' * round(v / pa['peak'] * 40)
        mark = ' <- csúcs' if h in pa['peak_hours'] else (' <- csendes' if h in pa['quiet_hours'] else '')
        print(f"  {h:>2d}h  {bar:<40s} {v*100:4.1f}%{mark}")
    print()

    print("--- 4) NAGYVERSENYEK IDOZONANKENT ---")
    print("  Minden régió a SAJÁT estéjében lát nagy futamot:\n")
    for s in big_race_schedule():
        print(f"  {s['utc_hour']:>2d}h UTC  =  {s['region']:16s} "
              f"helyi {s['local_hour']}h   (a játékosok {s['share']*100:.0f}%-a)")
    print()

    print("--- 5) TULJELENTKEZES ES ATIRANYITAS ---")
    STARTS_PER_HORSE = 5
    total_starts_season = RACERS * STARTS_PER_HORSE
    total_starts_day = total_starts_season / 30
    n_tracks = tracks_for_starts(total_starts_season)
    print(f"  {STARTS_PER_HORSE} start/ló/szezon · {n_tracks} pálya · "
          f"{round(total_starts_day):,} start/nap\n".replace(',', ' '))

    util = slot_utilisation(n_tracks, total_starts_day)
    print(f"  {'Óra':>4s} {'Igény':>7s} {'Kapacitás':>10s} {'Kihasz.':>9s} "
          f"{'Átlag mezőny':>13s} {'Túljel.':>9s}")
    for r in util['rows']:
        flag = '  TELE' if r['overflow'] > 0 else ''
        print(f"  {r['hour']:>3d}h {r['demand']:>7,d} {r['capacity']:>10,d} "
              f"{r['utilisation']:>8.1f}% {r['avg_field']:>13.1f} "
              f"{r['overflow']:>9,d}{flag}".replace(',', ' '))

    ab = absorb_overflow(util)
    print(f"\n  Túljelentkezés: {ab['overflow']:,}/nap ({util['overflow_pct']}%)"
          .replace(',', ' '))
    print(f"  Szabad kapacitás a csendes sávokban: {ab['free_capacity']:,}"
          .replace(',', ' '))
    if ab['can_absorb']:
        print(f"  -> A csendes sávok FELSZIVJAK a túljelentkezést.")
        print(f"     Aki nem fér be a csúcsidőbe, átteheti egy üresebb sávba —")
        print(f"     élőben nem biztos, hogy látja, de felvételről visszanézheti.")
    else:
        print(f"  -> {ab['unplaced']:,} start NEM fér el sehova. Több pálya kell."
              .replace(',', ' '))
    print()

    print("--- 5b) PARHUZAMOS FUTAMOK UGYANAZON A PALYAN ---")
    print("  Egy időpontban több futam megy, nyereménysávonként bontva.")
    print("  Ez egyben biztosítja, hogy összemérhető lovak fussanak egymás ellen.\n")
    PARALLEL_TRACKS = 6      # a parhuzamossag valtja ki a tobb palyat
    for label, hour in [('Csúcsidő (18h UTC)', 18), ('Átlagos (12h UTC)', 12),
                        ('Csendes (5h UTC)', 5)]:
        row = next(r for r in util['rows'] if r['hour'] == hour)
        sch = bracket_schedule(row['demand'], PARALLEL_TRACKS)
        print(f"  {label}  —  {row['demand']:,} start/óra  ·  "
              f"{sch['parallel_per_slot']} párhuzamos futam időpontonként"
              .replace(',', ' '))
        for r in sch['brackets']:
            if r['runs']:
                print(f"     {r['bracket']:16s} {r['races_per_hour']:>2d} futam/óra  "
                      f"({r['gap_min']:>2d} percenként)  {r['field']:>2d} lovas mezőny")
            else:
                print(f"     {r['bracket']:16s} — ritkábban indul "
                      f"({r['field']} jelentkező/óra)")
        print()

    print("--- 5c) AMIT A JATEKOS LAT ---")
    print("  A nyeremény-szűrő eldönti, melyik futamokat kínáljuk fel.")
    print("  Egy lónak a következő 24 órában ennyi futam közül lehet választani:\n")
    for b in EARNINGS_BRACKETS:
        total = 0
        for r in util['rows']:
            sch = bracket_schedule(r['demand'], PARALLEL_TRACKS)
            match = next(x for x in sch['brackets'] if x['bracket'] == b['label'])
            total += match['races_per_hour']
        print(f"  {b['label']:16s} {total:>4,d} választható futam / 24 óra"
              .replace(',', ' '))
    print("\n  Nevezés után a játékos MAR CSAK azokat a futamokat látja,")
    print("  ahova beírta a lovát — nem vész el az információtömegben.\n")

    print("--- 6) A RUGALMAS MEZONY HATASA ---")
    print("  A 8-14 közötti sáv lehetővé teszi, hogy a csendes órákban is")
    print("  elinduljon a futam, csak kisebb mezőnnyel:\n")
    quiet = [r for r in util['rows'] if r['hour'] in pa['quiet_hours']]
    peak = [r for r in util['rows'] if r['hour'] in pa['peak_hours']]
    if quiet:
        print(f"  Csendes órákban átlagos mezőny: "
              f"{sum(r['avg_field'] for r in quiet)/len(quiet):.1f} ló")
    if peak:
        print(f"  Csúcsórákban átlagos mezőny:    "
              f"{sum(r['avg_field'] for r in peak)/len(peak):.1f} ló")
    print(f"  (a rugalmas sáv: {FIELD_MIN}-{FIELD_MAX})\n")

    print("--- 7) OSSZEFOGLALAS ---")
    print(f"  Nevezés zárul:      {ENTRY_CLOSES_HOURS_BEFORE} órával a futam előtt")
    print(f"  Futam-sűrűség:      {RACE_INTERVAL_MIN} percenként, 24 órában, minden nap")
    print(f"  Pálya-kapacitás:    {SLOTS_PER_DAY_PER_TRACK} futam/pálya/nap")
    print(f"  Szükséges pálya:    {n_tracks} ({STARTS_PER_HORSE} start/ló/szezon mellett)")
    print(f"  Mezőnyméret:        {FIELD_MIN}-{FIELD_MAX} rugalmasan")
    print(f"  Nagyversenyek:      minden időzóna esti csúcsán")
    print(f"  Túljelentkezés:     {util['overflow_pct']}% — a csendes sávok felszívják")
    peak_sch = bracket_schedule(
        next(r for r in util['rows'] if r['hour'] == 18)['demand'], 6)
    print(f"  Pálya:              6 (a párhuzamosság váltja ki a többet)")
    print(f"  Párhuzamosság:      {peak_sch['parallel_per_slot']} futam/időpont csúcsidőben")
    print(f"  Szűrő:              életnyeremény szerint")
    print(f"  Nevezés után:       csak a saját futamok látszanak")
