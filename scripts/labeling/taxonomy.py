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
VOLUME_BAND = [
    "lt_100_mo", "100_499_mo", "500_1999_mo", "2000_plus_mo", "unspecified",
]

ALL = {
    "primary_job": PRIMARY_JOB,
    "handoff_topology": HANDOFF_TOPOLOGY,
    "system_gravity": SYSTEM_GRAVITY,
    "trust_surface": TRUST_SURFACE,
    "buying_trigger": BUYING_TRIGGER,
    "volume_band": VOLUME_BAND,
}
