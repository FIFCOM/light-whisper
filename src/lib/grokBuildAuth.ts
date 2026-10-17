import type { XaiAuthMode } from "@/types";

export function effectiveXaiAuthMode({
  storedMode,
  loggedIn,
}: {
  storedMode?: XaiAuthMode | null;
  loggedIn: boolean;
}): XaiAuthMode {
  if (storedMode === "api_key" || storedMode === "oauth") {
    return storedMode;
  }
  return loggedIn ? "oauth" : "api_key";
}

export function shouldShowGrokBuildAuth(provider: string): boolean {
  return provider === "xai";
}

export function shouldUseGrokBuildOauth({
  provider,
  authMode,
  loggedIn,
}: {
  provider: string;
  authMode: XaiAuthMode;
  loggedIn: boolean;
}): boolean {
  return provider === "xai" && authMode === "oauth" && loggedIn;
}
