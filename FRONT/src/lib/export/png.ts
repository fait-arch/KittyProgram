/** Descarga un nodo del DOM como PNG al tamaño real de la plantilla (html-to-image, MIT). */
export async function downloadNodePng(node: HTMLElement, filename: string, pixelRatio = 1) {
  const { toPng } = await import("html-to-image");
  const url = await toPng(node, {
    pixelRatio,
    cacheBust: true,
    // La vista previa está escalada con transform: se captura el nodo sin escala
    style: { transform: "none", transformOrigin: "top left", margin: "0" },
    width: node.offsetWidth,
    height: node.offsetHeight,
  });
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}
