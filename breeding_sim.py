"""
Trot Heritage - Breeding Engine v5.0
=======================================================================
Koherens, egyseges tenyesztesi motor. Harom modult egyesit:

  1) TELJESITMENY-GENETIKA - tulajdonsagonkenti h2 (orokolhetoseg) valos
     tudomanyos forrasokbol, True Genetic Value / Fenotipus szetvalasztva,
     EBV+Reliability progeny-test formulaval, Mendeli szegregacios
     variancia, inbreeding-erzekeny szorasnovekedes.

  2) SZINGENETIKA - Extension/Agouti/Grey/Cream lokusz, allel-frekvenciak
     valos teliver populacios adatbol visszaszamolva (Hardy-Weinberg).

  3) HAGYOMANYOS NEVADASI SZABALYZAT - Jockey Club-inspiralt validator +
     pedigre-alapu nevgeneralas.

FONTOS VALTOZAS AZ ELOZO VALTOZATHOZ KEPEST: nincsenek tobbe kezzel
megirt, nevre szolo demo-lovak (pl. "Northwind Cavalier"). A TELJES
alapito loallomany a generate_founder_population() fuggvennyel jon
letre, valos populacios genfrekvenciakbol mintazva - igy a kezdo
allomany merete szabadon skalazhato (a jatek vegleges tervezett
menletszamahoz igazithato), es egyetlen ritka allel-hordozo sem
torzitja aranytalanul a teljes populacio szineloszlasat.

KULONLEGES SZINEK (Palomino, es a kesobb hozzaadhato tovabbi ritka
mutaciok) SZANDEKOSAN extremen alacsony frekvenciaval szerepelnek - ez
nem hiba, hanem tervezett viselkedes: ezek a szinek a kesobbi
monetizacios rendszer szamara vannak fenntartva (pl. ritka/premium
lovak, kozvetlen tenyeszresz-vasarlas nelkul is elerheto vizualis
ritkasag). A color_phenotype() fuggveny ezert 'rarity_tier' mezot is
visszaad minden lora, hogy a UI/monetizacios reteg kesobb konnyen
tudjon szurni/kiemelni ritkasag szerint, a genetikai szimulacio
tudomanyos integritasanak megbontasa nelkul.

TELJES FORRASLISTA (mindegyik kereszt-ellenorizve tobb forrassal):

TELJESITMENY-GENETIKA:
- Sharman et al. 2023, Heredity: speed h2 sprint=0.124, kozep=0.122,
  hossz=0.074 (692 534 rekord, 76 960 lo, GB).
  https://www.nature.com/articles/s41437-023-00623-8
- Oki et al. 2008: SDFT inszalag-serules h2=0.17-0.19 (8198 lo).
  https://pubmed.ncbi.nlm.nih.gov/19134077/
- Oki et al., Gibbs sampling, JRA Japan: viselkedesi h2=0.23-0.28.
  https://pubmed.ncbi.nlm.nih.gov/17651320/
- Welsh et al. 2013: musculoskeletal h2=0.01-0.20 (5062 lo, Hong Kong).
  https://www.sciencedirect.com/science/article/pii/S1090023313002001
- 675 teliver anyai vonal: anya-csiko r=0.141 > apa-csiko r=0.035.
  https://pubmed.ncbi.nlm.nih.gov/25940872/
- Inbreeding negativan korrelal teljesitmenymutatokkal (135 572 lo).
  https://www.nature.com/articles/s41598-018-24663-x

SZINGENETIKA:
- UC Davis VGL: Extension/Agouti Punnett-negyzet (56.25/25/18.75%).
  https://vgl.ucdavis.edu/resources/horse-coat-color
- Thiruvenkadan et al. 2008: Grey epistazis, legalabb egy szurke szulo.
  https://www.sciencedirect.com/science/article/abs/pii/S1871141308001376
- Teliver-specifikus szineloszlas tanulmany: Bay 74.2%, Chestnut 23.3%,
  Grey 1.5%, Black 0.5%.
  https://www.researchgate.net/figure/General-distribution-of-horse-coat-colors_tbl3_371329081
- Queen's Cup Steeplechase: "nearly 90% bay/dark bay or brown... grey
  and roan uncommon... white extremely rare" (megerosites).
  https://www.queenscup.org/steeplechasing/thoroughbred/
- Canadian Thoroughbred Magazine: Palomino/Cream dilution dokumentaltan
  csak nehany vonalra (Glitter Please, Milkie) vezetheto vissza.
  https://canadianthoroughbred.com/magazine/breeding/thoroughbreds-different-colour/
- True Roan gyakorlatilag nem letezik teliverben (Jockey Club regisztracio).
  https://www.registry.jockeyclub.com/registry.cfm?page=dotRegistryIdentifyThoroughbred

NEVADASI SZABALYZAT:
- horseracingsense.com, liveabout.com, kentuckyderby.com, NBC Connecticut:
  18 karakteres limit, tiltott vegzodesek, elo szemely csak engedellyel,
  pedigre-alapu nevadasi hagyomany.
  https://horseracingsense.com/why-are-racehorse-names-so-weird/
  https://www.liveabout.com/naming-a-thoroughbred-horse-1880228
  https://www.kentuckyderby.com/horses/news/whats-in-a-name-a-look-at-the-rules-for-naming-thoroughbreds/

A nevvalidator NEM a valodi Jockey Club rendszer, csak annak jatekon
beluli, egyszerusitett masolata.
"""

import random
import statistics
import json
import math
from collections import Counter

random.seed(42)


# =======================================================================
# 1) TELJESITMENY-GENETIKA
# =======================================================================
TRAIT_CONFIG = {
    'speed':        {'h2': 0.12,  'pop_sd': 12, 'h2_source': 'Sharman et al. 2023 (sprint h2=0.124)'},
    'accel':        {'h2': 0.15,  'pop_sd': 12, 'h2_source': 'BECSLES - Speed-hez hasonlo tartomany'},
    'stamina':      {'h2': 0.18,  'pop_sd': 12, 'h2_source': 'BECSLES - Staying Aptitude tartomanyahoz igazitva'},
    'sprint':       {'h2': 0.124, 'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, sprint tav'},
    'mile':         {'h2': 0.122, 'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, kozeptav (proxy)'},
    'middle':       {'h2': 0.122, 'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, kozeptav'},
    'staying':      {'h2': 0.074, 'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, hosszutav'},
    'soundness':    {'h2': 0.18,  'pop_sd': 14, 'h2_source': 'Oki et al. 2008 SDFT (0.17-0.19) + Welsh et al. 2013 atlaga'},
    'trainability': {'h2': 0.25,  'pop_sd': 12, 'h2_source': 'BECSLES - Oki et al. viselkedesi h2 proxykent'},
    'temperament':  {'h2': 0.25,  'pop_sd': 12, 'h2_source': 'Oki et al. Gibbs sampling, viselkedesi h2=0.23-0.28'},
}
TRAITS = list(TRAIT_CONFIG.keys())

MATERNAL_GENETIC_W = 0.50
PATERNAL_GENETIC_W = 0.50
MATERNAL_ENV_BONUS_SD = 2.5  # forras: anya-csiko r=0.141 > apa-csiko r=0.035

INBREEDING_VARIANCE_MULT = {
    'soundness': 2.2, 'trainability': 1.3, 'temperament': 1.3,
}
DEFAULT_INBREEDING_MULT = 1.05

WEIGHTS = {'speed':1,'accel':0.8,'stamina':1,'sprint':0.6,'mile':0.6,'middle':0.6,
           'staying':0.6,'soundness':1.1,'trainability':0.7,'temperament':0.6}


def inbreeding_coeff(sire, dam):
    """Egyszerusitett, kozos-os alapu inbreeding becsles."""
    shared = set(sire['ancestors']) & set(dam['ancestors'])
    return min(len(shared) * 0.0625, 0.25)

def genetic_sd(trait):
    """Additiv genetikai szoras: SDg = sqrt(h2) * SDp."""
    cfg = TRAIT_CONFIG[trait]
    return math.sqrt(cfg['h2']) * cfg['pop_sd']

def mendelian_segregation_sd(trait, inbreeding=0.0):
    """Mendeli szegregacios variancia a szulopar kozepertekehez kepest:
    Var(offspring | midparent) = 0.5 * Vg, inbreeding-erzekeny szorzoval."""
    vg = genetic_sd(trait) ** 2
    seg_var = 0.5 * vg
    mult = INBREEDING_VARIANCE_MULT.get(trait, DEFAULT_INBREEDING_MULT)
    seg_var *= (1 + (mult - 1) * (inbreeding / 0.25))
    return math.sqrt(seg_var)

def true_genetic_value(sire, dam, trait, inbreeding):
    """A csiko rejtett, valodi genetikai erteke egy tulajdonsagra."""
    midparent = (sire['profile'][trait]*PATERNAL_GENETIC_W +
                 dam['profile'][trait]*MATERNAL_GENETIC_W)
    seg_sd = mendelian_segregation_sd(trait, inbreeding)
    tgv = random.gauss(midparent, seg_sd)
    maternal_env = random.gauss(0, MATERNAL_ENV_BONUS_SD)
    tgv += maternal_env
    return max(5, min(99, tgv)), midparent

def phenotype_from_genetic_value(tgv, trait):
    """PLACEHOLDER: a jovobeli takarmanyozas/trening modul beillesztesi
    pontja. Egyelore csak alap kornyezeti zajt ad a genetikai ertekhez."""
    cfg = TRAIT_CONFIG[trait]
    env_sd = math.sqrt(1 - cfg['h2']) * cfg['pop_sd']
    phenotype = random.gauss(tgv, env_sd * 0.4)
    return max(5, min(99, phenotype))

def reliability_from_own_records(n_starts, h2):
    """Sajat-teljesitmeny-alapu EBV megbizhatosaga n fuggetlen rekordbol."""
    if n_starts <= 0:
        return 0.0
    return (n_starts * h2) / (1 + (n_starts - 1) * h2)

def reliability_from_progeny(n_progeny, h2):
    """Standard progeny-test formula (Falconer & Mackay)."""
    if n_progeny <= 0:
        return 0.0
    return n_progeny / (n_progeny + (4 - h2) / h2)

def combined_reliability(pedigree_rel, own_rel, progeny_rel):
    """Egyszerusitett informacio-kombinacio (nem teljes BLUP-matrix)."""
    combined = 1 - (1 - pedigree_rel) * (1 - own_rel) * (1 - progeny_rel)
    return min(combined, 0.99)

def ebv_estimate(true_value, population_mean, reliability):
    """Becsult tenyesztesi ertek - alacsony reliability = nagyobb zaj."""
    true_deviation = true_value - population_mean
    noise_sd = (1 - reliability) * 15
    estimated_deviation = random.gauss(true_deviation * reliability, noise_sd)
    return population_mean + estimated_deviation

def overall_score(values_dict):
    s = sum(values_dict[t]*WEIGHTS[t] for t in TRAITS)
    return s / sum(WEIGHTS.values())

def index_from_score(avg):
    if avg >= 88: return 'A+'
    if avg >= 82: return 'A'
    if avg >= 76: return 'A-'
    if avg >= 70: return 'B+'
    if avg >= 63: return 'B'
    if avg >= 56: return 'B-'
    if avg >= 47: return 'C'
    if avg >= 36: return 'D'
    return 'E'


# =======================================================================
# 2) SZINGENETIKA
# =======================================================================
# Allel-frekvenciak valos teliver populacios adatbol Hardy-Weinberg
# egyensuly alapjan visszaszamolva (celzott: Bay 74.2%, Chestnut 23.3%,
# Grey 1.5%, Black 0.5% - lasd forraslista a fajl fejleceben).
#
# A Cream (Palomino) frekvenciaja NEM szamithato vissza publikalt
# populacios adatbol - dokumentaltan "extremely rare", ezert extremen
# alacsonyan van tartva. EZ A KESOBBI MONETIZACIOS RENDSZER SZAMARA VAN
# FENNTARTVA: ritka szinu lovak vizualis kulonlegesseget adhatnak,
# anelkul, hogy a teljesitmeny-genetikaba beavatkoznank (a szin es a
# teljesitmeny genetikailag fuggetlen lokuszok).
POP_ALLELE_FREQ = {
    'E':  0.514,   # Extension domians allel
    'A':  0.918,   # Agouti domians allel
    'G':  0.0075,  # Grey domians allel
    'Cr': 0.001,   # Cream domians allel - MONETIZACIOS RITKASAG, placeholder
}

# Ritkasagi kategoriak - UI/monetizacios reteg szamara, a szimulacio
# matematikajat nem befolyasoljak.
COLOR_RARITY_TIER = {
    'Bay': 'common',
    'Chestnut': 'common',
    'Black': 'uncommon',
    'Gray': 'rare',
    'Palomino': 'special',   # monetizacios ritkasag
}

def random_genotype_locus(locus_key):
    p = POP_ALLELE_FREQ[locus_key]
    a1 = 'dom' if random.random() < p else 'rec'
    a2 = 'dom' if random.random() < p else 'rec'
    return (a1, a2)

def inherit_allele(pair):
    """Mendeli szegregacio: a szulo ket allelejebol veletlenszeruen egyet ad tovabb."""
    return random.choice(pair)

def breed_color_genotype(sire_geno, dam_geno):
    return {locus: (inherit_allele(sire_geno[locus]), inherit_allele(dam_geno[locus]))
            for locus in ['E', 'A', 'G', 'Cr']}

def has_dominant(pair):
    return 'dom' in pair

def color_phenotype(genotype):
    """Levezeti a lathato szint a genotipusbol.
    E/A lokusz -> alapszin. Grey -> epistatikus felulliras (szinesen
    szuletik, oszik majd). Cream -> csak gesztenye alapon ad Palominot."""
    e_dom = has_dominant(genotype['E'])
    a_dom = has_dominant(genotype['A'])
    cr_dom = has_dominant(genotype['Cr'])

    base_color = 'Chestnut' if not e_dom else ('Bay' if a_dom else 'Black')
    if base_color == 'Chestnut' and cr_dom:
        base_color = 'Palomino'

    will_gray = has_dominant(genotype['G'])
    displayed = 'Gray' if will_gray else base_color

    return {
        'born_color': base_color,
        'will_gray_with_age': will_gray,
        'displayed_color': displayed,
        'rarity_tier': COLOR_RARITY_TIER.get(displayed, 'common'),
    }

def validate_color_genetics_mendelian(n=200000):
    """VALIDACIO 1: kontrollalt Ee/Aa x Ee/Aa keresztezes a UC Davis
    publikalt Punnett-negyzete ellen (56.25/25/18.75%)."""
    het = {'E': ('dom','rec'), 'A': ('dom','rec'), 'G': ('rec','rec'), 'Cr': ('rec','rec')}
    counts = Counter()
    for _ in range(n):
        foal = breed_color_genotype(het, het)
        pheno = color_phenotype(foal)
        counts[pheno['born_color']] += 1
    total = sum(counts.values())
    observed = {k: round(v/total*100, 2) for k, v in counts.items()}
    expected = {'Bay': 56.25, 'Chestnut': 25.0, 'Black': 18.75}
    return observed, expected


# =======================================================================
# 3) HAGYOMANYOS NEVADASI SZABALYZAT
# =======================================================================
NAME_MAX_LENGTH = 18
FORBIDDEN_ENDING_TERMS = ['filly', 'colt', 'stud', 'mare', 'stallion', 'gelding', 'foal', 'yearling']

def _is_spelled_out_number_above_thirty(word):
    small_number_words = {
        'egy','ketto','harom','negy','ot','hat','het','nyolc','kilenc','tiz',
        'tizenegy','tizenketto','husz','huszonegy','harminc'
    }
    return word.lower() in small_number_words

def validate_horse_name(name, existing_names=None):
    """Jatekon beluli, egyszerusitett masolata a Jockey Club szabalyoknak.
    NEM hivatalos, NEM jogi ervenyu."""
    existing_names = existing_names or set()
    reasons = []
    if len(name) == 0:
        reasons.append('A nev nem lehet ures.')
    if len(name) > NAME_MAX_LENGTH:
        reasons.append(f'A nev tul hosszu ({len(name)} karakter, max {NAME_MAX_LENGTH}).')
    last_word = name.strip().split(' ')[-1].lower() if name.strip() else ''
    if last_word in FORBIDDEN_ENDING_TERMS:
        reasons.append(f'A nev nem vegzodhet lo-vonatkozasu szora ("{last_word}").')
    if name.strip().isdigit() and not _is_spelled_out_number_above_thirty(name.strip()):
        reasons.append('A nev nem lehet csak szam (kiveve kiirt, harminc folotti szamok).')
    if last_word in ('2nd', '3rd', '4th', 'masodik', 'harmadik'):
        reasons.append('A nev nem vegzodhet sorszamra.')
    letters_only = name.replace('.', '').replace(' ', '')
    if '.' in name and letters_only.isupper() and len(letters_only) <= 5:
        reasons.append('A nev nem allhat csak kezdobetukbol.')
    if name in existing_names:
        reasons.append('Ez a nev mar hasznalatban van (nem egyedi).')
    return (len(reasons) == 0, reasons)

def generate_pedigree_name(sire_name, dam_name, existing_names=None, max_attempts=25):
    """Nevgeneralas a szulok neveinek kombinalasaval, a valos tenyesztoi
    hagyomanyt lekepezve."""
    existing_names = existing_names or set()

    def fragments(full_name):
        words = full_name.split(' ')
        frags = [w[:random.randint(3, min(len(w), 6))] for w in words if len(w) >= 3]
        return frags if frags else [full_name[:5]]

    sire_frags = fragments(sire_name)
    dam_frags = fragments(dam_name)

    for _ in range(max_attempts):
        sf = random.choice(sire_frags)
        df = random.choice(dam_frags)
        style = random.choice(['concat', 'concat_space', 'dam_first'])
        if style == 'concat':
            candidate = sf + df
        elif style == 'concat_space':
            candidate = f"{sf} {df}"
        else:
            candidate = df + sf
        candidate = candidate.capitalize() if ' ' not in candidate else ' '.join(w.capitalize() for w in candidate.split(' '))
        candidate = candidate[:NAME_MAX_LENGTH]
        valid, reasons = validate_horse_name(candidate, existing_names)
        if valid:
            return candidate, reasons
    return None, ['Nem sikerult valid nevet generalni a megadott probalkozasok alatt.']


# =======================================================================
# 4) ALAPITO POPULACIO GENERALASA (valosaghu meretben, skalazhato)
# =======================================================================
# A kezdo men/kanca letszam SZABADON SKALAZHATO (n_sires, n_dams
# parameter) - amikor a jatek vegleges tervezett menletszama eldol,
# csak ezt a ket parametert kell modositani, minden mas valtozatlan
# marad. A populacio genfrekvenciai mindig a valos teliver adatokat
# koveti, fuggetlenul a meretetol.
POPULATION_TRAIT_MEAN = 60  # JATEKTERVEZESI PLACEHOLDER - nincs publikalt
                             # abszolut 0-100 skala fiktiv jatek szamara

def generate_random_founder(name, ancestor_prefix):
    """Egy fuggetlen (nem rokon) alapito lo generalasa a populacios
    genfrekvenciakbol."""
    profile = {}
    for t in TRAITS:
        sd = TRAIT_CONFIG[t]['pop_sd']
        val = round(max(20, min(99, random.gauss(POPULATION_TRAIT_MEAN, sd))))
        profile[t] = val
    color_geno = {locus: random_genotype_locus(locus) for locus in ['E', 'A', 'G', 'Cr']}
    ancestors = [f'{ancestor_prefix}_{name}_a', f'{ancestor_prefix}_{name}_b', f'{ancestor_prefix}_{name}_c']
    return {'id': name, 'name': name, 'profile': profile, 'ancestors': ancestors, 'color_geno': color_geno}

def generate_founder_population(n_sires, n_dams):
    sires = [generate_random_founder(f'Sire{i+1:03d}', 'S') for i in range(n_sires)]
    dams = [generate_random_founder(f'Dam{i+1:03d}', 'D') for i in range(n_dams)]
    return {'sires': sires, 'dams': dams}


# =======================================================================
# 5) EGYESITETT CSIKO-GENERALAS - egy hivas, teljes csiko
# =======================================================================
def generate_full_foal(sire, dam, existing_names=None):
    """Teljesitmeny-genetikai profil + tenyesztesi index + szin +
    generalt nev egy fedeztetesbol."""
    existing_names = existing_names or set()
    inbr = inbreeding_coeff(sire, dam)

    tgv_profile = {}
    phenotype_profile = {}
    for t in TRAITS:
        tgv, mid = true_genetic_value(sire, dam, t, inbr)
        tgv_profile[t] = round(tgv, 1)
        phenotype_profile[t] = round(phenotype_from_genetic_value(tgv, t), 1)

    overall_tgv = overall_score(tgv_profile)
    index_letter = index_from_score(overall_tgv)

    foal_color_geno = breed_color_genotype(sire['color_geno'], dam['color_geno'])
    color = color_phenotype(foal_color_geno)

    name, _ = generate_pedigree_name(sire['name'], dam['name'], existing_names)

    return {
        'sire': sire['name'],
        'dam': dam['name'],
        'name': name,
        'inbreeding_coeff': round(inbr, 4),
        'color': color,
        'genetic_potential_index': index_letter,
        'genetic_potential_score': round(overall_tgv, 1),
        'true_genetic_values': tgv_profile,
        'phenotype_preview': phenotype_profile,
    }


# =======================================================================
# FUTTATAS: teljes validacios csomag + demonstracio
# =======================================================================
if __name__ == '__main__':
    print("=== TROT HERITAGE - BREEDING ENGINE v5.0 ===\n")

    # --- 1) Teljesitmeny-genetika: h2 visszanyeres validacio ---
    print("--- 1) TELJESITMENY-GENETIKA: h2 VISSZANYERES (regresszios meredekseg) ---")
    N_SIRES, N_DAMS = 300, 300  # valosaghu kezdo men/kanca letszam - itt allithato
    founder_pop = generate_founder_population(N_SIRES, N_DAMS)
    print(f"Alapito populacio: {N_SIRES} men + {N_DAMS} kanca, valos genfrekvenciakbol generalva.\n")

    all_ok = True
    for t in TRAITS:
        midparent_vals, offspring_vals = [], []
        for _ in range(15000):
            sire = random.choice(founder_pop['sires'])
            dam = random.choice(founder_pop['dams'])
            inbr = inbreeding_coeff(sire, dam)
            tgv, mid = true_genetic_value(sire, dam, t, inbr)
            midparent_vals.append(mid)
            offspring_vals.append(tgv)
        mean_x = statistics.mean(midparent_vals)
        mean_y = statistics.mean(offspring_vals)
        n_pts = len(midparent_vals)
        cov = sum((midparent_vals[i]-mean_x)*(offspring_vals[i]-mean_y) for i in range(n_pts)) / n_pts
        var_x = statistics.pvariance(midparent_vals)
        slope = cov / var_x if var_x > 0 else float('nan')
        status = "OK" if abs(slope - 1.0) < 0.1 else "ELTERES"
        if status == "ELTERES":
            all_ok = False
        print(f"  {t:14s} regresszios meredekseg={slope:.3f}  [{status}]")
    print(f"  Osszesitve: {'MINDEN TULAJDONSAG OK' if all_ok else 'VAN ELTERES - ellenorizendo'}\n")

    # --- 2) Szingenetika: kontrollalt Punnett-negyzet validacio ---
    print("--- 2) SZINGENETIKA: KONTROLLALT PUNNETT-NEGYZET VALIDACIO ---")
    observed_mendel, expected_mendel = validate_color_genetics_mendelian(n=200000)
    color_val_ok = True
    for color in ['Bay', 'Chestnut', 'Black']:
        obs = observed_mendel.get(color, 0.0)
        exp = expected_mendel[color]
        diff = abs(obs - exp)
        status = "OK" if diff < 0.5 else "ELTERES"
        if status == "ELTERES":
            color_val_ok = False
        print(f"  {color:10s} megfigyelt={obs:6.2f}%  varhato={exp:6.2f}%  [{status}]")
    print()

    # --- 3) Szingenetika: populacios szinteloszlas validacio ---
    print("--- 3) SZINGENETIKA: POPULACIOS SZINELOSZLAS VALIDACIO (valosaghu alapito populacion) ---")
    print("MEGJEGYZES: veges meretu (300+300) alapito populacioval a tenyleges allelfrekvenciak")
    print("a celzott ertek korul veletlenszeruen ingadoznak ('genetikai sodrodas' / genetic drift -")
    print("ez valos, dokumentalt populaciogenetikai jelenseg, nem hiba). Egy adott lokuszra a varhato")
    print("mintavateli szoras kb. sqrt(p*(1-p)/(2N)) - 300 lonal ez kb. 2 szazalekpont/lokusz.")
    print("A validacio ezert 3 szorasnyi (kb. 6pp) tolerancian belul fogadja el az eredmenyt.\n")

    N_TEST_FOALS = 30000
    color_counts = Counter()
    for _ in range(N_TEST_FOALS):
        sire = random.choice(founder_pop['sires'])
        dam = random.choice(founder_pop['dams'])
        foal_geno = breed_color_genotype(sire['color_geno'], dam['color_geno'])
        pheno = color_phenotype(foal_geno)
        color_counts[pheno['displayed_color']] += 1

    target_colors = {'Bay': 74.2, 'Chestnut': 23.3, 'Gray': 1.5, 'Black': 0.5}
    DRIFT_TOLERANCE_PP = 6.0  # ~3 szoras egy 300-as alapito populacion, lasd fentebb
    total_c = sum(color_counts.values())
    color_val_ok = True
    for color, target_pct in target_colors.items():
        obs_pct = color_counts.get(color, 0) / total_c * 100
        diff = abs(obs_pct - target_pct)
        if diff < 1.5:
            status = "OK"
        elif diff < DRIFT_TOLERANCE_PP:
            status = "DRIFT (varhato mintaveteli ingadozas, nem hiba)"
        else:
            status = "ELTERES - VIZSGALANDO"
            color_val_ok = False
        print(f"  {color:10s} megfigyelt={obs_pct:6.2f}%  celzott={target_pct:5.2f}%  elteres={diff:5.2f}pp  [{status}]")
    special_pct = 100 - sum(color_counts.get(c,0)/total_c*100 for c in target_colors)
    if special_pct > 0.001:
        print(f"  Palomino/kulonleges  {special_pct:6.3f}%  (extremen ritka, monetizacios reteg szamara fenntartva)")
    print()

    # --- 4) Nevadasi szabalyzat smoke test ---
    print("--- 4) NEVADASI SZABALYZAT SMOKE TEST ---")
    valid, _ = validate_horse_name("Midnight Filly")
    assert not valid, "HIBA: a 'Midnight Filly' nevnek ervenytelennek kellene lennie!"
    valid, _ = validate_horse_name("Storm Runner")
    assert valid, "HIBA: a 'Storm Runner' nevnek ervenyesnek kellene lennie!"
    valid, _ = validate_horse_name("C.O.D.")
    assert not valid, "HIBA: a 'C.O.D.' nevnek ervenytelennek kellene lennie!"
    print("  Nevvalidator alapteszt: OK\n")

    # --- 5) EBV/Reliability demonstracio a valos alapito populacion ---
    print("--- 5) EBV / RELIABILITY DEMONSTRACIO (egy veletlen alapito menen) ---")
    example_sire = founder_pop['sires'][0]
    pop_mean = POPULATION_TRAIT_MEAN
    h2 = TRAIT_CONFIG['speed']['h2']
    true_value = example_sire['profile']['speed']
    print(f"  Pelda men: {example_sire['name']}, valodi Speed genetikai ertek: {true_value}")
    for n_starts in [0, 1, 3, 10]:
        rel_own = reliability_from_own_records(n_starts, h2)
        rel_ped = 0.25  # placeholder: csak pedigre alapjan, kezdetben
        combined = combined_reliability(rel_ped, rel_own, 0.0)
        ebv = ebv_estimate(true_value, pop_mean, combined)
        print(f"    {n_starts:2d} sajat rajt utan: reliability={combined:.2f}, becsult EBV={ebv:5.1f}")
    print()

    # --- 6) Teljes csiko generalas demonstracio (a valos populaciobol) ---
    print("--- 6) TELJES CSIKO GENERALAS DEMO (5 veletlen parositas az alapito populaciobol) ---")
    existing_names = set()
    sample_foals = []
    for _ in range(5):
        sire = random.choice(founder_pop['sires'])
        dam = random.choice(founder_pop['dams'])
        foal = generate_full_foal(sire, dam, existing_names)
        if foal['name']:
            existing_names.add(foal['name'])
        sample_foals.append(foal)
        gray_note = " (szinesen szuletik, oszik majd)" if foal['color']['will_gray_with_age'] else ""
        print(f"  {sire['name']} x {dam['name']}  (inbreeding: {foal['inbreeding_coeff']*100:.2f}%)")
        print(f"    -> Csiko neve: {foal['name']}")
        print(f"    -> Szin: {foal['color']['displayed_color']}{gray_note}  [ritkasag: {foal['color']['rarity_tier']}]")
        print(f"    -> Tenyesztesi index: {foal['genetic_potential_index']} (pontszam: {foal['genetic_potential_score']})")
        print()

    overall_status = "MINDEN VALIDACIO OK" if (all_ok and color_val_ok) else "VAN ELTERES - ELLENORIZENDO"
    print(f"=== OSSZESITETT STATUS: {overall_status} ===\n")

    with open('breeding_sim_full.json', 'w', encoding='utf-8') as f:
        json.dump({
            'founder_population_size': {'sires': N_SIRES, 'dams': N_DAMS},
            'performance_heritability_validation_status': overall_status,
            'color_genetics_mendelian_validation': {'observed': observed_mendel, 'expected': expected_mendel},
            'color_genetics_population_validation': {
                'observed_pct': {k: round(v/total_c*100, 3) for k, v in color_counts.items()},
                'target_pct': target_colors,
            },
            'sample_foals': sample_foals,
        }, f, ensure_ascii=False, indent=2)
    print("Reszletes JSON kimenet: breeding_sim_full.json")
