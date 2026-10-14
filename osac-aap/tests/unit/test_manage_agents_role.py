"""Regression coverage for repairing already allocated scale-out Agents."""

from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar


TASKS_PATH = (
    Path(__file__).resolve().parents[2]
    / "collections/ansible_collections/osac/service/roles/manage_agents/tasks/select_and_label_new_agents.yml"
)


def _is_true(expression: str, variables: dict) -> bool:
    rendered = Templar(loader=DataLoader(), variables=variables).template("{{ " + expression + " }}")
    return rendered is True or str(rendered).lower() == "true"


def test_allocated_agents_without_role_are_repaired_when_scale_count_is_met() -> None:
    tasks = yaml.safe_load(TASKS_PATH.read_text(encoding="utf-8"))
    by_name = {task["name"]: (index, task) for index, task in enumerate(tasks)}
    listed_index, listed = by_name["List agents currently labeled with the cluster order label"]
    repair_index, repair = by_name["Set worker role on allocated agents without one"]
    add_index, add = by_name["Add agents to the cluster"]

    assert listed_index < repair_index < add_index
    assert listed["kubernetes.core.k8s_info"]["label_selectors"] == [
        "{{ cluster_order_label }}={{ manage_agents_cluster_order_name }}",
        "{{ agent_instance_type_label }}={{ manage_agents_instance_type }}",
    ]
    assert repair["loop"] == "{{ manage_agents_allocated.resources }}"
    assert repair["kubernetes.core.k8s_json_patch"] == {
        "api_version": "agent-install.openshift.io/v1beta1",
        "kind": "Agent",
        "name": "{{ agent.metadata.name }}",
        "namespace": "{{ agent.metadata.namespace }}",
        "patch": [{"op": "add", "path": "/spec/role", "value": "worker"}],
    }

    agents = [
        {"metadata": {"name": "missing"}, "spec": {"approved": True}},
        {"metadata": {"name": "empty"}, "spec": {"approved": True, "role": ""}},
        {"metadata": {"name": "null"}, "spec": {"approved": True, "role": None}},
        {"metadata": {"name": "worker"}, "spec": {"approved": True, "role": "worker"}},
        {"metadata": {"name": "other"}, "spec": {"approved": True, "role": "master"}},
    ]
    allocated = {"resources": agents}
    assert not _is_true(
        add["when"], {"manage_agents_desired_count": len(agents), "manage_agents_allocated": allocated}
    )
    assert [
        agent["metadata"]["name"]
        for agent in agents
        if _is_true(repair["when"], {"agent": agent})
    ] == ["missing", "empty", "null"]

    # Newly selected Agents still receive the role in the original selection patch.
    new_agent_patch = next(
        task for task in add["block"] if task["name"] == "Add selected agents to the cluster"
    )
    assert {"op": "add", "path": "/spec/role", "value": "worker"} in new_agent_patch[
        "kubernetes.core.k8s_json_patch"
    ]["patch"]
