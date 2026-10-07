import duckdb

con = duckdb.connect('data/clean/lending.duckdb')
con.execute("SET memory_limit='4GB'; SET threads=4;")

con.execute("""
CREATE OR REPLACE TABLE loans_clean AS
WITH base AS (
  SELECT
    ROW_NUMBER() OVER () AS loan_id,
    loan_amnt, funded_amnt,

    -- " 36 months" -> 36
    CAST(regexp_extract(term, '(\\d+)', 1) AS INTEGER) AS term_months,

    int_rate, installment, grade, sub_grade, purpose,

    -- "Dec-2015" -> 2015-12-01
    CAST(strptime('01-' || issue_d, '%d-%b-%Y') AS DATE) AS issue_date,

    loan_status, annual_inc, dti, emp_length, home_ownership,
    verification_status, addr_state,
    (fico_range_low + fico_range_high) / 2.0 AS fico_mid,
    total_pymnt, total_rec_prncp, total_rec_int,
    total_rec_late_fee, recoveries, out_prncp,

    CASE WHEN loan_status LIKE '%Charged Off%'
           OR loan_status = 'Default' THEN 1 ELSE 0 END AS is_default,

    CASE WHEN loan_status LIKE '%Fully Paid%'
           OR loan_status LIKE '%Charged Off%'
           OR loan_status = 'Default' THEN 1 ELSE 0 END AS is_closed
  FROM read_csv_auto('data/clean/loans_slim.csv',
       types={'issue_d':'VARCHAR','term':'VARCHAR','emp_length':'VARCHAR'},
       ignore_errors=true)
  WHERE loan_amnt IS NOT NULL
    AND issue_d IS NOT NULL
    AND grade IS NOT NULL
)
SELECT
  *,
  year(issue_date) AS issue_year,

  CASE WHEN annual_inc < 40000  THEN '1. <40k'
       WHEN annual_inc < 70000  THEN '2. 40-70k'
       WHEN annual_inc < 100000 THEN '3. 70-100k'
       ELSE '4. 100k+' END AS income_band,

  CASE WHEN dti < 10 THEN '1. <10'
       WHEN dti < 20 THEN '2. 10-20'
       WHEN dti < 30 THEN '3. 20-30'
       ELSE '4. 30+' END AS dti_band,

  CASE WHEN fico_mid < 670 THEN '1. <670'
       WHEN fico_mid < 700 THEN '2. 670-699'
       WHEN fico_mid < 740 THEN '3. 700-739'
       ELSE '4. 740+' END AS fico_band,

  -- profit sirf closed loans pe meaningful hai
  CASE WHEN is_closed = 1
       THEN total_rec_int + total_rec_late_fee + recoveries
            - (funded_amnt - total_rec_prncp)
       END AS net_profit
FROM base;
""")

con.execute("COPY loans_clean TO 'data/clean/loans_clean.parquet' (FORMAT PARQUET)")
print("done")