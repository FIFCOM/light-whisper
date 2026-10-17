import { describe, expect, it } from "vitest";

import {
  effectiveXaiAuthMode,
  shouldShowGrokBuildAuth,
  shouldUseGrokBuildOauth,
} from "./grokBuildAuth";

describe("effectiveXaiAuthMode", () => {
  it("returns the stored mode when the user has explicitly chosen api_key", () => {
    expect(effectiveXaiAuthMode({ storedMode: "api_key", loggedIn: true })).toBe("api_key");
    expect(effectiveXaiAuthMode({ storedMode: "api_key", loggedIn: false })).toBe("api_key");
  });

  it("returns the stored mode when the user has explicitly chosen oauth", () => {
    expect(effectiveXaiAuthMode({ storedMode: "oauth", loggedIn: true })).toBe("oauth");
    expect(effectiveXaiAuthMode({ storedMode: "oauth", loggedIn: false })).toBe("oauth");
  });

  it("defaults to oauth when no stored mode is set and a Grok Build session is logged in", () => {
    expect(effectiveXaiAuthMode({ storedMode: null, loggedIn: true })).toBe("oauth");
    expect(effectiveXaiAuthMode({ storedMode: undefined, loggedIn: true })).toBe("oauth");
  });

  it("defaults to api_key when no stored mode is set and the user is logged out", () => {
    expect(effectiveXaiAuthMode({ storedMode: null, loggedIn: false })).toBe("api_key");
    expect(effectiveXaiAuthMode({ storedMode: undefined, loggedIn: false })).toBe("api_key");
  });
});

describe("shouldShowGrokBuildAuth", () => {
  it("is true only for the xai provider", () => {
    expect(shouldShowGrokBuildAuth("xai")).toBe(true);
  });

  it("is false for OpenAI, other presets, custom providers, and casing variants", () => {
    expect(shouldShowGrokBuildAuth("openai")).toBe(false);
    expect(shouldShowGrokBuildAuth("deepseek")).toBe(false);
    expect(shouldShowGrokBuildAuth("cerebras")).toBe(false);
    expect(shouldShowGrokBuildAuth("custom-provider")).toBe(false);
    expect(shouldShowGrokBuildAuth("XAI")).toBe(false);
    expect(shouldShowGrokBuildAuth("Xai")).toBe(false);
    expect(shouldShowGrokBuildAuth("")).toBe(false);
  });
});

describe("shouldUseGrokBuildOauth", () => {
  it("is true only when the provider is xai, auth mode is oauth, and the user is logged in", () => {
    expect(shouldUseGrokBuildOauth({
      provider: "xai",
      authMode: "oauth",
      loggedIn: true,
    })).toBe(true);
  });

  it("is false when the provider is not xai even if oauth is selected and logged in", () => {
    expect(shouldUseGrokBuildOauth({
      provider: "openai",
      authMode: "oauth",
      loggedIn: true,
    })).toBe(false);
    expect(shouldUseGrokBuildOauth({
      provider: "deepseek",
      authMode: "oauth",
      loggedIn: true,
    })).toBe(false);
  });

  it("is false in api_key mode even when a Grok Build session is logged in", () => {
    expect(shouldUseGrokBuildOauth({
      provider: "xai",
      authMode: "api_key",
      loggedIn: true,
    })).toBe(false);
  });

  it("is false in oauth mode when the user is logged out", () => {
    expect(shouldUseGrokBuildOauth({
      provider: "xai",
      authMode: "oauth",
      loggedIn: false,
    })).toBe(false);
  });
});
