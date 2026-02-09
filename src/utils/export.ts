export const exportCsvFile = (filename, headers, rows) => {
  if (typeof window === "undefined") return;
  const escape = (v) => {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [headers.map(escape).join(','), ...rows.map(r => r.map(escape).join(','))].join('\n');
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  setTimeout(() => { URL.revokeObjectURL(url); link.remove(); }, 100);
};

/**
 * Export a chart container DOM element as a PNG image.
 * Finds the SVG inside the container, serializes it to a canvas, then triggers download.
 * @param {HTMLElement} containerEl - DOM element containing the chart SVG
 * @param {string} [filename='chart.png'] - Download filename
 */
export const exportChartAsPng = (containerEl, filename = 'chart.png') => {
  if (!containerEl) return;
  const svgEl = containerEl.querySelector('svg');
  if (!svgEl) return;

  const clone = svgEl.cloneNode(true);
  // Ensure the SVG has explicit dimensions for canvas rendering
  const rect = svgEl.getBoundingClientRect();
  const w = Math.round(rect.width * 2); // 2x for retina
  const h = Math.round(rect.height * 2);
  clone.setAttribute('width', w);
  clone.setAttribute('height', h);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

  // Inline computed styles for CSS variables used in the chart
  const computedStyle = getComputedStyle(document.documentElement);
  const cssVars = [
    '--bg-1', '--bg-2', '--bg-3', '--bg-hover',
    '--border-1', '--border-2',
    '--text-1', '--text-2', '--text-3', '--text-4',
    '--cyan', '--blue', '--green', '--red', '--amber',
  ];
  let inlineCSS = '';
  cssVars.forEach(v => {
    const val = computedStyle.getPropertyValue(v).trim();
    if (val) inlineCSS += `${v}:${val};`;
  });
  // Prepend a style element so CSS vars resolve when rendered in canvas
  const styleEl = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  styleEl.textContent = `:root,svg{${inlineCSS}}`;
  clone.insertBefore(styleEl, clone.firstChild);

  const serialized = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);

  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    // Dark background fill
    ctx.fillStyle = computedStyle.getPropertyValue('--bg-2').trim() || '#0f172a';
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);
    URL.revokeObjectURL(url);

    canvas.toBlob((pngBlob) => {
      if (!pngBlob) return;
      const pngUrl = URL.createObjectURL(pngBlob);
      const link = document.createElement('a');
      link.href = pngUrl;
      link.download = filename;
      link.rel = 'noopener';
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      setTimeout(() => { URL.revokeObjectURL(pngUrl); link.remove(); }, 100);
    }, 'image/png');
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
};
