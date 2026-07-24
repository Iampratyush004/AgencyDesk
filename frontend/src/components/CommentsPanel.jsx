import React, { useState, useEffect } from 'react';
import { getComments, createComment } from '../api/comments';

export default function CommentsPanel({ task, userContext }) {
  const [comments, setComments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [newComment, setNewComment] = useState('');
  const [visibility, setVisibility] = useState('internal');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const isClient = userContext?.role === 'client_user';

  const fetchComments = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getComments(task.id);
      setComments(data);
    } catch (err) {
      setError('Unable to load comments.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (task && task.id) {
      fetchComments();
    }
  }, [task?.id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const payload = {
        content: newComment.trim()
      };

      if (!isClient) {
        payload.visibility = visibility;
      }

      const created = await createComment(task.id, payload);
      setComments([...comments, created]);
      setNewComment('');
      if (!isClient) {
        setVisibility('internal');
      }
    } catch (err) {
      if (err.data && err.data.detail) {
        if (Array.isArray(err.data.detail)) {
          const messages = err.data.detail.map(d => `${d.loc.join('.')}: ${d.msg}`);
          setSubmitError(messages.join(', '));
        } else if (typeof err.data.detail === 'object') {
          if (err.data.detail.error) {
            setSubmitError(`${err.data.detail.error}${err.data.detail.blockers ? ` (${err.data.detail.blockers.join(', ')})` : ''}`);
          } else {
            setSubmitError(JSON.stringify(err.data.detail));
          }
        } else {
          setSubmitError(String(err.data.detail));
        }
      } else {
        setSubmitError('An unexpected error occurred while saving the comment.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatDateTime = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  if (isLoading) {
    return <div className="comments-panel"><div className="loading-state" style={{padding: '1rem'}}>Loading comments...</div></div>;
  }

  if (error) {
    return (
      <div className="comments-panel">
        <div className="error-state" style={{padding: '1rem'}}>
          <p>{error}</p>
          <button onClick={fetchComments} className="retry-btn">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="comments-panel">
      <h3>Comments</h3>

      <div className="comments-list">
        {comments.length === 0 ? (
          <div className="empty-state" style={{padding: '1rem'}}>No comments yet.</div>
        ) : (
          comments.map(c => (
            <div key={c.id} className="comment-item">
              <div className="comment-header">
                <div className="comment-meta">
                  {c.visibility && (
                    <span className={`visibility-badge visibility-${c.visibility}`}>
                      {c.visibility === 'client' ? 'Client visible' : 'Internal'}
                    </span>
                  )}
                </div>
                <span className="comment-timestamp">{formatDateTime(c.created_at)}</span>
              </div>
              <div className="comment-content">{c.content}</div>
            </div>
          ))
        )}
      </div>

      <form onSubmit={handleSubmit} className="comment-form">
        {submitError && (
          <div className="error-alert" style={{marginBottom: '1rem', padding: '0.5rem'}}>
            {submitError}
          </div>
        )}

        <div className="form-group">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Write a comment..."
            rows={3}
            disabled={isSubmitting}
            required
          />
        </div>

        {!isClient && (
          <div className="form-group" style={{marginTop: '1rem'}}>
            <label htmlFor="visibility">Visibility</label>
            <select
              id="visibility"
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="internal">Internal — agency staff only</option>
              <option value="client">Client visible — visible in the client portal</option>
            </select>
          </div>
        )}

        <div className="form-actions" style={{marginTop: '1rem'}}>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting || !newComment.trim()}>
            {isSubmitting ? 'Posting...' : 'Post Comment'}
          </button>
        </div>
      </form>
    </div>
  );
}
