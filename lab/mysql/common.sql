USE labdb;

CREATE TABLE lab_records (
    id integer PRIMARY KEY,
    label varchar(40) NOT NULL
);
INSERT INTO lab_records (id, label) VALUES
    (1, 'alpha'), (2, 'beta'), (3, 'gamma');
