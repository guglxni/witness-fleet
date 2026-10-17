import pytest
from isolated_acl_fixture import isolated_acl_server  # noqa: F401
from redis import Redis
from redis.exceptions import NoPermissionError


@pytest.mark.integration
def test_corpus_role_cannot_read_or_write_cross_key(isolated_acl_server):  # noqa: F811
    corpus = Redis(host=isolated_acl_server.host, port=isolated_acl_server.port,
                   username="wf_corpus", decode_responses=True)
    try:
        with pytest.raises(NoPermissionError):
            corpus.execute_command("GRAPH.RO_QUERY", "wf:demo:ops", "MATCH (n) RETURN count(n)")
        with pytest.raises(NoPermissionError):
            corpus.execute_command("GRAPH.QUERY", "wf:demo:ops", "MATCH (n) RETURN count(n)")
    finally:
        corpus.close()
