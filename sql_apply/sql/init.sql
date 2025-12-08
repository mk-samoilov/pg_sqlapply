DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'sqlapply') THEN
        EXECUTE 'CREATE SCHEMA sqlapply AUTHORIZATION ' || quote_ident(current_user);
        RAISE NOTICE 'Schema sqlapply created.';
    ELSE
        RAISE NOTICE 'Schema sqlapply already exists.';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'S'
          AND c.relname = 'sqlapply_history_seq'
          AND n.nspname = 'sqlapply'
    ) THEN
        EXECUTE '
            CREATE SEQUENCE sqlapply.sqlapply_history_seq
                INCREMENT 1
                MINVALUE 0
                MAXVALUE 999999999999999
                START 1
                CACHE 1
        ';
        RAISE NOTICE 'Sequence sqlapply.sqlapply_history_seq created.';
    ELSE
        RAISE NOTICE 'Sequence sqlapply.sqlapply_history_seq already exists.';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'sqlapply'
          AND table_name = 'sqlapply_history'
    ) THEN
        EXECUTE '
            CREATE TABLE sqlapply.sqlapply_history (
                id BIGINT DEFAULT nextval(''sqlapply.sqlapply_history_seq''),
                change_name VARCHAR(255) NOT NULL,
                script_file VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                src_checksum TEXT NOT NULL,
                CONSTRAINT sqlapply_history_pk PRIMARY KEY (id),
                CONSTRAINT sqlapply_history_un UNIQUE (change_name, script_file),
                CONSTRAINT status_check CHECK (status IN (''SUCCESS'', ''PSQL_FATAL_ERROR'', ''CONNECTION_ERROR'', ''SCRIPT_ERROR'', ''IN_PROGRESS'', ''EXECUTION_STOPPED''))
            )
        ';
        RAISE NOTICE 'Table sqlapply.sqlapply_history created.';
    ELSE
        RAISE NOTICE 'Table sqlapply.sqlapply_history already exists.';
    END IF;
END
$$;

ALTER TABLE IF EXISTS sqlapply.sqlapply_history OWNER TO current_user;
