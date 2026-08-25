"""
Breeder Tycoon - Auction House Engine v1.0
=======================================================================
HAROM AUKCIOS HAZ, KET KATEGORIA, NEGY VASARTIPUS.

Ez valtja ki a claiming mechanikat (tul bonyolult egy atlag jatekosnak)
ES a kozos jatekos-piacteret (a kinalat mindig meghaladna a keresletet).

=======================================================================
A RENDSZER
=======================================================================

NEGY HAZ, MINDEGYIK EGY KATEGORIARA. Igy aki kancat keres, csak a
kancahaz katalogusat bongeszi - nem kell atnyalaznia mindent.

  Ashford & Vale   - Yearling         hetvege (pentek-szombat)
  Kingsmere Hall   - Versenylo        hetvege (pentek-szombat)
  Harrowgate       - Kanca            hetvege (pentek-szombat)
  Millbrook        - Vegyes           HETFOTOL CSUTORTOKIG, minden nap

IDOZITES:
  Szerda 20:00 -> a hetvegi katalogusok megjelennek
  Naponta tobb aukcio indul, IDOZONAK SZERINT szetteritve. Egy europai
  jatekos hajnalban is licitalhat egy masik idozona sessionjen -
  hetvegen ez akar egesz napos program is lehet.

TETELSZAM:
  Egy session 80-100 tetel korul, DE NEM FIX SZAM. A tenyleges
  mennyiseg a jatekosok altal beadott lovaktol fugg; ha keves jon
  ossze, NPC-lovakkal toltjuk fel. A SESSIONOK SZAMA is a kinalattol
  fugg - de van egy minimum az idozona-lefedettseg miatt.

KET KATEGORIA minden vasartipuson belul:
  ELIT      - A es B fokozatu lovak, magasabb regisztracios dij
  STANDARD  - C, D, E fokozatu lovak

DIJAK:
  - Az ELADO NEM fizet semmit (elteres a valosagtol - ott a Keeneland
    1000 dollaros nevezesi dijat ker az eladotol).
  - A VEVO regisztracios dijat fizet: 1000 (standard) / 3000 (elit).
  - NINCS jutalek. Jatekrol van szo.

LICITALAS:
  - A jatekos licitalhat elore (maximum licit), es a "megbizottja"
    (a gep) licital helyette. Igy nem kell online lennie.
  - NPC LICITALOK biztositjak a likviditast: egy jo lo gyenge
    licit-idoszakban is jo penzert megy el.

ELADATLANSAG:
  - Cel: 15-20%. Ez TUDATOSAN MEGENGEDOBB a valosagnal (ott 26-34%).
  - Amit a jatekosok nem vesznek meg, azt az NPC felvasarolja.
  - A maradek hobbilonak megy (2500), vagy a jatekos ujra probalkozik.
  - Ez nem torzitja a rendszert: amit senki nem vesz meg, az gyenge lo,
    tehat sem a tenyesztoi premiumban, sem az NPC-versenyzesben nem fog
    kiugro szamokat termelni.

=======================================================================
FORRASOK
=======================================================================

1. Keeneland dijszerkezet: nevezesi dij 1000 USD lovankent a harom
   hagyomanyos vasarra, a digitalis eladason 300 USD, 5% jutalek.
   -> A JATEKBAN MEGFORDITVA: az elado nem fizet, a vevo igen.
   https://www.thoroughbreddailynews.com/keeneland-restructuring-commission-scale/
   https://www.keeneland.com/sales/keeneland-digital-sales-ring

2. RNA (Reserve Not Attained) arany a valosagban: Keeneland September
   2020: 26.4% (825 yearling nem kelt el 3922-bol); Fasig-Tipton
   Selected Yearlings Showcase: 33.7% (177 lo 348-bol).
   -> A jatekban 15-20%-ra allitva, tudatosan megengedobben.
   https://www.bloodhorse.com/horse-racing/articles/243688/eatons-mcdonald-assesses-fasig-tipton-keeneland-sales

3. Piac-polarizacio (valos jelenseg, amit a ket kategoria lekepez):
   "you have a strong upper and strong upper middle and then when you
   get to the bottom part of the market, there just isn't a [buyer]".
   -> Ezert kulon ELIT es STANDARD aukcio.
   https://www.thoroughbreddailynews.com/keeneland-restructuring-commission-scale/

4. Katalogus-konvenciok (black type, csiposzam): lasd listing_sim.py
   forrasait - Keeneland/Fasig-Tipton, ICSC 1981.
"""

import random
import statistics
from enum import Enum
from collections import Counter

random.seed(42)


# =======================================================================
# 1) FOKOZATOK ES KATEGORIAK
# =======================================================================
GRADE_ORDER = ['E', 'D', 'C', 'B-', 'B', 'B+', 'A-', 'A', 'A+']

ELITE_GRADES = {'B', 'B+', 'A-', 'A', 'A+'}   # a jatekos dontese: A es B savok


class Tier(Enum):
    ELITE = 'elite'
    STANDARD = 'standard'


TIER_CONFIG = {
    Tier.ELITE: {
        'label': 'Elit aukció',
        'buyer_fee': 3000,
        'note': 'A és B fokozatú lovak.',
    },
    Tier.STANDARD: {
        'label': 'Standard aukció',
        'buyer_fee': 1000,
        'note': 'C, D és E fokozatú lovak.',
    },
}


def tier_for_grade(grade):
    return Tier.ELITE if grade in ELITE_GRADES else Tier.STANDARD


# =======================================================================
# 2) VASARTIPUSOK - a szezon hetei szerint
# =======================================================================
class SaleType(Enum):
    YEARLING = 'yearling'
    RACEHORSE = 'racehorse'
    BROODMARE = 'broodmare'
    MIXED = 'mixed'


# A hazak MAR NEM hetek szerint valtakoznak - mindegyik a sajat
# kategoriajaval mukodik, folyamatosan. Igy aki kancat keres, mindig
# tudja, hova menjen.
SALE_CONFIG = {
    SaleType.YEARLING:  {'label': 'Yearling-vásár',  'accepts': ['yearling']},
    SaleType.RACEHORSE: {'label': 'Versenyló-vásár', 'accepts': ['racer', 'two_year_old']},
    SaleType.BROODMARE: {'label': 'Kancavásár',      'accepts': ['mare']},
    SaleType.MIXED:     {'label': 'Vegyes vásár',    'accepts': None},   # NINCS megkotes
}


def accepts_horse(sale_type, horse_role):
    accepts = SALE_CONFIG[sale_type]['accepts']
    return accepts is None or horse_role in accepts


# =======================================================================
# 3) A HAROM AUKCIOS HAZ
# =======================================================================
# Kulonbozo idopontok: senki ne maradjon le. A hazak jellege is elter -
# ez a valos piac-polarizaciot kepezi le (forras 3.).
AUCTION_HOUSES = {
    'ashford': {
        'name': 'Ashford & Vale',
        'sale_type': SaleType.YEARLING,
        'character': 'A yearling-piac rangos háza. Erős vevőkör, magasabb árak.',
        'days': ['péntek', 'szombat'],
        'price_factor': 1.12,
        'bidder_depth': 1.25,
    },
    'kingsmere': {
        'name': 'Kingsmere Hall',
        'sale_type': SaleType.RACEHORSE,
        'character': 'Kész versenylovak és nyers kétévesek háza.',
        'days': ['péntek', 'szombat'],
        'price_factor': 1.06,
        'bidder_depth': 1.15,
    },
    'harrowgate': {
        'name': 'Harrowgate',
        'sale_type': SaleType.BROODMARE,
        'character': 'Tenyészkancák és tenyészállatok háza.',
        'days': ['péntek', 'szombat'],
        'price_factor': 1.00,
        'bidder_depth': 1.00,
    },
    'millbrook': {
        'name': 'Millbrook',
        'sale_type': SaleType.MIXED,
        'character': 'Vegyes vásár — nincs megkötés. Hétfőtől csütörtökig, minden nap.',
        'days': ['hétfő', 'kedd', 'szerda', 'csütörtök'],
        'price_factor': 0.92,
        'bidder_depth': 0.90,
    },
}


def house_for_sale(sale_type):
    for k, h in AUCTION_HOUSES.items():
        if h['sale_type'] == sale_type:
            return k
    return 'millbrook'


CATALOGUE_RELEASE = 'szerda 20:00 (a hétvégi vásárokra)'


# =======================================================================
# 3b) SESSIONOK - idozona-lefedettseg + dinamikus tetelszam
# =======================================================================
# A JATEKOS DONTESE: egy session 80-100 tetel korul, de NEM FIX SZAM.
# A sessionok szama a kinalattol fugg - de van egy MINIMUM, hogy minden
# idozonabol elerheto legyen legalabb egy.
LOTS_PER_SESSION_TARGET = 90     # a 80-100-as sav kozepe, ha van eleg kinalat
LOTS_PER_SESSION_MAX = 100
LOTS_PER_SESSION_VIABLE = 25     # ez alatt mar nem aukcio, hanem lista
MIN_SESSIONS_PER_DAY = 4         # idozona-lefedettseg miatt
MAX_SESSIONS_PER_DAY = 12

# UTKOZES ES FELOLDASA: a 4 session minimuma (idozona-lefedettseg) es a
# 80-100 tetel/session cel keves lonal nem fer ossze. A jatekos
# prioritasa egyertelmu volt: "nem szeretnem, ha lemaradna valaki" -
# ezert az IDOZONA-LEFEDETTSEG NYER, es korai szakaszban kisebb
# sessionokat fogadunk el. A katalogus feltoltese gondoskodik rola,
# hogy meg ezek is eletkepes meretuek legyenek.
MIN_VIABLE_CATALOGUE = MIN_SESSIONS_PER_DAY * LOTS_PER_SESSION_VIABLE   # = 100

# Oradnkenti inditas, a nap folyaman szetteritve (UTC). Egy europai
# jatekos hajnalban is talal sessiont egy masik idozona idejeben.
SESSION_SLOTS_UTC = ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00',
                     '12:00', '14:00', '16:00', '18:00', '20:00', '22:00']

TIMEZONE_HINT = {
    '00:00': 'Ázsia/Óceánia délelőtt', '02:00': 'Ázsia délelőtt',
    '04:00': 'Ázsia délután', '06:00': 'Európa reggel',
    '08:00': 'Európa délelőtt', '10:00': 'Európa dél',
    '12:00': 'Európa délután', '14:00': 'Amerika reggel',
    '16:00': 'Amerika délelőtt', '18:00': 'Európa este / Amerika dél',
    '20:00': 'Amerika délután', '22:00': 'Amerika este',
}


def sessions_needed(lot_count):
    """Hany session kell ennyi tetelhez? A kinalat hatarozza meg, de a
    minimum az idozona-lefedettseget biztositja."""
    by_supply = -(-lot_count // LOTS_PER_SESSION_TARGET)   # felfele kerekites
    return max(MIN_SESSIONS_PER_DAY, min(MAX_SESSIONS_PER_DAY, by_supply))


def build_sessions(house_key, day, lot_count, rng=random):
    """Egy nap sessionjei egy hazban. A tetelek szetosztasa NEM egyenlo -
    kis szoras, hogy ne legyen gepies."""
    n = sessions_needed(lot_count)
    # egyenletesen szetteritett idopontok
    step = max(1, len(SESSION_SLOTS_UTC) // n)
    slots = SESSION_SLOTS_UTC[::step][:n]

    sessions = []
    remaining = lot_count
    for i, slot in enumerate(slots):
        last = (i == len(slots) - 1)
        if last:
            lots = remaining
        else:
            target = round(lot_count / n * rng.uniform(0.88, 1.12))
            lots = max(0, min(remaining - (len(slots) - i - 1), target))
        remaining -= lots
        sessions.append({
            'house': AUCTION_HOUSES[house_key]['name'],
            'day': day,
            'time_utc': slot,
            'timezone_hint': TIMEZONE_HINT[slot],
            'lots': lots,
            'tier': Tier.ELITE if i % 2 == 0 else Tier.STANDARD,
        })
    return sessions


# =======================================================================
# 3c) TETEL-FELTOLTES: ha keves a jatekos-lo, NPC-vel toltunk fel
# =======================================================================
# A JATEKOS DONTESE: kezdetben szinte minden tetel NPC-lo lesz. Ahogy no
# a jatekosbazis, egyre tobb a valodi lo, es az NPC-k aranya csokken.
# A rendszernek MINDKET szelsoseget kezelnie kell.
def fill_catalogue(player_lots, rng=random):
    """Osszeallitja egy nap katalogusat: a jatekos-lovak + NPC-toltelek.

    Visszaadja a teljes tetelszamot es az NPC-aranyt - ez utobbi
    jelzi, mennyire eleszt mar a piac.
    """
    n_player = len(player_lots)

    # a cel tetelszam a kinalathoz igazodik, de van also/felso hatar
    if n_player >= MIN_VIABLE_CATALOGUE:
        # van eleg valodi lo - a sessionok szama no, nem a toltelek
        total = n_player
        n_npc = 0
    else:
        # keves a valodi lo - feltoltjuk az eletkepes minimumig
        total = max(MIN_VIABLE_CATALOGUE,
                    round(MIN_VIABLE_CATALOGUE * rng.uniform(1.0, 1.25)))
        n_npc = total - n_player

    return {
        'total_lots': total,
        'player_lots': n_player,
        'npc_lots': n_npc,
        'npc_share_pct': round(n_npc / total * 100, 1) if total else 0,
    }


# =======================================================================
# 4) A LO BECSULT ERTEKE
# =======================================================================
def base_value(horse):
    """A lo alapertek-becslese. Ugyanaz a logika, mint a tobbi modulban."""
    q = horse.get('quality', 55)          # 0-99 osszesitett kepesseg
    earnings = horse.get('earnings', 0)
    age = horse.get('age', 3)
    role = horse.get('role', 'yearling')

    val = max(600, (q - 38) ** 2.1 * 7)
    val += earnings * 0.3

    if role == 'mare':
        val *= 1.25          # tenyeszertek
    if age > 6:
        val *= max(0.4, 1.0 - (age - 6) * 0.10)

    # ritka szin felar - a monetizacios reteg (breeding_sim rarity_tier)
    rarity = horse.get('rarity', 'common')
    val *= {'common': 1.0, 'uncommon': 1.08, 'rare': 1.25, 'special': 1.6}.get(rarity, 1.0)

    return round(val)


# =======================================================================
# 5) LICITALOK
# =======================================================================
# NPC LICITALOK: biztositjak, hogy egy jo lo gyenge licit-idoszakban is
# jo penzert menjen el. Enelkul a hajnali aukcio ertektelenne tenne a
# jo lovakat.
NPC_VALUATION_NOISE = 0.20


def npc_bidder_pool(horse, house_key, tier, rng=random):
    """Hany NPC licital, es mennyit ernek nekik?"""
    house = AUCTION_HOUSES[house_key]
    val = base_value(horse)

    # az elit aukcion melyebb a vevokor
    depth = house['bidder_depth'] * (1.35 if tier == Tier.ELITE else 1.0)
    n = max(1, round(rng.gauss(3.2 * depth, 1.1)))

    bidders = []
    for _ in range(n):
        est = val * rng.gauss(1.0, NPC_VALUATION_NOISE) * house['price_factor']
        bidders.append(max(400, round(est)))
    return bidders


# =======================================================================
# 6) AZ AUKCIO LEFUTTATASA
# =======================================================================
# Angol (emelkedo) aukcio: az ar addig no, amig egy licitalo marad.
# A gyoztes nagyjabol a MASODIK legmagasabb ertekelest fizeti.
BID_INCREMENT = 0.06     # 6%-os lepesek


class SaleResult(Enum):
    SOLD_TO_PLAYER = 'sold_to_player'
    SOLD_TO_NPC = 'sold_to_npc'
    UNSOLD = 'unsold'


def run_lot(horse, house_key, tier, reserve=None, player_max_bid=None, rng=random):
    """Egy tetel lefuttatasa.

    player_max_bid: a jatekos MAXIMUM LICITJE. A "megbizottja" (a gep)
    licital helyette - nem kell online lennie.
    """
    bidders = npc_bidder_pool(horse, house_key, tier, rng)
    all_bids = list(bidders)
    if player_max_bid:
        all_bids.append(player_max_bid)

    all_bids.sort(reverse=True)
    top = all_bids[0]
    second = all_bids[1] if len(all_bids) > 1 else round(top * 0.75)

    # a leutesi ar a masodik legmagasabb ertekeles + egy lepes
    hammer = min(top, round(second * (1 + BID_INCREMENT)))

    if reserve is not None and hammer < reserve:
        return {'result': SaleResult.UNSOLD, 'hammer': hammer, 'reserve': reserve,
                'bidders': len(all_bids)}

    player_won = bool(player_max_bid) and player_max_bid >= top
    return {
        'result': SaleResult.SOLD_TO_PLAYER if player_won else SaleResult.SOLD_TO_NPC,
        'hammer': hammer,
        'reserve': reserve,
        'bidders': len(all_bids),
        'buyer_fee': TIER_CONFIG[tier]['buyer_fee'],
    }


# =======================================================================
# 7) ELADATLANSAG KALIBRALASA (cel: 15-20%)
# =======================================================================
# A kikialtasi ar (reserve) az elado dontese. Ha tul magasra teszi,
# nem kel el. A rendszer alapertelmezese ugy van beallitva, hogy az
# eladatlansag a celsavba essen.
DEFAULT_RESERVE_FACTOR = 0.96   # empirikusan hangolva: ezzel az eladatlansag
                                # a celzott 15-20% savba esik


def default_reserve(horse, house_key):
    """Az alapertelmezett kikialtasi ar - a jatekos felulirhatja."""
    return round(base_value(horse) * AUCTION_HOUSES[house_key]['price_factor']
                 * DEFAULT_RESERVE_FACTOR)


# =======================================================================
# 8) AMI NEM KELT EL
# =======================================================================
HOBBY_PRICE = 2500     # villamar - barmikor, azonnal


def handle_unsold(horse, rng=random):
    """Amit a jatekosok nem vettek meg, azt az NPC felvasarolja; a
    maradek hobbilonak megy, vagy a jatekos ujra probalkozik."""
    val = base_value(horse)
    # az NPC a valos ertek alatt vasarol fel
    if rng.random() < 0.65:
        return {'action': 'npc_buyout', 'price': round(val * 0.72),
                'text': 'Az NPC-piac felvásárolta.'}
    if val < HOBBY_PRICE * 1.6:
        return {'action': 'hobby', 'price': HOBBY_PRICE,
                'text': f'Hobbilónak eladva ({HOBBY_PRICE} B$).'}
    return {'action': 'retry', 'price': 0,
            'text': 'Nem kelt el — a következő vásáron újra próbálkozhatsz.'}


def quick_sale():
    """Villamar: barmikor, azonnal, kerdes nelkul."""
    return {'price': HOBBY_PRICE,
            'text': f'Villámár — {HOBBY_PRICE} B$, azonnali kifizetés, '
                    f'a ló hobbilóként folytatja.'}


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - AUCTION HOUSE ENGINE v1.0 ===\n")

    print("--- 1) A NEGY HAZ ---")
    print(f"  Katalógusok: {CATALOGUE_RELEASE}\n")
    for k, h in AUCTION_HOUSES.items():
        days = ', '.join(h['days'])
        print(f"  {h['name']:18s} {SALE_CONFIG[h['sale_type']]['label']:16s} {days}")
        print(f"     {h['character']}")
        print(f"     ár-szorzó {h['price_factor']:.2f}  ·  vevőkör {h['bidder_depth']:.2f}×")
    print("\n  -> Aki kancát keres, csak a Harrowgate katalógusát böngészi.\n")

    print("--- 2) SESSIONOK: a kinalat hatarozza meg a szamukat ---")
    print(f"  Cél tételszám sessiononként: {LOTS_PER_SESSION_TARGET} "
          f"(max {LOTS_PER_SESSION_MAX}, nem fix szám)")
    print(f"  Minimum {MIN_SESSIONS_PER_DAY} session naponta — időzóna-lefedettség miatt")
    print(f"  Életképes minimum katalógus: {MIN_VIABLE_CATALOGUE} tétel\n")
    for lots in [100, 200, 360, 700, 1400]:
        n = sessions_needed(lots)
        print(f"  {lots:>4d} tétel -> {n:>2d} session  ({lots/n:>5.1f} tétel/session)")
    print()

    print("--- 3) EGY NAP MENETRENDJE (Harrowgate, 320 tetel) ---")
    rng = random.Random(5)
    for sess in build_sessions('harrowgate', 'péntek', 320, rng):
        print(f"  {sess['time_utc']} UTC  {TIER_CONFIG[sess['tier']]['label']:16s} "
              f"{sess['lots']:>3d} tétel   ({sess['timezone_hint']})")
    print("\n  -> Egy európai játékos hajnalban is talál sessiont — hétvégén")
    print("     ez akár egész napos program is lehet.\n")

    print("--- 3b) KATALOGUS-FELTOLTES: jatekos-lovak vs NPC ---")
    print("  Ahogy nő a játékosbázis, az NPC-k aránya csökken:\n")
    rng = random.Random(9)
    for n_player in [0, 30, 70, 120, 400]:
        f = fill_catalogue([None]*n_player, rng)
        bar = '#' * round(f['npc_share_pct']/100*24)
        print(f"  {n_player:>3d} játékos-ló -> {f['total_lots']:>3d} tétel, "
              f"ebből NPC {f['npc_lots']:>3d} ({f['npc_share_pct']:>5.1f}%)  {bar}")
    print()

    print("--- 4) UGYANAZ A LO, KULONBOZO HAZAKBAN ---")
    horse = {'name': 'Ashridge', 'quality': 68, 'earnings': 4000, 'age': 1,
             'role': 'yearling', 'rarity': 'common'}
    print(f"  {horse['name']} — becsült alapérték: {base_value(horse):,} B$\n".replace(',',' '))
    rng = random.Random(11)
    for k, h in AUCTION_HOUSES.items():
        prices = []
        for _ in range(300):
            r = run_lot(horse, k, Tier.ELITE, reserve=None, rng=rng)
            prices.append(r['hammer'])
        print(f"  {h['name']:16s} átlag {statistics.mean(prices):>8,.0f} B$   "
              f"medián {statistics.median(prices):>8,.0f} B$".replace(',',' '))
    print()

    print("--- 5) MAXIMUM LICIT — a megbizott licital helyetted ---")
    rng = random.Random(7)
    val = base_value(horse)
    print(f"  {horse['name']}, becsült érték {val:,} B$\n".replace(',',' '))
    for mult in [0.7, 0.9, 1.1, 1.4]:
        maxbid = round(val * mult)
        wins = 0; paid = []
        for _ in range(400):
            r = run_lot(horse, 'harrowgate', Tier.ELITE, None, maxbid, rng)
            if r['result'] == SaleResult.SOLD_TO_PLAYER:
                wins += 1; paid.append(r['hammer'])
        avg = statistics.mean(paid) if paid else 0
        print(f"  max licit {maxbid:>8,d} B$ ({int(mult*100)}%)  ->  "
              f"nyerés {wins/4:>5.1f}%   átlagos fizetett ár {avg:>8,.0f} B$".replace(',',' '))
    print("\n  -> A megbízott csak annyit licitál, amennyi a nyeréshez kell —")
    print("     nem a maximumot fizeted ki automatikusan.\n")

    print("--- 6) ELADATLANSAG KALIBRACIO (cel: 15-20%) ---")
    rng = random.Random(2024)
    N = 6000
    results = Counter()
    for _ in range(N):
        h = {'quality': rng.uniform(38, 88), 'earnings': rng.uniform(0, 30000),
             'age': rng.randint(1, 9), 'role': rng.choice(['yearling','racer','mare']),
             'rarity': 'common'}
        house = rng.choice(list(AUCTION_HOUSES.keys()))
        grade = 'B' if h['quality'] >= 63 else 'C'
        tier = tier_for_grade(grade)
        res = run_lot(h, house, tier, default_reserve(h, house), None, rng)
        results[res['result']] += 1
    unsold = results[SaleResult.UNSOLD]/N*100
    print(f"  {N} tétel, alapértelmezett kikiáltási árral:")
    print(f"     eladva:     {(N-results[SaleResult.UNSOLD])/N*100:5.1f}%")
    print(f"     eladatlan:  {unsold:5.1f}%   (cél: 15-20%, valós RNA: 26-34%)\n")

    print("--- 7) AMI NEM KELT EL ---")
    rng = random.Random(3)
    outcomes = Counter()
    for _ in range(2000):
        h = {'quality': rng.uniform(38, 70), 'earnings': 0, 'age': 2,
             'role': 'yearling', 'rarity': 'common'}
        outcomes[handle_unsold(h, rng)['action']] += 1
    labels = {'npc_buyout': 'NPC felvásárolta', 'hobby': 'Hobbilónak ment',
              'retry': 'Újra próbálkozik'}
    for k, v in outcomes.most_common():
        print(f"  {labels[k]:22s} {v/2000*100:5.1f}%")
    print()

    print("--- 8) VILLAMAR ---")
    q = quick_sale()
    print(f"  {q['text']}\n")

    print("--- 9) VALIDACIO ---")
    rng = random.Random(99)
    good = {'quality': 82, 'earnings': 20000, 'age': 3, 'role': 'racer', 'rarity': 'common'}
    poor = {'quality': 44, 'earnings': 0, 'age': 8, 'role': 'racer', 'rarity': 'common'}
    rare = {'quality': 68, 'earnings': 4000, 'age': 1, 'role': 'yearling', 'rarity': 'special'}

    ash = statistics.mean(run_lot(good,'ashford',Tier.ELITE,None,None,rng)['hammer'] for _ in range(300))
    mil = statistics.mean(run_lot(good,'millbrook',Tier.ELITE,None,None,rng)['hammer'] for _ in range(300))

    checks = [
        ('A és B fokozat az elit aukcióra kerül',
         tier_for_grade('A') == Tier.ELITE and tier_for_grade('B') == Tier.ELITE),
        ('C, D, E a standard aukcióra',
         all(tier_for_grade(g) == Tier.STANDARD for g in ['C','D','E'])),
        ('Az elit regisztráció 3000, a standard 1000',
         TIER_CONFIG[Tier.ELITE]['buyer_fee'] == 3000
         and TIER_CONFIG[Tier.STANDARD]['buyer_fee'] == 1000),
        ('Négy ház van, kategóriánként egy',
         len(AUCTION_HOUSES) == 4
         and len({h['sale_type'] for h in AUCTION_HOUSES.values()}) == 4),
        ('A vegyes ház hétfőtől csütörtökig működik',
         AUCTION_HOUSES['millbrook']['days'] == ['hétfő','kedd','szerda','csütörtök']),
        ('A kategóriás házak hétvégén',
         all(AUCTION_HOUSES[k]['days'] == ['péntek','szombat']
             for k in ['ashford','kingsmere','harrowgate'])),
        ('A vegyes vásár mindent elfogad',
         accepts_horse(SaleType.MIXED, 'mare') and accepts_horse(SaleType.MIXED, 'yearling')),
        ('A yearling-vásár nem fogad kancát',
         not accepts_horse(SaleType.YEARLING, 'mare')),
        ('A tételszám NEM fix — a kínálat határozza meg',
         sessions_needed(40) != sessions_needed(700)),
        ('Minden nap legalább 4 session (időzóna-lefedettség)',
         sessions_needed(1) >= MIN_SESSIONS_PER_DAY),
        ('Sok tétel esetén sem lépi túl a napi maximumot',
         sessions_needed(5000) <= MAX_SESSIONS_PER_DAY),
        ('A sessionök különböző időpontokban indulnak',
         len({s['time_utc'] for s in build_sessions('harrowgate','péntek',320,random.Random(1))}) >= 4),
        ('Kevés játékos-ló esetén NPC tölti fel',
         fill_catalogue([], random.Random(1))['npc_share_pct'] > 90),
        ('Sok játékos-ló esetén nincs NPC-töltelék',
         fill_catalogue([None]*300, random.Random(1))['npc_lots'] == 0),
        ('Minden session életképes méretű',
         all(sess['lots'] >= LOTS_PER_SESSION_VIABLE * 0.8
             for sess in build_sessions('harrowgate','péntek',
                                        MIN_VIABLE_CATALOGUE, random.Random(1)))),
        ('A rangosabb ház magasabb árat hoz', ash > mil * 1.10),
        ('Az eladatlanság a 15-20%-os célsávban', 15.0 <= unsold <= 20.0),
        ('A ritka szín érdemben többet ér',
         base_value(rare) > base_value({**rare, 'rarity':'common'}) * 1.5),
        ('Gyenge ló is elkel valamennyiért',
         run_lot(poor,'millbrook',Tier.STANDARD,None,None,rng)['hammer'] > 0),
        ('A villámár fix 2500', quick_sale()['price'] == 2500),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - HANGOLANDO'} ===")
