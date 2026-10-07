import duckdb

duckdb.sql("""
COPY (
  SELECT loan_amnt, funded_amnt, term, int_rate, installment,
         grade, sub_grade, purpose, issue_d, loan_status,
         annual_inc, dti, emp_length, home_ownership,
         verification_status, addr_state,
         fico_range_low, fico_range_high,
         total_pymnt, total_rec_prncp, total_rec_int,
         total_rec_late_fee, recoveries, out_prncp
  FROM read_csv_auto('data/raw/accepted_2007_to_2018Q4.csv',
                     ignore_errors=true, sample_size=-1)
) TO 'data/clean/loans_slim.csv' (HEADER, DELIMITER ',');
""")
print("done")