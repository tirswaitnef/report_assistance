-- Remove the image's default application grants before granting read access.
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'lab_app'@'%';
GRANT SELECT ON labdb.* TO 'lab_app'@'%';
