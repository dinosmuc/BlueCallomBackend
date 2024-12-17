from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import generate_completion, Prompt, Agent, execute_agent
from .serializers import PromptSerializer, AgentSerializer
import json
import logging
import traceback

logger = logging.getLogger(__name__)

class ChatView(APIView):
    def format_json_to_markdown(self, json_str):
        try:
            # Parse JSON if it's a string
            if isinstance(json_str, str):
                data = json.loads(json_str)
            else:
                data = json_str

            # If there's a "summary" field, use it directly
            if isinstance(data, dict) and "summary" in data:
                return data["summary"]

            # For other JSON structures, create a readable format
            if isinstance(data, dict):
                # Handle common story/content structures
                if "title" in data:
                    output = f"# {data['title']}\n\n"
                    
                    if "plot" in data:
                        plot = data["plot"]
                        output += f"{plot.get('introduction', '')}\n\n"
                        output += f"{plot.get('rising_action', '')}\n\n"
                        output += f"{plot.get('climax', '')}\n\n"
                        output += f"{plot.get('falling_action', '')}\n\n"
                        output += f"{plot.get('conclusion', '')}\n\n"
                    
                    if "theme" in data:
                        output += f"**Theme**: {data['theme']}"
                    
                    return output
                
                # For other JSON objects, create a readable format
                return "\n".join([f"**{k}**: {v}" for k, v in data.items()])
            
            return str(data)

        except json.JSONDecodeError:
            # If it's not JSON, return as is
            return json_str

    def post(self, request):
        try:
            message = request.data.get('message')
            system_prompt = request.data.get('system_prompt', "You are a helpful assistant.")
            
            if not message:
                return Response(
                    {'error': 'Message is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            response = generate_completion(system_prompt, message)
            
            if isinstance(response, dict) and 'error' in response:
                return Response(
                    response, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Format the response before sending it to the frontend
            formatted_response = self.format_json_to_markdown(response['response'])
                
            return Response({
                'response': formatted_response
            })

        except Exception as e:
            print(f"Error in ChatView: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TestView(APIView):
    def get(self, request):
        return Response({'message': 'Test endpoint working'})

class PromptView(APIView):
    def get(self, request, prompt_id=None):
        print(f"GET request received at PromptView. Path: {request.path}")  # Debug log
        if prompt_id:
            try:
                prompt = Prompt.objects.get(id=prompt_id)
                serializer = PromptSerializer(prompt)
                return Response(serializer.data)
            except Prompt.DoesNotExist:
                return Response(
                    {'error': 'Prompt not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        prompts = Prompt.objects.all()
        serializer = PromptSerializer(prompts, many=True)
        return Response(serializer.data)

    def post(self, request, prompt_id=None):
        # Handle prompt execution
        if prompt_id and 'execute' in request.path:
            try:
                prompt = Prompt.objects.get(id=prompt_id)
                input_data = request.data.get('input', '')
                system_prompt = request.data.get('system_prompt', prompt.system_prompt)
                user_prompt = request.data.get('user_prompt', prompt.default_user_prompt or input_data)

                result = generate_completion(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )

                if isinstance(result, dict) and 'error' in result:
                    return Response(
                        {'error': result['error']},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                return Response({
                    'response': result['response'],
                    'variable_updates': result.get('variable_updates', {})
                })

            except Prompt.DoesNotExist:
                return Response(
                    {'error': 'Prompt not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Handle new prompt creation
        else:
            serializer = PromptSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def put(self, request, prompt_id):
        try:
            prompt = Prompt.objects.get(id=prompt_id)
            serializer = PromptSerializer(prompt, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Prompt.DoesNotExist:
            return Response(
                {'error': 'Prompt not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, prompt_id):
        try:
            prompt = Prompt.objects.get(id=prompt_id)
            prompt.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Prompt.DoesNotExist:
            return Response(
                {'error': 'Prompt not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class AgentView(APIView):
    def get(self, request, agent_id=None):
        if agent_id:
            try:
                agent = Agent.objects.get(id=agent_id)
                serializer = AgentSerializer(agent)
                return Response(serializer.data)
            except Agent.DoesNotExist:
                return Response(
                    {'error': 'Agent not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            agents = Agent.objects.all()
            serializer = AgentSerializer(agents, many=True)
            return Response(serializer.data)

    def post(self, request, agent_id=None):
        if agent_id and 'execute' in request.path:
            try:
                input_data = request.data.get('input')
                human_inputs = request.data.get('human_inputs')
                result = execute_agent(agent_id, input_data, human_inputs)
                
                if 'error' in result:
                    return Response(
                        {'error': result['error']},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                    
                return Response({
                    'status': 'complete',
                    'execution_result': {
                        'response': result['response'],
                        'variables': result['variables'],
                        'prompt_outputs': result['prompt_outputs']
                    }
                })

            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Handle new agent creation
        else:
            serializer = AgentSerializer(data=request.data)
            if serializer.is_valid():
                instance = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def put(self, request, agent_id):
        try:
            agent = Agent.objects.get(id=agent_id)
            serializer = AgentSerializer(agent, data=request.data)
            
            if serializer.is_valid():
                instance = serializer.save()
                return Response(serializer.data)
                
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Agent.DoesNotExist:
            return Response(
                {'error': 'Agent not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, agent_id):
        try:
            agent = Agent.objects.get(id=agent_id)
            agent.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Agent.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

class ExecutionView(APIView):
    def get(self, request, agent_id):
        # Get the latest execution for this agent
        try:
            agent = Agent.objects.get(id=agent_id)
            # You might want to store executions in the database
            # For now, we'll just return the last execution result
            return Response({
                'status': 'success',
                'executions': []  # You can implement storage of past executions
            })
        except Agent.DoesNotExist:
            return Response({'error': 'Agent not found'}, status=404)

