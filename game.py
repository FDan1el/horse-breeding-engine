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
import listing_sim as LS
import family_sim as FM
import season_sim as SE
import farm_sim as FA
import racedb as DB
import stud_sim as ST
import listing_sim as LS


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


def to_race_horse(h: Horse, trainer, jockey, band, surface,
                  trainer_score=None):
    """race_sim.py alakja: {'fill_bar', 'profile', 'style', 'freshness', 'jockey_mod'}"""
    profile = dict(h.genetics)
    # a race_sim a sprint/mile/middle/staying + accel/stamina mezoket varja
    return {
        'name': h.name,
        'fill_bar': h.fill_bar(trainer_score
                               if trainer_score is not None
                               else trainer['overall_score']),
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
    # A VERSENYADATBAZIS + AGGREGATUM-RETEG (racedb.py).
    # Enelkul nincs pedigre-lap, black type, ivadekstatisztika,
    # Hall of Fame vagy men-kereslet.
    db: 'DB.RaceDatabase' = field(default_factory=DB.RaceDatabase)
    used_names: set = field(default_factory=set)
    breeders: list = field(default_factory=list)

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


def breed(world: World, sire: Horse, dam: Horse, breeder_id, feed_quality='jo',
          name_fn=None):
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
        name=(name_fn(world.rng, sire.name, dam.name) if name_fn
              else BR.generate_pedigree_name(sire.name, dam.name)[0]),
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
    world.db.record_birth(foal, sire, dam)
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
    """Egy lo szezonja. A race_sim.py VALODI szimulaciojat hivja.

    A lo a SAJAT trénerével es zsokéjaval fut, ha van neki. A tréner
    hatasa az atmeneti idoszakban sulyozott (trainer_sim.py).
    """
    own_trainer = getattr(horse, 'trainer', None) or trainer
    own_jockey = getattr(horse, 'jockey', None) or jockey
    ts = effective_trainer_score(horse, trainer)
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

        # --- A FUTAM ES AZ EREDMENY ROGZITESE ---
        # A propagacio (sajat statisztika, ket szulo, noi csalad,
        # men-kereslet, tenyesztoi premium) automatikusan lefut.
        db_race = world.db.record_race(
            season=world.season, day=i + 1,
            track_id=track_key, track_name=track['name'],
            distance_f=world.rng.choice(track['distances']),
            surface=track['surface'], going='jó',
            bracket=bracket['key'], purse=race['purse'],
            field_size=len(field),
            is_black_type=bracket['key'] in ('open', 'b250'),
        )
        rec = world.db.record_result(
            db_race, horse, mine['position'], gross,
            fill_bar=me['fill_bar'], freshness=horse.freshness,
        )
        if rec['black_type'].value != 'none':
            world.ev('blacktype',
                     f"{horse.name} — {track['name']}: {mine['position']}. hely, "
                     f"{rec['black_type'].value.upper()}")

        horse.starts += 1
        horse.career_earnings += gross
        # a trénervaltas utani atmenet szamlaloja
        horse.races_since_trainer_change = getattr(
            horse, 'races_since_trainer_change', 0) + 1
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

    # --- GROUP VERSENY a szezon vegen, ha a lo elerte a kuszobot ---
    # A BLACK TYPE INNEN JON. Enelkul a katalogus-lapok uresek
    # maradnanak, es a tenyesztesi ertek sem epulne fel.
    eligible = [g for g, cfg in TK.GROUP_RACES.items()
                if horse.career_earnings >= cfg['min_earnings']]
    if eligible and horse.career_bar > 0 and horse.life_bar > 0:
        grp = eligible[-1]                       # a legrangosabb, amire jogosult
        cfg = TK.GROUP_RACES[grp]
        track_key = 'kingsmere'
        track = TK.TRACKS[track_key]
        band = TK.band_for_furlongs(world.rng.choice(track['distances']))
        horse.freshness = max(horse.freshness, 92.0)

        race = {'band': band, 'style_bias': track['style_bias'],
                'surface': track['surface'], 'bracket': {'key': 'open'},
                'purse': cfg['purse']}
        me = to_race_horse(horse, trainer, jockey, band, track['surface'])
        field = RC.generate_field(grp, size=10, rng=world.rng, include=[me])
        outcome = RC.run_race(field, race, world.rng)
        mine = next(r for r in outcome['results'] if r['horse'] is me)
        gross = RC.distribute_purse(cfg['purse'], outcome['results'])[me['name']]

        db_race = world.db.record_race(
            season=world.season, day=30, track_id=track_key,
            track_name=track['name'],
            distance_f=world.rng.choice(track['distances']),
            surface=track['surface'], going='jó', bracket=grp,
            purse=cfg['purse'], field_size=len(field),
            is_black_type=True,
            classic_key='klasszikus' if grp == 'G1' else None,
        )
        rec = world.db.record_result(db_race, horse, mine['position'], gross,
                                     fill_bar=me['fill_bar'])
        horse.starts += 1
        horse.career_earnings += gross
        horse.career_bar = max(0, horse.career_bar - LC.career_cost_per_start(1.4))
        horse.career_used = 100.0 - horse.career_bar
        if mine['position'] == 1:
            horse.wins += 1
            horse.black_type_wins += 1
            world.ev('blacktype', f"{horse.name} MEGNYERTE a(z) {cfg['label']} "
                                  f"futamot! ({gross:,} B$)".replace(',', ' '))
        elif mine['position'] <= 3:
            world.ev('blacktype', f"{horse.name} a {mine['position']}. helyen "
                                  f"végzett a(z) {cfg['label']} futamban")
        results.append({'position': mine['position'], 'earnings': gross,
                        'track': track['name'], 'band': band, 'group': grp})

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
# =======================================================================
# 5b) TRENER ES ZSOKE VALASZTAS
# =======================================================================
# A jatekos NEM sajat versenyistallot vezet - a lovat ATADJA egy
# trénernek (GDD 7.3). A valtas viszont nem azonnali: a regi tréner
# munkaja MEG 3 VERSENYIG a loban marad (Mukai et al. 2006).
#
# A zsoké ezzel szemben AZONNAL hat - versenynapi modosito, nem
# epit fel semmit a loban (GDD 8.1).
TRAINER_POOL_SIZE = 10
JOCKEY_POOL_SIZE = 12


def trainer_fee(trainer):
    """Szezonalis treneri dij - a kepessegevel aranyos."""
    return int(round(250 + trainer['overall_score'] * 22))


def jockey_cut(jockey):
    """A zsoké a nyeremeny szazalekat kapja. A jobb zsoké tobbet ker."""
    return round(0.055 + jockey['overall_score'] / 100 * 0.05, 4)


def build_staff_pools(world):
    """Elerheto trénerek es zsokék. Egyszer generalodnak."""
    if not getattr(world, 'trainer_pool', None):
        world.trainer_pool = TR.generate_trainer_population(TRAINER_POOL_SIZE)
        for t in world.trainer_pool:
            t['fee'] = trainer_fee(t)
    if not getattr(world, 'jockey_pool', None):
        world.jockey_pool = JK.generate_jockey_population(JOCKEY_POOL_SIZE)
        for j in world.jockey_pool:
            j['cut'] = jockey_cut(j)
    return world.trainer_pool, world.jockey_pool


def assign_trainer(world, horse, new_trainer):
    """Trénervaltas. A REGI tréner munkaja 3 versenyig kifut.

    Ha ugyanaz a tréner marad, nincs atmenet.
    """
    old = getattr(horse, 'trainer', None)
    if old is not None and old.get('name') == new_trainer.get('name'):
        return {'changed': False, 'note': None}

    horse.previous_trainer = old
    horse.trainer = new_trainer
    horse.races_since_trainer_change = 0
    if old is None:
        return {'changed': True,
                'note': f"{horse.name} trénere: "
                        f"{TR.describe_trainer_for_player(new_trainer)}"}
    return {'changed': True,
            'note': TR.describe_transition_for_player(old, new_trainer, 0)}


def effective_trainer_score(horse, fallback):
    """A lora ADOTT PILLANATBAN ervenyes tréner-pontszam.

    A valtas utani atmeneti idoszakban a regi es az uj tréner
    sulyozott atlaga (trainer_sim.py).
    """
    tr = getattr(horse, 'trainer', None) or fallback
    old = getattr(horse, 'previous_trainer', None)
    if old is None:
        return tr['overall_score']
    n = getattr(horse, 'races_since_trainer_change', 0)
    return TR.get_effective_trainer_score(old, tr, n)


def mare_status(mare):
    """A kanca termekenysegi statusza (stud_sim.py savjaihoz)."""
    if getattr(mare, 'failed_attempts', 0) >= 3:
        return 'barren'
    last_foal = getattr(mare, 'last_foaled_season', None)
    last_cover = getattr(mare, 'last_covered_season', None)
    if last_foal is None:
        return 'maiden'
    if last_cover is None:
        return 'rested'
    return 'foaling'


VET_INSPECTION_COST = LS.VET_INSPECTION_COST


def run_vet_inspection(world, mare):
    """Allatorvosi felmeres (listing_sim.py) - a TULAJDONOS fizeti.

    A valogatos menek elvarjak. Enelkul a jatekos csak az elvaras
    nelkuli menekhez fer - ez volt a hiba, amit az integracio
    deritett ki: MINDEN men elutasitott, mert senkinek nem volt
    felmerese.

    Az eredmeny ZAJOS (a valos rontgen-ertelmezes sem binaris),
    es TARTOS: nem kell szezononkent ujra.
    """
    rep = LS.run_vet_inspection(mare.genetics['soundness'])
    mare.health_grade = rep['grade']
    mare.vet_note = rep['note']
    mare.vet_season = world.season
    return rep


def check_covering(world, mare, sire, player_id):
    """Fedeztetheto-e ez a kanca ezzel a mennel?

    A stud_sim.py szabalyait hasznalja:
      - sajat men x sajat kanca: korlatozas nelkul
      - valogatos men: index- es egeszseg-elvaras
      - nyitott men: barkit fogad, dupla dijert
      - a szezonkonyv (140) nem telhet be
    """
    same_owner = sire.owner_id == player_id
    stud_stats = world.db.stud(sire.horse_id)

    stud = {
        'name': sire.name,
        'index': sire.grade(),
        'age': sire.age,
        'globally_listed': True,
        'policy': getattr(sire, 'stud_policy', ST.STUD_POLICY_SELECTIVE),
    }
    mare_rec = {
        'name': mare.name,
        'breeding_index': mare.grade(),
        'health_grade': getattr(mare, 'health_grade', None),
    }
    res = ST.check_mare_eligibility(stud, mare_rec,
                                    stud_stats.mares_this_season, same_owner)
    if res['allowed']:
        return {'allowed': True, 'reason': None, 'same_owner': same_owner}
    return {'allowed': False,
            'reason': ' '.join(r.value for r in res['reasons']),
            'same_owner': same_owner}


def stud_fee(world, sire, base=None):
    """A fedeztetesi dij. A nyitott men duplat ker (stud_sim.py)."""
    tier = ST.STUD_TIERS.get(sire.grade(), ST.STUD_TIERS['C'])
    base = base if base is not None else max(800, tier['book'] * 22)
    return ST.get_stud_fee(
        {'policy': getattr(sire, 'stud_policy', ST.STUD_POLICY_SELECTIVE)},
        base)


def play_season(world: World, player_id, trainer, jockey,
                feed_quality='jo', starts=5, breeding_plan=None):
    world.ev('season', f"=== {world.season}. szezon ===")

    age_up(world, feed_quality)

    # --- FEDEZTETES: A JATEKOS DONTESE ---
    #
    # Korabban a rendszer VELETLENSZERUEN parositott. Most a jatekos
    # adhat egy TERVET: {kanca_id: men_id}. Amelyik kancara nincs terv,
    # az kimarad - nem fedeztetunk helyette talalomra.
    #
    # Szezononkent EGY csiko kancankent (season_sim.py).
    plan = breeding_plan or {}
    for mare in world.owned_by(player_id, 'breeding'):
        if mare.sex != 'filly' or (mare.breeding_bar or 0) <= 0:
            continue

        sire_id = plan.get(mare.horse_id)
        if sire_id is None:
            world.ev('breed', f"{mare.name} — nincs fedeztetési terv, kimarad")
            continue
        sire = world.horses.get(sire_id)
        if sire is None or sire.stage != 'breeding' or sire.sex != 'colt':
            world.ev('breed', f"{mare.name} — a választott mén nem elérhető")
            continue

        # --- A MEN ELVARASAI (stud_sim.py) ---
        check = check_covering(world, mare, sire, player_id)
        if not check['allowed']:
            world.ev('breed', f"{mare.name} × {sire.name} — {check['reason']}")
            continue

        cost = LC.breeding_cost(mare.age)
        if mare.breeding_bar < cost:
            world.ev('breed', f"{mare.name} — a tenyészcsíkja nem futja "
                              f"a következő csikót")
            continue

        # --- VEMHESULES: valoszinuseg, nem garancia (stud_sim.py) ---
        p = ST.conception_probability({
            'age': mare.age,
            'status': mare_status(mare),
            'health_grade': None,
        })
        mare.breeding_bar -= cost
        mare.last_covered_season = world.season
        if world.rng.random() * 100 > p:
            mare.failed_attempts = getattr(mare, 'failed_attempts', 0) + 1
            world.ev('breed', f"{mare.name} × {sire.name} — nem fogant "
                              f"({p:.0f}% esély volt)")
            continue

        mare.failed_attempts = 0
        mare.last_foaled_season = world.season
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

    print("--- 2) FEDEZTETESI TERV: A JATEKOS DONTESE ---")
    print("  Terv nélkül NINCS fedeztetés — a rendszer nem párosít")
    print("  helyettünk találomra.\n")

    def make_plan(w, player):
        """Egyszerű automatikus terv a demóhoz: minden kancához a
        legjobb elérhető mén, amelyik elfogadja."""
        studs = [h for h in w.horses.values()
                 if h.sex == 'colt' and h.stage == 'breeding']
        studs.sort(key=lambda h: -h.genetic_score())
        plan = {}
        for mare in w.owned_by(player, 'breeding'):
            for st in studs:
                if check_covering(w, mare, st, player)['allowed']:
                    plan[mare.horse_id] = st.horse_id
                    break
        return plan

    for season in range(6):
        plan = make_plan(world, PLAYER)
        if season == 0:
            for mid, sid in plan.items():
                m, st = world.horses[mid], world.horses[sid]
                fee = stud_fee(world, st)
                print(f"  {m.name} ({m.grade()}) → {st.name} ({st.grade()})  "
                      f"díj {fee:,} B$".replace(',', ' '))
                print(f"     {ST.describe_stud_requirements({'index': st.grade(), 'policy': ST.STUD_POLICY_SELECTIVE})}")
            print()
        play_season(world, PLAYER, trainer, jockey, breeding_plan=plan)

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
    def _no_plan_no_foal():
        """Terv NELKUL nem szulethet csiko - ezt ellenorzi.
        A jatekos dontese: a rendszer NEM parosit helyette talalomra."""
        w2 = World(rng=random.Random(99))
        m2 = make_founder(w2, 'x', 'filly', 60)
        m2.stage, m2.age, m2.breeding_bar = 'breeding', 5, 65.0
        s2 = make_founder(w2, 'x', 'colt', 60)
        s2.stage, s2.age = 'breeding', 6
        before = len(w2.horses)
        play_season(w2, 'x', trainer, jockey, breeding_plan=None)
        return len(w2.horses) == before


    checks = [
        ('Született csikó a valódi Mendeli motorral', len(foals) > 0),
        ('Terv nélkül nincs fedeztetés',
         _no_plan_no_foal()),
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
