# Appendix A: Setting up the project and the sample dataset

Build Kora's database from the repo root with
`python scripts/setup_kora.py`. It writes `data/kora.duckdb` in about
30 seconds. To rebuild from scratch, add `--force`. Add `--parquet` to
also export every table to `data/parquet/` for Fabric, Databricks or
Snowflake.

The rest of this appendix arrives as the book is written.
