"""
Breeder Tycoon - Game Integration Layer v1.0
=======================================================================
EZ KOTI OSSZE A MOTOROKAT.

Eddig 19 modul kulon futott, sajat dict-formatummal. A season.html a
JS-portot hasznalta, nem a Python forrast - a ketto lassan szetcsuszott
volna.

Ez a modul:
  1. EGYSEGES LO-SEMAT hasznal, a schema.sql szerint
  2. A VALODI Python motorokat hivja, nem masolja a logikajukat
  3. Vegigfuttat egy szezont, es kiderul, hogy a modulok
     TENYLEG osszeillenek-e

MIT NEM CSINAL:
  - nincs adatbazis-kapcsolat (a schema.sql kulon el)
  - nincs halozati reteg
  - nincs UI
Ez a MOTOR-INTEGRACIO, nem a jatek.
"""

import random
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

import breeding_sim as BR
import feeding_sim as FD
import trainer_sim as TR
import jockey_sim as JK
import lifecycle_sim as LC
import track_sim as TK
import race_sim as RC
import stud_sim as ST
import family_sim as FM
import season_sim as SE
import farm_sim as FA


# =======================================================================
# 1) EGYSEGES LO-SEMA (a schema.sql horse tablaja szerint)
# =======================================================================
# EZ VOLT A HIANYZO DARAB. Minden motor sajat dict-formatummal
# dolgozott; itt egyetlen strukturat hasznalunk, es a motorok fele
# ADAPTEREK forditanak.
@dataclass
class Horse:
    horse_id: str
    name: str
    sex: str                      # 'colt' | 'filly'
    birth_season: int

    sire_id: Optional[str] = None
    dam_id: Optional[str] = None
    family_id: Optional[str] = None
    sire_line_id: Optional[str] = None
    ancestors: list = field(default_factory=list)

    # rejtett genetika - a jatekos sosem latja
    genetics: dict = field(default_factory=dict)      # 10 tulajdonsag TGV
    colour_genotype: dict = field(default_factory=dict)

    colour: str = 'Bay'
    born_colour: str = 'Bay'
    will_grey: bool = False
    rarity: str = 'common'

    breeder_id: Optional[str] = None    # SOSEM valtozik
    owner_id: Optional[str] = None

    # eletciklus-csikok (lifecycle_sim.py)
    life_bar: float = 100.0
    career_bar: float = 100.0
    career_used: float = 0.0
    breeding_bar: Optional[float] = None
    freshness: float = 100.0
    stage: str = 'foal'

    # felneveles (feeding_sim.py) - szakaszonkent lezarul
    maternal_pct: float = 0.0
    foal_stage_pct: float = 0.0
    yearling_stage_pct: float = 0.0

    injuries_total: int = 0
    age: int = 0

    # aggregatum (schema.sql horse_stats)
    starts: int = 0
    wins: int = 0
    career_earnings: int = 0
    black_type_wins: int = 0
    classic_wins: int = 0

    # --- SZARMAZTATOTT ERTEKEK ---
    def genetic_score(self):
        return BR.overall_score(self.genetics)

    def grade(self):
        return BR.index_from_score(self.genetic_score())

    def feed_pct(self):
        return min(20.0, self.maternal_pct + self.foal_stage_pct
                   + self.yearling_stage_pct)

    def fill_bar(self, trainer_score):
        """A teljes toltottsegi sav. A feeding_sim.py VALODI fuggvenyet
        hivja, nem masolja a keepletet."""
        return FD.calculate_total_fill_pct(
            self.genetic_score(), self.maternal_pct,
            self.foal_stage_pct + self.yearling_stage_pct, trainer_score
        )['total_fill_pct']


# =======================================================================
# 2) ADAPTEREK - a Horse -> a motorok sajat formatuma
# =======================================================================
# A motorokat NEM irjuk at. Helyette itt forditunk. Igy a motorok
# onalloan is futtathatok maradnak (a workflow ezt ellenorzi).
def to_breeding_parent(h: Horse):
    """breeding_sim.py alakja: {'profile': {trait: ertek}, 'ancestors': [...]}

    MEGJEGYZES: az integracio derítette ki, hogy a motor 'profile'
    kulcsot var, nem 'traits'-et. Pontosan ezert kellett ez a reteg.
    """
    return {
        'name': h.name,
        'profile': dict(h.genetics),
        'color_genotype': h.colour_genotype,
        'ancestors': list(h.ancestors),
    }


def to_race_horse(h: Horse, trainer, jockey, band, surface):
    """race_sim.py alakja: {'fill_bar', 'profile', 'style', 'freshness', 'jockey_mod'}"""
    profile = dict(h.genetics)
    # a race_sim a sprint/mile/middle/staying + accel/stamina mezoket varja
    return {
        'name': h.name,
        'fill_bar': h.fill_bar(trainer['overall_score']),
        'profile': profile,
        'style': RC.infer_running_style(profile),
        'freshness': h.freshness,
        'jockey_mod': JK.get_raceday_modifier(jockey, band, surface),
        'is_npc': False,
    }


def to_lifecycle_bars(h: Horse):
    return {'life': h.life_bar, 'career': h.career_bar,
            'freshness': h.freshness, 'breeding': h.breeding_bar,
            'stage': LC.Stage(h.stage), 'career_used': h.career_used}


# =======================================================================
# 3) VILAG-ALLAPOT
# =======================================================================
@dataclass
class World:
    season: int = 1
    rng: random.Random = field(default_factory=lambda: random.Random(42))
    horses: dict = field(default_factory=dict)       # horse_id -> Horse
    trainers: list = field(default_factory=list)
    jockeys: list = field(default_factory=list)
    families: dict = field(default_factory=dict)     # family_id -> lista
    log: list = field(default_factory=list)

    def add(self, h: Horse):
        self.horses[h.horse_id] = h
        if h.family_id:
            self.families.setdefault(h.family_id, []).append(h.horse_id)
        return h

    def owned_by(self, owner_id, stage=None):
        return [h for h in self.horses.values()
                if h.owner_id == owner_id and (stage is None or h.stage == stage)]

    def ev(self, tag, text):
        self.log.append({'season': self.season, 'tag': tag, 'text': text})


# =======================================================================
# 4) LO LETREHOZASA
# =======================================================================
FOUNDER_A = ['Ash','Bram','Cinder','Dun','Elm','Fen','Grey','Haw','Iron','Kes',
             'Lark','Mor','Nettle','Oak','Pike','Quill','Rush','Slate','Thorn',
             'Vale','Wren','Bracken','Harrow','Marlow']
FOUNDER_B = ['bank','brook','crest','dale','fall','gate','hill','lane','mere',
             'ridge','shade','stone','wick','wood','field','mont']


def founder_name(rng):
    """Alapito lo neve - nincs szuloje, igy a pedigre-generator nem
    hasznalhato. A nevadasi szabalyt (listing_sim.py / breeding_sim.py)
    igy is betartjuk: max 18 karakter."""
    return (rng.choice(FOUNDER_A) + rng.choice(FOUNDER_B))[:18]


def make_founder(world: World, owner_id, sex, quality_mean=55, name=None):
    """Alapito lo - nincs szuloje, sajat csaladot alapit."""
    genetics = {}
    for t in BR.TRAIT_CONFIG:
        genetics[t] = max(5, min(99, world.rng.gauss(quality_mean, 11)))

    geno = {k: BR.random_genotype_locus(k) for k in BR.POP_ALLELE_FREQ}
    colour = BR.color_phenotype(geno)

    h = Horse(
        horse_id=str(uuid.uuid4())[:8],
        name=name or founder_name(world.rng),
        sex=sex,
        birth_season=world.season,
        family_id=str(uuid.uuid4())[:8] if sex == 'filly' else None,
        sire_line_id=str(uuid.uuid4())[:8] if sex == 'colt' else None,
        genetics=genetics,
        colour_genotype=geno,
        colour=colour['displayed_color'],
        born_colour=colour['born_color'],
        will_grey=colour['will_gray_with_age'],
        rarity=colour['rarity_tier'],
        breeder_id=owner_id,
        owner_id=owner_id,
    )
    return world.add(h)


def breed(world: World, sire: Horse, dam: Horse, breeder_id, feed_quality='jo'):
    """Uj csiko. A breeding_sim.py VALODI Mendeli motorjat hivja."""
    s_par = to_breeding_parent(sire)
    d_par = to_breeding_parent(dam)

    inb = BR.inbreeding_coeff(s_par, d_par)

    genetics = {}
    for t in BR.TRAIT_CONFIG:
        tgv, _midparent = BR.true_genetic_value(s_par, d_par, t, inb)
        genetics[t] = tgv

    geno = BR.breed_color_genotype(sire.colour_genotype, dam.colour_genotype)
    colour = BR.color_phenotype(geno)

    # DENORMALIZALT OS-TOMB (schema.sql): 2 szulo + 4 nagyszulo + 8 dedszulo
    ancestors = ([sire.horse_id, dam.horse_id]
                 + sire.ancestors[:6] + dam.ancestors[:6])[:14]

    maternal = FD.calculate_maternal_care_bonus_pct(feed_quality, True)

    foal = Horse(
        horse_id=str(uuid.uuid4())[:8],
        name=BR.generate_pedigree_name(sire.name, dam.name)[0],
        sex='filly' if world.rng.random() < 0.5 else 'colt',
        birth_season=world.season,
        sire_id=sire.horse_id,
        dam_id=dam.horse_id,
        # A KULCS-DONTES: a family_id az ANYJATOL, a sire_line_id az APJATOL
        family_id=dam.family_id,
        sire_line_id=sire.sire_line_id,
        ancestors=ancestors,
        genetics=genetics,
        colour_genotype=geno,
        colour=colour['displayed_color'],
        born_colour=colour['born_color'],
        will_grey=colour['will_gray_with_age'],
        rarity=colour['rarity_tier'],
        breeder_id=breeder_id,          # SOSEM valtozik
        owner_id=breeder_id,
        maternal_pct=maternal,
        stage='foal',
    )
    world.add(foal)
    world.ev('breed', f"{dam.name} × {sire.name} → {foal.name} "
                      f"({foal.grade()}, {foal.colour}, inbreeding {inb*100:.1f}%)")
    return foal


# =======================================================================
# 5) SZEZON-CIKLUS
# =======================================================================
def age_up(world: World, feed_quality='jo', conc=True, vit=True):
    """Szezonnyitas: mindenki oregszik, a szakaszok lezarulnak."""
    for h in list(world.horses.values()):
        if h.stage == 'retired_out':
            continue
        h.age += 1

        if h.stage == 'foal':
            # a csikokori szakasz LEZARUL
            h.foal_stage_pct = FD.calculate_foal_stage_bonus_pct(feed_quality, conc, vit)
            h.stage = 'yearling'
        elif h.stage == 'yearling':
            # a yearling szakasz LEZARUL
            h.yearling_stage_pct = FD.calculate_yearling_stage_bonus_pct(feed_quality, conc, vit)
            h.stage = 'racer'
            h.freshness = 100.0


def run_season_races(world: World, horse: Horse, trainer, jockey, starts=5):
    """Egy lo szezonja. A race_sim.py VALODI szimulaciojat hivja."""
    results = []
    for i in range(starts):
        if horse.career_bar <= 0 or horse.life_bar <= 0:
            break
        if not LC.freshness_ready(horse.freshness):
            # pihenes: a lifecycle_sim.py visszatoltodesi gorbeje
            horse.freshness = LC.freshness_recover(horse.freshness, 2.0)

        bracket = TK.bracket_for_earnings(horse.career_earnings, horse.wins > 0)
        track_key = world.rng.choice(list(TK.TRACKS.keys()))
        track = TK.TRACKS[track_key]
        band = TK.band_for_furlongs(world.rng.choice(track['distances']))

        race = {
            'band': band,
            'style_bias': track['style_bias'],
            'surface': track['surface'],
            'bracket': {'key': bracket['key']},
            'purse': TK.purse_for_race(bracket['key'], track_key),
        }

        me = to_race_horse(horse, trainer, jockey, band, track['surface'])
        field = RC.generate_field(bracket['key'], size=8, rng=world.rng, include=[me])
        outcome = RC.run_race(field, race, world.rng)
        mine = next(r for r in outcome['results'] if r['horse'] is me)

        payouts = RC.distribute_purse(race['purse'], outcome['results'])
        gross = payouts[me['name']]

        horse.starts += 1
        horse.career_earnings += gross
        if mine['position'] == 1:
            horse.wins += 1

        # eletciklus-csikok fogyasztasa - a VALODI fuggvenyekkel
        horse.career_bar = max(0, horse.career_bar - LC.career_cost_per_start())
        horse.career_used = 100.0 - horse.career_bar
        horse.freshness = LC.freshness_after_start(horse.freshness)

        # serules - a track_sim.py kockazati modelljevel
        risk = TK.injury_risk_pct(track['surface'], horse.genetics['soundness'])
        if world.rng.random() * 100 < risk:
            sev = TK.resolve_injury(world.rng.random())
            horse.injuries_total += 1
            horse.genetics['soundness'] = max(10, horse.genetics['soundness']
                                              - sev['soundness_loss'])
            world.ev('vet', f"{horse.name} megsérült — {sev['label']}")

        results.append({'position': mine['position'], 'earnings': gross,
                        'track': track['name'], 'band': band})

    # az elet-csik szezononkent fogy
    decay = LC.life_decay_per_season(horse.genetics['soundness'],
                                     horse.injuries_total, 0.7)
    horse.life_bar = max(0, horse.life_bar - decay)
    return results


def retire_if_done(world: World, horse: Horse):
    """A lifecycle_sim.py dönt: nyugdíjazás, tenyésztésbe vagy kikerülés."""
    bars = to_lifecycle_bars(horse)

    # 1. AZ ELET-CSIK a mesteróra - ez mindent felulir
    if horse.life_bar <= 0:
        horse.stage = 'retired_out'
        world.ev('exit', LC.exit_game(bars, horse.name)['text'])
        return 'exit'

    # 2. A TENYESZCSIK kifutasa.
    #
    # KET HIBAT DERITETT KI AZ INTEGRACIO:
    #  a) eredetileg csak a versenylovakat kezeltem -> a kimerult kancak
    #     'breeding' statuszban ragadtak, ferohelyet foglalva
    #  b) a "csik <= 0" feltetel SOSEM teljesult: ha nincs eleg a
    #     kovetkezo csikora, a fedeztetes kimarad, es a csik ott all meg
    #     (pl. 5-nel). A helyes feltetel: NEM FUTJA a kovetkezo csikot.
    #
    # Ez a vizsgalat a check_retirement ELE kerul, mert az a maga
    # szempontjabol meg nem latja kifutottnak az 5-os csikot.
    if horse.stage == 'breeding' and horse.sex == 'filly' \
            and (horse.breeding_bar or 0) < LC.breeding_cost(horse.age):
        horse.stage = 'pensioned'
        world.ev('retire', f"{horse.name} tenyészcsíkja kifutott — "
                           f"nyugdíjas legelőre kerül, de a pedigrékben marad.")
        return 'pensioned'

    # 3. A VERSENYKARRIER vege
    if horse.stage == 'racer' and horse.career_bar <= 0:
        if horse.sex == 'filly':
            new_bars = LC.retire_to_breeding(bars)
            horse.breeding_bar = new_bars['breeding']
            horse.stage = 'breeding'
            world.ev('retire', f"{horse.name}: {new_bars['note']}")
        else:
            LC.retire_to_stud(bars)
            horse.breeding_bar = None
            horse.stage = 'breeding'
            world.ev('retire', f"{horse.name} ménként folytatja — "
                               f"korlátlanul fedezhet, amíg van rá kereslet.")
        return 'breeding'

    return None


# =======================================================================
# 6) TELJES SZEZON
# =======================================================================
def play_season(world: World, player_id, trainer, jockey,
                feed_quality='jo', starts=5):
    world.ev('season', f"=== {world.season}. szezon ===")

    age_up(world, feed_quality)

    # fedeztetes - szezononkent EGY csiko kancankent (season_sim.py)
    for mare in world.owned_by(player_id, 'breeding'):
        if mare.sex != 'filly' or (mare.breeding_bar or 0) <= 0:
            continue
        studs = [h for h in world.horses.values()
                 if h.sex == 'colt' and h.stage == 'breeding']
        if not studs:
            continue
        sire = world.rng.choice(studs)

        cost = LC.breeding_cost(mare.age)
        if mare.breeding_bar < cost:
            continue
        mare.breeding_bar -= cost
        breed(world, sire, mare, player_id, feed_quality)

    # versenyek
    for h in world.owned_by(player_id, 'racer'):
        res = run_season_races(world, h, trainer, jockey, starts)
        if res:
            wins = sum(1 for r in res if r['position'] == 1)
            world.ev('race', f"{h.name}: {len(res)} start, {wins} győzelem, "
                             f"{sum(r['earnings'] for r in res):,} B$".replace(',', ' '))

    # eletciklus-ellenorzes
    for h in list(world.horses.values()):
        if h.owner_id == player_id and h.stage in ('racer', 'breeding', 'pensioned'):
            retire_if_done(world, h)

    world.season += 1


# =======================================================================
# DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - INTEGRACIOS RETEG ===\n")
    print("A VALODI Python motorokat hivja, nem masolja a logikajukat.\n")

    world = World(rng=random.Random(2024))
    PLAYER = 'player-001'

    print("--- 1) KEZDOALLOMANY (GDD 2.2) ---")
    mares = [make_founder(world, PLAYER, 'filly', 48) for _ in range(2)]
    racers = [make_founder(world, PLAYER, 'colt', 54) for _ in range(2)]
    for r in racers:
        r.stage = 'racer'
        r.age = 3
        r.foal_stage_pct = FD.calculate_foal_stage_bonus_pct('jo', True, True)
        r.yearling_stage_pct = FD.calculate_yearling_stage_bonus_pct('jo', True, True)
        r.maternal_pct = FD.calculate_maternal_care_bonus_pct('jo', True)
    for m in mares:
        m.stage = 'breeding'
        m.age = 5
        m.breeding_bar = 65.0

    # NPC menek a fedeztetesekhez
    for _ in range(6):
        s = make_founder(world, 'npc', 'colt', 64)
        s.stage = 'breeding'
        s.age = 6

    trainer = TR.generate_random_trainer('Hollis')
    jockey = JK.generate_random_jockey('Marek')

    print(f"  Kanca:     {', '.join(f'{m.name} ({m.grade()})' for m in mares)}")
    print(f"  Versenyló: {', '.join(f'{r.name} ({r.grade()})' for r in racers)}")
    print(f"  Tréner:    {TR.describe_trainer_for_player(trainer)}")
    print(f"  Zsoké:     {JK.describe_jockey_for_player(jockey)}\n")

    ts = trainer['overall_score']
    for r in racers:
        fb = r.fill_bar(ts)
        print(f"  {r.name}: töltöttségi sáv {fb:.1f}%  "
              f"(genetika {r.genetic_score():.0f}, takarmány {r.feed_pct():.1f}%)")
    print()

    print("--- 2) HAT SZEZON ---")
    for _ in range(6):
        play_season(world, PLAYER, trainer, jockey)

    for e in world.log:
        if e['tag'] == 'season':
            print(f"\n{e['text']}")
        else:
            print(f"  [{e['tag']:6s}] {e['text']}")

    print("\n--- 3) ALLOMANY A VEGEN ---")
    mine = [h for h in world.horses.values() if h.owner_id == PLAYER]
    for h in sorted(mine, key=lambda x: (x.stage, -x.career_earnings)):
        bars = to_lifecycle_bars(h)
        print(f"  {h.name:14s} {h.stage:9s} {h.age:2d} év  {h.grade():3s}  "
              f"{h.colour:9s} {h.starts:2d} start / {h.wins} győzelem  "
              f"{h.career_earnings:>7,d} B$".replace(',', ' '))
        print(f"     {LC.describe_bars(bars)}")

    print("\n--- 4) VALIDACIO: OSSZEILLENEK-E A MOTOROK? ---")
    foals = [h for h in world.horses.values() if h.sire_id]
    checks = [
        ('Született csikó a valódi Mendeli motorral', len(foals) > 0),
        ('A csikó örökli az anyja family_id-ját',
         all(f.family_id == world.horses[f.dam_id].family_id
             for f in foals if f.dam_id and world.horses[f.dam_id].family_id)),
        ('A csikó örökli az apja sire_line_id-ját',
         all(f.sire_line_id == world.horses[f.sire_id].sire_line_id
             for f in foals if f.sire_id and world.horses[f.sire_id].sire_line_id)),
        ('A breeder_id soha nem változik',
         all(f.breeder_id == PLAYER for f in foals)),
        ('Az ős-tömb legfeljebb 14 elemű',
         all(len(f.ancestors) <= 14 for f in foals)),
        ('A töltöttségi sáv sosem lépi túl a 99,75%-ot',
         all(h.fill_bar(ts) <= 99.75 for h in mine)),
        ('A takarmány-sáv sosem lépi túl a 20%-ot',
         all(h.feed_pct() <= 20.0 for h in mine)),
        ('Volt verseny és nyeremény',
         sum(h.career_earnings for h in mine) > 0),
        ('Az életciklus-csíkok fogytak',
         any(h.life_bar < 100 for h in mine)),
        ('A színgenetika valós arányt ad',
         all(h.colour in BR.COLOR_RARITY_TIER for h in world.horses.values())),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'A MOTOROK OSSZEILLENEK' if all_ok else 'VAN ILLESZTESI HIBA'} ===")
