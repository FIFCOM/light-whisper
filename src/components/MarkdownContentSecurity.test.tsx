import { cleanup, render } from "@testing-library/react";
import katex from "katex";
import { afterEach, describe, expect, it } from "vitest";
import MarkdownContent from "@/components/MarkdownContent";

afterEach(cleanup);

function withInheritedTrust(assertions: () => void): void {
  const descriptor = Object.getOwnPropertyDescriptor(Object.prototype, "trust");
  Object.defineProperty(Object.prototype, "trust", {
    configurable: true,
    value: true,
    writable: true,
  });

  try {
    assertions();
  } finally {
    if (descriptor) {
      Object.defineProperty(Object.prototype, "trust", descriptor);
    } else {
      Reflect.deleteProperty(Object.prototype, "trust");
    }
  }
}

describe("KaTeX trust boundary", () => {
  it("ignores inherited trust when rendering directly with default options", () => {
    withInheritedTrust(() => {
      const container = document.createElement("div");
      container.innerHTML = katex.renderToString(
        String.raw`x^2+\href{https://untrusted.invalid/direct}{untrusted}`,
      );

      expect(container.querySelector(".katex")).not.toBeNull();
      expect(container.querySelector("a, img")).toBeNull();
    });
  });

  it("blocks inherited trust in MarkdownContent while rendering inline and display math", () => {
    withInheritedTrust(() => {
      const { container } = render(
        <MarkdownContent
          content={String.raw`Inline $x^2+1$.

$$
\frac{1}{2}
$$

$\href{https://untrusted.invalid/markdown}{untrusted}$`}
        />,
      );

      expect(container.querySelectorAll(".katex")).toHaveLength(3);
      expect(container.querySelector("a, img")).toBeNull();
    });
  });

  it("allows a caller to explicitly opt into trusted commands", () => {
    const container = document.createElement("div");
    container.innerHTML = katex.renderToString(
      String.raw`\href{https://untrusted.invalid/explicit}{trusted}`,
      { trust: true },
    );

    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector("a")).toHaveAttribute(
      "href",
      "https://untrusted.invalid/explicit",
    );
  });
});
