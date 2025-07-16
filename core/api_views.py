from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.contrib.auth.models import User

from .models import Project, Case, Accession, Comment, ProjectLead
from .serializers import (
    ProjectSerializer, ProjectListSerializer, CaseSerializer, 
    CommentSerializer, AccessionSerializer, ProjectLeadSerializer,
    CaseCreateSerializer, CommentCreateSerializer, UserSerializer
)


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing projects
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        queryset = Project.objects.annotate(cases_count=Count('cases')).select_related('project_lead', 'created_by')
        
        # Filter by project lead
        project_lead = self.request.query_params.get('project_lead', None)
        if project_lead:
            queryset = queryset.filter(project_lead_id=project_lead)
        
        # Filter by name
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get project statistics"""
        total_projects = Project.objects.count()
        total_cases = Case.objects.count()
        
        projects_by_lead = Project.objects.values('project_lead__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        cases_by_status = Case.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        cases_by_tier = Case.objects.values('tier').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'total_projects': total_projects,
            'total_cases': total_cases,
            'projects_by_lead': projects_by_lead,
            'cases_by_status': cases_by_status,
            'cases_by_tier': cases_by_tier,
        })


class CaseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cases
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CaseSerializer
    
    def get_queryset(self):
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = Case.objects.filter(project_id=project_id)
        else:
            queryset = Case.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by tier
        tier = self.request.query_params.get('tier', None)
        if tier:
            queryset = queryset.filter(tier=tier)
        
        # Filter by name
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        return queryset.select_related('project').prefetch_related('comments__user', 'accessions').order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CaseCreateSerializer
        return CaseSerializer
    
    def perform_create(self, serializer):
        project_id = self.request.data.get('project_id')
        project = Project.objects.get(id=project_id)
        serializer.save(project=project)
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add a comment to a case"""
        case = self.get_object()
        serializer = CommentCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(case=case, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_accession(self, request, pk=None):
        """Add an accession number to a case"""
        case = self.get_object()
        accession_number = request.data.get('accession_number')
        
        if accession_number:
            accession = Accession.objects.create(
                case=case,
                accession_number=accession_number
            )
            serializer = AccessionSerializer(accession)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response({'error': 'Accession number is required'}, status=status.HTTP_400_BAD_REQUEST)


class ProjectLeadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project leads
    """
    queryset = ProjectLead.objects.all().order_by('name')
    serializer_class = ProjectLeadSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def projects(self, request, pk=None):
        """Get projects for a specific project lead"""
        project_lead = self.get_object()
        projects = project_lead.projects.annotate(cases_count=Count('cases'))
        serializer = ProjectListSerializer(projects, many=True)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing comments
    """
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        case_id = self.request.query_params.get('case', None)
        if case_id:
            return Comment.objects.filter(case_id=case_id).select_related('user').order_by('-created_at')
        return Comment.objects.all().select_related('user').order_by('-created_at')


class AccessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing accession numbers
    """
    serializer_class = AccessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        case_id = self.request.query_params.get('case', None)
        if case_id:
            return Accession.objects.filter(case_id=case_id)
        return Accession.objects.all()


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user information
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user information"""
        serializer = UserSerializer(request.user)
        user_data = serializer.data
        
        # Add user groups information
        user_data['groups'] = [group.name for group in request.user.groups.all()]
        user_data['permissions'] = {
            'can_edit': request.user.groups.filter(name='editor').exists() or request.user.is_superuser,
            'is_admin': request.user.is_superuser,
            'is_viewer': request.user.groups.filter(name='viewer').exists(),
            'is_editor': request.user.groups.filter(name='editor').exists(),
        }
        
        return Response(user_data) 