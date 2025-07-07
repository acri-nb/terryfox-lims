import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  TextField,
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Add,
  Search,
  MoreVert,
  Edit,
  Delete,
  Visibility,
  FolderOpen,
  Person,
  CalendarToday,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

interface Project {
  id: number;
  name: string;
  description: string;
  project_lead: {
    id: number;
    name: string;
  } | null;
  created_at: string;
  updated_at: string;
  created_by: {
    id: number;
    username: string;
  };
  cases_count: number;
}

interface ProjectLead {
  id: number;
  name: string;
}

const Projects: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectLeads, setProjectLeads] = useState<ProjectLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLead, setSelectedLead] = useState('');
  const [error, setError] = useState('');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState<'create' | 'edit' | 'delete'>('create');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    project_lead_id: '',
  });

  const fetchProjects = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (searchTerm) params.append('name', searchTerm);
      if (selectedLead) params.append('project_lead', selectedLead);

      const response = await axios.get(`/projects/?${params.toString()}`);
      setProjects(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching projects:', error);
      setError('Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedLead]);

  const fetchProjectLeads = useCallback(async () => {
    try {
      const response = await axios.get('/project-leads/');
      setProjectLeads(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching project leads:', error);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
    fetchProjectLeads();
  }, [fetchProjects, fetchProjectLeads]);

  useEffect(() => {
    const delayedSearch = setTimeout(() => {
      fetchProjects();
    }, 300);

    return () => clearTimeout(delayedSearch);
  }, [fetchProjects]);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, project: Project) => {
    setAnchorEl(event.currentTarget);
    setSelectedProject(project);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedProject(null);
  };

  const handleDialogOpen = (type: 'create' | 'edit' | 'delete', project?: Project) => {
    setDialogType(type);
    if (project) {
      setSelectedProject(project);
      setFormData({
        name: project.name,
        description: project.description,
        project_lead_id: project.project_lead?.id.toString() || '',
      });
    } else {
      setFormData({
        name: '',
        description: '',
        project_lead_id: '',
      });
    }
    setDialogOpen(true);
    handleMenuClose();
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedProject(null);
    setFormData({
      name: '',
      description: '',
      project_lead_id: '',
    });
    setError('');
  };

  const handleSubmit = async () => {
    try {
      const data = {
        ...formData,
        project_lead_id: formData.project_lead_id ? parseInt(formData.project_lead_id) : null,
      };

      if (dialogType === 'create') {
        await axios.post('/projects/', data);
      } else if (dialogType === 'edit' && selectedProject) {
        await axios.put(`/projects/${selectedProject.id}/`, data);
      } else if (dialogType === 'delete' && selectedProject) {
        await axios.delete(`/projects/${selectedProject.id}/`);
      }

      handleDialogClose();
      fetchProjects();
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Operation failed');
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Projects
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" fontWeight="bold">
          Projects ({projects.length})
        </Typography>
        {state.user?.permissions.can_edit && (
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => handleDialogOpen('create')}
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%)',
              },
            }}
          >
            New Project
          </Button>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Search and Filter */}
      <Box display="flex" gap={2} mb={3}>
        <TextField
          placeholder="Search projects..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
          sx={{ flexGrow: 1 }}
        />
        <FormControl sx={{ minWidth: 200 }}>
          <InputLabel>Project Lead</InputLabel>
          <Select
            value={selectedLead}
            onChange={(e) => setSelectedLead(e.target.value)}
            label="Project Lead"
          >
            <MenuItem value="">All Leads</MenuItem>
            {projectLeads.map((lead) => (
              <MenuItem key={lead.id} value={lead.id}>
                {lead.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* Projects Grid */}
      <Box
        display="grid"
        gridTemplateColumns="repeat(auto-fill, minmax(350px, 1fr))"
        gap={3}
      >
        {projects.map((project) => (
          <Card key={project.id} sx={{ height: 'fit-content' }}>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                <Typography variant="h6" fontWeight="bold" sx={{ flexGrow: 1 }}>
                  {project.name}
                </Typography>
                <IconButton
                  size="small"
                  onClick={(e) => handleMenuOpen(e, project)}
                >
                  <MoreVert />
                </IconButton>
              </Box>

              <Typography color="text.secondary" sx={{ mb: 2, minHeight: 40 }}>
                {project.description || 'No description provided'}
              </Typography>

              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Person fontSize="small" color="action" />
                <Typography variant="body2">
                  {project.project_lead?.name || 'No lead assigned'}
                </Typography>
              </Box>

              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <CalendarToday fontSize="small" color="action" />
                <Typography variant="body2">
                  {new Date(project.created_at).toLocaleDateString()}
                </Typography>
              </Box>

              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Chip
                  icon={<FolderOpen />}
                  label={`${project.cases_count} Cases`}
                  color="primary"
                  variant="outlined"
                />
                <Button
                  size="small"
                  onClick={() => navigate(`/projects/${project.id}`)}
                  endIcon={<Visibility />}
                >
                  View Details
                </Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      {projects.length === 0 && (
        <Box textAlign="center" py={8}>
          <FolderOpen sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No projects found
          </Typography>
          <Typography color="text.secondary">
            {searchTerm || selectedLead
              ? 'Try adjusting your search criteria'
              : 'Create your first project to get started'}
          </Typography>
        </Box>
      )}

      {/* Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => navigate(`/projects/${selectedProject?.id}`)}>
          <Visibility fontSize="small" sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        {state.user?.permissions.can_edit && (
          <>
            <MenuItem onClick={() => handleDialogOpen('edit', selectedProject!)}>
              <Edit fontSize="small" sx={{ mr: 1 }} />
              Edit
            </MenuItem>
            <MenuItem onClick={() => handleDialogOpen('delete', selectedProject!)}>
              <Delete fontSize="small" sx={{ mr: 1 }} />
              Delete
            </MenuItem>
          </>
        )}
      </Menu>

      {/* Create/Edit/Delete Dialog */}
      <Dialog open={dialogOpen} onClose={handleDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          {dialogType === 'create' && 'Create New Project'}
          {dialogType === 'edit' && 'Edit Project'}
          {dialogType === 'delete' && 'Delete Project'}
        </DialogTitle>
        <DialogContent>
          {dialogType === 'delete' ? (
            <Typography>
              Are you sure you want to delete "{selectedProject?.name}"? This action cannot be undone.
            </Typography>
          ) : (
            <Box sx={{ pt: 1 }}>
              <TextField
                fullWidth
                label="Project Name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                margin="normal"
                multiline
                rows={3}
              />
              <FormControl fullWidth margin="normal">
                <InputLabel>Project Lead</InputLabel>
                <Select
                  value={formData.project_lead_id}
                  onChange={(e) => setFormData({ ...formData, project_lead_id: e.target.value })}
                  label="Project Lead"
                >
                  <MenuItem value="">No Lead</MenuItem>
                  {projectLeads.map((lead) => (
                    <MenuItem key={lead.id} value={lead.id}>
                      {lead.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            color={dialogType === 'delete' ? 'error' : 'primary'}
          >
            {dialogType === 'create' && 'Create'}
            {dialogType === 'edit' && 'Save'}
            {dialogType === 'delete' && 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Projects; 