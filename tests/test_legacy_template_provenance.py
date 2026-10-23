"""Pure evidence/guard checks for legacy receipts; no database emulation."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from app.services import legacy_template_provenance_service as service
from app.services import template_release_service as releases
from scripts.migrations import marketplace_legacy_provenance as cutover


class LegacyTemplateProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.local = {"id": "legacy", "owner_user_id": 7, "origin": "authored",
            "source_template_id": None, "source_version_id": None, "front_html": "PERSONAL EDIT"}
        self.source = {"id": "original", "owner_user_id": 2, "origin": "authored", "source_template_id": None}
        self.install = {"id": "receipt", "user_id": 7, "source_note_type_id": "source-nt", "installed_note_type_id": "local-nt"}

    def test_unique_copy_preserves_original_author_without_inventing_release(self):
        with patch.object(service.repository, "template", side_effect=[self.local, self.source]), \
                patch.object(service.repository, "candidate_installs", return_value=[self.install]), \
                patch.object(service.repository, "active_template_ids", side_effect=[["legacy"], ["original"]]):
            result = service.legacy_reference(self.session, "legacy")
        self.assertEqual(result["source_template_id"], "original")
        self.assertEqual(result["source_owner_user_id"], 2)
        self.assertTrue(result["legacy_unpinned"])
        self.assertNotIn("applied_release_id", result)

    def test_ambiguous_mapping_stays_received_but_has_no_guessed_source(self):
        with patch.object(service.repository, "template", return_value=self.local), \
                patch.object(service.repository, "candidate_installs", return_value=[self.install]), \
                patch.object(service.repository, "active_template_ids", side_effect=[["legacy"], ["source-a", "source-b"]]):
            result = service.legacy_reference(self.session, "legacy")
            self.assertIsNone(result["source_template_id"])
            self.assertEqual(result["confidence"], "ambiguous_install_copy")
            self.assertTrue(service.is_received_template(self.session, self.local))

    def test_explicit_reviewed_pointer_survives_source_mapping_changes(self):
        migrated = {**self.local, "origin": "market_copy", "source_template_id": "original"}
        with patch.object(service.repository, "template", side_effect=[migrated, self.source]), \
                patch.object(service.repository, "candidate_installs", return_value=[self.install]), \
                patch.object(service.repository, "active_template_ids", side_effect=[["legacy"], ["new-source-a", "new-source-b"]]):
            self.assertEqual(service.legacy_reference(self.session, "legacy")["source_template_id"], "original")

    def test_inferred_copy_cannot_publish_as_authored(self):
        with patch.object(service.repository, "candidate_installs", return_value=[self.install]):
            with self.assertRaises(releases.TemplateReleaseError) as error:
                releases._authored(self.local, session=self.session)
        self.assertEqual(error.exception.code, "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN")

    def test_new_authored_template_without_copy_evidence_remains_authored(self):
        with patch.object(service.repository, "candidate_installs", return_value=[]):
            releases._authored(self.local, session=self.session)
            self.assertFalse(service.is_received_template(self.session, self.local))

    def test_cutover_changes_only_provenance_not_personal_content_or_pin(self):
        before = {"template": [{**self.local, "updated_at": "2026-10-01T00:00:00"}],
            "install": [{"applied_release_id": None}], "applications": [{"template_id": "legacy", "input_bindings": {"word": "field"}}]}
        original = deepcopy(before)
        after = cutover.expected_after({"before": before, "reference": {"source_template_id": "original"}})
        self.assertEqual(before, original)
        self.assertEqual(after["template"][0]["front_html"], "PERSONAL EDIT")
        self.assertIsNone(after["template"][0]["source_version_id"])
        self.assertEqual(after["install"], before["install"])
        self.assertEqual(after["applications"], before["applications"])


if __name__ == "__main__":
    unittest.main()
