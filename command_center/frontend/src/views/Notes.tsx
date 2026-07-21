import { useState, type FormEvent, type KeyboardEvent } from "react";
import { api, ApiError } from "../api/client";
import { useApi } from "../api/hooks";
import { useToast } from "../components/ToastProvider";
import { EmptyNote, ErrorState, Loading } from "../components/atoms";
import { relativeTime } from "../lib/format";

interface Props {
  onUnauthorized: () => void;
}

export function NotesView({ onUnauthorized }: Props) {
  const { data, error, loading, reload } = useApi(api.notes, onUnauthorized);
  const { notify } = useToast();
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);

  const notes = data
    ? [...data].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    : [];

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = body.trim();
    if (!text || saving) return;
    setSaving(true);
    try {
      await api.createNote({ body: text });
      setBody("");
      notify("Note saved to your notes.");
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return onUnauthorized();
      notify(err instanceof Error ? err.message : "Could not save the note.");
    } finally {
      setSaving(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void submit(e as unknown as FormEvent);
    }
  }

  return (
    <section className="view" aria-label="Notes">
      <div className="view-head">
        <h1>Notes</h1>
        <p className="sub">
          Your own thoughts, jotted for the record. Append-only, newest first.
          Text only in v1 — file and image attachments are deferred with blob
          storage.
        </p>
      </div>
      <div className="view-scroll">
        <form className="note-compose" onSubmit={submit}>
          <label className="lbl" htmlFor="noteInput">
            new note
          </label>
          <textarea
            id="noteInput"
            className="ta"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="A thought, a direction, a reminder to yourself — anything. Cmd/Ctrl+Enter to save."
          />
          <div className="note-compose-foot">
            <span className="hint">Saved to your notes; not sent to the team.</span>
            <button type="submit" className="btn btn-gate" disabled={saving || !body.trim()}>
              {saving ? "Saving…" : "Save note"}
            </button>
          </div>
        </form>

        {loading && <Loading label="loading notes" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && notes.length === 0 && (
          <EmptyNote title="No notes yet" body="Your first thought will dock here, newest first." />
        )}
        {notes.length > 0 && (
          <ol className="note-list" aria-label="Your notes, newest first">
            {notes.map((note) => (
              <li className="note-item" key={note.id}>
                <div className="nbody">{note.body}</div>
                <div className="nfoot">
                  {relativeTime(note.created_at)}
                  {note.context ? ` · ${note.context}` : ""}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
