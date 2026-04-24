"""Tests for arkiv bundle export.

mail-memex emits arkiv records in three layouts:
- directory: records.jsonl + schema.yaml + README.md (default)
- .zip:      the same three files inside a zip archive
- .tar.gz:   the same three files inside a gzipped tarball

All layouts share the same records; format is chosen from the output
path's extension.
"""

import json
import tarfile
import zipfile
from pathlib import Path

import yaml
from sqlalchemy import select

from mail_memex.core.database import Database
from mail_memex.core.models import Email
from mail_memex.core.marginalia import create_marginalia
from mail_memex.export.arkiv_export import ArkivExporter, _detect_compression


# ---------------------------------------------------------------------------
# Helpers to load records back from whichever layout was written
# ---------------------------------------------------------------------------


def _read_records_from_dir(out_dir: Path) -> list[dict]:
    text = (out_dir / "records.jsonl").read_text()
    return [json.loads(ln) for ln in text.strip().split("\n") if ln.strip()]


def _read_records_from_zip(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("records.jsonl") as f:
            text = f.read().decode("utf-8")
    return [json.loads(ln) for ln in text.strip().split("\n") if ln.strip()]


def _read_records_from_tar_gz(tar_path: Path) -> list[dict]:
    with tarfile.open(tar_path, "r:gz") as tf:
        extracted = tf.extractfile("records.jsonl")
        assert extracted is not None
        text = extracted.read().decode("utf-8")
    return [json.loads(ln) for ln in text.strip().split("\n") if ln.strip()]


# ---------------------------------------------------------------------------
# _detect_compression
# ---------------------------------------------------------------------------


class TestDetectCompression:
    def test_plain_path_is_directory(self):
        assert _detect_compression("/tmp/bundle") == "dir"

    def test_zip_extension(self):
        assert _detect_compression("/tmp/bundle.zip") == "zip"
        assert _detect_compression("/tmp/bundle.ZIP") == "zip"

    def test_tar_gz_extension(self):
        assert _detect_compression("bundle.tar.gz") == "tar.gz"
        assert _detect_compression("bundle.TAR.GZ") == "tar.gz"

    def test_tgz_extension(self):
        assert _detect_compression("bundle.tgz") == "tar.gz"


# ---------------------------------------------------------------------------
# Directory bundle (default)
# ---------------------------------------------------------------------------


class TestArkivDirectoryBundle:
    """The default bundle shape: records.jsonl + schema.yaml + README.md."""

    def test_directory_bundle_contains_all_three_files(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        assert (out / "records.jsonl").is_file()
        assert (out / "schema.yaml").is_file()
        assert (out / "README.md").is_file()

    def test_each_line_is_valid_json(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        for rec in _read_records_from_dir(out):
            assert isinstance(rec, dict)

    def test_email_record_has_arkiv_fields(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        email_records = [r for r in records if r.get("kind") == "email"]
        assert email_records, "expected at least one email record"
        r = email_records[0]
        assert r["mimetype"] == "message/rfc822"
        assert "timestamp" in r
        assert "metadata" in r
        assert r["uri"].startswith("mail-memex://email/")

    def test_metadata_has_required_fields(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        r = next(r for r in records if r.get("kind") == "email")
        meta = r["metadata"]
        assert "message_id" in meta
        assert "from_addr" in meta
        assert "subject" in meta

    def test_content_included_by_default(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        r = next(r for r in records if r.get("kind") == "email")
        assert "content" in r

    def test_no_body_option(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out, include_body=False).export(emails, session=session)
        for r in _read_records_from_dir(out):
            if r.get("kind") == "email":
                assert "content" not in r

    def test_tags_denormalized_and_sorted(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        found = False
        for r in records:
            tags = r.get("metadata", {}).get("tags")
            if tags:
                assert isinstance(tags, list)
                assert tags == sorted(tags)
                found = True
                break
        assert found, "expected at least one record with tags"

    def test_uri_contains_message_id(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        for r in _read_records_from_dir(out):
            if r.get("kind") == "email":
                msg_id = r["metadata"]["message_id"]
                assert r["uri"] == f"mail-memex://email/{msg_id}"

    def test_empty_export(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        result = ArkivExporter(out).export([])
        assert result.emails_exported == 0
        # records.jsonl exists but is empty.
        assert (out / "records.jsonl").read_text() == ""
        assert (out / "schema.yaml").is_file()
        assert (out / "README.md").is_file()

    def test_creates_parent_directories(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "deep" / "nested" / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        assert (out / "records.jsonl").is_file()


# ---------------------------------------------------------------------------
# .zip bundle
# ---------------------------------------------------------------------------


class TestArkivZipBundle:
    def test_zip_bundle_contains_three_files(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle.zip"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
        assert {"records.jsonl", "schema.yaml", "README.md"}.issubset(names)

    def test_zip_records_match_directory(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        dir_out = tmp_path / "dir"
        zip_out = tmp_path / "bundle.zip"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(dir_out).export(emails, session=session)
            ArkivExporter(zip_out).export(emails, session=session)
        dir_records = _read_records_from_dir(dir_out)
        zip_records = _read_records_from_zip(zip_out)
        assert dir_records == zip_records


# ---------------------------------------------------------------------------
# .tar.gz bundle
# ---------------------------------------------------------------------------


class TestArkivTarGzBundle:
    def test_tar_gz_bundle_contains_three_files(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle.tar.gz"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        with tarfile.open(out, "r:gz") as tf:
            names = set(tf.getnames())
        assert {"records.jsonl", "schema.yaml", "README.md"}.issubset(names)

    def test_tgz_extension_accepted(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle.tgz"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        with tarfile.open(out, "r:gz") as tf:
            assert "records.jsonl" in tf.getnames()

    def test_tar_records_match_directory(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        dir_out = tmp_path / "dir"
        tar_out = tmp_path / "bundle.tar.gz"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(dir_out).export(emails, session=session)
            ArkivExporter(tar_out).export(emails, session=session)
        dir_records = _read_records_from_dir(dir_out)
        tar_records = _read_records_from_tar_gz(tar_out)
        assert dir_records == tar_records


# ---------------------------------------------------------------------------
# Marginalia round-trip
# ---------------------------------------------------------------------------


class TestArkivMarginalia:
    """Bundle must include active marginalia when a session is passed."""

    def test_marginalia_appears_when_session_provided(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            create_marginalia(
                session,
                target_uris=["mail-memex://email/foo@bar"],
                content="Follow up on the proposal",
                category="todo",
            )
            session.flush()
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        marginalia = [r for r in records if r.get("kind") == "marginalia"]
        assert len(marginalia) == 1
        m = marginalia[0]
        assert m["uri"].startswith("mail-memex://marginalia/")
        assert m["content"] == "Follow up on the proposal"
        assert "mail-memex://email/foo@bar" in m["metadata"]["target_uris"]

    def test_marginalia_omitted_when_no_session(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        """Calling export(emails) without a session skips marginalia."""
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            create_marginalia(
                session,
                target_uris=["mail-memex://email/foo@bar"],
                content="legacy call without session",
            )
            session.flush()
            emails = list(session.execute(select(Email)).scalars())
            # Exporter call must happen inside the session so email
            # attributes are still attached.
            ArkivExporter(out).export(emails)
        records = _read_records_from_dir(out)
        assert all(r.get("kind") == "email" for r in records)

    def test_archived_marginalia_excluded(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        from mail_memex.core.marginalia import delete_marginalia

        out = tmp_path / "bundle"
        with populated_db.session() as session:
            created = create_marginalia(
                session,
                target_uris=["mail-memex://email/foo@bar"],
                content="to be archived",
            )
            session.flush()
            delete_marginalia(session, created["uuid"])
            session.flush()
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        assert all(r.get("kind") != "marginalia" for r in records)


# ---------------------------------------------------------------------------
# schema.yaml & README.md
# ---------------------------------------------------------------------------


class TestArkivSchemaYaml:
    def test_schema_yaml_parseable(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        schema = yaml.safe_load((out / "schema.yaml").read_text())
        assert schema["scheme"] == "mail-memex"
        assert "kinds" in schema
        assert "email" in schema["kinds"]
        assert "marginalia" in schema["kinds"]

    def test_schema_counts_match_records(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        schema = yaml.safe_load((out / "schema.yaml").read_text())
        records = _read_records_from_dir(out)
        email_recs = [r for r in records if r.get("kind") == "email"]
        assert schema["counts"]["email"] == len(email_recs)


class TestArkivReadme:
    def test_readme_has_echo_frontmatter(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            ArkivExporter(out).export(emails, session=session)
        text = (out / "README.md").read_text()
        assert text.startswith("---")
        assert "generator: mail-memex" in text
        assert "mail-memex import arkiv" in text


# ---------------------------------------------------------------------------
# ExportResult
# ---------------------------------------------------------------------------


class TestExportResult:
    def test_export_result_format(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            result = ArkivExporter(out).export(emails, session=session)
        assert result.format == "arkiv"
        assert result.output_path == str(out)

    def test_export_result_to_dict(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            result = ArkivExporter(out).export(emails, session=session)
        d = result.to_dict()
        assert d["format"] == "arkiv"
        assert d["emails_exported"] == 5

    def test_record_count_matches_email_count(
        self, populated_db: Database, tmp_path: Path
    ) -> None:
        out = tmp_path / "bundle"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            result = ArkivExporter(out).export(emails, session=session)
        records = _read_records_from_dir(out)
        email_records = [r for r in records if r.get("kind") == "email"]
        assert len(email_records) == result.emails_exported
