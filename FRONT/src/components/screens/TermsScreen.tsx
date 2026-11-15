"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "@/components/atoms/Icon";

const UPDATED = "14 de noviembre de 2026";

function Section({ id, icon, title, children }: { id: string; icon: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="flex scroll-mt-4 flex-col gap-3 rounded-lg bg-surface-high p-5 sm:p-6">
      <h2 className="flex items-center gap-2 font-display text-lg font-bold sm:text-xl">
        <Icon name={icon} className="text-primary" />
        {title}
      </h2>
      <div className="flex flex-col gap-2 text-[15px] leading-[23px] text-on-surface">{children}</div>
    </section>
  );
}

const TOC = [
  ["uso", "Uso de la herramienta"],
  ["datos", "Datos y estimaciones"],
  ["privacidad", "Privacidad"],
  ["seguridad", "Seguridad"],
  ["terceros", "Servicios de terceros"],
  ["fuentes", "Fuentes y licencias"],
  ["contacto", "Contacto y cambios"],
] as const;

/** Pantalla · términos de uso, privacidad y seguridad. */
export function TermsScreen() {
  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-6 px-4 py-6 sm:gap-8 sm:py-8 lg:px-8">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Términos · privacidad · seguridad</span>
        <h1 className="font-display text-[26px] leading-8 font-extrabold sm:text-[32px] sm:leading-10">Cómo usar CacaoResiliente con confianza</h1>
        <p className="text-base leading-6 text-on-surface-variant">
          Resumen en lenguaje claro de qué hace la herramienta, qué datos usa y cómo protegemos su información. Última actualización: {UPDATED}.
        </p>
      </header>

      <nav aria-label="Contenido" className="flex flex-wrap gap-2">
        {TOC.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="rounded-full border border-outline-variant px-3 py-1.5 text-sm text-on-surface-variant hover:bg-surface-high hover:text-on-surface">
            {label}
          </a>
        ))}
      </nav>

      <Section id="uso" icon="gavel" title="Uso de la herramienta">
        <p>
          CacaoResiliente es un prototipo creado para el NASA Space Apps Challenge 2026. Es gratuito y de uso informativo: ayuda a
          productores, técnicos y autoridades a anticipar pérdidas de cacao asociadas a El Niño.
        </p>
        <p>
          <b>No reemplaza la asesoría técnica.</b> Antes de tomar decisiones de siembra, inversión, crédito o seguro, valide la
          información con el INIAP, el MAG o un técnico de confianza. Al usar la herramienta usted acepta que las decisiones son suyas.
        </p>
        <p>No intente sobrecargar el servicio, extraer datos de forma masiva ni usarlo para fines ilegales.</p>
      </Section>

      <Section id="datos" icon="monitoring" title="Datos y estimaciones">
        <ul className="list-disc pl-5">
          <li>Las pérdidas son <b>estimaciones de un modelo</b>, no mediciones en campo. Pueden tener errores.</li>
          <li>Por cantón, el valor es un índice heredado de su provincia: el mapa lo marca como «Estimación por zona».</li>
          <li>Las zonas 2050 vienen de proyecciones climáticas de la NASA (NEX-GDDP-CMIP6) y están marcadas «por validar».</li>
          <li>Las alertas en lenguaje natural las redacta una inteligencia artificial a partir de cifras calculadas por el sistema. Si un texto no cuadra con las cifras, confíe en las cifras y repórtelo.</li>
        </ul>
        <p className="text-sm text-on-surface-variant">
          Detalles del cálculo y la validación del modelo en <Link href="/metodologia" className="font-semibold text-link underline underline-offset-2">Metodología</Link>.
        </p>
      </Section>

      <Section id="privacidad" icon="lock" title="Privacidad">
        <ul className="list-disc pl-5">
          <li><b>No pedimos cuenta, nombre, cédula ni correo.</b> La herramienta funciona sin registrarse.</li>
          <li>Lo que dibuja en «Mi finca» y lo que guarda para usar sin conexión se queda <b>en su propio dispositivo</b> (almacenamiento del navegador). Puede borrarlo desde la app o limpiando los datos del sitio.</li>
          <li>Recordamos su tema (claro u oscuro) y si plegó los paneles, también solo en su navegador.</li>
          <li>Para responder cada consulta, el servidor recibe datos técnicos de la solicitud (dirección IP, hora, página pedida). Se usan solo para operar el servicio y corregir errores; no se venden ni se usan para publicidad.</li>
          <li>No usamos cookies de publicidad ni rastreadores de terceros.</li>
        </ul>
      </Section>

      <Section id="seguridad" icon="shield" title="Seguridad">
        <ul className="list-disc pl-5">
          <li>Las claves de la base de datos y de los servicios de IA viven <b>solo en el servidor</b>; su navegador nunca las recibe.</li>
          <li>El sitio envía cabeceras de seguridad: bloquea que otras páginas lo incrusten (protección contra «clickjacking»), impide que el navegador adivine tipos de archivo y limita los permisos del dispositivo a la ubicación, que solo se usa si usted la activa.</li>
          <li>En producción el sitio debe servirse por HTTPS (conexión cifrada). Si ve una advertencia de certificado, no continúe.</li>
          <li>Nunca le pediremos contraseñas, códigos ni datos bancarios, ni por la app ni por WhatsApp.</li>
          <li>Si encuentra una falla de seguridad, avísenos por el canal de contacto antes de publicarla, para corregirla.</li>
        </ul>
      </Section>

      <Section id="terceros" icon="public" title="Servicios de terceros">
        <ul className="list-disc pl-5">
          <li><b>WhatsApp:</b> el botón «Asesoría» abre WhatsApp con un mensaje prellenado sobre lo que consultó. Usted decide si lo envía; desde ese momento aplica la política de privacidad de WhatsApp (Meta).</li>
          <li><b>Mapas:</b> los mapas de fondo, el satélite y el relieve se descargan de proveedores externos (NASA GIBS, EOX Sentinel-2, OpenFreeMap, AWS Terrain Tiles), y los íconos y letras desde Google Fonts, que pueden ver su dirección IP como en cualquier página con mapas.</li>
          <li><b>Inteligencia artificial:</b> para redactar alertas y respuestas, el servidor envía cifras agregadas por provincia al proveedor de IA. No se envían datos personales.</li>
        </ul>
      </Section>

      <Section id="fuentes" icon="database" title="Fuentes y licencias">
        <p>
          NASA (GPM IMERG, MODIS, SMAP, GLDAS, SRTM, NEX-GDDP-CMIP6), Copernicus ERA5-Land, NOAA CPC, FAOSTAT, INEC-ESPAC y FAO GAUL
          para los límites. Cada fuente mantiene su propia licencia; cite a la fuente original si reutiliza los datos exportados.
        </p>
      </Section>

      <Section id="contacto" icon="support_agent" title="Contacto y cambios">
        <p>
          Dudas, errores o reportes de seguridad: WhatsApp <a href="https://wa.me/593964213841" target="_blank" rel="noopener noreferrer" className="font-semibold text-link underline underline-offset-2">+593 96 421 3841</a>.
        </p>
        <p>Si cambiamos estos términos, actualizaremos la fecha de arriba. Seguir usando la herramienta implica aceptar la versión vigente.</p>
      </Section>

      <p className="text-xs leading-[18px] text-on-surface-variant">
        Texto informativo de un prototipo. No constituye asesoría legal; antes de un lanzamiento público conviene revisarlo con un abogado
        (en Ecuador aplica la Ley Orgánica de Protección de Datos Personales).
      </p>
    </div>
  );
}
