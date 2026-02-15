SELECT status FROM sqlapply.sqlapply_history
WHERE change_name = '%change_name' AND script_file = '%script_file'
LIMIT 1;