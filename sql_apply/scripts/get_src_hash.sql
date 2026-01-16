SELECT src_checksum FROM sqlapply.sqlapply_history
WHERE change_name = '%chg_name' AND script_file = '%script_name'
LIMIT 1;