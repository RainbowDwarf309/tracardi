from typing import Optional
from tracardi.context import get_context
from tracardi.domain.session import Session
from tracardi.domain.storage_record import RecordMetadata
from tracardi.service.storage.redis.cache import RedisCache
from tracardi.service.storage.redis.collections import Collection

redis_cache = RedisCache(ttl=None)


def load_session_cache(session_id: str, production):
    if not redis_cache.has(session_id, Collection.session):
        return None

    # start = time.time()

    context, session, session_metadata = redis_cache.get(
        session_id,
        f"{Collection.session}{production}:{session_id[0:2]}:")

    # print(session_metadata, flush=True)

    session = Session(**session)
    if session_metadata:
        session.set_meta_data(RecordMetadata(**session_metadata))

    # print("load session cache time", time.time() - start, flush=True)

    return session


def save_session_cache(session: Optional[Session]):
    if session:
        context = get_context()
        redis_cache.set(
            session.id,
            (
                {
                    "production": context.production,
                    "tenant": context.tenant
                },
                session.model_dump(mode="json", exclude_defaults=True),
                session.get_meta_data().model_dump() if session.has_meta_data() else None
            ),
            f"{Collection.session}{context.context_abrv()}:{session.id[0:2]}:"
        )
