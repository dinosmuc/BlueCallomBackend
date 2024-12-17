import os
from dotenv import load_dotenv
from openai import OpenAI
from django.db import models
import re
import json
import traceback
import logging

load_dotenv()
client = OpenAI(api_key=os.getenv("BLUE_OPENAI_API_KEY"))
logger = logging.getLogger(__name__)

class Prompt(models.Model):
    PROMPT_TYPES = [
        ('autonomous', 'Autonomous'),
        ('human', 'Human Input Required'),
        ('loop', 'Loop Prompt')
    ]
    
    name = models.CharField(max_length=200)
    system_prompt = models.TextField()
    data_handling = models.TextField(blank=True)
    default_user_prompt = models.TextField(blank=True)
    prompt_type = models.CharField(max_length=20, choices=PROMPT_TYPES, default='autonomous')
    generate_list = models.BooleanField(default=False)
    is_loop_prompt = models.BooleanField(default=False)
    loop_variable = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

def generate_completion(system_prompt, user_prompt, data_handling=None, variables=None):
    try:
        variables = variables or {}
        
        # Add support for index access in variables
        for var_name, var_value in list(variables.items()):
            # Check for index access pattern ${variable[index]}
            pattern = rf'\${{{var_name}\[(\d+)\]}}'
            matches = re.finditer(pattern, system_prompt + user_prompt)
            
            for match in matches:
                # Convert 1-based index to 0-based index
                index = int(match.group(1)) - 1  # Subtract 1 to convert from 1-based to 0-based
                full_match = match.group(0)
                
                try:
                    # Handle both string-encoded lists and actual lists
                    if isinstance(var_value, str):
                        try:
                            list_value = json.loads(var_value)
                        except json.JSONDecodeError:
                            list_value = var_value.split(',')
                    else:
                        list_value = var_value
                        
                    if isinstance(list_value, list) and 0 <= index < len(list_value):
                        item_value = list_value[index]
                        system_prompt = system_prompt.replace(full_match, str(item_value))
                        user_prompt = user_prompt.replace(full_match, str(item_value))
                    else:
                        print(f"Warning: Index {index + 1} is out of range for variable {var_name}")
                except (IndexError, TypeError):
                    print(f"Warning: Could not access index {index + 1} in variable {var_name}")
                    continue
            
            # Handle regular variable replacement
            system_prompt = system_prompt.replace(f"${{{var_name}}}", str(var_value))
            user_prompt = user_prompt.replace(f"${{{var_name}}}", str(var_value))

        print(f"Sending prompt - System: {system_prompt}")
        print(f"Sending prompt - User: {user_prompt}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        output = response.choices[0].message.content
        print(f"Raw output: {output}")

        result = {
            'response': output,
            'variable_updates': {}
        }

        if data_handling and 'append output to' in data_handling:
            var_name = data_handling.split('$$')[-1].strip()
            print(f"Target variable name: {var_name}")
            
            # For list generation prompts, ensure proper JSON format
            if output.startswith('[') and output.endswith(']'):
                try:
                    parsed_list = json.loads(output)
                    result['variable_updates'][var_name] = parsed_list
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract items from numbered list
                    items = []
                    for line in output.split('\n'):
                        clean_line = re.sub(r'^\d+\.\s*', '', line.strip())
                        if clean_line:
                            items.append(clean_line)
                    result['variable_updates'][var_name] = items
            else:
                # For non-list outputs
                current_list = variables.get(var_name, []) if variables else []
                if isinstance(current_list, str):
                    current_list = json.loads(current_list) if current_list else []
                if not isinstance(current_list, list):
                    current_list = []
                current_list.append(output)
                result['variable_updates'][var_name] = current_list

        print(f"Final result with updates: {result}")
        return result

    except Exception as e:
        print(f"Error in generate_completion: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {'error': str(e)}

class Agent(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class AgentVariable(models.Model):
    VARIABLE_TYPES = [
        ('text', 'Text'),
        ('list', 'List'),
    ]
    
    agent = models.ForeignKey(Agent, related_name='variables', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    default_value = models.TextField(blank=True)
    variable_type = models.CharField(max_length=20, choices=VARIABLE_TYPES, default='text')

    def __str__(self):
        return f"{self.agent.name} - {self.name} ({self.variable_type})"

class AgentPrompt(models.Model):
    agent = models.ForeignKey(Agent, related_name='prompts', on_delete=models.CASCADE)
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE)
    order = models.IntegerField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.agent.name} - {self.prompt.name} (Order: {self.order})"

class AgentCondition(models.Model):
    agent = models.ForeignKey(Agent, related_name='conditions', on_delete=models.CASCADE)
    variable_name = models.CharField(max_length=200)  # Which variable to check
    value = models.CharField(max_length=200)         # Value to compare against
    order = models.IntegerField()                    # Position in workflow

    class Meta:
        ordering = ['order']

    def get_true_branches(self):
        return self.branches.filter(branch_type='true')

    def get_false_branches(self):
        return self.branches.filter(branch_type='false')

class AgentPromptBranch(models.Model):
    BRANCH_TYPES = [
        ('true', 'True Branch'),
        ('false', 'False Branch')
    ]
    
    condition = models.ForeignKey(AgentCondition, related_name='branches', on_delete=models.CASCADE)
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE)
    branch_type = models.CharField(max_length=5, choices=BRANCH_TYPES)
    order = models.IntegerField()  # Order within the branch

    class Meta:
        ordering = ['order']

def execute_agent(agent_id, input_data=None, human_inputs=None):
    try:
        logger.info(f"Starting agent execution: agent_id={agent_id}, input_data={input_data}")
        agent = Agent.objects.get(id=agent_id)
        variables = {}
        
        # Initialize variables
        for var in agent.variables.all():
            logger.info(f"Initializing variable: {var.name} = {var.default_value}")
            variables[var.name] = var.default_value
            
        if input_data:
            variables['input'] = input_data
            
        prompt_outputs = []
        last_output = None
        
        # Log workflow items
        items = []
        for agent_prompt in agent.prompts.all():
            logger.info(f"Adding prompt to workflow: {agent_prompt.prompt.name} (order={agent_prompt.order})")
            items.append({
                'order': agent_prompt.order,
                'type': 'prompt',
                'item': agent_prompt
            })

        items.sort(key=lambda x: x['order'])
        logger.info(f"Sorted workflow items: {[{'type': i['type'], 'order': i['order']} for i in items]}")
        
        # Execute items in order
        for item in items:
            if item['type'] == 'prompt':
                agent_prompt = item['item']
                prompt = agent_prompt.prompt
                logger.info(f"Executing prompt: {prompt.name} (type={prompt.prompt_type})")
                
                if prompt.is_loop_prompt:
                    logger.info(f"Processing loop prompt with variable: {prompt.loop_variable}")
                    result = process_loop_prompt(prompt, variables)
                    if result:
                        iterations, updated_variables = result
                        logger.info(f"Loop prompt results: {len(iterations)} iterations")
                        prompt_outputs.append({
                            'type': 'loop',
                            'name': prompt.name,
                            'iterations': iterations
                        })
                        variables.update(updated_variables)
                        last_output = '\n\n'.join([iter['output'] for iter in iterations])
                else:
                    result = process_prompt(prompt, variables, human_inputs)
                    logger.info(f"Regular prompt result: {result}")
                    if result and result['status'] == 'complete':
                        prompt_outputs.append({
                            'type': 'prompt',
                            'name': prompt.name,
                            'output': result['response']
                        })
                        last_output = result['response']
                        if 'variable_updates' in result:
                            logger.info(f"Updating variables: {result['variable_updates']}")
                            variables.update(result['variable_updates'])
        
        logger.info(f"Agent execution completed. Final variables: {variables}")
        logger.info(f"Prompt outputs: {prompt_outputs}")
        
        return {
            'status': 'complete',
            'response': last_output,
            'variables': variables,
            'prompt_outputs': prompt_outputs
        }
        
    except Exception as e:
        logger.error(f"Error executing agent: {str(e)}", exc_info=True)
        return {'error': str(e)}

def process_loop_prompt(prompt, variables):
    logger.info(f"Starting loop prompt processing: {prompt.name}")
    logger.info(f"Loop variable: {prompt.loop_variable}")
    logger.info(f"Available variables: {variables}")
    
    list_var = variables.get(prompt.loop_variable)
    logger.info(f"List variable value: {list_var}")
    
    try:
        # Parse list variable
        if isinstance(list_var, str):
            try:
                items = json.loads(list_var)
                logger.info(f"Successfully parsed JSON list: {items}")
            except json.JSONDecodeError:
                items = [item.strip() for item in list_var.split('\n') if item.strip()]
                logger.info(f"Parsed as newline-separated list: {items}")
        elif isinstance(list_var, list):
            items = list_var
            logger.info(f"Using existing list: {items}")
        else:
            logger.error(f"Invalid list variable type: {type(list_var)}")
            raise ValueError(f"Invalid loop variable type: {type(list_var)}")

        iterations = []
        
        for idx, item in enumerate(items):
            logger.info(f"Processing iteration {idx + 1}/{len(items)}: {item}")
            iteration_variables = variables.copy()
            iteration_variables['item'] = item
            
            # Replace ${item} with actual item value in user prompt
            user_prompt = prompt.default_user_prompt.replace('${item}', str(item))
            logger.info(f"Formatted user prompt: {user_prompt}")
            
            result = generate_completion(
                system_prompt=prompt.system_prompt,
                user_prompt=user_prompt,
                data_handling=prompt.data_handling,
                variables=iteration_variables
            )
            
            logger.info(f"Iteration {idx + 1} result: {result}")
            iterations.append({
                'item': item,
                'output': result['response']
            })
            
        logger.info(f"Loop processing completed. Total iterations: {len(iterations)}")
        return iterations, variables
            
    except Exception as e:
        logger.error(f"Error in process_loop_prompt: {str(e)}", exc_info=True)
        return [], variables

def process_prompt(prompt, variables, human_inputs=None):
    try:
        # Handle human input prompts
        if prompt.prompt_type == 'human':
            if not human_inputs or prompt.id not in human_inputs:
                return {
                    'status': 'waiting_for_human_input',
                    'prompt_id': prompt.id,
                    'output_data': None
                }
            user_input = human_inputs[prompt.id]
        else:
            user_input = prompt.default_user_prompt

        # Handle loop prompts
        if prompt.is_loop_prompt:
            iterations, updated_variables = process_loop_prompt(prompt, variables)
            return {
                'status': 'complete',
                'response': iterations,
                'variable_updates': updated_variables,
                'output_data': {
                    'prompt_name': prompt.name,
                    'iterations': iterations
                }
            }

        # Regular prompt processing
        result = generate_completion(
            system_prompt=prompt.system_prompt,
            user_prompt=user_input,
            data_handling=prompt.data_handling,
            variables=variables
        )

        return {
            'status': 'complete',
            'response': result['response'],
            'variable_updates': result.get('variable_updates', {}),
            'output_data': {
                'prompt_name': prompt.name,
                'output': result['response']
            }
        }

    except Exception as e:
        print(f"Error processing prompt: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'output_data': None
        }







