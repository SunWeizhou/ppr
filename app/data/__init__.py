"""Data layer — protocols, constants, and in-memory store."""
from app.data.interfaces import (
    AgentRepository,
    CollectionRepository,
    EntityRepository,
    EventRepository,
    EvidenceClaimRepository,
    JobRepository,
    KeyValueRepository,
    PaperRepository,
    QueueRepository,
    RecommendationRepository,
    ResearchQuestionRepository,
    SearchRepository,
    StateStoreProtocol,
    SubscriptionRepository,
    UserProfileRepository,
)
from app.data._constants import (
    JOB_STATUS_VALUES,
    QUEUE_STATUS_VALUES,
    canonical_paper_id,
    utc_now,
)
