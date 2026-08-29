"""
Breeder Tycoon - World Generator v1.0
=======================================================================
AZ ALAPITO VILAG LETREHOZASA.

EZ VOLT A LEGNAGYOBB HIANY. Eddig:
  - a kezdo lovaknak NEM VOLT szarmazasa (ures os-tomb)
  - az NPC ellenfelek menet kozben generalt, AZONOSITO NELKULI lovak
  - a menallomanynak nem volt pedigreje, sem versenymultja
  - ezert nem letezett inbreeding, vervonal, csalad vagy mennezet

A megoldas: a jatek indulasa ELOTT felepitunk nehany generacionyi
tortenelmet.

    0. GENERACIO   taproot kancak es menek (osok, nincs szulojuk)
         |         minden kanca sajat family_id-t alapit
         |         minden men sajat sire_line_id-t alapit
         v
    1-N GENERACIO  elore tenyesztve ES LEFUTTATVA
         |         igy versenymultjuk, black type-juk, ivadek-
         |         statisztikajuk lesz
         v
    A JATEK KEZDETE
         - a jatekos kezdo lovai EBBOL a populaciobol jonnek
         - a menlista VALODI lovak, pedigrevel es rekorddal
         - a verseny-ellenfelek is valodi lovak

Igy az elso naptol van mit megnezni: kataloguslap, vervonal,
ivadekstatisztika, csalad.
"""

import random
import uuid

import breeding_sim as BR
import feeding_sim as FD
import track_sim as TK
import race_sim as RC
import trainer_sim as TR
import jockey_sim as JK
import lifecycle_sim as LC
import game as G
import naming as NM
import stud_sim as ST


# =======================================================================
# 1) MERETEZES
# =======================================================================
# A taproot generacio merete hatarozza meg a genallomany valtozatossagat.
# A stud_sim.py diverzitas-adata szerint egy szuk alapito populacio
# gyorsan beszukiti a vervonalakat - ezert bosegesen meretezunk.
DEFAULT_CONFIG = {
    'taproot_mares': 36,       # ennyi noi csalad alapul
    'taproot_studs': 14,       # ennyi menvonal alapul
    'generations': 4,          # ennyi nemzedeket tenyesztunk elore
    'foals_per_gen': 30,       # generacionkent ennyi csiko
    'races_per_horse': 22,     # TELJES palyafutas (5 start/szezon x ~5 szezon).
                               # 8-cal egyetlen lo sem erte el a Group
                               # kuszobot (60 000), tehat NEM VOLT black
                               # type a vilagban.
    'quality_mean': 58,        # a taproot atlagos kepessege
    'quality_sd': 12,
    'breeders': 14,           # NPC tenyesztok szama
}


def fresh_or_pedigree_name(rng, sire_name, dam_name):
    """A nevadas KEVERT.

    A tiszta pedigre-nevadas negy generacio utan elfajul: a szulok
    nevet osszefuzve "Wrenwrenwr" es "Gildbwrenrg" lesz belole.
    A valos tenyesztesben is csak a nevek egy resze utal a szulokre.

    Ezert az esetek ~35%-aban pedigre-nev, egyebkent friss nev.
    """
    if rng.random() < 0.35:
        try:
            nm = BR.generate_pedigree_name(sire_name, dam_name)[0]
            # ha az eredmeny ismetlodo szotagokat tartalmaz, dobjuk el
            low = nm.lower()
            if not any(low.count(frag) > 1 for frag in ('wren', 'gild', 'cold',
                                                        'oak', 'elm', 'fern')):
                return nm
        except Exception:
            pass
    return _name(rng)


# =======================================================================
# 1b) NPC TENYESZTOK
# =======================================================================
# A vilag nem nevtelen: minden lo mogott all egy TENYESZTO. Ez adja
# a jatek NPC-bazisat, es a tenyesztoi premium (GDD 9.3) cimzettjet is.
#
# A tenyesztok STRATEGIABAN kulonboznek - ez hozza letre a valos
# kiválasztódást: az elit menes a legjobb menekhez fer, a
# kereskedo mennyisegre megy, a hagyomanyorzo a sajat vonalat epiti.
BREEDER_PREFIX = ['Ashford', 'Kingsmere', 'Harrowgate', 'Millbrook',
                  'Thornbury', 'Wrenfield', 'Creedon', 'Blackwater',
                  'Fernhill', 'Oakmont', 'Ravensworth', 'Coldstream',
                  'Elmsworth', 'Highfield', 'Northgate', 'Stonebridge',
                  'Ivybridge', 'Larkspur', 'Marchmont', 'Pinehurst']
BREEDER_SUFFIX = ['Stud', 'Farm', 'Stables', 'Bloodstock', 'Park', 'Grange']

BREEDER_STRATEGIES = {
    'elite': {
        'label': 'Elit ménes',
        'share': 0.15,
        'stud_pick': 'best',        # a legjobb menhez fer
        'foals_per_season': 4,
        'feed': 'kivalo',
    },
    'commercial': {
        'label': 'Kereskedő',
        'share': 0.35,
        'stud_pick': 'value',       # ar/ertek aranyt nez
        'foals_per_season': 6,
        'feed': 'jo',
    },
    'traditional': {
        'label': 'Hagyományőrző',
        'share': 0.30,
        'stud_pick': 'line',        # a sajat vonalat epiti
        'foals_per_season': 3,
        'feed': 'jo',
    },
    'small': {
        'label': 'Kisgazda',
        'share': 0.20,
        'stud_pick': 'affordable',  # amit megenged maganak
        'foals_per_season': 2,
        'feed': 'kozepes',
    },
}


def make_breeders(rng, n=14):
    """NPC tenyesztok generalasa strategiakkal."""
    keys = list(BREEDER_STRATEGIES)
    weights = [BREEDER_STRATEGIES[k]['share'] for k in keys]
    used, out = set(), []
    for i in range(n):
        while True:
            nm = f"{rng.choice(BREEDER_PREFIX)} {rng.choice(BREEDER_SUFFIX)}"
            if nm not in used:
                used.add(nm)
                break
        strat = rng.choices(keys, weights)[0]
        out.append({
            'breeder_id': f"npc-{i:02d}",
            'name': nm,
            'strategy': strat,
            'label': BREEDER_STRATEGIES[strat]['label'],
            'mares': [],
            'foals_bred': 0,
            'black_type_bred': 0,
            'premium_earned': 0,
        })
    return out


def pick_stud(breeder, studs, rng, world):
    """A tenyeszto strategiaja szerint valaszt ment.

    EZ HOZZA LETRE A KIVALASZTODAST: az elit menesek a legjobb
    menekhez mennek, igy azok utodai dominalnak - ahogy a valos
    piacon is (lasd stud_sim.py diverzitas-adatait).
    """
    if not studs:
        return None
    mode = BREEDER_STRATEGIES[breeder['strategy']]['stud_pick']

    if mode == 'best':
        # a harom legjobb kozul valaszt
        top = sorted(studs, key=lambda h: -h.genetic_score())[:3]
        return rng.choice(top)
    if mode == 'value':
        # a kozepmezony felso resze
        ranked = sorted(studs, key=lambda h: -h.genetic_score())
        mid = ranked[len(ranked)//5: len(ranked)//2] or ranked
        return rng.choice(mid)
    if mode == 'line':
        # sajat vonal: az elozo evi menjeit reszesiti elonyben
        own = [s for s in studs if s.breeder_id == breeder['breeder_id']]
        if own and rng.random() < 0.6:
            return rng.choice(own)
        return rng.choice(studs)
    # affordable: az also ketharmadbol
    ranked = sorted(studs, key=lambda h: h.genetic_score())
    return rng.choice(ranked[:max(1, len(ranked) * 2 // 3)])


def _name(rng):
    A = ['Ash', 'Bram', 'Cinder', 'Dun', 'Elm', 'Fen', 'Grey', 'Haw', 'Iron',
         'Kes', 'Lark', 'Mor', 'Nettle', 'Oak', 'Pike', 'Quill', 'Rush',
         'Slate', 'Thorn', 'Vale', 'Wren', 'Bracken', 'Harrow', 'Marlow',
         'Coldm', 'Ferns', 'Gild', 'Hollow', 'Ivy', 'Juniper']
    B = ['bank', 'brook', 'crest', 'dale', 'fall', 'gate', 'hill', 'lane',
         'mere', 'ridge', 'shade', 'stone', 'wick', 'wood', 'field', 'mont',
         'water', 'reach', 'moor', 'holt']
    return (rng.choice(A) + rng.choice(B))[:18]


# =======================================================================
# 2) TAPROOT GENERACIO
# =======================================================================
def make_taproot(world, sex, quality_mean, quality_sd, owner='world',
                 elite=False, theme=None):
    """Alapito lo: NINCS szuloje. Sajat vonalat alapit.

    A noi vonal (family_id) es a menvonal (sire_line_id) INNEN indul -
    minden kesobbi lo valamelyik taproot-tol szarmazik.
    """
    # A KIVALASZTODASHOZ kell nehany KIEMELKEDO alapito. A valos
    # telivér-populacio is nehany domináns ostol szarmazik (Darley
    # Arabian, Godolphin Arabian, Byerley Turk) - ezert par alapito
    # jelentosen jobb a tobbinel.
    mean = quality_mean + (18 if elite else 0)
    genetics = {t: max(5, min(99, world.rng.gauss(mean, quality_sd)))
                for t in BR.TRAIT_CONFIG}
    geno = {k: BR.random_genotype_locus(k) for k in BR.POP_ALLELE_FREQ}
    colour = BR.color_phenotype(geno)

    h = G.Horse(
        horse_id=str(uuid.uuid4())[:8],
        name=NM.generate_name(world.rng, theme_key=theme,
                              used_names=world.used_names),
        sex=sex,
        birth_season=0,
        family_id=str(uuid.uuid4())[:8] if sex == 'filly' else None,
        sire_line_id=str(uuid.uuid4())[:8] if sex == 'colt' else None,
        genetics=genetics,
        colour_genotype=geno,
        colour=colour['displayed_color'],
        born_colour=colour['born_color'],
        will_grey=colour['will_gray_with_age'],
        rarity=colour['rarity_tier'],
        breeder_id=owner,
        owner_id=owner,
        stage='breeding',
        age=6,
    )
    if sex == 'filly':
        h.breeding_bar = 80.0
    world.used_names.add(h.name)
    h.line_theme = theme or NM.assign_theme(world.rng)
    h.is_elite_founder = elite
    if sex == 'colt':
        h.stud_policy = assign_stud_policy(world.rng)
    return world.add(h)


def assign_stud_policy(rng):
    """Valogatos vagy nyitott men (stud_sim.py 12.2).

    EZ OLDJA FEL A TYUK-TOJAS PROBLEMAT: a valogatos men jo kancat
    var, de a jatekos kezdo kancai gyengek. A NYITOTT men barkit
    fogad - dupla dijert.

    Az integracio deritette ki, hogy enelkul a jatekos kezdo kancai
    EGYETLEN mennel sem fedeztethetok.
    """
    return (ST.STUD_POLICY_OPEN if rng.random() < 0.38
            else ST.STUD_POLICY_SELECTIVE)


# =======================================================================
# 2b) MEZONY A VALODI POPULACIOBOL
# =======================================================================
# EZ VOLT A GYOKER-OK. A race_sim.generate_field() SZINTETIKUS NPC-ket
# general fix fillBar-savokbol (G3 = 76-92). A vilag legjobb lova viszont
# 67.8-nal all - igy SOHA nem nyerhetett Group futamot, tehat nem volt
# black type a vilagban.
#
# A megoldas: a mezony a VALODI populaciobol jojjon. Igy
#   - a mezony automatikusan a vilag szintjehez igazodik
#   - az ellenfelek AZONOSITOTT lovak, pedigrevel es rekorddal
#   - a jatekos megnezheti, ki ellen futott
def field_from_world(world, candidates, me, size, trainer, jockey,
                     band, surface):
    """Mezony osszeallitasa valodi lovakbol.

    Ha nincs eleg alkalmas lo, szintetikus NPC-vel toltjuk fel -
    de csak akkor.
    """
    me_fill = me['fill_bar']
    pool = [h for h in candidates
            if h.stage == 'racer' and h.career_bar > 0
            and abs(h.fill_bar(trainer['overall_score']) - me_fill) < 14]
    world.rng.shuffle(pool)

    field = [me]
    for h in pool:
        if len(field) >= size:
            break
        field.append(G.to_race_horse(h, trainer, jockey, band, surface))

    # ha keves a valodi lo, kiegeszitjuk - a mezony szintjehez igazitva
    while len(field) < size:
        npc = RC.generate_npc('b20', world.rng)
        npc['fill_bar'] = max(20.0, world.rng.gauss(me_fill, 6))
        field.append(npc)
    return field


# =======================================================================
# 3) TORTENELMI FUTAMOK
# =======================================================================
# A tortenelmi lovak IS futnak - igy lesz versenymultjuk, black type-juk
# es ivadekstatisztikajuk. Enelkul a menlista ures rekordokkal indulna.
def race_history(world, horse, trainer, jockey, n_races, cohort=None):
    """Egy tortenelmi lo palyafutasa. A VALODI race_sim-et hasznalja,
    es a mezony is a VALODI populaciobol jon (lasd field_from_world)."""
    cohort = cohort or []
    for i in range(n_races):
        if horse.career_bar <= 0:
            break
        bracket = TK.bracket_for_earnings(horse.career_earnings, horse.wins > 0)
        track_key = world.rng.choice(list(TK.TRACKS.keys()))
        track = TK.TRACKS[track_key]
        dist = world.rng.choice(track['distances'])
        band = TK.band_for_furlongs(dist)

        race = {'band': band, 'style_bias': track['style_bias'],
                'surface': track['surface'], 'bracket': {'key': bracket['key']},
                'purse': TK.purse_for_race(bracket['key'], track_key)}

        me = G.to_race_horse(horse, trainer, jockey, band, track['surface'])
        rivals = [h for h in cohort if h is not horse]
        field = field_from_world(world, rivals, me, 9, trainer, jockey,
                                 band, track['surface'])
        outcome = RC.run_race(field, race, world.rng)
        mine = next(r for r in outcome['results'] if r['horse'] is me)
        gross = RC.distribute_purse(race['purse'], outcome['results'])[me['name']]

        db_race = world.db.record_race(
            season=0, day=i + 1, track_id=track_key, track_name=track['name'],
            distance_f=dist, surface=track['surface'], going='jó',
            bracket=bracket['key'], purse=race['purse'],
            field_size=len(field),
            is_black_type=bracket['key'] in ('open', 'b250'))
        world.db.record_result(db_race, horse, mine['position'], gross,
                               fill_bar=me['fill_bar'])

        horse.starts += 1
        horse.career_earnings += gross
        if mine['position'] == 1:
            horse.wins += 1
        horse.career_bar = max(0, horse.career_bar - LC.career_cost_per_start())
        horse.career_used = 100.0 - horse.career_bar

    # --- Group futam, ha elerte a kuszobot: INNEN JON A BLACK TYPE ---
    eligible = [g for g, cfg in TK.GROUP_RACES.items()
                if horse.career_earnings >= cfg['min_earnings']]
    if eligible:
        grp = eligible[-1]
        cfg = TK.GROUP_RACES[grp]
        track = TK.TRACKS['kingsmere']
        band = TK.band_for_furlongs(world.rng.choice(track['distances']))
        race = {'band': band, 'style_bias': track['style_bias'],
                'surface': track['surface'], 'bracket': {'key': 'open'},
                'purse': cfg['purse']}
        me = G.to_race_horse(horse, trainer, jockey, band, track['surface'])
        # a Group mezony IS a vilag legjobbjaibol all
        elite = sorted([h for h in world.horses.values()
                        if h.stage == 'racer' and h is not horse],
                       key=lambda h: -h.fill_bar(trainer['overall_score']))[:30]
        field = field_from_world(world, elite, me, 10, trainer, jockey,
                                 band, track['surface'])
        outcome = RC.run_race(field, race, world.rng)
        mine = next(r for r in outcome['results'] if r['horse'] is me)
        gross = RC.distribute_purse(cfg['purse'], outcome['results'])[me['name']]

        db_race = world.db.record_race(
            season=0, day=30, track_id='kingsmere', track_name=track['name'],
            distance_f=10, surface=track['surface'], going='jó',
            bracket=grp, purse=cfg['purse'], field_size=len(field),
            is_black_type=True,
            classic_key='klasszikus' if grp == 'G1' else None)
        world.db.record_result(db_race, horse, mine['position'], gross,
                               fill_bar=me['fill_bar'])
        horse.starts += 1
        horse.career_earnings += gross
        if mine['position'] == 1:
            horse.wins += 1
            horse.black_type_wins += 1


# =======================================================================
# 4) A VILAG FELEPITESE
# =======================================================================
def build_world(config=None, seed=None, verbose=False):
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    rng = random.Random(seed if seed is not None else random.randint(1, 10**9))
    world = G.World(rng=rng)

    trainer = TR.generate_random_trainer('Világ')
    jockey = JK.generate_random_jockey('Világ')

    # --- NPC TENYESZTOK ---
    world.breeders = make_breeders(rng, cfg['breeders'])
    by_id = {b['breeder_id']: b for b in world.breeders}

    # --- 0. GENERACIO: taproot ---
    # Nehany KIEMELKEDO alapito - ok adjak a kesobbi elit vonalakat.
    elite_mares = max(2, cfg['taproot_mares'] // 12)
    elite_studs = max(2, cfg['taproot_studs'] // 5)

    mares = []
    for i in range(cfg['taproot_mares']):
        b = rng.choice(world.breeders)
        m = make_taproot(world, 'filly', cfg['quality_mean'], cfg['quality_sd'],
                         owner=b['breeder_id'], elite=(i < elite_mares))
        b['mares'].append(m.horse_id)
        mares.append(m)

    studs = []
    for i in range(cfg['taproot_studs']):
        b = rng.choice(world.breeders)
        st = make_taproot(world, 'colt', cfg['quality_mean'] + 3,
                          cfg['quality_sd'], owner=b['breeder_id'],
                          elite=(i < elite_studs))
        studs.append(st)

    if verbose:
        print(f"  {len(world.breeders)} NPC tenyésztő")
        print(f"  0. generáció: {len(mares)} taproot kanca "
              f"({elite_mares} kiemelkedő), {len(studs)} taproot mén "
              f"({elite_studs} kiemelkedő)")

    generations = [(mares, studs)]

    # --- 1..N GENERACIO ---
    for gen in range(1, cfg['generations'] + 1):
        prev_mares, prev_studs = generations[-1]
        pool = [m for m in prev_mares if (m.breeding_bar or 0) > 0]
        if not pool or not prev_studs:
            break

        new_horses = []
        # A TENYESZTOK dontenek - EZ HOZZA LETRE A KIVALASZTODAST
        for breeder in world.breeders:
            own_mares = [m for m in pool
                         if m.owner_id == breeder['breeder_id']]
            if not own_mares:
                own_mares = [rng.choice(pool)]
            n_foals = BREEDER_STRATEGIES[breeder['strategy']]['foals_per_season']
            feed = BREEDER_STRATEGIES[breeder['strategy']]['feed']

            for _ in range(n_foals):
                dam = rng.choice(own_mares)
                if (dam.breeding_bar or 0) < LC.breeding_cost(dam.age):
                    continue
                sire = pick_stud(breeder, prev_studs, rng, world)
                if sire is None:
                    continue
                dam.breeding_bar -= LC.breeding_cost(dam.age)

                foal = G.breed(world, sire, dam, breeder['breeder_id'],
                               feed_quality=feed,
                               name_fn=lambda r, sn, dn, _s=sire, _d=dam:
                                   NM.generate_name(r, _s, _d, world.horses,
                                                    getattr(_s, 'line_theme', None),
                                                    world.used_names))
                world.used_names.add(foal.name)
                foal.owner_id = breeder['breeder_id']
                foal.line_theme = NM.assign_theme(
                    rng, getattr(sire, 'line_theme', None))
                if foal.sex == 'colt':
                    foal.stud_policy = assign_stud_policy(rng)
                foal.stage = 'racer'
                foal.age = 3
                foal.foal_stage_pct = FD.calculate_foal_stage_bonus_pct(feed, True, True)
                foal.yearling_stage_pct = FD.calculate_yearling_stage_bonus_pct(feed, True, True)
                breeder['foals_bred'] += 1
                new_horses.append(foal)

        # a generacio LEFUT
        for h in new_horses:
            race_history(world, h, trainer, jockey, cfg['races_per_horse'],
                         cohort=new_horses)

        gen_bt = sum(1 for h in new_horses
                     if world.db.stats(h.horse_id).black_type_wins)
        gen_btp = sum(1 for h in new_horses
                      if world.db.stats(h.horse_id).black_type_places)

        # --- KIVALASZTODAS: csak a jobbak maradnak fenn ---
        gen_mares, gen_studs = [], []
        for h in new_horses:
            h.age = 6
            st = world.db.stats(h.horse_id)
            if st.black_type_wins:
                b = by_id.get(h.breeder_id)
                if b:
                    b['black_type_bred'] += 1
            if h.sex == 'filly':
                h.stage = 'breeding'
                h.breeding_bar = LC.breeding_bar_from_career(h.career_used)
                gen_mares.append(h)
            else:
                # SZIGORU szures a meneknel - a valos piac is igy mukodik:
                # a csikok toredekebol lesz men (stud_sim.py)
                q = h.genetic_score()
                if st.black_type_wins or q >= cfg['quality_mean'] + 8:
                    h.stage = 'breeding'
                    gen_studs.append(h)
                else:
                    h.stage = 'retired_out'

        # az elozo generacio legjobb menjei is elerhetok maradnak
        survivors = sorted(prev_studs, key=lambda x: -x.genetic_score())
        gen_studs += survivors[:max(3, len(survivors) // 3)]
        generations.append((gen_mares or prev_mares, gen_studs or prev_studs))

        if verbose:
            best = max((h.genetic_score() for h in new_horses), default=0)
            print(f"  {gen}. generáció: {len(new_horses)} csikó · "
                  f"{len(gen_mares)} kanca · {len(gen_studs)} mén · "
                  f"{gen_bt} black type győzelem, {gen_btp} helyezés · "
                  f"legjobb genetika {best:.0f}")

    world.season = 1
    return world, generations


# =======================================================================
# 5) A JATEKOS KEZDOALLOMANYA A VILAGBOL
# =======================================================================
def give_starting_stock(world, generations, player_id, feed_quality='jo'):
    """A jatekos kezdo lovai A VILAGBOL jonnek - valodi szarmazassal.

    A GDD 2.2 szerint: 2 gyenge kanca + 2 versenylo (a nagybatya
    hagyateka). A "gyenge" itt azt jelenti, hogy a populacio also
    harmadabol valasztunk.
    """
    latest_mares, _ = generations[-1]
    pool = sorted([m for m in latest_mares if (m.breeding_bar or 0) > 20],
                  key=lambda m: m.genetic_score())
    if len(pool) < 2:
        pool = sorted(latest_mares, key=lambda m: m.genetic_score())

    # az also harmadbol - "gyenge statokkal"
    lower = pool[:max(2, len(pool) // 3)]
    mares = world.rng.sample(lower, min(2, len(lower)))
    for m in mares:
        m.owner_id = player_id
        m.age = 5

    # KET VERSENYKORBELI LO - FRISSEN TENYESZTVE a vilag populaciojabol.
    #
    # Korabban a meglevo tortenelmi lovakbol valasztottam, de azoknak
    # mar elfogyott a karrier-csikjuk - igy csak a TAPROOTOK feleltek
    # meg a szuronek, amiknek viszont NINCS szarmazasuk. Pont az
    # ellenkezoje annak, amit el akartunk erni.
    latest_studs = generations[-1][1]
    mid_mares = sorted(latest_mares, key=lambda m: m.genetic_score())
    mid_mares = mid_mares[len(mid_mares)//3: 2*len(mid_mares)//3] or latest_mares
    mid_studs = sorted(latest_studs, key=lambda x: x.genetic_score())
    mid_studs = mid_studs[len(mid_studs)//3: 2*len(mid_studs)//3] or latest_studs

    racers = []
    for _ in range(2):
        dam = world.rng.choice(mid_mares)
        sire = world.rng.choice(mid_studs)
        foal = G.breed(world, sire, dam, player_id, feed_quality=feed_quality,
                       name_fn=fresh_or_pedigree_name)
        foal.owner_id = player_id
        foal.sex = 'colt'
        foal.stage = 'racer'
        foal.age = 3
        foal.career_bar = 100.0
        foal.career_used = 0.0
        foal.freshness = 100.0
        foal.foal_stage_pct = FD.calculate_foal_stage_bonus_pct(feed_quality, True, True)
        foal.yearling_stage_pct = FD.calculate_yearling_stage_bonus_pct(feed_quality, True, True)
        racers.append(foal)

    return {'mares': mares, 'racers': racers}


# =======================================================================
# 6) MENLISTA
# =======================================================================
def stud_roster(world, generations, limit=24, include_lower=True):
    """Az elerheto menek - VALODI lovak, pedigrevel es rekorddal."""
    _, studs = generations[-1]
    seen, out = set(), []
    for s in studs:
        if s.horse_id in seen or s.stage == 'retired_out':
            continue
        st = world.db.stats(s.horse_id)
        # A TAPROOT osok sosem futottak - ok az alapito generacio,
        # nem szerepelnek a menlistan. A jatekos csak olyan mennel
        # fedeztethet, akinek van versenymultja.
        if st.starts == 0:
            continue
        seen.add(s.horse_id)
        out.append({
            'horse_id': s.horse_id, 'name': s.name,
            'grade': s.grade(), 'colour': s.colour, 'rarity': s.rarity,
            'age': s.age,
            'starts': st.starts, 'wins': st.wins,
            'earnings': st.career_earnings,
            'black_type': st.black_type_wins,
            'black_type_places': st.black_type_places,
            'progeny': st.progeny_count,
            'progeny_winners': st.progeny_winners,
            'progeny_black_type': st.progeny_black_type,
            'sire': world.horses[s.sire_id].name if s.sire_id else None,
            'dam': world.horses[s.dam_id].name if s.dam_id else None,
            'policy': getattr(s, 'stud_policy', ST.STUD_POLICY_SELECTIVE),
        })
    out.sort(key=lambda r: (-r['black_type'], -r['black_type_places'],
                            -r['progeny_black_type'], -r['earnings']))
    top = out[:limit]

    # A LISTA ALJA IS KELL: a kezdo jatekos gyenge kancai csak
    # alacsonyabb fokozatu vagy nyitott mennel fedeztethetok.
    # Ha csak az elitet mutatnank, a jatekos elakadna.
    if include_lower:
        lower = [r for r in out[limit:]
                 if r['policy'] == ST.STUD_POLICY_OPEN
                 or ST.grade_rank(r['grade']) <= ST.grade_rank('B')]
        lower.sort(key=lambda r: -r['earnings'])
        top += lower[:8]
    return top


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    import time
    print("=== BREEDER TYCOON - ALAPITO VILAG ===\n")
    print("A jatek indulasa ELOTT felepitunk nehany generacionyi tortenelmet.\n")

    t0 = time.time()
    world, gens = build_world(seed=2024, verbose=True)
    elapsed = time.time() - t0

    print(f"\n  Felépítés ideje: {elapsed:.1f} mp")
    print(f"  Összes ló: {len(world.horses)}")
    print(f"  Lefutott futam: {len(world.db.races)}")
    print(f"  Női család: {len({h.family_id for h in world.horses.values() if h.family_id})}")
    print(f"  Ménvonal: {len({h.sire_line_id for h in world.horses.values() if h.sire_line_id})}\n")

    print("--- 1) A KEZDO LOVAKNAK MOST MAR VAN SZARMAZASA ---")
    stock = give_starting_stock(world, gens, 'player')
    for h in stock['mares'] + stock['racers']:
        sire = world.horses[h.sire_id].name if h.sire_id else 'taproot'
        dam = world.horses[h.dam_id].name if h.dam_id else 'taproot'
        print(f"  {h.name:13s} {h.sex:6s} {h.grade():3s}  {dam} × {sire}")
        print(f"     ős-tömb: {len([a for a in h.ancestors if a])} ismert ős")
    print()

    print("--- 2) MENLISTA: VALODI LOVAK REKORDDAL ---")
    roster = stud_roster(world, gens, 8)
    print(f"  {'Mén':14s} {'Idx':4s} {'Start/Gy':>9s} {'Nyeremény':>10s} "
          f"{'BT':>3s} {'Utód':>5s}  Származás")
    for s in roster:
        ped = f"{s['dam']} × {s['sire']}" if s['sire'] else 'taproot'
        print(f"  {s['name']:14s} {s['grade']:4s} {s['starts']:4d}/{s['wins']:<4d} "
              f"{s['earnings']:>10,d} {s['black_type']:>3d} {s['progeny']:>5d}  {ped}"
              .replace(',', ' '))
    print()

    print("--- 3) EGY MEN PEDIGRE-LAPJA ---")
    # A demohoz a LEGMELYEBB pedigreju lovat valasztjuk, hogy latszodjon
    # a tobbgeneracios visszakovetes.
    def depth_of(h, seen=None):
        seen = seen or set()
        if h is None or h.horse_id in seen:
            return 0
        seen.add(h.horse_id)
        return 1 + max(depth_of(world.horses.get(h.sire_id), seen),
                       depth_of(world.horses.get(h.dam_id), seen))

    candidates = [world.horses[r['horse_id']] for r in roster]
    candidates += sorted(world.horses.values(),
                         key=lambda h: -world.db.stats(h.horse_id).career_earnings)[:10]
    top = max(candidates, key=depth_of)
    page = world.db.catalogue_page(top, world.horses)
    p, f = page['pedigree'], page['form']
    print(f"  ┌─ {page['name']}  ({page['colour']})")
    print(f"  │  apja:  {p['sire'] or 'taproot'}  [{p['sire_black_type']}]")
    print(f"  │  anyja: {p['dam'] or 'taproot'}  [{p['dam_black_type']}]")
    print(f"  │  Forma: {f['starts']} start, {f['wins']} győzelem, "
          f"{f['earnings']:,} B$".replace(',', ' '))
    if page['progeny']:
        pr = page['progeny']
        print(f"  │  Utódok: {pr['count']} ({pr['winners']} győztes, "
              f"{pr['black_type']} black type)")
    if page['family']:
        fm = page['family']
        print(f"  └─ Család: {fm['offspring']} utód, {fm['black_type']} black type")
    print()

    print("--- 3b) NPC TENYESZTOK ---")
    print("  A világ nem névtelen: minden ló mögött áll egy tenyésztő.\n")
    print(f"  {'Tenyésztő':26s} {'Stratégia':16s} {'Csikó':>6s} {'BT':>4s}")
    for b in sorted(world.breeders, key=lambda x: -x['black_type_bred'])[:8]:
        print(f"  {b['name']:26s} {b['label']:16s} "
              f"{b['foals_bred']:>6d} {b['black_type_bred']:>4d}")
    print()

    print("--- 3c) TELJES PEDIGRE-VISSZAKOVETES ---")
    print("  A 14 elemű ős-tömb négy generációt fed le, de a TELJES vonal")
    print("  nem vész el — a sire_id/dam_id lánc tetszőleges mélységig jár.\n")
    deep = world.db.full_pedigree(top, world.horses, depth=5)

    def show(node, prefix='', role=''):
        if node is None:
            return
        bt = f" [{node['black_type']}]" if node['black_type'] != 'none' else ''
        rec = (f"{node['starts']}st/{node['wins']}gy"
               if node['starts'] else 'nem futott')
        print(f"  {prefix}{role}{node['name']}{bt}  ({rec})")
        if node['level'] < 3:
            show(node['sire'], prefix + '   ', 'a: ')
            show(node['dam'], prefix + '   ', 'a̶: ')
    show(deep)
    print()

    print("  TISZTA NŐI VONAL (a female family gerince):")
    for row in world.db.tail_female(top, world.horses, 6):
        bh = ' [BLUE HEN]' if row['is_blue_hen'] else ''
        print(f"     {row['generation']}. anya: {row['name']:16s} "
              f"{row['progeny']} utód, {row['progeny_black_type']} BT{bh}")
    print()
    print("  TISZTA MÉN VONAL:")
    for row in world.db.tail_male(top, world.horses, 6):
        print(f"     {row['generation']}. apa:  {row['name']:16s} "
              f"{row['starts']}st/{row['wins']}gy, {row['progeny']} utód")
    print()

    sib = world.db.siblings(top, world.horses)
    print(f"  TESTVEREK: {len(sib['full'])} teljes, {len(sib['half'])} fél")
    for r in (sib['full'] + sib['half'])[:4]:
        print(f"     {r['name']:16s} {r['starts']}st/{r['wins']}gy "
              f"{r['earnings']:>6,d} B$".replace(',', ' '))
    print()

    print("--- 4) INBREEDING MOST MAR LETEZIK ---")
    latest_mares, latest_studs = gens[-1]
    pairs = []
    for _ in range(200):
        m = world.rng.choice(latest_mares)
        s = world.rng.choice(latest_studs)
        inb = BR.inbreeding_coeff(G.to_breeding_parent(s), G.to_breeding_parent(m))
        pairs.append(inb)
    nonzero = [p for p in pairs if p > 0]
    print(f"  200 véletlen párosításból {len(nonzero)} rokon "
          f"({len(nonzero)/2:.0f}%)")
    if nonzero:
        print(f"  átlagos inbreeding a rokonoknál: "
              f"{sum(nonzero)/len(nonzero)*100:.1f}%")
        print(f"  legmagasabb: {max(nonzero)*100:.1f}%")
    print("  (korábban MINDIG 0% volt, mert nem volt származás)\n")

    print("--- 5) VALIDACIO ---")
    with_ancestry = [h for h in world.horses.values() if h.sire_id]
    taproots = [h for h in world.horses.values() if not h.sire_id]
    families = {h.family_id for h in world.horses.values() if h.family_id}
    lines = {h.sire_line_id for h in world.horses.values() if h.sire_line_id}
    raced = [h for h in world.horses.values() if h.starts > 0]
    bt_horses = [h for h in world.horses.values() if h.black_type_wins > 0]

    checks = [
        ('A világ több generációt tartalmaz', len(gens) >= 4),
        ('Vannak taproot ősök', len(taproots) >= 40),
        ('A lovak többségének van származása',
         len(with_ancestry) > len(taproots)),
        ('Több női család létezik', len(families) >= 20),
        ('Több ménvonal létezik', len(lines) >= 10),
        ('A történelmi lovak futottak', len(raced) >= 50),
        ('Van black type a világban', len(bt_horses) >= 1),
        ('A kezdő lovaknak van származása',
         all(h.sire_id for h in stock['racers'])),
        ('A ménlista valódi lovakból áll',
         all(s['starts'] > 0 for s in roster)),
        ('Az inbreeding már nem mindig nulla', len(nonzero) > 0),
        ('A felépítés 30 mp alatt lefut', elapsed < 30),
        ('Minden ló egyedi azonosítót kapott',
         len({h.horse_id for h in world.horses.values()}) == len(world.horses)),
        ('Minden név egyedi',
         len({h.name for h in world.horses.values()}) == len(world.horses)),
        ('A nevek nem fajulnak el (nincs ismétlődő szótag)',
         not any(h.name.lower().count('wren') > 1 or
                 h.name.lower().count('oak') > 1
                 for h in world.horses.values())),
        ('Vannak NPC tenyésztők', len(world.breeders) >= 10),
        ('A tenyésztők eltérő stratégiával dolgoznak',
         len({b['strategy'] for b in world.breeders}) >= 3),
        ('A tenyésztők neve alá tartoznak lovak',
         sum(b['foals_bred'] for b in world.breeders) > 50),
        ('Vannak kiemelkedő alapítók',
         any(getattr(h, 'is_elite_founder', False)
             for h in world.horses.values())),
        ('A teljes pedigré visszakövethető 4 generáción túl is',
         world.db.full_pedigree(top, world.horses, 5) is not None),
        ('A női vonal külön lekérdezhető',
         isinstance(world.db.tail_female(top, world.horses), list)),
        ('A testvérek lekérdezhetők',
         'full' in world.db.siblings(top, world.horses)),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'AZ ALAPITO VILAG KESZ' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
