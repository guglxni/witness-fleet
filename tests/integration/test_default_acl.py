import pytest
from isolated_acl_fixture import isolated_acl_server  # noqa: F401
from redis import Redis
from redis.exceptions import AuthenticationError, ResponseError


@pytest.mark.integration
def test_unauthenticated_default_connection_cannot_ping_or_query_graph(isolated_acl_server):  # noqa: F811
    client = Redis(host=isolated_acl_server.host, port=isolated_acl_server.port, socket_timeout=2)
    try:
        with pytest.raises((AuthenticationError, ResponseError)):
            client.ping()
        with pytest.raises((AuthenticationError, ResponseError)):
            client.execute_command('GRAPH.RO_QUERY', 'wf:demo:ops', 'MATCH (n) RETURN n LIMIT 1')
    finally:
        client.close()


@pytest.mark.integration
def test_readonly_role_cannot_write_or_read_cross_tenant_key(isolated_acl_server):  # noqa: F811
    client = Redis(host=isolated_acl_server.host, port=isolated_acl_server.port,
                   username='wf_read', socket_timeout=2)
    try:
        assert client.execute_command('GRAPH.RO_QUERY', 'wf:demo:ops', 'MATCH (n) RETURN count(n)')
        with pytest.raises(ResponseError):
            client.execute_command('GRAPH.QUERY', 'wf:demo:ops', 'CREATE (:AclDeniedProbe)')
        with pytest.raises(ResponseError):
            client.execute_command('GRAPH.RO_QUERY', 'wf:other:ops', 'MATCH (n) RETURN count(n)')
    finally:
        client.close()


@pytest.mark.integration
def test_named_health_role_has_no_graph_authority(isolated_acl_server):  # noqa: F811
    client = Redis(host=isolated_acl_server.host, port=isolated_acl_server.port,
                   username='wf_health', socket_timeout=2)
    try:
        assert client.ping() is True
        with pytest.raises(ResponseError):
            client.execute_command('GRAPH.RO_QUERY', 'wf:demo:ops', 'MATCH (n) RETURN n LIMIT 1')
    finally:
        client.close()
