from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Project, Case, Accession, Comment, ProjectLead

class AccessionInline(admin.TabularInline):
    model = Accession
    extra = 1

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ('user', 'created_at')

class CaseInline(admin.TabularInline):
    model = Case
    extra = 0
    show_change_link = True

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'other_id', 'project', 'status', 'tier', 'created_at', 'updated_at')
    list_filter = ('status', 'tier', 'project')
    search_fields = ('name', 'other_id', 'project__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [AccessionInline, CommentInline]

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'project_lead', 'created_by', 'created_at', 'updated_at', 'get_cases_count')
    list_filter = ('project_lead', 'created_by', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [CaseInline]
    
    def get_cases_count(self, obj):
        return obj.get_cases_count()
    get_cases_count.short_description = 'Cases'

@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_display = ('accession_number', 'case')
    list_filter = ('case__project',)
    search_fields = ('accession_number', 'case__name', 'case__project__name')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('case', 'user', 'created_at', 'get_short_text')
    list_filter = ('created_at', 'user', 'case__project')
    search_fields = ('text', 'case__name', 'user__username')
    readonly_fields = ('created_at',)
    
    def get_short_text(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    get_short_text.short_description = 'Comment'

# Extend UserAdmin to show group membership
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'get_groups')
    
    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    get_groups.short_description = 'Groups'

# Unregister the default UserAdmin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(ProjectLead)
class ProjectLeadAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
