DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'msgr_schema') THEN
        EXECUTE 'CREATE SCHEMA msgr_schema AUTHORIZATION ' || quote_ident(current_user);
        RAISE NOTICE 'Schema msgr_schema created.';
    ELSE
        RAISE NOTICE 'Schema msgr_schema already exists.';
    END IF;
END
$$;
