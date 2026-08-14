import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { supabase } from '../lib/supabase';
import { colors } from '../theme';

// Port of AuthView.swift (email/password path only for the trial).
// Apple/Google sign-in are native-flow extras — deferred, same as the Swift
// Google button which is still a TODO.

export default function LoginScreen() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = isSignUp
    ? email.length > 0 && password.length > 0 && password === confirm
    : email.length > 0 && password.length > 0;

  async function submit() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: { data: name ? { display_name: name } : undefined },
        });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (error) throw error;
      }
      // On success, App.tsx auth listener swaps to the conversation list.
    } catch (e: any) {
      setError(e?.message ?? 'Sign-in failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.brand}>
          <View style={styles.logo}>
            <Text style={styles.logoEmoji}>⛳</Text>
          </View>
          <Text style={styles.title}>Dimple</Text>
          <Text style={styles.subtitle}>Your AI Golf Coach</Text>
        </View>

        <View style={styles.form}>
          {isSignUp && (
            <Field
              placeholder="Full Name"
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
            />
          )}
          <Field
            placeholder="Email"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Field
            placeholder="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          {isSignUp && (
            <Field
              placeholder="Confirm Password"
              value={confirm}
              onChangeText={setConfirm}
              secureTextEntry
            />
          )}

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          <Pressable
            style={[styles.primary, (!valid || loading) && styles.primaryOff]}
            disabled={!valid || loading}
            onPress={submit}
          >
            {loading ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <Text style={styles.primaryText}>
                {isSignUp ? 'Create Account' : 'Sign In'}
              </Text>
            )}
          </Pressable>

          <Pressable
            style={styles.toggle}
            onPress={() => {
              setIsSignUp(!isSignUp);
              setPassword('');
              setConfirm('');
              setError(null);
            }}
          >
            <Text style={styles.toggleText}>
              {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
              <Text style={styles.toggleLink}>
                {isSignUp ? 'Sign In' : 'Sign Up'}
              </Text>
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Field(props: React.ComponentProps<typeof TextInput>) {
  return (
    <TextInput
      placeholderTextColor={colors.tertiaryLabel}
      style={styles.field}
      {...props}
    />
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.background },
  container: { paddingHorizontal: 28, paddingTop: 72, paddingBottom: 40 },
  brand: { alignItems: 'center', marginBottom: 40 },
  logo: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.forestGreen,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  logoEmoji: { fontSize: 32, color: colors.white },
  title: { fontSize: 40, fontWeight: '700', color: colors.label },
  subtitle: { fontSize: 15, color: colors.secondaryLabel, marginTop: 4 },
  form: { gap: 14 },
  field: {
    backgroundColor: colors.card,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 16,
    color: colors.label,
  },
  errorBox: {
    backgroundColor: '#E08A0014',
    borderRadius: 10,
    padding: 12,
  },
  errorText: { color: colors.secondaryLabel, fontSize: 13 },
  primary: {
    backgroundColor: colors.forestGreen,
    borderRadius: 14,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
  },
  primaryOff: { backgroundColor: colors.cardAlt },
  primaryText: { color: colors.white, fontSize: 16, fontWeight: '600' },
  toggle: { alignItems: 'center', paddingVertical: 16 },
  toggleText: { fontSize: 15, color: colors.secondaryLabel },
  toggleLink: { color: colors.forestGreen, fontWeight: '600' },
});
