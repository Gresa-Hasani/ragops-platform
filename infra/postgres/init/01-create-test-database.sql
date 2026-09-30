-- Separate database for integration tests so they never touch development data.
-- Runs only when the Postgres volume is first initialised.
CREATE DATABASE ragops_test;
