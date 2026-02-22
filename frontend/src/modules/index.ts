import { ReactElement } from 'react';

// ─── Module Manifest ─────────────────────────────────
// Each module exports a manifest. The main UI reads it
// to auto-register routes and navigation items.
// Module author works ONLY in their own folder.

export interface ModuleNavItem {
  label: string;
  path: string;
  icon: ReactElement;
}

export interface ModuleRoute {
  path: string;
  component: React.ComponentType;
}

export interface ModuleManifest {
  name: string;
  displayName: string;
  description: string;
  navigation: ModuleNavItem[];
  routes: ModuleRoute[];
}

// ─── Auto-discovery ──────────────────────────────────
// Vite scans all ./*/index.tsx at build time.
// Each module just needs to export any ModuleManifest-shaped object.
// No manual registration required — drop a folder and rebuild.

function isManifest(value: unknown): value is ModuleManifest {
  return (
    typeof value === 'object' &&
    value !== null &&
    'name' in value &&
    'routes' in value &&
    'navigation' in value &&
    Array.isArray((value as ModuleManifest).routes) &&
    Array.isArray((value as ModuleManifest).navigation)
  );
}

const moduleFiles = import.meta.glob<Record<string, unknown>>('./*/index.tsx', {
  eager: true,
});

const manifests: ModuleManifest[] = [];

for (const [, mod] of Object.entries(moduleFiles)) {
  for (const exp of Object.values(mod)) {
    if (isManifest(exp)) {
      manifests.push(exp);
    }
  }
}

export function getModuleManifests(): ModuleManifest[] {
  return manifests;
}
