"""
Breeder Tycoon - Integrity Engine v1.0
=======================================================================
CSALASVEDELEM: progressziós kapuk + anomalia-detektalas.

KET RETEG:
  A) MEGELOZES  - a jatek szerkezete tegye ertelmetlenne a csalast
  B) DETEKTALAS - ami atcsuszik, azt statisztikailag szurjuk ki

=======================================================================
AMI MAR SZERKEZETILEG VED (nem itt, hanem a jatek felepiteseben)
=======================================================================

1. MASODIK-ARAS AUKCIO (auction_sim.py): a leutesi ar a MASODIK
   legmagasabb ertekeles + egy lepes. Egy alt-fiok hiaba licital
   50 000-et egy 5 000-et ero lora - 5 300-at fizet. EGYETLEN
   alt-fiok nem tud szandekosan tulfizetni.

2. NINCS kozvetlen csere, ajandekozas vagy penzatutalas. Az aukcio az
   EGYETLEN jatekos-jatekos csatorna.

3. VILLAMAR fix 2 500 - nem mozgat erdemi erteket.

4. TENYESZTOI PREMIUM a TENYESZTOT koveti, nem a tulajdonost - egy
   alt-fioknak eladott lo utan is a tenyeszto kapja. Igy az eladas nem
   mozgatja a jovedelemforrast.

5. GLOBALIS MENLISTA black type-hoz kotott (stud_sim.py): egy fiokkal
   tenyesztett lo nem lesz men attol, hogy letezik - ki kell vinni a
   palyara es meg kell vernie a valodi mezonyt.

A VALODI RES: KET osszejatszo licitalo megtori a masodik-aras
mechanikat. Alt1 licital 50 000-et, Alt2 49 000-et -> a leutes ~50 000.
EZ ELLEN vedekezik ez a modul.

=======================================================================
FORRASOK
=======================================================================

1. Kereskedelmi HALOZAT elemzese, nem egyedi fiokoke: az AION-vizsgalat
   (a harmadik legnagyobb MMORPG) a rendellenes kereskedesi halozatokat
   kovette, es igy "nemcsak a gold farmer karaktereket, hanem a
   gold farming csoportok TELJES halozati strukturajat" felderitette.
   https://www.researchgate.net/publication/282839999_A_study_of_RMT_buyer_detection_for_the_collapse_of_GFG_in_MMORPG

2. A csalok SZANDEKOSAN szetteritik a tevekenyseget a fiokok kozott,
   hogy a kockazati kuszobok alatt maradjanak - ezert a fiokonkenti
   figyeles onmagaban hatastalan.
   https://bespot.com/use-case-fraud-prevention-multiple-account-game-studios/

3. Eszkoz-ujjlenyomat es viselkedes-elemzes: "a player using the same
   device cluster to run twenty accounts looks nearly identical on the
   backend". Ez a szabvany eszkozkeszlet, de KIJATSZHATO - ezert kell
   melle a gazdasagi anomalia-detektalas.
   https://phishfort.com/gaming-fraud-prevention/

4. Bot-detektalas viselkedesi jellemzokbol: valos MMORPG-adaton 96%-os
   pontossag. A modszertan atveheto: ismetlodo, gepies mintak keresese.
   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4844581/
"""

import random
import statistics
from enum import Enum
from collections import defaultdict, Counter

random.seed(42)


# =======================================================================
# A) PROGRESSZIOS KAPUK
# =======================================================================
# EZ A LEGERŐSEBB VEDELEM, mert nem detektal, hanem GAZDASAGTALANNA teszi
# a tamadast: minden alt-fiokkal vegig kell jatszani tobb szezont,
# mielott hasznalhato lenne ertektranszferre.
#
# A kapuk NEM buntetik a valodi kezdo jatekost: az elso szezonokban
# ugysem tud es nem is akar nagy osszeggel licitalni.

GATE_TIERS = [
    # (min_szezon, min_sajat_nyeremeny, max_licit, cimke)
    (0,  0,       6000,     'Kezdő'),
    (2,  8000,    25000,    'Megállapodott'),
    (4,  40000,   120000,   'Bejáratott'),
    (8,  150000,  None,     'Korlátlan'),
]


def bid_ceiling(account):
    """Mennyit licitalhat legfeljebb ez a fiok?

    account: {'seasons_played': int, 'lifetime_earnings': int}
    """
    seasons = account.get('seasons_played', 0)
    earnings = account.get('lifetime_earnings', 0)

    ceiling = GATE_TIERS[0][2]
    label = GATE_TIERS[0][3]
    for min_s, min_e, cap, name in GATE_TIERS:
        if seasons >= min_s and earnings >= min_e:
            ceiling, label = cap, name
    return {'ceiling': ceiling, 'tier': label}


def check_bid(account, amount):
    """Engedelyezett-e ez a licit?"""
    g = bid_ceiling(account)
    if g['ceiling'] is None or amount <= g['ceiling']:
        return {'allowed': True, 'tier': g['tier'], 'ceiling': g['ceiling'], 'reason': None}
    return {
        'allowed': False, 'tier': g['tier'], 'ceiling': g['ceiling'],
        'reason': (f"{g['tier']} szinten a licit felső határa "
                   f"{g['ceiling']:,} B$. Játssz több szezont, vagy szerezz "
                   f"több nyereményt a magasabb szinthez.").replace(',', ' '),
    }


# =======================================================================
# B) ANOMALIA-DETEKTALAS
# =======================================================================
# HAROM JEL, egyik sem elegendo onmagaban - EGYUTT adnak kepet.

# --- 1. jel: tulfizetes az NPC-ertekelesi plafonhoz kepest ---
# Ha a leutesi ar jelentosen meghaladja azt, amennyit az NPC-k ertek,
# az anomalia. Egy valodi jatekos is tulfizethet egy megkivant lora,
# ezert ez ONMAGABAN nem bizonyitek.
OVERPAY_FLAG_RATIO = 1.6     # ennyiszeres felett jelzunk
OVERPAY_SEVERE_RATIO = 2.5


def overpay_score(hammer_price, npc_valuation_ceiling):
    """0-1 kozotti pontszam: mennyire tulfizetes ez a tranzakcio?"""
    if npc_valuation_ceiling <= 0:
        return 0.0
    ratio = hammer_price / npc_valuation_ceiling
    if ratio < OVERPAY_FLAG_RATIO:
        return 0.0
    if ratio >= OVERPAY_SEVERE_RATIO:
        return 1.0
    return round((ratio - OVERPAY_FLAG_RATIO) /
                 (OVERPAY_SEVERE_RATIO - OVERPAY_FLAG_RATIO), 3)


# --- 2. jel: kapcsolati graf (forras 1.) ---
# Nem az egyedi fiokot nezzuk, hanem a KERESKEDESI HALOZATOT.
# Egy ismetlodo vevo-elado par a legerosebb jel.
REPEAT_PAIR_FLAG = 4         # ennyi tranzakcio utan teljes a jel
CONCENTRATION_FLAG = 0.6     # ha a fiok forgalmanak ennyi hanyada egy partnerrel megy
MIN_TXNS_FOR_CONCENTRATION = 3   # ez alatt a koncentracio ertelmetlen:
                                 # aki egyszer vasarolt, annal a forgalom
                                 # 100%-a egy partnerhez megy - ez NEM jel


class TradeGraph:
    """Vevo-elado kapcsolatok nyilvantartasa es elemzese."""

    def __init__(self):
        self.edges = defaultdict(list)      # (buyer, seller) -> [amounts]
        self.buyer_total = defaultdict(float)
        self.seller_total = defaultdict(float)
        self.buyer_count = defaultdict(int)
        self.seller_count = defaultdict(int)

    def record(self, buyer, seller, amount, overpay=0.0):
        self.edges[(buyer, seller)].append({'amount': amount, 'overpay': overpay})
        self.buyer_total[buyer] += amount
        self.seller_total[seller] += amount
        self.buyer_count[buyer] += 1
        self.seller_count[seller] += 1

    def pair_score(self, buyer, seller):
        """Mennyire gyanus ez a par? 0-1."""
        txns = self.edges.get((buyer, seller), [])
        if not txns:
            return 0.0

        n = len(txns)
        total = sum(t['amount'] for t in txns)

        # ISMETLODES: egyetlen tranzakcio NEM jel. Ket ember egyszer
        # uzletel egymassal - ez a normal mukodes.
        if n <= 1:
            repeat = 0.0
        else:
            repeat = min(1.0, (n - 1) / (REPEAT_PAIR_FLAG - 1))

        # KONCENTRACIO: csak akkor ertelmes, ha a fioknak van eleg
        # forgalma. Aki egyszer vasarolt, annal a forgalom 100%-a egy
        # partnerhez megy - ez matematikai muvi termek, nem jel.
        conc_score = 0.0
        if self.buyer_count[buyer] >= MIN_TXNS_FOR_CONCENTRATION or \
           self.seller_count[seller] >= MIN_TXNS_FOR_CONCENTRATION:
            buyer_conc = (total / self.buyer_total[buyer]
                          if self.buyer_count[buyer] >= MIN_TXNS_FOR_CONCENTRATION
                          and self.buyer_total[buyer] else 0)
            seller_conc = (total / self.seller_total[seller]
                           if self.seller_count[seller] >= MIN_TXNS_FOR_CONCENTRATION
                           and self.seller_total[seller] else 0)
            conc = max(buyer_conc, seller_conc)
            conc_score = min(1.0, max(0.0, (conc - CONCENTRATION_FLAG) / (1.0 - CONCENTRATION_FLAG)))

        # atlagos tulfizetes ezen az elen
        avg_overpay = statistics.mean(t['overpay'] for t in txns)

        # EGYETLEN tranzakcio maximum a tulfizetes-jelet hordozhatja -
        # onmagaban ez sem elegendo a riasztashoz.
        if n <= 1:
            return round(avg_overpay * 0.5, 3)

        # a harom jel egyutt - a legerosebb ketto sulyozott atlaga
        signals = sorted([repeat, conc_score, avg_overpay], reverse=True)
        return round(signals[0] * 0.6 + signals[1] * 0.4, 3)

    def suspicious_pairs(self, threshold=0.55):
        out = []
        for (buyer, seller) in self.edges:
            sc = self.pair_score(buyer, seller)
            if sc >= threshold:
                txns = self.edges[(buyer, seller)]
                out.append({
                    'buyer': buyer, 'seller': seller, 'score': sc,
                    'transactions': len(txns),
                    'total': round(sum(t['amount'] for t in txns)),
                })
        return sorted(out, key=lambda r: -r['score'])


# --- 3. jel: viselkedesi minta (forras 4.) ---
# Egy friss fiok, aki azonnal egyetlen eladora koncentral, es semmi
# mast nem csinal a jatekban - ez gepies minta.
def behaviour_score(account):
    """0-1: mennyire viselkedik "eldobhato fiokkent"?

    account mezoi: seasons_played, races_run, horses_bred,
                   auction_purchases, distinct_sellers
    """
    signals = []

    # alig jatszik, de vasarol
    activity = account.get('races_run', 0) + account.get('horses_bred', 0)
    purchases = account.get('auction_purchases', 0)
    if purchases > 0:
        ratio = activity / max(1, purchases)
        signals.append(1.0 if ratio < 0.5 else max(0.0, 1.0 - ratio / 3))

    # egyetlen eladora koncentral
    distinct = account.get('distinct_sellers', 1)
    if purchases >= 2:
        signals.append(1.0 if distinct == 1 else max(0.0, 1.0 - (distinct - 1) / 3))

    # nagyon friss fiok nagy forgalommal
    if account.get('seasons_played', 0) <= 2 and purchases >= 2:
        signals.append(0.8)

    return round(statistics.mean(signals), 3) if signals else 0.0


# =======================================================================
# C) OSSZESITETT KOCKAZATI PONTSZAM
# =======================================================================
# EGYIK JEL SEM ELEG ONMAGABAN. A valodi jatekos is tulfizethet, is
# vasarolhat ketszer ugyanattol, is lehet friss fiok. HAROM egybeeso
# jel viszont mar mintat mutat.
class RiskLevel(Enum):
    CLEAR = 'clear'
    WATCH = 'watch'
    REVIEW = 'review'
    ACTION = 'action'


RISK_LABELS = {
    RiskLevel.CLEAR:  ('Tiszta', 'Nincs teendő.'),
    RiskLevel.WATCH:  ('Megfigyelés', 'Naplózzuk, de nem avatkozunk be.'),
    RiskLevel.REVIEW: ('Kivizsgálás', 'Manuális ellenőrzés javasolt.'),
    RiskLevel.ACTION: ('Beavatkozás', 'Tranzakció visszavonása / fiók korlátozása.'),
}


def risk_assessment(pair_score_val, behaviour_score_val, device_match=False):
    """Osszesitett ertekeles.

    device_match: eszkoz/IP egyezes (forras 3.) - erosito jel, de
    onmagaban NEM bizonyitek (megosztott halozat, csaladtagok).
    """
    base = pair_score_val * 0.55 + behaviour_score_val * 0.45
    if device_match:
        base = min(1.0, base + 0.20)

    if base >= 0.75:
        level = RiskLevel.ACTION
    elif base >= 0.55:
        level = RiskLevel.REVIEW
    elif base >= 0.35:
        level = RiskLevel.WATCH
    else:
        level = RiskLevel.CLEAR

    return {'score': round(base, 3), 'level': level,
            'label': RISK_LABELS[level][0], 'action': RISK_LABELS[level][1]}


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDER TYCOON - INTEGRITY ENGINE v1.0 ===\n")

    print("--- 1) PROGRESSZIOS KAPUK ---")
    print("  A legerősebb védelem: nem detektál, hanem gazdaságtalanná teszi")
    print("  a támadást. Minden alt-fiókkal végig kell játszani több szezont.\n")
    print(f"  {'Szint':16s} {'Szezon':>7s} {'Nyeremény':>11s} {'Max licit':>12s}")
    for min_s, min_e, cap, name in GATE_TIERS:
        capstr = 'korlátlan' if cap is None else f'{cap:,}'.replace(',', ' ')
        print(f"  {name:16s} {min_s:>7d} {min_e:>11,d} {capstr:>12s}".replace(',', ' '))
    print()

    accounts = [
        ('Friss alt-fiók',   {'seasons_played': 0, 'lifetime_earnings': 0}),
        ('Két szezon után',  {'seasons_played': 2, 'lifetime_earnings': 12000}),
        ('Bejáratott',       {'seasons_played': 5, 'lifetime_earnings': 60000}),
        ('Veterán',          {'seasons_played': 10, 'lifetime_earnings': 400000}),
    ]
    print("  Egy 50 000 B$-os licit kísérlete:\n")
    for label, acc in accounts:
        r = check_bid(acc, 50000)
        mark = 'ENGEDÉLYEZVE' if r['allowed'] else 'ELUTASÍTVA  '
        print(f"  {label:18s} [{mark}]  ({r['tier']} szint)")
    print()

    print("--- 2) TULFIZETES-JEL ---")
    print("  Mennyire haladja meg a leütési ár az NPC-k értékelését?\n")
    print(f"  {'Leütés':>9s} {'NPC-plafon':>11s} {'Arány':>7s} {'Jel':>7s}")
    for hammer, ceiling in [(5300, 5000), (7500, 5000), (9000, 5000),
                            (13000, 5000), (25000, 5000)]:
        sc = overpay_score(hammer, ceiling)
        bar = '#' * round(sc * 12)
        print(f"  {hammer:>9,d} {ceiling:>11,d} {hammer/ceiling:>6.2f}× {sc:>7.2f}  {bar}".replace(',', ' '))
    print("\n  -> A második-áras aukció miatt egy magányos alt-fiók nem tud")
    print("     túlfizetni. Ez a jel a KÉT összejátszó licitálót fogja meg.\n")

    print("--- 3) KAPCSOLATI GRAF ---")
    print("  Nem az egyedi fiókot nézzük, hanem a kereskedési hálózatot.\n")

    g = TradeGraph()
    # normal forgalom: sok kulonbozo par
    rng = random.Random(7)
    for i in range(60):
        b = f'jatekos{rng.randint(1,20)}'
        s = f'jatekos{rng.randint(1,20)}'
        if b != s:
            g.record(b, s, rng.randint(2000, 30000), overpay=0.0)
    # gyanus minta: ismetlodo par, tulfizetessel
    for i in range(4):
        g.record('alt_fiok_A', 'fo_fiok', 48000, overpay=0.9)
    # hataresete: ketszer vasarolt ugyanattol, de normal aron
    g.record('jatekos3', 'jatekos11', 15000, overpay=0.0)
    g.record('jatekos3', 'jatekos11', 12000, overpay=0.0)

    flagged = g.suspicious_pairs(threshold=0.4)
    for p in flagged:
        print(f"  {p['buyer']:14s} -> {p['seller']:14s} "
              f"{p['transactions']} tranzakció, {p['total']:>7,d} B$   "
              f"pontszám {p['score']:.2f}".replace(',', ' '))
    total_pairs = len(g.edges)
    print(f"\n  {len(flagged)} jelzett pár {total_pairs} összes párból "
          f"({len(flagged)/total_pairs*100:.1f}%) — a téves riasztás alacsony marad.\n")

    print("--- 4) VISELKEDESI MINTA ---")
    profiles = [
        ('Valódi játékos', {'seasons_played': 6, 'races_run': 84, 'horses_bred': 9,
                            'auction_purchases': 5, 'distinct_sellers': 4}),
        ('Gyűjtögető típus', {'seasons_played': 4, 'races_run': 12, 'horses_bred': 2,
                              'auction_purchases': 8, 'distinct_sellers': 6}),
        ('Eldobható fiók', {'seasons_played': 1, 'races_run': 0, 'horses_bred': 0,
                            'auction_purchases': 4, 'distinct_sellers': 1}),
    ]
    for label, acc in profiles:
        print(f"  {label:18s} pontszám {behaviour_score(acc):.2f}")
    print()

    print("--- 5) OSSZESITETT ERTEKELES ---")
    print("  Egyik jel sem elég önmagában. Három egybeeső jel viszont minta.\n")
    cases = [
        ('Valódi játékos, kétszer vett ugyanattól', 0.35, 0.10, False),
        ('Gyanús pár, de aktív fiókok', 0.70, 0.20, False),
        ('Gyanús pár + passzív fiók', 0.70, 0.75, False),
        ('Gyanús pár + passzív fiók + azonos eszköz', 0.70, 0.75, True),
    ]
    for label, ps, bs, dev in cases:
        r = risk_assessment(ps, bs, dev)
        print(f"  {label:42s} {r['score']:.2f}  {r['label']:14s} {r['action']}")
    print()

    print("--- 6) VALIDACIO ---")
    checks = [
        ('Friss fiók nem licitálhat 50 000-et',
         not check_bid({'seasons_played': 0, 'lifetime_earnings': 0}, 50000)['allowed']),
        ('Veterán fiók korlátlanul licitálhat',
         check_bid({'seasons_played': 10, 'lifetime_earnings': 400000}, 999999)['allowed']),
        ('A kapu nem akadályozza a valódi kezdőt (6000-es licit)',
         check_bid({'seasons_played': 0, 'lifetime_earnings': 0}, 6000)['allowed']),
        ('A normál ár nem vált ki túlfizetés-jelet',
         overpay_score(5300, 5000) == 0.0),
        ('A háromszoros ár teljes jelet ad',
         overpay_score(15000, 5000) == 1.0),
        ('Az ismétlődő, túlfizetéses pár magas pontszámot kap',
         g.pair_score('alt_fiok_A', 'fo_fiok') >= 0.7),
        ('A kétszeri normál vásárlás nem elég a riasztáshoz',
         g.pair_score('jatekos3', 'jatekos11') < 0.55),
        ('Az aktív játékos alacsony viselkedési pontszámot kap',
         behaviour_score(profiles[0][1]) < 0.3),
        ('Az eldobható fiók magas pontszámot kap',
         behaviour_score(profiles[2][1]) > 0.7),
        ('Egyetlen erős jel önmagában nem vezet beavatkozáshoz',
         risk_assessment(0.9, 0.0, False)['level'] != RiskLevel.ACTION),
        ('Az eszközegyezés önmagában nem elég',
         risk_assessment(0.2, 0.2, True)['level'] in (RiskLevel.CLEAR, RiskLevel.WATCH)),
        ('Három egybeeső jel beavatkozást vált ki',
         risk_assessment(0.7, 0.75, True)['level'] == RiskLevel.ACTION),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
