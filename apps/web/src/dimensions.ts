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
    title: 'Trabajo principal',
    why: 'Asocia cada nota de descubrimiento con la capacidad del bot que el lead desea — empaquetado para Ventas, demanda de funcionalidades para Producto.',
    enums: [
      { key: 'scheduling_booking', label: 'Agendamiento y reservas', gloss: 'Citas y reservas' },
      { key: 'catalog_guided_selling', label: 'Catálogo y venta guiada', gloss: 'Descubrimiento de productos y recomendaciones' },
      { key: 'quoting_pricing', label: 'Cotización y precios', gloss: 'Estimaciones y cotizaciones de precio' },
      { key: 'order_taking', label: 'Toma de pedidos', gloss: 'Captura y envío de pedidos' },
      { key: 'claims_intake', label: 'Ingreso de reclamos', gloss: 'Registro y priorización de reclamos' },
      { key: 'shipment_tracking', label: 'Seguimiento de envíos', gloss: 'Estado de entrega y logística' },
      { key: 'lead_qualification', label: 'Calificación de leads', gloss: 'Filtrado y derivación de leads' },
      { key: 'faq_education', label: 'Preguntas frecuentes y educación', gloss: 'Responder preguntas comunes' },
    ],
  },
  {
    key: 'handoff_topology',
    title: 'Topología de transferencia',
    why: 'Cómo debe involucrar el bot a las personas — define la implementación y la tasa de conversión.',
    enums: [
      { key: 'bot_only_implied', label: 'Solo bot (implícito)', gloss: 'Totalmente automatizado, sin intervención humana' },
      { key: 'generic_human_handoff', label: 'Transferencia genérica a humano', gloss: 'Escalar a cualquier agente disponible' },
      { key: 'book_specialist', label: 'Agendar con especialista', gloss: 'Agendar tiempo con un experto' },
      { key: 'role_based_routing', label: 'Derivación por rol', gloss: 'Derivar al equipo o rol correcto' },
    ],
  },
  {
    key: 'system_gravity',
    title: 'Gravedad del sistema',
    why: 'Qué tan atado está a sistemas existentes — determina la carga de ingeniería de soluciones y el costo de implementación.',
    enums: [
      { key: 'standalone_ok', label: 'Independiente está bien', gloss: 'Funciona sin integraciones' },
      { key: 'named_system_desired', label: 'Sistema específico deseado', gloss: 'Prefiere una plataforma específica' },
      { key: 'must_integrate', label: 'Debe integrarse', gloss: 'Requiere una conexión profunda con el sistema' },
    ],
  },
    {
      key: 'trust_surface',
    title: 'Superficie de confianza',
    why: 'Sensibilidad del dominio — define el nivel de cumplimiento y quién debe aprobar.',
    enums: [
      { key: 'standard', label: 'Estándar', gloss: 'Negocio general, baja sensibilidad' },
      { key: 'health_sensitive', label: 'Sensible en salud', gloss: 'Contexto médico o de bienestar' },
      { key: 'regulated_advice_boundary', label: 'Límite de asesoría regulada', gloss: 'Límites legales, financieros o de cumplimiento' },
      { key: 'discretion_prestige', label: 'Discreción y prestigio', gloss: 'Alto contacto, confidencial, de lujo' },
    ],
  },
  {
    key: 'buying_trigger',
    title: 'Motivo de compra',
    why: 'Por qué están comprando ahora — orienta el coaching de vendedores y la calidad del pipeline.',
    enums: [
      { key: 'ops_saturation', label: 'Saturación operativa', gloss: 'Equipo sobrepasado por el volumen' },
      { key: 'coverage_gap', label: 'Brecha de cobertura', gloss: 'Faltan horarios o canales' },
      { key: 'growth_ambition', label: 'Ambición de crecimiento', gloss: 'Escalando operaciones' },
      { key: 'budget_cautious', label: 'Cauteloso con el presupuesto', gloss: 'Evaluación centrada en el costo' },
      { key: 'efficiency_general', label: 'Eficiencia (general)', gloss: 'Optimización sin un dolor puntual' },
    ],
  },
  {
    key: 'volume_band',
    title: 'Banda de volumen',
    why: 'Normaliza el volumen de WhatsApp declarado para el análisis de capacidad, precios y tasa de conversión.',
    enums: [
      { key: 'lt_100_mo', label: 'Menos de 100/mes', gloss: 'Volumen de mensajes bajo' },
      { key: '100_499_mo', label: '100–499/mes', gloss: 'Volumen moderado' },
      { key: '500_1999_mo', label: '500–1.999/mes', gloss: 'Volumen alto' },
      { key: '2000_plus_mo', label: '2.000+/mes', gloss: 'Volumen de escala empresarial' },
      { key: 'unspecified', label: 'No especificado', gloss: 'Volumen no declarado' },
    ],
  },
]
