import { describe, expect, it } from "vitest";

import { normalizeSelectionText } from "../selectionPolicy";

describe("normalizeSelectionText", () => {
  it.each(["", "   ", "\r\n\t"])('rejects an empty selection: %j', (text) => {
    expect(normalizeSelectionText(text)).toBeNull();
  });

  it("normalizes line endings and trims only the outer whitespace", () => {
    expect(normalizeSelectionText("  first\r\n  second  \r\n"))
      .toBe("first\n  second");
  });

  it("keeps the complete selection regardless of length", () => {
    const text = `${"a".repeat(100_000)}😀tail`;

    const normalized = normalizeSelectionText(text);

    expect(normalized).toBe(text);
  });
});
