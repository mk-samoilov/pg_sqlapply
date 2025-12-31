DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'msgr_schema' AND table_name = 'schema_info'
    ) THEN
        CREATE TABLE tgg.schema_info (
            version TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        );
        INSERT INTO tgg.schema_info (version) VALUES ('1.0');
        RAISE NOTICE 'Version 1.0 inserted into schema_info';
    ELSE
        UPDATE tgg.schema_info SET version = '1.0', updated_at = now();
        RAISE NOTICE 'Schema version updated to 1.0';
    END IF;
END
$$;
