// Node dimensions
export const NODE_WIDTH = 150;
export const NODE_HEIGHT = 70;

// Node styling
export const NODE_BORDER_WIDTH = 4;

// Layout spacing
export const LAYER_SPACING = 150;
export const NODE_SPACING = 20;
export const BAND_SPACING = 15;

// UI: Top margin above the ReactFlow canvas (in px)
export const FLOW_CONTAINER_MARGIN_TOP = 30;

// Visual spacing between multiple band arrows entering the same target
// Pixels between adjacent arrow entries (increase to give more space between arrows)
export const BAND_ENTRY_STAGGER_STEP = 8;
// Maximum absolute vertical offset applied at the target when staggering entries
export const BAND_ENTRY_STAGGER_CLAMP = 18;

// Configurable band colors by level and side.
// Level 1 (closest) defaults to white; then blue; then purple. Extend as needed.
export const BAND_COLORS: Record<number, { left: string; right: string }> = {
	1: { left: '#FFFFFF', right: '#FFFFFF' },
	2: { left: '#2F80ED', right: '#2F80ED' },
	3: { left: '#9B51E0', right: '#9B51E0' },
    4: { left: '#dbd81bff', right: '#dbd81bff' },
    5: { left: '#19d442ff', right: '#19d442ff' },
};

// Fallback stroke color for bands without an explicit color mapping
export const DEFAULT_BAND_COLOR = '#e0e0e0';