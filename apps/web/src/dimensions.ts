export type EnumDef = { key: string; label: string; gloss: string }

export type DimensionDef = {
  key: string
  title: string
  why: string
  enums: EnumDef[]
}

export const DIMENSIONS: DimensionDef[] = [
  {
    key: 'primary_job',
    title: 'Primary job',
    why: 'Maps each discovery note to the bot capability the prospect wants — packaging for Sales, feature demand for Product.',
    enums: [
      { key: 'scheduling_booking', label: 'Scheduling & booking', gloss: 'Appointments and reservations' },
      { key: 'catalog_guided_selling', label: 'Catalog & guided selling', gloss: 'Product discovery and recommendations' },
      { key: 'quoting_pricing', label: 'Quoting & pricing', gloss: 'Estimates and price quotes' },
      { key: 'order_taking', label: 'Order taking', gloss: 'Capturing and submitting orders' },
      { key: 'claims_intake', label: 'Claims intake', gloss: 'Filing and triaging claims' },
      { key: 'shipment_tracking', label: 'Shipment tracking', gloss: 'Delivery status and logistics' },
      { key: 'lead_qualification', label: 'Lead qualification', gloss: 'Screening and routing prospects' },
      { key: 'faq_education', label: 'FAQ & education', gloss: 'Answering common questions' },
    ],
  },
  {
    key: 'handoff_topology',
    title: 'Handoff topology',
    why: 'How the bot should involve humans — shapes implementation and win rate.',
    enums: [
      { key: 'bot_only_implied', label: 'Bot only (implied)', gloss: 'Fully automated, no human step' },
      { key: 'generic_human_handoff', label: 'Generic human handoff', gloss: 'Escalate to any available agent' },
      { key: 'book_specialist', label: 'Book specialist', gloss: 'Schedule time with an expert' },
      { key: 'role_based_routing', label: 'Role-based routing', gloss: 'Route to the right team or role' },
    ],
  },
  {
    key: 'system_gravity',
    title: 'System gravity',
    why: 'How glued to existing systems — drives SE load and delivery cost.',
    enums: [
      { key: 'standalone_ok', label: 'Standalone OK', gloss: 'Works without integrations' },
      { key: 'named_system_desired', label: 'Named system desired', gloss: 'Prefers a specific platform' },
      { key: 'must_integrate', label: 'Must integrate', gloss: 'Requires deep system connection' },
    ],
  },
  {
    key: 'trust_surface',
    title: 'Trust surface',
    why: 'Domain sensitivity — sets compliance tone and who must approve.',
    enums: [
      { key: 'standard', label: 'Standard', gloss: 'General business, low sensitivity' },
      { key: 'health_sensitive', label: 'Health sensitive', gloss: 'Medical or wellness context' },
      { key: 'regulated_advice_boundary', label: 'Regulated advice boundary', gloss: 'Legal, financial, or compliance limits' },
      { key: 'discretion_prestige', label: 'Discretion & prestige', gloss: 'High-touch, confidential, luxury' },
    ],
  },
  {
    key: 'voice_contract',
    title: 'Voice contract',
    why: 'Expected bot tone and brand fit — wrong voice kills a good demo.',
    enums: [
      { key: 'not_specified', label: 'Not specified', gloss: 'No tone preference stated' },
      { key: 'warm_hospitable', label: 'Warm & hospitable', gloss: 'Friendly, welcoming service' },
      { key: 'corporate_expert', label: 'Corporate expert', gloss: 'Professional, authoritative' },
      { key: 'motivational_energetic', label: 'Motivational & energetic', gloss: 'Upbeat, action-oriented' },
      { key: 'luxury_prestige', label: 'Luxury & prestige', gloss: 'Refined, exclusive feel' },
      { key: 'care_trustworthy', label: 'Care & trustworthy', gloss: 'Empathetic, reliable support' },
      { key: 'brand_custom', label: 'Brand custom', gloss: 'Matches a specific brand voice' },
    ],
  },
  {
    key: 'buying_trigger',
    title: 'Buying trigger',
    why: 'Why they are shopping now — seller coaching and pipeline quality.',
    enums: [
      { key: 'ops_saturation', label: 'Ops saturation', gloss: 'Team overwhelmed by volume' },
      { key: 'coverage_gap', label: 'Coverage gap', gloss: 'Missing hours or channels' },
      { key: 'growth_ambition', label: 'Growth ambition', gloss: 'Scaling up operations' },
      { key: 'budget_cautious', label: 'Budget cautious', gloss: 'Cost-conscious evaluation' },
      { key: 'efficiency_general', label: 'Efficiency (general)', gloss: 'Streamlining without one pain point' },
    ],
  },
  {
    key: 'volume_band',
    title: 'Volume band',
    why: 'Normalizes stated WhatsApp volume for capacity, pricing, and win-rate analysis.',
    enums: [
      { key: 'lt_100_mo', label: 'Under 100/mo', gloss: 'Low message volume' },
      { key: '100_499_mo', label: '100–499/mo', gloss: 'Moderate volume' },
      { key: '500_1999_mo', label: '500–1,999/mo', gloss: 'High volume' },
      { key: '2000_plus_mo', label: '2,000+/mo', gloss: 'Enterprise-scale volume' },
      { key: 'unspecified', label: 'Unspecified', gloss: 'Volume not stated' },
    ],
  },
]
