"""
Breeder Tycoon - Web Backend v1.0
=======================================================================
A VALODI Python motorokat szolgalja ki bongeszonek.

KIZAROLAG BEEPITETT MODULOKAT HASZNAL (http.server, json).
Nincs pip install, nincs requirements.txt - barhol elindul, ahol
van Python 3.

MIERT EZ:
  - a jatek logikaja EGYETLEN forrasban marad (a 17 motor)
  - a frontend NEM szamol semmit, csak megjelenit
  - megszunik a JS-port karbantartasa (season.html duplikacio)
  - ugyanezeket a vegpontokat hivhatja kesobb a Unity kliens is

INDITAS HELYBEN:
    python3 server.py

RENDER.COM:
    Start Command:  python3 server.py
    (a PORT kornyezeti valtozot automatikusan felismeri)
"""

import json
import os
import random
import uuid
import copy
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import game as G
import breeding_sim as BR
import trainer_sim as TR
import jockey_sim as JK
import feeding_sim as FD
import lifecycle_sim as LC
import track_sim as TK
import farm_sim as FA
import marketplace_sim as MP
import auction_sim as AU
import racedb as DB
import worldgen as WG
import calendar_sim as CAL
import auction_runtime as AR
import auction_sim as AU
import stud_sim as ST


# =======================================================================
# ALLAPOT
# =======================================================================
# Memoriaban tarolt vilagok. EGYELORE nincs adatbazis - a schema.sql
# akkor lep be, amikor tartos allapot kell. Render ingyenes szintjen
# a szolgaltatas inaktivitas utan alszik, tehat az allapot elveszhet.
# Teszteleshez ez elfogadhato.
WORLDS = {}
MAX_WORLDS = 40

COLOUR_HU = {'Bay': 'Pej', 'Chestnut': 'Sárga', 'Black': 'Fekete',
             'Gray': 'Szürke', 'Grey': 'Szürke', 'Palomino': 'Palomino'}

FEED_COST = {'rossz': 120, 'kozepes': 280, 'jo': 480, 'kivalo': 780}
CONCENTRATE_COST = 400
STABLE_UPKEEP = 700


# =======================================================================
# KOZOS VILAG
# =======================================================================
# A GDD szerint a jatek EGY KOZOS FIKTIV VILAGBAN jatszodik. Ezert a
# vilagot EGYSZER epitjuk fel, es minden munkamenet ennek egy masolatabol
# indul.
#
# MIERT KELL: a felepites ~1.7 mp helyben, de a Render ingyenes
# szintjenek megosztott CPU-jan ez tobbszorose lehet - es a bongeszo
# feladja, mielott a valasz megjonne (BrokenPipeError). A masolas
# viszont csak ~0.2 mp.
WORLD_SEED = 20260101          # a kozos vilag rogzitett magja
_BASE_WORLD = None


def base_world():
    """A kozos vilag - egyszer epul fel, utana csak masoljuk."""
    global _BASE_WORLD
    if _BASE_WORLD is None:
        print("A közös világ felépítése…", flush=True)
        t0 = __import__('time').time()
        _BASE_WORLD = WG.build_world(seed=WORLD_SEED)
        print(f"Kész: {len(_BASE_WORLD[0].horses)} ló, "
              f"{len(_BASE_WORLD[0].db.races)} futam "
              f"({__import__('time').time()-t0:.1f} mp)", flush=True)
    return _BASE_WORLD


def new_game(feed_quality='jo', trainer_level='mid', seed=None):
    """Uj jatek A KOZOS VILAGBOL.

    A kezdo lovaknak VALODI szarmazasuk van, a menlista valodi lovakbol
    all pedigrevel es versenymulttal.
    """
    base, base_gens = base_world()
    world = copy.deepcopy(base)
    generations = _remap_generations(base_gens, world)
    player = 'player'

    # a munkamenet sajat veletlen-forrasa, hogy a kezdo lovak elterjenek
    world.rng = random.Random(seed if seed is not None
                              else random.randint(1, 10**9))

    clock = CAL.GameClock(season=1, day=1, minute=0)
    cal = CAL.RaceCalendar(clock)
    cal.generate_ahead(world.rng, hours=72, per_slot=2)
    acal = AR.AuctionCalendar(clock)
    acal.generate_ahead(world.rng, world, days=7)

    stock = WG.give_starting_stock(world, generations, player, feed_quality)
    for m in stock['mares']:
        m.stage = 'breeding'
        m.age = 5
        if (m.breeding_bar or 0) < 40:
            m.breeding_bar = 65.0

    sid = str(uuid.uuid4())[:12]
    WORLDS[sid] = {
        'world': world, 'player': player, 'generations': generations,
        'trainer': TR.generate_random_trainer('Hollis'),
        'jockey': JK.generate_random_jockey('Marek'),
        'money': 50000, 'seed': seed,
        'farm': FA.new_farm(),
        'last_earnings': 0,
        # A VEGLEGES SZERKEZET: elore kiirt futamok + nevezesek.
        # Ma a gomb lepteti az orat, kesobb a valos ido.
        'clock': clock,
        'calendar': cal,
        'auctions': acal,
    }
    if len(WORLDS) > MAX_WORLDS:
        WORLDS.pop(next(iter(WORLDS)))
    return sid


def _remap_generations(base_gens, world):
    """A masolt vilagban a generacio-listak a REGI lo-objektumokra
    mutatnanak. Az azonositok alapjan atkotjuk oket az ujakra."""
    out = []
    for mares, studs in base_gens:
        out.append((
            [world.horses[m.horse_id] for m in mares
             if m.horse_id in world.horses],
            [world.horses[s.horse_id] for s in studs
             if s.horse_id in world.horses],
        ))
    return out


def auction_view(sid, session_id=None):
    """Az elerheto aukciok es a katalogus.

    A katalogus a start elott ~1.5 nappal jelenik meg (auction_sim.py).
    """
    st = WORLDS[sid]
    world, acal, clock = st['world'], st['auctions'], st['clock']
    acal.generate_ahead(world.rng, world, days=7)
    opens = acal.open_catalogues()

    def row(s):
        return {
            'session_id': s.session_id,
            'house': s.house_name, 'sale': s.sale_label,
            'tier': 'Elit' if s.tier == 'elite' else 'Standard',
            'buyer_fee': s.buyer_fee,
            'when': CAL.minutes_to_label(s.starts_at),
            'starts_in_min': s.starts_at - clock.now(),
            'lots': len(s.lots),
        }

    detail = None
    if session_id and session_id in acal.sessions:
        sess = acal.sessions[session_id]
        acal.fill_catalogue(sess, world, world.rng)
        lots = []
        for lot in sess.lots:
            h = world.horses.get(lot.horse_id)
            if h is None:
                continue
            hs = world.db.stats(h.horse_id)
            lots.append({
                'lot_id': lot.lot_id, 'hip': lot.hip,
                'name': h.name, 'grade': h.grade(),
                'colour': COLOUR_HU.get(h.colour, h.colour),
                'rarity': h.rarity, 'sex': h.sex, 'age': h.age,
                'stage': h.stage,
                'starts': hs.starts, 'wins': hs.wins,
                'earnings': hs.career_earnings,
                'black_type': hs.black_type_wins,
                'sire': world.horses[h.sire_id].name if h.sire_id else None,
                'dam': world.horses[h.dam_id].name if h.dam_id else None,
                'reserve': lot.reserve,
                'my_bid': lot.max_bid if lot.bidder_id == st['player'] else None,
                'mine': lot.seller_id == st['player'],
            })
        detail = {'session': row(sess), 'lots': lots}

    return {'now': clock.label(),
            'sessions': [row(s) for s in opens[:12]],
            'detail': detail}


def place_bid(sid, lot_id, amount):
    st = WORLDS[sid]
    res = st['auctions'].place_max_bid(lot_id, st['player'], int(amount))
    if res['ok']:
        lot = res['lot']
        h = st['world'].horses.get(lot.horse_id)
        st['world'].ev('auction', f"Maximum licit {int(amount):,} B$ — "
                                  f"{h.name if h else '?'}".replace(',', ' '))
    return {'ok': res['ok'], 'reason': res.get('reason')}


def consign_horse(sid, horse_id, session_id):
    """A jatekos beadja a lovat egy aukciora."""
    st = WORLDS[sid]
    world, acal = st['world'], st['auctions']
    horse = world.horses.get(horse_id)
    sess = acal.sessions.get(session_id)
    if horse is None or sess is None:
        return {'ok': False, 'reason': 'Nincs ilyen ló vagy aukció.'}
    if horse.owner_id != st['player']:
        return {'ok': False, 'reason': 'Ez nem a te lovad.'}
    if sess.status == AR.SessionStatus.RUN:
        return {'ok': False, 'reason': 'Az aukció már lezajlott.'}
    acal.fill_catalogue(sess, world, world.rng)
    if any(l.horse_id == horse_id for l in sess.lots):
        return {'ok': False, 'reason': 'Ez a ló már be van adva.'}
    reserve = AU.default_reserve(AR._horse_row(horse, world), sess.house_key)
    acal._add_lot(sess, horse_id, st['player'], reserve)
    world.ev('auction', f"{horse.name} beadva: {sess.house_name} "
                        f"({CAL.minutes_to_label(sess.starts_at)}), "
                        f"kikiáltás {reserve:,} B$".replace(',', ' '))
    return {'ok': True, 'reserve': reserve}


def race_calendar(sid, horse_id=None):
    """A nevezheto futamok, es a lo jelenlegi nevezesei.

    A VEGLEGES szerkezet: a futamok ELORE ki vannak irva, a nevezes
    24 oraval a start elott zarul.
    """
    st = WORLDS[sid]
    world, cal, clock = st['world'], st['calendar'], st['clock']

    # mindig van eleg futam elore
    cal.generate_ahead(world.rng, hours=72, per_slot=2)

    horse = world.horses.get(horse_id) if horse_id else None
    races = cal.open_races(horse, limit=40)

    def race_row(r):
        return {
            'race_id': r.race_id,
            'when': CAL.minutes_to_label(r.starts_at),
            'starts_in_min': r.starts_at - clock.now(),
            'closes_in_min': r.entries_close_at - clock.now(),
            'track': r.track_name, 'distance_f': r.distance_f,
            'surface': r.surface_hu, 'band': r.band,
            'bracket': r.bracket, 'purse': r.purse,
            'style_bias': r.style_bias,
            'entries': len(cal.active_entries(r.race_id)),
            'max_field': r.max_field,
            'black_type': r.is_black_type,
        }

    entries = []
    for h in world.owned_by(st['player'], 'racer'):
        for row in cal.entries_of(h.horse_id):
            r = row['race']
            entries.append({
                'horse_id': h.horse_id, 'horse': h.name,
                'race_id': r.race_id,
                'when': CAL.minutes_to_label(r.starts_at),
                'track': r.track_name, 'distance_f': r.distance_f,
                'bracket': r.bracket, 'purse': r.purse,
                'status': CAL.STATUS_LABELS[r.status],
            })

    return {
        'now': clock.label(),
        'races': [race_row(r) for r in races],
        'entries': entries,
        'racers': [{'horse_id': h.horse_id, 'name': h.name,
                    'grade': h.grade(),
                    'earnings': h.career_earnings, 'wins': h.wins,
                    'freshness': round(h.freshness),
                    'ready': LC.freshness_ready(h.freshness)}
                   for h in world.owned_by(st['player'], 'racer')],
    }


def enter_race(sid, horse_id, race_id):
    st = WORLDS[sid]
    horse = st['world'].horses.get(horse_id)
    if horse is None:
        return {'ok': False, 'reason': 'Nincs ilyen ló'}
    res = st['calendar'].enter(horse, st['player'], race_id)
    if res['ok']:
        r = res['race']
        st['world'].ev('entry', f"{horse.name} nevezve: {r.track_name} "
                                f"{r.distance_f}f, {r.bracket} "
                                f"({CAL.minutes_to_label(r.starts_at)})")
    return {'ok': res['ok'], 'reason': res.get('reason')}


def withdraw_entry(sid, horse_id, race_id):
    st = WORLDS[sid]
    res = st['calendar'].withdraw(horse_id, race_id)
    if res['ok']:
        h = st['world'].horses.get(horse_id)
        st['world'].ev('entry', f"{h.name if h else '?'} visszalépett")
    return res


def advance_time(sid, minutes):
    """Az ora leptetese es az esedekes futamok feldolgozasa.

    EZ A FUGGVENY VALTOZATLAN MARAD a folyamatos uzemben - csak az
    hivja mas: ma a gomb, kesobb egy 15 perces idozito.
    """
    st = WORLDS[sid]
    world, cal, clock = st['world'], st['calendar'], st['clock']
    before = len(world.log)
    clock.advance(minutes)
    cal.generate_ahead(world.rng, hours=72, per_slot=2)

    def on_result(o):
        bt = f" [{o['black_type'].upper()}]" if o['black_type'] != 'none' else ''
        world.ev('race', f"{o['horse'].name}: {o['position']}. hely "
                         f"{o['race'].track_name} {o['race'].distance_f}f — "
                         f"{o['earnings']:,} B$".replace(',', ' ') + bt)
        if o['owner'] == st['player']:
            st['money'] += o['earnings']
        if o['premium']:
            st['money'] += o['premium']

    results = CAL.process_due_races(
        cal, world, world.db, world.rng,
        st['trainer'], st['jockey'],
        G.to_race_horse, G.effective_trainer_score,
        on_result=on_result)

    # --- AZ AUKCIOK IS LEFUTNAK ---
    def money_cb(delta, reason):
        st['money'] += delta

    st['auctions'].generate_ahead(world.rng, world, days=7)
    AR.process_due_sessions(st['auctions'], world, world.rng,
                            st['player'], money_cb)

    # a lovak frissessege visszatoltodik az eltelt ido alatt
    for h in world.owned_by(st['player'], 'racer'):
        h.freshness = LC.freshness_recover(h.freshness, minutes / 1440.0)

    return {'now': clock.label(), 'results': len(results),
            'events': world.log[before:]}


def staff_options(sid):
    """Elerheto trénerek es zsokék, plusz a lovak jelenlegi felallasa."""
    st = WORLDS[sid]
    world, player = st['world'], st['player']
    trainers, jockeys = G.build_staff_pools(world)

    racers = []
    for h in world.owned_by(player, 'racer'):
        tr = getattr(h, 'trainer', None) or st['trainer']
        jk = getattr(h, 'jockey', None) or st['jockey']
        old = getattr(h, 'previous_trainer', None)
        n = getattr(h, 'races_since_trainer_change', 0)
        racers.append({
            'horse_id': h.horse_id, 'name': h.name, 'grade': h.grade(),
            'trainer': tr['name'],
            'trainer_label': TR.describe_trainer_for_player(tr),
            'jockey': jk['name'],
            'jockey_label': JK.describe_jockey_for_player(jk),
            'in_transition': old is not None and n < TR.TRAINER_CARRYOVER_RACES,
            'transition_note': (TR.describe_transition_for_player(old, tr, n)
                                if old is not None else None),
        })

    return {
        'trainers': [{
            'name': t['name'], 'label': TR.describe_trainer_for_player(t),
            'grade': t['index'], 'spec': t['primary_specialization'],
            'fee': t['fee'],
        } for t in sorted(trainers, key=lambda x: -x['overall_score'])],
        'jockeys': [{
            'name': j['name'], 'label': JK.describe_jockey_for_player(j),
            'grade': j['index'], 'spec': j['distance_specialization'],
            'surface': j['surface_specialization'],
            'cut': round(j['cut'] * 100, 1),
        } for j in sorted(jockeys, key=lambda x: -x['overall_score'])],
        'racers': racers,
        'carryover_races': TR.TRAINER_CARRYOVER_RACES,
    }


def assign_staff(sid, horse_id, trainer_name=None, jockey_name=None):
    st = WORLDS[sid]
    world = st['world']
    trainers, jockeys = G.build_staff_pools(world)
    horse = world.horses.get(horse_id)
    if horse is None:
        return {'error': 'Nincs ilyen ló'}

    notes = []
    if trainer_name:
        tr = next((t for t in trainers if t['name'] == trainer_name), None)
        if tr:
            r = G.assign_trainer(world, horse, tr)
            if r['note']:
                notes.append(r['note'])
                world.ev('staff', r['note'])
    if jockey_name:
        jk = next((j for j in jockeys if j['name'] == jockey_name), None)
        if jk:
            horse.jockey = jk
            note = (f"{horse.name} zsokéja: "
                    f"{JK.describe_jockey_for_player(jk)} — azonnal hat")
            notes.append(note)
            world.ev('staff', note)
    return {'notes': notes}


def breeding_options(sid):
    """Melyik kancahoz melyik men valaszthato, es mennyiert?

    A jatekos ebbol allitja ossze a fedeztetesi tervet.
    """
    s = WORLDS[sid]
    world, player = s['world'], s['player']
    roster = WG.stud_roster(world, s['generations'], 20)

    out = []
    for mare in world.owned_by(player, 'breeding'):
        if mare.sex != 'filly' or (mare.breeding_bar or 0) <= 0:
            continue
        status = G.mare_status(mare)
        p = ST.conception_probability({'age': mare.age, 'status': status,
                                       'health_grade': None})
        opts = []
        for r in roster:
            sire = world.horses[r['horse_id']]
            chk = G.check_covering(world, mare, sire, player)
            inb = BR.inbreeding_coeff(G.to_breeding_parent(sire),
                                      G.to_breeding_parent(mare))
            opts.append({
                'stud_id': r['horse_id'], 'name': r['name'],
                'grade': r['grade'], 'starts': r['starts'], 'wins': r['wins'],
                'earnings': r['earnings'], 'black_type': r['black_type'],
                'progeny': r['progeny'],
                'progeny_black_type': r['progeny_black_type'],
                'fee': G.stud_fee(world, sire),
                'allowed': chk['allowed'], 'reason': chk['reason'],
                'own_stud': chk['same_owner'],
                'inbreeding': round(inb * 100, 1),
            })
        opts.sort(key=lambda o: (not o['allowed'], -o['black_type'],
                                 -o['earnings']))
        blocked_by_vet = sum(1 for o in opts if not o['allowed']
                             and o['reason'] and 'állatorvosi' in o['reason'])
        out.append({
            'mare_id': mare.horse_id, 'mare': mare.name,
            'grade': mare.grade(), 'age': mare.age,
            'status': status,
            'conception_pct': p,
            'conception_label': ST.describe_conception_for_player(
                {'age': mare.age, 'status': status, 'health_grade': None}),
            'foals_left': round((mare.breeding_bar or 0) / 10, 1),
            'health_grade': getattr(mare, 'health_grade', None),
            'vet_cost': G.VET_INSPECTION_COST,
            'blocked_by_vet': blocked_by_vet,
            'studs': opts,
        })
    return out


def run_seasons(sid, feed_quality='jo', starts=5, seasons=1, plan=None):
    s = WORLDS[sid]
    world = s['world']
    before = len(world.log)

    for _ in range(max(1, min(12, seasons))):
        earned_before = sum(h.career_earnings for h in world.owned_by(s['player']))
        # a fedeztetesi dijak levonasa
        if plan:
            for mare_id, sire_id in plan.items():
                sire = world.horses.get(sire_id)
                if sire is not None:
                    s['money'] -= G.stud_fee(world, sire)

        G.play_season(world, s['player'], s['trainer'], s['jockey'],
                      feed_quality=feed_quality, starts=starts,
                      breeding_plan=plan)
        plan = None      # a terv csak az ELSO szezonra ervenyes
        earned = sum(h.career_earnings for h in world.owned_by(s['player'])) - earned_before

        # A nem-versenyzo lovak OLCSOBBAK: nincs treningterheles,
        # kisebb adag. Ugyanaz az arany, mint a season.html-ben.
        active = [h for h in world.owned_by(s['player'])
                  if h.stage not in ('retired_out', 'pensioned')]
        racers = [h for h in active if h.stage == 'racer']
        others = len(active) - len(racers)

        upkeep = len(racers) * STABLE_UPKEEP + others * int(STABLE_UPKEEP * 0.55)
        feed_unit = FEED_COST.get(feed_quality, 480) + CONCENTRATE_COST
        feed = len(racers) * feed_unit + others * int(feed_unit * 0.6)
        trainer_fee = len(racers) * int(250 + s['trainer']['overall_score'] * 22)

        s['money'] += earned - upkeep - feed - trainer_fee
        s['last_earnings'] = earned
        world.ev('money', f"Szezonzárás: bevétel {earned:,} B$, "
                          f"kiadás {upkeep+feed+trainer_fee:,} B$"
                 .replace(',', ' '))

    return world.log[before:]


def serialise(sid):
    s = WORLDS[sid]
    world, player = s['world'], s['player']
    ts = s['trainer']['overall_score']

    horses = []
    for h in world.owned_by(player):
        bars = G.to_lifecycle_bars(h)
        horses.append({
            'name': h.name, 'sex': h.sex, 'age': h.age, 'stage': h.stage,
            'grade': h.grade(), 'colour': h.colour,
            'colour_hu': COLOUR_HU.get(h.colour, h.colour), 'rarity': h.rarity,
            'fill_bar': round(h.fill_bar(ts), 1) if h.stage == 'racer' else None,
            'starts': h.starts, 'wins': h.wins, 'earnings': h.career_earnings,
            'bars': LC.describe_bars(bars),
            'black_type': world.db.stats(h.horse_id).black_type_wins,
            'progeny': world.db.stats(h.horse_id).progeny_count,
            'sire': world.horses[h.sire_id].name if h.sire_id else None,
            'dam': world.horses[h.dam_id].name if h.dam_id else None,
        })

    order = {'racer': 0, 'breeding': 1, 'yearling': 2, 'foal': 3,
             'pensioned': 4, 'retired_out': 5}
    horses.sort(key=lambda x: (order.get(x['stage'], 9), -x['earnings']))

    return {
        'session_id': sid,
        'season': world.season,
        'money': int(s['money']),
        'trainer': TR.describe_trainer_for_player(s['trainer']),
        'jockey': JK.describe_jockey_for_player(s['jockey']),
        'stable_capacity': FA.stable_capacity(s['farm']['stable_level']),
        'horses': horses,
        'totals': {
            'earnings': sum(h['earnings'] for h in horses),
            'starts': sum(h['starts'] for h in horses),
            'wins': sum(h['wins'] for h in horses),
            'foals': len([h for h in horses if h['sire']]),
            'races_run': len(world.db.races),
            'black_type': sum(h['black_type'] for h in horses),
            'premiums': sum(world.db.premiums.values()),
            'active': len([h for h in horses
                           if h['stage'] not in ('retired_out', 'pensioned')]),
        },
    }


def marketplace_for(sid):
    s = WORLDS[sid]
    fams = [h.family_id for h in s['world'].owned_by(s['player']) if h.family_id]
    mp = MP.daily_marketplace(sid, s['world'].season, player_family_ids=fams)
    return {
        'relief': mp['inbreeding_relief'],
        'offers': [{
            'label': o['label'], 'grade': o['grade'], 'colour': o['colour'],
            'rarity': o['rarity'], 'note': o['note'],
            'currency': o['currency'].value,
            'price': o.get('price'), 'band': o.get('price_band'),
        } for o in mp['offers']],
    }


def catalogue(sid, horse_name):
    """Egy lo TELJES pedigre-lapja a versenyadatbazisbol.

    Ez volt eddig lehetetlen: nem gyult adat, tehat nem volt mit
    megjeleniteni."""
    s = WORLDS[sid]
    world = s['world']
    horse = next((h for h in world.horses.values()
                  if h.name == horse_name), None)
    if horse is None:
        return None
    page = world.db.catalogue_page(horse, world.horses)
    page['colour_hu'] = COLOUR_HU.get(horse.colour, horse.colour)
    page['progeny_list'] = world.db.progeny_of(horse.horse_id, world.horses)
    return page


def leaderboards(sid):
    s = WORLDS[sid]
    world = s['world']
    return {
        'racing': world.db.leaderboard_racing(world.horses, 10),
        'breeding': world.db.leaderboard_breeding(world.horses, 10),
        'premiums': sum(world.db.premiums.values()),
        'races_run': len(world.db.races),
    }


def stud_list(sid):
    """Az elerheto menek - VALODI lovak, pedigrevel es rekorddal."""
    s = WORLDS[sid]
    return WG.stud_roster(s['world'], s['generations'], 20)


def world_info():
    return {
        'tracks': [{
            'name': t['name'],
            'surface': TK.SURFACE_LABELS_HU[t['surface']],
            'character': t['character'],
            'style_bias': t['style_bias'],
            'prestige': t['prestige'],
            'danger': TK.SURFACE_DANGER_INDEX[t['surface']],
        } for t in TK.TRACKS.values()],
        'houses': [{
            'name': h['name'],
            'sale_type': AU.SALE_CONFIG[h['sale_type']]['label'],
            'days': h['days'], 'character': h['character'],
        } for h in AU.AUCTION_HOUSES.values()],
    }


# =======================================================================
# HTTP
# =======================================================================
class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        # A bongeszo idokozben feladhatja a kerest (BrokenPipeError).
        # Ez NEM a szerver hibaja - csendben elnyeljuk, kulonben a
        # naplo tele lesz stack trace-szel.
        try:
            body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_html(self, path):
        try:
            with open(path, 'rb') as f:
                body = f.read()
        except OSError:
            self._send({'error': 'app.html hiányzik'}, 404)
            return
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except ValueError:
            return {}

    def do_GET(self):
        p = urlparse(self.path).path
        here = os.path.dirname(os.path.abspath(__file__))

        if p in ('/', '/index.html'):
            return self._send_html(os.path.join(here, 'app.html'))
        if p == '/api/health':
            return self._send({'status': 'ok', 'worlds': len(WORLDS)})
        if p == '/api/world':
            return self._send(world_info())
        if p.startswith('/api/state/'):
            sid = p.rsplit('/', 1)[-1]
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(serialise(sid))
        if p.startswith('/api/catalogue/'):
            parts = p.split('/')
            sid, name = parts[3], parts[4] if len(parts) > 4 else ''
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            from urllib.parse import unquote
            page = catalogue(sid, unquote(name))
            if page is None:
                return self._send({'error': 'Nincs ilyen ló'}, 404)
            return self._send(page)
        if p.startswith('/api/auctions/'):
            parts = p.split('/')
            sid = parts[3]
            ses = parts[4] if len(parts) > 4 else None
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(auction_view(sid, ses))
        if p.startswith('/api/calendar/'):
            parts = p.split('/')
            sid = parts[3]
            hid = parts[4] if len(parts) > 4 else None
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(race_calendar(sid, hid))
        if p.startswith('/api/staff/'):
            sid = p.rsplit('/', 1)[-1]
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(staff_options(sid))
        if p.startswith('/api/breeding/'):
            sid = p.rsplit('/', 1)[-1]
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(breeding_options(sid))
        if p.startswith('/api/studs/'):
            sid = p.rsplit('/', 1)[-1]
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(stud_list(sid))
        if p.startswith('/api/leaderboards/'):
            sid = p.rsplit('/', 1)[-1]
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(leaderboards(sid))
        if p.startswith('/api/marketplace/'):
            sid = p.rsplit('/', 1)[-1]
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(marketplace_for(sid))
        self._send({'error': 'ismeretlen végpont'}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        data = self._body()

        if p == '/api/new':
            sid = new_game(data.get('feed_quality', 'jo'),
                           data.get('trainer_level', 'mid'),
                           data.get('seed'))
            return self._send(serialise(sid))

        if p == '/api/bid':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(place_bid(sid, data.get('lot_id'),
                                        data.get('amount', 0)))

        if p == '/api/consign':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(consign_horse(sid, data.get('horse_id'),
                                            data.get('auction_id')))

        if p == '/api/enter':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(enter_race(sid, data.get('horse_id'),
                                         data.get('race_id')))

        if p == '/api/withdraw':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(withdraw_entry(sid, data.get('horse_id'),
                                             data.get('race_id')))

        if p == '/api/advance':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            mins = int(data.get('minutes', 1440))
            out = advance_time(sid, max(15, min(43200, mins)))
            state = serialise(sid)
            state['events'] = out['events']
            state['now'] = out['now']
            state['races_run'] = out['results']
            return self._send(state)

        if p == '/api/assign':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            return self._send(assign_staff(sid, data.get('horse_id'),
                                           data.get('trainer'),
                                           data.get('jockey')))

        if p == '/api/vet':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            st = WORLDS[sid]
            mare = next((h for h in st['world'].owned_by(st['player'])
                         if h.horse_id == data.get('mare_id')), None)
            if mare is None:
                return self._send({'error': 'Nincs ilyen ló'}, 404)
            if st['money'] < G.VET_INSPECTION_COST:
                return self._send({'error': 'Nincs elég pénz a felmérésre'}, 400)
            st['money'] -= G.VET_INSPECTION_COST
            rep = G.run_vet_inspection(st['world'], mare)
            st['world'].ev('vet', f"{mare.name} állatorvosi felmérése: "
                                  f"{rep['grade']} — {rep['note']}")
            return self._send({'grade': rep['grade'], 'note': rep['note'],
                               'cost': rep['cost'],
                               'money': int(st['money'])})

        if p == '/api/season':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            events = run_seasons(sid,
                                 data.get('feed_quality', 'jo'),
                                 int(data.get('starts', 5)),
                                 int(data.get('seasons', 1)),
                                 data.get('plan'))
            out = serialise(sid)
            out['events'] = events
            return self._send(out)

        self._send({'error': 'ismeretlen végpont'}, 404)

    def log_message(self, *args):
        pass        # csendes naplo


def main():
    port = int(os.environ.get('PORT', 8000))
    # A vilagot INDULASKOR epitjuk fel, nem az elso keresnel - igy a
    # jatekos nem var ra, es nem szakad meg a kapcsolat.
    base_world()
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f"Breeder Tycoon fut: http://0.0.0.0:{port}", flush=True)
    print("FIGYELEM: a munkamenetek MEMORIABAN vannak. A Render ingyenes",
          flush=True)
    print("szintje ujraindulhat, ilyenkor a jatekallas elvesz. A felulet",
          flush=True)
    print("ezt kezeli - automatikusan uj jatekot indit.", flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
