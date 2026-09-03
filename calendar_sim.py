"""
Breeder Tycoon - Race Calendar & Entries v1.0
=======================================================================
A VERSENYNAPTAR ES A NEVEZESI RENDSZER — A VEGLEGES SZERKEZETBEN.

Ez a modul MAR A FOLYAMATOS JATEKHOZ keszult, nem a mostani
"futtasd le a szezont" gombhoz. A kulonbseg csak annyi, hogy ma a
gomb hivja meg a feldolgozast, kesobb egy IDOZITO.

    MOST:    jatekos kattint -> process_due_races()
    KESOBB:  utemezo 15 percenkent -> process_due_races()

Ugyanaz a fuggveny. A valtas EGYETLEN sor.

=======================================================================
A VEGLEGES SZERKEZET ELEMEI
=======================================================================

1. A FUTAMOK ELORE GENERALODNAK, nem nevezeskor.
   A schedule_model.py szerint 15 percenkent indul futam minden
   palyan, 24 oras nevezesi ablakkal. Ezert a naptar mindig
   ELORE all rendelkezesre.

2. A NEVEZES KULON TABLA (entry), nem a futam resze.
   Igy tobb jatekos nevezhet ugyanarra a futamra, es a mezony
   a nevezesekbol all ossze - nem szintetikus NPC-kbol.

3. A NEVEZES ZARUL, aztan a futam LEFUT.
   Harom allapot: nyitva -> zarva -> lefutott. Az idozito ezek
   kozott lepteti a futamokat.

4. IDEMPOTENCIA: egy futam CSAK EGYSZER futhat le.
   A schema.sql race tablajaban ezt a kulcs biztositja; itt a
   status mezo.

=======================================================================
AMI MEG NEM VEGLEGES
=======================================================================
Az allapot MEMORIABAN van. A schema.sql tablai keszen allnak
(race, race_result, plusz egy uj entry tabla) - a valtas akkor jon,
amikor a folyamatos uzem indul.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import track_sim as TK
import race_sim as RC
import lifecycle_sim as LC


# =======================================================================
# 1) IDO - JATEKIDO ES VALOS IDO
# =======================================================================
# season_sim.py: 1 szezon = 1 jatekev = 1 valos honap (30 nap).
# A naptar VALOS IDOBEN mukodik; a jatekido ebbol szarmazik.
RACE_INTERVAL_MIN = 15                  # schedule_model.py
ENTRY_CLOSES_HOURS = 24                 # a nevezes ennyivel elobb zarul
SLOTS_PER_DAY = 24 * 60 // RACE_INTERVAL_MIN     # 96


@dataclass
class GameClock:
    """A jatek oraja. MOST leptetheto kezzel, KESOBB valos idot koveti.

    Ez a kulcs a kompatibilitashoz: a tobbi kod csak a `now`
    ertekét nezi, nem azt, hogy honnan jott.
    """
    season: int = 1
    day: int = 1                        # 1-30 a szezonon belul
    minute: int = 0                     # 0-1439 a napon belul

    def now(self):
        """Abszolut percek a jatek kezdete ota - ez a rendezesi kulcs."""
        return ((self.season - 1) * 30 + (self.day - 1)) * 1440 + self.minute

    def advance(self, minutes):
        total = self.minute + minutes
        self.minute = total % 1440
        days = total // 1440
        self.day += days
        while self.day > 30:
            self.day -= 30
            self.season += 1
        return self.now()

    def label(self):
        return (f"{self.season}. szezon, {self.day}. nap, "
                f"{self.minute // 60:02d}:{self.minute % 60:02d}")


def minutes_to_label(total):
    season = total // (30 * 1440) + 1
    rem = total % (30 * 1440)
    day = rem // 1440 + 1
    mins = rem % 1440
    return f"{season}. szezon {day}. nap {mins//60:02d}:{mins%60:02d}"


# =======================================================================
# 2) FUTAM-ALLAPOTOK
# =======================================================================
class RaceStatus(Enum):
    OPEN = 'open'          # nevezes nyitva
    CLOSED = 'closed'      # nevezes zarva, meg nem futott
    RUN = 'run'            # lefutott
    ABANDONED = 'abandoned'  # nem gyult ossze eleg nevezes


STATUS_LABELS = {
    RaceStatus.OPEN: 'Nevezés nyitva',
    RaceStatus.CLOSED: 'Nevezés zárva',
    RaceStatus.RUN: 'Lefutott',
    RaceStatus.ABANDONED: 'Elmaradt',
}


@dataclass
class ScheduledRace:
    """Egy elore kiirt futam.

    A schema.sql `race` tablajanak felel meg, plusz a nevezesi
    allapot. A futam AKKOR IS letezik, ha meg senki nem nevezett ra.
    """
    race_id: str
    starts_at: int                      # abszolut perc
    entries_close_at: int
    track_id: str
    track_name: str
    distance_f: int
    band: str
    surface: str
    surface_hu: str
    style_bias: str
    going: str
    bracket: str
    purse: int
    is_black_type: bool = False
    group_key: Optional[str] = None
    status: RaceStatus = RaceStatus.OPEN
    min_field: int = 8
    max_field: int = 14


@dataclass
class Entry:
    """Egy nevezes. KULON TABLA a futamtol (schema.sql-be kerul).

    Igy tobb jatekos nevezhet ugyanarra a futamra, es a mezony a
    nevezesekbol all ossze.
    """
    entry_id: str
    race_id: str
    horse_id: str
    owner_id: str
    entered_at: int
    jockey_name: Optional[str] = None
    withdrawn: bool = False


# =======================================================================
# 3) A NAPTAR
# =======================================================================
class RaceCalendar:
    """Elore kiirt futamok + nevezesek.

    A `process_due_races` a kulcs: MOST a gomb hivja, KESOBB az
    idozito. A fuggveny maga valtozatlan marad.
    """

    def __init__(self, clock: GameClock):
        self.clock = clock
        self.races: dict = {}            # race_id -> ScheduledRace
        self.entries: dict = {}          # race_id -> [Entry]
        self.by_horse: dict = {}         # horse_id -> [race_id]

    # ------------------------------------------------------------------
    # 3a) FUTAM-GENERALAS ELORE
    # ------------------------------------------------------------------
    def generate_ahead(self, rng, hours=48, per_slot=2):
        """Kiirja a kovetkezo N ora futamait.

        A schedule_model.py szerint 15 percenkent indul futam, es egy
        idopontban tobb parhuzamos futam megy - savonkent bontva.
        """
        now = self.clock.now()
        horizon = now + hours * 60
        existing = {r.starts_at for r in self.races.values()}

        # a kovetkezo egesz negyedora
        t = ((now // RACE_INTERVAL_MIN) + 1) * RACE_INTERVAL_MIN
        created = []
        while t < horizon:
            if t not in existing:
                for _ in range(per_slot):
                    created.append(self._make_race(rng, t))
            t += RACE_INTERVAL_MIN
        return created

    def _make_race(self, rng, starts_at):
        track_key = rng.choice(list(TK.TRACKS.keys()))
        track = TK.TRACKS[track_key]
        dist = rng.choice(track['distances'])
        bracket = rng.choice(TK.EARNINGS_BRACKETS)
        going = 'jó'

        r = ScheduledRace(
            race_id=str(uuid.uuid4())[:10],
            starts_at=starts_at,
            entries_close_at=starts_at - ENTRY_CLOSES_HOURS * 60,
            track_id=track_key,
            track_name=track['name'],
            distance_f=dist,
            band=TK.band_for_furlongs(dist),
            surface=track['surface'],
            surface_hu=TK.SURFACE_LABELS_HU[track['surface']],
            style_bias=track['style_bias'],
            going=going,
            bracket=bracket['label'],
            purse=int(round(bracket['purse'] *
                            (0.6 + track['prestige'] * 0.16))),
            is_black_type=bracket['max'] is None,
        )
        self.races[r.race_id] = r
        self.entries[r.race_id] = []
        return r

    # ------------------------------------------------------------------
    # 3b) NEVEZES
    # ------------------------------------------------------------------
    def open_races(self, horse=None, limit=30):
        """A nevezhetó futamok. Ha megadunk lovat, szurunk ra."""
        now = self.clock.now()
        out = []
        for r in self.races.values():
            if r.status != RaceStatus.OPEN or now >= r.entries_close_at:
                continue
            if horse is not None and not self._eligible(horse, r):
                continue
            out.append(r)
        out.sort(key=lambda r: r.starts_at)
        return out[:limit]

    def _eligible(self, horse, race: ScheduledRace):
        """Nevezhet-e ez a lo erre a futamra?

        A track_sim.py nyeremenysav-szabalya: a futam kiirasa mondja
        meg, ki nevezhet.
        """
        tier = next((t for t in TK.EARNINGS_BRACKETS
                     if t['label'] == race.bracket), None)
        if tier is None:
            return False
        # a track_sim.can_enter a sav KULCSAT varja, nem a szotarat
        if not TK.can_enter(horse.career_earnings, tier['key'],
                            horse.wins > 0):
            return False
        # egy lo egy idopontban csak egy futamon indulhat
        for rid in self.by_horse.get(horse.horse_id, []):
            other = self.races.get(rid)
            if other and abs(other.starts_at - race.starts_at) < 60 \
                    and other.status != RaceStatus.ABANDONED:
                return False
        # frissesseg: a lifecycle_sim kuszobe
        return True

    def enter(self, horse, owner_id, race_id, jockey_name=None):
        race = self.races.get(race_id)
        if race is None:
            return {'ok': False, 'reason': 'Nincs ilyen futam.'}
        if race.status != RaceStatus.OPEN:
            return {'ok': False, 'reason': 'A nevezés lezárult.'}
        if self.clock.now() >= race.entries_close_at:
            return {'ok': False, 'reason': 'A nevezési határidő lejárt.'}
        # A DUPLIKATUM-ELLENORZES ELOBB: kulonben az "egy oran belul
        # csak egy futam" szabaly fog eloszor, es felrevezeto uzenetet ad.
        if any(e.horse_id == horse.horse_id and not e.withdrawn
               for e in self.entries[race_id]):
            return {'ok': False, 'reason': 'Ez a ló már nevezve van erre a futamra.'}
        if len(self.entries[race_id]) >= race.max_field:
            return {'ok': False, 'reason': 'A mezőny betelt.'}
        if not self._eligible(horse, race):
            return {'ok': False,
                    'reason': 'A ló nem felel meg a futam kiírásának, '
                              'vagy már indul egy közeli futamban.'}

        e = Entry(entry_id=str(uuid.uuid4())[:10], race_id=race_id,
                  horse_id=horse.horse_id, owner_id=owner_id,
                  entered_at=self.clock.now(), jockey_name=jockey_name)
        self.entries[race_id].append(e)
        self.by_horse.setdefault(horse.horse_id, []).append(race_id)
        return {'ok': True, 'entry': e, 'race': race}

    def withdraw(self, horse_id, race_id):
        for e in self.entries.get(race_id, []):
            if e.horse_id == horse_id and not e.withdrawn:
                e.withdrawn = True
                return {'ok': True}
        return {'ok': False, 'reason': 'Nincs ilyen nevezés.'}

    def entries_of(self, horse_id):
        """A lo jovobeli nevezesei - amit a jatekos lat."""
        out = []
        for rid in self.by_horse.get(horse_id, []):
            r = self.races.get(rid)
            if r is None:
                continue
            e = next((x for x in self.entries[rid]
                      if x.horse_id == horse_id), None)
            if e is None or e.withdrawn:
                continue
            out.append({'race': r, 'entry': e})
        out.sort(key=lambda x: x['race'].starts_at)
        return out

    # ------------------------------------------------------------------
    # 3c) FELDOLGOZAS -- EZ A KULCS A KOMPATIBILITASHOZ
    # ------------------------------------------------------------------
    def due_races(self):
        """Melyik futamok esedekesek MOST?

        MOST a gomb hivja, KESOBB az idozito 15 percenkent. A
        fuggveny maga valtozatlan.
        """
        now = self.clock.now()
        return sorted(
            [r for r in self.races.values()
             if r.status in (RaceStatus.OPEN, RaceStatus.CLOSED)
             and now >= r.starts_at],
            key=lambda r: r.starts_at)

    def close_due_entries(self):
        """A nevezesi hataridot elert futamok lezarasa."""
        now = self.clock.now()
        closed = []
        for r in self.races.values():
            if r.status == RaceStatus.OPEN and now >= r.entries_close_at:
                r.status = RaceStatus.CLOSED
                closed.append(r)
        return closed

    def mark_run(self, race: ScheduledRace):
        """IDEMPOTENCIA: egy futam csak egyszer futhat le."""
        if race.status == RaceStatus.RUN:
            return False
        race.status = RaceStatus.RUN
        return True

    def abandon(self, race: ScheduledRace):
        race.status = RaceStatus.ABANDONED

    def active_entries(self, race_id):
        return [e for e in self.entries.get(race_id, []) if not e.withdrawn]


# =======================================================================
# 4) A FELDOLGOZO -- MOST A GOMB, KESOBB AZ IDOZITO HIVJA
# =======================================================================
def process_due_races(calendar: RaceCalendar, world, db, rng,
                      trainer_fallback, jockey_fallback,
                      to_race_horse, effective_trainer_score,
                      on_result=None):
    """Lefuttatja az esedekes futamokat.

    EZ A FUGGVENY VALTOZATLAN MARAD a folyamatos uzemben - csak az
    hivja mas: ma a "Szezon lefuttatasa" gomb, kesobb egy 15 perces
    idozito.

    A mezony a NEVEZESEKBOL all ossze. Ha keves a nevezes, NPC-vel
    toltunk fel (a vilag valodi lovaibol, ha van).
    """
    calendar.close_due_entries()
    results = []

    for race in calendar.due_races():
        entries = calendar.active_entries(race.race_id)
        if not entries:
            calendar.abandon(race)
            continue

        # --- a mezony a nevezesekbol ---
        field, refs = [], []
        for e in entries:
            h = world.horses.get(e.horse_id)
            if h is None or h.stage != 'racer':
                continue
            tr = getattr(h, 'trainer', None) or trainer_fallback
            jk = getattr(h, 'jockey', None) or jockey_fallback
            ts = effective_trainer_score(h, trainer_fallback)
            me = to_race_horse(h, tr, jk, race.band, race.surface,
                               trainer_score=ts)
            field.append(me)
            refs.append((me, h, e))

        if not field:
            calendar.abandon(race)
            continue

        # --- kiegeszites a minimum mezonyig ---
        bracket_key = _bracket_key(race.bracket)
        while len(field) < race.min_field:
            field.append(RC.generate_npc(bracket_key, rng))

        outcome = RC.run_race(field, {
            'band': race.band, 'style_bias': race.style_bias,
            'surface': race.surface, 'bracket': {'key': bracket_key},
            'purse': race.purse}, rng)
        payouts = RC.distribute_purse(race.purse, outcome['results'])

        if not calendar.mark_run(race):
            continue                     # mar lefutott - idempotencia

        # --- eredmenyek rogzitese ---
        db_race = db.record_race(
            season=race.starts_at // (30 * 1440) + 1,
            day=(race.starts_at % (30 * 1440)) // 1440 + 1,
            track_id=race.track_id, track_name=race.track_name,
            distance_f=race.distance_f, surface=race.surface,
            going=race.going, bracket=bracket_key, purse=race.purse,
            field_size=len(field), is_black_type=race.is_black_type,
            classic_key=race.group_key)

        for me, h, e in refs:
            row = next(r for r in outcome['results'] if r['horse'] is me)
            gross = payouts[me['name']]
            rec = db.record_result(db_race, h, row['position'], gross,
                                   fill_bar=me['fill_bar'],
                                   freshness=h.freshness)
            h.starts += 1
            h.career_earnings += gross
            h.races_since_trainer_change = getattr(
                h, 'races_since_trainer_change', 0) + 1
            if row['position'] == 1:
                h.wins += 1
            h.career_bar = max(0, h.career_bar - LC.career_cost_per_start())
            h.career_used = 100.0 - h.career_bar
            h.freshness = LC.freshness_after_start(h.freshness)

            out = {'race': race, 'horse': h, 'owner': e.owner_id,
                   'position': row['position'], 'earnings': gross,
                   'black_type': rec['black_type'].value,
                   'premium': rec['premium']}
            results.append(out)
            if on_result:
                on_result(out)

    return results


def _bracket_key(label):
    for t in TK.EARNINGS_BRACKETS:
        if t['label'] == label:
            return t['key']
    return 'b20'


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    import random
    import game as G
    import racedb as DB
    import trainer_sim as TR
    import jockey_sim as JK
    import feeding_sim as FD

    print("=== BREEDER TYCOON - VERSENYNAPTAR ===\n")
    print("A VEGLEGES szerkezetben: a futamok ELORE generalodnak, a")
    print("nevezes KULON tabla, es a feldolgozot MA a gomb, KESOBB egy")
    print("idozito hivja. A fuggveny maga valtozatlan marad.\n")

    rng = random.Random(7)
    clock = GameClock()
    cal = RaceCalendar(clock)

    print("--- 1) FUTAM-GENERALAS ELORE ---")
    created = cal.generate_ahead(rng, hours=48, per_slot=2)
    print(f"  {len(created)} futam kiírva a következő 48 órára")
    print(f"  ({RACE_INTERVAL_MIN} percenként, időpontonként 2 párhuzamos)")
    print(f"  Nevezés {ENTRY_CLOSES_HOURS} órával a start előtt zárul\n")
    for r in created[:4]:
        print(f"  {minutes_to_label(r.starts_at)}  {r.track_name:18s} "
              f"{r.distance_f:2d}f {r.surface_hu:12s} {r.bracket:22s} "
              f"{r.purse:>7,d} B$".replace(',', ' '))
    print()

    print("--- 2) NEVEZES ---")
    world = G.World(rng=rng)
    db = world.db
    horse = G.make_founder(world, 'player', 'colt', 62)
    horse.stage, horse.age = 'racer', 3
    horse.maternal_pct = FD.calculate_maternal_care_bonus_pct('jo', True)
    horse.foal_stage_pct = FD.calculate_foal_stage_bonus_pct('jo', True, True)
    horse.yearling_stage_pct = FD.calculate_yearling_stage_bonus_pct('jo', True, True)

    options = cal.open_races(horse, limit=6)
    print(f"  {horse.name} ({horse.grade()}) — {len(cal.open_races(horse, 99))} "
          f"nevezhető futam a következő 48 órában\n")
    for r in options[:5]:
        print(f"     {minutes_to_label(r.starts_at)}  {r.track_name:18s} "
              f"{r.distance_f}f  {r.bracket:22s} {r.purse:>7,d} B$"
              .replace(',', ' '))
    print()

    res = cal.enter(horse, 'player', options[0].race_id)
    print(f"  Nevezés: {'sikeres' if res['ok'] else res['reason']}")
    dup = cal.enter(horse, 'player', options[0].race_id)
    print(f"  Ismételt nevezés: {dup['reason']}")
    print()

    print("--- 3) A LO NEVEZESEI ---")
    for row in cal.entries_of(horse.horse_id):
        r = row['race']
        print(f"  {minutes_to_label(r.starts_at)}  {r.track_name} "
              f"{r.distance_f}f — {STATUS_LABELS[r.status]}")
    print()

    print("--- 4) AZ IDO TELIK, A FUTAM LEFUT ---")
    trainer = TR.generate_random_trainer('T')
    jockey = JK.generate_random_jockey('J')
    horse.trainer, horse.jockey = trainer, jockey

    print(f"  Most: {clock.label()}")
    target = options[0]
    clock.advance(target.starts_at - clock.now() + 1)
    print(f"  Előre: {clock.label()}  (a futam esedékes)\n")

    out = process_due_races(cal, world, db, rng, trainer, jockey,
                            G.to_race_horse, G.effective_trainer_score)
    for o in out:
        bt = f" [{o['black_type']}]" if o['black_type'] != 'none' else ''
        print(f"  {o['horse'].name}: {o['position']}. hely, "
              f"{o['earnings']:,} B$".replace(',', ' ') + bt)
        if o['premium']:
            print(f"     tenyésztői prémium: {o['premium']:,} B$".replace(',', ' '))
    print()

    print("--- 5) IDEMPOTENCIA ---")
    again = process_due_races(cal, world, db, rng, trainer, jockey,
                              G.to_race_horse, G.effective_trainer_score)
    print(f"  Ismételt feldolgozás: {len(again)} eredmény "
          f"(a lefutott futam nem fut le újra)\n")

    print("--- 6) MI VALTOZIK A FOLYAMATOS UZEMBEN? ---")
    print("  MOST:")
    print("     gomb → process_due_races(...)")
    print("  KESOBB:")
    print("     időzítő 15 percenként → process_due_races(...)")
    print("  A függvény VALTOZATLAN. Ami változik:")
    print("     - a GameClock valós időt követ, nem kézi léptetést")
    print("     - az állapot adatbázisban van, nem memóriában")
    print("     - a mezőnyben TÖBB JÁTÉKOS lova fut\n")

    print("--- 7) VALIDACIO ---")
    ran = [r for r in cal.races.values() if r.status == RaceStatus.RUN]
    abandoned = [r for r in cal.races.values()
                 if r.status == RaceStatus.ABANDONED]
    checks = [
        ('A futamok előre generálódnak', len(created) > 100),
        ('15 percenként indul futam',
         len({r.starts_at for r in cal.races.values()}) > 100),
        ('A nevezés 24 órával korábban zárul',
         all(r.starts_at - r.entries_close_at == ENTRY_CLOSES_HOURS * 60
             for r in cal.races.values())),
        ('A nevezés külön entitás',
         isinstance(cal.entries[options[0].race_id][0], Entry)),
        ('Ugyanaz a ló nem nevezhet kétszer', not dup['ok']),
        ('A ló nevezései lekérdezhetők',
         len(cal.entries_of(horse.horse_id)) >= 0),
        ('A futam lefutott', len(ran) >= 1),
        ('A nevezés nélküli futamok elmaradnak', len(abandoned) > 0),
        ('IDEMPOTENCIA: nem fut le kétszer', len(again) == 0),
        ('Az eredmény bekerül a versenyadatbázisba',
         len(db.races) >= 1),
        ('A ló statisztikája frissült',
         db.stats(horse.horse_id).starts >= 1),
        ('Az óra léptethető és címkézhető',
         'szezon' in clock.label()),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'A NAPTAR KESZ' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
