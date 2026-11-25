
import { useState, useRef, useEffect } from "react";
import {
  Bot,
  User,
  Send,
  Plus,
  Zap,
  Clock3,
  Cpu,
  Activity,
  Database,
  LoaderCircle,
  History,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
} from "lucide-react";

import "./App.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const STORAGE_KEY = "relay-conversations";

function createSessionId() {
  return `s-${crypto.randomUUID()}`;
}

function App() {
  const [sessionId, setSessionId] = useState(createSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedTraces, setExpandedTraces] = useState({});

  // Read known conversation IDs from browser storage.
  const [conversations, setConversations] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      const parsed = saved ? JSON.parse(saved) : [];

      return Array.isArray(parsed)
        ? parsed.filter(
            (chat) =>
              typeof chat.session_id === "string" &&
              typeof chat.title === "string"
          )
        : [];
    } catch {
      return [];
    }
  });

  const bottomRef = useRef(null);

  // Save the conversation index, not message contents.
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(conversations)
      );
    } catch {
      // Chat continues if browser storage is unavailable.
    }
  }, [conversations]);

  // Scroll to the latest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // ==========================================
  // LOAD A PREVIOUS CONVERSATION
  // ==========================================

  async function loadConversation(conversationId) {
    if (loading || conversationId === sessionId) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/sessions/${encodeURIComponent(
          conversationId
        )}/messages`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to load conversation."
        );
      }

      setMessages(data.messages);
      setSessionId(conversationId);
      setExpandedTraces({});
      setInput("");
    } catch (err) {
      setError(
        err.message || "Failed to load conversation."
      );
    } finally {
      setLoading(false);
    }
  }

  // ==========================================
  // START A NEW CONVERSATION
  // ==========================================
  
  function toggleTrace(messageIndex) {
    setExpandedTraces((previous) => ({
      ...previous,
      [messageIndex]: !previous[messageIndex],
    }));
  }

  function startNewChat() {
    if (loading) return;

    setSessionId(createSessionId());
    setExpandedTraces({});
    setMessages([]);
    setInput("");
    setError("");
  }

  // ==========================================
  // SEND A MESSAGE
  // ==========================================

  async function sendMessage() {
    const message = input.trim();

    if (!message || loading) return;

    const isFirstMessage = messages.length === 0;
    const currentSessionId = sessionId;

    setInput("");
    setError("");

    const userMessage = {
      role: "user",
      content: message,
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          message,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : "Unable to process your message.";

        throw new Error(detail);
      }

      // Display the successful assistant reply.
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: data.reply,
          metadata: data.metadata,
        },
      ]);

      // Save a new conversation only after success.
      if (isFirstMessage) {
        setConversations((previous) => {
          if (
            previous.some(
              (chat) =>
                chat.session_id === currentSessionId
            )
          ) {
            return previous;
          }

          const title =
            message.length > 35
              ? `${message.slice(0, 35)}...`
              : message;

          return [
            {
              session_id: currentSessionId,
              title,
            },
            ...previous,
          ];
        });
      }
    } catch (err) {
      // Failed requests are not saved by the backend.
      // Remove the optimistic user message as well.
      setMessages((previous) =>
        previous.slice(0, -1)
      );

      setInput(message);

      setError(
        err.message || "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  // ==========================================
  // APPLICATION INTERFACE
  // ==========================================

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Zap size={22} />
          </div>

          <div>
            <h2>Relay AI</h2>
            <span>Resilient Intelligence</span>
          </div>
        </div>

        <button
          type="button"
          className="new-chat-button"
          onClick={startNewChat}
          disabled={loading}
        >
          <Plus size={18} />
          New Conversation
        </button>

        {/* CONVERSATION HISTORY */}

        <div className="sidebar-section history-section">
          <div className="history-heading">
            <History size={15} />
            <p className="sidebar-label">
              RECENT CONVERSATIONS
            </p>
          </div>

          {conversations.length === 0 ? (
            <p className="history-empty">
              No conversations yet.
            </p>
          ) : (
            <div className="history-list">
              {conversations.map((conversation) => (
                <button
                  key={conversation.session_id}
                  type="button"
                  className={
                    "history-item " +
                    (conversation.session_id === sessionId
                      ? "active"
                      : "")
                  }
                  title={conversation.title}
                  disabled={loading}
                  onClick={() =>
                    loadConversation(
                      conversation.session_id
                    )
                  }
                >
                  <MessageSquare size={16} />

                  <span className="history-title">
                    {conversation.title}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* SYSTEM CAPABILITIES */}

        <div className="sidebar-section">
          <p className="sidebar-label">
            SYSTEM CAPABILITIES
          </p>

          <div className="sidebar-item">
            <Activity size={17} />
            Automatic Failover
          </div>

          <div className="sidebar-item">
            <Database size={17} />
            Response Caching
          </div>

          <div className="sidebar-item">
            <Cpu size={17} />
            Multi-Model AI
          </div>
        </div>

        <div className="sidebar-footer">
          <span className="status-dot" />
          <span>AI Gateway</span>
          <span className="status-label">
            Configured
          </span>
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <div>
            <h1>AI Workspace</h1>
            <p>
              Intelligent conversations with resilient
              infrastructure
            </p>
          </div>

          <div className="header-badge">
            <Activity size={15} />
            Multi-Provider
          </div>
        </header>

        <section className="chat-container">
          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">
                <Bot size={35} />
              </div>

              <h2>How can I help you today?</h2>

              <p>
                Powered by LiteLLM, with automatic provider
                failover and intelligent response caching.
              </p>
            </div>
          )}

          <div className="messages">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`message ${message.role}`}
                {...(message.role === "assistant"
                  ? { "data-testid": "assistant-message" }
                  : {})}
              >
                <div className="message-avatar">
                  {message.role === "assistant" ? (
                    <Bot size={19} />
                  ) : (
                    <User size={19} />
                  )}
                </div>

                <div className="message-body">
                  <div className="message-author">
                    {message.role === "assistant" ? "Relay AI" : "You"}
                  </div>

                  <div className="message-content">
                    {message.content}
                  </div>

                  {message.role === "assistant" && message.metadata && (
                    <div className="metadata">
                      <span className="metadata-item" data-testid="meta-source">
                        <Zap size={13} />
                        {message.metadata.resolution_source}
                      </span>
                      <span className="metadata-item" data-testid="meta-model">
                        <Cpu size={13} />
                        {message.metadata.model}
                      </span>
                      <span className="metadata-item" data-testid="meta-latency">
                        <Clock3 size={13} />
                        {message.metadata.latency_ms} ms
                      </span>
                      <span className="metadata-item">
                        Input: <span data-testid="meta-input-tokens">{message.metadata.input_tokens}</span>
                      </span>
                      <span className="metadata-item">
                        Output: <span data-testid="meta-output-tokens">{message.metadata.output_tokens}</span>
                      </span>
                    </div>
                  )}

                  {message.role === "assistant" &&
                    message.metadata?.failover_log?.length > 0 && (
                      <div className="gateway-diagnostics">
                        <button
                          type="button"
                          className="trace-toggle"
                          onClick={() => toggleTrace(index)}
                          aria-expanded={Boolean(expandedTraces[index])}
                        >
                          <ShieldCheck size={15} />
                          <span>Gateway Diagnostics</span>
                          <span className="trace-count">
                            {message.metadata.failover_log.length} attempt(s)
                          </span>
                          {expandedTraces[index] ? (
                            <ChevronUp size={15} />
                          ) : (
                            <ChevronDown size={15} />
                          )}
                        </button>

                        {expandedTraces[index] && (
                          <div className="trace-panel">
                            {message.metadata.failover_log.map((attempt, attemptIndex) => (
                              <div className="trace-entry" key={attemptIndex}>
                                <div className="trace-entry-top">
                                  <span className="trace-provider">
                                    {attempt.provider} · {attempt.key_id}
                                  </span>
                                  <span
                                    className={
                                      "trace-status " +
                                      (attempt.status === "SUCCESS"
                                        ? "trace-success"
                                        : "trace-failed")
                                    }
                                  >
                                    {attempt.status}
                                  </span>
                                </div>
                                <div className="trace-entry-details">
                                  <span>{attempt.reason}</span>
                                  <span>{attempt.duration_ms} ms</span>
                                  {attempt.simulated && (
                                    <span className="trace-simulated">Simulated</span>
                                  )}
                                </div>
                              </div>
                            ))}
                            <div className="trace-footer">
                              <span>Total request latency</span>
                              <strong>{message.metadata.latency_ms} ms</strong>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="loading-message">
                <LoaderCircle
                  size={18}
                  className="spinner"
                />
                Processing request...
              </div>
            )}

            {error && (
              <div
                className="error-message"
                role="alert"
              >
                {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </section>

        <div className="composer-container">
          <div className="composer">
            <textarea
              data-testid="chat-input"
              placeholder="Ask Relay AI anything..."
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              rows={1}
              maxLength={4000}
              disabled={loading}
            />

            <button
              type="button"
              data-testid="send-button"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              aria-label="Send message"
            >
              <Send size={19} />
            </button>
          </div>

          <p className="composer-note">
            Powered by LiteLLM • Gemini + Groq • SQLite
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;
