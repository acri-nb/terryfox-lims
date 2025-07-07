import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  ArrowBack,
  Add,
  Science,
  Person,
  CalendarToday,
} from '@mui/icons-material';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

interface Case {
  id: number;
  name: string;
  status: string;
  status_display: string;
  tier: string;
  tier_display: string;
  rna_coverage: number | null;
  dna_t_coverage: number | null;
  dna_n_coverage: number | null;
  created_at: string;
}

interface Project {
  id: number;
  name: string;
  description: string;
  project_lead: {
    id: number;
    name: string;
  } | null;
  created_at: string;
  created_by: {
    id: number;
    username: string;
  };
  cases: Case[];
  cases_count: number;
}

const ProjectDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { state } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchProject = useCallback(async () => {
    try {
      const response = await axios.get(`/projects/${id}/`);
      setProject(response.data);
    } catch (error) {
      console.error('Error fetching project:', error);
      setError('Failed to load project');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) {
      fetchProject();
    }
  }, [id, fetchProject]);

  const getStatusColor = (status: string) => {
    const colors: { [key: string]: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' } = {
      received: 'warning',
      library_prepped: 'info',
      transferred_to_nfl: 'secondary',
      bioinfo_analysis: 'error',
      completed: 'success',
    };
    return colors[status] || 'default';
  };

  const getTierColor = (tier: string) => {
    const colors: { [key: string]: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' } = {
      A: 'success',
      B: 'warning',
      FAIL: 'error',
    };
    return colors[tier] || 'default';
  };

  if (loading) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/projects')}
          sx={{ mb: 2 }}
        >
          Back to Projects
        </Button>
        <Typography variant="h4" gutterBottom>
          Loading Project...
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  if (error || !project) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/projects')}
          sx={{ mb: 2 }}
        >
          Back to Projects
        </Button>
        <Alert severity="error">{error || 'Project not found'}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate('/projects')}
        sx={{ mb: 2 }}
      >
        Back to Projects
      </Button>

      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" fontWeight="bold">
          {project.name}
        </Typography>
        {state.user?.permissions.can_edit && (
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => navigate(`/cases?project=${project.id}`)}
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%)',
              },
            }}
          >
            Add Case
          </Button>
        )}
      </Box>

      {/* Project Info */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Project Information
          </Typography>
          
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {project.description || 'No description provided'}
          </Typography>

          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Person fontSize="small" color="action" />
            <Typography variant="body2">
              <strong>Project Lead:</strong> {project.project_lead?.name || 'Not assigned'}
            </Typography>
          </Box>

          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <CalendarToday fontSize="small" color="action" />
            <Typography variant="body2">
              <strong>Created:</strong> {new Date(project.created_at).toLocaleDateString()}
            </Typography>
          </Box>

          <Box display="flex" alignItems="center" gap={1}>
            <Person fontSize="small" color="action" />
            <Typography variant="body2">
              <strong>Created by:</strong> {project.created_by.username}
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Cases */}
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              Cases ({project.cases.length})
            </Typography>
          </Box>

          {project.cases.length === 0 ? (
            <Box textAlign="center" py={4}>
              <Science sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
              <Typography variant="h6" color="text.secondary">
                No cases yet
              </Typography>
              <Typography color="text.secondary">
                Add your first case to get started
              </Typography>
            </Box>
          ) : (
            <Box
              display="grid"
              gridTemplateColumns="repeat(auto-fill, minmax(300px, 1fr))"
              gap={2}
            >
              {project.cases.map((case_) => (
                <Card
                  key={case_.id}
                  variant="outlined"
                  sx={{
                    cursor: 'pointer',
                    '&:hover': {
                      boxShadow: 2,
                    },
                  }}
                  onClick={() => navigate(`/cases/${case_.id}`)}
                >
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      {case_.name}
                    </Typography>

                    <Box display="flex" gap={1} mb={2}>
                      <Chip
                        label={case_.status_display}
                        color={getStatusColor(case_.status)}
                        size="small"
                      />
                      <Chip
                        label={`Tier ${case_.tier}`}
                        color={getTierColor(case_.tier)}
                        size="small"
                      />
                    </Box>

                    <Typography variant="body2" color="text.secondary">
                      RNA: {case_.rna_coverage || '--'} M |{' '}
                      DNA(T): {case_.dna_t_coverage || '--'} X |{' '}
                      DNA(N): {case_.dna_n_coverage || '--'} X
                    </Typography>

                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      Created: {new Date(case_.created_at).toLocaleDateString()}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default ProjectDetail; 