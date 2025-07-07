from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Project, Case, Accession, Comment, ProjectLead


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_superuser']


class ProjectLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLead
        fields = ['id', 'name']


class AccessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ['id', 'accession_number']


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'text', 'user', 'created_at']


class CaseSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    accessions = AccessionSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    
    class Meta:
        model = Case
        fields = [
            'id', 'name', 'other_id', 'status', 'status_display', 'tier', 'tier_display',
            'rna_coverage', 'dna_t_coverage', 'dna_n_coverage',
            'created_at', 'updated_at', 'comments', 'accessions'
        ]


class ProjectSerializer(serializers.ModelSerializer):
    project_lead = ProjectLeadSerializer(read_only=True)
    project_lead_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    cases = CaseSerializer(many=True, read_only=True)
    cases_count = serializers.IntegerField(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'project_lead', 'project_lead_id',
            'created_at', 'updated_at', 'created_by', 'cases', 'cases_count'
        ]
    
    def create(self, validated_data):
        project_lead_id = validated_data.pop('project_lead_id', None)
        project = Project.objects.create(**validated_data)
        
        if project_lead_id:
            try:
                project_lead = ProjectLead.objects.get(id=project_lead_id)
                project.project_lead = project_lead
                project.save()
            except ProjectLead.DoesNotExist:
                pass
        
        return project
    
    def update(self, instance, validated_data):
        project_lead_id = validated_data.pop('project_lead_id', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if project_lead_id is not None:
            if project_lead_id:
                try:
                    project_lead = ProjectLead.objects.get(id=project_lead_id)
                    instance.project_lead = project_lead
                except ProjectLead.DoesNotExist:
                    pass
            else:
                instance.project_lead = None
        
        instance.save()
        return instance


class ProjectListSerializer(serializers.ModelSerializer):
    """Simplified serializer for project lists"""
    project_lead = ProjectLeadSerializer(read_only=True)
    cases_count = serializers.IntegerField(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'project_lead',
            'created_at', 'updated_at', 'created_by', 'cases_count'
        ]


class CaseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = [
            'name', 'other_id', 'status', 'rna_coverage', 'dna_t_coverage', 'dna_n_coverage'
        ]


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['text'] 