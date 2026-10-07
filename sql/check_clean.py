import duckdb
con = duckdb.connect('data/clean/lending.duckdb')

print("1. Rows, defaults, closed")
print(con.sql("SELECT COUNT(*) AS rows, SUM(is_default) AS defaults, SUM(is_closed) AS closed FROM loans_clean"))

print("2. Duplicate loan IDs")
print(con.sql("SELECT COUNT(*) - COUNT(DISTINCT loan_id) AS duplicates FROM loans_clean"))

print("3. Default rate by grade")
print(con.sql("""SELECT grade, COUNT(*) AS closed_loans,
  ROUND(100.0*SUM(is_default)/COUNT(*),1) AS default_pct
  FROM loans_clean WHERE is_closed=1 GROUP BY grade ORDER BY grade"""))

print("4. Loans per year")
print(con.sql("SELECT issue_year, COUNT(*) AS n FROM loans_clean GROUP BY 1 ORDER BY 1"))

print("5. Nulls")
print(con.sql("""SELECT SUM(CASE WHEN annual_inc IS NULL THEN 1 END) AS null_income,
  SUM(CASE WHEN dti IS NULL THEN 1 END) AS null_dti,
  SUM(CASE WHEN issue_date IS NULL THEN 1 END) AS null_date FROM loans_clean"""))