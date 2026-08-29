import { fetch as expoFetch } from 'expo/fetch';
import { API_URL } from '../config';
import { authContext } from './supabase';

// Port of CoachService.swift. Streaming is the main path — see `stream()`.

export interface DrillRecommendation {
  priority: number;
  focus_area: string;
  drill_name: string;
  /** Ordered steps. Streamed one `@step` at a time, so this fills in gradually. */
  steps: string[];
  /** `steps` joined; kept for parity with the buffered endpoint. */
  instructions: string;
  expected_outcome: string;
}

export interface ConversationSummary {
  id: number;
  title: string | null;
  round_id: number | null;
  message_count: number;
  last_message_at: string | null;
  preview: string | null;
}

export interface StoredMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
}

export interface CoachChatResponse {
  conversation_id: number;
  answer: string;
  confidence: number;
  key_insights: string[];
  drill_recommendations: DrillRecommendation[];
}

/**
 * A coach failure with copy the chat can show directly. The chat bubble is
 * titled "Couldn't reach the coach." for every failure, so this message is the
 * only thing telling the player what actually went wrong — keep it specific.
 */
export class CoachError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'CoachError';
    this.status = status;
  }

  static fromStatus(status: number): CoachError {
    if (status === 524 || status === 504) {
      return new CoachError(
        'The coach took too long to start answering. Tap retry.',
        status
      );
    }
    if (status >= 500) {
      return new CoachError('The coach hit a snag on our end. Give it another try.', status);
    }
    return new CoachError(`Something went wrong (${status}). Tap retry.`, status);
  }

  static fromUnknown(e: unknown): CoachError {
    if (e instanceof CoachError) return e;
    const message = e instanceof Error ? e.message : String(e);
    if (/abort/i.test(message)) return new CoachError('That request was cancelled. Tap retry.');
    if (/network/i.test(message)) {
      return new CoachError('The connection dropped. Check your signal, then retry.');
    }
    return new CoachError(message || 'Something went wrong. Tap retry.');
  }
}

// ── Streaming ────────────────────────────────────────────────────────────────

export type StreamEvent =
  | { type: 'meta'; conversation_id: number; confidence: number }
  | { type: 'delta'; text: string }
  | { type: 'insight'; text: string }
  | { type: 'drill'; drill: DrillRecommendation & { index: number } }
  | { type: 'done'; answer: string };

/**
 * Streams a coach reply as it is written.
 *
 * Uses `expo/fetch` rather than the global one: React Native's built-in fetch
 * has no readable `response.body`, so it would buffer the whole stream and
 * hand it over at the end — exactly the behaviour we are trying to escape.
 *
 * The buffered endpoint can't send a byte until the model finishes, and
 * Cloudflare only gives the origin 100s to start responding, so a long reply
 * came back as a 524 and read to the player as an unreachable coach.
 */
export async function* streamCoach(
  message: string,
  conversationId: number | null,
  roundId: number | null = null,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const { token, userId } = await authContext();

  const response = await expoFetch(`${API_URL}/api/v1/coach/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      user_id: userId,
      conversation_id: conversationId,
      message,
      round_id: roundId,
    }),
    signal,
  });

  if (!response.ok) throw CoachError.fromStatus(response.status);
  if (!response.body) throw new CoachError('The coach sent an empty response. Tap retry.');

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line.
      let split: number;
      while ((split = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock?.();
  }
}

function parseFrame(frame: string): StreamEvent | null {
  let name = '';
  const dataLines: string[] = [];

  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) continue; // blank or keepalive
    if (line.startsWith('event:')) name = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
  }
  if (!dataLines.length) return null;

  let payload: any;
  try {
    payload = JSON.parse(dataLines.join('\n'));
  } catch {
    return null; // A frame we can't read costs one update, not the reply.
  }

  switch (name) {
    case 'meta':
      return { type: 'meta', conversation_id: payload.conversation_id, confidence: payload.confidence };
    case 'delta':
      return { type: 'delta', text: payload.text };
    case 'insight':
      return { type: 'insight', text: payload.text };
    case 'drill':
      return { type: 'drill', drill: payload };
    case 'done':
      return { type: 'done', answer: payload.answer };
    case 'error':
      throw new CoachError(payload.detail ?? 'The coach stopped partway. Tap retry.');
    default:
      return null;
  }
}

// ── Buffered endpoints ───────────────────────────────────────────────────────

async function getJson<T>(path: string): Promise<T> {
  const { token } = await authContext();
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw CoachError.fromStatus(response.status);
  return (await response.json()) as T;
}

export const coachApi = {
  stream: streamCoach,

  /** Buffered send. Kept for parity; prefer `stream` — see its comment. */
  async send(message: string, conversationId: number | null, roundId: number | null = null) {
    const { token, userId } = await authContext();
    const response = await fetch(`${API_URL}/api/v1/coach/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        user_id: userId,
        conversation_id: conversationId,
        message,
        round_id: roundId,
      }),
    });
    if (!response.ok) throw CoachError.fromStatus(response.status);
    return (await response.json()) as CoachChatResponse;
  },

  async fetchConversations(limit = 20): Promise<ConversationSummary[]> {
    const { userId } = await authContext();
    const data = await getJson<{ conversations: ConversationSummary[] }>(
      `/api/v1/coach/conversations?user_id=${userId}&limit=${limit}`
    );
    return data.conversations ?? [];
  },

  /**
   * The backend verifies ownership here, so `user_id` is required — omitting it
   * is a 422, not a 500. API_CONTRACT used to leave this out.
   */
  async fetchMessages(conversationId: number): Promise<StoredMessage[]> {
    const { userId } = await authContext();
    const data = await getJson<{ messages: StoredMessage[] }>(
      `/api/v1/coach/conversations/${conversationId}/messages?user_id=${userId}`
    );
    return data.messages ?? [];
  },
};
