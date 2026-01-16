UPDATE sqlapply.sqlapply_history
SET
    status = '%new_status',
    src_checksum = '%new_hash'
WHERE
    change_name = '%change_name'
    AND script_file = '%script_file';