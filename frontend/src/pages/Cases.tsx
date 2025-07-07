import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Alert,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Search,
  Science,
} from '@mui/icons-material';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';

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
  project: {
    id: number;
    name: string;
  };
}

const Cases: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [tierFilter, setTierFilter] = useState('');
  const [error, setError] = useState('');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const projectFilter = searchParams.get('project');

  const fetchCases = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (searchTerm) params.append('name', searchTerm);
      if (statusFilter) params.append('status', statusFilter);
      if (tierFilter) params.append('tier', tierFilter);
      if (projectFilter) params.append('project', projectFilter);

      const response = await axios.get(`/cases/?${params.toString()}`);
      setCases(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching cases:', error);
      setError('Failed to load cases');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, statusFilter, tierFilter, projectFilter]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

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
        <Typography variant="h4" gutterBottom>
          Cases
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" fontWeight="bold" mb={3}>
        Cases ({cases.length})
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Search and Filter */}
      <Box display="flex" gap={2} mb={3} flexWrap="wrap">
        <TextField
          placeholder="Search cases..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
          sx={{ flexGrow: 1, minWidth: 200 }}
        />
        <FormControl sx={{ minWidth: 150 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            label="Status"
          >
            <MenuItem value="">All Status</MenuItem>
            <MenuItem value="received">Received</MenuItem>
            <MenuItem value="library_prepped">Library Prepped</MenuItem>
            <MenuItem value="transferred_to_nfl">Transferred to NFL</MenuItem>
            <MenuItem value="bioinfo_analysis">Bioinfo Analysis</MenuItem>
            <MenuItem value="completed">Completed</MenuItem>
          </Select>
        </FormControl>
        <FormControl sx={{ minWidth: 120 }}>
          <InputLabel>Tier</InputLabel>
          <Select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            label="Tier"
          >
            <MenuItem value="">All Tiers</MenuItem>
            <MenuItem value="A">Tier A</MenuItem>
            <MenuItem value="B">Tier B</MenuItem>
            <MenuItem value="FAIL">Tier FAIL</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Cases Grid */}
      <Box
        display="grid"
        gridTemplateColumns="repeat(auto-fill, minmax(350px, 1fr))"
        gap={3}
      >
        {cases.map((case_) => (
          <Card
            key={case_.id}
            sx={{
              cursor: 'pointer',
              '&:hover': {
                boxShadow: 4,
              },
            }}
            onClick={() => navigate(`/cases/${case_.id}`)}
          >
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                {case_.name}
              </Typography>

              <Typography variant="body2" color="text.secondary" gutterBottom>
                Project: {case_.project.name}
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

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2">
                  <strong>RNA:</strong> {case_.rna_coverage || '--'} M
                </Typography>
                <Typography variant="body2">
                  <strong>DNA (T):</strong> {case_.dna_t_coverage || '--'} X
                </Typography>
                <Typography variant="body2">
                  <strong>DNA (N):</strong> {case_.dna_n_coverage || '--'} X
                </Typography>
              </Box>

              <Typography variant="caption" color="text.secondary">
                Created: {new Date(case_.created_at).toLocaleDateString()}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>

      {cases.length === 0 && (
        <Box textAlign="center" py={8}>
          <Science sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No cases found
          </Typography>
          <Typography color="text.secondary">
            {searchTerm || statusFilter || tierFilter
              ? 'Try adjusting your search criteria'
              : 'No cases available'}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default Cases; 