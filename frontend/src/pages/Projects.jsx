import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getProjects } from '../api/projects';

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchProjects = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getProjects();
      setProjects(data);
    } catch (err) {
      setError(err.data?.detail || 'Unable to load projects.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const formatStatus = (status) => {
    switch (status) {
      case 'active': return 'Active';
      case 'completed': return 'Completed';
      case 'archived': return 'Archived';
      default: return status;
    }
  };

  return (
    <div className="projects-page">
      <header className="page-header">
        <h1>Projects</h1>
        <p className="subtitle" style={{ textAlign: 'left', marginBottom: 0 }}>Projects available in your current workspace.</p>
      </header>

      <div className="page-content">
        {isLoading ? (
          <div className="loading-state">Loading projects...</div>
        ) : error ? (
          <div className="error-state">
            <p>{error}</p>
            <button onClick={fetchProjects} className="retry-btn">Retry</button>
          </div>
        ) : projects.length === 0 ? (
          <div className="empty-state">
            <h3>No projects yet</h3>
            <p>Projects you have access to will appear here.</p>
          </div>
        ) : (
          <div className="projects-grid">
            {projects.map((project) => (
              <Link key={project.id} to={`/projects/${project.id}`} className="project-card" style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                <div className="project-header">
                  <h3>{project.name}</h3>
                  <span className={`status-badge status-${project.status}`}>
                    {formatStatus(project.status)}
                  </span>
                </div>
                {project.description && (
                  <p className="project-description">{project.description}</p>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
