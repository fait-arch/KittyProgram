// Cliente de la API CacaoResiliente — cubre las 37 rutas de docs/backend/02-endpoints.md.
// Cada función = un endpoint. Mantener en sync con el contrato.

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
const V1 = `${BASE}/api/v1`;

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string
	) {
		super(message);
	}
}

type Q = Record<string, string | number | boolean | null | undefined>;

function qs(q?: Q) {
	if (!q) return '';
	const p = new URLSearchParams();
	for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
	const s = p.toString();
	return s ? `?${s}` : '';
}


async function req<T>(url: string, init: RequestInit & { token?: string; adminKey?: string } = {}): Promise<T> {
	const headers: Record<string, string> = { Accept: 'application/json' };
	if (init.body) headers['Content-Type'] = 'application/json';
	if (init.token) headers.Authorization = `Bearer ${init.token}`;
	if (init.adminKey) headers['X-Admin-Key'] = init.adminKey;
	const res = await fetch(url, { ...init, headers });
	const text = await res.text();
	let body: any = null;
	try { body = text ? JSON.parse(text) : null; } catch { body = text; }
	if (!res.ok) {
		// Backend: { detail, code } · FastAPI validación: { detail: [{msg, loc}] }
		const d = body?.detail ?? body;
		const code = body?.code ?? `http_${res.status}`;
		const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join('; ') : JSON.stringify(d);
		throw new ApiError(res.status, code, msg);
	}
	return body as T;
}

const get = <T = any>(path: string, q?: Q) => req<T>(`${V1}${path}${qs(q)}`);
const post = <T = any>(path: string, body: unknown, extra: { token?: string; adminKey?: string } = {}) =>
	req<T>(`${V1}${path}`, { method: 'POST', body: JSON.stringify(body ?? {}), ...extra });

export const api = {
	// ── Sistema ───────────────────────────────
	health: () => req<any>(`${BASE}/health`),
	meta: (crop = 'cacao') => get('/meta', { crop }),

	// ── Catálogos ─────────────────────────────
	crops: (region?: string) => get<any[]>('/crops', { region }),
	requirements: (crop: string) => get(`/crops/${crop}/requirements`),
	pathogens: (crop: string) => get<any[]>(`/crops/${crop}/pathogens`),
	phenology: (crop: string, region?: string) => get<any[]>(`/crops/${crop}/phenology`, { region }),
	scenarios: (crop = 'cacao', phase?: number) => get<any[]>('/scenarios', { crop, phase }),
	strategyCatalog: () => get<any[]>('/strategies'),

	// ── El Niño ───────────────────────────────
	ensoCurrent: () => get('/enso/current'),
	ensoHistory: (from?: string, to?: string, index = 'oni,nino12_anom') => get('/enso/history', { index, from, to }),
	ensoEvents: (phase?: 'nino' | 'nina', from?: number) => get<any[]>('/enso/events', { phase, from }),
	ensoYears: () => get<any[]>('/enso/years'),

	// ── Territorio ────────────────────────────
	areas: (q: { kind?: string; province?: string; has_crop?: string } = {}) => get<any[]>('/areas', q),
	areasGeojson: (q: { kind?: string; province?: string } = {}) => get('/areas/geojson', q),
	lookup: (lat: number, lon: number) => get('/areas/lookup', { lat, lon }),
	area: (id: string, crop = 'cacao') => get(`/areas/${id}`, { crop }),

	// ── Clima y riesgo por área ───────────────
	climate: (id: string, scenario: string, variables?: string) => get(`/areas/${id}/climate`, { scenario, variables }),
	series: (id: string, q: { variables?: string; from?: string; to?: string; anomaly?: boolean } = {}) =>
		get(`/areas/${id}/series`, q),
	hazards: (id: string, from?: string, to?: string) => get<any[]>(`/areas/${id}/hazards`, { from, to }),
	risk: (id: string, scenario: string, crop = 'cacao') => get(`/areas/${id}/risk`, { scenario, crop }),
	riskHistory: (id: string, pathogen?: string, from?: string, to?: string) =>
		get<any[]>(`/areas/${id}/risk/history`, { pathogen, from, to }),
	suitability: (id: string, crop = 'cacao', scenarios?: string) => get<any[]>(`/areas/${id}/suitability`, { crop, scenarios }),

	// ── Pérdidas ──────────────────────────────
	losses: (q: { scenario: string; kind?: string; province?: string; crop?: string }) => get('/losses', q),
	lossesGeojson: (q: { scenario: string; kind?: string; province?: string; crop?: string }) => get('/losses/geojson', q),
	lossesSummary: (q: { scenario: string; province?: string; crop?: string; vs?: string }) => get('/losses/summary', q),
	detail: (id: string, scenario: string, crop = 'cacao') => get(`/areas/${id}/detail`, { scenario, crop }),

	// ── Recomendaciones ───────────────────────
	strategies: (id: string, scenario: string, crop = 'cacao', priorities?: string) =>
		get(`/areas/${id}/strategies`, { scenario, crop, priorities }),
	insights: (id: string, scenario: string, crop = 'cacao', priorities?: string) =>
		get(`/areas/${id}/insights`, { scenario, crop, priorities }),
	ask: (id: string, body: { question: string; scenario: string; crop?: string; history?: { role: string; content: string }[] }) =>
		post(`/areas/${id}/ask`, body),
	predict: (body: { area_id: string; crop?: string; base_scenario: string; adjust: Record<string, number> }) =>
		post('/predict', body),

	// ── Fase 2 ────────────────────────────────
	compare: (area_id: string, scenarios: string, crop = 'cacao') => get('/compare', { area_id, scenarios, crop }),
	zones: (future: string, crop = 'cacao', province?: string) => get('/zones', { future, crop, province }),

	// ── Punto libre ───────────────────────────
	pointClimate: (lat: number, lon: number, crop = 'cacao') => get('/point/climate', { lat, lon, crop }),

	// ── Campo ─────────────────────────────────
	observations: (q: { area_id?: string; pathogen?: string; source?: string; limit?: number } = {}) =>
		get<any[]>('/observations', q),
	createObservation: (body: Record<string, unknown>, token: string) => post('/observations', body, { token }),

	// ── Admin ─────────────────────────────────
	adminCacheClear: (auth: { adminKey?: string; token?: string }) => post('/admin/cache/clear', {}, auth),
	adminModelReload: (auth: { adminKey?: string; token?: string }) => post('/admin/model/reload', {}, auth)
};

// ── Supabase Auth (REST, sin SDK) para POST /observations ──
const SB_URL = (import.meta.env.VITE_SUPABASE_URL ?? '').replace(/\/$/, '');
const SB_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';
export const supabaseConfigured = Boolean(SB_URL && SB_KEY);

export async function supabaseLogin(email: string, password: string): Promise<{ token: string; email: string }> {
	const res = await fetch(`${SB_URL}/auth/v1/token?grant_type=password`, {
		method: 'POST',
		headers: { apikey: SB_KEY, 'Content-Type': 'application/json' },
		body: JSON.stringify({ email, password })
	});
	const b = await res.json();
	if (!res.ok) throw new Error(b?.error_description ?? b?.msg ?? 'No se pudo iniciar sesión');
	return { token: b.access_token, email: b.user?.email ?? email };
}
