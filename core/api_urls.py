from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .api_views import (
    ProjectViewSet, CaseViewSet, ProjectLeadViewSet,
    CommentViewSet, AccessionViewSet, UserViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'cases', CaseViewSet, basename='case')
router.register(r'project-leads', ProjectLeadViewSet, basename='projectlead')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'accessions', AccessionViewSet, basename='accession')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
] 