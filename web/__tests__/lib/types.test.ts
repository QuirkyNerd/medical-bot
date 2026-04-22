import { describe, it, expect } from 'vitest';
import { PROVIDER_CONFIGS } from '@/lib/types';
import type { Provider } from '@/lib/types';

describe('Provider Types', () => {
  it('should only have the groq provider', () => {
    const providers: Provider[] = ['groq'];
    providers.forEach(provider => {
      expect(PROVIDER_CONFIGS[provider]).toBeDefined();
      expect(PROVIDER_CONFIGS[provider].name).toBe(provider);
      expect(PROVIDER_CONFIGS[provider].displayName).toBeDefined();
      expect(PROVIDER_CONFIGS[provider].requiresApiKey).toBeDefined();
      expect(Array.isArray(PROVIDER_CONFIGS[provider].models)).toBe(true);
    });
  });

  it('should have at least one model for groq', () => {
    Object.values(PROVIDER_CONFIGS).forEach(config => {
      expect(config.models.length).toBeGreaterThan(0);
      config.models.forEach(model => {
        expect(model.id).toBeDefined();
        expect(model.name).toBeDefined();
      });
    });
  });

  it('groq requires an API key', () => {
    expect(PROVIDER_CONFIGS.groq.requiresApiKey).toBe(true);
  });
});
