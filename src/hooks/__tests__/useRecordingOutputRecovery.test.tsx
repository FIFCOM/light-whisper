import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  handlers: new Map<string, (event: { payload: unknown }) => void>(),
  notify: vi.fn<(message: unknown, options?: {
    action?: { label: unknown; onClick: () => unknown };
  }) => void>(),
  copyToClipboard: vi.fn<(text: string) => Promise<string>>(),
  pasteText: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: async (event: string, handler: (event: { payload: unknown }) => void) => {
    mocks.handlers.set(event, handler);
    return () => mocks.handlers.delete(event);
  },
}));
vi.mock("@/api/tauri", () => ({
  startRecording: vi.fn(),
  stopRecording: vi.fn(),
  copyToClipboard: mocks.copyToClipboard,
  pasteText: mocks.pasteText,
}));
vi.mock("sonner", () => ({
  toast: Object.assign(mocks.notify, {
    warning: mocks.notify,
    error: mocks.notify,
    info: mocks.notify,
    message: mocks.notify,
    success: mocks.notify,
  }),
}));
vi.mock("@/i18n", () => ({ default: { t: (key: string) => key } }));

import { useRecording } from "@/hooks/useRecording";

beforeEach(() => {
  mocks.handlers.clear();
  mocks.notify.mockClear();
  mocks.pasteText.mockReset();
  mocks.copyToClipboard.mockReset().mockResolvedValue("copied");
});

function emit(event: string, payload: unknown) {
  act(() => mocks.handlers.get(event)?.({ payload }));
}

describe("useRecording deferred output recovery", () => {
  it.each(["target_changed", "target_unknown", "paste_failed"])(
    "keeps older dictation recoverable after a later assistant session for %s",
    async (reason) => {
      const { result } = renderHook(() => useRecording());
      await act(async () => { await Promise.resolve(); });

      emit("recording-state", {
        sessionId: 42,
        revision: 2,
        isRecording: true,
        isProcessing: false,
        mode: "assistant",
      });
      emit("recording-state", {
        sessionId: 42,
        revision: 3,
        isRecording: false,
        isProcessing: true,
        mode: "assistant",
      });
      emit("transcription-result", {
        sessionId: 42,
        text: "Assistant answer",
        interim: false,
        mode: "assistant",
      });
      emit("recording-state", {
        sessionId: 42,
        revision: 4,
        isRecording: false,
        isProcessing: false,
        mode: "assistant",
      });

      const originalText = "  旧听写 A\nOriginal punctuation!  ";
      emit("paste-recovery", { sessionId: 41, text: originalText, reason });

      expect(result.current.transcriptionResult).toBe("Assistant answer");
      expect(result.current.history.map(({ text }) => text)).toEqual(["Assistant answer"]);
      expect(result.current.isRecording).toBe(false);
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.resultMode).toBe("assistant");
      expect(mocks.notify).toHaveBeenCalledOnce();
      const options = mocks.notify.mock.calls[0][1];
      expect(options?.action).toEqual(expect.objectContaining({
        label: expect.anything(),
        onClick: expect.any(Function),
      }));
      expect(mocks.copyToClipboard).not.toHaveBeenCalled();
      expect(mocks.pasteText).not.toHaveBeenCalled();

      await act(async () => { await options!.action!.onClick(); });
      expect(mocks.copyToClipboard).toHaveBeenCalledExactlyOnceWith(originalText);
      expect(mocks.pasteText).not.toHaveBeenCalled();
      expect(result.current.transcriptionResult).toBe("Assistant answer");
      expect(result.current.history.map(({ text }) => text)).toEqual(["Assistant answer"]);
      expect(result.current.isRecording).toBe(false);
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.resultMode).toBe("assistant");
    },
  );

  it("ignores a recovery event after the hook unmounts", async () => {
    const { unmount } = renderHook(() => useRecording());
    await act(async () => { await Promise.resolve(); });
    const handler = mocks.handlers.get("paste-recovery");
    expect(handler).toBeDefined();
    unmount();

    act(() => handler!({
      payload: { sessionId: 41, text: "Retired dictation", reason: "target_changed" },
    }));

    expect(mocks.notify).not.toHaveBeenCalled();
    expect(mocks.copyToClipboard).not.toHaveBeenCalled();
  });
});
