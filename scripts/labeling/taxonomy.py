PRIMARY_JOB = [
    "scheduling_booking", "catalog_guided_selling", "quoting_pricing", "order_taking",
    "claims_intake", "shipment_tracking", "lead_qualification", "faq_education",
]
HANDOFF_TOPOLOGY = [
    "bot_only_implied", "generic_human_handoff", "book_specialist", "role_based_routing",
]
SYSTEM_GRAVITY = [
    "standalone_ok", "named_system_desired", "must_integrate",
]
TRUST_SURFACE = [
    "standard", "health_sensitive", "regulated_advice_boundary", "discretion_prestige",
]
BUYING_TRIGGER = [
    "ops_saturation", "coverage_gap", "growth_ambition", "budget_cautious", "efficiency_general",
]
# The model reports the unit a volume was stated in; it never converts between units.
VOLUME_PERIOD = [
    "daily", "weekly", "monthly", "yearly", "unspecified",
]

# Dimensions the model picks from a fixed list. `volume_amount` is an integer and
# is validated separately; `volume_band` is derived, never asked for.
ALL = {
    "primary_job": PRIMARY_JOB,
    "handoff_topology": HANDOFF_TOPOLOGY,
    "system_gravity": SYSTEM_GRAVITY,
    "trust_surface": TRUST_SURFACE,
    "buying_trigger": BUYING_TRIGGER,
    "volume_period": VOLUME_PERIOD,
}

VOLUME_BAND = [
    "lt_100_mo", "100_499_mo", "500_1999_mo", "2000_plus_mo", "unspecified",
]
PERIOD_MULTIPLIER = {"daily": 30.0, "weekly": 4.33, "monthly": 1.0, "yearly": 1 / 12}


def volume_band(amount: int | None, period: str | None) -> str:
    """Monthly band from a figure stated in its own unit.

    Asking a 27B model to bucket "300 consultas diarias" makes it do arithmetic,
    which it gets wrong far more often than it gets the reading wrong: measured
    against the transcripts, agreement fell from 72.8% on monthly figures to
    25.6% on daily ones. So the model reports the number and the unit, and the
    multiplication happens here, where it is exact and tested.
    """
    multiplier = PERIOD_MULTIPLIER.get(period or "")
    if not amount or amount <= 0 or multiplier is None:
        return "unspecified"
    monthly = amount * multiplier
    if monthly < 100:
        return "lt_100_mo"
    if monthly < 500:
        return "100_499_mo"
    if monthly < 2000:
        return "500_1999_mo"
    return "2000_plus_mo"
