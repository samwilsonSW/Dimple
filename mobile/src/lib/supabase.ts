import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { SUPABASE_ANON_KEY, SUPABASE_URL } from '../config';

// Session lives in AsyncStorage so a relaunch doesn't bounce the player back to
// the login screen. `detectSessionInUrl` is web-only and breaks on native.
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

/** Bearer token + lowercased user id, which the API matches case-sensitively. */
export async function authContext(): Promise<{ token: string; userId: string }> {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error('You are signed out. Sign in and try again.');
  return {
    token: data.session.access_token,
    // `match_shots` is case-sensitive on user_id and fails silently on a
    // mismatch — no error, just no results. Always lowercase.
    userId: data.session.user.id.toLowerCase(),
  };
}
