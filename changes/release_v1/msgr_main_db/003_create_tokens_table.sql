DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'S'
          AND c.relname = 'tokens_seq'
          AND n.nspname = 'msgr_schema'
    ) THEN
        EXECUTE '
            CREATE SEQUENCE msgr_schema.tokens_seq
                INCREMENT 1
                MINVALUE 0
                MAXVALUE 999999999999999
                START 1
                CACHE 1
        ';
        RAISE NOTICE 'Sequence msgr_schema.tokens_seq created.';
    ELSE
        RAISE NOTICE 'Sequence msgr_schema.tokens_seq already exists.';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'msgr_schema'
          AND table_name = 'tokens'
    ) THEN
        EXECUTE '
            CREATE TABLE msgr_schema.tokens (
                id BIGINT DEFAULT nextval(''msgr_schema.tokens_seq''),
                token TEXT NOT NULL,
                username VARCHAR(255) NOT NULL,
		created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP

                CONSTRAINT tokens_pk PRIMARY KEY (id)
            )
        ';
        RAISE NOTICE 'Table msgr_schema.tokens created.';
    ELSE
        RAISE NOTICE 'Table msgr_schema.tokens already exists.';
    END IF;
END
$$;

ALTER TABLE IF EXISTS msgr_schema.tokens OWNER TO current_user;
