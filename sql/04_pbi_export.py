import duckdb, os

con = duckdb.connect('data/clean/lending.duckdb')
con.execute("SET memory_limit='4GB'; SET threads=4;")

os.makedirs('data/clean/pbi', exist_ok=True)
os.makedirs('data/clean/pbi_sample', exist_ok=True)

# Lean fact table (kam columns = Power BI fast)
con.execute("""
CREATE OR REPLACE TABLE fact_loans_pbi AS
SELECT loan_id, issue_date,
       grade_key, purpose_key, state_key, borrower_key,
       loan_status, term_months,
       loan_amnt, funded_amnt, int_rate,
       total_rec_prncp, total_rec_int, total_rec_late_fee,
       recoveries, out_prncp,
       is_default, is_closed, net_profit,
       CASE WHEN is_default = 1
            THEN funded_amnt - total_rec_prncp END AS gross_loss
FROM fact_loans
""")

# Export: full data
con.execute("COPY fact_loans_pbi TO 'data/clean/pbi/fact_loans.parquet' (FORMAT PARQUET)")
for t in ['dim_date', 'dim_grade', 'dim_purpose', 'dim_state', 'dim_borrower']:
    con.execute(f"COPY {t} TO 'data/clean/pbi/{t}.parquet' (FORMAT PARQUET)")

# Backup: har saal se max 35k loans (sirf tab use kar jab full data bhaari lage)
con.execute("""
COPY (
  SELECT * EXCLUDE (rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY year(issue_date) ORDER BY random()) AS rn
    FROM fact_loans_pbi
  ) WHERE rn <= 35000
) TO 'data/clean/pbi_sample/fact_loans_sample.parquet' (FORMAT PARQUET)
""")

# Power BI me load ke baad in numbers se match karna hai
print("Fact rows        :", con.sql("SELECT COUNT(*) FROM fact_loans_pbi").fetchone()[0])
print("Total funded     :", con.sql("SELECT ROUND(SUM(funded_amnt)) FROM fact_loans_pbi").fetchone()[0])
print("Total interest   :", con.sql("SELECT ROUND(SUM(total_rec_int)) FROM fact_loans_pbi").fetchone()[0])
print("Default rate %   :", con.sql("SELECT ROUND(100.0*SUM(is_default)/SUM(is_closed),2) FROM fact_loans_pbi").fetchone()[0])

print("\nFiles:")
for folder in ['data/clean/pbi', 'data/clean/pbi_sample']:
    for f in sorted(os.listdir(folder)):
        mb = os.path.getsize(os.path.join(folder, f)) / 1e6
        print(f"  {folder}/{f}  {mb:.1f} MB")