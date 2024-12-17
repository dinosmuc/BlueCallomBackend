from rest_framework import serializers
from .models import Prompt, AgentVariable, AgentPrompt, AgentPromptBranch, AgentCondition, Agent
import logging

logger = logging.getLogger(__name__)

class PromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prompt
        fields = ['id', 'name', 'system_prompt', 'data_handling', 'default_user_prompt', 'prompt_type', 'generate_list', 'is_loop_prompt', 'loop_variable'] 

class AgentVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentVariable
        fields = ['name', 'default_value', 'variable_type']

class AgentPromptSerializer(serializers.ModelSerializer):
    prompt_id = serializers.PrimaryKeyRelatedField(
        source='prompt',
        queryset=Prompt.objects.all()
    )
    name = serializers.CharField(read_only=True, source='prompt.name')
    
    class Meta:
        model = AgentPrompt
        fields = ['prompt_id', 'order', 'name']

class AgentPromptBranchSerializer(serializers.ModelSerializer):
    prompt_id = serializers.PrimaryKeyRelatedField(
        source='prompt',
        queryset=Prompt.objects.all()
    )
    name = serializers.CharField(read_only=True, source='prompt.name')

    class Meta:
        model = AgentPromptBranch
        fields = ['prompt_id', 'branch_type', 'order', 'name']

class AgentConditionSerializer(serializers.ModelSerializer):
    true_branch = AgentPromptBranchSerializer(many=True, required=False)
    false_branch = AgentPromptBranchSerializer(many=True, required=False)
    
    class Meta:
        model = AgentCondition
        fields = ['id', 'variable_name', 'value', 'order', 'true_branch', 'false_branch']
    
    def create(self, validated_data):
        logger.debug(f"Creating AgentCondition with data: {validated_data}")
        true_branch_data = validated_data.pop('true_branch', [])
        false_branch_data = validated_data.pop('false_branch', [])
        
        condition = AgentCondition.objects.create(**validated_data)
        
        # Create true branch prompts
        for branch_data in true_branch_data:
            AgentPromptBranch.objects.create(
                condition=condition,
                prompt=branch_data['prompt'],
                branch_type='true',
                order=branch_data.get('order', 0)
            )
        
        # Create false branch prompts
        for branch_data in false_branch_data:
            AgentPromptBranch.objects.create(
                condition=condition,
                prompt=branch_data['prompt'],
                branch_type='false',
                order=branch_data.get('order', 0)
            )
        
        return condition

    def update(self, instance, validated_data):
        true_branch_data = validated_data.pop('true_branch', [])
        false_branch_data = validated_data.pop('false_branch', [])
        
        # Update condition fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Clear existing branches
        instance.branches.all().delete()
        
        # Recreate true branch prompts
        for branch_data in true_branch_data:
            AgentPromptBranch.objects.create(
                condition=instance,
                prompt=branch_data['prompt'],
                branch_type='true',
                order=branch_data.get('order', 0)
            )
        
        # Recreate false branch prompts
        for branch_data in false_branch_data:
            AgentPromptBranch.objects.create(
                condition=instance,
                prompt=branch_data['prompt'],
                branch_type='false',
                order=branch_data.get('order', 0)
            )
        
        return instance

    def validate_prompt_id(self, value):
        if not Prompt.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Invalid prompt_id provided.")
        return value

class AgentSerializer(serializers.ModelSerializer):
    variables = AgentVariableSerializer(many=True)
    prompts = AgentPromptSerializer(many=True)
    conditions = AgentConditionSerializer(many=True)
    
    class Meta:
        model = Agent
        fields = ['id', 'name', 'variables', 'prompts', 'conditions']

    def create(self, validated_data):
        variables_data = validated_data.pop('variables', [])
        prompts_data = validated_data.pop('prompts', [])
        conditions_data = validated_data.pop('conditions', [])
        
        agent = Agent.objects.create(**validated_data)
        
        # Create variables
        for variable_data in variables_data:
            AgentVariable.objects.create(agent=agent, **variable_data)
        
        # Create prompts
        for prompt_data in prompts_data:
            AgentPrompt.objects.create(agent=agent, **prompt_data)
            
        # Create conditions and their branches
        for condition_data in conditions_data:
            true_branch_data = condition_data.pop('true_branch', [])
            false_branch_data = condition_data.pop('false_branch', [])
            
            condition = AgentCondition.objects.create(
                agent=agent,
                variable_name=condition_data['variable_name'],
                value=condition_data['value'],
                order=condition_data['order']
            )
            
            # Create true branch prompts
            for branch_data in true_branch_data:
                AgentPromptBranch.objects.create(
                    condition=condition,
                    prompt=branch_data['prompt'],
                    branch_type='true',
                    order=branch_data['order']
                )
            
            # Create false branch prompts
            for branch_data in false_branch_data:
                AgentPromptBranch.objects.create(
                    condition=condition,
                    prompt=branch_data['prompt'],
                    branch_type='false',
                    order=branch_data['order']
                )
        
        return agent

    def update(self, instance, validated_data):
        variables_data = validated_data.pop('variables', [])
        prompts_data = validated_data.pop('prompts', [])
        conditions_data = validated_data.pop('conditions', [])
        
        # Update basic fields
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        
        # Update variables
        instance.variables.all().delete()
        for variable_data in variables_data:
            AgentVariable.objects.create(
                agent=instance,
                name=variable_data['name'],
                default_value=variable_data.get('default_value', ''),
                variable_type=variable_data.get('variable_type', 'text')
            )
        
        # Update prompts
        instance.prompts.all().delete()
        for prompt_data in prompts_data:
            AgentPrompt.objects.create(
                agent=instance,
                prompt=prompt_data['prompt'],
                order=prompt_data['order']
            )
        
        # Update conditions and their branches
        instance.conditions.all().delete()
        for condition_data in conditions_data:
            true_branch_data = condition_data.pop('true_branch', [])
            false_branch_data = condition_data.pop('false_branch', [])
            
            condition = AgentCondition.objects.create(
                agent=instance,
                variable_name=condition_data['variable_name'],
                value=condition_data['value'],
                order=condition_data['order']
            )
            
            # Create true branch prompts
            for branch_data in true_branch_data:
                AgentPromptBranch.objects.create(
                    condition=condition,
                    prompt=branch_data['prompt'],
                    branch_type='true',
                    order=branch_data['order']
                )
            
            # Create false branch prompts
            for branch_data in false_branch_data:
                AgentPromptBranch.objects.create(
                    condition=condition,
                    prompt=branch_data['prompt'],
                    branch_type='false',
                    order=branch_data['order']
                )
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation