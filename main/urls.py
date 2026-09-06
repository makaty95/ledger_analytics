from . import views
from django.urls import path

urlpatterns = [
    path("", views.main_view, name="main-view"),
    path("connect/", views.connect_db, name="init-connection-endpoint"),
    path("query/", views.chat, name="chatbot-endpoint"),
    path("results/", views.results_page, name="results-page-retrieval-endpoint"),
    path("init_connection/", views.init_connection, name="init-connect-view"),
path("disconnect/", views.disconnect, name="disconnect-db")
]