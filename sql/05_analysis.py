import duckdb, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

con = duckdb.connect('data/clean/lending.duckdb')
con.execute("SET memory_limit='6GB'; SET threads=4;")
os.makedirs('docs/analysis', exist_ok=True)

# ---------- 1. Risk segment (grade + FICO + DTI points) ----------
con.execute("""
CREATE OR REPLACE TABLE risk_scored AS
SELECT f.loan_id,
  (ascii(g.grade) - 64)
  + CASE b.fico_band WHEN '4. 740+' THEN 0 WHEN '3. 700-739' THEN 1
                     WHEN '2. 670-699' THEN 2 WHEN '1. <670' THEN 3 ELSE 1 END
  + CASE b.dti_band WHEN '1. <10' THEN 0 WHEN '2. 10-20' THEN 1
                    WHEN '3. 20-30' THEN 2 WHEN '4. 30+' THEN 3 ELSE 1 END AS risk_points
FROM fact_loans f
JOIN dim_grade g USING (grade_key)
JOIN dim_borrower b USING (borrower_key)
""")

# fact table me risk_segment jodna
con.execute("""
CREATE OR REPLACE TABLE fact_loans_pbi_v2 AS
SELECT p.*,
  r.risk_points,
  CASE WHEN r.risk_points <= 4 THEN '1. Low'
       WHEN r.risk_points <= 7 THEN '2. Medium'
       ELSE '3. High' END AS risk_segment
FROM fact_loans_pbi p
JOIN risk_scored r USING (loan_id)
""")
con.execute("COPY fact_loans_pbi_v2 TO 'data/clean/pbi/fact_loans.parquet' (FORMAT PARQUET)")

# ---------- 2. Vintage ----------
vintage = con.sql("""
SELECT year(f.issue_date) AS issue_year, g.grade,
       COUNT(*) AS loans, SUM(f.is_closed) AS closed, SUM(f.is_default) AS defaults,
       ROUND(100.0*SUM(f.is_default)/NULLIF(SUM(f.is_closed),0),1) AS default_pct,
       ROUND(100.0*(COUNT(*)-SUM(f.is_closed))/COUNT(*),1) AS pct_still_open
FROM fact_loans_pbi_v2 f JOIN dim_grade g USING (grade_key)
GROUP BY 1,2 ORDER BY 1,2
""").df()
vintage.to_csv('docs/analysis/vintage.csv', index=False)

# ---------- 3. Profit by grade ----------
profit = con.sql("""
SELECT g.grade, COUNT(*) AS closed_loans,
       ROUND(AVG(f.int_rate),2) AS avg_int_rate,
       ROUND(100.0*SUM(f.is_default)/COUNT(*),1) AS default_pct,
       ROUND(SUM(f.net_profit)/1e6,1) AS net_profit_musd,
       ROUND(100.0*SUM(f.net_profit)/SUM(f.funded_amnt),2) AS roi_pct
FROM fact_loans_pbi_v2 f JOIN dim_grade g USING (grade_key)
WHERE f.is_closed = 1
GROUP BY g.grade ORDER BY g.grade
""").df()
profit.to_csv('docs/analysis/profit_by_grade.csv', index=False)

# ---------- 4. Risk segment summary ----------
seg = con.sql("""
SELECT risk_segment, COUNT(*) AS loans,
       SUM(is_closed) AS closed,
       ROUND(100.0*SUM(is_default)/NULLIF(SUM(is_closed),0),1) AS default_pct,
       ROUND(AVG(int_rate),2) AS avg_int_rate,
       ROUND(100.0*SUM(net_profit)/NULLIF(SUM(CASE WHEN is_closed=1 THEN funded_amnt END),0),2) AS roi_pct
FROM fact_loans_pbi_v2 GROUP BY 1 ORDER BY 1
""").df()
seg.to_csv('docs/analysis/risk_segments.csv', index=False)

# ---------- 5. Budget (pichhle saal ke same month ka funded x 1.10) ----------
con.execute("""
CREATE OR REPLACE TABLE budget_monthly AS
WITH m AS (
  SELECT date_trunc('month', issue_date)::DATE AS month_start, SUM(funded_amnt) AS funded
  FROM fact_loans_pbi_v2 GROUP BY 1
)
SELECT cur.month_start, ROUND(prev.funded * 1.10, 0) AS budget_funded
FROM m cur
JOIN m prev ON prev.month_start = (cur.month_start - INTERVAL 1 YEAR)::DATE
""")
con.execute("COPY budget_monthly TO 'data/clean/pbi/budget_monthly.parquet' (FORMAT PARQUET)")

# ---------- Charts ----------
pv = vintage.pivot(index='issue_year', columns='grade', values='default_pct')
pv.loc[2009:2016].plot(figsize=(9,5), marker='o')
plt.title('Default % by issue year and grade (closed loans)')
plt.ylabel('Default %'); plt.xlabel('Issue year'); plt.grid(alpha=.3)
plt.savefig('docs/analysis/vintage.png', dpi=130, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(8,5))
colors = ['#6a1b9a' if v >= 0 else '#c62828' for v in profit['roi_pct']]
ax.bar(profit['grade'], profit['roi_pct'], color=colors)
ax.set_title('ROI % by grade (closed loans)'); ax.set_ylabel('Net profit / funded %')
ax.axhline(0, color='black', lw=.8)
plt.savefig('docs/analysis/roi_by_grade.png', dpi=130, bbox_inches='tight'); plt.close()

# ---------- Print ----------
print("\n=== PROFIT BY GRADE ===");   print(profit.to_string(index=False))
print("\n=== RISK SEGMENTS ===");     print(seg.to_string(index=False))
print("\n=== VINTAGE (default %, pivot) ==="); print(pv.to_string())
print("\n=== STILL OPEN % (grade A) ===")
print(vintage[vintage.grade=='A'][['issue_year','pct_still_open']].to_string(index=False))
print("\nBudget rows:", con.sql("SELECT COUNT(*) FROM budget_monthly").fetchone()[0])
print("Charts saved in docs/analysis/")