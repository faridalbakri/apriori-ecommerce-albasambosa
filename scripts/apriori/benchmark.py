#!/usr/bin/env python3

import json
import sys
from pathlib import Path

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'storage' / 'app' / 'apriori'
BASKETS_PATH = DATA_DIR / 'baskets.json'
PHP_RULES_PATH = DATA_DIR / 'php_rules.json'

MIN_SUPPORT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.02
MIN_CONFIDENCE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6


def load_json(path: Path):
    if not path.exists():
        print(f"ERROR: {path} not found. Run 'php artisan apriori:export-data' first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def rule_key(rule: dict) -> str:
    """Create a unique key for a rule: sorted antecedent -> sorted consequent."""
    ant = ','.join(sorted(str(x) for x in rule['antecedent']))
    cons = ','.join(sorted(str(x) for x in rule['consequent']))
    return f"{ant}->{cons}"


def main():
    print("=== Apriori PHP vs Python Benchmark ===\n")

    # Load baskets
    baskets = load_json(BASKETS_PATH)
    print(f"Loaded {len(baskets)} baskets.")

    # Python Apriori
    te = TransactionEncoder()
    te_ary = te.fit_transform(baskets)
    df_encoded = pd.DataFrame(te_ary, columns=te.columns_)

    frequent = apriori(df_encoded, min_support=MIN_SUPPORT, use_colnames=True)

    if frequent.empty:
        python_rules = []
    else:
        rules_df = association_rules(frequent, metric='confidence', min_threshold=MIN_CONFIDENCE)
        # Match PHP behavior: only keep rules with lift > 1 (positive correlation)
        rules_df = rules_df[rules_df['lift'] > 1.0]
        python_rules = []
        for _, row in rules_df.iterrows():
            python_rules.append({
                'antecedent': sorted(list(row['antecedents'])),
                'consequent': sorted(list(row['consequents'])),
            })

    print(f"Python found {len(python_rules)} rules.")

    # Load PHP rules
    php_rules = load_json(PHP_RULES_PATH)
    print(f"PHP found {len(php_rules)} rules.")

    if not python_rules and not php_rules:
        print("\nBoth implementations found zero rules. Test inconclusive.")
        return

    # Compare
    python_keys = set(rule_key(r) for r in python_rules)
    php_keys = set(rule_key(r) for r in php_rules)

    common = python_keys & php_keys
    only_python = python_keys - php_keys
    only_php = php_keys - python_keys

    precision = len(common) / len(php_keys) if php_keys else 0
    recall = len(common) / len(python_keys) if python_keys else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n--- Results ---")
    print(f"Common rules:         {len(common)}")
    print(f"Python-only rules:    {len(only_python)}")
    print(f"PHP-only rules:       {len(only_php)}")
    print(f"\nPrecision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    print(f"F1 Score:  {f1:.2%}")

    if only_php:
        print(f"\nWARNING: PHP-only rules (possible implementation differences):")
        for key in sorted(only_php)[:10]:
            print(f"  {key}")

    if only_python:
        print(f"\nWARNING: Python-only rules (possible misses in PHP):")
        for key in sorted(only_python)[:10]:
            print(f"  {key}")

    print(f"\nBenchmark complete. Target: F1 >= 0.95")


if __name__ == '__main__':
    main()
