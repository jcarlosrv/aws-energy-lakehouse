-- Athena bills by bytes scanned. These queries measure what the storage layout
-- saves, holding the row set and the answer constant.
--
-- Read DataScannedInBytes from GetQueryExecution for each statement.

-- An unpartitioned CSV mirror of the curated table: same rows, same columns,
-- no partitioning, row-oriented text.
CREATE TABLE energy.entsoe_load_csv
WITH (
    format = 'TEXTFILE',
    field_delimiter = ',',
    external_location = 's3://jcarlosrv-energy-lakehouse/benchmark/entsoe_load_csv/'
) AS
SELECT "timestamp", load_mw, country, year, month
FROM energy.entsoe_load;

-- Parity: both must return 744 rows and 51406.5669.
SELECT COUNT(*), ROUND(AVG(load_mw), 4)
FROM energy.entsoe_load
WHERE country = 'DE' AND year = 2026 AND month = 7;

SELECT COUNT(*), ROUND(AVG(load_mw), 4)
FROM energy.entsoe_load_csv
WHERE country = 'DE' AND year = 2026 AND month = 7;

-- A. Unpartitioned CSV, filtered.        1,787,790 bytes
SELECT AVG(load_mw)
FROM energy.entsoe_load_csv
WHERE country = 'DE' AND year = 2026 AND month = 7;

-- B. Partitioned Parquet, filtered.          6,985 bytes
SELECT AVG(load_mw)
FROM energy.entsoe_load
WHERE country = 'DE' AND year = 2026 AND month = 7;

-- C. Partitioned Parquet, no partition predicate, so pruning cannot apply.
--    Isolates the columnar contribution.   1,669,955 bytes
SELECT AVG(load_mw)
FROM energy.entsoe_load;

-- A / B = 256x total.  A / C = 1.07x from the format.  C / B = 239x from pruning.

-- Parquet answers this from footer metadata alone, scanning nothing;
-- the CSV table reads every byte.
SELECT COUNT(*) FROM energy.entsoe_load;      -- 0 bytes
SELECT COUNT(*) FROM energy.entsoe_load_csv;  -- 1,787,790 bytes
