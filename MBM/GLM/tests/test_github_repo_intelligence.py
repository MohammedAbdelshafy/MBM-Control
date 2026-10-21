from MBM.GLM.github_repo_intelligence import get_repo_pattern


def test_memory_contains_key_adopted_repos():
    for repo in (
        "langchain-ai/langgraph",
        "google/adk-python",
        "microsoft/playwright",
        "unclecode/crawl4ai",
        "triggerdotdev/trigger.dev",
        "obra/superpowers",
    ):
        assert get_repo_pattern(repo) is not None


def test_external_repos_are_pattern_layers():
    pattern = get_repo_pattern("langchain-ai/langgraph")
    assert pattern["boundary"] == "do_not_replace_glm_authority"
