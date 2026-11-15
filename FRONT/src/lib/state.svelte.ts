// Estado global de la app (Svelte 5 runes).
function load(k: string, d = '') {
	try { return localStorage.getItem(k) ?? d; } catch { return d; }
}
function save(k: string, v: string) {
	try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* sin storage */ }
}

export type MapMode = 'loss' | 'zones';
export type Theme = 'light' | 'dark';
export type Modal = null | 'enso' | 'method' | 'admin' | 'login';

class AppState {
	crop = $state('cacao');
	scenario = $state('nino');
	province = $state(''); // '' = todo el país
	mapMode = $state<MapMode>('loss');
	future = $state('ssp245_2050');
	showObservations = $state(true);

	selectedId = $state<string | null>(null);
	selectedName = $state('');
	point = $state<{ lat: number; lon: number } | null>(null);
	tab = $state('resumen');
	modal = $state<Modal>(null);

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
	}
	selectPoint(lat: number, lon: number) {
		this.point = { lat, lon };
		this.selectedId = null;
	}
	clear() {
		this.selectedId = null;
		this.point = null;
	}
	setSession(token: string, email: string) {
		this.token = token; this.userEmail = email;
		save('cr_token', token); save('cr_email', email);
	}
	setAdminKey(k: string) { this.adminKey = k; save('cr_admin', k); }
}

export const app = new AppState();
