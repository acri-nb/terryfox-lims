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
  Science,
  FolderOpen,
} from '@mui/icons-material';
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
  updated_at: string;
  project: {
    id: number;
    name: string;
  };
  comments: Array<{
    id: number;
    text: string;
    user: {
      id: number;
      username: string;
    };
    created_at: string;
  }>;
  accessions: Array<{
    id: number;
    accession_number: string;
  }>;
}

const CaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [case_, setCase] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchCase = useCallback(async () => {
    try {
      const response = await axios.get(`/cases/${id}/`);
      setCase(response.data);
    } catch (error) {
      console.error('Error fetching case:', error);
      setError('Failed to load case');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) {
      fetchCase();
    }
  }, [id, fetchCase]);

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
          onClick={() => navigate('/cases')}
          sx={{ mb: 2 }}
        >
          Back to Cases
        </Button>
        <Typography variant="h4" gutterBottom>
          Loading Case...
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  if (error || !case_) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/cases')}
          sx={{ mb: 2 }}
        >
          Back to Cases
        </Button>
        <Alert severity="error">{error || 'Case not found'}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate('/cases')}
        sx={{ mb: 2 }}
      >
        Back to Cases
      </Button>

      <Typography variant="h4" fontWeight="bold" mb={3}>
        {case_.name}
      </Typography>

      {/* Case Info */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              Case Information
            </Typography>
            <Box display="flex" gap={1}>
              <Chip
                label={case_.status_display}
                color={getStatusColor(case_.status)}
              />
              <Chip
                label={`Tier ${case_.tier}`}
                color={getTierColor(case_.tier)}
              />
            </Box>
          </Box>

          <Box display="flex" alignItems="center" gap={1} mb={2}>
            <FolderOpen fontSize="small" color="action" />
            <Typography variant="body2">
              <strong>Project:</strong> {case_.project.name}
            </Typography>
          </Box>

          <Typography variant="body2" sx={{ mb: 1 }}>
            <strong>Created:</strong> {new Date(case_.created_at).toLocaleDateString()}
          </Typography>
          <Typography variant="body2">
            <strong>Last Updated:</strong> {new Date(case_.updated_at).toLocaleDateString()}
          </Typography>
        </CardContent>
      </Card>

      {/* Coverage Information */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Coverage Information
          </Typography>
          
          <Box
            display="grid"
            gridTemplateColumns="repeat(auto-fit, minmax(200px, 1fr))"
            gap={2}
          >
            <Box>
              <Typography variant="body2" color="text.secondary">
                RNA Coverage
              </Typography>
              <Typography variant="h5" fontWeight="bold">
                {case_.rna_coverage || '--'} <small>M</small>
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                DNA (T) Coverage
              </Typography>
              <Typography variant="h5" fontWeight="bold">
                {case_.dna_t_coverage || '--'} <small>X</small>
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                DNA (N) Coverage
              </Typography>
              <Typography variant="h5" fontWeight="bold">
                {case_.dna_n_coverage || '--'} <small>X</small>
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Accession Numbers */}
      {case_.accessions.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Accession Numbers
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap">
              {case_.accessions.map((accession) => (
                <Chip
                  key={accession.id}
                  label={accession.accession_number}
                  variant="outlined"
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Comments */}
      {case_.comments.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Comments ({case_.comments.length})
            </Typography>
            <Box display="flex" flexDirection="column" gap={2}>
              {case_.comments.map((comment) => (
                <Card key={comment.id} variant="outlined">
                  <CardContent sx={{ py: 2 }}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="subtitle2" fontWeight="bold">
                        {comment.user.username}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(comment.created_at).toLocaleDateString()}
                      </Typography>
                    </Box>
                    <Typography variant="body2">
                      {comment.text}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {case_.comments.length === 0 && case_.accessions.length === 0 && (
        <Card>
          <CardContent>
            <Box textAlign="center" py={4}>
              <Science sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
              <Typography variant="h6" color="text.secondary">
                No additional information
              </Typography>
              <Typography color="text.secondary">
                No comments or accession numbers available for this case
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default CaseDetail; 