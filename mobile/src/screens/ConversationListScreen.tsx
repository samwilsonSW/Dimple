import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { coachApi, ConversationSummary } from '../lib/coach';
import { supabase } from '../lib/supabase';
import { colors } from '../theme';
import type { RootStackParamList } from '../../App';

type Props = NativeStackScreenProps<RootStackParamList, 'Conversations'>;

// Port of ConversationListView.swift — loading / empty / error / loaded states,
// pull-to-refresh, new-chat button, sign-out in the header.

export default function ConversationListScreen({ navigation }: Props) {
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (showSpinner: boolean) => {
    if (showSpinner) setItems(null);
    setError(null);
    try {
      const list = await coachApi.fetchConversations();
      setItems(list);
    } catch (e: any) {
      setError(e?.message ?? "Couldn't load conversations");
      setItems((prev) => prev ?? []);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(true);
    }, [load])
  );

  async function refresh() {
    setRefreshing(true);
    await load(false);
    setRefreshing(false);
  }

  return (
    <View style={styles.flex}>
      <FlatList
        data={items ?? []}
        keyExtractor={(c) => String(c.id)}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} />
        }
        ListHeaderComponent={
          <Pressable
            style={styles.newChat}
            onPress={() => navigation.navigate('Chat', {})}
          >
            <Text style={styles.newChatText}>＋ New Chat</Text>
          </Pressable>
        }
        ListEmptyComponent={
          items === null ? (
            <View style={styles.center}>
              <ActivityIndicator color={colors.forestGreen} size="large" />
            </View>
          ) : error ? (
            <View style={styles.center}>
              <Text style={styles.emptyTitle}>Couldn't load conversations</Text>
              <Text style={styles.emptyBody}>{error}</Text>
              <Pressable onPress={() => load(true)}>
                <Text style={styles.retry}>Try Again</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.center}>
              <Text style={styles.emptyTitle}>Talk to your coach</Text>
              <Text style={styles.emptyBody}>
                Ask about your game, your stats, or what to work on next.
              </Text>
            </View>
          )
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            onPress={() =>
              navigation.navigate('Chat', {
                conversationId: item.id,
                title: item.title?.trim() || 'Coach Chat',
              })
            }
          >
            <View style={styles.cardRow}>
              <Text style={styles.cardTitle} numberOfLines={1}>
                {item.title?.trim() || 'Coach Chat'}
              </Text>
              <Text style={styles.cardDate}>{displayDate(item.last_message_at)}</Text>
            </View>
            {!!item.preview && (
              <Text style={styles.cardPreview} numberOfLines={2}>
                {item.preview}
              </Text>
            )}
          </Pressable>
        )}
      />
    </View>
  );
}

function displayDate(raw: string | null): string {
  if (!raw) return '';
  const d = new Date(raw.includes('Z') || raw.includes('+') ? raw : raw + 'Z');
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const startOfDay = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function listHeaderRight() {
  return (
    <Pressable onPress={() => supabase.auth.signOut()} hitSlop={12}>
      <Text style={{ color: colors.forestGreen, fontWeight: '600' }}>Sign Out</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.background },
  list: { padding: 16, gap: 12, flexGrow: 1 },
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
    minHeight: 300,
    gap: 8,
  },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: colors.label },
  emptyBody: {
    fontSize: 14,
    color: colors.secondaryLabel,
    textAlign: 'center',
  },
  retry: {
    color: colors.forestGreen,
    fontWeight: '600',
    fontSize: 15,
    marginTop: 8,
  },
  newChat: {
    backgroundColor: '#2E7D321A',
    borderRadius: 14,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  newChatText: { color: colors.forestGreen, fontWeight: '600', fontSize: 16 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    gap: 6,
  },
  cardRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: colors.label, flex: 1 },
  cardDate: { fontSize: 12, color: colors.secondaryLabel },
  cardPreview: { fontSize: 14, color: colors.secondaryLabel },
});
