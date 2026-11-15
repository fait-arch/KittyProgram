<script lang="ts">
	// Menú lateral (☰): vista, filtros, herramientas, aprender y cuenta. Mismo lenguaje visual que las tarjetas.
	import { api } from '#lib/api';
	import { app, type OverlayId } from '#lib/state.svelte';
	import Icon from './Icon.svelte';
	import Segmented from './Segmented.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	let crops = $state<any[]>([]);
	let provinces = $state<any[]>([]);
	$effect(() => {
		api.crops().then((c) => (crops = c)).catch(() => {});
		api.areas({ kind: 'province' }).then((p) => (provinces = p)).catch(() => {});
	});

	const OVERLAYS: { id: OverlayId; label: string; hint: string }[] = [
		{ id: 'lluvia', label: 'Lluvia de ayer', hint: 'NASA GPM IMERG' },
		{ id: 'vegetacion', label: 'Vegetación (NDVI)', hint: 'MODIS, 8 días' },
		{ id: 'incendios', label: 'Incendios', hint: 'VIIRS / MODIS, 7 días' },
		{ id: 'temperatura', label: 'Temperatura del suelo', hint: 'MODIS, de día' },
		{ id: 'aire', label: 'Humo y polvo', hint: 'MODIS aerosoles' }
	];
	const viewOpts = [{ id: '2d', label: 'Mapa 2D' }, { id: '3d', label: 'Satélite 3D' }];

	const open = (m: typeof app.modal) => { app.modal = m; app.drawer = false; };
	const status = $derived(app.health?.status ?? '…');
	const statusColor = $derived(status === 'ok' ? 'var(--good)' : status === 'degraded' ? 'var(--warn)' : 'var(--bad)');
	function key(e: KeyboardEvent) { if (e.key === 'Escape') app.drawer = false; }
</script>

<svelte:window onkeydown={key} />
{#if app.drawer}
	<div class="scrim" onclick={() => (app.drawer = false)} role="presentation"></div>
	<aside class="drawer" aria-label="Menú">
		<header>
			<div class="brand">
				<img src="/favicon.svg" width="34" height="34" alt="" />
				<div><b>CacaoResiliente</b><small>Menú</small></div>
			</div>
			<button class="x" onclick={() => (app.drawer = false)} aria-label="Cerrar menú"><Icon name="close" /></button>
		</header>

		<div class="body">
			<section>
				<h4>Ver</h4>
				<label class="sw">
					<span class="ic"><Icon name="panel" /></span>
					<span class="tx">Panel de resumen<small>Totales y cantones más afectados</small></span>
					<input type="checkbox" checked={app.showOverview} onchange={(e) => app.setOverview(e.currentTarget.checked)} />
					<i></i>
				</label>
				<div class="field">
					<span class="ic"><Icon name={app.view === '3d' ? 'globe' : 'map'} /></span>
					<Segmented options={viewOpts} bind:value={app.view} size="sm" />
				</div>
				<label class="sw">
					<span class="ic"><Icon name="pin" /></span>
					<span class="tx">Observaciones de campo<small>Reportes de técnicos</small></span>
					<input type="checkbox" bind:checked={app.showObservations} />
					<i></i>
				</label>
				<details class="nasa">
					<summary><span class="ic"><Icon name="layers" /></span><span class="tx">Capas NASA del día<small>{Object.values(app.overlays).filter(Boolean).length || 'Ninguna'} activa(s)</small></span></summary>
					<div class="ovl">
						{#each OVERLAYS as o}
							<label class="chk"><input type="checkbox" bind:checked={app.overlays[o.id]} /> {o.label} <small>{o.hint}</small></label>
						{/each}
					</div>
				</details>
			</section>

			<section>
				<h4>Filtrar</h4>
				<div class="grid2">
					<label class="sel">Cultivo
						<select bind:value={app.crop}>{#each crops as c}<option value={c.id}>{c.name_es}</option>{/each}</select>
					</label>
					<label class="sel">Provincia
						<select bind:value={app.province}>
							<option value="">Todo el país</option>
							{#each provinces as p}<option value={p.name}>{p.name}</option>{/each}
						</select>
					</label>
				</div>
			</section>

			<section>
				<h4>Herramientas</h4>
				<button class="item" onclick={() => open('alerts')}><span class="ic accent"><Icon name="bell" /></span><span class="tx">Alertas<small>Avisos por provincia escritos por la IA</small></span></button>
				<button class="item" onclick={() => { app.startFinca(); if (page.url.pathname !== '/') goto('/'); }}><span class="ic accent"><Icon name="farm" /></span><span class="tx">Mi finca<small>Dibuja tu lote y calcula su pérdida</small></span></button>
				<button class="item" onclick={() => open('export')}><span class="ic accent"><Icon name="download" /></span><span class="tx">Exportar para QGIS<small>GeoJSON + estilo, SLD, CSV o PDF</small></span></button>
				<button class="item" onclick={() => open('share')}><span class="ic accent"><Icon name="share" /></span><span class="tx">Compartir<small>Enlace, WhatsApp o ficha impresa</small></span></button>
			</section>

			<section>
				<h4>Aprender</h4>
				<button class="item" onclick={() => open('enso')}><span class="ic"><Icon name="wave" /></span><span class="tx">El Niño: historia y eventos</span></button>
				<button class="item" onclick={() => open('method')}><span class="ic"><Icon name="book" /></span><span class="tx">Metodología y fuentes</span></button>
				<button class="item" onclick={() => open('terms')}><span class="ic"><Icon name="shield" /></span><span class="tx">Términos, privacidad y seguridad</span></button>
			</section>

		</div>

		<footer>
			<span class="dot" style="background:{statusColor}"></span>
			API {status === 'ok' ? 'en línea' : status === 'degraded' ? 'con avisos' : status} · datos {app.health?.data_source ?? '?'}
		</footer>
	</aside>
{/if}

<style>
	.scrim { position: fixed; inset: 0; background: rgb(20 26 22 / 0.35); backdrop-filter: blur(2px); z-index: 40; animation: fade 0.2s; }
	@keyframes fade { from { opacity: 0; } }
	.drawer {
		position: fixed; top: 0; right: 0; bottom: 0; z-index: 41; width: min(360px, 92vw);
		background: var(--surface); border-left: 1px solid var(--line); box-shadow: var(--shadow);
		display: flex; flex-direction: column; animation: slide 0.25s ease-out;
	}
	@keyframes slide { from { transform: translateX(24px); opacity: 0; } }
	header { display: flex; justify-content: space-between; align-items: center; padding: 0.9rem 1rem; background: var(--bar); color: #fff; }
	.brand { display: flex; gap: 0.6rem; align-items: center; }
	.brand img { border-radius: 9px; }
	.brand div { display: flex; flex-direction: column; line-height: 1.15; }
	.brand b { font-family: var(--display); font-size: 1.05rem; }
	.brand small { color: rgb(255 255 255 / 0.7); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }
	.x { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 999px; border: 1px solid rgb(255 255 255 / 0.2); background: rgb(255 255 255 / 0.08); color: #fff; cursor: pointer; }
	.x:hover { background: rgb(255 255 255 / 0.16); }
	.body { flex: 1; overflow: auto; padding: 0.6rem 0.9rem 1rem; display: flex; flex-direction: column; gap: 0.4rem; }
	section { display: flex; flex-direction: column; gap: 0.15rem; padding: 0.6rem 0; border-bottom: 1px solid var(--line); }
	section:last-child { border-bottom: 0; }
	h4 { margin: 0 0 0.3rem 0.35rem; font: 600 0.7rem/1 var(--font); text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-2); }
	.ic { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; background: var(--surface-2); color: var(--ink-2); flex-shrink: 0; }
	.ic.accent { background: var(--accent-soft); color: var(--accent); }
	.tx { display: flex; flex-direction: column; text-align: left; flex: 1; min-width: 0; font-weight: 500; }
	.tx small { font-weight: 400; color: var(--ink-2); font-size: 0.78rem; }
	.item, .sw, .field, .nasa summary { display: flex; align-items: center; gap: 0.7rem; padding: 0.45rem 0.35rem; border-radius: 12px; }
	.item { border: 0; background: none; cursor: pointer; width: 100%; }
	.item:hover, .sw:hover, .nasa summary:hover { background: var(--surface-2); }
	.sw { cursor: pointer; position: relative; }
	.sw input { position: absolute; opacity: 0; pointer-events: none; }
	.sw i { width: 38px; height: 22px; border-radius: 999px; background: var(--line); position: relative; flex-shrink: 0; transition: background 0.2s; }
	.sw i::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; box-shadow: 0 1px 2px rgb(0 0 0 / 0.3); transition: transform 0.2s; }
	.sw input:checked + i { background: var(--accent); }
	.sw input:checked + i::after { transform: translateX(16px); }
	.sw input:focus-visible + i { outline: 2px solid var(--accent); outline-offset: 2px; }
	.nasa summary { cursor: pointer; list-style: none; }
	.nasa summary::-webkit-details-marker { display: none; }
	.ovl { display: flex; flex-direction: column; gap: 0.35rem; padding: 0.3rem 0.4rem 0.4rem 3.2rem; }
	.chk { display: flex; gap: 0.45rem; align-items: baseline; font-size: 0.86rem; cursor: pointer; flex-wrap: wrap; }
	.chk input { accent-color: var(--accent); }
	.chk small { color: var(--ink-2); font-size: 0.74rem; }
	.grid2 { padding: 0 0.35rem; }
	.sel { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.76rem; color: var(--ink-2); }
	.sel select { color: var(--ink); width: 100%; }
	footer { display: flex; align-items: center; gap: 0.5rem; padding: 0.7rem 1rem; border-top: 1px solid var(--line); font-size: 0.78rem; color: var(--ink-2); }
	.dot { width: 8px; height: 8px; border-radius: 50%; }
</style>
