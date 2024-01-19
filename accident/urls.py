from django.urls import path
from . import views

urlpatterns = [
    path('hello-world/', views.hello_world, name='hello_world'),
    path('get-file-analysis', views.get_file_analysis, name='get_file_analysis'),
    path('get-answer', views.get_answer, name="get_answer"),
]
