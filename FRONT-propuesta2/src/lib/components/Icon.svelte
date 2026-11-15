<script lang="ts">
	// Íconos de línea (24×24, trazo 2) para menús y botones. Sin dependencias.
	let { name, size = 20 }: { name: string; size?: number } = $props();
	const P: Record<string, string> = {
		menu: 'M4 6h16M4 12h16M4 18h16',
		close: 'M6 6l12 12M18 6L6 18',
		panel: 'M4 5h16v14H4zM9 5v14',
		map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14',
		globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18',
		layers: 'M12 3 2 8l10 5 10-5-10-5zM2 13l10 5 10-5',
		bell: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4l2-2zM10 20a2 2 0 0 0 4 0',
		farm: 'M3 20h18M5 20V10l7-5 7 5v10M9 20v-6h6v6',
		download: 'M12 3v12m0 0-4-4m4 4 4-4M4 17v3h16v-3',
		share: 'M18 8a3 3 0 1 0-3-3M6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8.6 13.5l6.8 4M15.4 6.5l-6.8 4',
		wave: 'M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0M2 18c2-3 4-3 6 0s4 3 6 0 4-3 6 0',
		book: 'M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2V5zM4 19a2 2 0 0 1 2-2h14',
		shield: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z',
		user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
		gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 1.2 14H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 7a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 1.2V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 22.8 10H23a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
		pin: 'M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12zM12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
		eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
		chat: 'M4 4h16v12H8l-4 4V4z',
		link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
		print: 'M6 9V3h12v6M6 18H4v-7h16v7h-2M8 14h8v7H8z',
		undo: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3',
		check: 'M4 12l5 5L20 6',
		gps: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v3M12 19v3M2 12h3M19 12h3',
		trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
		chevL: 'M15 18l-6-6 6-6',
		chevR: 'M9 18l6-6-6-6',
		dash: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
		compare: 'M4 5h7v14H4zM13 5h7v14h-7zM7.5 9v6M16.5 11v4',
		spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6'
	};
</script>

<svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
	<path d={P[name] ?? ''} />
</svg>
