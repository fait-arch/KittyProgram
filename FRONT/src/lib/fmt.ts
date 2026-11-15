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

export const RISK_COLORS: Record<string, string> = {
	bajo: '#6f9b62', medio: '#c2a05a', alto: '#8b5e3c', muy_alto: '#6e1f1c'
};
export const RISK_LABEL: Record<string, string> = { bajo: 'Bajo', medio: 'Medio', alto: 'Alto', muy_alto: 'Muy alto' };

export const ZONE_COLORS: Record<string, string> = {
	segura: '#3f7d4e', manejo: '#c2a05a', transicion: '#6c7a89', critica: '#8f2d2a'
};
export const ZONE_LABEL: Record<string, string> = { segura: 'Segura', manejo: 'Manejo', transicion: 'Transición', critica: 'Crítica' };

export const PATHOGEN_LABEL: Record<string, string> = {
	monilia: 'Moniliasis', phytophthora: 'Mazorca negra', escoba_bruja: 'Escoba de bruja'
};
export const PATHOGEN_COLOR: Record<string, string> = {
	monilia: '#8b5e3c', phytophthora: '#4d7484', escoba_bruja: '#3f7d4e'
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
