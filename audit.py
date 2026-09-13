"""
Breeder Tycoon - Consistency Audit v1.0
=======================================================================
LOGIKAI KEPTELENSEGEK KERESESE AZ EGESZ MOTORLANCON.

A "2 eves lo 22 starttal" hiba mutatta meg, hogy a modulok kulon-kulon
validaltak, de az EGYUTTES allapotukat semmi nem ellenorizte.

Ez a modul NEM egysegteszt. Azt keresi, ami MATEMATIKAILAG lehetseges,
de A VILAGBAN KEPTELENSEG:
  - fiatalabb lo, mint amennyi startja van
  - csiko, akinek a szuloje nala fiatalabb
  - nyeremeny gyozelem nelkul, vagy forditva
  - kifutott csik mellett aktiv statusz
  - tenyeszallat, aki sosem volt versenyben ES nem is alapito
  - onmaga ose (koros pedigre)
"""

from collections import Counter, defaultdict


# =======================================================================
# SEGEDEK
# =======================================================================
def _stats(world, h):
    return world.db.stats(h.horse_id)


class Finding:
    def __init__(self, code, severity, horse, detail):
        self.code, self.severity = code, severity
        self.horse, self.detail = horse, detail

    def __repr__(self):
        nm = getattr(self.horse, 'name', '?')
        return f"[{self.severity}] {self.code}: {nm} — {self.detail}"


# =======================================================================
# ELLENORZESEK
# =======================================================================
def check_age_vs_starts(world):
    """A lo 2 evesen all versenybe, es szezononkent ~7 startot fut.

    EZ VOLT A MEGTALALT HIBA: 2 eves lo 22 starttal.
    """
    out = []
    for h in world.horses.values():
        st = _stats(world, h)
        if st.starts == 0:
            continue
        # A lo 2 EVESEN all versenybe, es mar az elso szezonjaban
        # futhat ~7-et. Ezert az elso 7 start MEG belefer a 2 eves korba.
        min_age = 2 + max(0, (st.starts - 1) // 7)
        if h.age < min_age:
            out.append(Finding('AGE_VS_STARTS', 'HIBA', h,
                               f"{h.age} éves, de {st.starts} startja van "
                               f"(minimum {min_age} lenne)"))
    return out


def check_parent_ages(world):
    """A szulo nem lehet fiatalabb a gyerekenel, es legalabb 3 evvel
    idosebbnek kell lennie (vemhesseg + a csiko kora)."""
    out = []
    for h in world.horses.values():
        for key, role in (('sire_id', 'apja'), ('dam_id', 'anyja')):
            pid = getattr(h, key, None)
            p = world.horses.get(pid) if pid else None
            if p is None:
                continue
            if p.age <= h.age:
                out.append(Finding('PARENT_YOUNGER', 'HIBA', h,
                                   f"{h.age} éves, de az {role} "
                                   f"({p.name}) csak {p.age}"))
            elif p.age - h.age < 3:
                out.append(Finding('PARENT_TOO_CLOSE', 'GYANUS', h,
                                   f"{h.age} éves, az {role} {p.age} — "
                                   f"csak {p.age - h.age} év különbség"))
    return out


def check_earnings_vs_form(world):
    """Nyeremeny csak helyezessel jarhat; gyozelem nyeremeny nelkul
    szinten gyanus."""
    out = []
    for h in world.horses.values():
        st = _stats(world, h)
        if st.career_earnings > 0 and st.starts == 0:
            out.append(Finding('EARNINGS_NO_START', 'HIBA', h,
                               f"{st.career_earnings} B$ nyeremény, "
                               f"de nincs startja"))
        if st.wins > st.starts:
            out.append(Finding('WINS_GT_STARTS', 'HIBA', h,
                               f"{st.wins} győzelem {st.starts} startból"))
        if st.wins > 0 and st.career_earnings == 0:
            out.append(Finding('WIN_NO_MONEY', 'GYANUS', h,
                               f"{st.wins} győzelem, de nulla nyeremény"))
    return out


def check_black_type(world):
    """A black type gyozelem nem lehet tobb a gyozelemnel, es a
    klasszikus sem tobb a black type-nal."""
    out = []
    for h in world.horses.values():
        st = _stats(world, h)
        if st.black_type_wins > st.wins:
            out.append(Finding('BT_GT_WINS', 'HIBA', h,
                               f"{st.black_type_wins} black type, "
                               f"de csak {st.wins} győzelem"))
        if st.classic_wins > st.black_type_wins:
            out.append(Finding('CLASSIC_GT_BT', 'HIBA', h,
                               f"{st.classic_wins} klasszikus, de csak "
                               f"{st.black_type_wins} black type"))
    return out


def check_progeny_counts(world):
    """Az ivadek-szamlalo egyezzen a tenyleges utodszammal, es a
    black type utod ne legyen tobb az osszes utodnal."""
    out = []
    actual = Counter()
    for h in world.horses.values():
        for key in ('sire_id', 'dam_id'):
            pid = getattr(h, key, None)
            if pid:
                actual[pid] += 1

    for h in world.horses.values():
        st = _stats(world, h)
        real = actual.get(h.horse_id, 0)
        if st.progeny_count != real:
            out.append(Finding('PROGENY_MISMATCH', 'HIBA', h,
                               f"a számláló {st.progeny_count} utódot mutat, "
                               f"valójában {real}"))
        if st.progeny_black_type > max(real, st.progeny_count):
            out.append(Finding('PROGENY_BT_TOO_MANY', 'HIBA', h,
                               f"{st.progeny_black_type} black type utód, "
                               f"de csak {real} utódja van"))
        if st.progeny_runners > max(real, st.progeny_count):
            out.append(Finding('PROGENY_RUNNERS_TOO_MANY', 'HIBA', h,
                               f"{st.progeny_runners} futó utód, "
                               f"de csak {real} utódja van"))
    return out


def check_lifecycle_bars(world):
    """A csikok es a statusz osszhangban legyenek."""
    out = []
    for h in world.horses.values():
        if h.stage == 'retired_out':
            continue
        if h.life_bar <= 0:
            out.append(Finding('DEAD_BUT_ACTIVE', 'HIBA', h,
                               f"az élet-csík kifutott, mégis "
                               f"'{h.stage}' állapotban van"))
        if h.stage == 'racer' and h.career_bar <= 0:
            out.append(Finding('NO_CAREER_BUT_RACING', 'HIBA', h,
                               "a versenykarrier kifutott, mégis versenyló"))
        for name, val in (('life_bar', h.life_bar),
                          ('career_bar', h.career_bar),
                          ('freshness', h.freshness)):
            if val is not None and not (0 <= val <= 100.01):
                out.append(Finding('BAR_OUT_OF_RANGE', 'HIBA', h,
                                   f"{name} = {val:.1f} (0-100 lenne)"))
        if h.breeding_bar is not None and not (0 <= h.breeding_bar <= 100.01):
            out.append(Finding('BAR_OUT_OF_RANGE', 'HIBA', h,
                               f"breeding_bar = {h.breeding_bar:.1f}"))
    return out


def check_stage_sex(world):
    """A men nem kaphat tenyeszcsikot (korlatlanul fedezhet), es a
    csiko nem lehet tenyeszallat."""
    out = []
    for h in world.horses.values():
        if h.sex == 'colt' and h.breeding_bar is not None:
            out.append(Finding('STALLION_HAS_BAR', 'GYANUS', h,
                               "ménnek nem lehet tenyészcsíkja"))
        if h.stage == 'breeding' and h.age < 3:
            out.append(Finding('TOO_YOUNG_TO_BREED', 'HIBA', h,
                               f"{h.age} évesen tenyészállat"))
        if h.stage == 'racer' and h.age < 2:
            out.append(Finding('TOO_YOUNG_TO_RACE', 'HIBA', h,
                               f"{h.age} évesen versenyló"))
    return out


def check_pedigree_cycles(world):
    """Egy lo nem lehet sajat ose."""
    out = []
    for h in world.horses.values():
        seen, frontier, depth = set(), [h.horse_id], 0
        while frontier and depth < 12:
            nxt = []
            for hid in frontier:
                x = world.horses.get(hid)
                if x is None:
                    continue
                for key in ('sire_id', 'dam_id'):
                    pid = getattr(x, key, None)
                    if not pid:
                        continue
                    if pid == h.horse_id:
                        out.append(Finding('PEDIGREE_CYCLE', 'HIBA', h,
                                           "önmaga őse a pedigréjében"))
                        frontier = []
                        break
                    if pid not in seen:
                        seen.add(pid)
                        nxt.append(pid)
            frontier = nxt
            depth += 1
    return out


def check_names(world):
    """Egyedi nevek, hosszkorlat, ertelmes forma."""
    out = []
    seen = {}
    for h in world.horses.values():
        low = h.name.lower()
        if low in seen:
            out.append(Finding('DUPLICATE_NAME', 'HIBA', h,
                               f"a név már foglalt: {seen[low]}"))
        seen[low] = h.name
        if len(h.name) > 18:
            out.append(Finding('NAME_TOO_LONG', 'HIBA', h,
                               f"{len(h.name)} karakter (max 18)"))
        # elfajult nev: ugyanaz a szotag tobbszor
        for frag in ('wren', 'oak', 'elm', 'gild', 'cold', 'fern'):
            if low.count(frag) > 1:
                out.append(Finding('DEGENERATE_NAME', 'GYANUS', h,
                                   f"ismétlődő szótag: {frag}"))
    return out


def check_ownership(world):
    """Minden lonak van tulajdonosa es tenyesztoje."""
    out = []
    for h in world.horses.values():
        if not getattr(h, 'owner_id', None):
            out.append(Finding('NO_OWNER', 'HIBA', h, "nincs tulajdonosa"))
        if not getattr(h, 'breeder_id', None):
            out.append(Finding('NO_BREEDER', 'HIBA', h, "nincs tenyésztője"))
    return out


def check_lineage_ids(world):
    """A family_id az anyatol, a sire_line_id az apatol oroklodik."""
    out = []
    for h in world.horses.values():
        dam = world.horses.get(getattr(h, 'dam_id', None))
        sire = world.horses.get(getattr(h, 'sire_id', None))
        if dam is not None and dam.family_id and h.family_id != dam.family_id:
            out.append(Finding('FAMILY_ID_BROKEN', 'HIBA', h,
                               "a family_id nem az anyjától származik"))
        if sire is not None and sire.sire_line_id \
                and h.sire_line_id != sire.sire_line_id:
            out.append(Finding('SIRE_LINE_BROKEN', 'HIBA', h,
                               "a sire_line_id nem az apjától származik"))
    return out


def check_colour_genetics(world):
    """A szurke lo szinesen szuletik; a szin a genotipushoz illjen."""
    out = []
    for h in world.horses.values():
        if h.colour == 'Gray' and not h.will_grey:
            out.append(Finding('GREY_FLAG', 'GYANUS', h,
                               "szürke, de nincs őszülés-jelölve"))
        if h.will_grey and h.born_colour == 'Gray':
            out.append(Finding('BORN_GREY', 'GYANUS', h,
                               "szürkének született (színesen kellene)"))
    return out


ALL_CHECKS = [
    ('Kor vs. startszám', check_age_vs_starts),
    ('Szülők kora', check_parent_ages),
    ('Nyeremény vs. forma', check_earnings_vs_form),
    ('Black type következetesség', check_black_type),
    ('Ivadék-számlálók', check_progeny_counts),
    ('Életciklus-csíkok', check_lifecycle_bars),
    ('Állapot és nem', check_stage_sex),
    ('Pedigré-körök', check_pedigree_cycles),
    ('Névadás', check_names),
    ('Tulajdonos és tenyésztő', check_ownership),
    ('Vonal-azonosítók', check_lineage_ids),
    ('Színgenetika', check_colour_genetics),
]


def audit(world, verbose=True):
    all_findings = []
    for label, fn in ALL_CHECKS:
        found = fn(world)
        all_findings.extend(found)
        errors = [f for f in found if f.severity == 'HIBA']
        sus = [f for f in found if f.severity == 'GYANUS']
        if verbose:
            mark = 'OK ' if not errors else 'HIBA'
            extra = ''
            if errors:
                extra = f"  {len(errors)} hiba"
            if sus:
                extra += f"  {len(sus)} gyanús"
            print(f"  [{mark}] {label:30s}{extra}")
            for f in (errors[:3] + sus[:2]):
                print(f"          {f}")
    return all_findings


# =======================================================================
# FUTTATAS
# =======================================================================
if __name__ == '__main__':
    import random
    import worldgen as WG
    import game as G
    import trainer_sim as TR
    import jockey_sim as JK

    print("=== BREEDER TYCOON - KOVETKEZETESSEG-ELLENORZES ===\n")
    print("Nem egysegteszt: azt keresi, ami matematikailag lehetseges,")
    print("de a vilagban KEPTELENSEG.\n")

    print("--- 1) AZ ALAPITO VILAG ---")
    world, gens = WG.build_world(seed=2024)
    print(f"  {len(world.horses)} ló, {len(world.db.races)} futam\n")
    f1 = audit(world)
    print()

    print("--- 2) 12 SZEZON JATEK UTAN ---")
    trainer = TR.generate_random_trainer('T')
    jockey = JK.generate_random_jockey('J')
    stock = WG.give_starting_stock(world, gens, 'player')
    for m in stock['mares']:
        m.stage, m.age = 'breeding', 5
        if (m.breeding_bar or 0) < 40:
            m.breeding_bar = 65.0

    def plan_for(w):
        studs = [h for h in w.horses.values()
                 if h.sex == 'colt' and h.stage == 'breeding']
        studs.sort(key=lambda h: -h.genetic_score())
        p = {}
        for mare in w.owned_by('player', 'breeding'):
            for st in studs:
                if G.check_covering(w, mare, st, 'player')['allowed']:
                    p[mare.horse_id] = st.horse_id
                    break
        return p

    for _ in range(12):
        G.play_season(world, 'player', trainer, jockey,
                      breeding_plan=plan_for(world))
    print(f"  {len(world.horses)} ló, {len(world.db.races)} futam\n")
    f2 = audit(world)
    print()

    errors = [f for f in f2 if f.severity == 'HIBA']
    sus = [f for f in f2 if f.severity == 'GYANUS']

    print("--- 3) OSSZESITES ---")
    by_code = Counter(f.code for f in f2)
    if by_code:
        for code, n in by_code.most_common():
            sev = next(f.severity for f in f2 if f.code == code)
            print(f"  {sev:7s} {code:26s} {n:>4d} eset")
    else:
        print("  Nincs találat.")
    print()
    print(f"  Összesen: {len(errors)} hiba, {len(sus)} gyanús eset "
          f"{len(world.horses)} lóra")
    print()
    print(f"=== STATUS: "
          f"{'A MOTOR KOVETKEZETES' if not errors else 'JAVITANDO'} ===")
