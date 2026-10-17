"""Read-only retained graph barrier identity validation, never a policy grant."""
import json
from datetime import UTC, datetime

from witness_fleet.domain import DispatchEvent


def validate_barrier(graph, event, *, holder_id, now_utc):
    """Bind one immutable outbox barrier to exact current holder/epoch/UTC lease."""
    if (not isinstance(event, DispatchEvent) or event.kind != 'EPOCH_BARRIER'
            or event.tenant_id != graph.tenant_id or not isinstance(holder_id, str) or not holder_id
            or not isinstance(now_utc, datetime) or now_utc.tzinfo is None
            or now_utc.utcoffset() != UTC.utcoffset(now_utc)):
        raise ValueError('typed tenant barrier, configured holder and explicit UTC required')
    event = DispatchEvent.model_validate(event.model_dump(mode='json'))
    before = graph.read_version_root()
    retained = graph._query(
        'MATCH (n) WHERE n.tenant_id=$tenant AND n.id=$id '
        'RETURN labels(n) AS labels,properties(n) AS properties',
        {'tenant': graph.tenant_id, 'id': event.id}).result_set
    after = graph.read_version_root()
    if before != after or not isinstance(after, dict) or len(retained) != 1:
        raise ValueError('unstable or ambiguous retained barrier')
    labels, row = retained[0][0], dict(retained[0][1])
    try:
        values = {key: row[key] for key in DispatchEvent.model_fields if key != 'payload'}
        values['payload'] = json.loads(row['payload_json'])
        if (labels != ['DispatchEvent'] or DispatchEvent.model_validate(values) != event
                or row.get('event_id') != event.id or json.loads(row['subject_ids_json']) != []):
            raise ValueError('retained barrier identity mismatch')
        epoch, sequence = after['coordinator_epoch'], after['dispatch_sequence']
        expires = after['coordinator_lease_expires_at_utc']
        lease = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if (after.get('tenant_id') != graph.tenant_id
                or any(type(after[key]) is not int or after[key] < 0
                       for key in ('coordinator_epoch', 'dispatch_sequence', 'graph_version'))
                or after['coordinator_holder_id'] != holder_id or epoch != event.coordinator_epoch
                or sequence < event.sequence or lease.tzinfo is None
                or lease.utcoffset() != UTC.utcoffset(lease) or lease <= now_utc
                or event.payload != {'coordinator_epoch': epoch, 'holder_id': holder_id,
                                     'lease_expires_at_utc': expires}):
            raise ValueError('barrier is not bound to a current live lease')
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError('invalid retained barrier or current lease') from exc
    return graph.tenant_id, holder_id, epoch, expires
