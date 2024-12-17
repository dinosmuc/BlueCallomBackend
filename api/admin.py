from django.contrib import admin
from .models import Prompt, Agent, AgentVariable, AgentPrompt

admin.site.register(Prompt)
admin.site.register(Agent)
admin.site.register(AgentVariable)
admin.site.register(AgentPrompt)

