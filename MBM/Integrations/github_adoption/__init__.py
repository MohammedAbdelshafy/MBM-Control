"""Optional integrations selected by the GitHub intelligence/adoption pipeline.

This package is deliberately dependency-light. External runtimes are optional and
must be installed only inside an isolated evaluation environment.
"""

from .catalog import ADOPTION_CATALOG, RepositorySpec
from .security import assert_public_url, wrap_untrusted_content

__all__ = [
    "ADOPTION_CATALOG",
    "RepositorySpec",
    "assert_public_url",
    "wrap_untrusted_content",
]
