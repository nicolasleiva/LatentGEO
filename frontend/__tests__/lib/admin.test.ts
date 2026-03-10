import { isAdminOnlyPath } from "@/lib/admin";

describe("isAdminOnlyPath", () => {
  it("keeps GitHub admin root protected while leaving the canonical callback public", () => {
    expect(isAdminOnlyPath("/en/integrations/github")).toBe(true);
    expect(isAdminOnlyPath("/en/integrations/github/repos")).toBe(true);
    expect(isAdminOnlyPath("/integrations/github/callback")).toBe(false);
  });
});
