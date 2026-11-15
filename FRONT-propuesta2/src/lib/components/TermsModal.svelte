<script lang="ts">
	let { page = false }: { page?: boolean } = $props();
	import { app } from '#lib/state.svelte';
	import Modal from './Modal.svelte';
</script>

<Modal title="Términos, privacidad y seguridad" wide {page} kicker="Términos · privacidad · seguridad" onclose={() => (app.modal = null)}>
	<p class="muted">Resumen en lenguaje claro. Última actualización: 15 de noviembre de 2026.</p>

	<section>
		<h3>Uso de la herramienta</h3>
		<p>CacaoResiliente es un prototipo gratuito del NASA Space Apps Challenge 2026 para anticipar pérdidas de cacao por El Niño.
			<b>No reemplaza la asesoría técnica:</b> valide con el INIAP, el MAG o un técnico antes de decidir siembras, inversiones, créditos o seguros.</p>
	</section>
	<section>
		<h3>Datos y estimaciones</h3>
		<ul>
			<li>Las pérdidas son estimaciones de un modelo, no mediciones en campo.</li>
			<li>Por cantón el valor es un índice heredado de su provincia; en la Amazonía es una extrapolación desde Sucumbíos.</li>
			<li>Las zonas 2050 vienen de proyecciones NASA NEX-GDDP-CMIP6 y están por validar.</li>
			<li>Las alertas las redacta una IA con cifras calculadas por el sistema: si un texto no cuadra, confíe en las cifras.</li>
		</ul>
	</section>
	<section>
		<h3>Privacidad</h3>
		<ul>
			<li><b>No hay cuentas ni roles:</b> no pedimos nombre, cédula, correo ni contraseña.</li>
			<li>Tu finca dibujada, el tema y si ocultaste paneles se guardan solo en tu navegador.</li>
			<li>Los reportes de campo y las consultas se envían por WhatsApp solo si tú lo decides; ahí aplica la política de WhatsApp (Meta).</li>
			<li>El servidor recibe datos técnicos de cada consulta (IP, hora) solo para operar y corregir errores. Sin publicidad ni rastreadores.</li>
		</ul>
	</section>
	<section>
		<h3>Seguridad</h3>
		<ul>
			<li>Las claves de la base de datos y de la IA están solo en el servidor; el navegador nunca las recibe.</li>
			<li>En producción el sitio debe servirse por HTTPS. Nunca te pediremos contraseñas, códigos ni datos bancarios.</li>
			<li>Si encuentras una falla, avísanos por WhatsApp (+593 96 421 3841) antes de publicarla.</li>
		</ul>
	</section>
	<section>
		<h3>Servicios de terceros y fuentes</h3>
		<p>Mapas: CARTO/OpenStreetMap, Sentinel-2 cloudless (EOX), AWS Terrain Tiles y NASA GIBS. Datos: NASA (GPM IMERG, MODIS, SMAP, GLDAS, SRTM, NEX-GDDP-CMIP6), ERA5-Land, NOAA CPC, FAOSTAT, INEC-ESPAC y FAO GAUL. Cite la fuente original si reutiliza los datos.</p>
	</section>
	<p class="disclaimer">Texto informativo de un prototipo; antes de un lanzamiento público conviene revisarlo con un abogado (Ley Orgánica de Protección de Datos Personales del Ecuador).</p>
</Modal>

<style>
	section { display: flex; flex-direction: column; gap: 0.35rem; }
	ul { margin: 0; padding-left: 1.15rem; display: flex; flex-direction: column; gap: 0.25rem; }
</style>
