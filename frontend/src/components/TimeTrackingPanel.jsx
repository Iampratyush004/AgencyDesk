import React, { useState, useEffect } from 'react';
import { createTimeEntry } from '../api/timeEntries';

export default function TimeTrackingPanel({ task, onTimeLogged }) {
  const [duration, setDuration] = useState('');
  const [note, setNote] = useState('');
  const [date, setDate] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [successMsg, setSuccessMsg] = useState('');

  // Set default local date on mount
  useEffect(() => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    setDate(`${year}-${month}-${day}`);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!duration || !date) return;

    setIsSubmitting(true);
    setSubmitError(null);
    setSuccessMsg('');

    try {
      const payload = {
        duration_minutes: parseInt(duration, 10),
        date: date,
        note: note.trim() || null
      };

      await createTimeEntry(task.id, payload);

      // Reset form on success
      setDuration('');
      setNote('');
      setSuccessMsg('Time logged successfully!');

      // Notify parent to refresh project hours summary
      if (onTimeLogged) {
        onTimeLogged();
      }

      // Clear success message after a few seconds
      setTimeout(() => setSuccessMsg(''), 3000);

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
        setSubmitError('An unexpected error occurred while logging time.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="time-tracking-panel" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
      <h3>Log Time</h3>
      <form onSubmit={handleSubmit} className="time-form" style={{ marginTop: '1rem' }}>
        {submitError && (
          <div className="error-alert" style={{marginBottom: '1rem', padding: '0.5rem'}}>
            {submitError}
          </div>
        )}
        {successMsg && (
          <div className="success-alert" style={{marginBottom: '1rem', padding: '0.5rem', backgroundColor: '#e6fffa', color: '#234e52', border: '1px solid #b2f5ea', borderRadius: '4px'}}>
            {successMsg}
          </div>
        )}

        <div className="form-row">
          <div className="form-group half">
            <label htmlFor="duration">Duration (minutes) *</label>
            <input
              id="duration"
              type="number"
              min="1"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="e.g. 60"
              disabled={isSubmitting}
              required
              style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '1rem' }}
            />
          </div>

          <div className="form-group half">
            <label htmlFor="date">Date *</label>
            <input
              id="date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              disabled={isSubmitting}
              required
              style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '1rem' }}
            />
          </div>
        </div>

        <div className="form-group" style={{marginTop: '1rem'}}>
          <label htmlFor="note">Note (optional)</label>
          <textarea
            id="note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What did you work on?"
            rows={2}
            disabled={isSubmitting}
          />
        </div>

        <div className="form-actions" style={{marginTop: '1rem'}}>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting || !duration || !date}>
            {isSubmitting ? 'Saving...' : 'Log Time'}
          </button>
        </div>
      </form>
    </div>
  );
}
