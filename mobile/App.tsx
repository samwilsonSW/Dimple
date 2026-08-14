import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { Session } from '@supabase/supabase-js';
import { supabase } from './src/lib/supabase';
import { assertConfig } from './src/config';
import LoginScreen from './src/screens/LoginScreen';
import ConversationListScreen, {
  listHeaderRight,
} from './src/screens/ConversationListScreen';
import CoachChatScreen from './src/screens/CoachChatScreen';
import { colors } from './src/theme';

export type RootStackParamList = {
  Login: undefined;
  Conversations: undefined;
  Chat: { conversationId?: number; title?: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    try {
      assertConfig();
    } catch (e: any) {
      setConfigError(e?.message ?? 'Missing config.');
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.forestGreen} size="large" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerTintColor: colors.forestGreen,
          headerTitleStyle: { color: colors.label },
        }}
      >
        {!session || configError ? (
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
        ) : (
          <>
            <Stack.Screen
              name="Conversations"
              component={ConversationListScreen}
              options={{ title: 'Coach', headerRight: listHeaderRight }}
            />
            <Stack.Screen
              name="Chat"
              component={CoachChatScreen}
              options={{ title: 'Dimple Coach' }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
