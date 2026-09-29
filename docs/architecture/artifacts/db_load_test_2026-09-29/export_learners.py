import json, sys
from pathlib import Path
sys.path.insert(0, ".")
from app import create_app
from app.services.study_composition_service import make_compatibility_composition_id
from models import db
from models.deck import Deck
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.study_authority_enrollment import StudyAuthorityEnrollment
app = create_app()
out = []
with app.app_context():
    for enr in StudyAuthorityEnrollment.query.order_by(StudyAuthorityEnrollment.learner_user_id).all():
        user = db.session.get(User, enr.learner_user_id)
        if not user.email.endswith("@load.test"):
            continue
        root = Deck.query.filter_by(owner_user_id=user.id, parent_id=None).first()
        children = [d.id for d in Deck.query.filter_by(owner_user_id=user.id, parent_id=root.id).order_by(Deck.id)]
        nt = NoteType.query.filter_by(user_id=user.id).first()
        tpl = Template.query.filter_by(note_type_id=nt.id).first()
        out.append({"user_id": user.id, "email": user.email, "root_deck_id": root.id, "child_deck_ids": children,
                    "composition_id": make_compatibility_composition_id(nt.id, tpl.id)})
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
print(len(out))
