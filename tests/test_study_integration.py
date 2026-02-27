"""Integration tests for study flow and counter updates."""

import unittest
from datetime import datetime, timedelta

from app import create_app
from models import db
from models.user import User
from models.card_progress import CardProgress


class StudyCounterIntegrationTest(unittest.TestCase):
    """Integration tests for counter updates after study."""

    def setUp(self):
        """Set up test app and database."""
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            
            # Create test user
            user = User(username="testuser", email="test@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id
            db.session.commit()
            self.card_ids = [f"card-{i}" for i in range(5)]

    def tearDown(self):
        """Clean up."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_new_cards_show_in_counter(self):
        """New entries should show in New counter before any study."""
        with self.app.app_context():
            # All cards should have no progress record yet
            for card_id in self.card_ids:
                progress = CardProgress.query.filter_by(
                    user_id=self.user_id,
                    card_id=card_id
                ).first()
                self.assertIsNone(progress)
            
            # They should be counted as "new"
            new_count = len(self.card_ids)
            self.assertEqual(new_count, 5)

    def test_learning_card_after_good_answer(self):
        """After answering 'good' to learning step, card should be learning."""
        with self.app.app_context():
            # Create initial progress as "new"
            progress = CardProgress(
                user_id=self.user_id,
                card_id=self.card_ids[0],
                queue="new"
            )
            db.session.add(progress)
            db.session.commit()
            
            # Simulate applyAnswer for "good" from learning
            from app.services.anki_scheduler import default_deck_options, applyAnswer
            from app.routes.vocabulary import _card_state_from_progress, _apply_card_state_to_progress
            
            options = default_deck_options()
            now = datetime.utcnow()
            
            state = _card_state_from_progress(progress, now)
            updated_state = applyAnswer(state, options, now, "good")
            _apply_card_state_to_progress(progress, updated_state, now)
            
            db.session.commit()
            
            # Reload and check
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=self.card_ids[0]
            ).first()
            
            # Should be learning now
            self.assertEqual(progress.queue, "learning")
            # due_at should be in the future (10m from now, default step 0->1)
            self.assertIsNotNone(progress.due_at)
            self.assertGreater(progress.due_at, now)

    def test_review_card_scheduling(self):
        """After graduating from learning to review, card should have due_day set."""
        with self.app.app_context():
            from app.services.anki_scheduler import default_deck_options, applyAnswer
            from app.routes.vocabulary import _card_state_from_progress, _apply_card_state_to_progress

            # Create progress as learning
            progress = CardProgress(
                user_id=self.user_id,
                card_id=self.card_ids[1],
                queue="learning",
                step_index=1,  # At last learning step
                due_at=datetime.utcnow() + timedelta(minutes=10)
            )
            db.session.add(progress)
            db.session.commit()
            
            options = default_deck_options()
            now = datetime.utcnow()
            
            # Answer "good" to graduate to review
            state = _card_state_from_progress(progress, now)
            updated_state = applyAnswer(state, options, now, "good")
            _apply_card_state_to_progress(progress, updated_state, now)
            
            db.session.commit()
            
            # Reload and check
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=self.card_ids[1]
            ).first()
            
            # Should be review now
            self.assertEqual(progress.queue, "review")
            # Should have due_day set
            self.assertIsNotNone(progress.due_day)
            self.assertIsNotNone(progress.interval_days)
            self.assertGreater(progress.interval_days, 0)


if __name__ == '__main__':
    unittest.main()
