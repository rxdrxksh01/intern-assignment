# NOTES

## 1. CSV problems found

The CSV was usable, but it needed cleaning before using it in the API or Q&A system.

I found these main problems:

- Some text fields had extra whitespace. The biggest issue was in `date_added`, where many values had leading spaces.
- A few title, description, and cast values had messy whitespace such as non-breaking spaces, newlines, tabs, or repeated spaces.
- Some `country` values ended with a trailing comma, which created empty values when splitting the field.
- Several optional metadata fields were missing:
  - `director`: 1,969 rows
  - `cast`: 570 rows
  - `country`: 476 rows
  - `date_added`: 11 rows
  - `rating`: 10 rows
- Multi-value fields were stored as comma-separated strings: `country`, `listed_in`, `cast`, and `director`.
- `duration` was stored as text, for example `90 min`, `1 Season`, or `3 Seasons`.
- I found one duplicate-content row where all cleaned fields matched another row except `show_id`.

## 2. What I fixed

All cleaning happens in code. I did not manually edit `data/netflix_titles.csv`.

The ingestion script currently does the following:

- Cleans text by removing extra spaces, non-breaking spaces, newlines, tabs, and repeated whitespace.
- Converts missing human-facing metadata to `"Unknown"` for:
  - `director`
  - `cast`
  - `country`
  - `rating`
  - `listed_in`
- Keeps missing `date_added` as `NULL` instead of `"Unknown"` because dates should stay sortable and filterable.
- Parses `date_added` into `YYYY-MM-DD`.
- Parses `release_year` as an integer.
- Splits `duration` into:
  - `duration_value`
  - `duration_unit`
- Normalized unclear rating abbreviations: `NR` to `Not Rated` and `UR` to `Unrated`.
- Splits comma-separated fields into separate child tables.
- Removes empty list values caused by trailing commas.
- Removes duplicate values inside list fields while keeping the original order.
- Drops duplicate-content rows where every cleaned field matches except `show_id`.

## 3. What I left unchanged

I intentionally did not over-clean the dataset.

I left these things unchanged:

- I did not drop rows just because optional metadata was missing.
- I did not drop duplicate titles generally because titles are not guaranteed to be unique.
- I did not add external metadata such as IMDb, TMDB, posters, language, or current Netflix availability.
- I did not scale numeric fields like `release_year` or duration because this is not a tabular ML model.
- I did not create many boolean quality-flag columns because the ingestion summary already reports the important issues.

## 4. Row dropping decisions

Rows are dropped only when they are not usable for the catalogue.

A row can be dropped for:

- missing `show_id`
- missing or invalid `type`
- missing `title`
- missing or invalid `release_year`
- missing `description`
- duplicate `show_id`
- duplicate full content except `show_id`

Rows are not dropped for missing:

- `director`
- `cast`
- `country`
- `rating`
- `date_added`

I kept those rows because missing optional metadata does not make a Netflix title unusable.

## 5. Missing value decisions

I used `"Unknown"` for missing human-facing metadata because it is clearer in API responses than returning empty values.

For example:

- missing director becomes `"Unknown"`
- missing cast becomes `"Unknown"`
- missing country becomes `"Unknown"`
- missing rating becomes `"Unknown"`

I did not use `"Unknown"` for dates or numeric fields.

For example:

- missing `date_added` stays `NULL`
- missing or invalid `duration` becomes `NULL` for `duration_value` and `duration_unit`

This keeps date and numeric fields easier to filter, sort, and query.

## 6. Schema decisions

I used SQLite because the dataset is small, local, and easy to reproduce.

The main table is:

- `titles`

It stores one row per Netflix title:

- `show_id`
- `type`
- `title`
- `release_year`
- `rating`
- `duration_value`
- `duration_unit`
- `date_added`
- `description`

I used `show_id` as the primary key because titles are not unique.

For multi-value fields, I created separate child tables:

- `title_countries`
- `title_genres`
- `title_cast`
- `title_directors`

I chose this because fields like `country`, `cast`, `director`, and `listed_in` can contain multiple comma-separated values.

For example, a title with `United States, India` should be stored as two country rows, not one raw string. This makes country filtering and country stats more accurate.

Each child table also has a `position` column. This preserves the original order from the CSV, which is useful for fields like cast and directors.

## 7. Current ingestion result

Running `python ingest.py` currently gives:

- Rows read: 6,234
- Rows loaded: 6,233
- Rows dropped: 1

The dropped row was a duplicate-content row where all cleaned fields matched another row except `show_id`.

The cleaned database is written to `data/netflix.db`.

The database contains these tables:

- `titles`
- `title_countries`
- `title_genres`
- `title_cast`
- `title_directors`

## 8. Current limitations of ingestion

The ingestion is good enough for the first part of the assignment, but it still has some limitations:

- `"Unknown"` is useful for display, but it means missing metadata is now mixed with normal values in the child tables.
- Duplicate detection only removes rows with identical cleaned content except `show_id`; it does not detect near-duplicates.
- The dataset is a historical Netflix snapshot and should not be treated as the current Netflix catalogue.
- The original CSV has limited metadata, so questions about language, IMDb rating, posters, or current availability cannot be answered from this data alone.
