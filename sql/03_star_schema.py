import duckdb, os

con = duckdb.connect('data/clean/lending.duckdb')
con.execute("SET memory_limit='4GB'; SET threads=4;")

# Saaf source view (khaali values ko 'Unknown' banaya)
con.execute("""
CREATE OR REPLACE TEMP VIEW src AS
SELECT
  loan_id, issue_date, loan_amnt, funded_amnt, term_months, int_rate,
  installment, loan_status, annual_inc, dti, fico_mid,
  total_pymnt, total_rec_prncp, total_rec_int, total_rec_late_fee,
  recoveries, out_prncp, is_default, is_closed, net_profit,
  grade,
  COALESCE(sub_grade, 'Unknown')           AS sub_grade,
  COALESCE(purpose, 'unknown')             AS purpose,
  COALESCE(addr_state, 'Unknown')          AS addr_state,
  COALESCE(home_ownership, 'Unknown')      AS home_ownership,
  COALESCE(verification_status, 'Unknown') AS verification_status,
  COALESCE(emp_length, 'Unknown')          AS emp_length,
  CASE WHEN annual_inc IS NULL THEN 'Unknown' ELSE income_band END AS income_band,
  CASE WHEN dti        IS NULL THEN 'Unknown' ELSE dti_band    END AS dti_band,
  CASE WHEN fico_mid   IS NULL THEN 'Unknown' ELSE fico_band   END AS fico_band
FROM loans_clean
""")

# Dimensions
con.execute("""
CREATE OR REPLACE TABLE dim_date AS
SELECT d::DATE AS date,
       year(d) AS year, quarter(d) AS quarter,
       month(d) AS month_num, strftime(d, '%b') AS month_name,
       strftime(d, '%Y-%m') AS year_month
FROM generate_series(DATE '2007-01-01', DATE '2018-12-31', INTERVAL 1 DAY) AS t(d)
""")

con.execute("""
CREATE OR REPLACE TABLE dim_grade AS
SELECT ROW_NUMBER() OVER (ORDER BY sub_grade) AS grade_key, grade, sub_grade
FROM (SELECT DISTINCT grade, sub_grade FROM src)
""")

con.execute("""
CREATE OR REPLACE TABLE dim_purpose AS
SELECT ROW_NUMBER() OVER (ORDER BY purpose) AS purpose_key, purpose
FROM (SELECT DISTINCT purpose FROM src)
""")

con.execute("""
CREATE OR REPLACE TABLE dim_state AS
SELECT ROW_NUMBER() OVER (ORDER BY addr_state) AS state_key, addr_state AS state
FROM (SELECT DISTINCT addr_state FROM src)
""")

con.execute("""
CREATE OR REPLACE TABLE dim_borrower AS
SELECT ROW_NUMBER() OVER (ORDER BY home_ownership, verification_status, emp_length,
                          income_band, dti_band, fico_band) AS borrower_key, *
FROM (SELECT DISTINCT home_ownership, verification_status, emp_length,
                      income_band, dti_band, fico_band FROM src)
""")

# Fact table
con.execute("""
CREATE OR REPLACE TABLE fact_loans AS
SELECT s.loan_id, s.issue_date,
       g.grade_key, p.purpose_key, st.state_key, b.borrower_key,
       s.loan_status, s.term_months, s.loan_amnt, s.funded_amnt,
       s.int_rate, s.installment, s.annual_inc, s.dti, s.fico_mid,
       s.total_pymnt, s.total_rec_prncp, s.total_rec_int,
       s.total_rec_late_fee, s.recoveries, s.out_prncp,
       s.is_default, s.is_closed, s.net_profit
FROM src s
LEFT JOIN dim_grade    g  ON s.sub_grade = g.sub_grade
LEFT JOIN dim_purpose  p  ON s.purpose = p.purpose
LEFT JOIN dim_state    st ON s.addr_state = st.state
LEFT JOIN dim_borrower b  ON s.home_ownership = b.home_ownership
                         AND s.verification_status = b.verification_status
                         AND s.emp_length = b.emp_length
                         AND s.income_band = b.income_band
                         AND s.dti_band = b.dti_band
                         AND s.fico_band = b.fico_band
""")

# Parquet export (Power BI ke liye)
os.makedirs('data/clean/star', exist_ok=True)
for t in ['fact_loans','dim_date','dim_grade','dim_purpose','dim_state','dim_borrower']:
    con.execute(f"COPY {t} TO 'data/clean/star/{t}.parquet' (FORMAT PARQUET)")

# Checks
print("Table sizes")
for t in ['fact_loans','dim_date','dim_grade','dim_purpose','dim_state','dim_borrower']:
    print(t, con.sql(f"SELECT COUNT(*) FROM {t}").fetchone()[0])

print("\nOrphan keys (sab 0 hone chahiye)")
print(con.sql("""SELECT
  SUM(CASE WHEN grade_key    IS NULL THEN 1 ELSE 0 END) AS no_grade,
  SUM(CASE WHEN purpose_key  IS NULL THEN 1 ELSE 0 END) AS no_purpose,
  SUM(CASE WHEN state_key    IS NULL THEN 1 ELSE 0 END) AS no_state,
  SUM(CASE WHEN borrower_key IS NULL THEN 1 ELSE 0 END) AS no_borrower
  FROM fact_loans"""))

print("\nStar schema se default % by grade (Step 3 se match hona chahiye)")
print(con.sql("""SELECT g.grade, ROUND(100.0*SUM(f.is_default)/COUNT(*),1) AS default_pct
  FROM fact_loans f JOIN dim_grade g USING (grade_key)
  WHERE f.is_closed = 1 GROUP BY g.grade ORDER BY g.grade"""))