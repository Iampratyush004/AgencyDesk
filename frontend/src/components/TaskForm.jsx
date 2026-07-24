import React, { useState } from 'react';

export default function TaskForm({ initialData = {}, onSubmit, onCancel, isSaving }) {
  const [formData, setFormData] = useState({
    title: initialData.title || '',
    description: initialData.description || '',
    status: initialData.status || 'todo',
    priority: initialData.priority || 'medium',
    visibility: initialData.visibility || 'internal',
    due_date: initialData.due_date || ''
  });

  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }

    try {
      const payload = {
        title: formData.title,
        description: formData.description || null,
        status: formData.status,
        priority: formData.priority,
        visibility: formData.visibility,
        due_date: formData.due_date || null
      };

      await onSubmit(payload);
    } catch (err) {
      if (err.data && err.data.detail) {
        if (Array.isArray(err.data.detail)) {
          const messages = err.data.detail.map(d => `${d.loc.join('.')}: ${d.msg}`);
          setError(messages.join(', '));
        } else if (typeof err.data.detail === 'object') {
          if (err.data.detail.error) {
            setError(`${err.data.detail.error}${err.data.detail.blockers ? ` (${err.data.detail.blockers.join(', ')})` : ''}`);
          } else {
            setError(JSON.stringify(err.data.detail));
          }
        } else {
          setError(String(err.data.detail));
        }
      } else {
        setError('An unexpected error occurred while saving the task.');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="task-form">
      {error && (
        <div className="error-alert">
          {error}
        </div>
      )}

      <div className="form-group">
        <label htmlFor="title">Title *</label>
        <input
          id="title"
          name="title"
          type="text"
          value={formData.title}
          onChange={handleChange}
          required
          disabled={isSaving}
        />
      </div>

      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          name="description"
          value={formData.description}
          onChange={handleChange}
          disabled={isSaving}
          rows={3}
        />
      </div>

      <div className="form-row">
        <div className="form-group half">
          <label htmlFor="status">Status</label>
          <select id="status" name="status" value={formData.status} onChange={handleChange} disabled={isSaving}>
            <option value="todo">Todo</option>
            <option value="in_progress">In Progress</option>
            <option value="review">Review</option>
            <option value="done">Done</option>
          </select>
        </div>

        <div className="form-group half">
          <label htmlFor="priority">Priority</label>
          <select id="priority" name="priority" value={formData.priority} onChange={handleChange} disabled={isSaving}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="visibility">Visibility</label>
        <select id="visibility" name="visibility" value={formData.visibility} onChange={handleChange} disabled={isSaving}>
          <option value="internal">Internal — agency staff only</option>
          <option value="client">Client visible — visible in the client portal</option>
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="due_date">Due Date</label>
        <input
          id="due_date"
          name="due_date"
          type="date"
          value={formData.due_date}
          onChange={handleChange}
          disabled={isSaving}
        />
      </div>

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Task'}
        </button>
      </div>
    </form>
  );
}
