const nf = (o: Intl.NumberFormatOptions) => new Intl.NumberFormat('es-EC', o);
const n0 = nf({ maximumFractionDigits: 0 });
const n1 = nf({ maximumFractionDigits: 1 });
const usdC = nf({ style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 });
const usdF = nf({ style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

export const num = (v: number | null | undefined, d = 0) => (v == null ? '—' : d ? n1.format(v) : n0.format(v));
export const pct = (v: number | null | undefined) => (v == null ? '—' : `${n1.format(v)} %`);
export const usd = (v: number | null | undefined, full = false) => (v == null ? '—' : (full ? usdF : usdC).format(v));
export const signed = (v: number | null | undefined, f: (x: number) => string = (x) => n1.format(x)) =>
	v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${f(Math.abs(v))}`;

export const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

// Escala de pérdida (igual que FRONT/src/lib/design/colors.ts): 5 niveles por % de pérdida,
// semáforo IPC / SNGR en tonos tierra que combinan con la paleta y se leen sobre el mapa claro u oscuro.
export const LOSS_RAMP = ['#e8dc9a', '#d9b04f', '#c4722f', '#963a25', '#4a1a17'] as const;
export const LOSS_ON = ['#2b221c', '#2b221c', '#2b221c', '#ffffff', '#ffffff'] as const;
export const LOSS_BREAKS = [5, 15, 30, 45] as const;
export const LOSS_CLASSES = [
	{ id: 'baja', label: 'Baja', range: '0–5 %' },
	{ id: 'moderada', label: 'Moderada', range: '5–15 %' },
	{ id: 'alta', label: 'Alta', range: '15–30 %' },
	{ id: 'muy_alta', label: 'Muy alta', range: '30–45 %' },
	{ id: 'critica', label: 'Crítica', range: '> 45 %' }
] as const;
export const lossLevel = (v: number | null | undefined): number => (v == null ? -1 : v <= 5 ? 0 : v <= 15 ? 1 : v <= 30 ? 2 : v <= 45 ? 3 : 4);
export const lossColor = (v: number | null | undefined): string => (v == null ? '#8a948c' : (LOSS_RAMP[lossLevel(v)] ?? '#8a948c'));
export const lossLabel = (v: number | null | undefined): string => (v == null ? 'Sin estimación' : (LOSS_CLASSES[lossLevel(v)]?.label ?? '—'));

// Clases de 4 niveles que devuelve el backend (risk_class), por compatibilidad
export const RISK_COLORS: Record<string, string> = {
	bajo: LOSS_RAMP[0], medio: LOSS_RAMP[1], alto: LOSS_RAMP[2], muy_alto: LOSS_RAMP[3]
};
export const RISK_LABEL: Record<string, string> = { bajo: 'Bajo', medio: 'Medio', alto: 'Alto', muy_alto: 'Muy alto' };

export const ZONE_COLORS: Record<string, string> = {
	segura: '#2f7f73', manejo: '#d9b04f', transicion: '#c4722f', critica: '#963a25'
};
export const ZONE_LABEL: Record<string, string> = { segura: 'Segura', manejo: 'Manejo', transicion: 'Transición', critica: 'Crítica' };

export const PATHOGEN_LABEL: Record<string, string> = {
	monilia: 'Moniliasis', phytophthora: 'Mazorca negra', escoba_bruja: 'Escoba de bruja'
};
export const PATHOGEN_COLOR: Record<string, string> = {
	monilia: '#a99f6a', phytophthora: '#2f7f73', escoba_bruja: '#4b3a2f'
};

export const STATUS_ICON: Record<string, string> = { ok: '●', warn: '▲', bad: '✕' };

export const PRIORITY_LABEL: Record<string, string> = {
	ingreso: 'Proteger ingreso', costo: 'Bajo costo', suelo: 'Cuidar suelo', agua: 'Ahorrar agua', mano_obra: 'Poca mano de obra'
};

export const ENSO_LABEL: Record<string, string> = { nino: 'El Niño', nina: 'La Niña', neutral: 'Neutral' };
export const INTENSITY: Record<string, string> = { debil: 'débil', moderado: 'moderado', fuerte: 'fuerte', muy_fuerte: 'muy fuerte' };

export function errMsg(e: unknown) {
	const a = e as { status?: number; code?: string; message?: string };
	const map: Record<string, string> = {
		ai_not_configured: 'La IA no está configurada en el servidor (falta la API key).',
		ai_rate_limited: 'La IA está saturada, prueba en un minuto.',
		ai_no_balance: 'El proveedor de IA no tiene saldo.',
		model_not_loaded: 'El modelo ML no está cargado en el servidor.',
		adjust_out_of_limits: 'Ajustes fuera de los límites permitidos.'
	};
	if (a?.code && map[a.code]) return map[a.code];
	if (a?.status === 404) return 'Sin datos para esta consulta.';
	if (a?.status === 401) return 'Necesitas iniciar sesión.';
	if (a?.status === 403) return 'Solo administradores.';
	return a?.message ?? 'Error inesperado';
}
