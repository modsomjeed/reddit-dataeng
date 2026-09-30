import load_clickhouse


def test_quote_escapes_backslashes_and_single_quotes():
    assert load_clickhouse.quote("it's") == "'it\\'s'"
    assert load_clickhouse.quote("a\\b") == "'a\\\\b'"


def test_load_reads_the_kind_folder_through_s3(monkeypatch):
    queries = []
    monkeypatch.setattr(load_clickhouse, "run_query", lambda env, query: queries.append(query))
    env = {"S3_BUCKET": "reddit-raw", "RUSTFS_ACCESS_KEY": "key", "RUSTFS_SECRET_KEY": "se'cret"}

    load_clickhouse.load(env, "comments", "2025-05-31.json")

    (query,) = queries
    assert "INSERT INTO reddit.comments" in query
    assert "s3('http://rustfs:9000/reddit-raw/comments/2025-05-31.json', 'key', 'se\\'cret', 'JSONAsString')" in query


def test_every_kind_has_an_insert_statement():
    assert set(load_clickhouse.INSERT_SQL) == {"posts", "comments"}
    for kind, sql in load_clickhouse.INSERT_SQL.items():
        assert f"INSERT INTO reddit.{kind}" in sql


def test_main_without_dates_loads_every_file(monkeypatch):
    patterns = []
    monkeypatch.setattr(load_clickhouse, "read_env", lambda: {})
    monkeypatch.setattr(load_clickhouse, "load", lambda env, kind, pattern: patterns.append((kind, pattern)))
    monkeypatch.setattr("sys.argv", ["load_clickhouse.py", "--kind", "posts"])

    load_clickhouse.main()
    assert patterns == [("posts", "*.json")]


def test_main_with_a_date_range_loads_one_file_per_day(monkeypatch):
    patterns = []
    monkeypatch.setattr(load_clickhouse, "read_env", lambda: {})
    monkeypatch.setattr(load_clickhouse, "load", lambda env, kind, pattern: patterns.append(pattern))
    monkeypatch.setattr(
        "sys.argv", ["load_clickhouse.py", "--kind", "comments", "--start", "2025-05-30", "--end", "2025-06-01"]
    )

    load_clickhouse.main()
    assert patterns == ["2025-05-30.json", "2025-05-31.json", "2025-06-01.json"]
