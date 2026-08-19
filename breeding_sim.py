"""
Breeding Engine v4.0 - EGYESITETT MOTOR
=======================================================================
Osszevonja a kulon fejlesztett modulokat egyetlen, egysegben futtathato
tenyesztesi motorba:

  1) TELJESITMENY-GENETIKA (korabban: breeding_sim_v2.py)
     - Tulajdonsagonkenti h2 (orokolhetoseg) valos tudomanyos forrasokbol
     - True Genetic Value vs Fenotipus szetvalasztasa
     - EBV / Reliability progeny-test formulaval
     - Mendeli szegregacios varianica, inbreeding-erzekeny szorasnovekedes

  2) SZINGENETIKA (korabban: breeding_sim_v3.py, A resz)
     - Extension/Agouti/Grey lokusz, validalva UC Davis publikalt
       Punnett-negyzet ellen

  3) HAGYOMANYOS NEVADASI SZABALYZAT (korabban: breeding_sim_v3.py, B resz)
     - Jockey Club-inspiralt validator + pedigre-alapu nevgeneralas

Az osszes forrashivatkozas es tudomanyos indoklas VALTOZATLANUL megmaradt
az egyes szekciok elejen - lasd a korabbi breeding_sim_v2.py es
breeding_sim_v3.py fajlokat a teljes forraslistaert. Itt csak a
legfontosabb forrasokat ismetlem meg roviden minden szekcio elejen.

EGY FUGGVENYHIVAS EGY TELJES CSIKOT AD KI: teljesitmeny-genetikai
profil + EBV/index + szin + generalt nev egyszerre (lasd:
generate_full_foal() a fajl vegen).
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
    'speed':        {'h2': 0.12, 'pop_sd': 12, 'h2_source': 'Sharman et al. 2023 (sprint h2=0.124)'},
    'accel':        {'h2': 0.15, 'pop_sd': 12, 'h2_source': 'BECSLES - Speed-hez hasonlo tartomany'},
    'stamina':      {'h2': 0.18, 'pop_sd': 12, 'h2_source': 'BECSLES - Staying Aptitude tartomanyahoz igazitva'},
    'sprint':       {'h2': 0.124,'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, sprint tav'},
    'mile':         {'h2': 0.122,'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, kozeptav (proxy)'},
    'middle':       {'h2': 0.122,'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, kozeptav'},
    'staying':      {'h2': 0.074,'pop_sd': 12, 'h2_source': 'Sharman et al. 2023, hosszutav'},
    'soundness':    {'h2': 0.18, 'pop_sd': 14, 'h2_source': 'Oki et al. 2008 SDFT (0.17-0.19) + Welsh et al. 2013 atlaga'},
    'trainability': {'h2': 0.25, 'pop_sd': 12, 'h2_source': 'BECSLES - Oki et al. viselkedesi h2 proxykent'},
    'temperament':  {'h2': 0.25, 'pop_sd': 12, 'h2_source': 'Oki et al. Gibbs sampling, viselkedesi h2=0.23-0.28'},
}
TRAITS = list(TRAIT_CONFIG.keys())

MATERNAL_GENETIC_W = 0.50
PATERNAL_GENETIC_W = 0.50
MATERNAL_ENV_BONUS_SD = 2.5

INBREEDING_VARIANCE_MULT = {
    'soundness': 2.2, 'trainability': 1.3, 'temperament': 1.3,
}
DEFAULT_INBREEDING_MULT = 1.05

WEIGHTS = {'speed':1,'accel':0.8,'stamina':1,'sprint':0.6,'mile':0.6,'middle':0.6,
           'staying':0.6,'soundness':1.1,'trainability':0.7,'temperament':0.6}


def inbreeding_coeff(sire, dam):
    shared = set(sire['ancestors']) & set(dam['ancestors'])
    return min(len(shared) * 0.0625, 0.25)

def genetic_sd(trait):
    cfg = TRAIT_CONFIG[trait]
    return math.sqrt(cfg['h2']) * cfg['pop_sd']

def mendelian_segregation_sd(trait, inbreeding=0.0):
    vg = genetic_sd(trait) ** 2
    seg_var = 0.5 * vg
    mult = INBREEDING_VARIANCE_MULT.get(trait, DEFAULT_INBREEDING_MULT)
    seg_var *= (1 + (mult - 1) * (inbreeding / 0.25))
    return math.sqrt(seg_var)

def true_genetic_value(sire, dam, trait, inbreeding):
    midparent = (sire['profile'][trait]*PATERNAL_GENETIC_W +
                 dam['profile'][trait]*MATERNAL_GENETIC_W)
    seg_sd = mendelian_segregation_sd(trait, inbreeding)
    tgv = random.gauss(midparent, seg_sd)
    maternal_env = random.gauss(0, MATERNAL_ENV_BONUS_SD)
    tgv += maternal_env
    return max(5, min(99, tgv)), midparent

def phenotype_from_genetic_value(tgv, trait):
    cfg = TRAIT_CONFIG[trait]
    env_sd = math.sqrt(1 - cfg['h2']) * cfg['pop_sd']
    phenotype = random.gauss(tgv, env_sd * 0.4)
    return max(5, min(99, phenotype))

def reliability_from_own_records(n_starts, h2):
    if n_starts <= 0:
        return 0.0
    return (n_starts * h2) / (1 + (n_starts - 1) * h2)

def reliability_from_progeny(n_progeny, h2):
    if n_progeny <= 0:
        return 0.0
    return n_progeny / (n_progeny + (4 - h2) / h2)

def combined_reliability(pedigree_rel, own_rel, progeny_rel):
    combined = 1 - (1 - pedigree_rel) * (1 - own_rel) * (1 - progeny_rel)
    return min(combined, 0.99)

def ebv_estimate(true_value, population_mean, reliability):
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
POP_ALLELE_FREQ = {'E': 0.65, 'A': 0.60, 'G': 0.12, 'Cr': 0.005}

def random_genotype_locus(locus_key):
    p = POP_ALLELE_FREQ[locus_key]
    a1 = 'dom' if random.random() < p else 'rec'
    a2 = 'dom' if random.random() < p else 'rec'
    return (a1, a2)

def inherit_allele(pair):
    return random.choice(pair)

def breed_color_genotype(sire_geno, dam_geno):
    return {locus: (inherit_allele(sire_geno[locus]), inherit_allele(dam_geno[locus]))
            for locus in ['E', 'A', 'G', 'Cr']}

def has_dominant(pair):
    return 'dom' in pair

def color_phenotype(genotype):
    e_dom = has_dominant(genotype['E'])
    a_dom = has_dominant(genotype['A'])
    cr_dom = has_dominant(genotype['Cr'])

    base_color = 'Chestnut' if not e_dom else ('Bay' if a_dom else 'Black')
    if base_color == 'Chestnut' and cr_dom:
        base_color = 'Palomino'

    will_gray = has_dominant(genotype['G'])
    return {
        'born_color': base_color,
        'will_gray_with_age': will_gray,
        'displayed_color': 'Gray' if will_gray else base_color,
    }

def validate_color_genetics(n=200000):
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
# 4) FIKTIV LOALLOMANY (teljesitmeny + szin genotipus egyben)
# =======================================================================
HORSES = {
    'sires': [
        {'id':'s1','name':'Northwind Cavalier',
         'profile':{'speed':88,'accel':82,'stamina':70,'sprint':90,'mile':85,'middle':60,'staying':35,'soundness':80,'trainability':75,'temperament':70},
         'ancestors':['s1a','s1b','s1c'],
         'color_geno': {'E': ('dom','rec'), 'A': ('dom','dom'), 'G': ('rec','rec'), 'Cr': ('rec','rec')}},
        {'id':'s2','name':'Ironbark Legacy',
         'profile':{'speed':74,'accel':71,'stamina':88,'sprint':55,'mile':78,'middle':85,'staying':82,'soundness':88,'trainability':82,'temperament':78},
         'ancestors':['s2a','s2b','s1a'],
         'color_geno': {'E': ('dom','dom'), 'A': ('rec','rec'), 'G': ('dom','rec'), 'Cr': ('rec','rec')}},
        {'id':'s3','name':'Duskfire Rebel',
         'profile':{'speed':80,'accel':85,'stamina':60,'sprint':88,'mile':72,'middle':50,'staying':30,'soundness':65,'trainability':60,'temperament':55},
         'ancestors':['s3a','s3b','s3c'],
         'color_geno': {'E': ('rec','rec'), 'A': ('dom','rec'), 'G': ('rec','rec'), 'Cr': ('rec','rec')}},
    ],
    'dams': [
        {'id':'d1','name':'Velvet Solstice',
         'profile':{'speed':79,'accel':76,'stamina':83,'sprint':65,'mile':82,'middle':80,'staying':70,'soundness':85,'trainability':88,'temperament':84},
         'ancestors':['d1a','d1b','s1a'],
         'color_geno': {'E': ('dom','rec'), 'A': ('dom','rec'), 'G': ('rec','rec'), 'Cr': ('rec','rec')}},
        {'id':'d2','name':'Amber Thistledown',
         'profile':{'speed':83,'accel':80,'stamina':65,'sprint':85,'mile':79,'middle':55,'staying':40,'soundness':72,'trainability':70,'temperament':66},
         'ancestors':['d2a','d2b','d2c'],
         'color_geno': {'E': ('dom','dom'), 'A': ('dom','dom'), 'G': ('rec','rec'), 'Cr': ('rec','rec')}},
        {'id':'d3','name':'Quiet Meridian',
         'profile':{'speed':68,'accel':65,'stamina':90,'sprint':40,'mile':65,'middle':85,'staying':92,'soundness':90,'trainability':79,'temperament':88},
         'ancestors':['d3a','d3b','s3a'],
         'color_geno': {'E': ('dom','rec'), 'A': ('rec','rec'), 'G': ('rec','rec'), 'Cr': ('rec','rec')}},
    ]
}


# =======================================================================
# 5) EGYESITETT CSIKO-GENERALAS - egy hivas, teljes csiko
# =======================================================================
def generate_full_foal(sire, dam, existing_names=None):
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

    name, name_info = generate_pedigree_name(sire['name'], dam['name'], existing_names)

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
# FUTTATAS: validaciok + teljes csiko-demonstracio
# =======================================================================
if __name__ == '__main__':
    print("=== BREEDING ENGINE v4.0 - EGYESITETT MOTOR ===\n")

    print("--- 1) TELJESITMENY-GENETIKA VALIDACIO (h2 visszanyeres) ---")
    all_ok = True
    for t in TRAITS:
        midparent_vals, offspring_vals = [], []
        for _ in range(15000):
            sire = random.choice(HORSES['sires'])
            dam = random.choice(HORSES['dams'])
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

    print("--- 2) SZINGENETIKA VALIDACIO (Punnett-negyzet ellenorzes) ---")
    observed, expected = validate_color_genetics(n=200000)
    for color in ['Bay', 'Chestnut', 'Black']:
        obs = observed.get(color, 0.0)
        exp = expected[color]
        diff = abs(obs - exp)
        status = "OK" if diff < 0.5 else "ELTERES"
        print(f"  {color:10s} megfigyelt={obs:6.2f}%  varhato={exp:6.2f}%  [{status}]")
    print()

    print("--- 3) NEVADASI SZABALYZAT SMOKE TEST ---")
    valid, reasons = validate_horse_name("Midnight Filly")
    assert not valid, "HIBA: a 'Midnight Filly' nevnek ervenytelennek kellene lennie!"
    valid, reasons = validate_horse_name("Storm Runner")
    assert valid, "HIBA: a 'Storm Runner' nevnek ervenyesnek kellene lennie!"
    print("  Nevvalidator alapteszt: OK\n")

    print("--- 4) TELJES CSIKO GENERALAS (teljesitmeny + szin + nev egyben) ---")
    existing_names = set()
    for sire in HORSES['sires']:
        for dam in HORSES['dams']:
            foal = generate_full_foal(sire, dam, existing_names)
            if foal['name']:
                existing_names.add(foal['name'])
            gray_note = " (szinesen szuletik, oszik majd)" if foal['color']['will_gray_with_age'] else ""
            print(f"  {sire['name']} x {dam['name']}  (inbreeding: {foal['inbreeding_coeff']*100:.2f}%)")
            print(f"    -> Csiko neve: {foal['name']}")
            print(f"    -> Szin: {foal['color']['displayed_color']}{gray_note}")
            print(f"    -> Tenyesztesi index: {foal['genetic_potential_index']} (genetikai potencial pontszam: {foal['genetic_potential_score']})")
            print()

    with open('breeding_sim_v4_full.json', 'w', encoding='utf-8') as f:
        sample_foals = []
        existing_names2 = set()
        for sire in HORSES['sires']:
            for dam in HORSES['dams']:
                foal = generate_full_foal(sire, dam, existing_names2)
                if foal['name']:
                    existing_names2.add(foal['name'])
                sample_foals.append(foal)
        json.dump({
            'performance_heritability_validation': 'lasd konzol kimenet - regresszios meredeksegek',
            'color_genetics_validation': {'observed': observed, 'expected': expected},
            'sample_foals': sample_foals,
        }, f, ensure_ascii=False, indent=2)
    print("Reszletes JSON kimenet: breeding_sim_v4_full.json")
