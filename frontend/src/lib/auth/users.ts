import type { Role } from "@/lib/api/contract";

export type SessionUser = { email: string; name: string; role: Role };

/**
 * Mock user directory — one per role. Replaced by real auth against the EEP later
 * (this is the frontend's mock-first session; production auth lives in the EEP).
 */
export const DEMO_USERS: SessionUser[] = [
  { email: "radiologist@demo", name: "Dr. Rana Radiologist", role: "radiologist" },
  { email: "tech@demo", name: "Tariq Technologist", role: "technologist" },
  { email: "viewer@demo", name: "Nadia (referring)", role: "viewer" },
  { email: "admin@demo", name: "Admin", role: "admin" },
];

export function findUser(email: string): SessionUser | undefined {
  return DEMO_USERS.find((u) => u.email === email);
}

export const ROLE_LABEL: Record<Role, string> = {
  radiologist: "Radiologist",
  technologist: "Technologist",
  viewer: "Viewer",
  admin: "Admin",
};
