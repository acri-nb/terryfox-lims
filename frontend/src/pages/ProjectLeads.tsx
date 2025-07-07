import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Add,
  MoreVert,
  Edit,
  Delete,
  Person,
  FolderOpen,
} from '@mui/icons-material';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

interface ProjectLead {
  id: number;
  name: string;
}

const ProjectLeads: React.FC = () => {
  const [leads, setLeads] = useState<ProjectLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedLead, setSelectedLead] = useState<ProjectLead | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState<'create' | 'edit' | 'delete'>('create');
  const [formData, setFormData] = useState({ name: '' });
  const [error, setError] = useState('');

  const { state } = useAuth();

  useEffect(() => {
    fetchLeads();
  }, []);

  const fetchLeads = async () => {
    try {
      const response = await axios.get('/project-leads/');
      setLeads(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching project leads:', error);
      setError('Failed to load project leads');
    } finally {
      setLoading(false);
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, lead: ProjectLead) => {
    setAnchorEl(event.currentTarget);
    setSelectedLead(lead);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedLead(null);
  };

  const handleDialogOpen = (type: 'create' | 'edit' | 'delete', lead?: ProjectLead) => {
    setDialogType(type);
    if (lead) {
      setSelectedLead(lead);
      setFormData({ name: lead.name });
    } else {
      setFormData({ name: '' });
    }
    setDialogOpen(true);
    handleMenuClose();
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedLead(null);
    setFormData({ name: '' });
    setError('');
  };

  const handleSubmit = async () => {
    try {
      if (dialogType === 'create') {
        await axios.post('/project-leads/', formData);
      } else if (dialogType === 'edit' && selectedLead) {
        await axios.put(`/project-leads/${selectedLead.id}/`, formData);
      } else if (dialogType === 'delete' && selectedLead) {
        await axios.delete(`/project-leads/${selectedLead.id}/`);
      }

      handleDialogClose();
      fetchLeads();
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Operation failed');
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Project Leads
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" fontWeight="bold">
          Project Leads ({leads.length})
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
            New Project Lead
          </Button>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Project Leads Grid */}
      <Box
        display="grid"
        gridTemplateColumns="repeat(auto-fill, minmax(300px, 1fr))"
        gap={3}
      >
        {leads.map((lead) => (
          <Card key={lead.id}>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Person color="primary" />
                  <Typography variant="h6" fontWeight="bold">
                    {lead.name}
                  </Typography>
                </Box>
                {state.user?.permissions.can_edit && (
                  <IconButton
                    size="small"
                    onClick={(e) => handleMenuOpen(e, lead)}
                  >
                    <MoreVert />
                  </IconButton>
                )}
              </Box>

              <Box display="flex" alignItems="center" gap={1}>
                <FolderOpen fontSize="small" color="action" />
                <Typography variant="body2" color="text.secondary">
                  Project Lead
                </Typography>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      {leads.length === 0 && (
        <Box textAlign="center" py={8}>
          <Person sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No project leads found
          </Typography>
          <Typography color="text.secondary">
            Create your first project lead to get started
          </Typography>
        </Box>
      )}

      {/* Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => handleDialogOpen('edit', selectedLead!)}>
          <Edit fontSize="small" sx={{ mr: 1 }} />
          Edit
        </MenuItem>
        <MenuItem onClick={() => handleDialogOpen('delete', selectedLead!)}>
          <Delete fontSize="small" sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Create/Edit/Delete Dialog */}
      <Dialog open={dialogOpen} onClose={handleDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          {dialogType === 'create' && 'Create New Project Lead'}
          {dialogType === 'edit' && 'Edit Project Lead'}
          {dialogType === 'delete' && 'Delete Project Lead'}
        </DialogTitle>
        <DialogContent>
          {dialogType === 'delete' ? (
            <Typography>
              Are you sure you want to delete "{selectedLead?.name}"? This action cannot be undone.
            </Typography>
          ) : (
            <TextField
              fullWidth
              label="Name"
              value={formData.name}
              onChange={(e) => setFormData({ name: e.target.value })}
              margin="normal"
              required
              autoFocus
            />
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

export default ProjectLeads; 