import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { Config } from '../../providers/ConfigManager';

interface TelemetryEvent {
  user_id: string;
  session_id?: string;
  event_type: string;
  event_data: Record<string, any>;
}

class TelemetryClient {
  private static instance: TelemetryClient;
  private client: SupabaseClient | null = null;
  private initialized = false;

  private constructor() {
    // Set up config integration - will be initialized when config becomes available
    this.setupConfigIntegration();
  }

  public static getInstance(): TelemetryClient {
    if (!TelemetryClient.instance) {
      TelemetryClient.instance = new TelemetryClient();
    }
    return TelemetryClient.instance;
  }

  private initializeWithConfig(config: Config): void {
    if (this.initialized) {
      // Reset for reinitialization
      this.initialized = false;
      this.client = null;
    }

    console.log('🔧 Initializing telemetry client...');
    console.log('📋 Telemetry config:', {
      collectTelemetry: config.collectTelemetry,
      hasUrl: !!config.telemetryUrl,
      hasKey: !!config.telemetryKey,
      userId: config.userId,
      urlPrefix: config.telemetryUrl?.substring(0, 30) + '...'
    });

    if (!config.collectTelemetry) {
      console.log('📵 Telemetry collection disabled in config.');
      this.initialized = true;
      return;
    }

    if (!config.telemetryUrl || !config.telemetryKey) {
      console.warn('❌ Telemetry enabled but credentials not found. Telemetry will be disabled.');
      this.initialized = true;
      return;
    }

    try {
      this.client = createClient(config.telemetryUrl, config.telemetryKey);
      console.log('✅ Telemetry client initialized successfully');
    } catch (error) {
      console.error('❌ Failed to initialize telemetry client:', error);
    }

    this.initialized = true;
  }

  public isAvailable(): boolean {
    // With ConfigManager approach, we don't initialize on-demand
    // Client will be initialized when config becomes available
    return this.client !== null;
  }

  private async logEvent(event: TelemetryEvent): Promise<boolean> {
    if (!this.isAvailable()) {
      console.warn('Telemetry not available, skipping event logging');
      return false;
    }

    try {
      console.log('Attempting to log telemetry event:', event);
      
      const { data, error } = await this.client!.from('user_actions').insert({
        user_id: event.user_id,
        session_id: event.session_id,
        event_type: event.event_type,
        event_data: event.event_data // Don't stringify - Supabase handles JSONB
      });

      if (error) {
        console.error('Supabase error logging UI event:', error);
        return false;
      }

      console.log(`✅ UI event logged successfully: ${event.event_type}`, data);
      return true;
    } catch (error) {
      console.error('Failed to log UI event:', error);
      return false;
    }
  }

  public async logNodeInputView(
    userId: string,
    sessionId: string,
    nodeId: string,
    inputValue: string,
    nodeType: string = ''
  ): Promise<boolean> {
    return this.logEvent({
      user_id: userId,
      session_id: sessionId,
      event_type: 'node_input_view',
      event_data: { 
        node_id: nodeId, 
        input_value: inputValue,
        node_type: nodeType 
      }
    });
  }

  public async logNodeOutputView(
    userId: string,
    sessionId: string,
    nodeId: string,
    outputValue: string,
    nodeType: string = ''
  ): Promise<boolean> {
    return this.logEvent({
      user_id: userId,
      session_id: sessionId,
      event_type: 'node_output_view',
      event_data: { 
        node_id: nodeId, 
        output_value: outputValue,
        node_type: nodeType 
      }
    });
  }

  private setupConfigIntegration(): void {
    // In webview context, we need to wait for ConfigManager to be available
    // This will be set up when the extension initializes ConfigManager
    if (typeof window !== 'undefined' && (window as any).configManager) {
      const configManager = (window as any).configManager;
      configManager.onConfigChange((config: Config) => {
        console.log('🔄 Config update received in telemetry client, reinitializing...');
        this.initializeWithConfig(config);
      });
    } else {
      // ConfigManager not available yet, try again later
      setTimeout(() => this.setupConfigIntegration(), 100);
    }
  }
}

// Export singleton instance
export const telemetryClient = TelemetryClient.getInstance();

// Utility functions for node input/output view tracking
export const trackNodeInputView = async (
  nodeId: string,
  inputValue: string,
  sessionId: string,
  nodeType: string = '',
  userId?: string
) => {
  console.log('🎯 trackNodeInputView called:', { nodeId, sessionId, nodeType, userId, valueLength: inputValue.length });
  const configManager = (window as any).configManager;
  const config = configManager?.getCurrentConfig();
  const finalUserId = userId || config?.userId || 'default_user';
  return telemetryClient.logNodeInputView(finalUserId, sessionId, nodeId, inputValue, nodeType);
};

export const trackNodeOutputView = async (
  nodeId: string,
  outputValue: string,
  sessionId: string,
  nodeType: string = '',
  userId?: string
) => {
  console.log('🎯 trackNodeOutputView called:', { nodeId, sessionId, nodeType, userId, valueLength: outputValue.length });
  const configManager = (window as any).configManager;
  const config = configManager?.getCurrentConfig();
  const finalUserId = userId || config?.userId || 'default_user';
  return telemetryClient.logNodeOutputView(finalUserId, sessionId, nodeId, outputValue, nodeType);
}; 