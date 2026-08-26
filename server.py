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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import game as G
import trainer_sim as TR
import jockey_sim as JK
import feeding_sim as FD
import lifecycle_sim as LC
import track_sim as TK
import farm_sim as FA
import marketplace_sim as MP
import auction_sim as AU
import racedb as DB


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


def new_game(feed_quality='jo', trainer_level='mid', seed=None):
    seed = seed if seed is not None else random.randint(1, 10**9)
    world = G.World(rng=random.Random(seed))
    player = 'player'

    for _ in range(2):
        m = G.make_founder(world, player, 'filly', 48)
        m.stage, m.age, m.breeding_bar = 'breeding', 5, 65.0

    for _ in range(2):
        r = G.make_founder(world, player, 'colt', 54)
        r.stage, r.age = 'racer', 3
        r.maternal_pct = FD.calculate_maternal_care_bonus_pct(feed_quality, True)
        r.foal_stage_pct = FD.calculate_foal_stage_bonus_pct(feed_quality, True, True)
        r.yearling_stage_pct = FD.calculate_yearling_stage_bonus_pct(feed_quality, True, True)

    for _ in range(8):
        s = G.make_founder(world, 'npc', 'colt', 64)
        s.stage, s.age = 'breeding', 6

    sid = str(uuid.uuid4())[:12]
    WORLDS[sid] = {
        'world': world, 'player': player,
        'trainer': TR.generate_random_trainer('Hollis'),
        'jockey': JK.generate_random_jockey('Marek'),
        'money': 50000, 'seed': seed,
        'farm': FA.new_farm(),
        'last_earnings': 0,
    }
    if len(WORLDS) > MAX_WORLDS:
        WORLDS.pop(next(iter(WORLDS)))
    return sid


def run_seasons(sid, feed_quality='jo', starts=5, seasons=1):
    s = WORLDS[sid]
    world = s['world']
    before = len(world.log)

    for _ in range(max(1, min(12, seasons))):
        earned_before = sum(h.career_earnings for h in world.owned_by(s['player']))
        G.play_season(world, s['player'], s['trainer'], s['jockey'],
                      feed_quality=feed_quality, starts=starts)
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
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path):
        try:
            with open(path, 'rb') as f:
                body = f.read()
        except OSError:
            self._send({'error': 'app.html hiányzik'}, 404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

        if p == '/api/season':
            sid = data.get('session_id')
            if sid not in WORLDS:
                return self._send({'error': 'Nincs ilyen munkamenet'}, 404)
            events = run_seasons(sid,
                                 data.get('feed_quality', 'jo'),
                                 int(data.get('starts', 5)),
                                 int(data.get('seasons', 1)))
            out = serialise(sid)
            out['events'] = events
            return self._send(out)

        self._send({'error': 'ismeretlen végpont'}, 404)

    def log_message(self, *args):
        pass        # csendes naplo


def main():
    port = int(os.environ.get('PORT', 8000))
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f"Breeder Tycoon fut: http://0.0.0.0:{port}")
    srv.serve_forever()


if __name__ == '__main__':
    main()
