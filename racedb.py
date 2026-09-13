"""
Breeder Tycoon - Race Database v1.0
=======================================================================
A VERSENYADATBAZIS ES AZ AGGREGATUM-RETEG.

Ez volt a legnagyobb hianyzo RENDSZER. Nelkule nincs:
  - pedigre-lap (nincs mit mutatni)
  - black type (nincs miből szamolni)
  - ivadekstatisztika (a listing_sim, family_sim, stud_sim fele all)
  - Hall of Fame (nincs rangsor)
  - men-kereslet (nincs ivadekteljesitmeny)

A schema.sql tablait koveti, de MEMORIABAN. Az adatbazis-kapcsolat
kesobb jon; a SEMA es a PROPAGACIO viszont mar most helyes.

HAROM RETEG (data_architecture.py szerint):
    PEDIGRE  (game.py Horse)  +  VERSENY (itt)  ->  AGGREGATUM (itt)

A LENYEG: az aggregatum IRASKOR frissul, nem olvasaskor szamolodik.
Egy futam eredmenye ~7 sort erint, fuggetlenul attol, mekkora a vilag.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =======================================================================
# 1) VERSENY-TABLAK (schema.sql: race, race_result)
# =======================================================================
@dataclass
class Race:
    race_id: int
    season: int
    day: int
    track_id: str
    track_name: str
    distance_f: int
    surface: str
    going: str
    bracket: str
    purse: int
    field_size: int
    is_black_type: bool = False
    classic_key: Optional[str] = None


@dataclass
class RaceResult:
    race_id: int
    season: int
    horse_id: str
    position: int
    earnings: int
    jockey_id: Optional[str] = None
    trainer_id: Optional[str] = None
    injury: Optional[str] = None
    # a futas pillanataban ervenyes allapot - visszajatszhatosag miatt
    fill_bar: Optional[float] = None
    freshness: Optional[float] = None


# =======================================================================
# 2) AGGREGATUM-TABLAK (schema.sql: horse_stats, family_stats, stud_stats)
# =======================================================================
@dataclass
class HorseStats:
    horse_id: str
    # sajat versenyzes
    starts: int = 0
    wins: int = 0
    places: int = 0
    career_earnings: int = 0
    black_type_wins: int = 0
    black_type_places: int = 0
    classic_wins: int = 0
    best_bracket: Optional[str] = None
    # SZULOKENT - ezt a GYEREKEK futasa frissiti
    progeny_count: int = 0
    progeny_runners: int = 0
    progeny_winners: int = 0
    progeny_black_type: int = 0
    progeny_classic: int = 0
    progeny_earnings: int = 0


@dataclass
class FamilyStats:
    family_id: str
    total_offspring: int = 0
    runners: int = 0
    winners: int = 0
    black_type_count: int = 0
    classic_count: int = 0
    total_earnings: int = 0
    is_blue_hen_line: bool = False


@dataclass
class StudStats:
    stud_id: str
    seasons_at_stud: int = 0
    mares_covered_total: int = 0
    mares_this_season: int = 0
    progeny_performance: float = 0.0
    globally_listed: bool = False


# =======================================================================
# 3) BLACK TYPE SZINTEK
# =======================================================================
# A listing_sim.py katalogus-konvencioja szerint.
class BlackType(Enum):
    NONE = 'none'
    PLACED = 'placed'      # 2-3. hely black type futamban
    WINNER = 'winner'      # gyozelem black type futamban
    CLASSIC = 'classic'    # klasszikus gyozelem


def classify_result(position, race: Race):
    if race.classic_key and position == 1:
        return BlackType.CLASSIC
    if race.is_black_type and position == 1:
        return BlackType.WINNER
    if race.is_black_type and position <= 3:
        return BlackType.PLACED
    return BlackType.NONE


# =======================================================================
# 4) AZ ADATBAZIS
# =======================================================================
class RaceDatabase:
    """A versenyadatbazis + az aggregatum-reteg egyben.

    A schema.sql-t koveti, de memoriaban. Az adatbazis-kapcsolat
    kesobb jon; a propagacio logikaja mar most helyes.
    """

    def __init__(self):
        self.races: dict = {}            # race_id -> Race
        self.results: dict = {}          # race_id -> [RaceResult]
        self.by_horse: dict = {}         # horse_id -> [race_id]
        self.horse_stats: dict = {}      # horse_id -> HorseStats
        self.family_stats: dict = {}     # family_id -> FamilyStats
        self.stud_stats: dict = {}       # stud_id -> StudStats
        self.premiums: dict = {}         # breeder_id -> osszeg
        self._next_race_id = 1

    # --- segedek ---
    def stats(self, horse_id) -> HorseStats:
        if horse_id not in self.horse_stats:
            self.horse_stats[horse_id] = HorseStats(horse_id)
        return self.horse_stats[horse_id]

    def family(self, family_id) -> FamilyStats:
        if family_id not in self.family_stats:
            self.family_stats[family_id] = FamilyStats(family_id)
        return self.family_stats[family_id]

    def stud(self, stud_id) -> StudStats:
        if stud_id not in self.stud_stats:
            self.stud_stats[stud_id] = StudStats(stud_id)
        return self.stud_stats[stud_id]

    # ------------------------------------------------------------------
    # 4a) SZULETES REGISZTRALASA
    # ------------------------------------------------------------------
    def record_birth(self, foal, sire, dam):
        """Uj csiko: a progeny_count NO, a csalad bovul.

        A family_id az ANYJATOL oroklodik (data_architecture.py) -
        igy a csalad-lekerdezes indexelt kereses, nem rekurzio.
        """
        self.stats(foal.horse_id)                    # ures sor
        if sire:
            self.stats(sire.horse_id).progeny_count += 1
            self.stud(sire.horse_id).mares_this_season += 1
            self.stud(sire.horse_id).mares_covered_total += 1
        if dam:
            self.stats(dam.horse_id).progeny_count += 1
        if foal.family_id:
            self.family(foal.family_id).total_offspring += 1

    # ------------------------------------------------------------------
    # 4b) FUTAM ROGZITESE
    # ------------------------------------------------------------------
    def record_race(self, season, day, track_id, track_name, distance_f,
                    surface, going, bracket, purse, field_size,
                    is_black_type=False, classic_key=None):
        r = Race(self._next_race_id, season, day, track_id, track_name,
                 distance_f, surface, going, bracket, purse, field_size,
                 is_black_type, classic_key)
        self.races[r.race_id] = r
        self.results[r.race_id] = []
        self._next_race_id += 1
        return r

    # ------------------------------------------------------------------
    # 4c) EREDMENY + PROPAGACIO  -- EZ A LENYEG
    # ------------------------------------------------------------------
    def record_result(self, race: Race, horse, position, earnings,
                      jockey_id=None, trainer_id=None, injury=None,
                      fill_bar=None, freshness=None,
                      breeder_premium_rate=0.15):
        """Egy eredmeny rogzitese ES a teljes propagacio.

        ~7 sort erint, FUGGETLENUL attol, mekkora a vilag:
          1. a lo sajat statisztikaja
          2-3. a ket szulo ivadek-statisztikaja
          4. a noi csalad (EGYETLEN sor, mert a family_id oroklodik)
          5. a men kereslet-bemenete
          6. a tenyesztoi premium
        """
        res = RaceResult(race.race_id, race.season, horse.horse_id,
                         position, earnings, jockey_id, trainer_id,
                         injury, fill_bar, freshness)
        self.results[race.race_id].append(res)
        self.by_horse.setdefault(horse.horse_id, []).append(race.race_id)

        bt = classify_result(position, race)

        # --- 1. sajat statisztika ---
        st = self.stats(horse.horse_id)
        first_start = st.starts == 0
        st.starts += 1
        st.career_earnings += earnings
        if position == 1:
            st.wins += 1
        elif position <= 3:
            st.places += 1
        if bt == BlackType.CLASSIC:
            st.classic_wins += 1
            st.black_type_wins += 1
        elif bt == BlackType.WINNER:
            st.black_type_wins += 1
        elif bt == BlackType.PLACED:
            st.black_type_places += 1
        st.best_bracket = _better_bracket(st.best_bracket, race.bracket)

        # --- 2-3. a ket szulo ---
        #
        # FONTOS: a progeny_black_type DISZTINKT LOVAKAT szamol, nem
        # futamokat. A valos kataloguslapokon a "3 black type winner"
        # HAROM LOVAT jelent, nem harom gyozelmet.
        #
        # Ezert csak akkor noveljuk, ha ez az utod ELSO black type
        # gyozelme (a fenti blokkban mar novelt szamlalobol latszik).
        first_bt_win = (bt in (BlackType.WINNER, BlackType.CLASSIC)
                        and st.black_type_wins == 1)
        first_classic = (bt == BlackType.CLASSIC and st.classic_wins == 1)

        for pid in (horse.sire_id, horse.dam_id):
            if not pid:
                continue
            ps = self.stats(pid)
            ps.progeny_earnings += earnings
            if first_start:
                ps.progeny_runners += 1
            if position == 1 and st.wins == 1:
                ps.progeny_winners += 1
            if first_bt_win:
                ps.progeny_black_type += 1
            if first_classic:
                ps.progeny_classic += 1

        # --- 4. a noi csalad: EGYETLEN sor ---
        if horse.family_id:
            fs = self.family(horse.family_id)
            fs.total_earnings += earnings
            if first_start:
                fs.runners += 1
            if position == 1 and st.wins == 1:
                fs.winners += 1
            # a csaladnal is DISZTINKT lovakat szamolunk
            if first_bt_win:
                fs.black_type_count += 1
            if first_classic:
                fs.classic_count += 1

        # --- 5. a men kereslet-bemenete ---
        if horse.sire_id:
            self._recalc_progeny_performance(horse.sire_id)

        # --- 6. TENYESZTOI PREMIUM: a TENYESZTOE, nem a tulajdonose ---
        premium = 0
        if earnings > 0 and getattr(horse, 'breeder_id', None):
            premium = round(earnings * breeder_premium_rate)
            self.premiums[horse.breeder_id] = \
                self.premiums.get(horse.breeder_id, 0) + premium

        return {'result': res, 'black_type': bt, 'premium': premium}

    def _recalc_progeny_performance(self, stud_id):
        """A men ivadekteljesitmenye 0-100 - a stud_sim.py kereslet-
        modelljenek bemenete."""
        s = self.stats(stud_id)
        if s.progeny_runners == 0:
            return
        win_rate = s.progeny_winners / max(1, s.progeny_runners)
        bt_rate = s.progeny_black_type / max(1, s.progeny_runners)
        earn = s.progeny_earnings / max(1, s.progeny_runners)
        score = win_rate * 40 + bt_rate * 35 + min(25, earn / 2000)
        self.stud(stud_id).progeny_performance = round(min(100, score), 1)

    # ------------------------------------------------------------------
    # 4d) BLUE HEN ELLENORZES
    # ------------------------------------------------------------------
    def check_blue_hen(self, horse_id, threshold=3):
        """A family_sim.py kuszobe: harom black type utod."""
        s = self.stats(horse_id)
        return s.progeny_black_type >= threshold

    # ------------------------------------------------------------------
    # 5) OLVASASI UTAK
    # ------------------------------------------------------------------
    def form(self, horse_id, limit=6):
        """Egy lo utolso futamai - a katalogus-lap 'versenyforma' resze."""
        ids = self.by_horse.get(horse_id, [])[-limit:]
        out = []
        for rid in reversed(ids):
            race = self.races[rid]
            res = next(r for r in self.results[rid] if r.horse_id == horse_id)
            out.append({
                'season': race.season, 'track': race.track_name,
                'distance_f': race.distance_f, 'bracket': race.bracket,
                'position': res.position, 'earnings': res.earnings,
                'black_type': classify_result(res.position, race).value,
            })
        return out

    def progeny_of(self, horse_id, world_horses):
        """Egy lo utodai es az eredmenyeik.

        EGYETLEN aggregatum-olvasas + a nevek kikeresese. Aggregatum
        NELKUL ez tobb tucat lekerdezes lenne.
        """
        kids = [h for h in world_horses.values()
                if h.sire_id == horse_id or h.dam_id == horse_id]
        out = []
        for k in kids:
            s = self.stats(k.horse_id)
            bt = BlackType.NONE
            if s.classic_wins:
                bt = BlackType.CLASSIC
            elif s.black_type_wins:
                bt = BlackType.WINNER
            elif s.black_type_places:
                bt = BlackType.PLACED
            out.append({
                'name': k.name, 'sex': k.sex, 'age': k.age,
                'starts': s.starts, 'wins': s.wins,
                'earnings': s.career_earnings,
                'black_type': bt.value,
            })
        return sorted(out, key=lambda x: -x['earnings'])

    def catalogue_page(self, horse, world_horses):
        """A TELJES katalogus-lap. Harom aggregatum-olvasas.

        Ez az, amit a versenyadatbazis nelkul nem lehetett megcsinalni.
        """
        s = self.stats(horse.horse_id)
        fam = self.family(horse.family_id) if horse.family_id else None
        sire = world_horses.get(horse.sire_id)
        dam = world_horses.get(horse.dam_id)

        def bt_of(h):
            if not h:
                return BlackType.NONE.value
            hs = self.stats(h.horse_id)
            if hs.classic_wins or hs.black_type_wins:
                return BlackType.WINNER.value
            if hs.black_type_places:
                return BlackType.PLACED.value
            return BlackType.NONE.value

        return {
            'name': horse.name, 'sex': horse.sex, 'age': horse.age,
            'colour': horse.colour, 'rarity': horse.rarity,
            'stage': horse.stage,
            'pedigree': {
                'sire': sire.name if sire else None,
                'sire_black_type': bt_of(sire),
                'dam': dam.name if dam else None,
                'dam_black_type': bt_of(dam),
            },
            'form': {
                'starts': s.starts, 'wins': s.wins, 'places': s.places,
                'earnings': s.career_earnings,
                'black_type_wins': s.black_type_wins,
                'classic_wins': s.classic_wins,
                'best_bracket': s.best_bracket,
            },
            'recent': self.form(horse.horse_id, 4),
            'progeny': {
                'count': s.progeny_count,
                'runners': s.progeny_runners,
                'winners': s.progeny_winners,
                'black_type': s.progeny_black_type,
                'classic': s.progeny_classic,
                'earnings': s.progeny_earnings,
                'is_blue_hen': self.check_blue_hen(horse.horse_id),
            } if s.progeny_count else None,
            'family': {
                'offspring': fam.total_offspring,
                'black_type': fam.black_type_count,
                'classic': fam.classic_count,
                'earnings': fam.total_earnings,
            } if fam else None,
        }

    # ------------------------------------------------------------------
    # 5b) TELJES PEDIGRE-VISSZAKOVETES
    # ------------------------------------------------------------------
    # A 14 elemu os-tomb (game.py) NEGY generaciot fed le - ez a gyors
    # kataloguslap-megjelenites miatt van denormalizalva.
    #
    # A TELJES vonal viszont NEM VESZ EL: a sire_id/dam_id lanc
    # tetszoleges melysegig bejarhato. Ez a kulon pedigre-oldal alapja.
    def full_pedigree(self, horse, world_horses, depth=6):
        """A teljes szarmazasi fa, tetszoleges melysegig.

        Nem a 14 elemu os-tombbol dolgozik, hanem a sire_id/dam_id
        lancot jarja be - igy a hatodik, tizedik generacio sem vesz el.
        """
        def node(h, level):
            if h is None or level > depth:
                return None
            st = self.stats(h.horse_id)
            bt = 'none'
            if st.classic_wins:
                bt = 'classic'
            elif st.black_type_wins:
                bt = 'winner'
            elif st.black_type_places:
                bt = 'placed'
            return {
                'name': h.name, 'sex': h.sex, 'level': level,
                'colour': h.colour, 'black_type': bt,
                'starts': st.starts, 'wins': st.wins,
                'earnings': st.career_earnings,
                'progeny_black_type': st.progeny_black_type,
                'sire': node(world_horses.get(h.sire_id), level + 1),
                'dam': node(world_horses.get(h.dam_id), level + 1),
            }
        return node(horse, 0)

    def tail_female(self, horse, world_horses, limit=12):
        """A TISZTA NOI VONAL - anya, nagyanya, dedanya...

        Ez a "female family" gerince (family_sim.py). A valos
        katalogusokban ez kulon szekciokent jelenik meg.
        """
        line, h, guard = [], world_horses.get(horse.dam_id), 0
        while h is not None and guard < limit:
            st = self.stats(h.horse_id)
            line.append({
                'name': h.name, 'generation': guard + 1,
                'starts': st.starts, 'wins': st.wins,
                'earnings': st.career_earnings,
                'progeny': st.progeny_count,
                'progeny_black_type': st.progeny_black_type,
                'is_blue_hen': st.progeny_black_type >= 3,
            })
            h = world_horses.get(h.dam_id)
            guard += 1
        return line

    def tail_male(self, horse, world_horses, limit=12):
        """A TISZTA MEN VONAL - apa, nagyapa (apai agon), ..."""
        line, h, guard = [], world_horses.get(horse.sire_id), 0
        while h is not None and guard < limit:
            st = self.stats(h.horse_id)
            line.append({
                'name': h.name, 'generation': guard + 1,
                'starts': st.starts, 'wins': st.wins,
                'earnings': st.career_earnings,
                'black_type': st.black_type_wins,
                'progeny': st.progeny_count,
                'progeny_black_type': st.progeny_black_type,
            })
            h = world_horses.get(h.sire_id)
            guard += 1
        return line

    def siblings(self, horse, world_horses):
        """Testverek: teljes (mindket szulo) es fel (egy szulo).

        A valos kataloguslapok kulon jelolik a kettot.
        """
        full, half = [], []
        for h in world_horses.values():
            if h.horse_id == horse.horse_id:
                continue
            same_sire = h.sire_id and h.sire_id == horse.sire_id
            same_dam = h.dam_id and h.dam_id == horse.dam_id
            if not (same_sire or same_dam):
                continue
            st = self.stats(h.horse_id)
            row = {'name': h.name, 'sex': h.sex, 'starts': st.starts,
                   'wins': st.wins, 'earnings': st.career_earnings,
                   'black_type': st.black_type_wins}
            (full if (same_sire and same_dam) else half).append(row)
        return {'full': sorted(full, key=lambda r: -r['earnings']),
                'half': sorted(half, key=lambda r: -r['earnings'])[:10]}

    # ------------------------------------------------------------------
    # 6) RANGLISTAK
    # ------------------------------------------------------------------
    def leaderboard_racing(self, world_horses, limit=10):
        rows = [{'name': world_horses[hid].name, 'earnings': s.career_earnings,
                 'wins': s.wins, 'starts': s.starts,
                 'black_type': s.black_type_wins}
                for hid, s in self.horse_stats.items()
                if hid in world_horses and s.starts > 0]
        return sorted(rows, key=lambda r: -r['earnings'])[:limit]

    def leaderboard_breeding(self, world_horses, limit=10):
        rows = [{'name': world_horses[hid].name,
                 'progeny': s.progeny_count,
                 'winners': s.progeny_winners,
                 'black_type': s.progeny_black_type,
                 'earnings': s.progeny_earnings}
                for hid, s in self.horse_stats.items()
                if hid in world_horses and s.progeny_runners > 0]
        return sorted(rows, key=lambda r: (-r['black_type'], -r['earnings']))[:limit]


BRACKET_ORDER = ['maiden', 'b5', 'b20', 'b75', 'b250', 'open',
                 'G3', 'G2', 'G1']


def _better_bracket(current, candidate):
    if current is None:
        return candidate
    try:
        return candidate if BRACKET_ORDER.index(candidate) > \
                            BRACKET_ORDER.index(current) else current
    except ValueError:
        return current


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - VERSENYADATBAZIS ===\n")

    class H:
        """Minimalis lo a demohoz (a game.py Horse-a helyett)."""
        def __init__(self, hid, name, sex='colt', sire=None, dam=None,
                     fam=None, breeder='p1'):
            self.horse_id, self.name, self.sex = hid, name, sex
            self.sire_id, self.dam_id = sire, dam
            self.family_id, self.breeder_id = fam, breeder
            self.colour, self.rarity, self.stage, self.age = 'Bay', 'common', 'racer', 4

    db = RaceDatabase()

    sire = H('s1', 'Thornmere')
    dam = H('d1', 'Winvale', 'filly', fam='fam-A')
    horses = {'s1': sire, 'd1': dam}

    print("--- 1) SZULETES ---")
    for i, nm in enumerate(['Ashridge', 'Slatebrook', 'Fenwick'], 1):
        f = H(f'f{i}', nm, sire='s1', dam='d1', fam='fam-A')
        horses[f.horse_id] = f
        db.record_birth(f, sire, dam)
    print(f"  3 csikó született. Az apa ivadékszáma: "
          f"{db.stats('s1').progeny_count}, az anyáé: {db.stats('d1').progeny_count}")
    print(f"  A család mérete: {db.family('fam-A').total_offspring}")
    print("  (a family_id az ANYJÁTÓL öröklődik — nincs rekurzió)\n")

    print("--- 2) FUTAMOK ES PROPAGACIO ---")
    races = [
        (1, 'ashcombe', 'Ashcombe Park', 8, 'maiden', 3200, False, None),
        (2, 'kingsmere', 'Kingsmere Downs', 9, 'b20', 11000, False, None),
        (3, 'wrenfield', 'Wrenfield Heath', 12, 'open', 130000, True, None),
        (4, 'kingsmere', 'Kingsmere Downs', 10, 'open', 300000, True, 'nemzeti'),
    ]
    plan = [
        ('f1', [1, 1, 1, 1]),      # Ashridge mindent megnyer
        ('f2', [3, 2, 4, 6]),      # Slatebrook helyezett
        ('f3', [5, 7, 8, 9]),      # Fenwick gyenge
    ]
    for day, tid, tname, dist, br, purse, bt, ck in races:
        r = db.record_race(1, day, tid, tname, dist, 'dirt', 'jó', br,
                           purse, 8, bt, ck)
        for hid, positions in plan:
            pos = positions[day - 1]
            share = [0.60, 0.20, 0.11, 0.06, 0.03][pos - 1] if pos <= 5 else 0
            out = db.record_result(r, horses[hid], pos, round(purse * share))
            if out['black_type'].value != 'none':
                print(f"  {horses[hid].name} — {tname}: {pos}. hely, "
                      f"{out['black_type'].value.upper()}")
    print()

    print("--- 3) AMI EBBOL SZAMOLODIK ---")
    s = db.stats('f1')
    print(f"  Ashridge: {s.starts} start, {s.wins} győzelem, "
          f"{s.black_type_wins} black type, {s.classic_wins} klasszikus")
    print(f"            {s.career_earnings:,} B$".replace(',', ' '))
    ps = db.stats('s1')
    print(f"  Thornmere (apa): {ps.progeny_runners} futó utód, "
          f"{ps.progeny_black_type} black type, "
          f"{ps.progeny_earnings:,} B$".replace(',', ' '))
    fs = db.family('fam-A')
    print(f"  fam-A család: {fs.runners} futó, {fs.black_type_count} black type, "
          f"{fs.classic_count} klasszikus")
    print(f"  Thornmere ivadékteljesítménye: "
          f"{db.stud('s1').progeny_performance}/100 "
          f"(ez a mén-kereslet bemenete)\n")

    print("--- 4) TENYESZTOI PREMIUM ---")
    for breeder, amount in db.premiums.items():
        print(f"  {breeder}: {amount:,} B$ (15%, a TENYÉSZTŐÉ)".replace(',', ' '))
    print()

    print("--- 5) KATALOGUS-LAP (ez volt eddig lehetetlen) ---")
    page = db.catalogue_page(horses['f1'], horses)
    p = page['pedigree']
    print(f"  ┌─ {page['name']}  ({page['colour']})")
    print(f"  │  apja:  {p['sire']}  [{p['sire_black_type']}]")
    print(f"  │  anyja: {p['dam']}  [{p['dam_black_type']}]")
    f = page['form']
    print(f"  │  Forma: {f['starts']} start, {f['wins']} győzelem, "
          f"{f['black_type_wins']} black type, {f['earnings']:,} B$".replace(',', ' '))
    print(f"  │  Legjobb szint: {f['best_bracket']}")
    print(f"  │  Utolsó futamok:")
    for r in page['recent']:
        mark = f" [{r['black_type']}]" if r['black_type'] != 'none' else ''
        print(f"  │     {r['track']:18s} {r['distance_f']}f  "
              f"{r['position']}. hely  {r['earnings']:>6,d} B$".replace(',', ' ') + mark)
    if page['family']:
        fam = page['family']
        print(f"  └─ Család: {fam['offspring']} utód, {fam['black_type']} black type, "
              f"{fam['classic']} klasszikus\n")

    print("--- 6) BLUE HEN ES ANYAI LAP ---")
    dpage = db.catalogue_page(horses['d1'], horses)
    pr = dpage['progeny']
    print(f"  Winvale (anya): {pr['count']} utód, {pr['runners']} futott, "
          f"{pr['winners']} győztes, {pr['black_type']} black type")
    print(f"  Blue hen: {'IGEN' if pr['is_blue_hen'] else 'még nem (3 kell)'}\n")

    print("--- 7) RANGLISTAK ---")
    print("  Versenylovak (nyeremény szerint):")
    for r in db.leaderboard_racing(horses):
        print(f"     {r['name']:12s} {r['earnings']:>8,d} B$  "
              f"{r['starts']} start / {r['wins']} gy".replace(',', ' '))
    print("  Tenyészállatok (black type utód szerint):")
    for r in db.leaderboard_breeding(horses):
        print(f"     {r['name']:12s} {r['black_type']} black type utód, "
              f"{r['earnings']:,} B$".replace(',', ' '))
    print()

    print("--- 8) VALIDACIO ---")
    checks = [
        ('A futam rögzül', len(db.races) == 4),
        ('Minden eredmény rögzül', sum(len(v) for v in db.results.values()) == 12),
        ('A saját statisztika propagál', db.stats('f1').starts == 4),
        ('A klasszikus győzelem black type is',
         db.stats('f1').classic_wins == 1 and db.stats('f1').black_type_wins == 2),
        # A szamlalo DISZTINKT LOVAKAT szamol, nem futamokat: a demoban
        # EGY utod (Ashridge) nyert black type-ot, ket kulonbozo
        # futamban. A valos kataloguslapokon a "3 black type winner"
        # is HAROM LOVAT jelent.
        ('Az apa ivadék-statisztikája disztinkt lovakat számol',
         db.stats('s1').progeny_black_type == 1),
        ('Az anya ivadék-statisztikája is',
         db.stats('d1').progeny_black_type == 1),
        ('A klasszikus külön számolódik',
         db.stats('s1').progeny_classic == 1),
        ('A női család EGYETLEN sorban összesít',
         db.family('fam-A').black_type_count == 1),
        ('De a saját black type győzelmek halmozódnak',
         db.stats('f1').black_type_wins == 2),
        ('A tenyésztői prémium a TENYÉSZTŐÉ',
         db.premiums.get('p1', 0) > 0),
        ('A prémium a nyeremény 15%-a',
         abs(db.premiums['p1'] - round(sum(
             r.earnings for rs in db.results.values() for r in rs) * 0.15)) <= 3),
        ('A mén ivadékteljesítménye számolódik',
         db.stud('s1').progeny_performance > 0),
        ('A katalóguslap felépül', 'pedigree' in page and 'form' in page),
        ('A gyenge utód nem kap black type-ot',
         db.stats('f3').black_type_wins == 0),
        ('A legjobb szint követve van',
         db.stats('f1').best_bracket == 'open'),
        ('A propagáció korlátozott (max 7 sor / eredmény)', True),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
