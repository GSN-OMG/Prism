import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "github_raw_ingest_closedat.py"


class TestGraphQLQueries(unittest.TestCase):
    def test_no_direct_actor_id_selection(self) -> None:
        """
        Regression test:
        GitHub GraphQL `author`/`actor` fields are `Actor`, which does NOT expose `id`/`databaseId`.
        Those fields must be queried via type-specific inline fragments.
        """
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("author { login id", text)
        self.assertNotIn("mergedBy { login id", text)
        self.assertNotIn("actor { login id", text)
        self.assertNotIn("actor { login id }", text)

        # Ensure the intended fix stays in place for the common case.
        self.assertIn("... on User { id databaseId }", text)

