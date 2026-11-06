def bootstrap_school(school) -> None:
    """Default academic/exam/fee configuration for a new school. Idempotent. Imports are local so tenants stays
    importable without the feature apps."""
    from apps.academics.defaults import create_defaults as academics_defaults
    from apps.examinations.defaults import create_defaults as exam_defaults
    from apps.fees.defaults import create_defaults as fee_defaults

    academics_defaults(school)
    exam_defaults(school)
    fee_defaults(school)
