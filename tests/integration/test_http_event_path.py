from fastapi.testclient import TestClient

from services.simulator.http import create_app


def test_stale_cursor_replay_is_not_new_admission_or_motion(tmp_path):
    from test_protocol_commands import command_event
    from test_service_admission import control
    with TestClient(create_app(root=tmp_path)) as client:
        client.post('/episodes', json={'episode_id':'physical','scenario':'SC-001','seed':3})
        first = control('f',1,'FENCE_INSTALL',{'task_id':'task','task_fence':1,'resource_fences':{'corridor':1}})
        assert client.post('/events',json=first.model_dump(mode='json')).json()['status']=='ACCEPTED'
        cmd=command_event(sequence=2,until=100)
        assert client.post('/events',json=cmd.model_dump(mode='json')).json()['status']=='ACCEPTED'
        assert client.post('/events',json=cmd.model_dump(mode='json')).json()['status']=='REPLAY'
        assert client.get('/state').json()['started_commands']==1
        assert client.post('/advance',json={'ticks':2}).status_code==200
        assert client.get('/commands/cmd').json()['state']=='CONTROLLER_DONE'
