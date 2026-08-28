import { describe, expect, it, vi } from "vitest";

import { openRegisteredFile } from "./project";

describe("openRegisteredFile", () => {
  it("calls the restricted local API with the registered path", async () => {
    const fetcher = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true, path: "docs/architecture.md" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      openRegisteredFile("docs/architecture.md", fetcher),
    ).resolves.toEqual({ ok: true, path: "docs/architecture.md" });
    expect(fetcher).toHaveBeenCalledWith("/api/open-file", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path: "docs/architecture.md" }),
    });
  });
});
