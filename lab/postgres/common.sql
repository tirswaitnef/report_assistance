\set ON_ERROR_STOP on
\getenv app_password POSTGRES_APP_PASSWORD

CREATE ROLE lab_app LOGIN PASSWORD :'app_password';
CREATE TABLE public.lab_records (
    id integer PRIMARY KEY,
    label text NOT NULL
);
INSERT INTO public.lab_records (id, label) VALUES
    (1, 'alpha'), (2, 'beta'), (3, 'gamma');

-- These are deliberately non-sensitive, generated fixture records.
COMMENT ON TABLE public.lab_records IS 'Synthetic research lab fixture; no personal or production data';
