// Runtime config from EXPO_PUBLIC_ env vars (see .env.example).
// Falls back to hardcoded non-secret values so the app still boots with a
// clear error instead of an undefined URL.

export const SUPABASE_URL =
  process.env.EXPO_PUBLIC_SUPABASE_URL ??
  'https://homeympykewfrsifkpbb.supabase.co';

export const SUPABASE_ANON_KEY =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  'https://dimple-api.chokepointmonitor.com';

export function assertConfig() {
  if (!SUPABASE_ANON_KEY) {
    throw new Error(
      'Missing EXPO_PUBLIC_SUPABASE_ANON_KEY. Copy mobile/.env.example to mobile/.env and paste the Supabase publishable key.'
    );
  }
}
