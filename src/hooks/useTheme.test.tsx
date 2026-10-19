import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { THEME_STORAGE_KEY } from "@/lib/constants";
import { useTheme } from "./useTheme";

function mockMedia(initialDark = false) {
  let systemDark = initialDark;
  let reducedMotion = false;
  const system = new EventTarget() as MediaQueryList;
  const reduced = new EventTarget() as MediaQueryList;
  Object.defineProperty(system, "matches", { get: () => systemDark });
  Object.defineProperty(reduced, "matches", { get: () => reducedMotion });
  vi.stubGlobal("matchMedia", vi.fn((query: string) => (
    query === "(prefers-color-scheme: dark)" ? system : reduced
  )));
  return {
    setSystemDark(dark: boolean) {
      if (systemDark === dark) return;
      systemDark = dark;
      const event = new Event("change");
      Object.defineProperty(event, "matches", { value: dark });
      system.dispatchEvent(event);
    },
    setReducedMotion(reduced: boolean) { reducedMotion = reduced; },
  };
}

function receiveStoredTheme(value: string | null) {
  const oldValue = localStorage.getItem(THEME_STORAGE_KEY);
  if (value === null) localStorage.removeItem(THEME_STORAGE_KEY);
  else localStorage.setItem(THEME_STORAGE_KEY, value);
  window.dispatchEvent(new StorageEvent("storage", {
    key: THEME_STORAGE_KEY, oldValue, newValue: value, storageArea: localStorage,
  }));
}

function expectDOM(dark: boolean) {
  expect(document.documentElement.dataset.theme).toBe(dark ? "dark" : "light");
  expect(document.documentElement.classList.contains("dark")).toBe(dark);
  expect(document.documentElement).not.toHaveClass("no-transition");
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.classList.remove("dark", "no-transition");
});

afterEach(() => {
  cleanup();
  delete (document as Partial<Document>).startViewTransition;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

it("synchronizes all mounted consumers when either selects a theme", () => {
  const media = mockMedia();
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());

  act(() => settings.result.current.setTheme("dark"));
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "dark", isDark: true });
  }
  expectDOM(true);
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

  act(() => main.result.current.setTheme("light"));
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "light", isDark: false });
  }
  expectDOM(false);
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");

  act(() => settings.result.current.setTheme("system"));
  act(() => media.setSystemDark(true));
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "system", isDark: true });
  }
  expectDOM(true);
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
});

it.each(["dark", "light"] as const)("keeps manual %s when an older consumer receives OS changes", (theme) => {
  const dark = theme === "dark";
  const media = mockMedia(!dark);
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  act(() => settings.result.current.setTheme(theme));
  act(() => media.setSystemDark(dark));
  act(() => media.setSystemDark(!dark));

  expectDOM(dark);
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme, isDark: dark });
  }
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe(theme);
});

it("synchronizes cross-window storage selections and follows OS changes only in system mode", () => {
  const media = mockMedia();
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  for (const theme of ["dark", "light", "system"] as const) {
    act(() => receiveStoredTheme(theme));
    act(() => media.setSystemDark(true));
    const dark = theme !== "light";
    for (const consumer of [main, settings]) {
      expect(consumer.result.current).toMatchObject({ theme, isDark: dark });
    }
    expectDOM(dark);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe(theme);
    act(() => media.setSystemDark(false));
    expectDOM(theme === "dark");
  }
});

it("keeps the latest stored preference when an older storage event arrives after a local selection", () => {
  mockMedia();
  localStorage.setItem(THEME_STORAGE_KEY, "light");
  const olderEvent = new StorageEvent("storage", {
    key: THEME_STORAGE_KEY, newValue: "light", storageArea: localStorage,
  });
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  act(() => settings.result.current.setTheme("dark"));
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

  act(() => window.dispatchEvent(olderEvent));

  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "dark", isDark: true });
  }
  expectDOM(true);
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
});

it.each(["invalid", null])("uses system mode when a storage event contains %s", (value) => {
  mockMedia();
  localStorage.setItem(THEME_STORAGE_KEY, "dark");
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  act(() => receiveStoredTheme(value));

  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "system", isDark: false });
  }
  expectDOM(false);
});

it("uses system mode after another window clears storage", () => {
  const media = mockMedia();
  localStorage.setItem(THEME_STORAGE_KEY, "dark");
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  act(() => {
    localStorage.clear();
    window.dispatchEvent(new StorageEvent("storage", { key: null, storageArea: localStorage }));
  });
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "system", isDark: false });
  }
  expectDOM(false);
  act(() => media.setSystemDark(true));
  expectDOM(true);
});

it("ignores unrelated keys and session storage events", () => {
  mockMedia();
  localStorage.setItem(THEME_STORAGE_KEY, "dark");
  const { result } = renderHook(() => useTheme());
  act(() => {
    localStorage.setItem("unrelated-preference", "light");
    window.dispatchEvent(new StorageEvent("storage", {
      key: "unrelated-preference", newValue: "light", storageArea: localStorage,
    }));
    sessionStorage.setItem(THEME_STORAGE_KEY, "light");
    window.dispatchEvent(new StorageEvent("storage", {
      key: THEME_STORAGE_KEY, newValue: "light", storageArea: sessionStorage,
    }));
  });
  expect(result.current).toMatchObject({ theme: "dark", isDark: true });
  expectDOM(true);
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
});

it("keeps remaining consumers live and removes event effects after the final unmount", () => {
  const media = mockMedia();
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  settings.unmount();
  act(() => media.setSystemDark(true));
  expect(main.result.current).toMatchObject({ theme: "system", isDark: true });
  expectDOM(true);
  main.unmount();
  act(() => {
    media.setSystemDark(false);
    receiveStoredTheme("light");
  });
  expectDOM(true);
});

it("reloads the latest stored preference after every consumer unmounts", () => {
  const media = mockMedia();
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  act(() => settings.result.current.setTheme("dark"));
  expectDOM(true);
  settings.unmount();
  main.unmount();

  localStorage.setItem(THEME_STORAGE_KEY, "light");
  act(() => media.setSystemDark(true));
  const remounted = renderHook(() => useTheme());
  expect(remounted.result.current).toMatchObject({ theme: "light", isDark: false });
  expectDOM(false);
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");

  act(() => media.setSystemDark(false));
  act(() => media.setSystemDark(true));
  expect(remounted.result.current).toMatchObject({ theme: "light", isDark: false });
  expectDOM(false);
  act(() => remounted.result.current.setTheme("system"));
  expect(remounted.result.current).toMatchObject({ theme: "system", isDark: true });
  expectDOM(true);
  act(() => media.setSystemDark(false));
  expect(remounted.result.current).toMatchObject({ theme: "system", isDark: false });
  expectDOM(false);
});

it("shares manual preferences when reading or writing storage is unavailable", () => {
  const media = mockMedia();
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("storage unavailable"); });
  const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage unavailable"); });
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  act(() => settings.result.current.setTheme("dark"));
  act(() => media.setSystemDark(true));
  act(() => media.setSystemDark(false));

  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "dark", isDark: true });
  }
  expectDOM(true);
  expect(write).toHaveBeenCalledWith(THEME_STORAGE_KEY, "dark");
});

it.each(["dark", "light"] as const)("keeps manual %s for consumers mounted later while storage is unavailable", (theme) => {
  const dark = theme === "dark";
  const media = mockMedia(!dark);
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("storage unavailable"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage unavailable"); });
  const main = renderHook(() => useTheme());
  act(() => main.result.current.setTheme(theme));
  expect(main.result.current).toMatchObject({ theme, isDark: dark });
  expectDOM(dark);

  const settings = renderHook(() => useTheme());
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme, isDark: dark });
  }
  expectDOM(dark);

  act(() => media.setSystemDark(dark));
  act(() => media.setSystemDark(!dark));
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme, isDark: dark });
  }
  expectDOM(dark);
});

it("changes themes immediately without support and uses one transition when supported, except for reduced motion", () => {
  const media = mockMedia();
  const { result } = renderHook(() => useTheme());
  expectDOM(false);
  act(() => result.current.setTheme("dark"));
  expectDOM(true);

  const skip = vi.fn();
  const transition = vi.fn((apply: () => void) => {
    apply();
    return { finished: Promise.resolve(), skipTransition: skip };
  });
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: transition });
  act(() => result.current.setTheme("light"));
  expect(transition).toHaveBeenCalledOnce();
  expectDOM(false);
  act(() => result.current.setTheme("dark"));
  expect(skip).toHaveBeenCalledOnce();
  media.setReducedMotion(true);
  act(() => result.current.setTheme("light"));
  expect(transition).toHaveBeenCalledTimes(2);
  expectDOM(false);
});

it("keeps the latest shared preference when a reversed transition callback arrives late", () => {
  mockMedia();
  const main = renderHook(() => useTheme());
  const settings = renderHook(() => useTheme());
  const callbacks: (() => void)[] = [];
  const skip = vi.fn();
  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    value: vi.fn((apply: () => void) => {
      callbacks.push(apply);
      return { finished: Promise.resolve(), skipTransition: skip };
    }),
  });
  act(() => settings.result.current.setTheme("dark"));
  act(() => main.result.current.setTheme("light"));
  act(() => callbacks.forEach((apply) => apply()));

  expect(skip).toHaveBeenCalled();
  expectDOM(false);
  for (const consumer of [main, settings]) {
    expect(consumer.result.current).toMatchObject({ theme: "light", isDark: false });
  }
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
});
