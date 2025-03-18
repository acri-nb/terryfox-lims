from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Project, Case, Accession, Comment

class AccessionInline(admin.TabularInline):
    model = Accession
    extra = 1

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at', 'updated_at', 'get_cases_count')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def get_cases_count(self, obj):
        return obj.cases.count()
    get_cases_count.short_description = 'Cases'

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'status', 'tier', 'rna_coverage', 'dna_t_coverage', 'dna_n_coverage', 'created_at')
    list_filter = ('status', 'tier', 'project', 'created_at')
    search_fields = ('name', 'project__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [AccessionInline, CommentInline]
    
    fieldsets = (
        (None, {
            'fields': ('project', 'name', 'status', 'tier')
        }),
        ('Coverage Information', {
            'fields': ('rna_coverage', 'dna_t_coverage', 'dna_n_coverage')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

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
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_groups')
    
    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    get_groups.short_description = 'Groups'

# Unregister the default UserAdmin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
