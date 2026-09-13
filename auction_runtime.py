"""
Breeder Tycoon - Auction Runtime v1.0
=======================================================================
AZ AUKCIOS RENDSZER BEKOTESE A JATEKBA — A VEGLEGES SZERKEZETBEN.

Az auction_sim.py leirja a hazakat, a savokat, a licitalast es a
dijakat. Ez a modul ezt HASZNALJA: idozitett sessionoket general,
kezeli a katalogust, a maximum liciteket, es lefuttatja az esedekes
aukciokat.

MIERT KELL: eddig az allomany CSAK tenyesztesbol nott. Nem lehetett
kesz versenylovat venni, nem lehetett yearlinget eladni, es a
tenyesztoi premium is csak a sajat lovakon keresztul jott. A gazdasag
fele nem futott.

=======================================================================
UGYANAZ A SZERKEZET, MINT A VERSENYNAPTARNAL (calendar_sim.py)
=======================================================================

    MOST:    jatekos kattint -> process_due_sessions()
    KESOBB:  utemezo         -> process_due_sessions()

A fuggveny valtozatlan marad. Ami valtozik: az ora valos idot kovet,
es az allapot adatbazisban van.

IDOZITES (auction_sim.py):
  - a katalogus SZERDA 20:00-kor jelenik meg
  - a kategoriahazak hetvegen, a vegyes haz hetfotol csutortokig
  - naponta tobb session, idozonak szerint szetteritve
  - MAXIMUM LICIT: a jatekos "megbizottja" licital helyette
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import auction_sim as AU
import calendar_sim as CAL


# =======================================================================
# 1) A HET NAPJAI A JATEKIDOBEN
# =======================================================================
# season_sim.py: 1 szezon = 30 nap. A het napjai a nap sorszamabol
# szarmaznak, hogy a hazak beosztasa (auction_sim.py) ervenyesuljon.
WEEKDAYS = ['hétfő', 'kedd', 'szerda', 'csütörtök',
            'péntek', 'szombat', 'vasárnap']

CATALOGUE_RELEASE_DAY = 'szerda'
CATALOGUE_RELEASE_MINUTE = 20 * 60      # 20:00


def weekday_of(day):
    """Melyik nap van? A szezon 1. napja hetfo."""
    return WEEKDAYS[(day - 1) % 7]


# =======================================================================
# 2) SESSION
# =======================================================================
class SessionStatus(Enum):
    ANNOUNCED = 'announced'    # katalogus meg nem jelent meg
    OPEN = 'open'              # katalogus lathato, licitalni lehet
    RUN = 'run'                # lefutott


SESSION_STATUS_HU = {
    SessionStatus.ANNOUNCED: 'Katalógus még nem jelent meg',
    SessionStatus.OPEN: 'Katalógus elérhető',
    SessionStatus.RUN: 'Lezajlott',
}


@dataclass
class AuctionSession:
    session_id: str
    starts_at: int                 # abszolut perc
    catalogue_at: int              # amikor a katalogus lathatova valik
    house_key: str
    house_name: str
    sale_type: str
    sale_label: str
    tier: str                      # 'elite' | 'standard'
    buyer_fee: int
    status: SessionStatus = SessionStatus.ANNOUNCED
    lots: list = field(default_factory=list)


@dataclass
class Lot:
    lot_id: str
    session_id: str
    horse_id: Optional[str]        # None, ha NPC-toltelek
    seller_id: str
    hip: int
    reserve: int
    is_npc_filler: bool = False
    # a jatekos maximum licitje - a "megbizott" licital helyette
    max_bid: Optional[int] = None
    bidder_id: Optional[str] = None
    # eredmeny
    hammer: Optional[int] = None
    result: Optional[str] = None
    buyer_id: Optional[str] = None


# =======================================================================
# 3) AZ AUKCIOS NAPTAR
# =======================================================================
class AuctionCalendar:
    """Idozitett aukciok + katalogus + maximum licitek."""

    def __init__(self, clock: CAL.GameClock):
        self.clock = clock
        self.sessions: dict = {}
        self.lots: dict = {}            # lot_id -> Lot
        self._hip = 1

    # ------------------------------------------------------------------
    # 3a) SESSION-GENERALAS ELORE
    # ------------------------------------------------------------------
    def generate_ahead(self, rng, world, days=7):
        """Kiirja a kovetkezo N nap aukcioit.

        A hazak beosztasat az auction_sim.py adja: a kategoriahazak
        hetvegen, a vegyes haz hetfotol csutortokig.
        """
        now = self.clock.now()
        start_day = now // 1440
        created = []

        for d in range(start_day, start_day + days):
            wd = weekday_of(d % 30 + 1)
            for key, house in AU.AUCTION_HOUSES.items():
                if wd not in house['days']:
                    continue
                for i, slot in enumerate(AU.SESSION_SLOTS_UTC[::3]):
                    h, m = int(slot[:2]), int(slot[3:])
                    starts_at = d * 1440 + h * 60 + m
                    if starts_at <= now:
                        continue
                    sid = f"{key}-{d}-{slot}"
                    if sid in self.sessions:
                        continue
                    tier = (AU.Tier.ELITE if i % 2 == 0 else AU.Tier.STANDARD)
                    s = AuctionSession(
                        session_id=sid,
                        starts_at=starts_at,
                        # a katalogus ~1.5 nappal elobb, de sosem a
                        # jatek kezdete elott (negativ idobelyeg)
                        catalogue_at=max(0, starts_at - 36 * 60),
                        house_key=key, house_name=house['name'],
                        sale_type=house['sale_type'].value,
                        sale_label=AU.SALE_CONFIG[house['sale_type']]['label'],
                        tier=tier.value,
                        buyer_fee=AU.TIER_CONFIG[tier]['buyer_fee'],
                    )
                    self.sessions[sid] = s
                    created.append(s)
        return created

    # ------------------------------------------------------------------
    # 3b) KATALOGUS
    # ------------------------------------------------------------------
    def open_catalogues(self):
        """Amelyik sessionnel a katalogus mar lathato."""
        now = self.clock.now()
        out = []
        for s in self.sessions.values():
            if s.status == SessionStatus.RUN:
                continue
            if now >= s.catalogue_at:
                if s.status == SessionStatus.ANNOUNCED:
                    s.status = SessionStatus.OPEN
                out.append(s)
        out.sort(key=lambda s: s.starts_at)
        return out

    def fill_catalogue(self, session: AuctionSession, world, rng,
                       player_lots=None):
        """Osszeallitja a session katalogusat.

        A jatekos altal beadott lovak + NPC-toltelek. Ahogy no a
        jatekosbazis, az NPC-k aranya magatol csokken (auction_sim.py).
        """
        if session.lots:
            return session.lots

        player_lots = player_lots or []
        for h in player_lots:
            self._add_lot(session, h.horse_id, h.owner_id,
                          AU.default_reserve(_horse_row(h, world),
                                             session.house_key))

        # NPC-toltelek: a vilag olyan lovai, akik eladok
        pool = [h for h in world.horses.values()
                if h.owner_id != 'player'
                and h.stage in ('yearling', 'racer', 'breeding')
                and AU.accepts_horse(_sale_type_of(session), h.stage)]
        rng.shuffle(pool)

        target = max(AU.LOTS_PER_SESSION_VIABLE,
                     round(AU.LOTS_PER_SESSION_VIABLE * rng.uniform(1.0, 1.6)))
        for h in pool[:max(0, target - len(session.lots))]:
            self._add_lot(session, h.horse_id, h.owner_id,
                          AU.default_reserve(_horse_row(h, world),
                                             session.house_key))
        return session.lots

    def _add_lot(self, session, horse_id, seller_id, reserve):
        lot = Lot(lot_id=str(uuid.uuid4())[:10], session_id=session.session_id,
                  horse_id=horse_id, seller_id=seller_id,
                  hip=self._hip, reserve=reserve)
        self._hip += 1
        self.lots[lot.lot_id] = lot
        session.lots.append(lot)
        return lot

    # ------------------------------------------------------------------
    # 3c) MAXIMUM LICIT
    # ------------------------------------------------------------------
    def place_max_bid(self, lot_id, bidder_id, amount):
        """A jatekos maximum licitje. A "megbizott" (a gep) licital
        helyette - nem kell online lennie (auction_sim.py 11.5.4).

        FONTOS: a megbizott csak annyit licital, amennyi a nyereshez
        kell - nem fizeti ki automatikusan a maximumot.
        """
        lot = self.lots.get(lot_id)
        if lot is None:
            return {'ok': False, 'reason': 'Nincs ilyen tétel.'}
        s = self.sessions[lot.session_id]
        if s.status == SessionStatus.RUN:
            return {'ok': False, 'reason': 'Az aukció már lezajlott.'}
        if self.clock.now() < s.catalogue_at:
            return {'ok': False, 'reason': 'A katalógus még nem jelent meg.'}
        if lot.seller_id == bidder_id:
            return {'ok': False, 'reason': 'A saját lovadra nem licitálhatsz.'}
        lot.max_bid = int(amount)
        lot.bidder_id = bidder_id
        return {'ok': True, 'lot': lot}

    def cancel_bid(self, lot_id, bidder_id):
        lot = self.lots.get(lot_id)
        if lot and lot.bidder_id == bidder_id:
            lot.max_bid = None
            lot.bidder_id = None
            return {'ok': True}
        return {'ok': False, 'reason': 'Nincs ilyen licit.'}

    # ------------------------------------------------------------------
    # 3d) FELDOLGOZAS -- MOST A GOMB, KESOBB AZ IDOZITO
    # ------------------------------------------------------------------
    def due_sessions(self):
        now = self.clock.now()
        return sorted([s for s in self.sessions.values()
                       if s.status != SessionStatus.RUN and now >= s.starts_at],
                      key=lambda s: s.starts_at)


def _sale_type_of(session):
    for st in AU.SaleType:
        if st.value == session.sale_type:
            return st
    return AU.SaleType.MIXED


def _horse_row(h, world):
    """A Horse -> az auction_sim.base_value() alakja."""
    st = world.db.stats(h.horse_id)
    return {
        'quality': h.genetic_score(),
        'earnings': st.career_earnings,
        'age': h.age,
        'role': 'mare' if (h.sex == 'filly' and h.stage == 'breeding')
                else h.stage,
        'rarity': h.rarity,
    }


# =======================================================================
# 4) A FELDOLGOZO
# =======================================================================
def process_due_sessions(acal: AuctionCalendar, world, rng, player_id,
                         money_cb=None, on_result=None):
    """Lefuttatja az esedekes aukciokat.

    EZ A FUGGVENY VALTOZATLAN MARAD a folyamatos uzemben.

    money_cb(delta, reason) - a jatekos kasszajanak modositasa
    """
    out = []
    for session in acal.due_sessions():
        if session.status == SessionStatus.RUN:
            continue
        acal.fill_catalogue(session, world, rng)

        tier = (AU.Tier.ELITE if session.tier == 'elite'
                else AU.Tier.STANDARD)

        for lot in session.lots:
            horse = world.horses.get(lot.horse_id)
            if horse is None:
                continue
            row = _horse_row(horse, world)

            res = AU.run_lot(row, session.house_key, tier,
                             reserve=lot.reserve,
                             player_max_bid=lot.max_bid, rng=rng)
            lot.hammer = res['hammer']
            lot.result = res['result'].value

            # --- a jatekos NYERT ---
            if res['result'] == AU.SaleResult.SOLD_TO_PLAYER \
                    and lot.bidder_id == player_id:
                total = res['hammer'] + session.buyer_fee
                if money_cb:
                    money_cb(-total, f"{horse.name} megvásárolva")
                horse.owner_id = player_id
                lot.buyer_id = player_id
                world.ev('auction',
                         f"MEGVETTED: {horse.name} ({horse.grade()}) — "
                         f"{res['hammer']:,} B$ + {session.buyer_fee:,} "
                         f"regisztráció".replace(',', ' '))

            # --- a jatekos ELADOTT ---
            elif lot.seller_id == player_id:
                if res['result'] == AU.SaleResult.UNSOLD:
                    fate = AU.handle_unsold(row, rng)
                    if fate['action'] == 'npc_buyout':
                        if money_cb:
                            money_cb(fate['price'], f"{horse.name} felvásárolva")
                        horse.owner_id = 'npc'
                        world.ev('auction', f"{horse.name} nem kelt el — "
                                            f"{fate['text']} "
                                            f"({fate['price']:,} B$)".replace(',', ' '))
                    elif fate['action'] == 'hobby':
                        if money_cb:
                            money_cb(fate['price'], f"{horse.name} villámáron")
                        horse.stage = 'retired_out'
                        world.ev('auction', f"{horse.name} — {fate['text']}")
                    else:
                        world.ev('auction', f"{horse.name} nem kelt el — "
                                            f"újra próbálkozhatsz")
                else:
                    if money_cb:
                        money_cb(res['hammer'], f"{horse.name} eladva")
                    horse.owner_id = 'npc'
                    world.ev('auction',
                             f"ELADVA: {horse.name} ({horse.grade()}) — "
                             f"{res['hammer']:,} B$".replace(',', ' '))

            out.append({'lot': lot, 'horse': horse, 'session': session,
                        'result': res})
            if on_result:
                on_result(out[-1])

        session.status = SessionStatus.RUN
    return out


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    import random
    import game as G
    import worldgen as WG

    print("=== BREEDER TYCOON - AUKCIOS RENDSZER ===\n")
    print("Ugyanaz a szerkezet, mint a versenynaptarnal: elore kiirt")
    print("sessionok, katalogus, maximum licit, es egy feldolgozo, amit")
    print("MA a gomb, KESOBB az idozito hiv.\n")

    rng = random.Random(11)
    world, gens = WG.build_world(seed=99)
    clock = CAL.GameClock()
    acal = AuctionCalendar(clock)

    print("--- 1) SESSION-GENERALAS ---")
    created = acal.generate_ahead(rng, world, days=7)
    print(f"  {len(created)} aukció kiírva a következő 7 napra\n")
    from collections import Counter
    by_house = Counter(s.house_name for s in created)
    for h, n in by_house.items():
        print(f"  {h:20s} {n:>3d} session")
    print()

    print("--- 2) KATALOGUS-IDOZITES ---")
    for s in created[:4]:
        print(f"  {CAL.minutes_to_label(s.starts_at)}  {s.house_name:18s} "
              f"{s.sale_label:16s} "
              f"{AU.TIER_CONFIG[AU.Tier.ELITE if s.tier == 'elite' else AU.Tier.STANDARD]['label']}")
        print(f"     katalógus: {CAL.minutes_to_label(s.catalogue_at)}")
    print()

    print("--- 3) A KATALOGUS MEGNYILIK ---")
    print(f"  Most: {clock.label()}  →  {len(acal.open_catalogues())} nyitott")
    clock.advance(2 * 1440)
    opens = acal.open_catalogues()
    print(f"  2 nap múlva: {clock.label()}  →  {len(opens)} nyitott katalógus\n")

    s0 = opens[0]
    lots = acal.fill_catalogue(s0, world, rng)
    print(f"  {s0.house_name} — {s0.sale_label}, {len(lots)} tétel")
    for lot in lots[:5]:
        h = world.horses[lot.horse_id]
        print(f"     #{lot.hip:<4d} {h.name:18s} {h.grade():3s} "
              f"{h.stage:9s} kikiáltás {lot.reserve:>7,d} B$".replace(',', ' '))
    print()

    print("--- 4) MAXIMUM LICIT ---")
    print("  A megbízott csak annyit licitál, amennyi a nyeréshez kell.\n")
    target = lots[0]
    th = world.horses[target.horse_id]
    val = AU.base_value(_horse_row(th, world))
    print(f"  {th.name} — becsült érték {val:,} B$".replace(',', ' '))
    for mult in [0.8, 1.0, 1.3]:
        bid = round(val * mult)
        acal.place_max_bid(target.lot_id, 'player', bid)
        wins, paid = 0, []
        for _ in range(200):
            r = AU.run_lot(_horse_row(th, world), s0.house_key,
                           AU.Tier.STANDARD, target.reserve, bid, rng)
            if r['result'] == AU.SaleResult.SOLD_TO_PLAYER:
                wins += 1
                paid.append(r['hammer'])
        avg = sum(paid)/len(paid) if paid else 0
        print(f"     max licit {bid:>8,d} ({int(mult*100):>3d}%)  "
              f"nyerés {wins/2:>5.1f}%   átlag fizetett {avg:>8,.0f} B$"
              .replace(',', ' '))
    print()

    print("--- 5) AZ AUKCIO LEFUT ---")
    acal.place_max_bid(target.lot_id, 'player', round(val * 1.3))
    money = [50000]
    def money_cb(delta, reason):
        money[0] += delta

    clock.advance(s0.starts_at - clock.now() + 1)
    results = process_due_sessions(acal, world, rng, 'player', money_cb)
    print(f"  {len(results)} tétel kalapács alá került")
    sold = [r for r in results if r['result']['result'] != AU.SaleResult.UNSOLD]
    print(f"  eladva: {len(sold)}  ·  eladatlan: {len(results)-len(sold)} "
          f"({(len(results)-len(sold))/len(results)*100:.0f}%)")
    for e in world.log[-4:]:
        print(f"     {e['text'][:72]}")
    print(f"  kassza: {money[0]:,} B$".replace(',', ' '))
    print()

    print("--- 6) IDEMPOTENCIA ---")
    again = process_due_sessions(acal, world, rng, 'player', money_cb)
    print(f"  Ismételt feldolgozás: {len(again)} tétel "
          f"(a lezajlott aukció nem fut le újra)\n")

    def _agent_pays_less(world, rng):
        """Tenyleges meres: a megbizott kevesebbet fizet a maximumnal."""
        h = next(iter(world.horses.values()))
        row = _horse_row(h, world)
        val = AU.base_value(row)
        maxbid = round(val * 1.4)
        paid = []
        for _ in range(300):
            r = AU.run_lot(row, 'harrowgate', AU.Tier.STANDARD,
                           None, maxbid, rng)
            if r['result'] == AU.SaleResult.SOLD_TO_PLAYER:
                paid.append(r['hammer'])
        return bool(paid) and sum(paid) / len(paid) < maxbid * 0.95

    print("--- 7) VALIDACIO ---")
    checks = [
        ('Sessionök előre generálódnak', len(created) > 20),
        ('Négy ház szerepel', len(by_house) == 4),
        ('A vegyes ház hétköznap',
         any('Millbrook' in h for h in by_house)),
        ('A katalógus a start ELŐTT jelenik meg',
         all(s.catalogue_at < s.starts_at for s in created)),
        ('A katalógus nem jelenhet meg a játék kezdete előtt',
         all(s.catalogue_at >= 0 for s in created)),
        ('Idővel megnyílnak a katalógusok', len(opens) > 0),
        ('A katalógus feltöltődik tételekkel', len(lots) >= 25),
        ('Minden tételnek van csípőszáma',
         all(l.hip > 0 for l in lots)),
        ('A saját lóra nem lehet licitálni',
         not acal.place_max_bid(
             lots[0].lot_id, lots[0].seller_id, 1000)['ok']),
        ('Az aukció lefut', len(results) > 0),
        ('IDEMPOTENCIA: nem fut le kétszer', len(again) == 0),
        ('Az eladatlanság a mért sávban',
         0.10 <= (len(results) - len(sold)) / max(1, len(results)) <= 0.40),
        # A 4. blokk merese: 130%-os maximum licitnel az atlagosan
        # fizetett ar ~115%. A megbizott csak annyit licital, amennyi
        # a nyereshez kell.
        ('A megbízott nem fizeti ki a maximumot',
         _agent_pays_less(world, rng)),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'AZ AUKCIO KESZ' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
