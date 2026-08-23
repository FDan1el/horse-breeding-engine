"""
Trot Heritage - Stabling & Fertility Status Engine v1.0
=======================================================================
Ket osszefuggo rendszer:

  A) FEROHELYEK - ket kulon tipus:
       ISTALLOHELY:       draga, szukos. Tenyesztes, verseny, felneveles.
       NYUGDIJAS LEGELO:  olcso, boseges. Csak tartas, nem termel.

     Ez oldja fel a feszultseget a jatekos ket celja kozott:
       - a meddo/gyenge kanca ne pazarolja a szukos istallohelyet
       - DE a kedves lo ne essen ki a jatekbol
     A nyugdijazott lo a jatekban MARAD: szerepel a pedigrekben, az
     utodlistakon, a vervonalban - csak nem foglal munkahelyet.

     Ez valos gyakorlat: a termekenyseget vesztett vagy idos kancakat
     "pensioned" allapotba helyezik, legelon elik le a hatralevo eveiket.
     https://www.champsofthetrack.com/post/life-of-a-broodmare

  B) MEDDO STATUSZ - a JATEKOS DONTESE szerint a 3. sikertelen
     probalkozas utan all be.

     Ez valos alapon all: a "meddo" (barren) statusz onmagaban is
     rontja a kovetkezo evi eselyt - elso fedeztetesre 40% a meddo
     kancanal, szemben az 54%-kal a csikosnal.
     https://pubmed.ncbi.nlm.nih.gov/1060797/
     A leggyakoribb ok a meddove minositesre maga a "failure to
     conceive".
     https://ker.com/equinews/mare-age-biggest-predictor-of-foaling-success/

  EMBRIOATULTETES: a valosagban ezzel oldjak meg az ertekes idos kanca
  problemajat, de a jatekos kifejezett dontese alapjan EZT A JATEK NEM
  TARTALMAZZA - tul bonyolult reteg lenne. Itt csak azert jelezzuk,
  hogy a kesobbi fejlesztok tudjak: ez tudatos kihagyas, nem feledekenyseg.
"""

from enum import Enum


# =======================================================================
# 1) FEROHELY-TIPUSOK
# =======================================================================
class Housing(Enum):
    STABLE = 'stable'       # istallohely - szukos, draga
    PASTURE = 'pasture'     # nyugdijas legelo - boseges, olcso


# Jatektervezesi placeholder ertekek - a vegleges gazdasagi kalibracio
# kesobb tortenik, de az ARANY a lenyeg: a legelo nagysagrendileg
# olcsobb es sokkal tobb fer el belole.
HOUSING_CONFIG = {
    Housing.STABLE: {
        'label': 'Istállóhely',
        'upkeep_per_season': 800,
        'note': 'Tenyésztés, verseny és felnevelés csak innen lehetséges.',
    },
    Housing.PASTURE: {
        'label': 'Nyugdíjas legelő',
        'upkeep_per_season': 120,
        'note': 'A ló a játékban marad — pedigrékben, utódlistákon —, de nem termel.',
    },
}

# Mit enged az adott ferohely?
STABLE_ONLY_ACTIVITIES = {'breeding', 'racing', 'training', 'rearing'}


def can_perform(activity, housing):
    """Vegezheto-e az adott tevekenyseg ebbol a ferohelybol?"""
    if activity in STABLE_ONLY_ACTIVITIES:
        return housing == Housing.STABLE
    return True


def upkeep_cost(horses):
    """Szezonalis tartasi koltseg a teljes allomanyra."""
    total = 0
    breakdown = {Housing.STABLE: 0, Housing.PASTURE: 0}
    for h in horses:
        housing = h.get('housing', Housing.STABLE)
        cost = HOUSING_CONFIG[housing]['upkeep_per_season']
        total += cost
        breakdown[housing] += cost
    return {'total': total, 'breakdown': breakdown}


# =======================================================================
# 2) TERMEKENYSEGI STATUSZ
# =======================================================================
# A JATEKOS DONTESE: a meddo statusz a 3. SIKERTELEN PROBALKOZAS utan
# all be. Elotte a kanca meg "probalkozo" - a jatekos meg nem kap
# vegleges jelzest.
BARREN_THRESHOLD = 3


class FertilityStatus(Enum):
    MAIDEN = 'maiden'         # meg nem ellett
    FOALING = 'foaling'       # elozo evben ellett - a legjobb eselyu
    TRYING = 'trying'         # sikertelen probalkozas(ok), de meg nem meddo
    BARREN = 'barren'         # 3 sikertelen probalkozas utan
    RESTED = 'rested'         # kihagyott szezon
    PENSIONED = 'pensioned'   # nyugdijazva - mar nem fedeztetheto


STATUS_LABELS_HU = {
    FertilityStatus.MAIDEN: 'Még nem ellett',
    FertilityStatus.FOALING: 'Tavaly ellett',
    FertilityStatus.TRYING: 'Sikertelen fedeztetés',
    FertilityStatus.BARREN: 'Meddő',
    FertilityStatus.RESTED: 'Pihentetett',
    FertilityStatus.PENSIONED: 'Nyugdíjazva',
}


def update_fertility_status(mare, conceived):
    """A fedeztetesi szezon vegen frissiti a kanca statuszat.

    mare mezoi: status, failed_attempts
    conceived: True/False - fogant-e ebben a szezonban
    """
    status = mare.get('status', FertilityStatus.MAIDEN)
    failed = mare.get('failed_attempts', 0)

    if status == FertilityStatus.PENSIONED:
        return {'status': status, 'failed_attempts': failed, 'warning': None}

    if conceived:
        # sikeres fedeztetes: a szamlalo nullazodik
        return {
            'status': FertilityStatus.FOALING,
            'failed_attempts': 0,
            'warning': None,
        }

    failed += 1
    if failed >= BARREN_THRESHOLD:
        return {
            'status': FertilityStatus.BARREN,
            'failed_attempts': failed,
            'warning': ('Három egymást követő sikertelen fedeztetés után a kanca '
                        'meddőnek minősül. Az esélye tovább romlik — érdemes '
                        'mérlegelni a nyugdíjazást.'),
        }

    remaining = BARREN_THRESHOLD - failed
    return {
        'status': FertilityStatus.TRYING,
        'failed_attempts': failed,
        'warning': (f'{failed}. sikertelen fedeztetés. További {remaining} '
                    f'eredménytelen próbálkozás után meddőnek minősül.'),
    }


def pension_mare(mare):
    """Nyugdijazas: a kanca legelore kerul, tobbe nem fedeztetheto, de a
    jatekban marad - pedigrekben, utodlistakon, a vervonalban."""
    return {
        **mare,
        'status': FertilityStatus.PENSIONED,
        'housing': Housing.PASTURE,
        'note': 'Nyugdíjazva — a vérvonalban és az utódlistákon továbbra is szerepel.',
    }


def conception_status_key(status):
    """A stud_sim.py vemhesulesi modelljehez illeszkedo kulcs."""
    mapping = {
        FertilityStatus.FOALING: 'foaling',
        FertilityStatus.MAIDEN: 'maiden',
        FertilityStatus.TRYING: 'barren',    # a probalkozo mar a meddo savban van
        FertilityStatus.BARREN: 'barren',
        FertilityStatus.RESTED: 'rested',
    }
    return mapping.get(status)


# =======================================================================
# 3) DONTESTAMOGATAS: megeri-e istallohelyen tartani?
# =======================================================================
def stabling_advice(mare, conception_pct, stable_upkeep=None):
    """Jatekos-barat javaslat, hogy erdemes-e istallohelyen tartani a
    kancat. NEM kenyszerit semmire - csak lathatova teszi a koltseget."""
    if mare.get('status') == FertilityStatus.PENSIONED:
        return 'Nyugdíjazva — legelőn, minimális költséggel.'

    stable = HOUSING_CONFIG[Housing.STABLE]['upkeep_per_season']
    pasture = HOUSING_CONFIG[Housing.PASTURE]['upkeep_per_season']
    diff = stable - pasture

    if conception_pct >= 68:
        return f'Érdemes istállóhelyen tartani — jó esély a csikóra.'
    if conception_pct >= 50:
        return (f'Bizonytalan. Az istállóhely szezononként {diff} B$-ral többe kerül, '
                f'és egy férőhelyet is leköt.')
    return (f'Alacsony esély. Az istállóhely szezononként {diff} B$-ral többe kerül, '
            f'és elvesz egy helyet egy termékenyebb kanca elől.')


# =======================================================================
# VALIDACIO / DEMONSTRACIO
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - STABLING & FERTILITY STATUS ENGINE v1.0 ===\n")

    print("--- 1) FEROHELY-TIPUSOK ---")
    for h in Housing:
        c = HOUSING_CONFIG[h]
        print(f"  {c['label']:20s} {c['upkeep_per_season']:5d} B$/szezon")
        print(f"     {c['note']}")
    ratio = (HOUSING_CONFIG[Housing.STABLE]['upkeep_per_season'] /
             HOUSING_CONFIG[Housing.PASTURE]['upkeep_per_season'])
    print(f"  -> Az istállóhely {ratio:.1f}× drágább, ezért a nyugdíjazás valódi könnyítés.\n")

    print("--- 2) MIT ENGED AZ ADOTT FEROHELY ---")
    for activity in ['breeding', 'racing', 'training', 'rearing', 'showing']:
        s = "IGEN" if can_perform(activity, Housing.STABLE) else "NEM "
        p = "IGEN" if can_perform(activity, Housing.PASTURE) else "NEM "
        print(f"  {activity:10s} istálló: [{s}]   legelő: [{p}]")
    print()

    print("--- 3) MEDDO STATUSZ: a 3. sikertelen probalkozas utan ---")
    mare = {'name': 'Velvet Solstice', 'age': 14,
            'status': FertilityStatus.FOALING, 'failed_attempts': 0}
    print(f"  Kiindulás: {mare['name']}, {STATUS_LABELS_HU[mare['status']]}\n")

    season_results = [False, False, False]
    for i, conceived in enumerate(season_results, 1):
        res = update_fertility_status(mare, conceived)
        mare.update(res)
        print(f"  {i}. szezon: {'fogant' if conceived else 'nem fogant'} "
              f"-> {STATUS_LABELS_HU[mare['status']]}")
        if res['warning']:
            print(f"     ⚠ {res['warning']}")
    print()

    print("  Ellenpélda — sikeres fedeztetés nullázza a számlálót:")
    mare2 = {'name': 'Amber', 'status': FertilityStatus.TRYING, 'failed_attempts': 2}
    r = update_fertility_status(mare2, conceived=True)
    print(f"     2 sikertelen után fogant -> {STATUS_LABELS_HU[r['status']]}, "
          f"számláló: {r['failed_attempts']}\n")

    print("--- 4) NYUGDIJAZAS: a lo a jatekban marad ---")
    pensioned = pension_mare(mare)
    print(f"  {pensioned['name']}: {STATUS_LABELS_HU[pensioned['status']]}")
    print(f"     Férőhely: {HOUSING_CONFIG[pensioned['housing']]['label']} "
          f"({HOUSING_CONFIG[pensioned['housing']]['upkeep_per_season']} B$/szezon)")
    print(f"     {pensioned['note']}")
    print(f"     Fedeztethető: {'igen' if can_perform('breeding', pensioned['housing']) else 'nem'}\n")

    print("--- 5) DONTESTAMOGATAS (nem kenyszerit, csak lathatova tesz) ---")
    for name, pct in [('fiatal csikós kanca', 88.0), ('átlagos kanca', 72.0),
                      ('bizonytalan kanca', 54.0), ('meddő, idős kanca', 38.0)]:
        m = {'status': FertilityStatus.FOALING}
        print(f"  {name:22s} ({pct:4.1f}%): {stabling_advice(m, pct)}")
    print()

    print("--- 6) SZEZONALIS TARTASI KOLTSEG (pelda allomany) ---")
    herd = [
        {'name': 'Amber',    'housing': Housing.STABLE},
        {'name': 'Quietfire','housing': Housing.STABLE},
        {'name': 'Duskmere', 'housing': Housing.STABLE},
        {'name': 'Velvet',   'housing': Housing.PASTURE},
        {'name': 'Old Rose', 'housing': Housing.PASTURE},
    ]
    cost = upkeep_cost(herd)
    print(f"  3 istállóhely + 2 nyugdíjas legelő")
    print(f"     istálló: {cost['breakdown'][Housing.STABLE]:5d} B$")
    print(f"     legelő:  {cost['breakdown'][Housing.PASTURE]:5d} B$")
    print(f"     összesen: {cost['total']:5d} B$/szezon")
    all_stable = upkeep_cost([{**h, 'housing': Housing.STABLE} for h in herd])
    print(f"  Ha mind az 5 istállóban állna: {all_stable['total']} B$ "
          f"(+{all_stable['total'] - cost['total']} B$)\n")

    print("--- 7) VALIDACIO ---")
    checks = [
        ('A meddő státusz pontosan a 3. sikertelen után áll be',
         update_fertility_status({'status': FertilityStatus.TRYING, 'failed_attempts': 2},
                                 False)['status'] == FertilityStatus.BARREN),
        ('A 2. sikertelen még csak figyelmeztetés',
         update_fertility_status({'status': FertilityStatus.TRYING, 'failed_attempts': 1},
                                 False)['status'] == FertilityStatus.TRYING),
        ('Sikeres fedeztetés nullázza a számlálót',
         update_fertility_status({'status': FertilityStatus.TRYING, 'failed_attempts': 2},
                                 True)['failed_attempts'] == 0),
        ('Legelőről nem lehet fedeztetni',
         not can_perform('breeding', Housing.PASTURE)),
        ('Legelőről nem lehet versenyezni',
         not can_perform('racing', Housing.PASTURE)),
        ('A nyugdíjazott ló legelőre kerül',
         pension_mare({'name': 'x'})['housing'] == Housing.PASTURE),
        ('A nyugdíjazás érdemben olcsóbb',
         HOUSING_CONFIG[Housing.PASTURE]['upkeep_per_season'] <
         HOUSING_CONFIG[Housing.STABLE]['upkeep_per_season'] / 3),
        ('Nyugdíjazott lovat nem lehet újra fedeztetni',
         update_fertility_status({'status': FertilityStatus.PENSIONED,
                                  'failed_attempts': 0}, True)['status'] == FertilityStatus.PENSIONED),
    ]
    all_ok = True
    for label, ok in checks:
        if not ok:
            all_ok = False
        print(f"  [{'OK ' if ok else 'HIBA'}] {label}")
    print()
    print(f"=== OSSZESITETT STATUS: "
          f"{'MINDEN VALIDACIO OK' if all_ok else 'VAN ELTERES - ELLENORIZENDO'} ===")
