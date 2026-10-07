import duckdb

cols = duckdb.sql("""
  DESCRIBE SELECT *
  FROM read_csv_auto('data/raw/accepted_2007_to_2018Q4.csv',
                     sample_size=5000, ignore_errors=true)
""").df()

print(len(cols), "columns")
print(cols[['column_name', 'column_type']].to_string())
cols[['column_name', 'column_type']].to_csv('docs/columns.csv', index=False)