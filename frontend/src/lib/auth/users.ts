import type { Role } from "@/lib/api/contract";

/** The signed-in user (from the EEP, stored in the session cookie). */
export type SessionUser = { id: string; email: string; name: string; role: Role };

/** A user record as returned by the EEP admin API. */
export type ManagedUser = SessionUser & { active: boolean; created_at: string };

export const ROLE_LABEL: Record<Role, string> = {
  radiologist: "Radiologist",
  technologist: "Technologist",
  viewer: "Viewer",
  admin: "Admin",
};

export const ROLES: Role[] = ["radiologist", "technologist", "viewer", "admin"];
