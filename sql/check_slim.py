import duckdb

print(duckdb.sql("SELECT COUNT(*) AS rows FROM 'data/clean/loans_slim.csv'"))

print(duckdb.sql("""
  SELECT loan_status, COUNT(*) AS n
  FROM 'data/clean/loans_slim.csv'
  GROUP BY loan_status ORDER BY n DESC
"""))

print(duckdb.sql("SELECT * FROM 'data/clean/loans_slim.csv' LIMIT 5"))