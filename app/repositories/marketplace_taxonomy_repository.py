from __future__ import annotations

from typing import Any
from models import db
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomyOption,
    TaxonomySubject,
    TaxonomySubjectOptionMap,
)


def list_domains(*, include_inactive: bool = False) -> list[TaxonomyDomain]:
    query = db.session.query(TaxonomyDomain)
    if not include_inactive:
        query = query.filter(TaxonomyDomain.is_active.is_(True))
    return query.order_by(TaxonomyDomain.sort_order.asc(), TaxonomyDomain.id.asc()).all()


def get_domain(domain_id: str) -> TaxonomyDomain | None:
    return db.session.query(TaxonomyDomain).get(domain_id)


def create_domain(
    *,
    domain_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> TaxonomyDomain:
    domain = TaxonomyDomain(
        id=domain_id.strip(),
        label=label.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    db.session.add(domain)
    return domain


def update_domain(
    domain_id: str,
    *,
    label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> TaxonomyDomain | None:
    domain = get_domain(domain_id)
    if not domain:
        return None
    if label is not None:
        domain.label = label.strip()
    if sort_order is not None:
        domain.sort_order = sort_order
    if is_active is not None:
        domain.is_active = is_active
    return domain


def delete_domain(domain_id: str) -> bool:
    domain = get_domain(domain_id)
    if not domain:
        return False
    db.session.delete(domain)
    return True


def list_subjects(
    *,
    domain_id: str | None = None,
    include_inactive: bool = False,
) -> list[TaxonomySubject]:
    query = db.session.query(TaxonomySubject)
    if domain_id:
        query = query.filter(TaxonomySubject.domain_id == domain_id)
    if not include_inactive:
        query = query.filter(TaxonomySubject.is_active.is_(True))
    return query.order_by(TaxonomySubject.sort_order.asc(), TaxonomySubject.id.asc()).all()


def get_subject(subject_id: str) -> TaxonomySubject | None:
    return db.session.query(TaxonomySubject).get(subject_id)


def create_subject(
    *,
    subject_id: str,
    domain_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> TaxonomySubject:
    subject = TaxonomySubject(
        id=subject_id.strip(),
        domain_id=domain_id.strip(),
        label=label.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    db.session.add(subject)
    return subject


def update_subject(
    subject_id: str,
    *,
    domain_id: str | None = None,
    label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> TaxonomySubject | None:
    subject = get_subject(subject_id)
    if not subject:
        return None
    if domain_id is not None:
        subject.domain_id = domain_id.strip()
    if label is not None:
        subject.label = label.strip()
    if sort_order is not None:
        subject.sort_order = sort_order
    if is_active is not None:
        subject.is_active = is_active
    return subject


def delete_subject(subject_id: str) -> bool:
    subject = get_subject(subject_id)
    if not subject:
        return False
    db.session.delete(subject)
    return True


def list_frameworks(
    *,
    subject_id: str | None = None,
    include_inactive: bool = False,
) -> list[TaxonomyFramework]:
    query = db.session.query(TaxonomyFramework)
    if subject_id:
        query = query.filter(TaxonomyFramework.subject_id == subject_id)
    if not include_inactive:
        query = query.filter(TaxonomyFramework.is_active.is_(True))
    return query.order_by(TaxonomyFramework.sort_order.asc(), TaxonomyFramework.id.asc()).all()


def get_framework(framework_id: str) -> TaxonomyFramework | None:
    return db.session.query(TaxonomyFramework).get(framework_id)


def create_framework(
    *,
    framework_id: str,
    subject_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> TaxonomyFramework:
    framework = TaxonomyFramework(
        id=framework_id.strip(),
        subject_id=subject_id.strip(),
        label=label.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    db.session.add(framework)
    return framework


def update_framework(
    framework_id: str,
    *,
    subject_id: str | None = None,
    label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> TaxonomyFramework | None:
    framework = get_framework(framework_id)
    if not framework:
        return None
    if subject_id is not None:
        framework.subject_id = subject_id.strip()
    if label is not None:
        framework.label = label.strip()
    if sort_order is not None:
        framework.sort_order = sort_order
    if is_active is not None:
        framework.is_active = is_active
    return framework


def delete_framework(framework_id: str) -> bool:
    framework = get_framework(framework_id)
    if not framework:
        return False
    db.session.delete(framework)
    return True


def list_framework_levels(
    *,
    framework_id: str | None = None,
    subject_id: str | None = None,
    include_inactive: bool = False,
) -> list[TaxonomyFrameworkLevel]:
    query = db.session.query(TaxonomyFrameworkLevel)
    if framework_id:
        query = query.filter(TaxonomyFrameworkLevel.framework_id == framework_id)
    if subject_id:
        query = query.filter(TaxonomyFrameworkLevel.subject_id == subject_id)
    if not include_inactive:
        query = query.filter(TaxonomyFrameworkLevel.is_active.is_(True))
    return query.order_by(TaxonomyFrameworkLevel.sort_order.asc(), TaxonomyFrameworkLevel.id.asc()).all()


def get_framework_level(level_id: str) -> TaxonomyFrameworkLevel | None:
    return db.session.query(TaxonomyFrameworkLevel).get(level_id)


def create_framework_level(
    *,
    level_id: str,
    framework_id: str,
    subject_id: str,
    label: str,
    difficulty_band: str = "beginner",
    suggested_tags: list[str] | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> TaxonomyFrameworkLevel:
    level = TaxonomyFrameworkLevel(
        id=level_id.strip(),
        framework_id=framework_id.strip(),
        subject_id=subject_id.strip(),
        label=label.strip(),
        difficulty_band=difficulty_band.strip(),
        suggested_tags=suggested_tags or [],
        sort_order=sort_order,
        is_active=is_active,
    )
    db.session.add(level)
    return level


def update_framework_level(
    level_id: str,
    *,
    label: str | None = None,
    difficulty_band: str | None = None,
    suggested_tags: list[str] | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> TaxonomyFrameworkLevel | None:
    level = get_framework_level(level_id)
    if not level:
        return None
    if label is not None:
        level.label = label.strip()
    if difficulty_band is not None:
        level.difficulty_band = difficulty_band.strip()
    if suggested_tags is not None:
        level.suggested_tags = suggested_tags
    if sort_order is not None:
        level.sort_order = sort_order
    if is_active is not None:
        level.is_active = is_active
    return level


def delete_framework_level(level_id: str) -> bool:
    level = get_framework_level(level_id)
    if not level:
        return False
    db.session.delete(level)
    return True


def list_options(
    *,
    option_type: str | None = None,
    include_inactive: bool = False,
) -> list[TaxonomyOption]:
    query = db.session.query(TaxonomyOption)
    if option_type:
        query = query.filter(TaxonomyOption.option_type == option_type)
    if not include_inactive:
        query = query.filter(TaxonomyOption.is_active.is_(True))
    return query.order_by(TaxonomyOption.sort_order.asc(), TaxonomyOption.id.asc()).all()


def get_option(option_id: str, option_type: str | None = None) -> TaxonomyOption | None:
    query = db.session.query(TaxonomyOption).filter(TaxonomyOption.id == option_id)
    if option_type:
        query = query.filter(TaxonomyOption.option_type == option_type)
    return query.first()


def create_option(
    *,
    option_id: str,
    option_type: str,
    label: str,
    sub_label: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> TaxonomyOption:
    opt = TaxonomyOption(
        id=option_id.strip(),
        option_type=option_type.strip(),
        label=label.strip(),
        sub_label=sub_label.strip() if sub_label else None,
        sort_order=sort_order,
        is_active=is_active,
    )
    db.session.add(opt)
    return opt


def update_option(
    option_id: str,
    option_type: str | None = None,
    *,
    label: str | None = None,
    sub_label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> TaxonomyOption | None:
    opt = get_option(option_id, option_type=option_type)
    if not opt:
        return None
    if label is not None:
        opt.label = label.strip()
    if sub_label is not None:
        opt.sub_label = sub_label.strip() if sub_label else None
    if sort_order is not None:
        opt.sort_order = sort_order
    if is_active is not None:
        opt.is_active = is_active
    return opt


def delete_option(option_id: str, option_type: str | None = None) -> bool:
    opt = get_option(option_id, option_type=option_type)
    if not opt:
        return False
    db.session.delete(opt)
    return True


def list_subject_option_maps(
    *,
    subject_id: str | None = None,
    option_type: str | None = None,
) -> list[TaxonomySubjectOptionMap]:
    query = db.session.query(TaxonomySubjectOptionMap)
    if subject_id:
        query = query.filter(TaxonomySubjectOptionMap.subject_id == subject_id)
    if option_type:
        query = query.filter(TaxonomySubjectOptionMap.option_type == option_type)
    return query.all()


def set_subject_option_maps(
    *,
    subject_id: str,
    option_type: str,
    option_ids: list[str],
) -> None:
    db.session.query(TaxonomySubjectOptionMap).filter(
        TaxonomySubjectOptionMap.subject_id == subject_id,
        TaxonomySubjectOptionMap.option_type == option_type,
    ).delete(synchronize_session=False)
    for opt_id in option_ids:
        mapping = TaxonomySubjectOptionMap(
            subject_id=subject_id,
            option_id=opt_id,
            option_type=option_type,
        )
        db.session.add(mapping)


def get_full_taxonomy_tree(*, include_inactive: bool = False) -> dict[str, Any]:
    domains = list_domains(include_inactive=include_inactive)
    subjects = list_subjects(include_inactive=include_inactive)
    frameworks = list_frameworks(include_inactive=include_inactive)
    levels = list_framework_levels(include_inactive=include_inactive)
    options = list_options(include_inactive=include_inactive)
    mappings = list_subject_option_maps()

    return {
        "domains": domains,
        "subjects": subjects,
        "frameworks": frameworks,
        "levels": levels,
        "options": options,
        "mappings": mappings,
    }
