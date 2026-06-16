import time
from typing import Optional

from .merge import MergeResult, merge_trees
from .objects import Commit
from .service import VCSError, VCSService


def cherry_pick(service: VCSService, commit_oid: str, author: Optional[str] = None) -> MergeResult:
    """Apply the changes introduced by commit_oid onto the current HEAD."""
    commit = Commit.read(service.objects, commit_oid)
    if not commit.parents:
        raise VCSError("cannot cherry-pick a commit with no parents")

    parent_oid = commit.parents[0]
    parent_tree = Commit.read(service.objects, parent_oid).tree

    head_oid = service.refs.get_head()
    if head_oid is None:
        raise VCSError("no commits on current branch")
    head_tree = Commit.read(service.objects, head_oid).tree

    result = merge_trees(service.objects, parent_tree, head_tree, commit.tree)
    service._checkout_tree(result.tree_oid)

    if not result.conflicts:
        new_commit = Commit(
            tree=result.tree_oid,
            parents=[head_oid],
            author=author or commit.author,
            committer=author or commit.author,
            message=commit.message,
            timestamp=time.time(),
        )
        oid = new_commit.write(service.objects)
        service.refs.update_head(oid)

    return result
