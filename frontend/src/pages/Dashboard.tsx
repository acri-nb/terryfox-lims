import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  LinearProgress,
  Avatar,
} from '@mui/material';
// Grid import removed - using Box with CSS Grid instead
import {
  FolderOpen,
  Science,
  TrendingUp,
  People,
  Add,
} from '@mui/icons-material';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

interface Statistics {
  total_projects: number;
  total_cases: number;
  projects_by_lead: Array<{ project_lead__name: string; count: number }>;
  cases_by_status: Array<{ status: string; count: number }>;
  cases_by_tier: Array<{ tier: string; count: number }>;
}

const Dashboard: React.FC = () => {
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { state } = useAuth();

  useEffect(() => {
    const fetchStatistics = async () => {
      try {
        const response = await axios.get('/projects/statistics/');
        setStatistics(response.data);
      } catch (error) {
        console.error('Error fetching statistics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStatistics();
  }, []);

  const getStatusColor = (status: string) => {
    const colors: { [key: string]: string } = {
      received: '#f39c12',
      library_prepped: '#3498db',
      transferred_to_nfl: '#9b59b6',
      bioinfo_analysis: '#e74c3c',
      completed: '#27ae60',
    };
    return colors[status] || '#95a5a6';
  };

  const getTierColor = (tier: string) => {
    const colors: { [key: string]: string } = {
      A: '#27ae60',
      B: '#f39c12',
      FAIL: '#e74c3c',
    };
    return colors[tier] || '#95a5a6';
  };

  const formatStatusName = (status: string) => {
    const names: { [key: string]: string } = {
      received: 'Received',
      library_prepped: 'Library Prepped',
      transferred_to_nfl: 'Transferred to NFL',
      bioinfo_analysis: 'Bioinfo Analysis',
      completed: 'Completed',
    };
    return names[status] || status;
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  if (!statistics) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <Typography>Error loading statistics</Typography>
      </Box>
    );
  }

  const statusData = statistics.cases_by_status.map(item => ({
    name: formatStatusName(item.status),
    value: item.count,
    color: getStatusColor(item.status),
  }));

  const tierData = statistics.cases_by_tier.map(item => ({
    name: `Tier ${item.tier}`,
    value: item.count,
    color: getTierColor(item.tier),
  }));

  const projectLeadData = statistics.projects_by_lead.slice(0, 5).map(item => ({
    name: item.project_lead__name || 'Not specified',
    projects: item.count,
  }));

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Typography variant="h4" fontWeight="bold">
          Dashboard
        </Typography>
        {(state.user?.permissions.can_edit) && (
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => navigate('/projects')}
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

      {/* Statistics Cards */}
      <Box
        display="grid"
        gridTemplateColumns="repeat(auto-fit, minmax(250px, 1fr))"
        gap={3}
        mb={4}
      >
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Total Projects
                </Typography>
                <Typography variant="h4" fontWeight="bold">
                  {statistics.total_projects}
                </Typography>
              </Box>
              <Avatar sx={{ bgcolor: 'primary.main', width: 56, height: 56 }}>
                <FolderOpen />
              </Avatar>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Total Cases
                </Typography>
                <Typography variant="h4" fontWeight="bold">
                  {statistics.total_cases}
                </Typography>
              </Box>
              <Avatar sx={{ bgcolor: 'secondary.main', width: 56, height: 56 }}>
                <Science />
              </Avatar>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Active Projects
                </Typography>
                <Typography variant="h4" fontWeight="bold">
                  {statistics.projects_by_lead.length}
                </Typography>
              </Box>
              <Avatar sx={{ bgcolor: 'success.main', width: 56, height: 56 }}>
                <TrendingUp />
              </Avatar>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Project Leads
                </Typography>
                <Typography variant="h4" fontWeight="bold">
                  {statistics.projects_by_lead.filter(p => p.project_lead__name).length}
                </Typography>
              </Box>
              <Avatar sx={{ bgcolor: 'warning.main', width: 56, height: 56 }}>
                <People />
              </Avatar>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Charts */}
      <Box display="flex" flexDirection="column" gap={3}>
        <Box
          display="grid"
          gridTemplateColumns={{ xs: '1fr', md: '1fr 1fr' }}
          gap={3}
        >
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Cases by Status
              </Typography>
              <Box height={300}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statusData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {statusData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Cases by Tier
              </Typography>
              <Box height={300}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={tierData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {tierData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Box>

        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight="bold" gutterBottom>
              Projects by Lead
            </Typography>
            <Box height={300}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={projectLeadData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="projects" fill="#667eea" />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </CardContent>
        </Card>

        {/* Quick Status Overview */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight="bold" gutterBottom>
              Status Overview
            </Typography>
            <Box display="flex" gap={2} flexWrap="wrap">
              {statistics.cases_by_status.map((status) => (
                <Chip
                  key={status.status}
                  label={`${formatStatusName(status.status)}: ${status.count}`}
                  sx={{
                    backgroundColor: getStatusColor(status.status),
                    color: 'white',
                    fontWeight: 'bold',
                  }}
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default Dashboard; 