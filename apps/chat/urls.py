from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('<int:conversation_id>/', views.conversation_view, name='conversation'),
    path('<int:conversation_id>/messages/', views.messages_partial_view, name='messages_partial'),
    path('<int:conversation_id>/kirim/', views.send_message_view, name='send_message'),
    path('mulai/<slug:item_slug>/', views.start_conversation_view, name='start_conversation'),
    path('mulai-jual/<slug:sale_slug>/', views.start_sale_conversation_view, name='start_sale_conversation'),
]
