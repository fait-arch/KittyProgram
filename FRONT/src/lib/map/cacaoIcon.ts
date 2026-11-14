/**
 * Ícono de mazorca de cacao dibujado en un canvas (sin archivos externos) para MapLibre.
 * Se genera uno por color de zona: el color dice qué tan óptima es la zona para sembrar.
 */
export function cacaoIcon(fill: string, size = 48): ImageData {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d")!;
  const s = size / 48;
  g.scale(s, s);
  g.translate(24, 24);
  g.rotate(-0.45);
  // sombra
  g.shadowColor = "rgba(0,0,0,.45)";
  g.shadowBlur = 4;
  g.shadowOffsetY = 1.5;
  // mazorca
  g.beginPath();
  g.moveTo(0, -20);
  g.bezierCurveTo(11, -15, 13, 12, 0, 20);
  g.bezierCurveTo(-13, 12, -11, -15, 0, -20);
  g.closePath();
  g.fillStyle = fill;
  g.fill();
  g.shadowColor = "transparent";
  g.lineWidth = 2.5;
  g.strokeStyle = "#ffffff";
  g.stroke();
  // surcos de la mazorca
  g.lineWidth = 1.4;
  g.strokeStyle = "rgba(0,0,0,.28)";
  for (const k of [-5, 0, 5]) {
    g.beginPath();
    g.moveTo(k * 0.6, -17);
    g.quadraticCurveTo(k * 1.25, 0, k * 0.6, 17);
    g.stroke();
  }
  // pedúnculo
  g.beginPath();
  g.moveTo(0, -20);
  g.lineTo(0, -24);
  g.lineWidth = 2.5;
  g.strokeStyle = "#5b3a1e";
  g.stroke();
  return g.getImageData(0, 0, size, size);
}

/** Patrón rayado del nivel Crítico para fill-pattern (igual que QGIS y el mapa 2D) */
export function hatchPattern(size = 12): ImageData {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d")!;
  g.fillStyle = "#640000";
  g.fillRect(0, 0, size, size);
  g.strokeStyle = "rgba(255,255,255,.7)";
  g.lineWidth = 2;
  for (const o of [-size, 0, size]) {
    g.beginPath();
    g.moveTo(o, size);
    g.lineTo(o + size, 0);
    g.stroke();
  }
  return g.getImageData(0, 0, size, size);
}
