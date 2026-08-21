"""
Trot Heritage - Feeding Engine v1.0
=======================================================================
3 savos takarmanyozasi rendszer, a tréner-motorral (trainer_sim.py) es
a tenyesztesi motorral (breeding_sim.py) azonos filozofiaval:

  - Alap (szena + zab) - ingyenes/alap savkent
  - Prémium Teljesitmenytap - energia/feherje-dus, teljesitmeny-orientalt
  - Prémium Egeszsegtap - asvanyi anyag/vitamin-dus, soundness-orientalt

FONTOS: a ket premium sav SZANDEKOSAN KULONBOZO tulajdonsagokra hat, nem
altalanos "fizetsz tobbet = mindenben jobb" logikat kovet - ez tudatos
jatektervezesi/monetizacios dontes, hogy a valasztas strategiai maradjon,
ne pay-to-win.

FORRASOK (a savok es hatasaik tudomanyos alapjahoz):

1. Kentucky Equine Research, "Think Energy When Feeding the Racehorse":
   a szena onmagaban nem fedezi egy verseny-tréningben levo lo magas
   energiaigenyet - kiegeszito energiaforras (jellemzoen zab) szukseges.
   https://ker.com/equinews/think-energy-when-feeding-the-racehorse/

2. Pennsylvania Horse Racing Association, "What Do Racehorses Eat?":
   versenylovak kb. 12-14% feherjet igenyelnek, tobblet zsirt a
   allokepesseghez, valamint vitaminokat/asvanyi anyagokat az optimalis
   teljesitmenyhez.
   https://pennhorseracing.com/stories/what-do-racehorses-eat/

3. Mad Barn Feed Bank, konkret kereskedelmi versenyloTapok elemzese
   (Racehorse Mix, Race Horse Feed): 14% feherje, 5-7% zsir, magas
   energiatartalom - ez a PREMIUM TELJESITMENYTAP savunk realisztikus
   alapja.
   https://madbarn.com/feeds/racehorse-mix-gain-equine-nutrition/
   https://madbarn.com/feeds/race-horse-feed-lifeline/

4. BloodHorse, "Feeding Racehorses": a kalcium es foszfor aranya
   dontoen fontos a csont-/izuleti fejlodeshez, kulonosen fiatal,
   novekvo lovaknal - nem megfelelo asvanyianyag-bevitel fejlodesi
   csontrendellenessegekhez (DOD) vezethet. Ez a PREMIUM EGESZSEGTAP
   savunk alapja (Soundness-re hat).
   https://www.bloodhorse.com/horse-racing/articles/145185/feeding-racehorses

5. BloodHorse, "Feed for Speed": FONTOS OVATOSSAGI FORRAS - a szerzo
   kifejezetten figyelmeztet, hogy egyetlen "csoda-kiegeszito" hatasa
   a teljes diéta kevesebb, mint 0.1%-a - azaz a premium tapoknak NEM
   szabad tulzott, arany-fokozatu elonyt adniuk a jatekban sem.
   https://www.bloodhorse.com/horse-racing/articles/145211/feed-for-speed

6. Merck Animal Health / Mad Barn / eXtension: novekedesben levo
   csikoknak/yearlingeknek 14-16% nyersfeherje, lizin-aminosav,
   kalcium/foszfor legalabb 1.5:1 aranyban, rez/cink/szelen/E-vitamin
   szukseges a csont-/izuleti fejlodeshez.
   https://www.merck-animal-health-usa.com/horse-owners-and-professionals/foal-mare-care/foal-care-overview/foal-nutrition-and-foal-growth/
   https://madbarn.com/how-to-feed-a-growing-foal/
   https://horses.extension.org/feeding-a-growing-horse/

7. Kentucky Equine Research, "Developmental Orthopedic Disease in
   Foals": tuletetes (tul sok energia/feherje, tul gyors novekedes)
   NOVELI a fejlodesi csontrendellenesseg (DOD) kockazatat - tehat a
   csikotapnal NEM a maximalizalas, hanem az egyensuly a cel.
   https://ker.com/equinews/developmental-orthopedic-disease-in-foals-an-overview/

8. AQHA, "Creep Feeding Foals": a kalcium/foszfor/rez/cink/szelen/
   E-vitamin egyensulya kritikus, "tul sok, tul keves vagy rossz arany
   is artalmas lehet ebben az eletszakaszban".
   https://www.aqha.com/blog-detail-view/-/asset_publisher/NoPXPVhTAWTK/content/tips-for-creep-feeding-your-fo-1

9. Horse Journals, "Developmental Orthopedic Disease in Foals":
   megerositi a tuletetes-kockazatot, es hogy a tulzott energiabevitel
   /gyors novekedes osteochondrosis-hoz vezethet.
   https://www.horsejournals.com/horse-care/feed-nutrition/developmental-orthopedic-disease-foals

EZERT: egyik sav sem ad 95%+ hatekonysagot, es az alap sav sem esik
50% ala - a realisztikus tartomany szuk, a valasztas inkabb IRANY
(melyik tulajdonsagra optimalizalsz), nem NYERS ERO kulonbseg. A
csikotap KULON ELETSZAKASZRA szol (novekedesi periodus), es tudatosan
NEM a legmagasabb hatekonysagu sav semmilyen kategoriaban - a valos
tuletetesi kockazatot tukrozve.
"""

TRAITS_PERFORMANCE = ['speed', 'accel', 'stamina', 'sprint', 'mile', 'middle', 'staying']
TRAITS_HEALTH = ['soundness']
TRAITS_OTHER = ['trainability', 'temperament']

FEED_TIERS = {
    'alap': {
        'label': 'Alap (széna + zab)',
        'tier': 'alap',
        'life_stage': 'felnott',
        'source_note': (
            'Hagyomanyos szena+zab alapdiéta. Fedezi az alapveto energia- '
            'es rostszuksegletet, de onmagaban nem eri el egy intenziv '
            'treningben levo verseny lo teljes energiaigenyet (forras 1.).'
        ),
        'trait_effectiveness': {
            **{t: 0.65 for t in TRAITS_PERFORMANCE},
            **{t: 0.60 for t in TRAITS_HEALTH},
            **{t: 0.65 for t in TRAITS_OTHER},
        },
    },
    'premium_teljesitmeny': {
        'label': 'Prémium Teljesítménytáp',
        'tier': 'premium',
        'life_stage': 'felnott',
        'source_note': (
            'Magas energiatartalmu, feherjeben/zsirban dusabb koncentraltap '
            '(kb. 14% feherje, 5-7% zsir - valos kereskedelmi versenylo-tapok '
            'receptúraja alapjan, forras 3.). Tobblet energiat es izomepitest '
            'tamogat, ezert a sebesseg/gyorsulas/allokepesseg jellegu '
            'tulajdonsagokra hat leginkabb (forras 2.).'
        ),
        'trait_effectiveness': {
            **{t: 0.88 for t in TRAITS_PERFORMANCE},
            **{t: 0.62 for t in TRAITS_HEALTH},       # nem celzott, csak alap szint
            **{t: 0.68 for t in TRAITS_OTHER},
        },
    },
    'premium_egeszseg': {
        'label': 'Prémium Egészségtáp',
        'tier': 'premium',
        'life_stage': 'felnott',
        'source_note': (
            'Asvanyi anyag- es vitamin-dus kiegeszito tap (kalcium/foszfor '
            'aranyt tamogato, E-vitamin, izuleti tamogatas). A csont- es '
            'izuleti egeszseget celozza, kulonosen fontos novekedesben levo '
            'fiatal lovaknal (forras 4.).'
        ),
        'trait_effectiveness': {
            **{t: 0.67 for t in TRAITS_PERFORMANCE},  # nem celzott, csak alap szint
            **{t: 0.90 for t in TRAITS_HEALTH},
            **{t: 0.72 for t in TRAITS_OTHER},         # jobb kozerzet -> enyhen jobb temperamentum is
        },
    },
    'csiko_tap': {
        'label': 'Csikótáp (creep feed)',
        'tier': 'eletszakasz-specifikus',
        'life_stage': 'csiko',
        'source_note': (
            'Novekedesben levo csikoknak/yearlingeknek szant specialis tap: '
            '14-16% nyersfeherje, kiemelten lizin-aminosav az izom-/'
            'csontfejlodeshez, valamint kalcium/foszfor (legalabb 1.5:1 '
            'aranyban), rez, cink, szelen es E-vitamin a porc-/izuleti '
            'fejlodeshez (forras 6-8.). MAS EletSZAKASZRA szol, mint a masik '
            'harom sav - nem versenyzo felnott lovaknak, hanem a novekedesi '
            'idoszakra.'
        ),
        'caution_note': (
            'FONTOS, VALOS KOCKAZAT (forras 6., 7., 9.): tobb tanulmany is '
            'megerositi, hogy a TULETETES (tul sok energia/feherje, tul '
            'gyors novekedesi utem) NOVELI a fejlodesi csontrendellenesseg '
            '(DOD - osteochondrosis, izuleti deformaciok) kockazatat. Azaz '
            'ITT NEM IGAZ az "minel tobb, annal jobb" elv - az egyensuly '
            'szamit, nem a maximalizalas. Ez a jatekban egy JOVOBELI '
            'ADAGOLAS-MECHANIKA (meg nem implementalt) alapja lesz: a '
            'tuletetes a soundness-t ronthatja, nem javithatja majd.'
        ),
        'trait_effectiveness': {
            **{t: 0.75 for t in TRAITS_PERFORMANCE},  # alapozo hatas, nem verseny-maximalizalas
            **{t: 0.85 for t in TRAITS_HEALTH},        # csont-/izuleti fejlodes fokusz
            **{t: 0.78 for t in TRAITS_OTHER},         # korai szoktatas/kezeles hatasa
        },
    },
}

# FONTOS BALANSZ-KORLAT (forras 5. alapjan: egyetlen tap sem adhat
# tulzott, "csoda-kiegeszito" szintu elonyt): egyik sav sem lepheti
# tul a MAX_EFFECTIVENESS erteket, es egyik sem eshet MIN_EFFECTIVENESS
# ala - ez a monetizacios balansz vedelme, nem tudomanyos adat.
MAX_EFFECTIVENESS = 0.90
MIN_EFFECTIVENESS = 0.55


def get_feeding_effectiveness(feed_tier_key, trait):
    """0-1 kozotti hatekonysagi ertek egy adott takarmany-sav es
    tulajdonsag kombinaciora. Ez lesz a bemenete a kesobbi, MEG NEM
    VEGLEGESITETT fenotipus-kepletnek (genetika + felneveles + tréning
    egyesitese) - ugyanaz az integracios minta, mint a tréner-motorban
    (get_training_effectiveness)."""
    tier = FEED_TIERS[feed_tier_key]
    val = tier['trait_effectiveness'].get(trait, 0.65)
    return round(max(MIN_EFFECTIVENESS, min(MAX_EFFECTIVENESS, val)), 3)


def describe_feed_tier_for_player(feed_tier_key):
    """A jatekosnak megjelenitett nezet - cimke + rovid leiras, NYERS
    hatekonysagi szazalek nelkul (ugyanaz az elv, mint a lo/tréner
    A-E indexnel: a reszletek a hatterben maradnak)."""
    tier = FEED_TIERS[feed_tier_key]
    return f"{tier['label']} ({tier['tier']})"


# =======================================================================
# 6) TAKARMANY-PIACTER: BESZALLITO-VALASZTAS + KOMBINACIOS BONUSZ
# =======================================================================
# A JATEKOS KONCEPCIOJA (nem tudomanyos forrasbol, hanem jatektervezesi
# specifikacio): a takarmanyozas egy piacter-mechanika. Az alap-
# alapanyagok (szena, zab, arpa) NEM markasak, csak egy gazda/termelo
# nevet es minosegi szintet kapnak. A koncentraltapok (csiko/verseny/
# anyakanca/vitaminos stb.) MARKASAK, kategorizaltak, es a jatekos
# egyszerre TOBBET is valaszthat. Az adagolast a "virtualis tréner"
# automatikusan kezeli - a jatekosnak csak a VALASZTAS a dolga.
#
# A tobb egyszerre valasztott termek hatasa NEM egyszeruen atlagolodik
# vagy a legjobb szamit, hanem egy KORLATOZOTT (max 15%), KOMBINACIOS
# BONUSZ-rendszerben adodik ossze - ez jatektervezesi dontes, konkret
# szamokkal a felhasznalotol:
#   - Alap-alapanyag (szena+zab) minosege ad egy alap bonuszt:
#       gyenge=0%, kozepes=2%, jo=3.5%, kivalo=5%
#   - Ha a jatekos EGYSZERRE hasznal csiko- ES verseny-kategoriaju
#     tapot, az egy szinergikus kombinaciot alkot: +5%
#   - Ha EZEN FELUL vitaminos kiegeszitot is hasznal: +5% tovabbi
#   - A TELJES bonusz sosem lepheti at a 15%-os plafont
#     (5 alap + 5 kombo + 5 vitamin = 15% - ez a maximum eset)
BASE_FEED_QUALITY_BONUS = {
    'gyenge': 0.0,
    'kozepes': 2.0,
    'jo': 3.5,
    'kivalo': 5.0,
}

MAX_TOTAL_FEED_BONUS_PCT = 15.0
COMBO_BONUS_PCT = 5.0       # csiko + verseny egyutt hasznalva
VITAMIN_BONUS_PCT = 5.0     # vitaminos kiegeszito hasznalata eseten


def calculate_feed_bonus_pct(base_feed_quality, selected_concentrate_categories):
    """Kiszamitja a teljes takarmany-bonuszt (szazalekpontban), a
    jatekos altal megadott kombinacios szabaly szerint.

    base_feed_quality: 'gyenge' | 'kozepes' | 'jo' | 'kivalo'
    selected_concentrate_categories: halmaz, pl. {'csiko', 'verseny', 'vitaminos'}

    Visszateres: 0-15 kozotti szazalekpont-ertek (a genetikai-potencial
    'toltottsegi savhoz' adodik majd hozza, amikor az a rendszer elkeszul).
    """
    bonus = BASE_FEED_QUALITY_BONUS.get(base_feed_quality, 0.0)

    if {'csiko', 'verseny'}.issubset(selected_concentrate_categories):
        bonus += COMBO_BONUS_PCT

    if 'vitaminos' in selected_concentrate_categories:
        bonus += VITAMIN_BONUS_PCT

    return round(min(bonus, MAX_TOTAL_FEED_BONUS_PCT), 2)


# =======================================================================
# 7) ANYAKANCA TARTASI KORULMENYEI - alap-konstansok (a 8. blokk hasznalja)
# =======================================================================
GENETIC_SCORE_MAX = 99  # a tenyesztesi motor (breeding_sim.py) genetic_potential_score also-felso hatara
GENETIC_SCORE_MIN = 5

MATERNAL_HAY_OATS_BONUS = {
    'rossz': 0.0,
    'kozepes': 1.0,
    'jo': 2.0,
    'kivalo': 3.0,
}
KANCATAP_BONUS_PCT = 2.0
MAX_MATERNAL_CARE_BONUS_PCT = 5.0  # 3 (kivalo szena/zab) + 2 (kancatáp) = 5


def calculate_maternal_care_bonus_pct(hay_oats_quality, uses_kancatap):
    """Az anyakanca tartasi korulmenyeibol szarmazo bonusz (max 5%,
    a 20%-os takarmany-sav elso resze - lasd 8. blokk)."""
    bonus = MATERNAL_HAY_OATS_BONUS.get(hay_oats_quality, 0.0)
    if uses_kancatap:
        bonus += KANCATAP_BONUS_PCT
    return round(min(bonus, MAX_MATERNAL_CARE_BONUS_PCT), 2)


# =======================================================================
# 8) TELJES TOLTOTTSEGI SAV - VEGLEGES ARANY: 55% genetika + 20% takarmany
#    + 25% tréner
# =======================================================================
# A JATEKOS VEGLEGES SPECIFIKACIOJA (55/20/25 arany):
#
#   - GENETIKA: 55% - erre a jatekosnak NINCS kozvetlen ratasa, csak a
#     parositas (mén+kanca) kivalasztasan keresztul.
#
#   - TAKARMANYOZAS: 20% - EZ PONTOSAN EGYEZIK azzal, amit mar
#     megepitettunk: anyakanca gondoskodas (max 5%) + felnott takarmany-
#     piacter kombo-bonusz (max 15%) = 20%. Nincs tobbe hianyzo resz.
#
#   - TRENER: 25% - a tréner attributumainak minosege hatarozza meg,
#     mekkora hanyadat realizalja ebbol a 25%-bol. Mivel a trainer_sim.py
#     generalt attributumai LEGFELJEBB 99-ig terjednek (sosem 100-ig),
#     a tréner altal realizalt resz MATEMATIKAILAG SOSEM eri el a teljes
#     25%-ot - nincs a jatekban "tokeletes tréner", ahogy "tokeletes lo"
#     sincs.
#
# FONTOS, DOKUMENTALT TUDATOS ELTERES A SZAKIRODALOMTOL:
# Tobb forras is direkt szazalekos becslest ad a genetika altalanos
# hozzajarulasarol a lovak sportteljesitmenyehez:
#   - LeCheval (francia lotenyesztesi genetikai szervezet, idezve az
#     Arioneo szaklapban): "genetics explains between 25 and 45% of
#     sporting performance depending on the breed and discipline"
#     https://training.arioneo.com/en/blog-will-racehorse-genetics-studies-revolutionize-horse-racing/
#   - The Plaid Horse Magazine: "in thoroughbreds, 30% of racing
#     performance is due to hereditary components"
#     https://www.theplaidhorse.com/2021/09/23/why-study-the-genetics-of-racehorses/
#
# A SZAKIRODALMI TARTOMANY TEHAT KB. 25-45% (gyakran 30% korul
# kerekitve), NEM 55%. A JATEKBAN HASZNALT 55% EZERT TUDATOS,
# DOKUMENTALT ELTERES a valos becslesektol - a fejleszto kifejezett
# dontese alapjan, azert, mert a jatekosi elmeny szempontjabol jobb,
# ha a tenyesztes (a jatek "gerince", ahogy a projekt eredeti
# koncepcioja is megfogalmazta) hangsulyosabb szerepet kap, mint a
# valosagban. Ez NEM tevedes vagy pontatlansag - tudatosan vallalt
# jatektervezesi dontes, es itt vilagosan jelolve van, hogy ne
# keveredjen ossze a tobbi, ténylegesen tudomanyos adaton alapulo
# ertekkel.
GENETIC_MAX_PCT = 55.0
FEEDING_MAX_PCT = 20.0   # = MAX_MATERNAL_CARE_BONUS_PCT (5) + MAX_TOTAL_FEED_BONUS_PCT (15)
TRAINER_MAX_PCT = 25.0
TRAINER_SCORE_THEORETICAL_MAX = 100.0
TRAINER_SCORE_PRACTICAL_MAX = 99.0  # a trainer_sim.py generalt attributumai soha nem erik el a 100-at


def calculate_genetic_fill_pct(genetic_potential_score):
    """A tenyesztesi motor (breeding_sim.py) genetic_potential_score
    erteket (5-99 skala) atvaltja a toltottsegi sav genetikai reszere
    (0-55%), linearisan skalazva."""
    clamped = max(GENETIC_SCORE_MIN, min(GENETIC_SCORE_MAX, genetic_potential_score))
    fraction = clamped / GENETIC_SCORE_MAX
    return round(fraction * GENETIC_MAX_PCT, 2)


def calculate_trainer_realized_pct(trainer_overall_score):
    """A tréner altal realizalt resz a 25%-os sajat savbol. Mivel a
    trainer_sim.py generalt attributumai legfeljebb 99-ig terjednek,
    ez az ertek MATEMATIKAILAG SOSEM eri el a teljes 25%-ot."""
    capped_score = min(trainer_overall_score, TRAINER_SCORE_PRACTICAL_MAX)
    fraction = capped_score / TRAINER_SCORE_THEORETICAL_MAX
    return round(fraction * TRAINER_MAX_PCT, 2)


def calculate_feeding_realized_pct(maternal_bonus_pct, adult_feed_bonus_pct):
    """A takarmanyozasi sav (max 20%) - anyakanca gondoskodas (max 5%)
    + felnott takarmany-piacter kombo-bonusz (max 15%). Ez a ket mar
    megepitett mechanika PONTOSAN lefedi a teljes 20%-os savot, nincs
    tobbe hianyzo resz."""
    return round(min(maternal_bonus_pct + adult_feed_bonus_pct, FEEDING_MAX_PCT), 2)


def calculate_total_fill_pct(genetic_potential_score, maternal_bonus_pct, adult_feed_bonus_pct, trainer_overall_score):
    """A TELJES toltottsegi sav: genetika (fix, max 55%) + takarmanyozas
    (max 20%) + tréner (max 25%, gyakorlatban sosem teljes)."""
    genetic_part = calculate_genetic_fill_pct(genetic_potential_score)
    feeding_part = calculate_feeding_realized_pct(maternal_bonus_pct, adult_feed_bonus_pct)
    trainer_part = calculate_trainer_realized_pct(trainer_overall_score)

    total = round(genetic_part + feeding_part + trainer_part, 2)
    return {
        'genetic_part_pct': genetic_part,
        'feeding_part_pct': feeding_part,
        'trainer_part_pct': trainer_part,
        'total_fill_pct': min(total, 100.0),
    }


def calculate_birth_fill_pct(genetic_potential_score, hay_oats_quality, uses_kancatap):
    """A csiko szuletesi toltottsegi %-a: genetika (max 55%) + anyakanca
    tartasi korulmenyei (max 5%, a 20%-os takarmany-sav elso resze) =
    max 60%. A maradek 40% (felnott takarmany-piacter max 15% + tréner
    max 25%) kesobb, a nevendekkori es felnott eletszakaszban toltodik."""
    genetic_part = calculate_genetic_fill_pct(genetic_potential_score)
    maternal_part = calculate_maternal_care_bonus_pct(hay_oats_quality, uses_kancatap)
    return round(genetic_part + maternal_part, 2)


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - FEEDING ENGINE v1.0 ===\n")

    print("--- 1) TAKARMANY-SAVAK HATEKONYSAGA TULAJDONSAG-KATEGORIANKENT ---")
    header = f"{'Sav':30s} {'Eletszakasz':12s} {'Teljesitmeny':>14s} {'Soundness':>11s} {'Egyeb':>8s}"
    print(header)
    for key, tier in FEED_TIERS.items():
        perf_avg = sum(get_feeding_effectiveness(key, t) for t in TRAITS_PERFORMANCE) / len(TRAITS_PERFORMANCE)
        health_avg = sum(get_feeding_effectiveness(key, t) for t in TRAITS_HEALTH) / len(TRAITS_HEALTH)
        other_avg = sum(get_feeding_effectiveness(key, t) for t in TRAITS_OTHER) / len(TRAITS_OTHER)
        print(f"{tier['label']:30s} {tier['life_stage']:12s} {perf_avg*100:13.1f}% {health_avg*100:10.1f}% {other_avg*100:7.1f}%")
    print()

    print("--- 2) VALIDACIO: minden ertek a MIN/MAX korlaton belul van-e ---")
    all_ok = True
    for key, tier in FEED_TIERS.items():
        for trait, val in tier['trait_effectiveness'].items():
            if not (MIN_EFFECTIVENESS <= val <= MAX_EFFECTIVENESS):
                all_ok = False
                print(f"  HIBA: {key} / {trait} = {val} kivul esik a [{MIN_EFFECTIVENESS}, {MAX_EFFECTIVENESS}] tartomanyon!")
    print(f"  Minden ertek a balansz-korlaton belul: {'OK' if all_ok else 'HIBA'}\n")

    print("--- 3) VALIDACIO: a premium tapok a sajat celteruleteiken egyertelmuen jobbak-e az alapnal ---")
    perf_check = get_feeding_effectiveness('premium_teljesitmeny', 'speed') > get_feeding_effectiveness('alap', 'speed')
    health_check = get_feeding_effectiveness('premium_egeszseg', 'soundness') > get_feeding_effectiveness('alap', 'soundness')
    cross_check_1 = get_feeding_effectiveness('premium_teljesitmeny', 'soundness') < get_feeding_effectiveness('premium_egeszseg', 'soundness')
    cross_check_2 = get_feeding_effectiveness('premium_egeszseg', 'speed') < get_feeding_effectiveness('premium_teljesitmeny', 'speed')
    print(f"  Teljesitmenytap jobb sebessegben, mint az alap: {'OK' if perf_check else 'HIBA'}")
    print(f"  Egeszsegtap jobb soundness-ben, mint az alap: {'OK' if health_check else 'HIBA'}")
    print(f"  Teljesitmenytap NEM jobb soundness-ben, mint az Egeszsegtap: {'OK' if cross_check_1 else 'HIBA'}")
    print(f"  Egeszsegtap NEM jobb sebessegben, mint a Teljesitmenytap: {'OK' if cross_check_2 else 'HIBA'}")
    specialization_ok = perf_check and health_check and cross_check_1 and cross_check_2
    print(f"  -> A ket premium sav valoban KULONBOZO iranyba specializalt (nem 'fizetsz tobbet = mindenben jobb'): {'OK' if specialization_ok else 'HIBA'}\n")

    print("--- 4) VALIDACIO: a csikotap NEM a legerosebb sav semmilyen kategoriaban (tuletetes-kockazat elve) ---")
    foal_not_strongest_perf = get_feeding_effectiveness('csiko_tap', 'speed') < get_feeding_effectiveness('premium_teljesitmeny', 'speed')
    foal_not_strongest_health = get_feeding_effectiveness('csiko_tap', 'soundness') < get_feeding_effectiveness('premium_egeszseg', 'soundness')
    foal_better_than_base_health = get_feeding_effectiveness('csiko_tap', 'soundness') > get_feeding_effectiveness('alap', 'soundness')
    print(f"  Csikotap teljesitmenyben gyengebb, mint a Teljesitmenytap: {'OK' if foal_not_strongest_perf else 'HIBA'}")
    print(f"  Csikotap soundness-ben gyengebb, mint az Egeszsegtap: {'OK' if foal_not_strongest_health else 'HIBA'}")
    print(f"  Csikotap soundness-ben jobb, mint az Alap: {'OK' if foal_better_than_base_health else 'HIBA'}")
    foal_ok = foal_not_strongest_perf and foal_not_strongest_health and foal_better_than_base_health
    print(f"  -> A csikotap kiegyensulyozott, novekedesi-fokuszu sav, nem 'legjobb mindenben': {'OK' if foal_ok else 'HIBA'}\n")

    print("--- 5) JATEKOSNAK MEGJELENITETT NEZET ---")
    for key in FEED_TIERS:
        print(f"  \"{describe_feed_tier_for_player(key)}\"")
    print()

    overall_status = "MINDEN VALIDACIO OK" if (all_ok and specialization_ok and foal_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== OSSZESITETT STATUS (1-5. blokk): {overall_status} ===\n")

    # --- 6) Takarmany-piacter bonuszszamitas validacio ---
    print("--- 6) TAKARMANY-PIACTER BONUSZ VALIDACIO (beszallito-valasztas + kombinacio) ---")
    test_cases_bonus = [
        ('gyenge', set(), 0.0, "csak gyenge alap-alapanyag, semmi koncentratum"),
        ('kivalo', set(), 5.0, "kivalo alap-alapanyag onmagaban"),
        ('jo', {'csiko', 'verseny'}, 8.5, "jo alap + csiko+verseny kombo (3.5+5)"),
        ('kivalo', {'csiko', 'verseny', 'vitaminos'}, 15.0, "MAXIMUM ESET: kivalo alap + teljes kombo + vitamin (5+5+5=15)"),
        ('kivalo', {'verseny'}, 5.0, "kivalo alap + csak verseny (nincs kombo, csiko hianyzik)"),
        ('kivalo', {'vitaminos'}, 10.0, "kivalo alap + csak vitamin, kombo nelkul (5+5)"),
    ]
    bonus_ok = True
    for quality, categories, expected, note in test_cases_bonus:
        result = calculate_feed_bonus_pct(quality, categories)
        status = "OK" if abs(result - expected) < 0.01 else "ELTERES"
        if status == "ELTERES":
            bonus_ok = False
        print(f"  {quality:8s} + {str(sorted(categories)):35s} -> {result:5.2f}%  (varhato: {expected:5.2f}%)  [{status}]  {note}")
    print(f"\n  Maximalis elerheto bonusz soha nem lepi at a {MAX_TOTAL_FEED_BONUS_PCT}%-ot: {'OK' if bonus_ok else 'HIBA'}\n")

    overall_status_final = "MINDEN VALIDACIO OK" if (all_ok and specialization_ok and foal_ok and bonus_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== VEGSO OSSZESITETT STATUS (1-6. blokk): {overall_status_final} ===\n")

    # --- 7) Szuletesi toltottsegi sav validacio ---
    print("--- 7) SZULETESI TOLTOTTSEGI SAV VALIDACIO (genetika max 55% + anyakanca gondoskodas max 5%) ---")
    test_cases_birth = [
        (99, 'kivalo', True, 60.0, "MAXIMUM ESET: tokeletes genetika + kivalo szena/zab + kancatáp (55+3+2=60)"),
        (99, 'rossz', False, 55.0, "tokeletes genetika, de semmi anyai tamogatas"),
        (50, 'kozepes', False, 28.79, "kozepes genetika (50/99*55=27.78), kozepes szena/zab (+1)"),
        (72, 'jo', True, 44.0, "72-es genetikai pontszam (a korabbi pelda-lo), jo szena/zab (+2) + kancatáp (+2)"),
        (5, 'rossz', False, 2.78, "minimum genetikai pontszam (5/99*55=2.78), semmi anyai tamogatas"),
    ]
    birth_ok = True
    for score, quality, kancatap, expected, note in test_cases_birth:
        result = calculate_birth_fill_pct(score, quality, kancatap)
        status = "OK" if abs(result - expected) < 0.1 else "ELTERES"
        if status == "ELTERES":
            birth_ok = False
        print(f"  genetika={score:3d}  szena/zab={quality:8s}  kancatáp={'igen' if kancatap else 'nem':4s} -> {result:6.2f}%  (varhato: {expected:6.2f}%)  [{status}]")
        print(f"      {note}")
    print(f"\n  Maximalis elerheto szuletesi toltottseg soha nem lepi at a 60%-ot: {'OK' if birth_ok else 'HIBA'}\n")

    grand_total_status = "MINDEN VALIDACIO OK" if (all_ok and specialization_ok and foal_ok and bonus_ok and birth_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== OSSZESITETT STATUS (1-7. blokk): {grand_total_status} ===\n")

    # --- 8) Teljes toltottsegi sav - integralt demonstracio (55/20/25) ---
    print("--- 8) TELJES TOLTOTTSEGI SAV: 55% genetika + 20% takarmany + 25% tréner ---")
    print("KEPLET: total = genetika (max 55%, fix) + takarmany (max 20%) + tréner (max 25%, gyakorlatban sosem teljes)\n")

    integration_cases = [
        (99, 5.0, 15.0, 95, "kivalo genetika, maximalis takarmanyozas (5+15=20), kivalo tréner (95)"),
        (99, 5.0, 15.0, 40, "kivalo genetika, maximalis takarmanyozas, DE gyenge tréner (40)"),
        (72, 4.0, 8.5, 70, "korabbi pelda-lo (72), jo takarmanyozas, kozepes-jo tréner (70)"),
        (30, 0.0, 0.0, 60, "gyenge genetika, semmi takarmany-bonusz, kozepes tréner"),
    ]
    fill_ok = True
    for score, maternal, adult_bonus, trainer_score, note in integration_cases:
        result = calculate_total_fill_pct(score, maternal, adult_bonus, trainer_score)
        print(f"  {note}")
        print(f"    genetika={score} -> genetikai resz: {result['genetic_part_pct']}% (max 55%)")
        print(f"    takarmany resz: {result['feeding_part_pct']}% (max 20%)")
        print(f"    tréner pontszam={trainer_score} -> realizalt resz: {result['trainer_part_pct']}% (max 25%, sosem teljes)")
        print(f"    >>> TELJES TOLTOTTSEG: {result['total_fill_pct']}%\n")

    max_possible = calculate_total_fill_pct(99, MAX_MATERNAL_CARE_BONUS_PCT, MAX_TOTAL_FEED_BONUS_PCT, TRAINER_SCORE_PRACTICAL_MAX)
    if max_possible['total_fill_pct'] >= 100.0:
        fill_ok = False
    print(f"  ELMELETI MAXIMUM (99-es genetika, teljes 20%-os takarmany-kihasznaltsag, 99-es tréner):")
    print(f"    -> {max_possible['total_fill_pct']}%  (SOSEM lehet pontosan 100%, a tréner-skala miatt: {'OK' if max_possible['total_fill_pct'] < 100.0 else 'HIBA - eleri a 100%-ot!'})\n")

    final_status = "MINDEN VALIDACIO OK" if (all_ok and specialization_ok and foal_ok and bonus_ok and birth_ok and fill_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== TELJES OSSZESITETT STATUS: {final_status} ===")
