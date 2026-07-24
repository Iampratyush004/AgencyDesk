import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getProject, getProjectDashboard } from '../api/projects';
import { getProjectTasks, createTask, updateTask } from '../api/tasks';
import { useAuth } from '../auth/AuthContext';
import TaskForm from '../components/TaskForm';
import CommentsPanel from '../components/CommentsPanel';
import TimeTrackingPanel from '../components/TimeTrackingPanel';
import FilesPanel from '../components/FilesPanel';

export default function ProjectDetail() {
  const { projectId } = useParams();
  const { userContext } = useAuth();

  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isNotFound, setIsNotFound] = useState(false);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [viewingTask, setViewingTask] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    setIsNotFound(false);

    try {
      const [projectData, tasksData, dashboardData] = await Promise.all([
        getProject(projectId),
        getProjectTasks(projectId),
        getProjectDashboard(projectId)
      ]);
      setProject(projectData);
      setTasks(tasksData);
      setDashboard(dashboardData);
    } catch (err) {
      if (err.status === 404) {
        setIsNotFound(true);
      } else {
        setError('Unable to load project.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDashboard = async () => {
    try {
      const dashboardData = await getProjectDashboard(projectId);
      setDashboard(dashboardData);
    } catch (err) {
      console.error("Failed to refresh dashboard");
    }
  };

  useEffect(() => {
    fetchData();
  }, [projectId]);

  const handleCreateTask = async (payload) => {
    setIsSaving(true);
    try {
      await createTask(projectId, payload);
      setIsCreateModalOpen(false);
      const newTasks = await getProjectTasks(projectId);
      setTasks(newTasks);
      await fetchDashboard();
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdateTask = async (payload) => {
    setIsSaving(true);
    try {
      await updateTask(editingTask.id, payload);
      setEditingTask(null);
      const newTasks = await getProjectTasks(projectId);
      setTasks(newTasks);
      await fetchDashboard();
    } finally {
      setIsSaving(false);
    }
  };

  const formatStatus = (status) => {
    switch (status) {
      case 'active': return 'Active';
      case 'completed': return 'Completed';
      case 'archived': return 'Archived';
      case 'todo': return 'Todo';
      case 'in_progress': return 'In Progress';
      case 'review': return 'Review';
      case 'done': return 'Done';
      default: return status;
    }
  };

  const formatPriority = (priority) => {
    switch (priority) {
      case 'low': return 'Low';
      case 'medium': return 'Medium';
      case 'high': return 'High';
      case 'urgent': return 'Urgent';
      default: return priority;
    }
  };

  const formatVisibility = (visibility) => {
    switch (visibility) {
      case 'internal': return 'Internal';
      case 'client': return 'Client visible';
      default: return visibility;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return null;
    const [year, month, day] = dateString.split('-');
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatMinutesToHours = (minutes) => {
    if (!minutes) return '0h 0m';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours === 0) return `${mins}m`;
    if (mins === 0) return `${hours}h`;
    return `${hours}h ${mins}m`;
  };

  if (isLoading) {
    return (
      <div className="project-detail-page">
        <div className="loading-state">Loading project...</div>
      </div>
    );
  }

  if (isNotFound) {
    return (
      <div className="project-detail-page">
        <div className="error-state">
          <h3 style={{color: 'var(--text-main)', marginBottom: '0.5rem'}}>Project not found</h3>
          <p>This project does not exist or you don't have access to it.</p>
          <Link to="/projects" className="retry-btn" style={{ display: 'inline-block', textDecoration: 'none' }}>
            Back to Projects
          </Link>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="project-detail-page">
        <div className="error-state">
          <p>{error}</p>
          <button onClick={fetchData} className="retry-btn">Retry</button>
        </div>
      </div>
    );
  }

  const columns = [
    { id: 'todo', title: 'Todo' },
    { id: 'in_progress', title: 'In Progress' },
    { id: 'review', title: 'Review' },
    { id: 'done', title: 'Done' }
  ];

  const canMutateTasks = userContext?.role === 'agency_admin' || userContext?.role === 'agency_member';

  return (
    <div className="project-detail-page">
      <div className="project-detail-header" style={{ marginBottom: '2rem' }}>
        <Link to="/projects" className="back-link" style={{ display: 'inline-block', marginBottom: '1rem', color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.875rem' }}>&larr; Back to Projects</Link>
        <div className="project-title-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.5rem' }}>
          <div className="header-actions">
            <h1 style={{ margin: 0, fontSize: '1.5rem' }}>{project.name}</h1>
            <span className={`status-badge status-${project.status}`}>
              {formatStatus(project.status)}
            </span>
          </div>
          {canMutateTasks && (
            <button className="btn btn-primary" onClick={() => setIsCreateModalOpen(true)}>
              Create Task
            </button>
          )}
        </div>
        {project.description && (
          <p className="project-description-large" style={{ color: 'var(--text-muted)' }}>{project.description}</p>
        )}

        {dashboard && (
          <div className="project-dashboard-metrics" style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div className="metric-card" style={{ padding: '1rem', backgroundColor: 'var(--bg-color)', borderRadius: '8px', border: '1px solid var(--border)', minWidth: '100px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '600' }}>Todo</div>
              <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-main)', marginTop: '0.25rem' }}>{dashboard.task_counts.todo}</div>
            </div>
            <div className="metric-card" style={{ padding: '1rem', backgroundColor: 'var(--bg-color)', borderRadius: '8px', border: '1px solid var(--border)', minWidth: '100px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '600' }}>In Progress</div>
              <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-main)', marginTop: '0.25rem' }}>{dashboard.task_counts.in_progress}</div>
            </div>
            <div className="metric-card" style={{ padding: '1rem', backgroundColor: 'var(--bg-color)', borderRadius: '8px', border: '1px solid var(--border)', minWidth: '100px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '600' }}>Review</div>
              <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-main)', marginTop: '0.25rem' }}>{dashboard.task_counts.review}</div>
            </div>
            <div className="metric-card" style={{ padding: '1rem', backgroundColor: 'var(--bg-color)', borderRadius: '8px', border: '1px solid var(--border)', minWidth: '100px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '600' }}>Done</div>
              <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-main)', marginTop: '0.25rem' }}>{dashboard.task_counts.done}</div>
            </div>
            {dashboard.hours_logged !== undefined && (
              <div className="metric-card" style={{ padding: '1rem', backgroundColor: 'var(--bg-color)', borderRadius: '8px', border: '1px solid var(--border)', minWidth: '100px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '600' }}>Time Logged</div>
                <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-main)', marginTop: '0.25rem' }}>{formatMinutesToHours(dashboard.hours_logged)}</div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="task-board">
        {columns.map((col) => {
          const columnTasks = tasks.filter(t => t.status === col.id);

          return (
            <div key={col.id} className="task-column">
              <div className="column-header">
                <h3>{col.title}</h3>
                <span className="task-count">{columnTasks.length}</span>
              </div>

              <div className="column-content">
                {columnTasks.length === 0 ? (
                  <div className="empty-column">No tasks</div>
                ) : (
                  columnTasks.map(task => (
                    <div key={task.id} className="task-card">
                      <div className="task-card-header">
                        <h4>{task.title}</h4>
                        <div className="header-actions">
                          <button className="edit-action" onClick={() => setViewingTask(task)}>Details</button>
                          {canMutateTasks && (
                            <button className="edit-action" onClick={() => setEditingTask(task)}>Edit</button>
                          )}
                        </div>
                      </div>

                      <div className="task-meta">
                        <span className={`priority-badge priority-${task.priority}`}>
                          {formatPriority(task.priority)}
                        </span>

                        {task.visibility && (
                          <span className={`visibility-badge visibility-${task.visibility}`}>
                            {formatVisibility(task.visibility)}
                          </span>
                        )}
                      </div>

                      {task.due_date && (
                        <div className="task-due-date">
                          Due: {formatDate(task.due_date)}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {isCreateModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Create Task</h2>
            </div>
            <div className="modal-body">
              <TaskForm
                onSubmit={handleCreateTask}
                onCancel={() => setIsCreateModalOpen(false)}
                isSaving={isSaving}
              />
            </div>
          </div>
        </div>
      )}

      {editingTask && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Edit Task</h2>
            </div>
            <div className="modal-body">
              <TaskForm
                initialData={editingTask}
                onSubmit={handleUpdateTask}
                onCancel={() => setEditingTask(null)}
                isSaving={isSaving}
              />
            </div>
          </div>
        </div>
      )}

      {viewingTask && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Task Details</h2>
              <button className="back-btn" onClick={() => setViewingTask(null)} style={{fontSize: '1rem'}}>&times;</button>
            </div>
            <div className="modal-body">
              <h3 style={{marginBottom: '1rem', fontSize: '1.25rem'}}>{viewingTask.title}</h3>

              <div className="task-meta" style={{marginBottom: '1rem'}}>
                <span className={`status-badge status-${viewingTask.status}`}>
                  {formatStatus(viewingTask.status)}
                </span>
                <span className={`priority-badge priority-${viewingTask.priority}`}>
                  {formatPriority(viewingTask.priority)}
                </span>
                {viewingTask.visibility && (
                  <span className={`visibility-badge visibility-${viewingTask.visibility}`}>
                    {formatVisibility(viewingTask.visibility)}
                  </span>
                )}
              </div>

              {viewingTask.description && (
                <div style={{marginBottom: '1.5rem', whiteSpace: 'pre-wrap', color: 'var(--text-muted)'}}>
                  {viewingTask.description}
                </div>
              )}

              {canMutateTasks && (
                <TimeTrackingPanel task={viewingTask} onTimeLogged={fetchDashboard} />
              )}

              <FilesPanel task={viewingTask} userContext={userContext} />

              <CommentsPanel task={viewingTask} userContext={userContext} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
