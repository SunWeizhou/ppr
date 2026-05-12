import { useRef } from "preact/hooks";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function AgentInput({ onSend, disabled }: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const el = inputRef.current;
    if (!el) return;
    const value = el.value.trim();
    if (!value || disabled) return;
    onSend(value);
    el.value = "";
    el.style.height = "auto";
  }

  function handleInput() {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  return (
    <form class="ap-composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        ref={inputRef}
        class="ap-composer-input"
        placeholder="Ask Paper Agent..."
        rows={1}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
      />
      <button
        type="submit"
        class="ap-composer-send"
        disabled={disabled}
        aria-label="Send message"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </form>
  );
}
