"""
Kanban pipeline – maps task status to the next agent and next status.

Flow:
  backlog → [DevelopmentAgent] → dev
  dev     → [QAAgent]         → qa
  qa      → [DocAgent]        → docs
  docs    → [DeployAgent]     → deploy
  deploy  →                   → done
"""
from __future__ import annotations

from agents.deploy_agent import DeployAgent
from agents.development_agent import DevelopmentAgent
from agents.documentation_agent import DocumentationAgent
from agents.qa_agent import QAAgent
from agents.base_agent import BaseAgent
from database.models import AgentName, TaskStatus

# Ordered pipeline stages
PIPELINE: list[tuple[TaskStatus, BaseAgent, AgentName, TaskStatus]] = [
    (TaskStatus.BACKLOG,  DevelopmentAgent,    AgentName.DEVELOPMENT,  TaskStatus.DEV),
    (TaskStatus.DEV,      QAAgent,             AgentName.QA,           TaskStatus.QA),
    (TaskStatus.QA,       DocumentationAgent,  AgentName.DOCUMENTATION, TaskStatus.DOCS),
    (TaskStatus.DOCS,     DeployAgent,         AgentName.DEPLOY,       TaskStatus.DEPLOY),
]

# current_status → (AgentClass, agent_name_enum, next_status)
STAGE_MAP: dict[TaskStatus, tuple[type[BaseAgent], AgentName, TaskStatus]] = {
    from_status: (agent_cls, agent_name, to_status)
    for from_status, agent_cls, agent_name, to_status in PIPELINE
}
