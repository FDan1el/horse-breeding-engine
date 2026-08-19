"""
Breeding Engine v1.0 - tomeges szimulacio (spec 23-24. pont)
100 000 fiktiv csikó generálása, statisztikai ellenorzes.

Ez ugyanazt a leegyszerusitett öröklesi/varianca modellt hasznalja,
mint a boengeszos teszt (index.html), Pythonban, hogy nagy tetelben
ellenorizhető legyen a viselkedese (nem torzit-e, a szorasok
ertelmesek-e, az inbreeding hatasa kimutathato-e).

MINDEN parameter (variancia, anyai suly, inbreeding-koefficiens
kepzese) JATEKTERVEZESI PLACEHOLDER a spec 25. pontja szerint,
nem vegleges tudomanyos kalibracio.
"""

import random
import statistics
import json

random.seed(42)  # reprodukalhatosag miatt

TRAITS = ['speed','accel','stamina','sprint','mile','middle','staying',
          'soundness','trainability','temperament']

HORSES = {
    'sires': [
        {'id':'s1','name':'Northwind Cavalier',
         'profile':{'speed':88,'accel':82,'stamina':70,'sprint':90,'mile':85,'middle':60,'staying':35,'soundness':80,'trainability':75,'temperament':70},
         'ancestors':['s1a','s1b','s1c']},
        {'id':'s2','name':'Ironbark Legacy',
         'profile':{'speed':74,'accel':71,'stamina':88,'sprint':55,'mile':78,'middle':85,'staying':82,'soundness':88,'trainability':82,'temperament':78},
         'ancestors':['s2a','s2b','s1a']},
        {'id':'s3','name':'Duskfire Rebel',
         'profile':{'speed':80,'accel':85,'stamina':60,'sprint':88,'mile':72,'middle':50,'staying':30,'soundness':65,'trainability':60,'temperament':55},
         'ancestors':['s3a','s3b','s3c']},
    ],
    'dams': [
        {'id':'d1','name':'Velvet Solstice',
         'profile':{'speed':79,'accel':76,'stamina':83,'sprint':65,'mile':82,'middle':80,'staying':70,'soundness':85,'trainability':88,'temperament':84},
         'ancestors':['d1a','d1b','s1a']},
        {'id':'d2','name':'Amber Thistledown',
         'profile':{'speed':83,'accel':80,'stamina':65,'sprint':85,'mile':79,'middle':55,'staying':40,'soundness':72,'trainability':70,'temperament':66},
         'ancestors':['d2a','d2b','d2c']},
        {'id':'d3','name':'Quiet Meridian',
         'profile':{'speed':68,'accel':65,'stamina':90,'sprint':40,'mile':65,'middle':85,'staying':92,'soundness':90,'trainability':79,'temperament':88},
         'ancestors':['d3a','d3b','s3a']},
    ]
}

MATERNAL_W = 0.53
PATERNAL_W = 0.47
BASE_SD = 6.5
INBREEDING_SD_BONUS_SOUNDNESS = 18  # placeholder

def inbreeding_coeff(sire, dam):
    shared = set(sire['ancestors']) & set(dam['ancestors'])
    return min(len(shared) * 0.0625, 0.25)

def breed_one(sire, dam):
    inbr = inbreeding_coeff(sire, dam)
    foal = {}
    for t in TRAITS:
        mid = sire['profile'][t]*PATERNAL_W + dam['profile'][t]*MATERNAL_W
        sd = BASE_SD + (INBREEDING_SD_BONUS_SOUNDNESS*inbr if t == 'soundness' else 0)
        val = round(random.gauss(mid, sd))
        val = max(20, min(99, val))
        foal[t] = val
    return foal, inbr, {t: sire['profile'][t]*PATERNAL_W + dam['profile'][t]*MATERNAL_W for t in TRAITS}

WEIGHTS = {'speed':1,'accel':0.8,'stamina':1,'sprint':0.6,'mile':0.6,'middle':0.6,
           'staying':0.6,'soundness':1.1,'trainability':0.7,'temperament':0.6}

def overall_score(profile):
    s = sum(profile[t]*WEIGHTS[t] for t in TRAITS)
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

def run_simulation(n_per_pair=100000):
    results = []
    pair_summaries = []

    for sire in HORSES['sires']:
        for dam in HORSES['dams']:
            inbr = inbreeding_coeff(sire, dam)
            trait_samples = {t: [] for t in TRAITS}
            scores = []
            soundness_samples = []
            for _ in range(n_per_pair):
                foal, _, mids = breed_one(sire, dam)
                for t in TRAITS:
                    trait_samples[t].append(foal[t])
                scores.append(overall_score(foal))

            bucket_counts = {'Klasszis':0,'Nagyon jó':0,'Jó':0,'Átlagos':0,'Gyenge':0}
            for s in scores:
                if s >= 85: bucket_counts['Klasszis'] += 1
                elif s >= 75: bucket_counts['Nagyon jó'] += 1
                elif s >= 63: bucket_counts['Jó'] += 1
                elif s >= 50: bucket_counts['Átlagos'] += 1
                else: bucket_counts['Gyenge'] += 1

            trait_stats = {}
            for t in TRAITS:
                samp = trait_samples[t]
                mid_expected = sire['profile'][t]*PATERNAL_W + dam['profile'][t]*MATERNAL_W
                trait_stats[t] = {
                    'expected_mid': round(mid_expected, 2),
                    'sim_mean': round(statistics.mean(samp), 2),
                    'sim_sd': round(statistics.stdev(samp), 2),
                    'min': min(samp),
                    'max': max(samp),
                }

            pair_summary = {
                'sire': sire['name'],
                'dam': dam['name'],
                'inbreeding_coeff': round(inbr, 4),
                'n': n_per_pair,
                'mean_overall_score': round(statistics.mean(scores), 2),
                'sd_overall_score': round(statistics.stdev(scores), 2),
                'bucket_pct': {k: round(v/n_per_pair*100, 1) for k, v in bucket_counts.items()},
                'trait_stats': trait_stats,
                'soundness_sd_check': trait_stats['soundness']['sim_sd'],
            }
            pair_summaries.append(pair_summary)

    return pair_summaries


if __name__ == '__main__':
    N = 100000 // 9  # 9 par, kb. 11111 fedeztetes/par -> osszesen kb 100 000
    summaries = run_simulation(n_per_pair=N)

    total_n = sum(p['n'] for p in summaries)
    print(f"=== BREEDING ENGINE v1.0 - TOMEGES SZIMULACIO ===")
    print(f"Osszes szimulalt fedeztetes: {total_n}")
    print(f"Parok szama: {len(summaries)} (3 mén x 3 kanca)")
    print()

    for p in summaries:
        print(f"--- {p['sire']} x {p['dam']} ---")
        print(f"  Inbreeding koefficiens: {p['inbreeding_coeff']*100:.2f}%")
        print(f"  Atlagos osszesitett score: {p['mean_overall_score']} (szoras: {p['sd_overall_score']})")
        print(f"  Eloszlas: ", end="")
        print(", ".join(f"{k}={v}%" for k, v in p['bucket_pct'].items()))
        print(f"  Soundness szoras (inbreeding-erzekeny): {p['soundness_sd_check']}")
        # legnagyobb elteres varttol/tenylegestol - torzitas-ellenorzes
        max_dev = max(abs(ts['sim_mean']-ts['expected_mid']) for ts in p['trait_stats'].values())
        print(f"  Max eltérés (torzítás-ellenőrzés, várt vs. szimulált átlag): {max_dev:.2f}")
        print()

    # osszesitett torzitas-check az egesz szimulaciora
    all_devs = []
    for p in summaries:
        for t, ts in p['trait_stats'].items():
            all_devs.append(abs(ts['sim_mean'] - ts['expected_mid']))
    print(f"=== TORZITAS-ELLENORZES (osszes tulajdonsag, osszes par) ===")
    print(f"Atlagos eltérés várt vs. szimulált középérték között: {statistics.mean(all_devs):.3f}")
    print(f"Maximum eltérés: {max(all_devs):.3f}")
    print("(0-hoz kozeli ertek = a modell nem torzit, a varianca-generalas korrekt)")
    print()

    with open('breeding_sim_full.json', 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print("Reszletes JSON kimenet: breeding_sim_full.json")
