from django.urls import path
from . import views

urlpatterns = [
    # Home page
    path('', views.home, name='home'),
    
    # Project URLs
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:project_id>/update/', views.project_update, name='project_update'),
    path('projects/<int:project_id>/delete/', views.project_delete, name='project_delete'),
    
    # Case URLs
    path('cases/<int:case_id>/', views.case_detail, name='case_detail'),
    path('projects/<int:project_id>/cases/create/', views.case_create, name='case_create'),
    path('projects/<int:project_id>/cases/batch/', views.batch_case_create, name='batch_case_create'),
    path('projects/<int:project_id>/cases/import-csv/', views.csv_case_import, name='csv_case_import'),
    path('cases/<int:case_id>/delete/', views.case_delete, name='case_delete'),
    
    # Project Lead URLs
    path('project-leads/', views.project_lead_list, name='project_lead_list'),
    path('project-leads/create/', views.project_lead_create, name='project_lead_create'),
    path('project-leads/<int:lead_id>/update/', views.project_lead_update, name='project_lead_update'),
    path('project-leads/<int:lead_id>/delete/', views.project_lead_delete, name='project_lead_delete'),
] 