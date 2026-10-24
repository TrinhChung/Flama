"""Safety and comparison contracts for the read-only Browse baseline CLI."""

import unittest

from scripts.benchmark_browse_mysql import compare_reports, digest, require_read_sql


class BrowseBaselineToolTests(unittest.TestCase):
    def report(self, payload=None, *, error=False):
        sample = {"error_type": "OperationalError"} if error else {"payload_sha256": digest(payload)}
        return {"as_of_utc": "2026-10-24T00:00:00Z", "cases": [
            {"name": "page", "input_sha256": "same-case", "samples": [sample]},
        ]}

    def test_writer_and_server_side_effect_statements_are_refused(self):
        for statement in ("UPDATE notes SET tags='[]'", "DELETE FROM notes", "CREATE TABLE x (id INT)",
                          "SELECT 'x' INTO OUTFILE '/tmp/x'", "SELECT GET_LOCK('x', 5)", "CALL writer()",
                          "WITH x AS (SELECT 1) DELETE FROM notes", "WITH x AS (SELECT 1) UPDATE notes SET tags='[]'",
                          "WITH x AS (SELECT 1) REPLACE INTO notes SELECT * FROM x", "SELECT 1; DELETE FROM notes"):
            with self.subTest(statement=statement), self.assertRaises(RuntimeError):
                require_read_sql(statement)

    def test_canonical_locking_reads_and_explain_remain_available(self):
        require_read_sql("SELECT id FROM users WHERE id = %s LOCK IN SHARE MODE")
        require_read_sql("SELECT id FROM study_progress_subjects FOR UPDATE")
        require_read_sql("EXPLAIN FORMAT=JSON SELECT id FROM notes")
        require_read_sql("WITH x AS (SELECT replace(name, %s, %s) FROM decks) SELECT * FROM x")

    def test_comparison_preserves_order_and_nested_array_values(self):
        first = {"items": [{"id": "a", "value": [["x", "y"], "z"]}, {"id": "b"}]}
        self.assertTrue(compare_reports(self.report(first), self.report(first))["equivalent"])
        self.assertFalse(compare_reports(self.report(first), self.report({"items": list(reversed(first["items"]))}))["equivalent"])
        second = {"items": [{"id": "a", "value": ["x", "y", "z"]}, {"id": "b"}]}
        self.assertFalse(compare_reports(self.report(first), self.report(second))["equivalent"])

    def test_equal_failures_do_not_certify_equivalence(self):
        self.assertFalse(compare_reports(self.report(error=True), self.report(error=True))["equivalent"])

    def test_clock_and_case_inputs_must_match(self):
        before, after = self.report({}), self.report({})
        after["as_of_utc"] = "2026-10-25T00:00:00Z"
        self.assertFalse(compare_reports(before, after)["equivalent"])
        after = self.report({})
        after["cases"][0]["input_sha256"] = "changed-input"
        self.assertFalse(compare_reports(before, after)["equivalent"])


if __name__ == "__main__":
    unittest.main()
