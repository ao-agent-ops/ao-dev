// Configuration utilities for telemetry
export interface TelemetryConfig {
  collectTelemetry: boolean;
  supabaseUrl: string;
  supabaseKey: string;
  userId: string;
}

declare const vscode: any;

/**
 * Get telemetry configuration from config (via window globals set by extension)
 */
export const getTelemetryConfig = (): Partial<TelemetryConfig> => {
  console.log('🔍 Getting telemetry config...');
  
  // Try to get from window global variables (set by extension)
  const config: Partial<TelemetryConfig> = {};

  console.log('Window globals:', {
    collectTelemetry: (window as any).COLLECT_TELEMETRY,
    hasSupabaseUrl: !!(window as any).SUPABASE_URL,
    hasSupabaseKey: !!(window as any).SUPABASE_ANON_KEY,
    hasUserId: !!(window as any).USER_ID,
    supabaseUrl: (window as any).SUPABASE_URL,
    userId: (window as any).USER_ID
  });

  // First check if telemetry collection is enabled
  config.collectTelemetry = (window as any).COLLECT_TELEMETRY || false;

  if ((window as any).SUPABASE_URL && config.collectTelemetry) {
    config.supabaseUrl = (window as any).SUPABASE_URL;
  }
  
  if ((window as any).SUPABASE_ANON_KEY && config.collectTelemetry) {
    config.supabaseKey = (window as any).SUPABASE_ANON_KEY;
  }

  if ((window as any).USER_ID) {
    config.userId = (window as any).USER_ID;
  }

  // No fallbacks - if values are missing, log error and disable telemetry
  if (config.collectTelemetry && (!config.supabaseUrl || !config.supabaseKey || !config.userId)) {
    console.error('❌ Telemetry enabled but missing required config values. Disabling telemetry.');
    config.collectTelemetry = false;
    config.supabaseUrl = undefined;
    config.supabaseKey = undefined;
  }

  console.log('🎯 Final config:', {
    collectTelemetry: config.collectTelemetry,
    hasUrl: !!config.supabaseUrl,
    hasKey: !!config.supabaseKey,
    userId: config.userId
  });

  return config;
};

/**
 * Request configuration from the VS Code extension
 */
export const requestTelemetryConfig = (): void => {
  if (typeof vscode !== 'undefined') {
    vscode.postMessage({
      type: 'requestTelemetryConfig'
    });
  }
}; 