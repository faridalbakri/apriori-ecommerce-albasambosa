#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

# --- Config ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXCEL_PATH = PROJECT_ROOT / 'docs' / 'data' / 'histori-transaksi.xlsx'
OUTPUT_DIR = PROJECT_ROOT / 'storage' / 'app' / 'apriori'
RULES_PATH = OUTPUT_DIR / 'rules.json'
MAPPING_PATH = OUTPUT_DIR / 'product_mapping.csv'
UNMATCHED_PATH = OUTPUT_DIR / 'unmatched_products.md'
MIN_SUPPORT = 0.02
MIN_CONFIDENCE = 0.6
FUZZY_THRESHOLD = 70

# --- Known product names from database ---
KNOWN_PRODUCTS = [
    # Frozen Food
    "Sambosa Original Frozen",
    "Sambosa Smoked Beef Frozen",
    "Risol Rougut Frozen",
    "Pastel Ayam Frozen",
    "Roti Maryam Frozen",
    "Kroket Frozen",
    # Makanan Matang
    "Sambosa Original",
    "Sambosa Smoked Beef",
    "Risol Rougut",
    "Pastel Ayam",
    "Kroket",
    "Roti Maryam",
    # Minuman
    "Teh Botol",
    "Susu Kurma",
    "Air Mineral",
]


def normalize_price(val) -> int | None:
    """Convert Rp 3.000 / 4000 / '4.000' to integer."""
    if pd.isna(val) or val == '' or val == '-':
        return None
    s = str(val).strip()
    s = s.replace('Rp', '').replace('rp', '').replace('.', '').replace(',', '').strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def normalize_date(val) -> str | None:
    """Convert various date formats to YYYY-MM-DD."""
    if pd.isna(val) or val == '' or val == '-':
        return None
    s = str(val).strip()

    formats = [
        '%Y-%m-%d',      # 2025-12-06
        '%d/%m/%Y',      # 28/11/2025
        '%m/%d/%Y',      # 11/16/2025
        '%d %b %Y',      # 08 Dec 2025
        '%d-%m-%Y',      # 20-12-2025
        '%d %B %Y',      # 08 December 2025
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(s, format=fmt).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            continue

    # Last resort: let pandas try auto-detection
    try:
        return pd.to_datetime(s).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return s


def normalize_menu(name) -> str:
    """Normalize product name: lowercase, trim, collapse whitespace."""
    if pd.isna(name) or str(name).strip() == '':
        return ''
    s = str(name).strip().lower()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    return s


def fuzzy_match(menu_name: str, db_names: list[str], original_names: list[str]) -> tuple[str | None, int]:
    """Fuzzy match a menu name to the closest known product. Returns (match, score)."""
    if not menu_name:
        return None, 0

    # Try exact match first (case-insensitive)
    for i, db_name in enumerate(db_names):
        if menu_name == db_name or menu_name in db_name or db_name in menu_name:
            return original_names[i], 100

    # Fuzzy match against lowered names, return original case
    match, score, _ = process.extractOne(menu_name, db_names, scorer=fuzz.token_sort_ratio)
    if match is not None:
        idx = db_names.index(match)
        return original_names[idx], score
    return match, score


def main():
    print(f"Reading {EXCEL_PATH}...")
    df = pd.read_excel(EXCEL_PATH, sheet_name='Transaksi')
    print(f"  Loaded {len(df)} rows, {df['ID_Transaksi'].nunique()} unique transactions")

    # --- Clean: remove TEST rows ---
    mask_test = (df['ID_Transaksi'].str.upper().str.strip() == 'TEST') | pd.isna(df['ID_Transaksi'])
    df = df[~mask_test].copy()
    print(f"  After removing TEST rows: {len(df)} rows")

    # --- Filter: Nov 2025 – April 2026 ---
    df['Tanggal_pd'] = pd.to_datetime(df['Tanggal'], format='mixed', dayfirst=True)
    date_mask = (
        (df['Tanggal_pd'] >= pd.Timestamp('2025-11-01')) &
        (df['Tanggal_pd'] <= pd.Timestamp('2026-04-30'))
    )
    df = df[date_mask].copy()
    print(f"  After date filter (Nov 2025–Apr 2026): {len(df)} rows, {df['ID_Transaksi'].nunique()} transactions")
    df = df.drop(columns=['Tanggal_pd'])

    # --- Normalize ---
    df['Harga_Int'] = df['Harga_Satuan'].apply(normalize_price)
    df['Nama_Normalized'] = df['Nama_Menu'].apply(normalize_menu)

    # --- Load admin mapping CSV if it exists ---
    admin_mapping = {}
    if MAPPING_PATH.exists():
        with open(MAPPING_PATH, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                original = row.get('original_name', '').strip().lower()
                mapped = row.get('mapped_product', '').strip()
                if original and mapped and mapped != '-':
                    admin_mapping[original] = mapped
        if admin_mapping:
            print(f"  Loaded {len(admin_mapping)} manual mappings from {MAPPING_PATH}")

    # Apply admin mapping first, then fuzzy match for the rest
    def match_product(normalized_name):
        # Check admin mapping first (exact match on normalized name)
        if normalized_name in admin_mapping:
            return admin_mapping[normalized_name], 100

        # Fall back to fuzzy match
        return fuzzy_match(normalized_name, known_lower, KNOWN_PRODUCTS)

    # --- Fuzzy match to known products ---
    known_lower = [n.lower() for n in KNOWN_PRODUCTS]
    match_results = df['Nama_Normalized'].apply(match_product)
    df['Matched_Product'] = match_results.apply(lambda x: x[0])
    df['Match_Score'] = match_results.apply(lambda x: x[1])

    # Identify unmatched products and generate mapping CSV
    unmatched = df[df['Match_Score'] < FUZZY_THRESHOLD][
        ['Nama_Menu', 'Nama_Normalized', 'Matched_Product', 'Match_Score']
    ].drop_duplicates()

    if not unmatched.empty:
        # Write CSV mapping template for admin
        csv_rows = []
        for _, row in unmatched.iterrows():
            csv_rows.append({
                'original_name': row['Nama_Normalized'],
                'best_match': row['Matched_Product'] or '-',
                'match_score': f"{row['Match_Score']:.1f}%",
                'mapped_product': '',  # Admin fills this
            })

        with open(MAPPING_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['original_name', 'best_match', 'match_score', 'mapped_product'])
            writer.writeheader()
            writer.writerows(csv_rows)

        # Write markdown reference
        with open(UNMATCHED_PATH, 'w', encoding='utf-8') as f:
            f.write("# Produk yang Tidak Match (perlu mapping manual)\n\n")
            f.write(f"Threshold: {FUZZY_THRESHOLD}%\n")
            f.write(f"File mapping: {MAPPING_PATH}\n\n")
            f.write("## Cara mapping:\n")
            f.write("1. Buka `product_mapping.csv` di Excel\n")
            f.write("2. Isi kolom `mapped_product` dengan nama produk yang benar dari database\n")
            f.write("3. Save CSV\n")
            f.write("4. Jalankan ulang: `python scripts/apriori/clean_and_mine.py`\n\n")
            f.write("## Daftar Produk di Database:\n")
            for p in KNOWN_PRODUCTS:
                f.write(f"- {p}\n")
            f.write("\n## Produk Unmatch:\n")
            f.write("| # | Nama Asli | Nama Normalized | Best Match | Score |\n")
            f.write("|---|-----------|-----------------|------------|-------|\n")
            for i, row in enumerate(unmatched.itertuples(), 1):
                f.write(f"| {i} | {row.Nama_Menu} | {row.Nama_Normalized} | {row.Matched_Product or '-'} | {row.Match_Score}% |\n")

        print(f"\n  WARNING: {len(unmatched)} produk tidak match.")
        print(f"  Mapping CSV: {MAPPING_PATH}")
        print(f"  Referensi:   {UNMATCHED_PATH}")
        print(f"  Isi kolom mapped_product lalu jalankan ulang script ini.")

        # Exclude unmatched from further processing
        df = df[df['Match_Score'] >= FUZZY_THRESHOLD]
    else:
        print("  OK: Semua produk ter-match!")

    # --- Filter out products not in KNOWN_PRODUCTS ---
    known_set = set(KNOWN_PRODUCTS)
    before = len(df)
    df = df[df['Matched_Product'].isin(known_set)].copy()
    removed = before - len(df)
    if removed > 0:
        removed_products = set()
        removed_df = df[~df['Matched_Product'].isin(known_set)] if before != len(df) else None
        print(f"  Filtered out {removed} rows (products not in known list)")

    # --- Build baskets ---
    # Group by transaction ID, collect matched product names
    baskets = df.groupby('ID_Transaksi')['Matched_Product'].apply(list).tolist()
    print(f"\n  Baskets: {len(baskets)} transactions ready for mining")

    # --- Apriori ---
    if len(baskets) < 50:
        print(f"  WARNING: Only {len(baskets)} transactions (min 50 required). Skipping Apriori.")
        return

    te = TransactionEncoder()
    te_ary = te.fit_transform(baskets)
    df_encoded = pd.DataFrame(te_ary, columns=te.columns_)

    print("  Running Apriori...")
    frequent = apriori(df_encoded, min_support=MIN_SUPPORT, use_colnames=True)

    if frequent.empty:
        print("  No frequent itemsets found.")
        rules = []
    else:
        rules_df = association_rules(frequent, metric='confidence', min_threshold=MIN_CONFIDENCE)
        print(f"  Found {len(rules_df)} rules")

        # Convert to JSON structure
        rules = []
        for _, row in rules_df.iterrows():
            rules.append({
                'antecedent': list(row['antecedents']),
                'consequent': list(row['consequents']),
                'support': round(float(row['support']), 6),
                'confidence': round(float(row['confidence']), 6),
                'lift': round(float(row['lift']), 6),
            })

    # --- Export ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(RULES_PATH, 'w') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"\nDONE: {len(rules)} rules exported to {RULES_PATH}")


if __name__ == '__main__':
    main()
