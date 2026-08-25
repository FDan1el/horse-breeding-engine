"""
Breeder Tycoon - Daily Marketplace Engine v1.0
=======================================================================
NAPI PIACTER. Teljesen kulonallo az aukcioktol (auction_sim.py) -
semmi koze hozzajuk.

A jatek 24 orankent general megveheto lovakat, JATEKOSONKENT ELTERO
osszeallitasban. Csak NPC-lovak, nem jatekos altal tenyesztettek.

HAROM CELJA VAN:

  1. GENETIKAI FRISSITES - egy zart populacioban az inbreeding
     felhalmozodik. A piacter friss, ROKONSAG NELKULI vervonalat
     injektal. Ez nem csak bolt, hanem a genallomany karbantartasa.

  2. VERVONAL-FRISSITES - a jatekos hozzafer olyan csaladokhoz, amik
     nincsenek meg az allomanyaban.

  3. KULONLEGES SZINEK - a monetizacio fo pontja. A ritka szinek
     (szurke, fekete, palomino) a szingenetikai motorban (breeding_sim.py)
     szandekosan extremen ritkak - itt viszont celzottan vasarolhatok.

=======================================================================
MONETIZACIOS ELV (GDD 21.8-cal osszhangban)
=======================================================================
Ami MECHANIKAI ELONYT ad, jatekbeli penzert.
Ami CSAK KINEZET, az mehet valodi penzert.

A piacteren ez igy bomlik:
  - B es C kanca            -> jatekbeli penz
  - B+ kanca                -> valodi penz  (ez HATARESET, lasd lent)
  - kulonleges szinu lovak  -> valodi penz  (tisztan kozmetikai)

HATARESET-JELZES: a B+ kanca MECHANIKAI elonyt ad (jobb genetika),
tehat szigoruan veve serti a fenti elvet. Ez TUDATOS engedmeny -
de erdemes tudni, hogy ez az egyetlen pont, ahol a jatek pay-to-win
iranyba mozdul. Ellensulyozza:
  - a B+ kanca elerheto jatekbeli penzert is (aukcion, 11.5)
  - a vervonal-epites hosszu tavon felulmulja a vasarolt kancat
    (season.html meres: a Kancabefekteto strategia nem dominal)
"""

import random
from enum import Enum

random.seed(42)


# =======================================================================
# 1) A NAPI AJANLAT SZERKEZETE
# =======================================================================
REFRESH_HOURS = 24
OFFERS_PER_DAY = 6          # jatekosonkent ennyi lo jelenik meg


class Currency(Enum):
    GAME = 'game'           # jatekbeli B$
    PREMIUM = 'premium'     # valodi penz


class OfferTier(Enum):
    MARE_C = 'mare_c'
    MARE_B = 'mare_b'
    MARE_BPLUS = 'mare_bplus'
    RARE_COLOUR = 'rare_colour'


# A napi ajanlat osszetetele. A tobbseg jatekbeli penzert elerheto -
# a premium tetelek ritkak, hogy ne legyen tolakodo.
OFFER_MIX = [
    (OfferTier.MARE_C,      0.40, Currency.GAME),
    (OfferTier.MARE_B,      0.32, Currency.GAME),
    (OfferTier.MARE_BPLUS,  0.16, Currency.PREMIUM),
    (OfferTier.RARE_COLOUR, 0.12, Currency.PREMIUM),
]

TIER_CONFIG = {
    OfferTier.MARE_C: {
        'label': 'C kanca',
        'quality_range': (44, 58),
        'price_range': (6000, 16000),
        'note': 'Alapszintű tenyészkanca. Friss vérvonalat hoz.',
    },
    OfferTier.MARE_B: {
        'label': 'B kanca',
        'quality_range': (58, 70),
        'price_range': (24000, 52000),
        'note': 'Rendes tenyészkanca, használható alapnak.',
    },
    OfferTier.MARE_BPLUS: {
        'label': 'B+ kanca',
        'quality_range': (70, 80),
        'price_range': None,          # premium valuta
        'premium_price': 'közepes',
        'note': 'Erős tenyészkanca — ugrás a vérvonalban.',
    },
    OfferTier.RARE_COLOUR: {
        'label': 'Különleges színű ló',
        'quality_range': (52, 78),    # SZANDEKOSAN valtozatos
        'price_range': None,
        'premium_price': 'magas',
        'note': 'Ritka szín, változatos statokkal. A szín a lényeg, '
                'nem a genetika.',
    },
}

# A kulonleges szinek - a szingenetikai motor ritkasagi kategoriaibol
RARE_COLOURS = [
    {'colour': 'Szürke',   'rarity': 'rare',    'weight': 0.50},
    {'colour': 'Fekete',   'rarity': 'uncommon','weight': 0.34},
    {'colour': 'Palomino', 'rarity': 'special', 'weight': 0.16},
]


# =======================================================================
# 2) GENETIKAI FRISSITES - EZ A VALODI RENDSZERFUNKCIO
# =======================================================================
# A kinalt lovak vervonala NEM lehet azonos azzal, ami a jatekosnak
# mar megvan. Igy a piacter tenylegesen friss genetikat injektal, nem
# csak ugyanabbol tobbet.
def pick_fresh_lineage(player_family_ids, all_family_ids, rng=random):
    """Olyan csaladot valaszt, ami a jatekosnak NINCS meg."""
    available = [f for f in all_family_ids if f not in player_family_ids]
    if not available:
        available = all_family_ids       # ha mindet birja, barmi johet
    return rng.choice(available)


def inbreeding_relief(player_avg_inbreeding):
    """Mennyire surgetos a frissites? Ez befolyasolja, hany C/B kanca
    jelenik meg a napi ajanlatban.

    Magas atlagos inbreeding -> tobb friss vervonal a kinalatban.
    """
    if player_avg_inbreeding >= 0.14:
        return {'urgency': 'magas', 'extra_mare_slots': 2,
                'note': 'Az állományod erősen rokon — friss vérvonal ajánlott.'}
    if player_avg_inbreeding >= 0.07:
        return {'urgency': 'közepes', 'extra_mare_slots': 1,
                'note': 'Kezd összeszűkülni a vérvonalad.'}
    return {'urgency': 'alacsony', 'extra_mare_slots': 0, 'note': None}


# =======================================================================
# 3) A NAPI AJANLAT GENERALASA
# =======================================================================
def daily_seed(player_id, day):
    """Determinisztikus mag: a napi ajanlat a nap folyaman NEM valtozik,
    de jatekosonkent es naponkent mas."""
    return hash((str(player_id), int(day))) & 0x7fffffff


def generate_offer(tier, rng, family_id=None):
    cfg = TIER_CONFIG[tier]
    lo, hi = cfg['quality_range']
    quality = round(rng.uniform(lo, hi), 1)

    offer = {
        'tier': tier,
        'label': cfg['label'],
        'quality': quality,
        'grade': grade_of(quality),
        'family_id': family_id,
        'note': cfg['note'],
    }

    if tier == OfferTier.RARE_COLOUR:
        weights = [c['weight'] for c in RARE_COLOURS]
        chosen = rng.choices(RARE_COLOURS, weights=weights, k=1)[0]
        offer['colour'] = chosen['colour']
        offer['rarity'] = chosen['rarity']
    else:
        offer['colour'] = 'Pej'
        offer['rarity'] = 'common'

    if cfg['price_range']:
        plo, phi = cfg['price_range']
        # az ar a minoseggel no a savon belul
        t = (quality - lo) / max(1, hi - lo)
        offer['currency'] = Currency.GAME
        offer['price'] = int(round(plo + (phi - plo) * t))
    else:
        offer['currency'] = Currency.PREMIUM
        offer['price_band'] = cfg['premium_price']

    return offer


def grade_of(q):
    if q >= 88: return 'A+'
    if q >= 82: return 'A'
    if q >= 76: return 'A-'
    if q >= 70: return 'B+'
    if q >= 63: return 'B'
    if q >= 56: return 'B-'
    if q >= 47: return 'C'
    if q >= 36: return 'D'
    return 'E'


def daily_marketplace(player_id, day, player_family_ids=None,
                      all_family_ids=None, avg_inbreeding=0.0):
    """A jatekos napi kinalata. 24 orankent frissul."""
    rng = random.Random(daily_seed(player_id, day))
    player_family_ids = player_family_ids or []
    all_family_ids = all_family_ids or [f'fam-{i}' for i in range(40)]

    relief = inbreeding_relief(avg_inbreeding)
    slots = OFFERS_PER_DAY + relief['extra_mare_slots']

    tiers = [t for t, _, _ in OFFER_MIX]
    weights = [w for _, w, _ in OFFER_MIX]

    # ha surgos a frissites, tobb kanca jon (kevesebb kulonleges szin)
    if relief['extra_mare_slots']:
        weights = [w * (1.25 if t != OfferTier.RARE_COLOUR else 0.6)
                   for t, w, _ in OFFER_MIX]

    offers = []
    for _ in range(slots):
        tier = rng.choices(tiers, weights=weights, k=1)[0]
        fam = pick_fresh_lineage(player_family_ids, all_family_ids, rng)
        offers.append(generate_offer(tier, rng, fam))

    return {
        'player_id': player_id, 'day': day,
        'refresh_in_hours': REFRESH_HOURS,
        'offers': offers,
        'inbreeding_relief': relief,
        'fresh_lineages': sum(1 for o in offers
                              if o['family_id'] not in player_family_ids),
    }


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - NAPI PIACTER ===\n")

    print("--- 1) A RENDSZER CELJA ---")
    print("  a) GENETIKAI FRISSÍTÉS — zárt populációban az inbreeding")
    print("     felhalmozódik; a piactér friss vérvonalat injektál")
    print("  b) VÉRVONAL-FRISSÍTÉS — hozzáférés új családokhoz")
    print("  c) KÜLÖNLEGES SZÍNEK — a monetizáció fő pontja\n")
    print(f"  Frissül: {REFRESH_HOURS} óránként  ·  "
          f"alap kínálat: {OFFERS_PER_DAY} ló  ·  játékosonként eltérő\n")

    print("--- 2) A KINALAT OSSZETETELE ---")
    print(f"  {'Kategória':24s} {'Arány':>7s} {'Fizetés':>12s}")
    for tier, share, cur in OFFER_MIX:
        c = 'játékbeli' if cur == Currency.GAME else 'VALÓDI PÉNZ'
        print(f"  {TIER_CONFIG[tier]['label']:24s} {share*100:>6.0f}% {c:>12s}")
    game_share = sum(s for _, s, c in OFFER_MIX if c == Currency.GAME)
    print(f"\n  A kínálat {game_share*100:.0f}%-a játékbeli pénzért elérhető —")
    print("  a prémium tételek ritkák, hogy ne legyen tolakodó.\n")

    print("--- 3) EGY NAPI KINALAT ---")
    player_fams = ['fam-3', 'fam-11', 'fam-19']
    mp = daily_marketplace('player-001', day=8, player_family_ids=player_fams)
    for o in mp['offers']:
        if o['currency'] == Currency.GAME:
            price = f"{o['price']:,} B$".replace(',', ' ')
        else:
            price = f"prémium ({o['price_band']})"
        colour = f" · {o['colour']}" if o['rarity'] != 'common' else ''
        print(f"  {o['label']:24s} {o['grade']:3s}{colour:12s} {price:>18s}")
        print(f"     {o['note']}")
    print(f"\n  Friss vérvonal a kínálatban: {mp['fresh_lineages']}/{len(mp['offers'])}\n")

    print("--- 4) A KINALAT REAGAL AZ ALLOMANYRA ---")
    print("  Ha a játékos vérvonala összeszűkül, több friss kanca jön:\n")
    for inb, label in [(0.02, 'változatos állomány'),
                       (0.09, 'szűkülő vérvonal'),
                       (0.17, 'erősen rokon állomány')]:
        r = inbreeding_relief(inb)
        m = daily_marketplace('player-002', 8, player_fams, avg_inbreeding=inb)
        mares = sum(1 for o in m['offers'] if o['tier'] != OfferTier.RARE_COLOUR)
        note = f"  — {r['note']}" if r['note'] else ''
        print(f"  átlagos inbreeding {inb*100:>4.0f}%  ({label:24s})  "
              f"{len(m['offers'])} ajánlat, ebből {mares} kanca{note}")
    print()

    print("--- 5) A KULONLEGES SZINEK ELOSZLASA ---")
    rng = random.Random(1)
    counts = {}
    for _ in range(3000):
        o = generate_offer(OfferTier.RARE_COLOUR, rng)
        counts[o['colour']] = counts.get(o['colour'], 0) + 1
    for c in RARE_COLOURS:
        n = counts.get(c['colour'], 0)
        print(f"  {c['colour']:10s} {n/3000*100:>5.1f}%  ({c['rarity']})")
    print("\n  A tenyésztési motorban ezek extrém ritkák (Palomino 0,07%) —")
    print("  itt viszont célzottan vásárolhatók. Ez a monetizáció lényege.\n")

    print("--- 6) MONETIZACIOS HATARESET ---")
    print("  A B+ kanca MECHANIKAI előnyt ad (jobb genetika), tehát")
    print("  szigorúan véve sérti a 'csak kinézet valódi pénzért' elvet.")
    print("  Ez TUDATOS engedmény. Ellensúlyozza:")
    print("     - a B+ kanca elérhető játékbeli pénzért is (aukción)")
    print("     - a vérvonal-építés hosszú távon felülmúlja a vásárolt kancát")
    print("       (season.html mérés: a Kancabefektető stratégia nem dominál)\n")

    print("--- 7) VALIDACIO ---")
    a = daily_marketplace('p-1', 8)
    b = daily_marketplace('p-1', 8)
    c = daily_marketplace('p-1', 9)
    d = daily_marketplace('p-2', 8)

    checks = [
        ('Ugyanaz a játékos, ugyanaz a nap: azonos kínálat',
         [o['label'] for o in a['offers']] == [o['label'] for o in b['offers']]),
        ('Másik nap: más kínálat',
         [o['label'] for o in a['offers']] != [o['label'] for o in c['offers']]),
        ('Másik játékos: más kínálat',
         [o['label'] for o in a['offers']] != [o['label'] for o in d['offers']]),
        ('A kínálat többsége játékbeli pénzért elérhető',
         game_share > 0.6),
        ('A friss vérvonal elkerüli a játékos meglévő családjait',
         daily_marketplace('p-9', 8, ['fam-0','fam-1'])['fresh_lineages'] ==
         len(daily_marketplace('p-9', 8, ['fam-0','fam-1'])['offers'])),
        ('Erős inbreeding esetén több ajánlat jön',
         len(daily_marketplace('p-3', 8, avg_inbreeding=0.17)['offers']) >
         len(daily_marketplace('p-3', 8, avg_inbreeding=0.01)['offers'])),
        ('A B+ kanca prémium valutáért megy',
         TIER_CONFIG[OfferTier.MARE_BPLUS]['price_range'] is None),
        ('A C és B kanca játékbeli pénzért',
         TIER_CONFIG[OfferTier.MARE_C]['price_range'] is not None
         and TIER_CONFIG[OfferTier.MARE_B]['price_range'] is not None),
        ('A különleges színű ló statjai változatosak',
         TIER_CONFIG[OfferTier.RARE_COLOUR]['quality_range'][1] -
         TIER_CONFIG[OfferTier.RARE_COLOUR]['quality_range'][0] >= 20),
        ('A piactér nem függ az aukciós modultól (nincs import)',
         not any(l.strip().startswith(('import ', 'from ')) and 'auction' in l
                 for l in open(__file__, encoding='utf-8'))),
        ('A kínálat determinisztikus a napon belül',
         daily_seed('p-1', 8) == daily_seed('p-1', 8)
         and daily_seed('p-1', 8) != daily_seed('p-1', 9)),
        ('Csak NPC-lovak — nincs játékos-tenyésztésű a kínálatban',
         all('bred_by_player' not in o for o in a['offers'])),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
