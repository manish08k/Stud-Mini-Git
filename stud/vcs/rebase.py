from typing import List

from .cherry_pick import cherry_pick
from .merge import MergeResult
from .objects import Commit
from .service import VCSError, VCSService


def rebase(service: VCSService, onto: str, branch: str) -> List[MergeResult]:
    """
    Replay the commits unique to `branch` (since its merge-base with `onto`)
    on top of `onto`, then move `branch` to the new tip.

    Stops and returns early if any cherry-pick produces conflicts.
    """
    onto_oid = service.refs.resolve(onto)
    branch_oid = service.refs.resolve(branch)
    if onto_oid is None:
        raise VCSError(f"unknown revision: {onto}")
    if branch_oid is None:
        raise VCSError(f"unknown revision: {branch}")

    base_oid = service.merge_base(onto_oid, branch_oid)

    to_replay_oids: List[str] = []
    oid = branch_oid
    while oid and oid != base_oid:
        to_replay_oids.append(oid)
        commit = Commit.read(service.objects, oid)
        oid = commit.parents[0] if commit.parents else None

    to_replay_oids.reverse()

    if onto_oid == base_oid and not to_replay_oids:
        return []

    service.checkout(onto)
    results: List[MergeResult] = []

    for commit_oid in to_replay_oids:
        result = cherry_pick(service, commit_oid)
        results.append(result)
        if result.conflicts:
            return results

    new_tip = service.refs.get_head()
    service.refs.update_branch(branch, new_tip)
    service.refs.set_head_symbolic(branch)

    return results
