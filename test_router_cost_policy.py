"""No remote inference before an explicitly configured free provider."""
from unittest.mock import patch

import router


def test_disabled_remote_llm_never_calls_any_provider():
    with patch.object(router, 'REMOTE_LLM_ENABLED', False), patch.object(router, '_post_chat') as post:
        result = router.route_chat([{'role': 'user', 'content': 'test'}])
    assert result.ok is False
    assert result.provider == 'none'
    post.assert_not_called()


def test_explicitly_enabled_router_preserves_primary_route():
    expected = router.RouteResult(ok=True, provider='omniroute', content='fixture')
    with patch.object(router, 'REMOTE_LLM_ENABLED', True), patch.object(router, '_post_chat', return_value=expected) as post:
        result = router.route_chat([{'role': 'user', 'content': 'test'}])
    assert result is expected
    post.assert_called_once()
