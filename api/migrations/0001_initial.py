# Generated by Django 5.1.4 on 2024-12-17 00:28

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Prompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('system_prompt', models.TextField()),
                ('data_handling', models.TextField(blank=True)),
                ('default_user_prompt', models.TextField(blank=True)),
                ('prompt_type', models.CharField(choices=[('autonomous', 'Autonomous'), ('human', 'Human Input Required'), ('loop', 'Loop Prompt')], default='autonomous', max_length=20)),
                ('generate_list', models.BooleanField(default=False)),
                ('is_loop_prompt', models.BooleanField(default=False)),
                ('loop_variable', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='AgentVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('default_value', models.TextField(blank=True)),
                ('variable_type', models.CharField(choices=[('text', 'Text'), ('list', 'List')], default='text', max_length=20)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variables', to='api.agent')),
            ],
        ),
        migrations.CreateModel(
            name='AgentPrompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField()),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prompts', to='api.agent')),
                ('prompt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.prompt')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
