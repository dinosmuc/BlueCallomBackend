from django.urls import path
from .views import ChatView, TestView, PromptView, AgentView, ExecutionView

urlpatterns = [
    path('chat/', ChatView.as_view(), name='chat'),
    path('test/', TestView.as_view(), name='test'),
    path('prompts/', PromptView.as_view(), name='prompts-list'),
    path('prompts/<int:prompt_id>/', PromptView.as_view(), name='prompt-detail'),
    path('prompts/<int:prompt_id>/execute/', PromptView.as_view(), name='execute-prompt'),
    path('agents/', AgentView.as_view(), name='agents-list'),
    path('agents/<int:agent_id>/', AgentView.as_view(), name='agent-detail'),
    path('agents/<int:agent_id>/execute/', AgentView.as_view(), name='execute-agent'),
    path('agents/<int:agent_id>/executions/', ExecutionView.as_view(), name='agent-executions'),
]
