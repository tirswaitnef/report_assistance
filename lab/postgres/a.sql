\set ON_ERROR_STOP on

-- Intentionally excessive privileges for the lab application account.
ALTER ROLE lab_app SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS;
GRANT ALL PRIVILEGES ON TABLE public.lab_records TO lab_app;
