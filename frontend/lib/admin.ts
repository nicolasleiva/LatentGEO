const DEFAULT_ADMIN_ROLES = ["admin", "ops-admin"];

function normalizeList(value: unknown): string[] {
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);
  }
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);
  }
  return [];
}

function collectClaimValues(
  user: Record<string, unknown> | null | undefined,
  claimKey: string,
): string[] {
  if (!user) return [];

  const collected: string[] = [];
  for (const [key, value] of Object.entries(user)) {
    if (key === claimKey || key.endsWith(`/${claimKey}`)) {
      collected.push(...normalizeList(value));
    }
  }
  return Array.from(new Set(collected));
}

export function isAdminSessionUser(
  user: Record<string, unknown> | null | undefined,
): boolean {
  if (!user) return false;

  const email =
    typeof user.email === "string" ? user.email.trim().toLowerCase() : "";
  const adminEmails = new Set(
    normalizeList(process.env.AUTH0_ADMIN_EMAILS || ""),
  );
  if (email && adminEmails.has(email)) {
    return true;
  }

  const configuredRoles = normalizeList(process.env.AUTH0_ADMIN_ROLE_NAMES || "");
  const adminRoles = new Set(
    configuredRoles.length > 0 ? configuredRoles : DEFAULT_ADMIN_ROLES,
  );
  const roles = collectClaimValues(user, "roles");
  if (roles.some((role) => adminRoles.has(role))) {
    return true;
  }

  const adminPermissions = new Set(
    normalizeList(process.env.AUTH0_ADMIN_PERMISSIONS || ""),
  );
  if (adminPermissions.size > 0) {
    const permissions = collectClaimValues(user, "permissions");
    if (permissions.some((permission) => adminPermissions.has(permission))) {
      return true;
    }
  }

  return false;
}

export function isAdminOnlyPath(pathname: string): boolean {
  return (
    pathname.startsWith("/en/ops") ||
    pathname === "/en/integrations/github" ||
    pathname.startsWith("/en/integrations/github/") ||
    pathname === "/en/integrations/hubspot/rollback" ||
    pathname.startsWith("/en/integrations/hubspot/rollback/")
  );
}
