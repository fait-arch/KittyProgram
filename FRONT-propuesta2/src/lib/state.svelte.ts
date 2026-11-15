// Estado global de la app (Svelte 5 runes).
function load(k: string, d = '') {
	try { return localStorage.getItem(k) ?? d; } catch { return d; }
}
function save(k: string, v: string) {
	try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* sin storage */ }
}

export type MapMode = 'loss' | 'zones';
export type Theme = 'light' | 'dark';
export type Modal = null | 'enso' | 'method' | 'admin' | 'login' | 'alerts' | 'export' | 'share' | 'terms';
export type View = '2d' | '3d';
export type OverlayId = 'lluvia' | 'vegetacion' | 'incendios' | 'temperatura' | 'aire';
export type LonLat = [number, number];
export type Finca = { points: LonLat[]; ha: number; center: LonLat; cantonId: string | null; cantonName: string; name?: string };

class AppState {
	crop = $state('cacao');
	scenario = $state('actual'); // temporada en curso (Ecuador está con El Niño)
	province = $state(''); // '' = todo el país
	mapMode = $state<MapMode>('loss');
	future = $state('ssp245_2050');
	showObservations = $state(true);

	selectedId = $state<string | null>(null);
	selectedName = $state('');
	point = $state<{ lat: number; lon: number } | null>(null);
	tab = $state('resumen');
	modal = $state<Modal>(null);
	/** Menú lateral (☰) */
	drawer = $state(false);
	health = $state<any>(null);

	// ── Vista (se recuerda en el navegador) ──
	showOverview = $state(load('cr_ov', '1') === '1');
	#view = $state<View>(load('cr_view') === '3d' ? '3d' : '2d');
	get view(): View { return this.#view; }
	set view(v: View) { this.#view = v; save('cr_view', v); }
	// Opciones del mapa 3D (panel «Capas»)
	base3d = $state<'satelite' | 'predeterminado' | 'hidrografico' | 'nasa' | 'bluemarble'>('satelite');
	/** Tipo de mapa en 2D: 'tema' = claro/oscuro según el tema (CARTO), o cualquiera de los del 3D en plano */
	base2d = $state<'tema' | 'satelite' | 'predeterminado' | 'hidrografico' | 'nasa' | 'bluemarble'>('tema');
	globe = $state(true);
	labels = $state(true);
	terrain = $state(true);
	cacaoIcons = $state(true);
	/** Provincias en relieve: altura = % de pérdida del escenario */
	prov3d = $state(false);
	measuring = $state(false);
	measure = $state<LonLat[]>([]);
	overlays = $state<Record<OverlayId, boolean>>({ lluvia: false, vegetacion: false, incendios: false, temperatura: false, aire: false });

	// ── Mi finca ──
	fincaMode = $state(false);           // dibujando: cada clic en el mapa agrega una esquina
	draft = $state<LonLat[]>([]);
	finca = $state<Finca | null>(null);
	setOverview(v: boolean) { this.showOverview = v; save('cr_ov', v ? '1' : '0'); }
	setView(v: View) { this.view = v; }

	// prioridades del agricultor (0–5) → ?priorities=ingreso:5,costo:4
	priorities = $state<Record<string, number>>({ ingreso: 3, costo: 3, suelo: 0, agua: 0, mano_obra: 0 });

	token = $state(load('cr_token'));
	userEmail = $state(load('cr_email'));
	adminKey = $state(load('cr_admin'));
	theme = $state<Theme>(load('cr_theme') === 'dark' ? 'dark' : 'light');

	constructor() { this.applyTheme(); }
	toggleTheme() {
		this.theme = this.theme === 'dark' ? 'light' : 'dark';
		save('cr_theme', this.theme);
		this.applyTheme();
	}
	private applyTheme() {
		if (typeof document !== 'undefined') document.documentElement.dataset.theme = this.theme;
	}

	/** Contador que se incrementa tras /admin/cache/clear para forzar recargas. */
	refresh = $state(0);

	get prioritiesParam() {
		return Object.entries(this.priorities).filter(([, v]) => v > 0).map(([k, v]) => `${k}:${v}`).join(',') || undefined;
	}

	select(id: string, name = '') {
		this.selectedId = id;
		this.selectedName = name;
		this.point = null;
		this.finca = null;
	}
	selectPoint(lat: number, lon: number) {
		this.point = { lat, lon };
		this.selectedId = null;
		this.finca = null;
	}
	clear() {
		this.selectedId = null;
		this.point = null;
		this.finca = null;
	}
	startFinca() {
		this.clear();
		this.draft = [];
		this.fincaMode = true;
		this.drawer = false;
	}

	/** Estado ↔ URL: un enlace abre el mismo mapa (escenario, cantón, capa, vista, provincia). */
	fromUrl() {
		if (typeof location === 'undefined') return;
		const q = new URLSearchParams(location.search);
		const sc = q.get('escenario'); if (sc) this.scenario = sc;
		const c = q.get('canton'); if (c) { this.selectedId = c; this.selectedName = q.get('nombre') ?? ''; }
		const pr = q.get('provincia'); if (pr) this.province = pr;
		if (q.get('capa') === 'zonas') this.mapMode = 'zones';
		const f = q.get('futuro'); if (f) this.future = f;
		const v = q.get('vista'); if (v === '3d' || v === '2d') this.view = v;
		const t = q.get('pestana'); if (t) this.tab = t;
	}
	get url() {
		const q = new URLSearchParams();
		q.set('escenario', this.scenario);
		if (this.selectedId) { q.set('canton', this.selectedId); if (this.selectedName) q.set('nombre', this.selectedName); if (this.tab !== 'resumen') q.set('pestana', this.tab); }
		if (this.province) q.set('provincia', this.province);
		if (this.mapMode === 'zones') { q.set('capa', 'zonas'); q.set('futuro', this.future); }
		if (this.view === '3d') q.set('vista', '3d');
		return `${location.origin}${location.pathname}?${q}`;
	}
	setSession(token: string, email: string) {
		this.token = token; this.userEmail = email;
		save('cr_token', token); save('cr_email', email);
	}
	setAdminKey(k: string) { this.adminKey = k; save('cr_admin', k); }
}

export const app = new AppState();
