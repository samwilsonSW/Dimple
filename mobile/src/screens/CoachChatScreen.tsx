import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import {
  coachApi,
  CoachError,
  DrillRecommendation,
} from '../lib/coach';
import { colors } from '../theme';
import type { RootStackParamList } from '../../App';

type Props = NativeStackScreenProps<RootStackParamList, 'Chat'>;

// Port of CoachChatView.swift — message thread, send/retry, typing indicator,
// drill cards, confidence meter, suggested prompts on empty chat.

interface ChatMsg {
  key: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  confidence?: number;
  insights?: string[];
  drills?: DrillRecommendation[];
}

const SUGGESTED = [
  'What should I work on?',
  'How is my putting?',
  'Analyze my last round',
  'Give me a driving drill',
];

let keySeq = 0;
const nextKey = () => `m${++keySeq}`;

export default function CoachChatScreen({ route, navigation }: Props) {
  const { conversationId: initialId, title } = route.params;
  const [conversationId, setConversationId] = useState<number | null>(
    initialId ?? null
  );
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const failedText = useRef<string | null>(null);
  const listRef = useRef<FlatList<ChatMsg>>(null);

  useEffect(() => {
    if (title) navigation.setOptions({ title });
  }, [title, navigation]);

  const loadHistory = useCallback(async () => {
    if (!conversationId) return;
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const history = await coachApi.fetchMessages(conversationId);
      setMessages(
        history.map((m) => ({
          key: nextKey(),
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
        }))
      );
    } catch (e: any) {
      setHistoryError(e?.message ?? "Couldn't load this conversation");
    } finally {
      setLoadingHistory(false);
    }
  }, [conversationId]);

  useEffect(() => {
    if (conversationId && messages.length === 0) loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setInput('');
    setSending(true);
    failedText.current = null;
    setMessages((prev) => [
      ...prev.filter((m) => m.role !== 'error'),
      { key: nextKey(), role: 'user', content: trimmed },
    ]);
    try {
      const resp = await coachApi.send(trimmed, conversationId);
      if (!conversationId) setConversationId(resp.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          key: nextKey(),
          role: 'assistant',
          content: resp.answer,
          confidence: resp.confidence,
          insights: resp.key_insights,
          drills: resp.drill_recommendations,
        },
      ]);
    } catch (e: any) {
      failedText.current = trimmed;
      const msg =
        e instanceof CoachError ? e.message : 'Something went wrong. Tap retry.';
      setMessages((prev) => [
        ...prev,
        { key: nextKey(), role: 'error', content: msg },
      ]);
    } finally {
      setSending(false);
    }
  }

  function retry() {
    const text = failedText.current;
    if (!text) return;
    setMessages((prev) => prev.filter((m) => m.role !== 'error'));
    send(text);
  }

  const isNewEmpty = !conversationId && messages.length === 0 && !sending;

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.key}
        contentContainerStyle={styles.thread}
        onContentSizeChange={() =>
          listRef.current?.scrollToEnd({ animated: true })
        }
        ListHeaderComponent={
          loadingHistory ? (
            <View style={styles.historyBox}>
              <ActivityIndicator color={colors.forestGreen} />
              <Text style={styles.historyText}>Loading conversation…</Text>
            </View>
          ) : historyError ? (
            <View style={styles.historyBox}>
              <Text style={styles.emptyTitle}>Couldn't load this conversation</Text>
              <Text style={styles.emptyBody}>{historyError}</Text>
              <Pressable onPress={loadHistory}>
                <Text style={styles.retry}>Try Again</Text>
              </Pressable>
            </View>
          ) : isNewEmpty ? (
            <View style={styles.idle}>
              <Text style={styles.idleTitle}>Ask me anything about your game.</Text>
              <View style={styles.suggestions}>
                {SUGGESTED.map((q) => (
                  <Pressable key={q} style={styles.chip} onPress={() => send(q)}>
                    <Text style={styles.chipText}>{q}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null
        }
        renderItem={({ item }) =>
          item.role === 'user' ? (
            <View style={styles.userRow}>
              <View style={styles.userBubble}>
                <Text style={styles.userText}>{item.content}</Text>
              </View>
            </View>
          ) : item.role === 'error' ? (
            <View style={styles.errorBubble}>
              <Text style={styles.errorTitle}>Couldn't reach the coach.</Text>
              <Text style={styles.errorBody} numberOfLines={3}>
                {item.content}
              </Text>
              <Pressable onPress={retry}>
                <Text style={styles.retry}>↻ Retry</Text>
              </Pressable>
            </View>
          ) : (
            <AssistantBubble msg={item} />
          )
        }
        ListFooterComponent={
          sending ? (
            <View style={styles.typing}>
              <ActivityIndicator size="small" color={colors.forestGreen} />
              <Text style={styles.typingText}>Analyzing your game…</Text>
            </View>
          ) : null
        }
      />

      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          placeholder="Message your coach…"
          placeholderTextColor={colors.tertiaryLabel}
          value={input}
          onChangeText={setInput}
          multiline
        />
        <Pressable
          style={[
            styles.sendBtn,
            (!input.trim() || sending) && styles.sendBtnOff,
          ]}
          disabled={!input.trim() || sending}
          onPress={() => send(input)}
        >
          <Text style={styles.sendArrow}>↑</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function AssistantBubble({ msg }: { msg: ChatMsg }) {
  return (
    <View style={styles.assistantRow}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>⛳</Text>
      </View>
      <View style={styles.assistantBubble}>
        {typeof msg.confidence === 'number' && (
          <Confidence value={msg.confidence} />
        )}
        <Text style={styles.assistantText}>{msg.content}</Text>
        {!!msg.insights?.length && (
          <View style={styles.insights}>
            <Text style={styles.insightsTitle}>💡 Key Insights</Text>
            {msg.insights.map((ins, i) => (
              <Text key={i} style={styles.insightItem}>
                ✓ {ins}
              </Text>
            ))}
          </View>
        )}
        {msg.drills?.map((d) => <DrillCard key={d.priority} drill={d} />)}
      </View>
    </View>
  );
}

function Confidence({ value }: { value: number }) {
  const color =
    value <= 2 ? colors.error : value === 3 ? colors.champagneGold : colors.sageGreen;
  return (
    <View style={styles.confRow}>
      <Text style={styles.confLabel}>CONFIDENCE</Text>
      <View style={styles.confPips}>
        {[1, 2, 3, 4, 5].map((i) => (
          <View
            key={i}
            style={[
              styles.confPip,
              { backgroundColor: i <= value ? color : colors.cardAlt },
            ]}
          />
        ))}
      </View>
    </View>
  );
}

function DrillCard({ drill }: { drill: DrillRecommendation }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={styles.drill}>
      <Pressable style={styles.drillHeader} onPress={() => setOpen(!open)}>
        <View style={styles.drillBadge}>
          <Text style={styles.drillBadgeText}>{drill.priority}</Text>
        </View>
        <View style={styles.drillHeadText}>
          <Text style={styles.drillName}>{drill.drill_name}</Text>
          <Text style={styles.drillFocus}>{drill.focus_area}</Text>
        </View>
        <Text style={styles.drillChevron}>{open ? '▾' : '▸'}</Text>
      </Pressable>
      {open && (
        <View style={styles.drillBody}>
          <Text style={styles.drillInstructions}>{drill.instructions}</Text>
          <Text style={styles.drillOutcome}>⚑ {drill.expected_outcome}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.background },
  thread: { padding: 16, gap: 12, flexGrow: 1 },
  idle: { paddingVertical: 24, gap: 16 },
  idleTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.secondaryLabel,
  },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    backgroundColor: '#2E7D3214',
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#2E7D3233',
  },
  chipText: { color: colors.forestGreen, fontSize: 14, fontWeight: '500' },
  userRow: { flexDirection: 'row', justifyContent: 'flex-end' },
  userBubble: {
    backgroundColor: colors.forestGreen,
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '80%',
  },
  userText: { color: colors.white, fontSize: 16 },
  assistantRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  avatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#7C9A7226',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 14 },
  assistantBubble: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 18,
    padding: 14,
    gap: 10,
  },
  assistantText: { fontSize: 16, color: colors.label, lineHeight: 22 },
  insights: { gap: 6 },
  insightsTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.champagneGold,
  },
  insightItem: { fontSize: 14, color: colors.label, lineHeight: 20 },
  confRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  confLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.tertiaryLabel,
    letterSpacing: 0.6,
  },
  confPips: { flexDirection: 'row', gap: 4 },
  confPip: { width: 18, height: 5, borderRadius: 3 },
  drill: {
    backgroundColor: colors.cardAlt,
    borderRadius: 14,
    overflow: 'hidden',
  },
  drillHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 12,
  },
  drillBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#C9A2271F',
    alignItems: 'center',
    justifyContent: 'center',
  },
  drillBadgeText: { color: colors.champagneGold, fontWeight: '700' },
  drillHeadText: { flex: 1 },
  drillName: { fontSize: 14, fontWeight: '600', color: colors.label },
  drillFocus: { fontSize: 12, color: colors.secondaryLabel },
  drillChevron: { color: colors.tertiaryLabel, fontSize: 14 },
  drillBody: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    padding: 12,
    gap: 8,
  },
  drillInstructions: { fontSize: 14, color: colors.label, lineHeight: 20 },
  drillOutcome: { fontSize: 12, color: colors.secondaryLabel },
  errorBubble: {
    backgroundColor: '#E08A0014',
    borderRadius: 18,
    padding: 14,
    gap: 6,
    borderWidth: 1,
    borderColor: '#E08A0033',
  },
  errorTitle: { fontSize: 14, fontWeight: '600', color: colors.label },
  errorBody: { fontSize: 12, color: colors.secondaryLabel },
  retry: { color: colors.forestGreen, fontWeight: '600', fontSize: 14 },
  typing: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.card,
    alignSelf: 'flex-start',
    borderRadius: 18,
    padding: 14,
  },
  typingText: { fontSize: 14, color: colors.secondaryLabel },
  historyBox: {
    alignItems: 'center',
    gap: 8,
    padding: 24,
    minHeight: 120,
    justifyContent: 'center',
  },
  historyText: { fontSize: 14, color: colors.secondaryLabel },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: colors.label },
  emptyBody: {
    fontSize: 13,
    color: colors.secondaryLabel,
    textAlign: 'center',
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    backgroundColor: colors.background,
  },
  input: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 22,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 16,
    maxHeight: 110,
    color: colors.label,
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.forestGreen,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnOff: { backgroundColor: colors.cardAlt },
  sendArrow: { color: colors.white, fontSize: 18, fontWeight: '700' },
});
