import backup_raw


def test_backup_copies_new_files_and_skips_ones_already_there(tmp_path, fake_s3):
    fake_s3.objects = {"posts/2025-05-31.json": b"[1]", "comments/2025-05-31.json": b"[2, 3]"}
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "2025-05-31.json").write_bytes(b"[1]")

    backup_raw.backup(fake_s3, "reddit-raw", tmp_path)

    assert (tmp_path / "comments" / "2025-05-31.json").read_bytes() == b"[2, 3]"
    assert (tmp_path / "posts" / "2025-05-31.json").read_bytes() == b"[1]"


def test_backup_recopies_a_file_whose_size_changed(tmp_path, fake_s3):
    fake_s3.objects = {"posts/2025-05-31.json": b"[1, 2, 3]"}
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "2025-05-31.json").write_bytes(b"[1]")

    backup_raw.backup(fake_s3, "reddit-raw", tmp_path)
    assert (tmp_path / "posts" / "2025-05-31.json").read_bytes() == b"[1, 2, 3]"


def test_restore_uploads_only_what_the_bucket_is_missing(tmp_path, fake_s3):
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "2025-05-30.json").write_bytes(b"[1]")
    (tmp_path / "posts" / "2025-05-31.json").write_bytes(b"[2]")
    fake_s3.objects = {"posts/2025-05-30.json": b"[1]"}

    backup_raw.restore(fake_s3, "reddit-raw", tmp_path)

    assert fake_s3.objects == {"posts/2025-05-30.json": b"[1]", "posts/2025-05-31.json": b"[2]"}
