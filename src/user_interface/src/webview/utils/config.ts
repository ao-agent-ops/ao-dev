// Configuration utilities for telemetry
export interface TelemetryConfig {
  supabaseUrl: string;
  supabaseKey: string;
  userId: string;
}

declare const vscode: any;

/**
 * Get telemetry configuration from VS Code extension settings or environment
 */
export const getTelemetryConfig = (): Partial<TelemetryConfig> => {
  console.log('🔍 Getting telemetry config...');
  
  // Try to get from window global variables (set by extension)
  const config: Partial<TelemetryConfig> = {};

  console.log('Window globals:', {
    hasSupabaseUrl: !!(window as any).SUPABASE_URL,
    hasSupabaseKey: !!(window as any).SUPABASE_ANON_KEY,
    hasUserId: !!(window as any).USER_ID,
    supabaseUrl: (window as any).SUPABASE_URL,
    userId: (window as any).USER_ID
  });

  if ((window as any).SUPABASE_URL) {
    config.supabaseUrl = (window as any).SUPABASE_URL;
  }
  
  if ((window as any).SUPABASE_ANON_KEY) {
    config.supabaseKey = (window as any).SUPABASE_ANON_KEY;
  }

  if ((window as any).USER_ID) {
    config.userId = (window as any).USER_ID;
  }

  // Fallback to process.env for development
  if (!config.supabaseUrl && process.env.SUPABASE_URL) {
    config.supabaseUrl = process.env.SUPABASE_URL;
    console.log('📦 Using SUPABASE_URL from process.env');
  }
  
  if (!config.supabaseKey && process.env.SUPABASE_ANON_KEY) {
    config.supabaseKey = process.env.SUPABASE_ANON_KEY;
    console.log('📦 Using SUPABASE_ANON_KEY from process.env');
  }

  if (!config.userId) {
    config.userId = 'default_user'; // Default fallback
    console.log('📦 Using default userId');
  }

  console.log('🎯 Final config:', {
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